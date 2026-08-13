"""Anti-Bypass Regression(FORGE-AI-FOUNDATION-010 §10、2026-08-13)。

指示書の要求をそのまま引く:

> **AIRouterを呼べる** だけでは不十分。**AIRouterを通らずAIを呼べない**
> ことをRegression化してください。最低でも、Production HTTP Entry Point
> → AI Task → Injected FakeRouter を通し、Router invocationをassertして
> ください。今回のような、基盤はあるのにProductでは使っていなかった
> という問題を3回目起こさないでください。

---

## なぜこのテストが要るのか(2度起きた事故)

1. `ModelGateway`(FORGE-QUALITY-AI-INDEPENDENCE-003)——Task別Routingと
   fallbackを実装し、Unit Testも通っていたが、**本番から一度も
   構築されなかった**(TD59)。
2. `classify_correction`(FORGE-CONVERSATION-FOUNDATION-007 §10)——
   訂正意図の分類器を作ったが、`ConversationEngine`から呼んでいなかった。

どちらも「クラスがある + Unit Testが通る」を完成と数えたために起きた。
**呼べること**を測っても、**呼んでいること**は分からない。

## このテストの測り方

`ProviderRouter.resolve()`——「Provider名 → Adapter」の唯一の解決口——を
**爆発するように差し替える**。Routerを通る経路は、注入した
FakeRouter自身のresolveを使うので影響を受けない。Routerを通らずに
Adapterを取ってきて呼ぶ経路があれば、その瞬間に`BypassDetected`が
上がる。

「Routerを呼んでいるか」をassertするだけでは足りない——Routerも呼び、
**かつ**別経路でも呼んでいる、という状態を見逃す。塞ぐべきは
「Routerを通らない経路が存在しないこと」の方である。
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

try:
    from fastapi.testclient import TestClient

    from app.ai.foundation.providers import MockLLMAdapter
    from app.ai.gateway.ai_router import AIRouter, ModelDescriptor, RoutedResult
    from app.ai.gateway.tasks import ForgeTask
    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - 依存が無い環境
    _FASTAPI_AVAILABLE = False


class BypassDetected(AssertionError):
    """AIRouterを通らずにAdapterを解決しようとした。"""


class RecordingRouter(AIRouter):
    """本物の`AIRouter`。ただし呼ばれたTaskを記録する。

    挙動を差し替えた偽物ではなく**本物を継承している**のが要点で、
    候補選択・失敗分類・Circuit Breakerといった実際のRouting処理を
    そのまま通す。記録だけを足している。
    """

    def __init__(self) -> None:
        self.calls: list[tuple[ForgeTask, str]] = []
        super().__init__(
            # Routerに渡すresolveだけは生き残る。これが「Router経由の
            # 呼び出し」の唯一の入口になる。
            resolve=lambda name: MockLLMAdapter(),
            catalog=(ModelDescriptor(provider="mock", is_local=True, test_only=False),),
        )

    def generate(
        self,
        task: ForgeTask,
        prompt: str,
        response_schema: dict[str, Any],
        *,
        provider: str | None = None,
    ) -> RoutedResult:
        self.calls.append((task, prompt))
        return super().generate(task, prompt, response_schema, provider=provider)

    @property
    def tasks(self) -> list[ForgeTask]:
        return [task for task, _ in self.calls]


def _explode(name: str) -> Any:
    raise BypassDetected(
        f"AIRouterを通らずにProvider '{name}' を解決しようとしました。"
        "AI呼び出しは必ず AIRouter.bind()/generate() を経由してください。"
    )


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestNoAICallBypassesTheRouter(unittest.TestCase):
    """Production HTTP Entry Point → AI Task → Injected FakeRouter。"""

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)
        self.router = RecordingRouter()
        # `routers/ai.py`・`prompt_pipeline.py`はどちらも関数
        # `default_router()`を呼ぶので、モジュール変数を差し替えれば
        # 両方に届く(import時に値を束ねていないことも同時に検証される)。
        self._router_patch = patch(
            "app.ai.gateway.ai_router._default_router", self.router
        )
        # Router以外からのAdapter解決を全て失敗させる。
        self._resolve_patch = patch(
            "app.ai.runtime.provider_router.ProviderRouter.resolve", staticmethod(_explode)
        )
        self._router_patch.start()
        self._resolve_patch.start()
        self.addCleanup(self._router_patch.stop)
        self.addCleanup(self._resolve_patch.stop)

    # -- /converse ---------------------------------------------------------

    def test_converse_conversation_step_goes_through_the_router(self) -> None:
        response = self.client.post(
            "/api/v1/ai/converse", json={"message": "買い物で何を買うか忘れる"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(ForgeTask.CONVERSATION_STEP, self.router.tasks)

    def test_converse_build_path_runs_the_cognitive_pipeline_through_the_router(self) -> None:
        """`/converse`がBUILDまで進んだ場合、Cognitive Pipelineの
        AI呼び出しもRouterを通る。

        **ここが3例目の事故が起きていた場所である**: `/converse`の
        会話ステップだけがRouter経由で、生成本体
        (`PromptPipeline`→`ForgeAIProviderBridge`)は
        `ProviderRouter.resolve()`を直接呼んでいた。
        """
        response = self.client.post(
            "/api/v1/ai/converse", json={"message": "買い物で何を買うか忘れる"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "build", "この入力はBUILDまで進む想定")
        self.assertIn(ForgeTask.COGNITIVE_STAGE, self.router.tasks)

    # -- /generate ---------------------------------------------------------

    def test_generate_goes_through_the_router(self) -> None:
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "買い物メモを作りたい"}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(ForgeTask.COGNITIVE_STAGE, self.router.tasks)

    def test_generate_with_an_explicit_provider_still_goes_through_the_router(self) -> None:
        """Provider明示は**Routingを迂回する**が、**Routerは迂回しない**。

        この2つは別のことである。明示指定は「候補選びをしない」であって
        「Routerを通らない」ではない——通らなくなると、失敗分類も
        Circuit Breakerも効かなくなる。
        """
        response = self.client.post(
            "/api/v1/ai/generate",
            json={
                "version": "1.0",
                "input": {
                    "natural_language": "買い物メモを作りたい",
                    "generation_options": {"provider": "mock"},
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(ForgeTask.COGNITIVE_STAGE, self.router.tasks)

    # -- /update -----------------------------------------------------------

    _VALID_DOC = {
        "version": "1.0", "initial_screen_id": "s1", "app": {"title": "買い物メモ"},
        "screens": [{
            "id": "s1", "title": "買い物メモ",
            "state": {"items": {"type": "checklist", "value": []}},
            "body": {
                "type": "column", "id": "root",
                "children": [
                    {"type": "checklist", "id": "list_view", "state_ref": "items",
                     "empty_state_text": "まだありません"},
                ],
            },
        }],
    }

    def test_update_goes_through_the_router_with_its_own_task(self) -> None:
        """`/update`はRouterを通り、かつ**会話とは別のTask**で通る。

        mockは`response_schema={}`に対して`{}`を返すため、更新結果は
        Validator不合格(422)になる——それでよい。ここで見ているのは
        「AI呼び出しがRouterを通ったか」であって、更新の成否ではない。
        """
        response = self.client.post(
            "/api/v1/ai/update",
            json={"forge_document": self._VALID_DOC, "change_request": "予算も管理したい"},
        )
        self.assertIn(response.status_code, (200, 422), response.text)
        self.assertIn(ForgeTask.FORGE_LANGUAGE_UPDATE, self.router.tasks)

    # -- 迂回そのものの検出 -------------------------------------------------

    def test_the_guard_itself_actually_fires(self) -> None:
        """**このテストが何も検出できない置物になっていないこと**を確かめる。

        `_explode`が本当に効いているかを確認しないと、「迂回が無い」の
        ではなく「検出できていない」だけ、という状態に気付けない
        (Mockが常に成功する形のテストで何度も起きている失敗)。
        """
        from app.ai.runtime.provider_router import ProviderRouter

        with self.assertRaises(BypassDetected):
            ProviderRouter().resolve("mock")


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestRouterTasksAreDistinguished(unittest.TestCase):
    """Taskを渡していること自体を検証する。

    全部`CONVERSATION_STEP`で通っていても上のテストは通ってしまう。
    Task別profile(構造化出力の要求・時間予算・試行上限)は、正しい
    Taskが渡って初めて意味を持つ。
    """

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)
        self.router = RecordingRouter()
        patcher = patch("app.ai.gateway.ai_router._default_router", self.router)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_update_does_not_reuse_the_conversation_task(self) -> None:
        self.client.post(
            "/api/v1/ai/update",
            json={
                "forge_document": TestNoAICallBypassesTheRouter._VALID_DOC,
                "change_request": "予算も管理したい",
            },
        )
        self.assertEqual(self.router.tasks, [ForgeTask.FORGE_LANGUAGE_UPDATE] * len(self.router.tasks))
        self.assertTrue(self.router.tasks, "AI呼び出しが1回も記録されていない")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
