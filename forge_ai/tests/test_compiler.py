"""compiler.py のテスト。"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

from forge_ai.core.compiler import MAX_TITLE_LENGTH, Compiler, ForgeIRWidget, clamp_title
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
        # FORGE-PRODUCT-VISION-002(2026-08-12)対応: design_tokensを常に
        # 出力するようになったため、version="1.0"(design_tokens非対応)
        # ではなく"1.5"以降を宣言するようになった(`compiler.py`参照)。
        self.assertEqual(reparsed["version"], "1.5")

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


class TestCompilerDesignTokensByDomain(unittest.TestCase):
    """FORGE-PRODUCT-VISION-002(2026-08-12、CEO「アプリストアレベルの
    品質にするにはどうすればいいか」対応)の回帰テスト。

    以前は`Compiler`(legacy Checklist/Form経路)がdesign_tokensを
    一切出力せず、Curated Domain Library(5 Domain)を除く全Domain
    (shopping・survey・travel等、実際に生成されるアプリの大半)が
    Flutter既定のMaterial配色のまま描画されていた
    (`forge_ai/core/ir/forge_language_compiler.py`側だけが
    design_tokensを持っていた)。`design_tokens_for_domain()`により、
    `Compiler`が扱う全Domainにもテーマ適用が広がったことを確認する。
    """

    def setUp(self) -> None:
        self.compiler = Compiler(MockProvider())
        self.plan = ApplicationPlan(
            title="テスト",
            screens=(ScreenPlan(name="main", purpose="test", key_elements=("item",)),),
            data_entities=("item",),
            primary_flow=(),
        )

    def test_every_domain_category_gets_non_empty_design_tokens(self) -> None:
        for category in DomainCategory:
            with self.subTest(category=category):
                ir = self.compiler.compile(self.plan, domain_category=category.value)
                self.assertTrue(ir.design_tokens, f"{category.value}のdesign_tokensが空です")
                self.assertIn("primary", ir.design_tokens["color_scheme"])

    def test_different_domains_can_receive_different_color_presets(self) -> None:
        """全Domainが同じ1色に固定されているわけではないことを確認する
        (少数のプリセットから選ばれる、`FORGE-PRODUCT-DESIGN-LAYER-
        PROPOSAL.md`3.4節の設計を`Compiler`経路にも適用したことの確認)。"""
        shopping = self.compiler.compile(self.plan, domain_category="shopping")
        survey = self.compiler.compile(self.plan, domain_category="survey")
        self.assertNotEqual(
            shopping.design_tokens["color_scheme"]["primary"],
            survey.design_tokens["color_scheme"]["primary"],
        )

    def test_unknown_domain_category_falls_back_to_calm_preset(self) -> None:
        ir = self.compiler.compile(self.plan, domain_category="no_such_domain")
        self.assertEqual(ir.design_tokens["color_scheme"]["primary"], "#5B7C99")

    def test_form_template_also_receives_domain_design_tokens(self) -> None:
        ir = self.compiler.compile(self.plan, domain_category="survey", template="form")
        self.assertTrue(ir.design_tokens)
        self.assertEqual(ir.design_tokens["color_scheme"]["primary"], "#5C6470")


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


class _StubProvider:
    """FORGE-AI-QUALITY-001テスト専用: `complete()`が常に固定の
    `structured`を返すだけの、`AIProvider` Protocolを満たすStub。"""

    def __init__(self, structured: dict) -> None:
        self._structured = structured

    def complete(self, prompt):
        from forge_ai.provider.provider_interface import ProviderResponse

        return ProviderResponse(text="stub", structured=self._structured)


class TestCompilerProviderExampleItems(unittest.TestCase):
    """FORGE-AI-QUALITY-001(2026-08-11)の回帰テスト: Providerが
    `example_items`を返した場合、静的な`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`
    テーブルより優先して使う(実際のGemini APIで複数ジャンルを試した際、
    静的テーブルしか使われず、依頼内容を反映しない画一的な出力になって
    いた不具合への対応)。"""

    def _compile_with(self, key_elements: tuple[str, ...], structured: dict):
        plan = ApplicationPlan(
            title="テストアプリ",
            screens=(ScreenPlan(name="main", purpose="test", key_elements=key_elements),),
            data_entities=key_elements,
            primary_flow=(),
        )
        provider = _StubProvider(structured)
        return Compiler(provider).compile(plan)

    def test_provider_example_items_take_priority_over_static_table(self) -> None:
        """"item"は静的テーブルで牛乳・卵・パンになるはずだが、Providerが
        依頼内容に即した`example_items`を返した場合はそちらを使う。"""
        ir = self._compile_with(
            ("item",),
            {"title": "満足度アンケート", "example_items": ["ピアノ教室の満足度", "先生の対応"]},
        )
        texts = [entry["text"] for entry in ir.screens[0].state["items"].value]
        self.assertEqual(texts, ["ピアノ教室の満足度", "先生の対応"])

    def test_empty_provider_example_items_falls_back_to_static_table(self) -> None:
        """Providerが`example_items`を返さない(空リスト)場合は、既存の
        静的テーブルへ安全にフォールバックする(既存動作を壊さない)。"""
        ir = self._compile_with(("item",), {"title": "買い物リスト", "example_items": []})
        texts = [entry["text"] for entry in ir.screens[0].state["items"].value]
        self.assertEqual(texts, ["牛乳", "卵", "パン"])

    def test_missing_example_items_key_falls_back_to_static_table(self) -> None:
        """`example_items`キー自体が無い場合(MockProvider・旧LLM応答)も、
        既存の静的テーブルへ安全にフォールバックする。"""
        ir = self._compile_with(("item",), {"title": "買い物リスト"})
        texts = [entry["text"] for entry in ir.screens[0].state["items"].value]
        self.assertEqual(texts, ["牛乳", "卵", "パン"])

    def test_non_string_or_malformed_example_items_are_ignored(self) -> None:
        """Providerが不正な形(文字列以外の要素・非リスト)を返しても、
        クラッシュせず静的テーブルへフォールバックする(実LLM応答の
        構造がGeminiのStructured Output契約に厳密に沿わない場合の
        安全策)。"""
        ir = self._compile_with(("item",), {"title": "買い物リスト", "example_items": [1, 2, None, "  "]})
        texts = [entry["text"] for entry in ir.screens[0].state["items"].value]
        self.assertEqual(texts, ["牛乳", "卵", "パン"])


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
        常にChecklist単一画面を返す(後方互換の一部としてパラメータ
        自体は残しているが、画面構成自体は無視される)。

        FORGE-PRODUCT-VISION-002(2026-08-12)対応:
        version(design_tokensの有無に伴い"1.0"→"1.5")は
        `domain_category`の値に応じて変わりうるようになったため
        (`design_tokens_for_domain()`参照)、ここでは固定していない。"""
        for domain_category in (None, "shopping", "fishing_log", "household_budget", "habit_tracking"):
            with self.subTest(domain_category=domain_category):
                ir = self.compiler.compile(self.plan, domain_category=domain_category)
                self.assertEqual(ir.version, "1.5")
                self.assertEqual(len(ir.screens), 1)
                widget_types = [c.type for c in ir.screens[0].body.children]
                self.assertNotIn("form", widget_types)
                self.assertIn("checklist", widget_types)

    def test_compile_without_domain_category_argument_still_works(self) -> None:
        """`domain_category`省略時(既存呼び出し元との後方互換)も
        正しく動作する(design_tokensは"calm"へフォールバックする)。"""
        ir = self.compiler.compile(self.plan)
        self.assertEqual(ir.version, "1.5")
        self.assertEqual(ir.design_tokens["color_scheme"]["primary"], "#5B7C99")


