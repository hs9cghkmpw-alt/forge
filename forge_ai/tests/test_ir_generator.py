"""IRGeneratorのテスト(FORGE v0.6、FORGE IR v1 Phase2)。

指示書「FORGE v0.6 開発指示」の「IRGeneratorテスト」節に列挙された
項目を実装する。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.ir.ir_generator import SUPPORTED_DOMAIN_CATEGORIES, IRGenerator  # noqa: E402
from forge_ai.core.ir.ir_types import ActionKind, Entity, EventTrigger, FieldType, ViewKind  # noqa: E402
from forge_ai.core.planner import ApplicationPlan  # noqa: E402


class TestIRGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = IRGenerator()
        # `IRGenerator.generate()`は現状`plan`の内容を使わない(決定的に
        # `domain_category`だけから導出するため)、テストでは最小限の
        # ApplicationPlanを渡す。
        self.plan = ApplicationPlan(title="test", screens=(), data_entities=(), primary_flow=())

    # --- 指示書の明示的な項目 ---

    def test_fishing_log_produces_fish_record_entity(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        self.assertEqual(len(ir.entities), 1)
        entity = ir.entities[0]
        self.assertEqual(entity.name, "fish_record")
        self.assertEqual(entity.label, "釣果記録")
        self.assertEqual(entity.field_names(), ("species", "size", "weight", "location", "date"))

    def test_household_budget_produces_transaction_entity(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="household_budget")
        assert ir is not None
        entity = ir.entities[0]
        self.assertEqual(entity.name, "transaction")
        # v1.12(FORGE-R1-CLOSURE-015 §2.3)で`entry_type`(収支の別)を足した。
        # それまで収入と支出を区別できず、いくら記録しても
        # 「今いくら残っているか」に答えられなかった。
        self.assertEqual(
            entity.field_names(), ("entry_type", "category", "amount", "date", "payment_method")
        )
        self.assertIsNotNone(entity.monetary_flow, "お金の出入りが宣言されていない")
        self.assertEqual(entity.monetary_flow.amount_field, "amount")
        self.assertEqual(entity.monetary_flow.outflow_value, "支出")

    def test_habit_tracking_produces_habit_entity(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="habit_tracking")
        assert ir is not None
        entity = ir.entities[0]
        self.assertEqual(entity.name, "habit")
        self.assertEqual(entity.field_names(), ("name", "goal", "completed", "date"))

    def test_view_action_event_references_are_consistent(self) -> None:
        """View・Action・Event参照が整合していることを、3 Domain全てに
        ついて確認する(`ForgeIR.referential_integrity_errors()`を使う、
        IRGeneratorが内部で使っているのと同じ検査を、テスト側からも
        独立して実行する)。"""
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                ir = self.generator.generate(self.plan, domain_category=domain_category)
                assert ir is not None
                self.assertEqual(ir.referential_integrity_errors(), ())

    def test_same_input_always_produces_the_same_ir(self) -> None:
        """同じ入力から常に同じIRが生成される(決定的生成の確認)。"""
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                first = self.generator.generate(self.plan, domain_category=domain_category)
                second = self.generator.generate(self.plan, domain_category=domain_category)
                self.assertEqual(first, second)

    # --- 追加の防御的テスト ---

    def test_unsupported_domain_returns_none(self) -> None:
        """対象外Domainは`None`を返す(例外にしない、フォールバック
        判断を呼び出し側に委ねるため)。"""
        self.assertIsNone(self.generator.generate(self.plan, domain_category="shopping"))
        self.assertIsNone(self.generator.generate(self.plan, domain_category="unknown_domain_xyz"))

    def test_supported_domain_categories_contains_exactly_the_three_target_domains(self) -> None:
        """FORGE v1.0 Product Quality Sprint1でCurated Domain Libraryを
        7 Domainへ拡張した(todo/reading_log/inventory/diaryを追加)。
        テスト名は過去の経緯(Stage1時点で「3 Domain」だった)を残す
        ため変更していないが、内容は現在の7 Domainを検証する。"""
        self.assertEqual(
            SUPPORTED_DOMAIN_CATEGORIES,
            frozenset({
                "fishing_log", "household_budget", "habit_tracking",
                "todo", "reading_log", "inventory", "diary",
            }),
        )

    def test_list_view_and_form_view_both_exist_for_each_domain(self) -> None:
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                ir = self.generator.generate(self.plan, domain_category=domain_category)
                assert ir is not None
                kinds = {v.kind for v in ir.views}
                self.assertIn(ViewKind.LIST, kinds)
                self.assertIn(ViewKind.FORM, kinds)

    def test_form_view_has_create_mode(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        form_view = next(v for v in ir.views if v.kind == ViewKind.FORM)
        self.assertEqual(form_view.mode, "create")

    def test_create_entity_action_exists_and_targets_the_entity(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        create_actions = [a for a in ir.actions if a.kind == ActionKind.CREATE_ENTITY]
        self.assertEqual(len(create_actions), 1)
        self.assertEqual(create_actions[0].entity, "fish_record")

    def test_submit_event_binds_form_view_to_create_action(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        form_view = next(v for v in ir.views if v.kind == ViewKind.FORM)
        create_action = next(a for a in ir.actions if a.kind == ActionKind.CREATE_ENTITY)
        matching_events = [
            e for e in ir.events if e.source_view == form_view.id and e.action == create_action.id
        ]
        self.assertEqual(len(matching_events), 1)
        self.assertEqual(matching_events[0].trigger, EventTrigger.SUBMIT)

    def test_navigation_graph_initial_view_is_the_list_view(self) -> None:
        """Stage1のForge Language Compilerが単一画面に畳み込むため、
        現状`edges`は空になる(ir_generator.pyのコメント参照)。"""
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        list_view = next(v for v in ir.views if v.kind == ViewKind.LIST)
        self.assertEqual(ir.navigation.initial_view, list_view.id)
        self.assertEqual(ir.navigation.edges, ())

    def test_numeric_fields_have_number_type_and_pattern_validation(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        entity = ir.entities[0]
        size_field = next(f for f in entity.fields if f.name == "size")
        self.assertEqual(size_field.type, FieldType.NUMBER)
        self.assertTrue(any(v.type == "pattern" for v in size_field.validations))

    def test_required_fields_have_required_validation(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        entity = ir.entities[0]
        species_field = next(f for f in entity.fields if f.name == "species")
        self.assertTrue(species_field.required)
        self.assertTrue(any(v.type == "required" for v in species_field.validations))

    def test_optional_fields_have_no_required_validation(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        entity = ir.entities[0]
        location_field = next(f for f in entity.fields if f.name == "location")
        self.assertFalse(location_field.required)
        self.assertFalse(any(v.type == "required" for v in location_field.validations))

    def test_boolean_field_has_boolean_type_and_no_pattern_validation(self) -> None:
        """FORGE v1.0(Workstream G)新規: booleanは`add_record`同様、
        `pattern`によるstring検査を課さない(値そのものがbool型のstateに
        束縛されるため、Compiler側の設計、forge_language_compiler.py
        参照)。"""
        ir = self.generator.generate(self.plan, domain_category="habit_tracking")
        assert ir is not None
        entity = ir.entities[0]
        completed_field = next(f for f in entity.fields if f.name == "completed")
        self.assertEqual(completed_field.type, FieldType.BOOLEAN)
        self.assertFalse(completed_field.required)
        self.assertFalse(any(v.type == "pattern" for v in completed_field.validations))

    def test_date_field_has_date_type_and_pattern_validation(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        entity = ir.entities[0]
        date_field = next(f for f in entity.fields if f.name == "date")
        self.assertEqual(date_field.type, FieldType.DATE)
        self.assertTrue(any(v.type == "pattern" for v in date_field.validations))

    def test_choice_field_has_choice_type_and_grounded_options(self) -> None:
        """FORGE v1.0(Workstream G)新規: `category`のoptionsは、既存の
        `compiler.py`の`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT["transaction"]`
        (架空ではなく既存コードに実在する例)に基づく(根拠の無い
        choice optionsを発明していないことの裏付け)。"""
        ir = self.generator.generate(self.plan, domain_category="household_budget")
        assert ir is not None
        entity = ir.entities[0]
        category_field = next(f for f in entity.fields if f.name == "category")
        self.assertEqual(category_field.type, FieldType.CHOICE)
        self.assertIn("食費", category_field.choices)
        self.assertIn("交通費", category_field.choices)
        self.assertIn("娯楽", category_field.choices)

    def test_species_field_remains_string_no_invented_choices(self) -> None:
        """FORGE v1.0(Workstream G)新規: `species`(魚種)には既存の
        「固定選択肢」データが無いため、string型のまま維持している
        (choice型へ勝手に変換していないことの裏付け)。"""
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        entity = ir.entities[0]
        species_field = next(f for f in entity.fields if f.name == "species")
        self.assertEqual(species_field.type, FieldType.STRING)
        self.assertEqual(species_field.choices, ())

    def test_all_three_domains_use_all_five_supported_types_collectively(self) -> None:
        """3 Domain全体で、Supported Typesの5種(string/number/boolean/
        date/choice)全てが実際に使われていることを確認する(Workstream
        B〜Dの型別実装を3 Domainで実地検証できるようにするための設計
        意図の裏付け)。"""
        used_types: set[FieldType] = set()
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            ir = self.generator.generate(self.plan, domain_category=domain_category)
            assert ir is not None
            used_types.update(f.type for f in ir.entities[0].fields)
        self.assertEqual(used_types, {
            FieldType.STRING, FieldType.NUMBER, FieldType.BOOLEAN, FieldType.DATE, FieldType.CHOICE,
        })

    def test_field_type_is_the_only_source_of_truth_for_a_fields_type(self) -> None:
        """FORGE v1.0 Workstream A監査の裏付け: `_FieldSpec`はもはや
        `is_numeric`という影の型情報を持たない(`FieldType`のみが
        Source of Truthであることの直接確認)。"""
        from forge_ai.core.ir.ir_generator import _FieldSpec

        self.assertNotIn("is_numeric", _FieldSpec.__slots__)
        self.assertIn("field_type", _FieldSpec.__slots__)

    def test_primary_field_for_no_longer_exists(self) -> None:
        """FORGE v1.0 Workstream A監査で発見した死んだコード
        (`primary_field_for`)が削除されたことの回帰テスト
        (再度追加された場合、それが実際に使われているかを再監査する
        きっかけになるようにする)。"""
        import forge_ai.core.ir.ir_generator as ir_generator_module

        self.assertFalse(hasattr(ir_generator_module, "primary_field_for"))

    def test_list_view_display_fields_cover_all_entity_fields(self) -> None:
        """一覧Viewの`display_fields`が、Entityの全Fieldを含んでいる
        こと(Forge Language Compilerが現状主要Fieldしか反映できない
        こと自体は、ForgeLanguageCompiler側の制約であり、IR自体は
        全Field分の意図を保持しているべき、というProposal 3章の
        方針を裏付ける)。"""
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        list_view = next(v for v in ir.views if v.kind == ViewKind.LIST)
        entity = ir.entities[0]
        self.assertEqual(set(list_view.display_fields), set(entity.field_names()))


class TestIRGeneratorPhase2Crud(unittest.TestCase):
    """FORGE v0.8(Record Runtime Phase2)。update/delete Actionと編集Viewの回帰テスト。"""

    def setUp(self) -> None:
        self.generator = IRGenerator()
        self.plan = ApplicationPlan(title="test", screens=(), data_entities=(), primary_flow=())

    def test_update_and_delete_entity_actions_exist(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        kinds = {a.kind for a in ir.actions}
        self.assertIn(ActionKind.UPDATE_ENTITY, kinds)
        self.assertIn(ActionKind.DELETE_ENTITY, kinds)
        # CREATE_ENTITYもPhase2導入前と変わらず存在すること(後方互換)。
        self.assertIn(ActionKind.CREATE_ENTITY, kinds)

    def test_update_and_delete_actions_target_the_entity(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        update_action = next(a for a in ir.actions if a.kind == ActionKind.UPDATE_ENTITY)
        delete_action = next(a for a in ir.actions if a.kind == ActionKind.DELETE_ENTITY)
        self.assertEqual(update_action.entity, "fish_record")
        self.assertEqual(delete_action.entity, "fish_record")

    def test_edit_form_view_exists_with_edit_mode(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        edit_views = [v for v in ir.views if v.kind == ViewKind.FORM and v.mode == "edit"]
        self.assertEqual(len(edit_views), 1)
        # 作成用(mode="create")のForm Viewは、Phase2導入後も引き続き
        # 別に1件存在する(編集用Viewで置き換えられていないこと)。
        create_views = [v for v in ir.views if v.kind == ViewKind.FORM and v.mode == "create"]
        self.assertEqual(len(create_views), 1)

    def test_edit_form_submit_event_binds_to_update_action(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        edit_view = next(v for v in ir.views if v.kind == ViewKind.FORM and v.mode == "edit")
        update_action = next(a for a in ir.actions if a.kind == ActionKind.UPDATE_ENTITY)
        matching = [e for e in ir.events if e.source_view == edit_view.id and e.action == update_action.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].trigger, EventTrigger.SUBMIT)

    def test_list_view_tap_event_binds_to_delete_action(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        list_view = next(v for v in ir.views if v.kind == ViewKind.LIST)
        delete_action = next(a for a in ir.actions if a.kind == ActionKind.DELETE_ENTITY)
        matching = [e for e in ir.events if e.source_view == list_view.id and e.action == delete_action.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].trigger, EventTrigger.TAP)

    def test_all_three_domains_have_full_crud_ir_shape(self) -> None:
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                ir = self.generator.generate(self.plan, domain_category=domain_category)
                assert ir is not None
                self.assertEqual(len(ir.views), 3, "list + create form + edit form")
                self.assertEqual(len(ir.actions), 3, "create + update + delete")
                self.assertEqual(len(ir.events), 3, "submit(create) + submit(edit) + tap(delete)")
                self.assertEqual(ir.referential_integrity_errors(), ())

    def test_ir_does_not_define_a_select_action_kind(self) -> None:
        """設計判断の裏付け(ir_generator.pyモジュールdocstring参照):
        「選択」はIRのActionKindには存在しない、Forge Language
        Compiler固有の実装詳細である。"""
        self.assertFalse(hasattr(ActionKind, "SELECT_ENTITY"))


class TestIRGeneratorProductQualitySprint1(unittest.TestCase):
    """FORGE v1.0 Product Quality Sprint1。Curated Domain Library
    拡張(todo/reading_log/inventory/diary)とvisual_styleの回帰テスト。
    """

    def setUp(self) -> None:
        self.generator = IRGenerator()
        self.plan = ApplicationPlan(title="test", screens=(), data_entities=(), primary_flow=())

    def test_todo_domain_has_expected_fields(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="todo")
        assert ir is not None
        entity = ir.entities[0]
        self.assertEqual(entity.name, "todo_item")
        self.assertEqual(entity.field_names(), ("title", "priority", "due_date", "completed"))
        priority_field = next(f for f in entity.fields if f.name == "priority")
        self.assertEqual(priority_field.type, FieldType.CHOICE)
        self.assertEqual(priority_field.choices, ("高", "中", "低"))

    def test_reading_log_domain_has_expected_fields(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="reading_log")
        assert ir is not None
        entity = ir.entities[0]
        self.assertEqual(entity.name, "book_record")
        self.assertEqual(entity.field_names(), ("title", "author", "status", "rating", "finished_date"))
        status_field = next(f for f in entity.fields if f.name == "status")
        self.assertEqual(status_field.choices, ("読みたい", "読書中", "読了"))
        rating_field = next(f for f in entity.fields if f.name == "rating")
        self.assertEqual(rating_field.type, FieldType.NUMBER)

    def test_inventory_domain_has_expected_fields(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="inventory")
        assert ir is not None
        entity = ir.entities[0]
        self.assertEqual(entity.name, "inventory_item")
        self.assertEqual(entity.field_names(), ("item_name", "quantity", "category", "expiry_date", "location"))
        quantity_field = next(f for f in entity.fields if f.name == "quantity")
        self.assertTrue(quantity_field.required)

    def test_diary_domain_has_expected_fields(self) -> None:
        ir = self.generator.generate(self.plan, domain_category="diary")
        assert ir is not None
        entity = ir.entities[0]
        self.assertEqual(entity.name, "diary_entry")
        self.assertEqual(entity.field_names(), ("title", "content", "mood", "date"))
        mood_field = next(f for f in entity.fields if f.name == "mood")
        self.assertEqual(len(mood_field.choices), 5)

    def test_all_seven_domains_produce_valid_referentially_consistent_ir(self) -> None:
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                ir = self.generator.generate(self.plan, domain_category=domain_category)
                assert ir is not None
                self.assertEqual(ir.referential_integrity_errors(), ())

    def test_every_domain_has_a_visual_style(self) -> None:
        """FORGE v1.0新規。全Domainが`visual_style`(platform非依存の
        雰囲気ヒント)を持つことを確認する。"""
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                ir = self.generator.generate(self.plan, domain_category=domain_category)
                assert ir is not None
                self.assertIn(ir.entities[0].visual_style, {"calm", "warm", "vibrant", "neutral"})

    def test_visual_style_default_is_calm_when_unspecified(self) -> None:
        """Entityのvisual_styleは既定値"calm"を持つ(既存呼び出し方が
        壊れていないことの確認、後方互換性)。"""
        entity = Entity(name="x", label="X", fields=())
        self.assertEqual(entity.visual_style, "calm")

    def test_new_domains_do_not_invent_ungrounded_choice_options_beyond_curation(self) -> None:
        """指示書の制約の裏付け: choice型のFieldは全て、このモジュール
        自身が明示的にCurationした固定リストを持ち、実行時に動的生成
        されたものではない(決定的生成であることの再確認、
        test_same_input_always_produces_the_same_irと同じ観点)。"""
        for domain_category in ("todo", "reading_log", "inventory", "diary"):
            first = self.generator.generate(self.plan, domain_category=domain_category)
            second = self.generator.generate(self.plan, domain_category=domain_category)
            assert first is not None and second is not None
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
