"""Golden Finance E2E — **自然言語から**意味的役割が画面まで届くか
(FORGE-R1-CLOSURE-015 §11、2026-08-17)。

---

## 何を通すのか

```
「毎日の収入と支出を記録したい。今月の残高を一番目立たせたい。」
  ↓ Conversation / Cognitive Pipeline（本番のHTTP経路）
  ↓ Design Intent（AIが密度と面を選ぶ）
  ↓ Compiler（構造から決まるroleを付ける）
  ↓ Forge Language v1.12
  ↓ Validator
  ↓ Generation Evidence
```

## 固定JSONを流し込むのは禁止(§11.1)

RendererへDocumentを直接入れるテストは**E2Eではない**。それは
「書いたものが書いたとおりに描かれる」ことしか示さない。ここは
**自然言語から始める**。

## Templateを増やしていないこと

「収入と支出」に答えられるようになったのは、家計簿用の固定Template
を足したからではなく、`MonetaryFlow`という**意味**をIRが持てるように
なったからである。同じ仕組みで、Curatedに無いDomainでも
（AIが`monetary_flow`相当の構造を設計すれば）同じ形になる。

## AIはTest Doubleである

実Cloud APIは呼ばない(Gemini quotaを消費しない)。差し替えているのは
**AIの答えだけ**で、Pipelineも記録も本番のものである。
"""

from __future__ import annotations

import os
import sys
import unittest

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # forge_ai/ はrepoルート直下

from app.ai.gateway.generation_evidence import (  # noqa: E402
    DesignDecisionSource,
    default_generation_store,
)
from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402
from app.main import app  # noqa: E402
from forge_ai.provider.mock_provider import MockProvider  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402

_NEED = "毎日の収入と支出を記録したい。今月の残高を一番目立たせたい。"

# 「落ち着いて読ませたい」「一覧は持ち上げる」をAIが選んだ、という想定。
_AI_DESIGN_ANSWER = {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}


class _AiAnswersDesignIntent:
    """`design_intent`にだけ答える。他の段は本番のBridgeへ委ねる。"""

    def __init__(self, inner: object) -> None:
        self._inner = inner or MockProvider()

    def complete(self, prompt):  # noqa: ANN001
        if prompt.stage == "design_intent":
            return ProviderResponse(text="", structured=_AI_DESIGN_ANSWER)
        return self._inner.complete(prompt)


def _widgets(widget: dict):
    yield widget
    for child in widget.get("children", []) or ():
        yield from _widgets(child)


class TestGoldenFinanceReachesSemanticRoles(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import app.ai.runtime.prompt_pipeline as pipeline_module

        cls.store = default_generation_store()
        cls.store.reset()

        original = pipeline_module.run_cognitive_pipeline

        def patched(text, provider=None, **kwargs):  # noqa: ANN001, ANN202
            return original(text, _AiAnswersDesignIntent(provider), **kwargs)

        pipeline_module.run_cognitive_pipeline = patched
        try:
            response = TestClient(app).post(
                "/api/v1/ai/generate",
                json={"input": {"natural_language": _NEED,
                                "generation_options": {"provider": "mock"}}},
            )
        finally:
            pipeline_module.run_cognitive_pipeline = original

        assert response.status_code == 200, response.text
        cls.result = response.json()["result"]
        cls.document = cls.result["forge_document"]
        cls.all_widgets = [w for s in cls.document["screens"] for w in _widgets(s["body"])]
        cls.roles = {
            w["id"]: w["style_role"] for w in cls.all_widgets
            if isinstance(w.get("style_role"), str)
        }

    # --- 生成物そのもの ---------------------------------------------------

    def test_the_document_is_valid(self) -> None:
        result = validate_forge_document(self.document)
        self.assertTrue(result.valid, [e.to_dict() for e in result.errors])
        self.assertEqual(self.document["version"], "1.12")

    def test_the_balance_is_the_single_most_important_number(self) -> None:
        """「今月の残高を一番目立たせたい」に対する答え。"""
        primaries = [w for w in self.all_widgets if w.get("style_role") == "metric.primary"]
        self.assertEqual(len(primaries), 1, "主KPIが1つでない＝階層が消えている")
        self.assertEqual(primaries[0]["label"], "残高")
        self.assertEqual(primaries[0]["type"], "metric_view")

    def test_the_balance_subtracts_the_outflow(self) -> None:
        """**単純な合計を残高と呼ばない。**"""
        balance = next(w for w in self.all_widgets if w.get("style_role") == "metric.primary")
        self.assertEqual(balance["aggregate"], "sum")
        self.assertEqual(balance["negative_when"], "支出")

    def test_income_and_expense_carry_finance_roles(self) -> None:
        """§9。語彙にあるだけでなく、**本番の生成物に出る**こと。"""
        self.assertIn("finance.income", self.roles.values())
        self.assertIn("finance.expense", self.roles.values())

    def test_income_and_expense_are_not_state_colours(self) -> None:
        """**支出はエラーではない。** state.dangerで代用していないこと。"""
        self.assertNotIn("state.danger", self.roles.values())

    def test_the_primary_action_is_marked(self) -> None:
        primary_actions = [r for r in self.roles.values() if r == "button.primary"]
        self.assertEqual(len(primary_actions), 1, "主要操作は画面に1つ")

    def test_the_destructive_action_is_not_primary(self) -> None:
        self.assertEqual(self.roles.get("record_delete_button"), "button.secondary")

    # --- AIが選んだ意味 ---------------------------------------------------

    def test_the_ai_chose_the_density_and_the_surface(self) -> None:
        self.assertEqual(self.roles.get("root_tabs"), "density.relaxed")
        self.assertEqual(self.roles.get("records_list_view"), "surface.elevated")

    # --- Evidence ---------------------------------------------------------

    def test_the_evidence_separates_the_ai_choices(self) -> None:
        record = self.store.all_records()[0]
        ai_roles = {d.role for d in record.ai_selected_roles}
        self.assertEqual(ai_roles, {"density.relaxed", "surface.elevated"})
        self.assertEqual(record.fallback_roles, ())

    def test_the_compiler_roles_are_marked_deterministic(self) -> None:
        record = self.store.all_records()[0]
        deterministic = {d.role for d in record.design_decisions
                         if d.source is DesignDecisionSource.DETERMINISTIC}
        self.assertIn("metric.primary", deterministic)
        self.assertIn("finance.income", deterministic)

    def test_the_visual_structure_is_recorded(self) -> None:
        """§10。UNKNOWNのままにしない。"""
        structure = self.store.all_records()[0].visual_structure
        self.assertEqual(structure["primary_metric_count"], 1)
        self.assertEqual(structure["primary_action_count"], 1)
        self.assertEqual(structure["role_coverage_ratio"], 1.0)
        self.assertEqual(structure["duplicated_singular_roles"], [])
        self.assertGreater(structure["hierarchy_depth"], 1)

    def test_the_critic_evaluated_the_semantic_design(self) -> None:
        """§3。Criticがこの軸を見たこと。"""
        trace = self.result["diagnostics"]["decision_trace"]
        trace_stages = [t.get("stage") for t in trace]
        self.assertIn("semantic_design", trace_stages)

    def test_no_free_text_leaks_into_the_evidence(self) -> None:
        record = self.store.all_records()[0]
        self.assertNotIn(_NEED, repr(record.to_dict()))


if __name__ == "__main__":
    unittest.main()
