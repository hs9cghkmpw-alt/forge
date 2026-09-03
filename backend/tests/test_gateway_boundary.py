"""Provider境界 / Local Provider / Benchmark のテスト
(FORGE-QUALITY-AI-INDEPENDENCE-003 Phase F・G、2026-08-12。
FORGE-AI-FOUNDATION-010 Phase Bで`ModelGateway`削除に伴い整理)。

指示書1章「ForgeをGeminiを使うアプリにしてはならない」の、
実装上の境界を固定する。

**Routing/Fallbackそのもののテストはここには無い**。`AIRouter`
(`tests/test_ai_router.py`)が担当する。以前ここにあった
`ModelGateway`のRouting/Fallbackテストは、同じ責務の実装が2つ
あったために存在していたもので、実装の削除と共に落とした
(`test_ai_router.py`が同じ性質をより厳密に——失敗種別・Quota・
Circuit Breaker込みで——検査している)。
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.foundation.local_provider import (  # noqa: E402
    LocalModelError,
    LocalModelProvider,
    extract_json_object,
)
from app.ai.gateway.ai_router import AIRouter, ModelDescriptor  # noqa: E402
from app.ai.gateway.tasks import ForgeTask  # noqa: E402

import pytest

from app.ai.gateway.external_call_policy import allow_mocked_transport


# FORGE-EXTERNAL-CALL-DEFAULT-DENY(2026-09-03)。
#
# このファイルは `httpx.Client.post` を差し替えており、**ネットワークへは
# 一切出ない**。`external_call_policy` は既定で実 Provider への通信を拒否
# するので、「ここは出ていない」ことを明示的に宣言する。
#
# 環境変数ではなく呼び出し側の明示にしてあるのは、`.env` の中身で挙動が
# 変わる経路をもう一度作らないためである（それが 2026-09-02 の事故の形）。
@pytest.fixture(autouse=True)
def _network_is_mocked_in_this_module():
    with allow_mocked_transport():
        yield




class _FakeAdapter:
    def __init__(self, value: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self._value = value or {"ok": True}
        self._error = error
        self.calls = 0

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._value


def _router(adapters: dict[str, Any]) -> AIRouter:
    """名前付きのFake Adapter群を候補に持つ`AIRouter`。

    Benchmarkは常に`provider`を明示して呼ぶので、catalogの中身は
    候補選びには使われない。それでも実際の名前で登録しておくのは、
    明示指定が無い呼び方に変わったときに気付けるようにするため。
    """
    return AIRouter(
        resolve=lambda name: adapters[name],
        catalog=tuple(
            ModelDescriptor(provider=name, is_local=True) for name in adapters
        ),
    )


class TestRouterKnowsNoProviders(unittest.TestCase):
    """指示書1章: 上位ロジックはProviderを知らない。"""

    def test_the_router_module_does_not_import_any_concrete_provider(self) -> None:
        """Routerが特定Providerをimportしていたら、その時点で
        「交換可能な推論部品」という前提が崩れる。

        FORGE-AI-FOUNDATION-010 Phase B: 検査対象を`model_gateway.py`
        (削除済み)から`ai_router.py`へ移すと同時に、**判定方法を
        文字列検索からimport解析へ変えた**。

        以前は`assertNotIn("GeminiProvider", source)`だった。`ai_router.py`
        にはCatalogの設計判断を説明するコメントがあり、そこで
        「`GeminiProvider`が実装済みだから候補に載せている」と述べた
        だけで落ちた。**依存しているのか、依存について書いているのか**を
        区別できない検査だったということである。散文で落ちる検査は、
        いずれコメントを削って通される。

        測るべきは「具体的なProvider実装をimportしているか」なので、
        ASTのimport文だけを見る。
        """
        import ast

        import app.ai.gateway.ai_router as module

        with open(module.__file__, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(alias.name for alias in node.names)

        forbidden_names = {"GeminiProvider", "LocalModelProvider", "MockLLMAdapter"}
        forbidden_modules = {
            "google.generativeai", "google.genai", "genai", "openai", "anthropic",
            "app.ai.foundation.providers", "app.ai.foundation.local_provider",
        }
        self.assertEqual(
            imported & (forbidden_names | forbidden_modules), set(),
            f"Routerが具体的なProvider実装をimportしている: {imported & (forbidden_names | forbidden_modules)}",
        )
        # `ProviderRouter`(名前→Adapterの解決表)だけは`default_router()`が
        # 遅延importしてよい。Router本体はそれも知らずに動く
        # (`AIRouter.__init__`は`resolve`関数を受け取るだけ)。
        self.assertNotIn(
            "app.ai.foundation.interfaces", imported,
            "Router本体はAdapterの具体型にも依存しない(resolve関数を受け取るだけ)",
        )


class TestExtractJsonObject(unittest.TestCase):
    """小さいローカルモデルの「行儀の悪い」応答に耐えること。"""

    def test_plain_json(self) -> None:
        self.assertEqual(extract_json_object('{"a": 1}'), {"a": 1})

    def test_json_wrapped_in_a_code_fence(self) -> None:
        self.assertEqual(extract_json_object('```json\n{"a": 1}\n```'), {"a": 1})

    def test_json_with_surrounding_chatter(self) -> None:
        self.assertEqual(
            extract_json_object('はい、こちらです:\n{"a": 1}\n以上です。'), {"a": 1}
        )

    def test_unparseable_output_raises_instead_of_returning_empty(self) -> None:
        """TD40の教訓: 空dictを返して「成功」に見せかけない。"""
        with self.assertRaises(LocalModelError):
            extract_json_object("すみません、わかりません")

    def test_a_json_array_is_not_accepted_as_an_object(self) -> None:
        with self.assertRaises(LocalModelError):
            extract_json_object("[1, 2, 3]")


class TestLocalProviderContract(unittest.TestCase):
    """実モデル無しで検証できる範囲(HTTP契約の組み立て)。"""

    def test_it_is_configurable_and_not_hardwired_to_ollama(self) -> None:
        """指示書17章: Ollama固定にしない。"""
        provider = LocalModelProvider(base_url="http://example.test:8080/v1", model="llama3.2:1b")
        self.assertEqual(provider.model, "llama3.2:1b")
        self.assertEqual(provider._base_url, "http://example.test:8080/v1")  # noqa: SLF001

    def test_environment_variables_configure_it(self) -> None:
        os.environ["FORGE_LOCAL_MODEL"] = "qwen2.5:0.5b-instruct"
        try:
            self.assertEqual(LocalModelProvider().model, "qwen2.5:0.5b-instruct")
        finally:
            del os.environ["FORGE_LOCAL_MODEL"]

    def test_connection_failure_becomes_a_clear_local_model_error(self) -> None:
        """Runtimeが起動していない環境でも、意味の分かる例外にする
        (`ModelGateway`がfallbackできるよう、例外型で識別可能にする)。"""
        provider = LocalModelProvider(base_url="http://127.0.0.1:1/v1", timeout_seconds=1.0)
        with self.assertRaises(LocalModelError) as caught:
            provider.complete_structured("test", {})
        self.assertIn("接続できません", str(caught.exception))

    def test_it_satisfies_the_llm_adapter_protocol(self) -> None:
        """`LLMAdapter`は`@runtime_checkable`ではないため、
        `isinstance`ではなく構造(呼べる`complete_structured`を持つか)で
        確認する。"""
        import inspect

        provider = LocalModelProvider()
        self.assertTrue(callable(provider.complete_structured))
        signature = inspect.signature(provider.complete_structured)
        self.assertEqual(list(signature.parameters), ["prompt", "response_schema"])


class TestGeminiIsJustOneProvider(unittest.TestCase):
    """指示書31章 最低条件D: Gemini SDKを使わなくてもForge AI Taskを
    実行できるProvider境界が存在すること。"""

    def test_the_conversation_engine_does_not_import_gemini(self) -> None:
        import app.ai.runtime.conversation_engine as module

        with open(module.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("GeminiProvider", source)
        self.assertNotIn("generativelanguage", source)

    def test_the_conversation_policy_does_not_import_any_provider(self) -> None:
        import app.ai.runtime.conversation_policy as module

        with open(module.__file__, encoding="utf-8") as handle:
            source = handle.read()
        for forbidden in ("Gemini", "genai", "httpx", "openai"):
            self.assertNotIn(forbidden, source)

    def test_a_conversation_step_runs_through_a_non_gemini_provider(self) -> None:
        """Geminiを一切使わずに、会話1ターンが最後まで通ること。"""
        from app.ai.runtime.conversation_engine import ConversationEngine
        from app.ai.runtime.conversation_types import (
            ConversationAction,
            ConversationSession,
            ConversationTurn,
        )

        class _NonGemini:
            def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
                return json.loads(json.dumps({
                    "problem": "買い物で忘れる", "known": [], "unknowns": [], "assumptions": [],
                    "confidence": 0.9, "next_action": "build", "question": "",
                    "question_key": "", "build_brief": "買い物リストを作る",
                    "external_effect": False, "destructive": False,
                }))

        session = ConversationSession(session_id="s").with_turn(
            ConversationTurn(role="user", text="買い物で何買うか忘れる")
        )
        result = ConversationEngine(_NonGemini()).step(session)
        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertEqual(result.build_brief, "買い物リストを作る")



class TestBenchmarkHarness(unittest.TestCase):
    """指示書19章: 同一Task・同一Datasetで比較できること。"""

    def _cases(self):
        from app.ai.gateway.benchmark import BenchmarkCase

        return [
            BenchmarkCase(
                name=f"case{i}", prompt="p", response_schema={},
                required_keys=("impact",),
                check=lambda v: v.get("impact") == "high",
            )
            for i in range(4)
        ]

    def test_it_measures_accuracy_schema_rate_and_failures_separately(self) -> None:
        from app.ai.gateway.benchmark import run_benchmark

        router = _router({
            "good": _FakeAdapter({"impact": "high"}),
            "malformed": _FakeAdapter({"nothing": 1}),
            "broken": _FakeAdapter(error=RuntimeError("down")),
        })
        report = run_benchmark(
            router, ForgeTask.CONVERSATION_STEP, self._cases(),
            ["good", "malformed", "broken"],
        )
        by_provider = {s.provider: s for s in report.scores}
        self.assertEqual(by_provider["good"].task_accuracy, 1.0)
        self.assertEqual(by_provider["good"].failure_rate, 0.0)
        self.assertEqual(by_provider["malformed"].schema_valid_rate, 0.0)
        self.assertEqual(by_provider["broken"].failure_rate, 1.0)

    def test_a_failing_provider_does_not_stop_the_benchmark(self) -> None:
        """指示書27章: 片方が落ちてもBenchmarkは取れる。"""
        from app.ai.gateway.benchmark import run_benchmark

        router = _router({
            "broken": _FakeAdapter(error=RuntimeError("quota")),
            "good": _FakeAdapter({"impact": "high"}),
        })
        report = run_benchmark(
            router, ForgeTask.CONVERSATION_STEP, self._cases(), ["broken", "good"],
        )
        self.assertEqual(len(report.scores), 2)
        self.assertEqual(report.winner(), "good")

    def test_a_schema_compliant_but_wrong_provider_never_wins(self) -> None:
        """Benchmarkを実際に走らせて見つけた実バグの回帰テスト。

        `mock`は常に`"mock_result"`を返すため、schema適合率100%・
        正答率0%になる。適合率の下限しか無かった頃は、これが
        「勝者」として選ばれてしまっていた。
        """
        from app.ai.gateway.benchmark import run_benchmark

        router = _router({"formal": _FakeAdapter({"impact": "mock_result"})})
        report = run_benchmark(
            router, ForgeTask.CONVERSATION_STEP, self._cases(), ["formal"],
        )
        score = report.scores[0]
        self.assertEqual(score.schema_valid_rate, 1.0)
        self.assertEqual(score.task_accuracy, 0.0)
        self.assertIsNone(report.winner(), "形式だけ整ったProviderが採用されている")

    def test_the_impact_dataset_is_shared_across_providers(self) -> None:
        """指示書19章「同一Dataset」。Providerごとに問題を変えない。"""
        from app.ai.gateway.impact_benchmark import build_impact_cases

        first = [c.prompt for c in build_impact_cases()]
        second = [c.prompt for c in build_impact_cases()]
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 16)

    def test_the_impact_dataset_covers_every_impact_level(self) -> None:
        from app.ai.gateway.impact_benchmark import build_impact_cases

        levels = {c.name.split(":", 1)[0] for c in build_impact_cases()}
        self.assertEqual(levels, {"blocking", "high", "low", "cosmetic"})


if __name__ == "__main__":
    unittest.main()
