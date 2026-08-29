"""Semantic Role Extraction と Capability Decomposition の契約
（GENERATED-UI-QG-V2-R4 / TD87・TD89、2026-08-26）。

**このテストが守っているのは1つの規則である。**

> ACTOR と CONTEXT は、作るものの構造を決めてはならない。

「子ども」が体重・身長を呼び、「旅行」が持ち物リストを呼んでいたのが
TD89 であり、その両方がこの規則違反である。
"""

from __future__ import annotations

import unittest

from forge_ai.core.ir.capability_ir import entity_spec_from_plan
from forge_ai.core.semantics.capabilities import (
    SEMANTIC_CAPABILITIES,
    SupportLevel,
)
from forge_ai.core.semantics.capability_plan import (
    StructuralMode,
    plan_capabilities,
)
from forge_ai.core.semantics.roles import (
    SemanticRole,
    concepts_blocked_by_role,
    extract_semantic_roles,
)

KIDS = "子どもが朝の支度をひとつずつチェックできるようにしたい"
PHOTO = "旅行の写真を日付ごとに残してメモを付けたい"
ANALYTICS = "部署ごとの売上を月別に集計してグラフで比べたい"
GAME = "植物を育てながら音を組み合わせるゲームを作りたい"
STUDY = "英単語を出題して、正解率の推移を見たい"
WORKLOG = "今日やる作業を登録して、終わったものを消していきたい"
FINANCE = "毎日の収入と支出を記録して残高を見たい"
MAP = "釣った場所を地図に残して魚の種類を記録したい"


class TestRolesSeparateWhoFromWhat(unittest.TestCase):
    def test_a_child_is_an_actor(self) -> None:
        roles = extract_semantic_roles(KIDS)
        self.assertIn("child", roles.of(SemanticRole.ACTOR))
        self.assertNotIn("child", roles.of(SemanticRole.RECORDED_DATA))
        self.assertNotIn("child", roles.structural_values())

    def test_travel_is_a_context(self) -> None:
        roles = extract_semantic_roles(PHOTO)
        self.assertIn("travel", roles.of(SemanticRole.CONTEXT))
        self.assertNotIn("travel", roles.structural_values())

    def test_what_gets_recorded_comes_from_recorded_data(self) -> None:
        roles = extract_semantic_roles(PHOTO)
        self.assertEqual(
            roles.of(SemanticRole.RECORDED_DATA), ("photo", "date", "note"),
        )

    def test_structural_values_never_include_actor_or_context(self) -> None:
        """**この1行がこの層の全部である。**"""
        for need in (KIDS, PHOTO, ANALYTICS, GAME, STUDY, WORKLOG, FINANCE, MAP):
            with self.subTest(need=need):
                roles = extract_semantic_roles(need)
                structural = set(roles.structural_values())
                self.assertFalse(structural & set(roles.of(SemanticRole.ACTOR)))
                self.assertFalse(structural & set(roles.of(SemanticRole.CONTEXT)))

    def test_an_unknown_need_yields_no_roles(self) -> None:
        """**推測で埋めない。** 空欄は空欄のまま。"""
        self.assertTrue(extract_semantic_roles("ぷるぷるした何か").is_empty)
        self.assertTrue(extract_semantic_roles("").is_empty)


class TestConceptBlocking(unittest.TestCase):
    def test_actor_concepts_are_blocked_from_domain_selection(self) -> None:
        self.assertIn("child", concepts_blocked_by_role(KIDS))

    def test_context_concepts_are_blocked_from_domain_selection(self) -> None:
        self.assertIn("destination", concepts_blocked_by_role(PHOTO))

    def test_needs_that_are_genuinely_about_the_domain_are_not_blocked(self) -> None:
        """既に通っていた Need を壊さない。"""
        for need in ("買い物リストを作りたい", FINANCE, ANALYTICS):
            with self.subTest(need=need):
                self.assertEqual(concepts_blocked_by_role(need), frozenset())

    def test_a_context_word_is_the_subject_when_nothing_else_is_said(self) -> None:
        """**他に何も語られていなければ、その語が主題である。**

        実装中に既存 Golden が落ちて気付いた:
        「旅行の計画を立てたい」「スーパーで買う物を管理したい」は、
        場面しか語っていないのではなく、**場面が主題**である。
        """
        for need in ("旅行の計画を立てたい", "スーパーで買う物を管理したい"):
            with self.subTest(need=need):
                self.assertEqual(concepts_blocked_by_role(need), frozenset())