class TestCompilerFormTemplate(unittest.TestCase):
    """FORGE-AI-QUALITY-001(2026-08-11)新設: `template="form"`の
    回帰テスト。以前はTemplate Selectorが"form"を選んでも
    `Compiler.compile()`へ一切伝わらず、常にChecklist単一画面になって
    いた(実機Gemini確認で発見、`TECH_DEBT.md`参照)。"""

    def setUp(self) -> None:
        self.provider = MockProvider()

    def _compile_form(self, key_elements: tuple[str, ...]):
        plan = ApplicationPlan(
            title="満足度アンケート",
            screens=(ScreenPlan(name="main", purpose="test", key_elements=key_elements),),
            data_entities=key_elements,
            primary_flow=(),
        )
        return Compiler(self.provider).compile(plan, template="form")

    def test_default_template_is_unaffected(self) -> None:
        """`template`引数を省略した場合、既存の挙動(Checklist単一画面)
        自体は変わらないことの回帰テスト(versionはFORGE-PRODUCT-
        VISION-002対応でdesign_tokens常時出力に伴い"1.5"へ引き上げ済み、
        `test_compiler_always_produces_checklist_template_regardless_
        of_domain_category`と同じ理由)。"""
        plan = ApplicationPlan(
            title="x", screens=(ScreenPlan(name="main", purpose="x", key_elements=("item",)),),
            data_entities=("item",), primary_flow=(),
        )
        ir = Compiler(self.provider).compile(plan)
        self.assertEqual(ir.version, "1.5")
        self.assertEqual(len(ir.screens), 1)

    def test_form_template_produces_two_screens(self) -> None:
        """入力画面+送礼(thanks)画面の2画面構成になる
        (`form_template.py`・`templates.dart`のbuildFormTemplateと同形)。"""
        ir = self._compile_form(("question",))
        self.assertEqual(len(ir.screens), 2)
        self.assertEqual(ir.initial_screen_id, "generated_screen")
        self.assertEqual({s.id for s in ir.screens}, {"generated_screen", "thanks_screen"})

    def test_form_template_uses_form_and_heading_widgets(self) -> None:
        ir = self._compile_form(("question",))
        main_screen = next(s for s in ir.screens if s.id == "generated_screen")
        widget_types = {w.type for w in _flatten(main_screen.body)}
        self.assertIn("form", widget_types)
        self.assertIn("heading", widget_types)
        self.assertIn("card", widget_types)
        self.assertIn("text_field", widget_types)
        self.assertNotIn("checklist", widget_types)

    def test_form_template_creates_one_text_field_per_question(self) -> None:
        """Providerが返す(または静的テーブルの)複数の質問文それぞれに、
        対応するtext_fieldが1つずつ作られる。"""
        provider = _StubProvider({
            "title": "満足度アンケート",
            "example_items": ["サービス全体の満足度", "スタッフの対応"],
        })
        plan = ApplicationPlan(
            title="満足度アンケート",
            screens=(ScreenPlan(name="main", purpose="test", key_elements=("question",)),),
            data_entities=("question",), primary_flow=(),
        )
        ir = Compiler(provider).compile(plan, template="form")
        main_screen = next(s for s in ir.screens if s.id == "generated_screen")
        placeholders = [
            w.properties.get("placeholder") for w in _flatten(main_screen.body) if w.type == "text_field"
        ]
        self.assertEqual(placeholders, ["サービス全体の満足度", "スタッフの対応"])
        self.assertEqual(len(main_screen.state), 2)

    def test_form_template_version_is_1_5(self) -> None:
        """form/heading/card Widget(v1.1)+validationプロパティ(v1.2)を
        使うため、v1.2以降を宣言する必要がある(そうしないと実際の
        Validatorがform/heading/cardを未知Widgetとして拒否する、
        `test_form_template_validates_against_real_backend_validator`
        参照)。FORGE-PRODUCT-VISION-002(2026-08-12)対応でdesign_tokens
        を常に出力するようになったため、実際の宣言値は"1.2"ではなく
        design_tokens対応の下限である"1.5"になる。"""
        ir = self._compile_form(("question",))
        self.assertEqual(ir.version, "1.5")

    def test_form_template_submit_action_navigates_to_thanks_screen(self) -> None:
        ir = self._compile_form(("question",))
        main_screen = next(s for s in ir.screens if s.id == "generated_screen")
        form_widget = next(w for w in _flatten(main_screen.body) if w.type == "form")
        self.assertEqual(
            form_widget.properties.get("submit_action"),
            {"type": "navigate", "target_screen_id": "thanks_screen"},
        )

    def test_form_template_to_json_dict_is_json_serializable(self) -> None:
        import json

        ir = self._compile_form(("question",))
        serialized = json.dumps(ir.to_json_dict(), ensure_ascii=False)
        reparsed = json.loads(serialized)
        self.assertEqual(reparsed["version"], "1.5")

    @unittest.skipUnless(
        importlib.util.find_spec("app") is not None or os.path.isdir(
            os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app")
        ),
        "backend/app が無い環境では外部検証をスキップする(forge_ai/自体の必須依存ではない)",
    )
    def test_form_template_validates_against_real_backend_validator(self) -> None:
        """`TestCompiler.test_compiled_output_validates_against_real_
        backend_validator`と同じ理由(forge_ai/自体はbackend/への依存を
        持たないが、実際の本物のValidatorに通ることを一度だけ追加確認
        する)。特にversion="1.2"の設定漏れ(=form/heading/cardが未知
        Widgetとして拒否される)を検出する目的が大きい。"""
        backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        try:
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return

        ir = self._compile_form(("question", "answer"))
        result = validate_forge_document(ir.to_json_dict())
        self.assertTrue(result.valid, msg=result.to_dict())


