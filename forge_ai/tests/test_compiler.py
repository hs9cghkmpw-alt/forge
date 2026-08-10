"""compiler.py のテスト。"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

from forge_ai.core.compiler import Compiler, ForgeIRWidget
from forge_ai.core.domain_model import DomainCategory, DomainRegistry
from forge_ai.core.intent_model import IntentBuilder
from forge_ai.core.meaning_model import MeaningExtractor
from forge_ai.core.planner import ApplicationPlan, Planner, ScreenPlan
from forge_ai.core.world_model import WorldModelBuilder
from forge_ai.provider.mock_provider import MockProvider


def _run_pipeline_to_compile(text: str, category: DomainCategory, provider: MockProvider):
    registry = DomainRegistry()
    world = WorldModelBuilder().build(registry.get(category))
    meaning = MeaningExtractor(provider).extract(text, world)
    intent = IntentBuilder(provider).build(meaning, world)
    plan = Planner(provider).plan(intent)
    return Compiler(provider).compile(plan)


class TestCompiler(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockProvider()

    def test_compile_produces_at_least_one_screen(self) -> None:
        ir = _run_pipeline_to_compile("add item track price", DomainCategory.SHOPPING, self.provider)
        self.assertGreaterEqual(len(ir.screens), 1)

    def test_compile_initial_screen_id_exists_in_screens(self) -> None:
        ir = _run_pipeline_to_compile("add item", DomainCategory.SHOPPING, self.provider)
        screen_ids = {s.id for s in ir.screens}
        self.assertIn(ir.initial_screen_id, screen_ids)

    def test_compile_uses_only_forge_widget_vocabulary(self) -> None:
        """Compilerが生成するWidget typeは、既知のForge Language v1.0語彙
        (text/text_field/button/column/row/checklist)のみであることを確認する。"""
        known_types = {"text", "text_field", "button", "column", "row", "checklist"}
        ir = _run_pipeline_to_compile("add item", DomainCategory.SHOPPING, self.provider)
        for screen in ir.screens:
            for widget in _flatten(screen.body):
                self.assertIn(widget.type, known_types, f"未知のWidget type: {widget.type}")

    def test_to_json_dict_is_json_serializable(self) -> None:
        import json

        ir = _run_pipeline_to_compile("add item", DomainCategory.SHOPPING, self.provider)
        serialized = json.dumps(ir.to_json_dict(), ensure_ascii=False)
        self.assertIsInstance(serialized, str)
        # 往復確認: JSON化→再parseしても同じ構造になる。
        reparsed = json.loads(serialized)
        self.assertEqual(reparsed["version"], "1.0")

    def test_compile_never_crashes_across_all_domains(self) -> None:
        for category in DomainCategory:
            with self.subTest(category=category):
                ir = _run_pipeline_to_compile(f"manage {category.value}", category, self.provider)
                self.assertIsNotNone(ir)

    def test_compile_handles_empty_key_elements_without_crashing(self) -> None:
        """MockProviderが1つも概念を返さなかった場合(空入力等)でも、
        Compilerが空のchecklistを作らず、最低1件のfallback itemを持つことを
        確認する(TECH_DEBT的な既知の空チェックリスト問題を未然に防ぐ)。"""
        ir = _run_pipeline_to_compile("", DomainCategory.GENERIC, self.provider)
        checklist_state = ir.screens[0].state["items"]
        self.assertGreater(len(checklist_state.value), 0)

    @unittest.skipUnless(
        importlib.util.find_spec("app") is not None or os.path.isdir(
            os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app")
        ),
        "backend/app が無い環境では外部検証をスキップする(forge_ai/自体の必須依存ではない)",
    )
    def test_compiled_output_validates_against_real_backend_validator(self) -> None:
        """forge_ai/自体はbackend/への依存を持たないが、テスト実行環境に
        backend/app/ai/validators/schema_validator.py がある場合に限り、
        実際に生成したForge IRが本物のValidatorに通ることを一度だけ
        追加確認する(forge_ai/の必須テストではなく、統合的な安心材料)。"""
        backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        try:
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return

        for category in DomainCategory:
            with self.subTest(category=category):
                ir = _run_pipeline_to_compile(f"manage {category.value} records", category, self.provider)
                result = validate_forge_document(ir.to_json_dict())
                self.assertTrue(result.valid, msg=result.to_dict())


def _flatten(widget: ForgeIRWidget) -> list[ForgeIRWidget]:
    result = [widget]
    for child in widget.children:
        result.extend(_flatten(child))
    return result


class TestCompilerRealisticExampleItems(unittest.TestCase):
    """FORGE_v0.2_修正指示.md P3(可能なら)の回帰テスト:
    「item / price / quantity」のような内部の概念識別子ではなく、
    ユーザーが完成品と感じられる現実的な初期データを使う。"""

    def setUp(self) -> None:
        self.provider = MockProvider()

    def _compile_with_key_elements(self, key_elements: tuple[str, ...]):
        plan = ApplicationPlan(
            title="テストアプリ",
            screens=(ScreenPlan(name="main", purpose="test", key_elements=key_elements),),
            data_entities=key_elements,
            primary_flow=(),
        )
        return Compiler(self.provider).compile(plan)

    def test_shopping_item_concept_uses_realistic_grocery_examples(self) -> None:
        """指示書の例(牛乳・卵・パン)そのものを検証する。"""
        ir = self._compile_with_key_elements(("item", "price", "quantity", "store"))
        texts = [entry["text"] for entry in ir.screens[0].state["items"].value]
        self.assertEqual(texts, ["牛乳", "卵", "パン"])
        self.assertNotIn("item", texts)
        self.assertNotIn("price", texts)
        self.assertNotIn("quantity", texts)

    def test_task_concept_uses_realistic_task_examples(self) -> None:
        ir = self._compile_with_key_elements(("task", "deadline", "priority"))
        texts = [entry["text"] for entry in ir.screens[0].state["items"].value]
        self.assertNotIn("task", texts)
        self.assertTrue(all(len(t) > 1 for t in texts))  # 生の識別子1語だけではない

    def test_unknown_concept_falls_back_to_raw_key_elements_without_crashing(self) -> None:
        """既知の概念テーブルに無い識別子は、既存動作(生の識別子を
        そのまま使う)へ安全にフォールバックする(既存の未知Domainでの
        回帰を防ぐ)。"""
        ir = self._compile_with_key_elements(("totally_unknown_concept_xyz",))
        texts = [entry["text"] for entry in ir.screens[0].state["items"].value]
        self.assertEqual(texts, ["totally_unknown_concept_xyz"])

    def test_empty_key_elements_still_falls_back_to_generic_item(self) -> None:
        """既存の空要素フォールバック(`["item"]`)は、今回の変更でも
        壊れていない(むしろ"item"という識別子自体が、Shopping向けの
        例値テーブルにも登録されているため、空の場合は牛乳・卵・パンに
        なる。これは意図した挙動である: 空の場合の既定Domainは
        Shopping相当のGenericフォールバックのため)。"""
        ir = self._compile_with_key_elements(())
        texts = [entry["text"] for entry in ir.screens[0].state["items"].value]
        self.assertGreater(len(texts), 0)


class TestCompilerAfterIRMigration(unittest.TestCase):
    """FORGE v0.6(FORGE IR v1 Phase2)の回帰テスト。

    Template-aware Compiler Stage1(FORGE v0.3)で`Compiler`へ一時的に
    追加した「Data Model登録Domainなら複数フィールドの単一画面を返す」
    という分岐は、`forge_ai/core/ir/`パッケージへ移設した
    (`forge_ai/tests/test_ir_generator.py`・
    `forge_ai/tests/test_forge_language_compiler.py`参照)。この
    クラスは、`Compiler`自体が(移設後も)Checklist単一画面という
    単一の責務に戻っていることを確認する。
    """

    def setUp(self) -> None:
        self.provider = MockProvider()
        self.compiler = Compiler(self.provider)
        self.plan = ApplicationPlan(
            title="テスト",
            screens=(ScreenPlan(name="main", purpose="test", key_elements=("species", "size")),),
            data_entities=("species", "size"),
            primary_flow=(),
        )

    def test_compiler_always_produces_checklist_template_regardless_of_domain_category(self) -> None:
        """`domain_category`に、FORGE IR v1移設対象の3 Domain
        (fishing_log等)を渡しても、`Compiler`自体はもう特別扱いせず、
        常にChecklist単一画面(version 1.0)を返す(後方互換の一部として
        パラメータ自体は残しているが、無視される)。"""
        for domain_category in (None, "shopping", "fishing_log", "household_budget", "habit_tracking"):
            with self.subTest(domain_category=domain_category):
                ir = self.compiler.compile(self.plan, domain_category=domain_category)
                self.assertEqual(ir.version, "1.0")
                self.assertEqual(len(ir.screens), 1)
                widget_types = [c.type for c in ir.screens[0].body.children]
                self.assertNotIn("form", widget_types)
                self.assertIn("checklist", widget_types)

    def test_compile_without_domain_category_argument_still_works(self) -> None:
        """`domain_category`省略時(既存呼び出し元との後方互換)も
        正しく動作する。"""
        ir = self.compiler.compile(self.plan)
        self.assertEqual(ir.version, "1.0")


if __name__ == "__main__":
    unittest.main()
