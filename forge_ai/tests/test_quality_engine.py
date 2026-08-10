"""quality_engine.py のテスト。6軸それぞれの挙動を検証する。"""

from __future__ import annotations

import unittest

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRStateValue, ForgeIRWidget
from forge_ai.core.planner import ApplicationPlan, ScreenPlan
from forge_ai.quality.quality_engine import QualityEngine


def _valid_ir() -> ForgeIRDocument:
    screen = ForgeIRScreen(
        id="s1",
        title="Test Screen",
        state={"items": ForgeIRStateValue(type="checklist", value=[{"id": "item_1", "text": "milk", "done": False}])},
        body=ForgeIRWidget(
            type="column", id="root",
            children=(ForgeIRWidget(type="checklist", id="cl1", properties={"state_ref": "items"}),),
        ),
    )
    return ForgeIRDocument(version="1.0", initial_screen_id="s1", screens=(screen,), app_title="Test")


def _plan_with_entities(*entities: str) -> ApplicationPlan:
    return ApplicationPlan(
        title="Test",
        screens=(ScreenPlan(name="main", purpose="test", key_elements=entities),),
        data_entities=entities,
        primary_flow=(),
    )


class TestQualityEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = QualityEngine()

    def test_valid_ir_scores_high_on_correctness(self) -> None:
        score = self.engine.evaluate(_valid_ir(), _plan_with_entities("milk"))
        self.assertEqual(score.correctness, 1.0)

    def test_ir_with_no_screens_scores_zero_correctness(self) -> None:
        empty_ir = ForgeIRDocument(version="1.0", initial_screen_id="s1", screens=())
        score = self.engine.evaluate(empty_ir, _plan_with_entities("x"))
        self.assertEqual(score.correctness, 0.0)

    def test_ir_with_invalid_initial_screen_id_scores_partial_correctness(self) -> None:
        screen = ForgeIRScreen(id="s1", title="T", state={}, body=ForgeIRWidget(type="text", id="t1"))
        ir = ForgeIRDocument(version="1.0", initial_screen_id="does_not_exist", screens=(screen,))
        score = self.engine.evaluate(ir, _plan_with_entities("x"))
        self.assertLess(score.correctness, 1.0)
        self.assertGreater(score.correctness, 0.0)

    def test_completeness_reflects_entity_coverage(self) -> None:
        ir = _valid_ir()
        full_score = self.engine.evaluate(ir, _plan_with_entities("milk"))
        partial_score = self.engine.evaluate(ir, _plan_with_entities("milk", "totally_unrelated_entity_xyz"))
        self.assertGreater(full_score.completeness, partial_score.completeness)

    def test_completeness_with_no_data_entities_is_perfect(self) -> None:
        ir = _valid_ir()
        score = self.engine.evaluate(ir, _plan_with_entities())
        self.assertEqual(score.completeness, 1.0)

    def test_runtime_safety_fails_when_nesting_exceeds_limit(self) -> None:
        # 13段のネスト(上限12を超える)を作る。
        widget = ForgeIRWidget(type="text", id="leaf")
        for i in range(13):
            widget = ForgeIRWidget(type="column", id=f"c{i}", children=(widget,))
        screen = ForgeIRScreen(id="s1", title="T", state={}, body=widget)
        ir = ForgeIRDocument(version="1.0", initial_screen_id="s1", screens=(screen,))
        score = self.engine.evaluate(ir, _plan_with_entities("x"))
        self.assertEqual(score.runtime_safety, 0.0)

    def test_maintainability_penalizes_duplicate_widget_ids(self) -> None:
        screen = ForgeIRScreen(
            id="s1", title="T", state={},
            body=ForgeIRWidget(
                type="column", id="root",
                children=(
                    ForgeIRWidget(type="text", id="dup"),
                    ForgeIRWidget(type="text", id="dup"),
                ),
            ),
        )
        ir = ForgeIRDocument(version="1.0", initial_screen_id="s1", screens=(screen,))
        score = self.engine.evaluate(ir, _plan_with_entities("x"))
        self.assertLess(score.maintainability, 1.0)

    def test_overall_is_average_of_six_dimensions(self) -> None:
        score = self.engine.evaluate(_valid_ir(), _plan_with_entities("milk"))
        manual_avg = (
            score.correctness + score.completeness + score.simplicity
            + score.runtime_safety + score.explainability + score.maintainability
        ) / 6
        self.assertAlmostEqual(score.overall, manual_avg, places=9)

    def test_to_dict_includes_all_seven_keys(self) -> None:
        score = self.engine.evaluate(_valid_ir(), _plan_with_entities("milk"))
        d = score.to_dict()
        expected_keys = {
            "correctness", "completeness", "simplicity",
            "runtime_safety", "explainability", "maintainability", "overall",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_evaluate_never_crashes_on_minimal_ir(self) -> None:
        screen = ForgeIRScreen(id="s1", title="", state={}, body=ForgeIRWidget(type="text", id="t1"))
        ir = ForgeIRDocument(version="1.0", initial_screen_id="s1", screens=(screen,))
        score = self.engine.evaluate(ir, _plan_with_entities())
        self.assertIsNotNone(score)


if __name__ == "__main__":
    unittest.main()
