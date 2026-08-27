import unittest

from forge_ai.core.semantics.capability_plan import StructuralMode, plan_capabilities


class CapabilityCompositionTests(unittest.TestCase):
    def test_total_compare_and_trend_are_composed_without_shadowing(self) -> None:
        plan = plan_capabilities("部署ごとの売上を比較して、合計と月別推移も見たい")
        self.assertIs(plan.structural_mode, StructuralMode.RECORD_ENTITY)
        self.assertEqual(plan.views, (
            "view.list", "view.total", "view.group_compare", "view.trend",
        ))
        self.assertEqual(
            {field.capability for field in plan.fields}, {"record.text", "record.number"},
        )

    def test_structural_mode_never_encodes_view_combinations(self) -> None:
        self.assertEqual({mode.value for mode in StructuralMode}, {
            "unknown", "checklist", "record_entity",
        })
