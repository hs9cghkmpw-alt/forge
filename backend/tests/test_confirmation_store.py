"""ConfirmationStoreのテスト(FORGE v0.2 P0.2・P1.7対応)。

fastapi/pydanticに依存しない、純粋なPythonロジックのため、この
サンドボックスでも実際に実行・検証できる。
"""

from __future__ import annotations

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.runtime.confirmation_store import (  # noqa: E402
    MAX_CONFIRMATION_ROUNDS,
    ConfirmationNotFoundError,
    ConfirmationRoundExceededError,
    ConfirmationStore,
)


class TestConfirmationStore(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ConfirmationStore()

    def test_create_returns_a_record_with_a_request_id(self) -> None:
        record = self.store.create(
            original_natural_language="福祉支援の記録を管理したい",
            engine="forge_ai",
            provider="mock",
            reached_stage="ambiguity_detection",
            reason="priority1_privacy_safety_permission",
        )
        self.assertTrue(record.request_id)
        self.assertEqual(record.round_count, 1)

    def test_get_returns_the_same_record(self) -> None:
        created = self.store.create(
            original_natural_language="test", engine="forge_ai", provider="mock",
            reached_stage="ambiguity_detection", reason="ambiguity_high_severity",
        )
        fetched = self.store.get(created.request_id)
        self.assertEqual(fetched.request_id, created.request_id)
        self.assertEqual(fetched.original_natural_language, "test")

    def test_get_unknown_request_id_raises_not_found(self) -> None:
        with self.assertRaises(ConfirmationNotFoundError):
            self.store.get("does-not-exist")

    def test_get_expired_record_raises_not_found_and_discards_it(self) -> None:
        created = self.store.create(
            original_natural_language="test", engine="forge_ai", provider="mock",
            reached_stage="ambiguity_detection", reason="x",
        )
        # 期限切れを直接シミュレートする(created_atを過去へ書き換える)。
        object.__setattr__(created, "created_at", time.time() - 3601 * 24)  # 十分に古い
        # storeにも同じインスタンスが入っているため、これで期限切れ扱いになる。
        with self.assertRaises(ConfirmationNotFoundError):
            self.store.get(created.request_id)
        self.assertEqual(self.store.size(), 0)  # discardされていること

    def test_consume_and_advance_invalidates_the_original_request_id(self) -> None:
        created = self.store.create(
            original_natural_language="福祉の記録を管理したい", engine="forge_ai", provider="mock",
            reached_stage="ambiguity_detection", reason="priority1_privacy_safety_permission",
        )
        self.store.consume_and_advance(created.request_id, answer="家族のみが対象です")
        with self.assertRaises(ConfirmationNotFoundError):
            self.store.get(created.request_id)  # 既に消費済み(discard済み)

    def test_consume_and_advance_returns_original_input_and_answer_separately(self) -> None:
        """FORGE v0.2 Final Gate P0.1の回帰テスト: 文字列結合(内部ラベル
        付き)は行わず、元の入力と回答を別々の値として返す。"""
        created = self.store.create(
            original_natural_language="福祉の記録を管理したい", engine="forge_ai", provider="mock",
            reached_stage="ambiguity_detection", reason="priority1_privacy_safety_permission",
        )
        _record, original, answer = self.store.consume_and_advance(created.request_id, answer="家族のみが対象です")
        self.assertEqual(original, "福祉の記録を管理したい")
        self.assertEqual(answer, "家族のみが対象です")
        # 内部管理用ラベル(「補足回答」等)がどちらの値にも混入していないこと。
        self.assertNotIn("補足回答", original)
        self.assertNotIn("補足回答", answer)

    def test_create_stores_previous_diagnostics_for_reconfirmation_tracking(self) -> None:
        """FORGE v0.2 Final Gate P0.7の回帰テスト: 再確認時に前回状態
        (ambiguity_report・domain_classification・decision_trace)を
        追跡できる。"""
        created = self.store.create(
            original_natural_language="test", engine="forge_ai", provider="mock",
            reached_stage="domain_classification", reason="priority2_low_domain_confidence",
            ambiguity_report={"overall_severity": "low", "issues": []},
            domain_classification={"primary_domain": "generic", "confidence": 0.2},
            decision_trace=({"stage": "domain_classification", "decision": "generic"},),
        )
        fetched = self.store.get(created.request_id)
        self.assertEqual(fetched.previous_ambiguity_report, {"overall_severity": "low", "issues": []})
        self.assertEqual(fetched.previous_domain_classification, {"primary_domain": "generic", "confidence": 0.2})
        self.assertEqual(len(fetched.previous_decision_trace), 1)

    def test_diagnostics_default_to_none_when_not_provided(self) -> None:
        """診断情報を渡さなかった場合、架空の値を作らずNoneのままにする
        (共通指示書「不明な内容を推測で断定すること」の禁止)。"""
        created = self.store.create(
            original_natural_language="test", engine="forge_ai", provider="mock",
            reached_stage="ambiguity_detection", reason="x",
        )
        self.assertIsNone(created.previous_ambiguity_report)
        self.assertIsNone(created.previous_domain_classification)
        self.assertEqual(created.previous_decision_trace, ())

    def test_round_limit_is_enforced(self) -> None:
        """MAX_CONFIRMATION_ROUNDS(既定3)に達した状態のセッションで
        回答しようとすると、無限に確認を繰り返さず打ち切られる。"""
        created = self.store.create(
            original_natural_language="test", engine="forge_ai", provider="mock",
            reached_stage="ambiguity_detection", reason="x",
            round_count=MAX_CONFIRMATION_ROUNDS,
        )
        with self.assertRaises(ConfirmationRoundExceededError) as ctx:
            self.store.consume_and_advance(created.request_id, answer="answer")
        self.assertEqual(ctx.exception.round_count, MAX_CONFIRMATION_ROUNDS)

    def test_round_limit_error_still_discards_the_session(self) -> None:
        """上限超過であっても、古いセッションを残さない(メモリリーク防止)。"""
        created = self.store.create(
            original_natural_language="test", engine="forge_ai", provider="mock",
            reached_stage="ambiguity_detection", reason="x",
            round_count=MAX_CONFIRMATION_ROUNDS,
        )
        with self.assertRaises(ConfirmationRoundExceededError):
            self.store.consume_and_advance(created.request_id, answer="answer")
        self.assertEqual(self.store.size(), 0)

    def test_discard_is_idempotent_for_unknown_ids(self) -> None:
        """存在しないrequest_idをdiscardしても例外を投げない。"""
        self.store.discard("does-not-exist")  # 例外が出ないことの確認

    def test_size_reflects_active_sessions(self) -> None:
        self.assertEqual(self.store.size(), 0)
        r1 = self.store.create(
            original_natural_language="a", engine="forge_ai", provider="mock",
            reached_stage="s", reason="r",
        )
        self.store.create(
            original_natural_language="b", engine="forge_ai", provider="mock",
            reached_stage="s", reason="r",
        )
        self.assertEqual(self.store.size(), 2)
        self.store.discard(r1.request_id)
        self.assertEqual(self.store.size(), 1)

    def test_sessions_are_isolated_per_store_instance(self) -> None:
        """モジュールレベルの`default_confirmation_store`と、テスト用に
        構築した独立インスタンスが状態を共有しないことを確認する
        (テストの独立性を担保する設計の裏付け)。"""
        from app.ai.runtime.confirmation_store import default_confirmation_store

        other_store = ConfirmationStore()
        record = other_store.create(
            original_natural_language="a", engine="forge_ai", provider="mock",
            reached_stage="s", reason="r",
        )
        with self.assertRaises(ConfirmationNotFoundError):
            default_confirmation_store.get(record.request_id)


if __name__ == "__main__":
    unittest.main()
