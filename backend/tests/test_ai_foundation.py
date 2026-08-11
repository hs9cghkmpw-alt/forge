"""AI Foundation(PHASE6)の構造テスト。

実際のAI呼び出しは無い(実装していないため)。ここでは、
- IR型(IntentIR/PlanIR/CriticResult)が期待通りに構築できること
- 全Providerスタブが呼び出されると明確にNotImplementedErrorを返すこと
  (無言で失敗したり、誤って動いたふりをしたりしないこと)
だけを検証する。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.foundation.interfaces import (  # noqa: E402
    CriticResult,
    IntentIR,
    PlanIR,
    ScreenPlan,
)
from app.ai.foundation.providers import (  # noqa: E402
    ClaudeProvider,
    ForgeAIProvider,
    GeminiProvider,
    OSSProvider,
    OpenAIProvider,
)


class TestIntermediateRepresentations(unittest.TestCase):
    def test_intent_ir_construction(self):
        intent = IntentIR(
            purpose="持ち物チェックリストを作りたい",
            target_users=("親",),
            required_features=("チェック", "追加"),
        )
        self.assertEqual(intent.purpose, "持ち物チェックリストを作りたい")
        self.assertEqual(intent.required_features, ("チェック", "追加"))

    def test_plan_ir_construction(self):
        plan = PlanIR(
            screens=(ScreenPlan(screen_id="main", purpose="チェックリスト表示"),),
            template_hint="checklist",
        )
        self.assertEqual(len(plan.screens), 1)
        self.assertEqual(plan.template_hint, "checklist")

    def test_intent_ir_schema_version_defaults_to_1_0_and_is_backward_compatible(self):
        """FORGE-AI-CONNECT-001 TD22対応(2026-08-11)。既存の呼び出し方
        (`schema_version`を渡さない)が引き続き動作し、既定値"1.0"に
        なることの回帰テスト。"""
        intent = IntentIR(purpose="x")
        self.assertEqual(intent.schema_version, "1.0")

    def test_plan_ir_schema_version_defaults_to_1_0_and_is_backward_compatible(self):
        plan = PlanIR(screens=(ScreenPlan(screen_id="main", purpose="x"),))
        self.assertEqual(plan.schema_version, "1.0")

    def test_critic_result_construction(self):
        result = CriticResult(score=82, release_ready=False, required_fixes=("add_back_navigation",))
        self.assertEqual(result.score, 82)
        self.assertFalse(result.release_ready)


class TestProviderStubsAreHonestlyUnimplemented(unittest.TestCase):
    """全Providerが「実装されたふりをしない」ことを保証する回帰テスト。

    FORGE-AI-CONNECT-001(2026-08-10)で`GeminiProvider`を実装したため、
    このテストの対象から`GeminiProvider`を除外した。`GeminiProvider`
    自体の「実装したふりをしない」ことの検証(APIキー無し→
    `NotImplementedError`ではなく`RuntimeError`)は
    `test_gemini_provider.py`で別途行っている。
    """

    def test_all_providers_raise_not_implemented(self):
        providers = [OpenAIProvider(), ClaudeProvider(), OSSProvider(), ForgeAIProvider()]
        for provider in providers:
            with self.subTest(provider=provider.provider_name):
                with self.assertRaises(NotImplementedError):
                    provider.complete_structured("test", {})

    def test_provider_names_are_distinct(self):
        providers = [OpenAIProvider(), ClaudeProvider(), GeminiProvider(), OSSProvider(), ForgeAIProvider()]
        names = [p.provider_name for p in providers]
        self.assertEqual(len(names), len(set(names)), "Provider名が重複しています")


if __name__ == "__main__":
    unittest.main()
