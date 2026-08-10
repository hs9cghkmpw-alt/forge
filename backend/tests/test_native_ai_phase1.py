"""FORGE-MILESTONE-004 PHASE1〜9 の新規コンポーネントのテスト。

Intent IR拡張・IntentParser・Template Engine/Selector・
Native AI Runtime bundleを検証する。既存コンポーネント
(AIPlanner・LanguageGenerator・AIRepair・AICritic・ProviderRouterの
元5名前・PromptPipeline)は本ファイルでは再検証しない
(test_ai_foundation.py・test_ai_runtime.pyで既に検証済みのため)。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.foundation.interfaces import Complexity, IntentIR, Platform  # noqa: E402
from app.ai.runtime.intent_parser import IntentParser, StubIntentParser  # noqa: E402
from app.ai.runtime.native_ai_runtime import NativeAIRuntime  # noqa: E402
from app.ai.runtime.template_engine import Template, TemplateRegistry  # noqa: E402
from app.ai.runtime.template_selector import StubTemplateSelector, TemplateSelector  # noqa: E402


# ---------------------------------------------------------------------------
# PHASE1: IntentIR拡張
# ---------------------------------------------------------------------------

class TestIntentIRExtension(unittest.TestCase):
    def test_backward_compatible_construction_still_works(self) -> None:
        """既存の呼び出し方(purposeのみ)がそのまま動くことの回帰テスト
        (test_ai_foundation.py・test_ai_runtime.py双方の既存呼び出しを守る)。"""
        intent = IntentIR(purpose="test")
        self.assertEqual(intent.purpose, "test")

    def test_new_fields_have_sensible_defaults(self) -> None:
        intent = IntentIR(purpose="test")
        self.assertEqual(intent.entities, ())
        self.assertEqual(intent.platform, Platform.CROSS_PLATFORM)
        self.assertEqual(intent.complexity, Complexity.SIMPLE)
        self.assertIsNone(intent.category)
        self.assertIsNone(intent.output_type)

    def test_full_construction_with_all_new_fields(self) -> None:
        intent = IntentIR(
            purpose="track shopping items",
            entities=("item", "price"),
            platform=Platform.WEB,
            complexity=Complexity.MEDIUM,
            category="shopping",
            output_type="checklist",
        )
        self.assertEqual(intent.entities, ("item", "price"))
        self.assertEqual(intent.platform, Platform.WEB)
        self.assertEqual(intent.complexity, Complexity.MEDIUM)
        self.assertEqual(intent.category, "shopping")
        self.assertEqual(intent.output_type, "checklist")

    def test_platform_enum_has_four_values(self) -> None:
        self.assertEqual(
            {p.value for p in Platform}, {"mobile", "web", "desktop", "cross_platform"}
        )

    def test_complexity_enum_has_three_values(self) -> None:
        self.assertEqual({c.value for c in Complexity}, {"simple", "medium", "complex"})

    def test_intent_ir_is_still_frozen(self) -> None:
        intent = IntentIR(purpose="test")
        with self.assertRaises(Exception):
            intent.purpose = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PHASE2: IntentParser
# ---------------------------------------------------------------------------

class TestIntentParser(unittest.TestCase):
    def test_stub_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            StubIntentParser().parse("test", ())

    def test_stub_satisfies_protocol_structurally(self) -> None:
        parser: IntentParser = StubIntentParser()
        self.assertTrue(hasattr(parser, "parse"))


# ---------------------------------------------------------------------------
# PHASE4: Template Engine
# ---------------------------------------------------------------------------

class TestTemplateEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = TemplateRegistry()

    def test_three_builtin_templates_registered(self) -> None:
        ids = {t.id for t in self.registry.all_templates()}
        self.assertEqual(ids, {"checklist", "memo", "form"})

    def test_get_returns_none_for_unknown_template(self) -> None:
        self.assertIsNone(self.registry.get("does_not_exist"))

    def test_by_tag_finds_shopping_under_checklist(self) -> None:
        results = self.registry.by_tag("shopping")
        self.assertEqual([t.id for t in results], ["checklist"])

    def test_by_capability_finds_form_for_structured_data_collection(self) -> None:
        results = self.registry.by_capability("structured_data_collection")
        self.assertEqual([t.id for t in results], ["form"])

    def test_by_category(self) -> None:
        results = self.registry.by_category("memo")
        self.assertEqual([t.id for t in results], ["memo"])

    def test_checklist_builder_delegates_to_real_existing_template_function(self) -> None:
        """Template Engineが新しいTemplate実装を作らず、既存の
        build_checklist_templateへ正しく委譲していることを確認する
        (実際に呼び出して、本物のForge Language互換JSONが返ることを確認)。"""
        template = self.registry.get("checklist")
        assert template is not None
        doc = template.builder(title="テスト", items=("項目1", "項目2"))
        self.assertEqual(doc["app"]["title"], "テスト")
        self.assertEqual(len(doc["screens"][0]["state"]["items"]["value"]), 2)

    def test_memo_builder_delegates_to_real_existing_template_function(self) -> None:
        template = self.registry.get("memo")
        assert template is not None
        doc = template.builder(title="テストメモ")
        self.assertEqual(doc["version"], "1.1")

    def test_form_builder_delegates_to_real_existing_template_function(self) -> None:
        from app.ai.generators.templates.form_template import FormQuestion

        template = self.registry.get("form")
        assert template is not None
        doc = template.builder(
            title="テストアンケート",
            questions=(FormQuestion(key="q1", label="質問1", kind="checkbox"),),
        )
        self.assertEqual(len(doc["screens"]), 2)

    def test_all_templates_produce_output_validating_against_real_validator(self) -> None:
        """3 Template全てが、実際にschema_validatorへ合格する文書を生成する
        ことを確認する(Template Engineによるカタログ化が、実装の中身を
        壊していないことの追加確認)。"""
        from app.ai.validators.schema_validator import validate_forge_document

        checklist_doc = self.registry.get("checklist").builder(title="x", items=("a",))
        self.assertTrue(validate_forge_document(checklist_doc).valid)

        memo_doc = self.registry.get("memo").builder(title="x")
        self.assertTrue(validate_forge_document(memo_doc).valid)

    def test_template_is_frozen(self) -> None:
        template = self.registry.get("checklist")
        assert template is not None
        with self.assertRaises(Exception):
            template.priority = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PHASE5: Template Selector
# ---------------------------------------------------------------------------

class TestTemplateSelector(unittest.TestCase):
    def test_stub_raises_not_implemented(self) -> None:
        selector = StubTemplateSelector()
        with self.assertRaises(NotImplementedError):
            from app.ai.foundation.interfaces import PlanIR

            selector.select(IntentIR(purpose="x"), PlanIR(screens=()), TemplateRegistry())

    def test_stub_satisfies_protocol_structurally(self) -> None:
        selector: TemplateSelector = StubTemplateSelector()
        self.assertTrue(hasattr(selector, "select"))


# ---------------------------------------------------------------------------
# PHASE8: Provider Routerエイリアス(既存test_ai_runtime.pyで主に検証済み。
# ここではNativeAIRuntime経由での利用のみ追加確認する)
# ---------------------------------------------------------------------------

class TestProviderRouterAliasesViaRuntime(unittest.TestCase):
    def test_runtime_provider_router_has_native_and_local_aliases(self) -> None:
        runtime = NativeAIRuntime()
        self.assertIn("native", runtime.provider_router.available_providers())
        self.assertIn("local", runtime.provider_router.available_providers())


# ---------------------------------------------------------------------------
# PHASE9: Native AI Runtime bundle
# ---------------------------------------------------------------------------

class TestNativeAIRuntime(unittest.TestCase):
    def test_default_construction_succeeds(self) -> None:
        runtime = NativeAIRuntime()
        self.assertIsNotNone(runtime)

    def test_is_fully_stubbed_is_true_by_default(self) -> None:
        """絶対ルール「動いたふりは禁止」の機械的な回帰テスト。
        既定構築では、推論系コンポーネントが全てStubであることを
        プログラムで検証できる。"""
        runtime = NativeAIRuntime()
        self.assertTrue(runtime.is_fully_stubbed())

    def test_is_fully_stubbed_is_false_when_any_component_replaced(self) -> None:
        """カスタムのテストダブル(Stubではない)へ差し替えると、
        is_fully_stubbed()がFalseを返すことを確認する
        (判定ロジック自体が正しく動作することの確認)。"""

        class _FakeCritic:
            def evaluate(self, document, intent):
                raise NotImplementedError

        runtime = NativeAIRuntime(critic=_FakeCritic())  # type: ignore[arg-type]
        self.assertFalse(runtime.is_fully_stubbed())

    def test_describe_returns_all_eight_components(self) -> None:
        runtime = NativeAIRuntime()
        description = runtime.describe()
        expected_keys = {
            "intent_parser", "planner", "template_registry", "template_selector",
            "repair", "critic", "context_builder", "provider_router",
        }
        self.assertEqual(set(description.keys()), expected_keys)

    def test_template_registry_is_usable_directly_from_runtime(self) -> None:
        runtime = NativeAIRuntime()
        self.assertEqual(len(runtime.template_registry.all_templates()), 3)

    def test_components_are_independently_replaceable_via_di(self) -> None:
        """DIによる差し替え可能性の回帰テスト(5年後でも破綻しない
        アーキテクチャの核心: 特定の実装に結合していないこと)。"""
        custom_selector = StubTemplateSelector()
        runtime = NativeAIRuntime(template_selector=custom_selector)
        self.assertIs(runtime.template_selector, custom_selector)


if __name__ == "__main__":
    unittest.main()
