"""Learning Contract の語彙と境界（FORGE-017A §5・§6・§10）。

---

## このファイルが守っているもの

017Aの指摘は「契約をEvidence Store型と1:1に固定するな」だった。
commit BまでのLearning Event V1は、**いま実装がある型を並べただけ**で、
Growing AIの構想から勝手に縮小していた。

実装が無いものを「未実装」として持つのと、**構想から消す**のは違う。
このファイルは後者が起きていないことを見張る。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.learning_contract import (  # noqa: E402
    ContributionTarget,
    DataResidency,
    IntelligenceScope,
    LearningEventType,
    LearningTaskId,
    learning_task_for,
    registered_task_ids,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402


class TestEventTypesAreNotNarrowedToTheStores(unittest.TestCase):
    """**Evidence Storeの型に縛らない**（017A §5）。"""

    def test_the_vocabulary_is_wider_than_the_four_stores(self) -> None:
        store_backed = {
            LearningEventType.GENERATION, LearningEventType.REVISION,
            LearningEventType.AI_CALL, LearningEventType.BENCHMARK,
        }
        self.assertGreater(
            len(set(LearningEventType)), len(store_backed),
            "Event種類がEvidence Storeの型数まで縮んでいる（構想から消していないか）",
        )

    def test_the_planned_types_survive(self) -> None:
        """**構想にあった種類を消さない。** 未実装でよいが、無くさない。"""
        for name in ("FEEDBACK", "REGENERATION", "BUILD", "COMPILE", "TEST",
                     "VALIDATION", "RUNTIME", "CRASH", "TOOL_RESULT"):
            with self.subTest(event_type=name):
                self.assertTrue(
                    hasattr(LearningEventType, name),
                    f"{name} が構想から消えている（017 §5の一覧を参照）",
                )

    def test_unimplemented_types_do_not_claim_to_be_emitted(self) -> None:
        """**「型があるから作れる」と混同しない**（Product Direction §7）。"""
        for event_type in (LearningEventType.BUILD, LearningEventType.CRASH,
                           LearningEventType.TOOL_RESULT, LearningEventType.RUNTIME):
            with self.subTest(event_type=event_type.value):
                self.assertFalse(event_type.is_emitted_today)

    def test_feedback_is_emitted_today(self) -> None:
        """017A §2でEventとして残るようにしたので、これは実際に作れる。"""
        self.assertTrue(LearningEventType.FEEDBACK.is_emitted_today)

    def test_feedback_is_its_own_event_not_an_attribute(self) -> None:
        """時系列がそれ自体Evidenceなので、生成物の属性では表せない。"""
        self.assertIn(LearningEventType.FEEDBACK, set(LearningEventType))


class TestTaskVocabularyIsNotForgeTaskOnly(unittest.TestCase):
    """**ForgeTaskはAI Routingの語彙であり、Learning SDKの語彙ではない**
    （017A §6）。"""

    def test_every_forge_task_has_a_learning_task_id(self) -> None:
        """**対応の書き忘れを見張る。**

        `ForgeTask`へ値を足した人がここを忘れると、そのTaskのEventだけ
        静かにLearning側から消える。
        """
        for task in ForgeTask:
            with self.subTest(task=task.value):
                self.assertIsInstance(learning_task_for(task), LearningTaskId)

    def test_there_are_task_ids_that_are_not_forge_tasks(self) -> None:
        """`flutter.build`はAIを呼ばないので`ForgeTask`になりようがない。

        それでもLearning Eventとしては事実である。`ForgeTask`へ無理に
        足すと、**Providerが要らないTaskがRouting表に並ぶ**。
        """
        mapped = {learning_task_for(t).value for t in ForgeTask}
        registered = {t.value for t in registered_task_ids()}
        self.assertTrue(registered - mapped, "ForgeTask以外のTaskが1つも無い")
        self.assertIn("flutter.build", registered)
        self.assertIn("runtime.render", registered)

    def test_task_ids_are_namespaced(self) -> None:
        for task_id in registered_task_ids():
            with self.subTest(task=task_id.value):
                self.assertIn(".", task_id.value)
                self.assertTrue(task_id.namespace)

    def test_free_text_is_rejected(self) -> None:
        """自由文が通ると、Datasetが誰にも読めないラベルで汚れる。"""
        for bad in ("Flutter Build", "build!", "ビルド", "", "a b"):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    LearningTaskId("flutter", bad)

    def test_an_uppercase_namespace_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LearningTaskId("Flutter", "build")

    def test_an_unmapped_task_raises_instead_of_defaulting(self) -> None:
        """**既定値へ落とさない。** 落とすと、対応を書き忘れたTaskが
        全部同じラベルに潰れて後から見分けられなくなる。"""
        import app.ai.gateway.learning_contract as contract

        saved = dict(contract._FORGE_TASK_MAPPING)
        try:
            contract._FORGE_TASK_MAPPING.pop(ForgeTask.ENTITY_SYNTHESIS)
            with self.assertRaises(KeyError):
                learning_task_for(ForgeTask.ENTITY_SYNTHESIS)
        finally:
            contract._FORGE_TASK_MAPPING.clear()
            contract._FORGE_TASK_MAPPING.update(saved)


class TestScopeIsSplitIntoAxes(unittest.TestCase):
    """**「誰の知能か」と「外へ出してよいか」を1つの値に兼ねさせない**
    （017A §10）。"""

    def test_the_two_axes_are_separate_types(self) -> None:
        self.assertNotEqual(set(IntelligenceScope), set(DataResidency))

    def test_residency_defaults_to_local_only(self) -> None:
        """**分からないものを「出してよい」へ倒さない。**"""
        self.assertEqual(DataResidency.LOCAL_ONLY.value, "local_only")
        # 既定として使う値が先頭に在ること(意図の表明)
        self.assertIs(next(iter(DataResidency)), DataResidency.LOCAL_ONLY)

    def test_contribution_defaults_to_none(self) -> None:
        self.assertIs(next(iter(ContributionTarget)), ContributionTarget.NONE)

    def test_app_scope_can_still_be_local_only(self) -> None:
        """1軸では表せない組み合わせが表せること。

        「Appの知能を改善するが、内容はCloudへ出せない」は実在する。
        """
        combination = (IntelligenceScope.APP, DataResidency.LOCAL_ONLY)
        self.assertEqual(combination[0].value, "app")
        self.assertEqual(combination[1].value, "local_only")

    def test_personal_and_cloud_eligible_are_independent_values(self) -> None:
        """`personal`が「外へ出すな」を兼ねていないこと。

        兼ねていると、片方の意図で書かれた値がもう片方の判断に使われる。
        Personalの既定を`local_only`にするのは**運用の規則**であって、
        型が勝手にそう決めるわけではない。
        """
        self.assertNotIn(
            IntelligenceScope.PERSONAL.value, {r.value for r in DataResidency}
        )


if __name__ == "__main__":
    unittest.main()
