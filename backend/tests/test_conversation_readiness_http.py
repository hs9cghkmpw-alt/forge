"""Conversation Readiness のHTTP統合テスト
(FORGE-CONVERSATION-READY-001、2026-08-12、指示書14章 Integration/Failure)。

`test_converse_and_update_http.py`と同じく、`app.main`をimportする前に
Feature Flagのenv varを設定する(既存のテスト分離バグ対策、TD42参照)。
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# `app.main`はプロセス内で一度しかimportされないため、Feature Flagを
# 立てる前にimportすると、以降の全テストでrouterが登録されないままに
# なる(TD42で実際に踏んだ事故)。import順に依存する副作用を避ける。
# 値は必ず`"true"`にすること。`feature_flags.py`は`== "true"`で判定
# しており、`"1"`はFalse扱いになる。しかもこのファイルは
# `test_converse_and_update_http.py`より辞書順で先に読み込まれるため、
# ここで`"1"`を`setdefault`すると、後続ファイルの正しい`setdefault`が
# 「既に設定済み」として無視され、**Folder/Workspaceのrouterが
# プロセス全体で登録されないまま**になる(実際にこれで7件落とした)。
os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from app.main import app  # noqa: E402

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False

from app.ai.runtime.conversation_metrics import default_conversation_metrics  # noqa: E402
from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationReadiness,
    ConversationStepResult,
    NeedModel,
    UnknownImpact,
    UnknownItem,
)
from app.ai.runtime.pipeline_errors import ForgeValidationError, PlanningError  # noqa: E402


def _step(action: ConversationAction, **kwargs: Any) -> ConversationStepResult:
    defaults: dict[str, Any] = {
        "need_model": NeedModel(problem="p"),
        "readiness": ConversationReadiness.BUILD_READY,
    }
    defaults.update(kwargs)
    return ConversationStepResult(action=action, **defaults)


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestConverseAskCarriesReadiness(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_ask_response_reports_readiness_and_records_the_question_key(self) -> None:
        step = _step(
            ConversationAction.ASK,
            question="何を記録したいですか?", question_key="what_to_track",
            readiness=ConversationReadiness.NEEDS_QUESTION,
            need_model=NeedModel(
                problem="p",
                unknowns=(UnknownItem(key="what_to_track", impact=UnknownImpact.BLOCKING, reason="未定"),),
            ),
        )
        with patch("app.routers.ai.ConversationEngine") as engine_cls:
            engine_cls.return_value.step.return_value = step
            response = self.client.post(
                "/api/v1/ai/converse", json={"message": "何か作って", "provider": "mock"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ask")
        self.assertEqual(body["readiness"], "needs_question")
        self.assertEqual(body["need_model"]["unknowns"][0]["impact"], "blocking")
        self.assertEqual(body["need_model"]["unknowns"][0]["reason"], "未定")

    def test_insufficient_information_is_reported_as_such(self) -> None:
        step = _step(
            ConversationAction.ASK, question="もう一度だけ",
            readiness=ConversationReadiness.INSUFFICIENT_INFORMATION,
        )
        with patch("app.routers.ai.ConversationEngine") as engine_cls:
            engine_cls.return_value.step.return_value = step
            response = self.client.post(
                "/api/v1/ai/converse", json={"message": "うーん", "provider": "mock"},
            )
        self.assertEqual(response.json()["readiness"], "insufficient_information")


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestConverseConfirmResponse(unittest.TestCase):
    """指示書4章: CONFIRMが会話の1ターンとして返る。"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_confirm_action_returns_a_confirm_status_with_a_reason(self) -> None:
        step = _step(
            ConversationAction.CONFIRM,
            question="家族へ送信しますか?",
            confirm_reason="Forgeの外(他の人・外部サービス)へ影響が及ぶため",
            readiness=ConversationReadiness.NEEDS_CONFIRMATION,
        )
        with patch("app.routers.ai.ConversationEngine") as engine_cls:
            engine_cls.return_value.step.return_value = step
            response = self.client.post(
                "/api/v1/ai/converse", json={"message": "これを家族にも送って", "provider": "mock"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "confirm")
        self.assertEqual(body["question"], "家族へ送信しますか?")
        self.assertIn("外", body["reason"])
        self.assertTrue(body["session_id"])

    def test_confirm_keeps_the_session_alive_so_the_user_can_answer(self) -> None:
        """確認は会話の続きである——セッションを破棄してはならない。"""
        step = _step(
            ConversationAction.CONFIRM, question="よいですか?",
            confirm_reason="r", readiness=ConversationReadiness.NEEDS_CONFIRMATION,
        )
        with patch("app.routers.ai.ConversationEngine") as engine_cls:
            engine_cls.return_value.step.return_value = step
            first = self.client.post(
                "/api/v1/ai/converse", json={"message": "全部削除して", "provider": "mock"},
            )
            session_id = first.json()["session_id"]
            second = self.client.post(
                "/api/v1/ai/converse",
                json={"session_id": session_id, "message": "はい", "provider": "mock"},
            )
        self.assertEqual(second.status_code, 200, second.text)


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestBuildFailureFallback(unittest.TestCase):
    """指示書8章・14章(Failure): BUILD → Pipeline失敗 → 安全な着地。"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def _converse_with_failure(self, error: Exception):
        step = _step(ConversationAction.BUILD, build_brief="何かを作る")
        with patch("app.routers.ai.ConversationEngine") as engine_cls, \
                patch("app.routers.ai.PromptPipeline") as pipeline_cls:
            engine_cls.return_value.step.return_value = step
            pipeline_cls.return_value.run.side_effect = error
            return self.client.post(
                "/api/v1/ai/converse", json={"message": "何か作って", "provider": "mock"},
            )

    def test_understanding_stage_failure_returns_to_the_conversation(self) -> None:
        """原因が追加質問で解消しうるなら「作れませんでした」で終わらせない。"""
        response = self._converse_with_failure(
            PlanningError("入力が曖昧です", stage="domain_classification")
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "ask")
        self.assertIn("少しだけ確認させて", body["question"])
        self.assertEqual(body["readiness"], "insufficient_information")

    def test_validator_failure_is_reported_as_an_error_not_as_a_question(self) -> None:
        """指示書8章: AIの失敗をユーザーの情報不足のように見せない。"""
        response = self._converse_with_failure(
            ForgeValidationError("生成物がスキーマに適合しません", stage="validation")
        )
        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

    def test_a_recoverable_failure_keeps_the_session_for_the_next_turn(self) -> None:
        response = self._converse_with_failure(
            PlanningError("曖昧", stage="intent_recognition")
        )
        session_id = response.json()["session_id"]
        step = _step(ConversationAction.ASK, question="もう一度", question_key="k")
        with patch("app.routers.ai.ConversationEngine") as engine_cls:
            engine_cls.return_value.step.return_value = step
            follow_up = self.client.post(
                "/api/v1/ai/converse",
                json={"session_id": session_id, "message": "買い物リスト", "provider": "mock"},
            )
        self.assertEqual(follow_up.status_code, 200, follow_up.text)


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestConversationMetricsAreRecorded(unittest.TestCase):
    """指示書10章: 構造化メトリクスが実際に貯まる(本文は残さない)。"""

    def setUp(self) -> None:
        self.client = TestClient(app)
        default_conversation_metrics.reset()

    def test_ask_then_build_records_question_count_and_assumptions(self) -> None:
        ask = _step(
            ConversationAction.ASK, question="家族と使いますか?", question_key="shared_usage",
            readiness=ConversationReadiness.NEEDS_QUESTION,
        )
        with patch("app.routers.ai.ConversationEngine") as engine_cls:
            engine_cls.return_value.step.return_value = ask
            first = self.client.post(
                "/api/v1/ai/converse", json={"message": "買い物で忘れる", "provider": "mock"},
            )
        session_id = first.json()["session_id"]
        metrics = default_conversation_metrics.snapshot(session_id)
        self.assertEqual(metrics.questions_before_build, 1)

    def test_confirm_is_counted(self) -> None:
        step = _step(
            ConversationAction.CONFIRM, question="よいですか?", confirm_reason="r",
            readiness=ConversationReadiness.NEEDS_CONFIRMATION,
        )
        with patch("app.routers.ai.ConversationEngine") as engine_cls:
            engine_cls.return_value.step.return_value = step
            response = self.client.post(
                "/api/v1/ai/converse", json={"message": "家族に送って", "provider": "mock"},
            )
        metrics = default_conversation_metrics.snapshot(response.json()["session_id"])
        self.assertEqual(metrics.confirm_count, 1)

    def test_build_failure_fallback_is_counted(self) -> None:
        step = _step(ConversationAction.BUILD, build_brief="b")
        with patch("app.routers.ai.ConversationEngine") as engine_cls, \
                patch("app.routers.ai.PromptPipeline") as pipeline_cls:
            engine_cls.return_value.step.return_value = step
            pipeline_cls.return_value.run.side_effect = PlanningError(
                "曖昧", stage="domain_classification"
            )
            response = self.client.post(
                "/api/v1/ai/converse", json={"message": "何か", "provider": "mock"},
            )
        metrics = default_conversation_metrics.snapshot(response.json()["session_id"])
        self.assertEqual(metrics.build_failure_count, 1)
        self.assertEqual(metrics.build_to_ask_fallback_count, 1)

    def test_metrics_never_store_raw_conversation_text(self) -> None:
        """Privacy方針(指示書10章)の構造的な確認: 記録APIは本文を
        受け取る引数を持たない。"""
        import inspect

        signature = inspect.signature(default_conversation_metrics.record)
        self.assertEqual(
            set(signature.parameters) - {"self"},
            {"session_id", "action", "readiness", "question_key",
             "blocking_unknowns", "safe_assumptions"},
        )

    def test_session_ids_are_hashed_not_stored_verbatim(self) -> None:
        default_conversation_metrics.record("plain-session-id", "ask")
        with default_conversation_metrics._lock:  # noqa: SLF001 — 内部表現の確認が目的
            stored_keys = list(default_conversation_metrics._sessions)  # noqa: SLF001
        self.assertNotIn("plain-session-id", stored_keys)


if __name__ == "__main__":
    unittest.main()
