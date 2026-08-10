"""Cognitive Intent Recognizer・Domain Classifier・World Builder・
Requirement Extractor のテスト(FORGE-MILESTONE-007第一段階)。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.domain_model import DomainRegistry  # noqa: E402
from forge_ai.core.orchestration.cognitive_types import AmbiguityReport, NormalizedInput  # noqa: E402
from forge_ai.core.understanding.domain_classifier import CognitiveDomainClassifier  # noqa: E402
from forge_ai.core.understanding.intent_recognizer import CognitiveIntentRecognizer  # noqa: E402
from forge_ai.core.understanding.meaning_extractor import CognitiveMeaningExtractor  # noqa: E402
from forge_ai.core.understanding.requirement_extractor import RequirementExtractor  # noqa: E402
from forge_ai.core.understanding.world_builder import CognitiveWorldBuilder  # noqa: E402


def _ok_ambiguity() -> AmbiguityReport:
    return AmbiguityReport(issues=(), overall_severity="low", detection_status="ok")


class TestCognitiveIntentRecognizer(unittest.TestCase):
    def setUp(self) -> None:
        self.recognizer = CognitiveIntentRecognizer()

    def test_shopping_keyword_extracts_item_concept(self) -> None:
        normalized = NormalizedInput(original_text="x", normalized_text="買い物リストを作りたい")
        intent = self.recognizer.recognize(normalized, _ok_ambiguity())
        self.assertIn("item", intent.required_concepts)

    def test_all_six_target_inputs_extract_at_least_one_concept(self) -> None:
        inputs = (
            "買い物リストを作りたい", "今日のタスクを管理したい", "日記を記録したい",
            "簡単なアンケートを作りたい", "予定を管理したい", "在庫を管理したい",
        )
        for text in inputs:
            with self.subTest(text=text):
                normalized = NormalizedInput(original_text=text, normalized_text=text)
                intent = self.recognizer.recognize(normalized, _ok_ambiguity())
                self.assertGreater(len(intent.required_concepts), 0, f"{text!r}から概念を抽出できなかった")

    def test_missing_goal_ambiguity_lowers_confidence(self) -> None:
        normalized = NormalizedInput(original_text="", normalized_text="")
        high_severity_report = AmbiguityReport(
            issues=(__import__("forge_ai.core.orchestration.cognitive_types", fromlist=["AmbiguityIssue"]).AmbiguityIssue(
                category="missing_goal", severity="high", description="test"
            ),),
            overall_severity="high",
        )
        intent = self.recognizer.recognize(normalized, high_severity_report)
        self.assertLess(intent.confidence, 0.5)

    def test_no_keyword_match_still_returns_valid_intent(self) -> None:
        """既知の語彙に一致しなくても、クラッシュせず低confidenceのIntentを返す。"""
        normalized = NormalizedInput(original_text="xyz123", normalized_text="xyz123")
        intent = self.recognizer.recognize(normalized, _ok_ambiguity())
        self.assertEqual(intent.required_concepts, ())


class TestCognitiveDomainClassifier(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = CognitiveDomainClassifier()
        self.registry = DomainRegistry()

    def _classify(self, concepts, actions=()):
        from forge_ai.core.intent_model import Intent

        intent = Intent(goal="test", required_concepts=concepts, required_actions=actions, constraints=())
        return self.classifier.classify(intent, self.registry)

    def test_matching_concept_selects_correct_domain(self) -> None:
        result = self._classify(("task",))
        self.assertEqual(result.primary_domain.category.value, "task_management")

    def test_all_zero_scores_falls_back_to_generic(self) -> None:
        """CEO実物監査(4回目)指摘5: 全Domainのスコアが0の場合、必ずGeneric。"""
        result = self._classify(("完全に一致しない概念xyz",))
        self.assertEqual(result.primary_domain.category.value, "generic")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.score_margin, 0.0)

    def test_candidates_include_raw_and_normalized_score(self) -> None:
        result = self._classify(("task",))
        self.assertTrue(all(hasattr(c, "raw_score") and hasattr(c, "normalized_score") for c in result.candidates))

    def test_candidates_cover_all_registered_domains(self) -> None:
        result = self._classify(("task",))
        self.assertEqual(len(result.candidates), len(self.registry.all_domains()))

    def test_confidence_reflects_fraction_of_intent_explained(self) -> None:
        """Blueprint 4.3節「B案」: Intentが持つ全シグナルのうち、
        primary_domainが説明できた割合。1個中1個一致なら1.0。"""
        result = self._classify(("task",))
        self.assertAlmostEqual(result.confidence, 1.0)

    def test_partial_match_confidence_is_less_than_one(self) -> None:
        result = self._classify(("task", "完全に無関係な概念xyz"))
        self.assertLess(result.confidence, 1.0)
        self.assertGreater(result.confidence, 0.0)


class TestCognitiveWorldBuilder(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = CognitiveWorldBuilder()
        self.classifier = CognitiveDomainClassifier()
        self.registry = DomainRegistry()

    def test_world_reflects_domain_concepts(self) -> None:
        from forge_ai.core.intent_model import Intent

        intent = Intent(goal="x", required_concepts=("task",), required_actions=(), constraints=())
        classification = self.classifier.classify(intent, self.registry)
        world = self.builder.build(classification, intent)
        self.assertGreater(len(world.objects), 0)

    def test_intent_actors_are_added_to_world(self) -> None:
        from forge_ai.core.intent_model import Intent

        intent = Intent(
            goal="x", required_concepts=("item",), required_actions=(), constraints=(),
            actors=("family_member",),
        )
        classification = self.classifier.classify(intent, self.registry)
        world = self.builder.build(classification, intent)
        self.assertIn("family_member", [a.name for a in world.actors])

    def test_intent_constraints_become_rules(self) -> None:
        from forge_ai.core.intent_model import Intent

        intent = Intent(
            goal="x", required_concepts=("item",), required_actions=(), constraints=("複数利用者",),
        )
        classification = self.classifier.classify(intent, self.registry)
        world = self.builder.build(classification, intent)
        self.assertTrue(any("複数利用者" in rule.description for rule in world.rules))


class TestCognitiveMeaningExtractor(unittest.TestCase):
    """CEO指示(Phase 1.2)5章のUnit Test要件に対応。"""

    def setUp(self) -> None:
        self.normalizer_result_for = lambda text: NormalizedInput(original_text=text, normalized_text=text)
        self.intent_recognizer = CognitiveIntentRecognizer()
        self.domain_classifier = CognitiveDomainClassifier()
        self.world_builder = CognitiveWorldBuilder()
        self.meaning_extractor = CognitiveMeaningExtractor()
        self.registry = DomainRegistry()

    def _meaning_for(self, text: str):
        normalized = self.normalizer_result_for(text)
        intent = self.intent_recognizer.recognize(normalized, _ok_ambiguity())
        classification = self.domain_classifier.classify(intent, self.registry)
        world = self.world_builder.build(classification, intent)
        return self.meaning_extractor.extract(normalized, world, intent), world, intent

    def test_extracts_actor(self) -> None:
        meaning, _, _ = self._meaning_for("家族で共有できる買い物リストを作りたい")
        self.assertIn("家族", meaning.actors)

    def test_extracts_entity(self) -> None:
        meaning, _, _ = self._meaning_for("写真と気分を記録できる日記がほしい")
        self.assertIn("photo", meaning.entities)
        self.assertIn("mood", meaning.entities)

    def test_extracts_action(self) -> None:
        meaning, _, _ = self._meaning_for("家族で共有できる買い物リストを作りたい")
        self.assertIn("share", meaning.actions)

    def test_extracts_constraint(self) -> None:
        meaning, _, _ = self._meaning_for("家族で共有できる買い物リストを作りたい")
        self.assertTrue(any("共有" in c for c in meaning.constraints))

    def test_extracts_temporal_condition(self) -> None:
        meaning, _, _ = self._meaning_for("毎週月曜日の予定を管理したい")
        self.assertIn("毎週月曜日", meaning.temporal_conditions)

    def test_extracts_state_condition(self) -> None:
        meaning, _, _ = self._meaning_for("在庫が少なくなったら分かるようにしたい")
        self.assertTrue(any("在庫" in s for s in meaning.state_conditions))

    def test_evidence_span_is_preserved(self) -> None:
        meaning, _, _ = self._meaning_for("家族で共有できる買い物リストを作りたい")
        self.assertIn("家族", meaning.evidence_spans)
        self.assertIn("共有", meaning.evidence_spans)

    def test_semantic_units_hold_action_target_relationship(self) -> None:
        """文字列の羅列ではなく、action/target/evidenceの関係を保持する
        (CEO指示1.1「少なくともaction・target・qualifier・evidenceの
        関係を保持すること」)。"""
        meaning, _, _ = self._meaning_for("写真と気分を記録できる日記がほしい")
        self.assertGreater(len(meaning.semantic_units), 0)
        unit = meaning.semantic_units[0]
        self.assertTrue(unit.action)
        self.assertTrue(unit.evidence)

    def test_unknown_input_produces_safe_low_confidence_result(self) -> None:
        """未知入力(修飾語を含まない、単純な入力)では、confidenceが
        低め(0.9ではなく0.6)になり、クラッシュしない。"""
        meaning, _, _ = self._meaning_for("何かアプリを作りたい")
        self.assertLessEqual(meaning.confidence, 0.6)
        self.assertIsInstance(meaning.summary, str)

    def test_deterministic_for_same_input(self) -> None:
        """同じ入力に対して、常に同じ結果を返す(決定的)。"""
        meaning1, _, _ = self._meaning_for("期限と優先度を設定できるタスク管理アプリ")
        meaning2, _, _ = self._meaning_for("期限と優先度を設定できるタスク管理アプリ")
        self.assertEqual(meaning1, meaning2)

    def test_simple_input_without_qualifiers_has_empty_qualifier_fields(self) -> None:
        """既存6例のような、修飾語を含まない単純な入力では、
        constraints/temporal/stateが空のままであること(既存の
        単純な入力を壊さないことの確認)。"""
        meaning, _, _ = self._meaning_for("買い物リストを作りたい")
        self.assertEqual(meaning.constraints, ())
        self.assertEqual(meaning.temporal_conditions, ())
        self.assertEqual(meaning.state_conditions, ())


class TestRequirementExtractor(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = RequirementExtractor()
        self.builder = CognitiveWorldBuilder()
        self.classifier = CognitiveDomainClassifier()
        self.registry = DomainRegistry()

    def _build_world_and_intent(self, concepts):
        from forge_ai.core.intent_model import Intent
        from forge_ai.core.orchestration.cognitive_types import ExtractedMeaning

        intent = Intent(goal="x", required_concepts=concepts, required_actions=(), constraints=())
        classification = self.classifier.classify(intent, self.registry)
        world = self.builder.build(classification, intent)
        # FORGE-MILESTONE-007 Phase 1.2: RequirementExtractor.extract()の
        # シグネチャがmeaningを含む3引数へ復元されたため、これらの既存
        # テストにも最小限のExtractedMeaning(修飾情報を含まない、
        # World/Intentのみのテストを引き続き検証するための空のmeaning)
        # を渡す。
        meaning = ExtractedMeaning(summary=intent.goal)
        return world, intent, meaning

    def test_extracts_functional_requirements_for_each_object(self) -> None:
        world, intent, meaning = self._build_world_and_intent(("task",))
        requirements = self.extractor.extract(meaning, world, intent)
        functional = requirements.by_category("functional")
        self.assertGreaterEqual(len(functional), len(world.objects))

    def test_always_includes_validation_requirement_for_nonempty_concepts(self) -> None:
        world, intent, meaning = self._build_world_and_intent(("item",))
        requirements = self.extractor.extract(meaning, world, intent)
        self.assertGreater(len(requirements.by_category("validation")), 0)

    def test_privacy_keyword_adds_privacy_requirement(self) -> None:
        world, intent, meaning = self._build_world_and_intent(("patient",))
        requirements = self.extractor.extract(meaning, world, intent)
        self.assertGreater(len(requirements.by_category("privacy")), 0)

    def test_always_includes_at_least_one_accessibility_requirement(self) -> None:
        world, intent, meaning = self._build_world_and_intent(("item",))
        requirements = self.extractor.extract(meaning, world, intent)
        self.assertGreater(len(requirements.by_category("accessibility")), 0)

    def _build_with_meaning(self, concepts, meaning_kwargs):
        from forge_ai.core.intent_model import Intent
        from forge_ai.core.orchestration.cognitive_types import ExtractedMeaning

        intent = Intent(goal="x", required_concepts=concepts, required_actions=(), constraints=())
        classification = self.classifier.classify(intent, self.registry)
        world = self.builder.build(classification, intent)
        meaning = ExtractedMeaning(summary=intent.goal, **meaning_kwargs)
        return world, intent, meaning

    def test_meaning_action_becomes_functional_requirement_with_operation_ref(self) -> None:
        """CEO指示1.4「MeaningのAction → Functional Requirement」、および
        target_ref/operation_refの整合性の確認。"""
        world, intent, meaning = self._build_with_meaning(("item",), {"actions": ("share",)})
        # "share"はPermission Requirementへ変換されるため、functionalには
        # 含まれない(別のテストで確認)。ここではfunctional以外のaction
        # (例: "notify")で確認する。
        world2, intent2, meaning2 = self._build_with_meaning(("stock",), {"actions": ("notify",)})
        requirements = self.extractor.extract(meaning2, world2, intent2)
        functional_from_meaning = [
            r for r in requirements.by_category("functional") if r.derived_from == "meaning"
        ]
        self.assertTrue(any(r.operation_ref == "notify" for r in functional_from_meaning))

    def test_meaning_entity_becomes_data_requirement_with_target_ref(self) -> None:
        """CEO指示1.4「MeaningのEntity → Data Requirement」の確認。"""
        world, intent, meaning = self._build_with_meaning(("entry",), {"entities": ("photo",)})
        requirements = self.extractor.extract(meaning, world, intent)
        data_from_meaning = [r for r in requirements.by_category("data") if r.derived_from == "meaning"]
        self.assertTrue(any(r.target_ref == "photo" for r in data_from_meaning))

    def test_meaning_constraint_becomes_validation_requirement(self) -> None:
        """CEO指示1.4「Constraint → ConstraintまたはValidation
        Requirement」の確認。"""
        world, intent, meaning = self._build_with_meaning(("item",), {"constraints": ("複数利用者による共有アクセスが必要",)})
        requirements = self.extractor.extract(meaning, world, intent)
        self.assertTrue(any("複数利用者" in r.description for r in requirements.by_category("validation")))

    def test_meaning_temporal_condition_becomes_schedule_requirement(self) -> None:
        """CEO指示1.4「Temporal condition → Schedule/Notification関連
        Requirement」の確認。"""
        world, intent, meaning = self._build_with_meaning(("event",), {"temporal_conditions": ("毎週月曜日",)})
        requirements = self.extractor.extract(meaning, world, intent)
        self.assertTrue(any("毎週月曜日" in r.description for r in requirements.by_category("schedule")))

    def test_meaning_state_condition_becomes_state_requirement(self) -> None:
        """CEO指示1.4「State condition → State遷移または表示
        Requirement」の確認。"""
        world, intent, meaning = self._build_with_meaning(("stock",), {"state_conditions": ("在庫が少ない状態",)})
        requirements = self.extractor.extract(meaning, world, intent)
        self.assertTrue(any("在庫が少ない状態" in r.description for r in requirements.by_category("state")))

    def test_meaning_sharing_actor_becomes_permission_requirement_with_operation_ref(self) -> None:
        """CEO指示1.4「Actor / Sharing → Permission / Collaboration
        Requirement」、target_ref/operation_refの整合性の確認。"""
        world, intent, meaning = self._build_with_meaning(("item",), {"actors": ("家族",), "actions": ("share",)})
        requirements = self.extractor.extract(meaning, world, intent)
        permission_reqs = requirements.by_category("permission")
        self.assertGreater(len(permission_reqs), 0)
        self.assertTrue(any(r.operation_ref == "share" for r in permission_reqs))

    def test_world_baseline_requirements_are_not_marked_as_meaning_derived(self) -> None:
        """World由来のFunctional/Data Requirementは`derived_from`が
        既定値"world"のままであり、"meaning"にはならない(Meaning由来の
        要件とWorld由来の要件を区別できることの確認)。"""
        world, intent, meaning = self._build_world_and_intent(("item",))
        requirements = self.extractor.extract(meaning, world, intent)
        world_derived = [r for r in requirements.requirements if r.category == "functional" and r.derived_from != "meaning"]
        self.assertGreater(len(world_derived), 0)


if __name__ == "__main__":
    unittest.main()
