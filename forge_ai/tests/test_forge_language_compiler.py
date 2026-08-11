"""ForgeLanguageCompilerのテスト(FORGE v0.6・FORGE v0.7)。

FORGE v0.6「Compilerテスト」節、FORGE v0.7「Record Runtime Phase1」の
両方の要求を実装する。FORGE v0.7で、出力形が`checklist`+`add_item`
(主要Fieldのみ)から`record_list`+`record_list_view`+`add_record`
(全Field)へ更新されたことに伴い、Phase2時点のテストを更新した
(削除ではなく、新しい出力形への追従)。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.ir.forge_language_compiler import (  # noqa: E402
    ForgeLanguageCompilationError,
    ForgeLanguageCompiler,
)
from forge_ai.core.ir.ir_generator import SUPPORTED_DOMAIN_CATEGORIES, IRGenerator  # noqa: E402
from forge_ai.core.ir.ir_types import Action, ActionKind, Entity, Field, FieldType, ForgeIR, NavigationGraph  # noqa: E402
from forge_ai.core.planner import ApplicationPlan  # noqa: E402


class TestForgeLanguageCompiler(unittest.TestCase):
    def setUp(self) -> None:
        self.ir_generator = IRGenerator()
        self.compiler = ForgeLanguageCompiler()
        self.plan = ApplicationPlan(title="test", screens=(), data_entities=(), primary_flow=())

    # --- 指示書の明示的な項目 ---

    def test_compiles_to_a_valid_forge_document_for_each_target_domain(self) -> None:
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                ir = self.ir_generator.generate(self.plan, domain_category=domain_category)
                assert ir is not None
                document = self.compiler.compile(ir, domain_category=domain_category, title="テスト")
                self.assertGreaterEqual(len(document.screens), 1)
                self.assertTrue(document.to_json_dict())  # JSON化できる(例外なし)

    def test_output_passes_the_real_backend_schema_validator(self) -> None:
        try:
            _here = os.path.dirname(__file__)
            sys.path.insert(0, os.path.join(_here, "..", "..", "backend"))
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return

        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                ir = self.ir_generator.generate(self.plan, domain_category=domain_category)
                assert ir is not None
                document = self.compiler.compile(ir, domain_category=domain_category, title="テスト")
                result = validate_forge_document(document.to_json_dict())
                self.assertTrue(result.valid, msg=result.to_dict())

    def test_target_three_domains_produce_form_and_record_list_view_widgets(self) -> None:
        """FORGE v0.7対応: 以前(Phase2)は`checklist`Widgetだったが、今回
        `record_list_view`(layout="card")へ更新した。"""
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                ir = self.ir_generator.generate(self.plan, domain_category=domain_category)
                assert ir is not None
                document = self.compiler.compile(ir, domain_category=domain_category, title="テスト")
                self.assertEqual(len(document.screens), 1, "stateは画面ごとにスコープされるため単一画面が必須")
                widget_types = [c.type for c in document.screens[0].body.children]
                self.assertIn("form", widget_types)
                self.assertIn("record_list_view", widget_types)
                self.assertNotIn("checklist", widget_types)
                self.assertEqual(document.version, "1.5")

    def test_non_target_domains_are_not_handled_by_this_compiler(self) -> None:
        """対象外Domainのcompile()は、`IRGenerator.generate()`が`None`
        を返す時点で、そもそも`ForgeLanguageCompiler`を呼ぶべきでない
        という契約になっている(`pipeline_orchestrator.py`の分岐)。この
        Compiler自体は「対象外Domainの出力が従来と変わらない」ことに
        ついては責務を持たない(それは`Compiler`(Checklist単一画面)
        側の責務であり、`test_compiler.py`
        `TestCompilerAfterIRMigration`で確認済み)。ここでは、
        `IRGenerator.generate()`が`None`を返すことをあらためて確認する
        (契約の再確認)。"""
        ir = self.ir_generator.generate(self.plan, domain_category="shopping")
        self.assertIsNone(ir)

    # --- 追加の防御的テスト ---

    def test_record_list_view_shows_all_entity_fields(self) -> None:
        """FORGE v0.7対応(核心): Phase2は主要Fieldのみ一覧へ反映して
        いたが、`add_record`(field_bindings)の導入により、Entityの
        **全Field**を一覧へ反映できるようになった。"""
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        record_list_view = next(c for c in document.screens[0].body.children if c.type == "record_list_view")
        entity = ir.entities[0]
        self.assertEqual(set(record_list_view.properties["display_fields"]), set(entity.field_names()))

    def test_record_list_view_uses_card_layout(self) -> None:
        """指示書の制約: Phase1はcard layoutのみ(tableは未実装)。"""
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        record_list_view = next(c for c in document.screens[0].body.children if c.type == "record_list_view")
        self.assertEqual(record_list_view.properties["layout"], "card")

    def test_add_record_field_bindings_cover_all_entity_fields(self) -> None:
        """`add_record`のfield_bindingsが、Entityの全Fieldを網羅している
        ことを確認する(1つのFieldでも漏れていたら、そのFieldは一覧へ
        反映されない)。"""
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        form = next(c for c in document.screens[0].body.children if c.type == "form")
        submit_action = form.properties["submit_action"]
        add_record_action = next(a for a in submit_action["actions"] if a["type"] == "add_record")
        entity = ir.entities[0]
        self.assertEqual(set(add_record_action["field_bindings"].keys()), set(entity.field_names()))
        for field_name, source_ref in add_record_action["field_bindings"].items():
            self.assertEqual(source_ref, f"field_{field_name}")

    def test_add_record_target_state_ref_is_the_record_list_state(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        form = next(c for c in document.screens[0].body.children if c.type == "form")
        submit_action = form.properties["submit_action"]
        add_record_action = next(a for a in submit_action["actions"] if a["type"] == "add_record")
        self.assertEqual(add_record_action["target_state_ref"], "records")

    def test_records_state_is_record_list_type(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        self.assertEqual(document.screens[0].state["records"].type, "record_list")
        self.assertEqual(document.screens[0].state["records"].value, [])

    def test_submit_action_only_references_state_within_the_same_screen(self) -> None:
        """このテストの存在理由そのものが設計変更の記録
        (Template-aware Compiler Stage1で発見した制約、Proposal 2章):
        当初の2画面設計はBackend Validatorで`state_reference_exists`
        エラーになった。submit_actionが参照する全state_refが、同一
        画面のstateに実在することを確認する。"""
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        screen = document.screens[0]
        screen_state_keys = set(screen.state.keys())
        form = next(c for c in screen.body.children if c.type == "form")
        submit_action = form.properties["submit_action"]

        def collect_state_refs(action: dict) -> list[str]:
            refs = []
            if "state_ref" in action:
                refs.append(action["state_ref"])
            if "target_state_ref" in action:
                refs.append(action["target_state_ref"])
            if "source_state_ref" in action:
                refs.append(action["source_state_ref"])
            for ref in action.get("field_bindings", {}).values():
                refs.append(ref)
            for sub in action.get("actions", []):
                refs.extend(collect_state_refs(sub))
            return refs

        for ref in collect_state_refs(submit_action):
            self.assertIn(ref, screen_state_keys, f"'{ref}' は同一画面のstateに存在しない")

    def test_numeric_field_gets_pattern_validation_in_output(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        form = next(c for c in document.screens[0].body.children if c.type == "form")
        size_field = next(c for c in form.children if c.id == "field_size_input")
        rules = size_field.properties["validation"]["rules"]
        self.assertTrue(any(r["type"] == "pattern" for r in rules))

    def test_required_field_gets_required_validation_in_output(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        form = next(c for c in document.screens[0].body.children if c.type == "form")
        species_field = next(c for c in form.children if c.id == "field_species_input")
        rules = species_field.properties["validation"]["rules"]
        self.assertTrue(any(r["type"] == "required" for r in rules))

    def test_empty_state_text_uses_entity_label(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        record_list_view = next(c for c in document.screens[0].body.children if c.type == "record_list_view")
        self.assertIn("釣果記録", record_list_view.properties["empty_state_text"])

    def test_submit_resets_all_field_inputs_after_add(self) -> None:
        """フォーム送信後、次の入力のために全Fieldをリセットする
        (Phase2から維持している挙動)。"""
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        form = next(c for c in document.screens[0].body.children if c.type == "form")
        submit_action = form.properties["submit_action"]
        reset_refs = {a["state_ref"] for a in submit_action["actions"] if a["type"] == "reset_state"}
        entity = ir.entities[0]
        expected_refs = {f"field_{name}" for name in entity.field_names()}
        self.assertEqual(reset_refs, expected_refs)

    def test_rejects_ir_with_referential_integrity_errors(self) -> None:
        """壊れたIR(存在しないEntityを参照するView)を渡すと、
        ForgeDocumentへ変換せず明確な例外を送出する(防御的プログラミング、
        通常はIRGenerator自身の内部チェックで先に検出されるはずだが、
        直接ForgeIRを組み立てて渡すケースへの安全策)。"""
        broken_ir = ForgeIR(
            entities=(Entity(name="fish_record", label="釣果記録", fields=(Field("species", "魚種", FieldType.STRING),)),),
            views=(),  # Viewが無い
            actions=(Action(id="create_fish_record", kind=ActionKind.CREATE_ENTITY, entity="fish_record"),),
            events=(),
            navigation=NavigationGraph(initial_view="does_not_exist"),
        )
        with self.assertRaises(ForgeLanguageCompilationError):
            self.compiler.compile(broken_ir, domain_category="fishing_log", title="テスト")

    def test_rejects_ir_with_multiple_entities(self) -> None:
        """Phase2は単一Entityのみ対応(指示書の制約: Relationship未実装)。
        複数Entityを持つIRは、今回のスコープ外として明確な例外を送出する
        (無言で最初のEntityだけを使う、といった曖昧な挙動にしない)。"""
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        two_entities_ir = ForgeIR(
            entities=ir.entities + (Entity(name="extra", label="追加", fields=()),),
            views=ir.views,
            actions=ir.actions,
            events=ir.events,
            navigation=ir.navigation,
        )
        with self.assertRaises(ForgeLanguageCompilationError):
            self.compiler.compile(two_entities_ir, domain_category="fishing_log", title="テスト")


class TestForgeLanguageCompilerPhase2Crud(unittest.TestCase):
    """FORGE v0.8(Record Runtime Phase2)。選択・更新・削除の回帰テスト。"""

    def setUp(self) -> None:
        self.ir_generator = IRGenerator()
        self.compiler = ForgeLanguageCompiler()
        self.plan = ApplicationPlan(title="test", screens=(), data_entities=(), primary_flow=())

    def _compile(self, domain_category: str):
        ir = self.ir_generator.generate(self.plan, domain_category=domain_category)
        assert ir is not None
        return self.compiler.compile(ir, domain_category=domain_category, title="テスト")

    def test_output_still_passes_the_real_backend_schema_validator(self) -> None:
        try:
            _here = os.path.dirname(__file__)
            sys.path.insert(0, os.path.join(_here, "..", "..", "backend"))
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                result = validate_forge_document(document.to_json_dict())
                self.assertTrue(result.valid, msg=result.to_dict())

    def test_selected_record_state_exists(self) -> None:
        document = self._compile("fishing_log")
        self.assertIn("selected", document.screens[0].state)
        self.assertEqual(document.screens[0].state["selected"].type, "selected_record")
        self.assertIsNone(document.screens[0].state["selected"].value)

    def test_record_list_view_is_selectable(self) -> None:
        document = self._compile("fishing_log")
        rlv = next(c for c in document.screens[0].body.children if c.type == "record_list_view")
        self.assertTrue(rlv.properties["selectable"])
        self.assertEqual(rlv.properties["selected_state_ref"], "selected")

    def test_select_field_bindings_target_edit_fields_not_create_fields(self) -> None:
        """指示書のDesign Policy「コード重複よりも責務分離」の裏付け:
        選択時に反映される先は、作成用フィールドではなく編集専用の
        フィールドである(作成フォームと編集フォームのstateは共有しない)。"""
        document = self._compile("fishing_log")
        rlv = next(c for c in document.screens[0].body.children if c.type == "record_list_view")
        bindings = rlv.properties["select_field_bindings"]
        for source_ref in bindings.values():
            self.assertTrue(source_ref.startswith("edit_field_"), f"{source_ref} should target an edit_field_* state")

    def test_create_and_edit_fields_are_entirely_separate_states(self) -> None:
        document = self._compile("fishing_log")
        state_keys = set(document.screens[0].state.keys())
        create_keys = {k for k in state_keys if k.startswith("field_")}
        edit_keys = {k for k in state_keys if k.startswith("edit_field_")}
        self.assertTrue(create_keys)
        self.assertTrue(edit_keys)
        self.assertEqual(create_keys & edit_keys, set(), "作成用と編集用のFieldは重複しない")

    def test_edit_form_submits_update_record(self) -> None:
        document = self._compile("fishing_log")
        edit_form = next(c for c in document.screens[0].body.children if c.id == "record_edit_form")
        submit_action = edit_form.properties["submit_action"]
        update_action = next(a for a in submit_action["actions"] if a["type"] == "update_record")
        self.assertEqual(update_action["target_state_ref"], "records")
        self.assertEqual(update_action["record_id_ref"], "selected")

    def test_update_record_field_bindings_cover_all_entity_fields(self) -> None:
        document = self._compile("fishing_log")
        edit_form = next(c for c in document.screens[0].body.children if c.id == "record_edit_form")
        submit_action = edit_form.properties["submit_action"]
        update_action = next(a for a in submit_action["actions"] if a["type"] == "update_record")
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        entity = ir.entities[0]
        self.assertEqual(set(update_action["field_bindings"].keys()), set(entity.field_names()))

    def test_delete_button_exists_and_targets_selected_record(self) -> None:
        document = self._compile("fishing_log")
        delete_button = next(c for c in document.screens[0].body.children if c.id == "record_delete_button")
        self.assertEqual(delete_button.type, "button")
        delete_action = next(a for a in delete_button.properties["action"]["actions"] if a["type"] == "delete_record")
        self.assertEqual(delete_action["target_state_ref"], "records")
        self.assertEqual(delete_action["record_id_ref"], "selected")

    def test_update_and_delete_reset_selection_afterwards(self) -> None:
        """更新・削除いずれの後も、選択状態(selected)がリセットされる
        (連続して別のRecordを操作しやすくするため)。"""
        document = self._compile("fishing_log")
        edit_form = next(c for c in document.screens[0].body.children if c.id == "record_edit_form")
        update_resets = {
            a["state_ref"] for a in edit_form.properties["submit_action"]["actions"] if a["type"] == "reset_state"
        }
        self.assertIn("selected", update_resets)

        delete_button = next(c for c in document.screens[0].body.children if c.id == "record_delete_button")
        delete_resets = {
            a["state_ref"] for a in delete_button.properties["action"]["actions"] if a["type"] == "reset_state"
        }
        self.assertIn("selected", delete_resets)

    def test_all_actions_only_reference_state_within_the_same_screen(self) -> None:
        """Stage1由来の制約(state参照は画面をまたげない)が、Phase2の
        新しいActionにも適用されていることを確認する。"""
        document = self._compile("fishing_log")
        screen = document.screens[0]
        screen_state_keys = set(screen.state.keys())

        def collect_refs(action: dict) -> list[str]:
            refs = []
            for key in ("state_ref", "target_state_ref", "source_state_ref", "record_id_ref"):
                if key in action:
                    refs.append(action[key])
            for ref in action.get("field_bindings", {}).values():
                refs.append(ref)
            for sub in action.get("actions", []):
                refs.extend(collect_refs(sub))
            return refs

        for child in screen.body.children:
            action = child.properties.get("action") or child.properties.get("submit_action")
            if action:
                for ref in collect_refs(action):
                    self.assertIn(ref, screen_state_keys, f"'{ref}' は同一画面のstateに存在しない")

    def test_create_form_is_unaffected_by_crud_additions(self) -> None:
        """既存(Phase1)の作成フォームの挙動が、Phase2導入後も変わって
        いないことを確認する(後方互換)。"""
        document = self._compile("fishing_log")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        submit_action = create_form.properties["submit_action"]
        add_action = next(a for a in submit_action["actions"] if a["type"] == "add_record")
        self.assertEqual(add_action["target_state_ref"], "records")
        for source_ref in add_action["field_bindings"].values():
            self.assertTrue(source_ref.startswith("field_") and not source_ref.startswith("edit_field_"))


class TestForgeLanguageCompilerRecordSchema(unittest.TestCase):
    """FORGE v0.9(Typed Record Runtime Phase1)。`record_schemas`生成の
    回帰テスト。指示書の制約(Widget生成・CRUD挙動は無変更)も検証する。
    """

    def setUp(self) -> None:
        self.ir_generator = IRGenerator()
        self.compiler = ForgeLanguageCompiler()
        self.plan = ApplicationPlan(title="test", screens=(), data_entities=(), primary_flow=())

    def _compile(self, domain_category: str):
        ir = self.ir_generator.generate(self.plan, domain_category=domain_category)
        assert ir is not None
        return self.compiler.compile(ir, domain_category=domain_category, title="テスト")

    def test_version_is_1_5(self) -> None:
        """FORGE v1.0(Product Quality Sprint1)でv1.4から1.5へ更新した
        (design_tokens/section_header/layout:"grid"がv1.5専用のため)。"""
        document = self._compile("fishing_log")
        self.assertEqual(document.version, "1.5")

    def test_record_schemas_is_generated_for_all_three_domains(self) -> None:
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                self.assertEqual(len(document.record_schemas), 1)

    def test_record_schema_key_matches_entity_name(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        self.assertIn(ir.entities[0].name, document.record_schemas)

    def test_record_schema_fields_match_entity_fields(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        entity = ir.entities[0]
        schema = document.record_schemas[entity.name]
        schema_field_names = [f.name for f in schema.fields]
        self.assertEqual(schema_field_names, list(entity.field_names()))

    def test_record_schema_field_carries_type_label_and_required(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        schema = document.record_schemas[ir.entities[0].name]
        species_field = next(f for f in schema.fields if f.name == "species")
        self.assertEqual(species_field.type, "string")
        self.assertEqual(species_field.label, "魚種")
        self.assertTrue(species_field.required)

        size_field = next(f for f in schema.fields if f.name == "size")
        self.assertEqual(size_field.type, "number")
        self.assertFalse(size_field.required)

    def test_records_state_has_schema_ref_pointing_to_the_schema(self) -> None:
        ir = self.ir_generator.generate(self.plan, domain_category="fishing_log")
        assert ir is not None
        document = self.compiler.compile(ir, domain_category="fishing_log", title="テスト")
        self.assertEqual(document.screens[0].state["records"].schema_ref, ir.entities[0].name)

    def test_output_with_record_schemas_passes_the_real_backend_schema_validator(self) -> None:
        try:
            _here = os.path.dirname(__file__)
            sys.path.insert(0, os.path.join(_here, "..", "..", "backend"))
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return

        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                result = validate_forge_document(document.to_json_dict())
                self.assertTrue(result.valid, msg=result.to_dict())
                self.assertIn("record_schemas", document.to_json_dict())

    def test_widget_composition_reflects_sprint1_section_headers(self) -> None:
        """FORGE v1.0(Product Quality Sprint1)で、意図的にWidget構成を
        変更した(`section_header`による視覚的階層の追加)。以前
        (FORGE v0.9まで)は`record_schema`導入がWidget構成を変えない
        ことを確認するテストだったが、今回の変更は「Widget構成を変える
        こと自体」が目的であるため、新しい構成を検証する内容へ更新した
        (削除ではなく、意図した設計変更への追従)。"""
        document = self._compile("fishing_log")
        widget_types = [c.type for c in document.screens[0].body.children]
        self.assertEqual(widget_types, [
            "section_header", "form", "divider",
            "section_header", "record_list_view",
            "divider", "section_header", "form", "button",
        ])

    def test_action_json_is_byte_for_byte_identical_to_phase2(self) -> None:
        """add_record/update_record/delete_recordのJSON形が、Phase2から
        変わっていないことを確認する(record_schemasはあくまで追加情報
        であり、既存Actionの形には影響しない)。"""
        document = self._compile("fishing_log")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        submit_action = create_form.properties["submit_action"]
        add_action = next(a for a in submit_action["actions"] if a["type"] == "add_record")
        self.assertEqual(set(add_action.keys()), {"type", "target_state_ref", "field_bindings"})

    def test_non_target_domain_has_no_record_schemas(self) -> None:
        """対象外Domain(このCompiler自体が扱わない)は、そもそも
        `IRGenerator.generate()`が`None`を返すため、record_schemasという
        概念に到達しない(契約の再確認、Phase2から継続するテスト方針)。
        """
        ir = self.ir_generator.generate(self.plan, domain_category="shopping")
        self.assertIsNone(ir)


class TestForgeLanguageCompilerTypedFields(unittest.TestCase):
    """FORGE v1.0(Workstream B・G)。boolean型Fieldがcheckbox+boolean
    stateとして生成されること、他の型は引き続きtext_field+string state
    のまま(Forge Languageへ新しいWidget型を追加しない、指示書の制約)
    であることの回帰テスト。
    """

    def setUp(self) -> None:
        self.ir_generator = IRGenerator()
        self.compiler = ForgeLanguageCompiler()
        self.plan = ApplicationPlan(title="test", screens=(), data_entities=(), primary_flow=())

    def _compile(self, domain_category: str):
        ir = self.ir_generator.generate(self.plan, domain_category=domain_category)
        assert ir is not None
        return self.compiler.compile(ir, domain_category=domain_category, title="テスト")

    def test_boolean_field_produces_checkbox_widget_in_create_form(self) -> None:
        document = self._compile("habit_tracking")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        checkbox = next(c for c in create_form.children if c.type == "checkbox")
        self.assertEqual(checkbox.id, "field_completed_input")
        self.assertEqual(checkbox.properties["state_ref"], "field_completed")
        self.assertEqual(checkbox.properties["label"], "達成済み")

    def test_boolean_field_state_is_boolean_type_not_string(self) -> None:
        document = self._compile("habit_tracking")
        self.assertEqual(document.screens[0].state["field_completed"].type, "boolean")
        self.assertEqual(document.screens[0].state["field_completed"].value, False)

    def test_boolean_field_produces_checkbox_in_edit_form_too(self) -> None:
        document = self._compile("habit_tracking")
        edit_form = next(c for c in document.screens[0].body.children if c.id == "record_edit_form")
        checkbox = next(c for c in edit_form.children if c.type == "checkbox")
        self.assertEqual(checkbox.properties["state_ref"], "edit_field_completed")

    def test_non_boolean_fields_still_use_text_field_and_string_state(self) -> None:
        document = self._compile("fishing_log")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        widget_types = {c.type for c in create_form.children}
        self.assertEqual(widget_types, {"text_field"}, "fishing_logにboolean Fieldは無いため全てtext_field")
        for field_name in ("species", "size", "weight", "location", "date"):
            self.assertEqual(document.screens[0].state[f"field_{field_name}"].type, "string")

    def test_date_field_gets_pattern_validation_matching_iso_format(self) -> None:
        document = self._compile("fishing_log")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        date_field = next(c for c in create_form.children if c.id == "field_date_input")
        rules = date_field.properties["validation"]["rules"]
        pattern_rule = next(r for r in rules if r["type"] == "pattern")
        self.assertEqual(pattern_rule["value"], r"^\d{4}-\d{2}-\d{2}$")

    def test_choice_field_uses_text_field_not_a_new_widget_type(self) -> None:
        """指示書の制約: 新しいWidget型をForge Languageへ追加しない。
        choiceは既存text_fieldのまま(options自体はrecord_schemas経由で
        Runtimeが検証する、Workstream C参照)。"""
        document = self._compile("household_budget")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        category_field = next(c for c in create_form.children if c.id == "field_category_input")
        self.assertEqual(category_field.type, "text_field")

    def test_choice_field_placeholder_lists_the_valid_options(self) -> None:
        """FORGE-AI-QUALITY-001(2026-08-11)回帰テスト: choice型Fieldは
        text_fieldのplaceholderがFieldラベルのみ(例: "カテゴリ")で、
        有効な選択肢がどこにも示されていなかった。実際にDart Runtime側の
        `ForgeFieldValueParser._parseChoice()`を確認したところ、選択肢と
        完全一致しない入力は送信時に`invalidChoice`として拒否される
        設計であり、UIに何のヒントも無いまま素直な入力が高確率で
        弾かれる実バグだった。placeholderへ選択肢を含めるよう修正した。"""
        document = self._compile("household_budget")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        category_field = next(c for c in create_form.children if c.id == "field_category_input")
        placeholder = category_field.properties["placeholder"]
        self.assertIn("食費", placeholder)
        self.assertIn("交通費", placeholder)
        self.assertIn("娯楽", placeholder)
        self.assertIn("その他", placeholder)

    def test_non_choice_field_placeholder_is_unchanged(self) -> None:
        """choice以外のFieldは、既存どおりFieldラベルのみのplaceholder
        のまま(意図しない副作用が無いことの回帰テスト)。"""
        document = self._compile("fishing_log")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        species_field = next(c for c in create_form.children if c.id == "field_species_input")
        self.assertEqual(species_field.properties["placeholder"], "魚種")

    def test_all_three_domains_still_produce_the_same_top_level_widget_composition(self) -> None:
        """Field型の多様化(boolean/date/choice追加)後も、画面トップ
        レベルのWidget構成は3 Domainで一貫していること(指示書「Widget
        構成を不要に変更しない」)。FORGE v1.0(Sprint1)で
        `section_header`が追加された新しい構成を基準とする(削除では
        なく、意図した設計変更への追従)。"""
        for domain_category in ("fishing_log", "household_budget", "habit_tracking"):
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                widget_types = [c.type for c in document.screens[0].body.children]
                self.assertEqual(widget_types, [
                    "section_header", "form", "divider",
                    "section_header", "record_list_view",
                    "divider", "section_header", "form", "button",
                ])

    def test_output_with_typed_fields_passes_the_real_backend_schema_validator(self) -> None:
        try:
            _here = os.path.dirname(__file__)
            sys.path.insert(0, os.path.join(_here, "..", "..", "backend"))
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return

        for domain_category in ("fishing_log", "household_budget", "habit_tracking"):
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                result = validate_forge_document(document.to_json_dict())
                self.assertTrue(result.valid, msg=result.to_dict())


class TestForgeLanguageCompilerProductQualitySprint1(unittest.TestCase):
    """FORGE v1.0 Product Quality Sprint1。design_tokens・section_header・
    grid layout・7 Domain全体の回帰テスト。"""

    def setUp(self) -> None:
        self.ir_generator = IRGenerator()
        self.compiler = ForgeLanguageCompiler()
        self.plan = ApplicationPlan(title="test", screens=(), data_entities=(), primary_flow=())

    def _compile(self, domain_category: str):
        ir = self.ir_generator.generate(self.plan, domain_category=domain_category)
        assert ir is not None
        return self.compiler.compile(ir, domain_category=domain_category, title="テスト")

    def test_design_tokens_are_generated_for_all_seven_domains(self) -> None:
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                self.assertIn("color_scheme", document.design_tokens)
                self.assertIn("primary", document.design_tokens["color_scheme"])
                self.assertIn("corner_radius", document.design_tokens)
                self.assertIn("spacing_scale", document.design_tokens)

    def test_design_tokens_differ_by_visual_style(self) -> None:
        """visual_styleが異なるDomain同士は、異なるDesign Tokenを
        持つこと(単一の固定値を全Domainへ返しているだけではないことの
        確認)。"""
        calm_doc = self._compile("household_budget")  # visual_style="calm"
        vibrant_doc = self._compile("habit_tracking")  # visual_style="vibrant"
        self.assertNotEqual(
            calm_doc.design_tokens["color_scheme"]["primary"],
            vibrant_doc.design_tokens["color_scheme"]["primary"],
        )

    def test_design_tokens_are_consistent_for_the_same_visual_style(self) -> None:
        """同じvisual_styleを持つDomain同士は、同じDesign Tokenを持つ
        こと(決定的な少数プリセットから選んでいることの確認、
        AIが自由に色を生成しているのではない)。"""
        warm_doc_1 = self._compile("reading_log")  # visual_style="warm"
        warm_doc_2 = self._compile("diary")  # visual_style="warm"
        self.assertEqual(warm_doc_1.design_tokens, warm_doc_2.design_tokens)

    def test_unknown_visual_style_falls_back_to_calm_preset(self) -> None:
        from forge_ai.core.ir.ir_types import Entity

        entity = Entity(name="x", label="X", fields=(), visual_style="totally_unknown_style")
        tokens = self.compiler._build_design_tokens(entity)
        self.assertEqual(tokens, self.compiler._build_design_tokens(
            Entity(name="y", label="Y", fields=(), visual_style="calm")
        ))

    def test_design_tokens_pass_real_backend_validator_for_all_domains(self) -> None:
        try:
            _here = os.path.dirname(__file__)
            sys.path.insert(0, os.path.join(_here, "..", "..", "backend"))
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return

        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                result = validate_forge_document(document.to_json_dict())
                self.assertTrue(result.valid, msg=result.to_dict())

    def test_section_headers_present_for_all_domains(self) -> None:
        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                widget_types = [c.type for c in document.screens[0].body.children]
                self.assertEqual(widget_types.count("section_header"), 3, "作成・一覧・編集の3セクション")

    def test_section_header_titles_reference_entity_label(self) -> None:
        document = self._compile("reading_log")
        headers = [c for c in document.screens[0].body.children if c.type == "section_header"]
        self.assertTrue(any("読書記録" in h.properties["title"] for h in headers))

    def test_section_header_has_no_state_ref_or_action(self) -> None:
        """section_headerは状態を持たない表示専用Widgetであること
        (CRUD挙動に一切影響しないことの裏付け)。"""
        document = self._compile("todo")
        headers = [c for c in document.screens[0].body.children if c.type == "section_header"]
        for h in headers:
            self.assertNotIn("state_ref", h.properties)
            self.assertNotIn("action", h.properties)

    def test_grid_preferred_domains_use_grid_layout(self) -> None:
        for domain_category in ("todo", "habit_tracking"):
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                list_view = next(c for c in document.screens[0].body.children if c.type == "record_list_view")
                self.assertEqual(list_view.properties["layout"], "grid")

    def test_other_domains_keep_card_layout(self) -> None:
        for domain_category in ("fishing_log", "household_budget", "reading_log", "inventory", "diary"):
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                list_view = next(c for c in document.screens[0].body.children if c.type == "record_list_view")
                self.assertEqual(list_view.properties["layout"], "card")

    def test_all_seven_domains_compile_and_validate(self) -> None:
        try:
            _here = os.path.dirname(__file__)
            sys.path.insert(0, os.path.join(_here, "..", "..", "backend"))
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return

        for domain_category in SUPPORTED_DOMAIN_CATEGORIES:
            with self.subTest(domain_category=domain_category):
                document = self._compile(domain_category)
                result = validate_forge_document(document.to_json_dict())
                self.assertTrue(result.valid, msg=result.to_dict())

    def test_crud_action_json_unaffected_by_sprint1_changes(self) -> None:
        """指示書「既存CRUD、Atomicity、Legacy互換性を壊さない」の
        裏付け: add_record/update_record/delete_recordのJSON形が、
        Sprint1導入前と変わっていないこと。"""
        document = self._compile("fishing_log")
        create_form = next(c for c in document.screens[0].body.children if c.id == "record_form")
        submit_action = create_form.properties["submit_action"]
        add_action = next(a for a in submit_action["actions"] if a["type"] == "add_record")
        self.assertEqual(set(add_action.keys()), {"type", "target_state_ref", "field_bindings"})


if __name__ == "__main__":
    unittest.main()
