"""Input Normalizer・Ambiguity Detector のテスト(FORGE-MILESTONE-007第一段階)。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.domain_model import DomainRegistry  # noqa: E402
from forge_ai.core.input_processing.ambiguity_detector import AmbiguityDetector  # noqa: E402
from forge_ai.core.input_processing.normalizer import InputNormalizer  # noqa: E402


class TestInputNormalizer(unittest.TestCase):
    def setUp(self) -> None:
        self.normalizer = InputNormalizer()

    def test_preserves_original_text(self) -> None:
        result = self.normalizer.normalize("  買い物リストを作りたい  ")
        self.assertEqual(result.original_text, "  買い物リストを作りたい  ")

    def test_strips_leading_and_trailing_whitespace(self) -> None:
        result = self.normalizer.normalize("  買い物リストを作りたい  ")
        self.assertEqual(result.normalized_text, "買い物リストを作りたい")

    def test_collapses_internal_whitespace(self) -> None:
        result = self.normalizer.normalize("買い物   リストを作りたい")
        self.assertEqual(result.normalized_text, "買い物 リストを作りたい")

    def test_normalizes_fullwidth_question_mark(self) -> None:
        result = self.normalizer.normalize("作りたい？")
        self.assertIn("?", result.normalized_text)
        self.assertNotIn("？", result.normalized_text)

    def test_empty_input_does_not_crash(self) -> None:
        result = self.normalizer.normalize("")
        self.assertEqual(result.normalized_text, "")


class TestAmbiguityDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = AmbiguityDetector()
        self.registry = DomainRegistry()

    def _detect(self, text: str):
        from forge_ai.core.orchestration.cognitive_types import NormalizedInput

        return self.detector.detect(NormalizedInput(original_text=text, normalized_text=text), self.registry)

    def test_simple_clear_input_is_low_severity(self) -> None:
        report = self._detect("買い物リストを作りたい")
        self.assertEqual(report.overall_severity, "low")
        self.assertFalse(report.has_priority1_issue)

    def test_empty_input_is_high_severity_missing_goal(self) -> None:
        report = self._detect("")
        self.assertEqual(report.overall_severity, "high")
        self.assertTrue(any(i.category == "missing_goal" for i in report.issues))

    def test_privacy_keyword_triggers_priority1(self) -> None:
        report = self._detect("福祉支援の記録を管理したい")
        self.assertEqual(report.overall_severity, "high")
        self.assertTrue(report.has_priority1_issue)

    def test_detection_status_is_ok_by_default(self) -> None:
        """M006 4.4節: 検出処理自体は例外を投げない設計のため、
        通常は常にdetection_status='ok'になる。"""
        report = self._detect("買い物リストを作りたい")
        self.assertEqual(report.detection_status, "ok")

    # --- FORGE v0.2 PART B 7.1節: 新規4分類の回帰テスト ---

    def test_missing_actor_is_low_severity_and_does_not_escalate(self) -> None:
        """Actorが明示されない典型的な入力(6例の実例)でmissing_actorが
        LOWとして記録されるが、overall_severityを押し上げないこと。"""
        report = self._detect("買い物リストを作りたい")
        self.assertTrue(any(i.category == "missing_actor" and i.severity == "low" for i in report.issues))
        self.assertEqual(report.overall_severity, "low")

    def test_explicit_actor_suppresses_missing_actor_issue(self) -> None:
        report = self._detect("私の買い物リストを作りたい")
        self.assertFalse(any(i.category == "missing_actor" for i in report.issues))

    def test_missing_domain_detected_for_unrecognized_vocabulary(self) -> None:
        report = self._detect("特殊なものを扱いたい")
        self.assertTrue(any(i.category == "missing_domain" and i.severity == "medium" for i in report.issues))
        self.assertEqual(report.overall_severity, "medium")

    def test_missing_domain_not_triggered_for_known_vocabulary(self) -> None:
        report = self._detect("買い物リストを作りたい")
        self.assertFalse(any(i.category == "missing_domain" for i in report.issues))

    def test_multiple_possible_templates_detected_for_cross_domain_keyword(self) -> None:
        """「出欠」はattendance/task_managementの両方のtypical_conceptsに
        対応するため、複数分野にまたがる曖昧さとして検出されるべき。"""
        report = self._detect("出欠を管理したい")
        issue = next((i for i in report.issues if i.category == "multiple_possible_templates"), None)
        self.assertIsNotNone(issue)
        self.assertEqual(issue.severity, "medium")

    def test_single_domain_concept_does_not_trigger_multiple_templates(self) -> None:
        report = self._detect("買い物リストを作りたい")
        self.assertFalse(any(i.category == "multiple_possible_templates" for i in report.issues))

    def test_conflicting_requirements_detected_for_contradiction_pair(self) -> None:
        report = self._detect("公開する項目と非公開の項目を両方管理したい")
        self.assertTrue(any(i.category == "conflicting_requirements" and i.severity == "medium" for i in report.issues))

    def test_no_contradiction_no_conflicting_requirements_issue(self) -> None:
        report = self._detect("買い物リストを作りたい")
        self.assertFalse(any(i.category == "conflicting_requirements" for i in report.issues))

    def test_severity_aggregation_uses_highest_not_presence(self) -> None:
        """severity集約は「1件でもissueがあればmedium以上」ではなく、
        最も重大なissueのseverityを採用する(missing_actorがLOWのみの
        場合、他にmedium/high issueが無ければoverall_severityは'low')。"""
        low_only_report = self._detect("買い物リストを作りたい")
        self.assertEqual(len(low_only_report.issues), 1)
        self.assertEqual(low_only_report.issues[0].severity, "low")
        self.assertEqual(low_only_report.overall_severity, "low")

        medium_report = self._detect("出欠を管理したい")
        self.assertTrue(any(i.severity == "low" for i in medium_report.issues))
        self.assertTrue(any(i.severity == "medium" for i in medium_report.issues))
        self.assertEqual(medium_report.overall_severity, "medium")  # not overridden by the low issue

    def test_privacy_issue_still_dominates_severity_aggregation(self) -> None:
        """HIGH(privacy_safety_permission)が他のLOW/MEDIUM issueと共存
        しても、overall_severityは'high'のまま(集約ロジック変更の回帰)。"""
        report = self._detect("福祉支援の記録を管理したい")
        self.assertEqual(report.overall_severity, "high")
        self.assertTrue(report.has_priority1_issue)

    # --- FORGE v0.2 P2 8・9・11章: 8分類完成・否定語考慮・Lexicon拡充 ---

    def test_missing_data_detected_when_action_present_but_no_concept(self) -> None:
        """「管理したい」だけでは、操作意図はあるが対象データが不明。"""
        report = self._detect("管理したい")
        self.assertTrue(any(i.category == "missing_data" and i.severity == "medium" for i in report.issues))

    def test_missing_data_not_triggered_when_object_is_named(self) -> None:
        report = self._detect("買い物リストを作りたい")
        self.assertFalse(any(i.category == "missing_data" for i in report.issues))

    def test_missing_action_detected_when_concept_present_but_no_verb(self) -> None:
        """「買い物」だけでは、対象は分かるが操作(追加/管理等)が不明。"""
        report = self._detect("買い物")
        self.assertTrue(any(i.category == "missing_action" and i.severity == "medium" for i in report.issues))

    def test_missing_action_not_triggered_for_golden_examples(self) -> None:
        """`lexicon.GENERIC_ACTION_HINTS`により、6例のような自然な文では
        誤検出しないことを確認する(以前の見送り理由の解消を裏付ける)。"""
        for text in (
            "買い物リストを作りたい", "今日のタスクを管理したい", "日記を記録したい",
            "簡単なアンケートを作りたい", "予定を管理したい", "在庫を管理したい",
        ):
            with self.subTest(text=text):
                report = self._detect(text)
                self.assertFalse(any(i.category == "missing_action" for i in report.issues))
                self.assertFalse(any(i.category == "missing_data" for i in report.issues))
                self.assertEqual(report.overall_severity, "low")

    def test_negated_contradiction_does_not_trigger_conflicting_requirements(self) -> None:
        """P2 9章「否定語を考慮する」: 「公開はしない」のように否定されている
        場合、'公開'/'非公開'ペアが両方出現していても矛盾として扱わない。"""
        report = self._detect("公開はしないが非公開設定もしたい")
        self.assertFalse(any(i.category == "conflicting_requirements" for i in report.issues))

    def test_non_negated_contradiction_still_triggers(self) -> None:
        """否定語が無ければ、引き続き矛盾として検出する(回帰)。"""
        report = self._detect("公開する項目と非公開の項目を両方管理したい")
        self.assertTrue(any(i.category == "conflicting_requirements" for i in report.issues))

    def test_household_budget_vocabulary_is_recognized(self) -> None:
        """P2 11章: 家計簿がmissing_domainとして誤検出されない。"""
        report = self._detect("家計簿の収入と支出を記録したい")
        self.assertFalse(any(i.category == "missing_domain" for i in report.issues))

    def test_child_growth_vocabulary_is_recognized(self) -> None:
        """P2 11章: 成長記録がmissing_domainとして誤検出されない。"""
        report = self._detect("子どもの身長と体重の成長記録をつけたい")
        self.assertFalse(any(i.category == "missing_domain" for i in report.issues))

    def test_business_task_synonym_maps_to_task_concept(self) -> None:
        """P2 11章: 「業務」がtask_managementの語彙として認識される。"""
        report = self._detect("業務を管理したい")
        self.assertFalse(any(i.category == "missing_domain" for i in report.issues))


class TestSharedLexiconDependencyDirection(unittest.TestCase):
    """FORGE v0.2 PART B 7.1節の回帰テスト: `ambiguity_detector.py`
    (input_processing/)が`intent_recognizer.py`(understanding/)を
    直接importしていないこと(Blueprint Task5.2「同階層モジュール間の
    直接import禁止」)。共有語彙は`core/lexicon.py`(下位層)経由でのみ
    参照してよい。"""

    def test_ambiguity_detector_does_not_import_understanding_layer(self) -> None:
        import inspect

        import forge_ai.core.input_processing.ambiguity_detector as module

        source = inspect.getsource(module)
        self.assertNotIn("from forge_ai.core.understanding", source)
        self.assertIn("from forge_ai.core.lexicon", source)

    def test_intent_recognizer_and_ambiguity_detector_share_the_same_lexicon(self) -> None:
        """辞書の二重管理(ドリフト)が起きていないことを、実際に同一
        オブジェクトを参照していることで確認する。"""
        from forge_ai.core.input_processing import ambiguity_detector as amb_module
        from forge_ai.core.lexicon import CONCEPT_KEYWORDS
        from forge_ai.core.understanding import intent_recognizer as intent_module

        self.assertIs(amb_module.CONCEPT_KEYWORDS, CONCEPT_KEYWORDS)
        self.assertIs(intent_module._CONCEPT_KEYWORDS, CONCEPT_KEYWORDS)


if __name__ == "__main__":
    unittest.main()