if __name__ == "__main__":
    unittest.main()


class TestClampTitle(unittest.TestCase):
    """FORGE-CONVERSATION-READY-001(2026-08-12)で発見した実バグの
    回帰テスト。

    `/converse`導入後、Cognitive Pipelineへ渡るのはユーザーの短い一言
    ではなく「会話全体を要約した自己完結型のbuild_brief」になったため、
    80文字を超えるタイトルが現実に生成されるようになった。Validatorは
    これを`string_length`のblockingエラーとするが、**Repairでは直らない**
    ため、利用者には「Repair(2回)後もValidatorに合格しませんでした」と
    しか見えていなかった(実機Geminiで再現・確認した)。
    """

    def test_a_long_brief_style_title_is_clamped_to_the_first_sentence(self) -> None:
        long_title = (
            "ユーザーが自分専用で読んだ本の感想を記録・管理するための読書ノートアプリ。"
            "入力および管理機能として、本のタイトル、著者名、読了日、5段階の星評価、"
            "感想テキストフィールドを備え、記録した本の一覧表示・詳細閲覧ができる構造とする。"
        )
        self.assertGreater(len(long_title), MAX_TITLE_LENGTH)
        clamped = clamp_title(long_title)
        self.assertEqual(clamped, "ユーザーが自分専用で読んだ本の感想を記録・管理するための読書ノートアプリ")
        self.assertLessEqual(len(clamped), MAX_TITLE_LENGTH)

    def test_a_long_title_without_any_sentence_break_is_hard_truncated(self) -> None:
        clamped = clamp_title("あ" * 200)
        self.assertLessEqual(len(clamped), MAX_TITLE_LENGTH)
        self.assertTrue(clamped.endswith("…"))

    def test_a_long_first_sentence_is_still_clamped(self) -> None:
        """最初の句点までが既に長すぎる場合も、必ず上限内へ収める。"""
        clamped = clamp_title("あ" * 200 + "。短い続き")
        self.assertLessEqual(len(clamped), MAX_TITLE_LENGTH)

    def test_short_titles_are_left_untouched(self) -> None:
        self.assertEqual(clamp_title("買い物リスト"), "買い物リスト")

    def test_empty_and_none_titles_fall_back_instead_of_producing_an_invalid_document(self) -> None:
        """Validatorは1文字以上を要求するため、空文字は許されない。"""
        for raw in ("", "   ", None):
            with self.subTest(raw=raw):
                self.assertTrue(clamp_title(raw))

    def test_compiler_output_title_always_satisfies_the_validator_limit(self) -> None:
        long_plan = ApplicationPlan(
            title="あ" * 300,
            screens=(ScreenPlan(name="main", purpose="x", key_elements=("item",)),),
            data_entities=("item",), primary_flow=(),
        )
        ir = Compiler(MockProvider()).compile(long_plan)
        self.assertLessEqual(len(ir.app_title or ""), MAX_TITLE_LENGTH)
        for screen in ir.screens:
            self.assertLessEqual(len(screen.title), MAX_TITLE_LENGTH)
