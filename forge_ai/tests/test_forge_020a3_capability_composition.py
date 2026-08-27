"""複数の見せ方を求められても、**どれも消えない**（020A3 / 020A2 §2）。

020A2 と 020A3 が同じ要求を別々に実装したので、merge のときに
**語彙を1つへ寄せた**。正典は
`forge_ai/core/semantics/capabilities.py` である
（`record.*` ではなく `data.*`、`view.total` ではなく `view.metric`）。

意図は 020A3 のまま——「合計」「比較」「推移」を同時に言われたときに
1つの Shape へ潰さない。
"""

import unittest

from forge_ai.core.semantics.capabilities import SEMANTIC_CAPABILITIES
from forge_ai.core.semantics.capability_plan import StructuralMode, plan_capabilities


class CapabilityCompositionTests(unittest.TestCase):
    def test_total_compare_and_trend_are_composed_without_shadowing(self) -> None:
        plan = plan_capabilities("部署ごとの売上を比較して、合計と月別推移も見たい")
        self.assertIs(plan.structure, StructuralMode.RECORD_ENTITY)
        self.assertEqual(
            set(plan.views),
            {"view.list", "view.metric", "view.group_compare", "view.trend"},
        )
        self.assertEqual(
            {field.capability for field in plan.fields}, {"data.text", "data.number"},
        )

    def test_structural_mode_never_encodes_view_combinations(self) -> None:
        self.assertEqual({mode.value for mode in StructuralMode}, {
            "unknown", "checklist", "record_entity",
        })

    def test_every_planned_capability_exists_in_the_canonical_catalog(self) -> None:
        """**2つ目の語彙を作らない。**

        `record.entity` のような別系統の ID をどこかで作ると、そこから
        表が2つに割れる（020A2 §1 が禁じた形）。
        """
        plan = plan_capabilities("部署ごとの売上を比較して、合計と月別推移も見たい")
        for capability_id in plan.requested:
            with self.subTest(capability=capability_id):
                self.assertIn(capability_id, SEMANTIC_CAPABILITIES)