class TestCapabilityPlanShapes(unittest.TestCase):
    """020A2 で `PlanShape` を `StructuralMode` + views へ分けた。

    「どういう構造か」と「何を見たいか」は別の軸である——組み合わせ
    enum を増やすと、複数の見せ方を求められたときに残りが黙って消える
    （実測済み、`test_020a2_compositional_plan.py`）。
    """

    def test_each_need_gets_its_own_structure_and_views(self) -> None:
        expected = {
            KIDS: (StructuralMode.CHECKLIST, set()),
            WORKLOG: (StructuralMode.CHECKLIST, set()),
            PHOTO: (StructuralMode.RECORD_ENTITY, {"view.list"}),
            MAP: (StructuralMode.RECORD_ENTITY, {"view.list"}),
            GAME: (StructuralMode.RECORD_ENTITY, {"view.list"}),
            FINANCE: (StructuralMode.RECORD_ENTITY, {"view.list", "view.metric"}),
            ANALYTICS: (
                StructuralMode.RECORD_ENTITY,
                {"view.list", "view.group_compare", "view.bar_chart"},
            ),
            STUDY: (StructuralMode.RECORD_ENTITY, {"view.list", "view.trend"}),
        }
        for need, (structure, views) in expected.items():
            with self.subTest(need=need):
                plan = plan_capabilities(need)
                self.assertIs(plan.structure, structure)
                self.assertTrue(
                    views <= set(plan.views), f"{views} ⊄ {set(plan.views)}",
                )

    def test_the_morning_routine_records_nothing_and_is_a_checklist(self) -> None:
        plan = plan_capabilities(KIDS)
        self.assertEqual(plan.fields, ())
        self.assertEqual(plan.entity_label, "支度")
        self.assertIn("interact.check_off", plan.interactions)

    def test_the_photo_diary_records_photo_date_and_memo(self) -> None:
        plan = plan_capabilities(PHOTO)
        self.assertEqual([f.name for f in plan.fields], ["photo", "date", "note"])

    def test_context_becomes_a_field_only_for_comparison(self) -> None:
        """**「〜ごと」だけでは場面を記録項目にしない。**

        実装中に踏んだ: 「日付ごとに残して」の「ごと」で `group_by` が
        立ち、CONTEXT の「旅行」が写真1枚ごとの欄になっていた。
        """
        self.assertIn("department", [f.name for f in plan_capabilities(ANALYTICS).fields])
        self.assertNotIn("trip", [f.name for f in plan_capabilities(PHOTO).fields])

    def test_an_unknown_need_yields_an_unknown_structure(self) -> None:
        """**既定の checklist へ倒さない。**"""
        plan = plan_capabilities("ぷるぷるした何か")
        self.assertIs(plan.structure, StructuralMode.UNKNOWN)
        self.assertFalse(plan.is_actionable)


class TestThePlanAdmitsWhatForgeCannotDo(unittest.TestCase):
    def test_a_game_names_what_is_missing(self) -> None:
        """**無いものを checklist で代用して黙らない。**"""
        plan = plan_capabilities(GAME)
        self.assertIn("simulate.loop", plan.requested)
        self.assertIn("simulate.loop", plan.simulations)
        self.assertNotIn("simulate.loop", plan.missing)
        self.assertIn("effect.media_compose", plan.missing)

    def test_photo_is_recorded_as_partial_not_as_done(self) -> None:
        plan = plan_capabilities(PHOTO)
        self.assertIn("data.photo", plan.partial)
        self.assertIs(
            SEMANTIC_CAPABILITIES["data.photo"].support, SupportLevel.PARTIAL,
        )

    def test_trend_is_declared_partial(self) -> None:
        """推移は**時系列グラフではない**。近似だと書いてある。"""
        self.assertIn("view.trend", plan_capabilities(STUDY).partial)

    def test_every_catalog_entry_is_described(self) -> None:
        for capability_id, definition in SEMANTIC_CAPABILITIES.items():
            with self.subTest(capability=capability_id):
                self.assertIsInstance(definition.support, SupportLevel)
                self.assertTrue(definition.label_ja.strip())
                self.assertTrue(definition.intent.strip())

    def test_everything_not_implemented_says_what_it_cannot_do(self) -> None:
        """**「partial」とだけ書いて済ませない。**"""
        for definition in SEMANTIC_CAPABILITIES.values():
            if definition.support is SupportLevel.IMPLEMENTED:
                continue
            with self.subTest(capability=definition.id):
                self.assertTrue(definition.limitation.strip())


class TestPlanToEntitySpec(unittest.TestCase):
    def test_a_checklist_plan_has_no_entity(self) -> None:
        """checklist は Entity を持たない道具である。"""
        self.assertIsNone(entity_spec_from_plan(plan_capabilities(KIDS)))

    def test_an_unknown_plan_produces_nothing(self) -> None:
        self.assertIsNone(entity_spec_from_plan(plan_capabilities("ぷるぷるした何か")))

    def test_a_record_log_becomes_an_entity_spec(self) -> None:
        spec = entity_spec_from_plan(plan_capabilities(PHOTO))
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual([f.label for f in spec.field_specs], ["写真", "日付", "メモ"])
        # **最初の1つだけ必須。** 全部必須だと記録する前に全部埋めさせる。
        self.assertTrue(spec.field_specs[0].required)
        self.assertFalse(spec.field_specs[1].required)

    def test_money_is_additive_and_accuracy_is_averageable(self) -> None:
        """`CLAUDE.md` の Measure Semantics を守る。"""
        finance = entity_spec_from_plan(plan_capabilities(FINANCE))
        study = entity_spec_from_plan(plan_capabilities(STUDY))
        assert finance is not None and study is not None
        self.assertEqual(
            next(f for f in finance.field_specs if f.name == "amount").measure.value,
            "additive",
        )
        self.assertEqual(
            next(f for f in study.field_specs if f.name == "accuracy").measure.value,
            "averageable",
        )


class TestNoPerNeedTemplates(unittest.TestCase):
    """**専用 Template を作っていないことを固定する。**

    `kids_template` / `photo_template` を作れば8つの Need は違う画面に
    なる。それは対応したことにならない——9つ目でまた同じ問題が起きる。
    """

    def test_the_structural_vocabulary_stays_small(self) -> None:
        self.assertLessEqual(
            len(StructuralMode), 3,
            "Need ごとに構造を足している（それは Template と同じ）",
        )

    def test_no_structure_is_named_after_a_need(self) -> None:
        forbidden = ("kids", "photo", "analytics", "game", "study", "travel", "child")
        for mode in StructuralMode:
            for word in forbidden:
                self.assertNotIn(word, mode.value)


if __name__ == "__main__":
    unittest.main()


class TestSubjectTableNeverHoldsAnActorOrContext(unittest.TestCase):
    """**表の中身も固定する**（配線破壊試験 M11 の生存を受けて追加）。

    `_subject_of()` は構造役だけを回っていたが、それを守っていたのは
    **表に `child` / `travel` が無いこと**であって、コードではなかった。
    `_SUBJECT_LABELS` に1行足せば、Entity が「旅行」になる。

    表とコードの両方で規則を固定する。
    """

    def test_no_subject_label_is_an_actor_or_context_value(self) -> None:
        from forge_ai.core.semantics.capability_plan import _SUBJECT_LABELS
        from forge_ai.core.semantics.roles import _ROLE_LEXICON

        forbidden = {
            value for _surface, role, value in _ROLE_LEXICON
            if role in (SemanticRole.ACTOR, SemanticRole.CONTEXT)
        }
        overlap = forbidden & set(_SUBJECT_LABELS)
        self.assertEqual(
            overlap, set(),
            f"actor / context の値が Entity の主題表に載っている: {sorted(overlap)}",
        )

    def test_the_code_refuses_even_if_the_table_is_wrong(self) -> None:
        """表が壊れてもコード側が止めること。"""
        import forge_ai.core.semantics.capability_plan as module

        original = dict(module._SUBJECT_LABELS)
        try:
            module._SUBJECT_LABELS["travel"] = ("trip", "旅行")
            module._SUBJECT_LABELS["child"] = ("child", "こども")
            self.assertNotEqual(plan_capabilities(PHOTO).entity_label, "旅行")
            self.assertNotEqual(plan_capabilities(KIDS).entity_label, "こども")
        finally:
            module._SUBJECT_LABELS.clear()
            module._SUBJECT_LABELS.update(original)


class TestTheRecordCanBeIdentified(unittest.TestCase):
    """**数えられる対象には、1件ずつの名前が要る**（実描画で見て追加）。

    Round 4 の2回目、「英単語を出題して、正解率の推移を見たい」が
    **正解率の欄しか無い**画面になっていた。どの単語の正解率なのかを
    入れる場所が無い。
    """

    def test_a_managed_object_gets_its_own_field(self) -> None:
        for need, first in ((STUDY, "word"), (GAME, "plant"), (MAP, "fish")):
            with self.subTest(need=need):
                names = [f.name for f in plan_capabilities(need).fields]
                self.assertEqual(names[0], first, names)

    def test_a_plan_without_a_managed_object_does_not_invent_one(self) -> None:
        """**無い主題を捏造しない。**"""
        self.assertNotIn("item", [f.name for f in plan_capabilities(PHOTO).fields])

    def test_a_checklist_gains_no_field(self) -> None:
        self.assertEqual(plan_capabilities(KIDS).fields, ())

    def test_subject_of_role_refuses_actor_and_context(self) -> None:
        """**コードでも止める。** 表の中身だけに頼らない。"""
        from forge_ai.core.semantics.capability_plan import _subject_of_role

        roles = extract_semantic_roles(KIDS)
        for role in (SemanticRole.ACTOR, SemanticRole.CONTEXT):
            with self.subTest(role=role), self.assertRaises(ValueError):
                _subject_of_role(roles, role)
