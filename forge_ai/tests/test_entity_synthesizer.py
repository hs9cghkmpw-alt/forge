"""entity_synthesizer.py のテスト(FORGE-PRODUCT-VISION-002、2026-08-12)。

CEO「つくれるアプリの自由度をあげたい。トップレベルまで」対応。

このモジュールの要点は「**AIの出力を決して信用しない**」ことにあるため、
テストの大半は、意図的に壊れた/悪意のある/型の違う応答を投げて、
決定的なサニタイズが期待どおり働くことの確認に充てている。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from typing import Any

from forge_ai.core.ir.entity_synthesizer import EntitySynthesizer
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler
from forge_ai.core.ir.ir_generator import IRGenerator
from forge_ai.core.ir.ir_types import FieldType
from forge_ai.core.planner import ApplicationPlan, ScreenPlan
from forge_ai.prompt.prompt_builder import Prompt
from forge_ai.provider.provider_interface import ProviderResponse


class _StubProvider:
    """指定した`structured`をそのまま返す`AIProvider`実装。"""

    def __init__(self, structured: dict[str, Any]) -> None:
        self._structured = structured
        self.last_prompt: Prompt | None = None

    def complete(self, prompt: Prompt) -> ProviderResponse:
        self.last_prompt = prompt
        return ProviderResponse(text="stub", structured=self._structured)


class _RaisingProvider:
    def complete(self, prompt: Prompt) -> ProviderResponse:
        raise RuntimeError("provider is down")


_PLAN = ApplicationPlan(
    title="通院記録",
    screens=(ScreenPlan(name="main", purpose="記録する", key_elements=("visit",)),),
    data_entities=("visit",),
    primary_flow=(),
)


def _synthesize(structured: dict[str, Any]):
    return EntitySynthesizer(_StubProvider(structured)).synthesize(
        _PLAN, user_text="通院の記録をつけたい", domain_name="hospital"
    )


_WELL_FORMED: dict[str, Any] = {
    "entity_name": "visit_record",
    "entity_label": "受診記録",
    "visual_style": "calm",
    "fields": [
        {"name": "hospital_name", "label": "病院名", "type": "string", "required": True},
        {"name": "visit_date", "label": "受診日", "type": "date", "required": False},
        {"name": "cost", "label": "費用", "type": "number", "required": False},
        {
            "name": "department", "label": "診療科", "type": "choice", "required": False,
            "choices": ["内科", "外科", "皮膚科"],
        },
    ],
}


class TestEntitySynthesizerHappyPath(unittest.TestCase):
    def test_well_formed_response_becomes_entity_spec(self) -> None:
        spec = _synthesize(_WELL_FORMED)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.name, "visit_record")
        self.assertEqual(spec.label, "受診記録")
        self.assertEqual(spec.visual_style, "calm")
        self.assertEqual([f.name for f in spec.field_specs],
                         ["hospital_name", "visit_date", "cost", "department"])

    def test_field_types_are_mapped_to_the_ir_enum(self) -> None:
        spec = _synthesize(_WELL_FORMED)
        assert spec is not None
        types = {f.name: f.field_type for f in spec.field_specs}
        self.assertEqual(types["hospital_name"], FieldType.STRING)
        self.assertEqual(types["visit_date"], FieldType.DATE)
        self.assertEqual(types["cost"], FieldType.NUMBER)
        self.assertEqual(types["department"], FieldType.CHOICE)

    def test_choice_options_are_preserved(self) -> None:
        spec = _synthesize(_WELL_FORMED)
        assert spec is not None
        department = next(f for f in spec.field_specs if f.name == "department")
        self.assertEqual(department.choices, ("内科", "外科", "皮膚科"))

    def test_prompt_carries_the_user_text_and_uses_the_dedicated_stage(self) -> None:
        """`entity_synthesis` stageで呼ぶこと自体が重要である
        (`forge_ai_provider_bridge.py`がstage名でresponse schemaを
        引くため、stage名を間違えると未知stage用の
        `{"type": "object"}`へ落ち、Geminiが空dictを返す。TD40参照)。"""
        provider = _StubProvider(_WELL_FORMED)
        EntitySynthesizer(provider).synthesize(
            _PLAN, user_text="通院の記録をつけたい", domain_name="hospital"
        )
        assert provider.last_prompt is not None
        self.assertEqual(provider.last_prompt.stage, "entity_synthesis")
        self.assertEqual(provider.last_prompt.context["user_text"], "通院の記録をつけたい")


class TestEntitySynthesizerRejectsUnusableResponses(unittest.TestCase):
    """`None`を返す(=呼び出し側が従来のChecklistへ安全に落ちる)ケース。"""

    def test_empty_dict_returns_none(self) -> None:
        """TD40で実機確認した「Geminiがスキーマを解釈できないと空dictを
        返す」ケース。ここが実質的な防波堤であるため明示的に確認する。"""
        self.assertIsNone(_synthesize({}))

    def test_non_dict_returns_none(self) -> None:
        self.assertIsNone(_synthesize(None))  # type: ignore[arg-type]
        self.assertIsNone(_synthesize([1, 2, 3]))  # type: ignore[arg-type]

    def test_missing_entity_name_returns_none(self) -> None:
        self.assertIsNone(_synthesize({"entity_label": "x", "fields": [
            {"name": "a", "label": "a", "type": "string"}]}))

    def test_entity_name_with_no_usable_ascii_returns_none(self) -> None:
        """全て日本語のentity_nameは、identifierへ機械的に直せないため諦める。"""
        self.assertIsNone(_synthesize({**_WELL_FORMED, "entity_name": "受診記録"}))

    def test_empty_fields_returns_none(self) -> None:
        self.assertIsNone(_synthesize({**_WELL_FORMED, "fields": []}))

    def test_fields_not_a_list_returns_none(self) -> None:
        self.assertIsNone(_synthesize({**_WELL_FORMED, "fields": "hospital_name"}))

    def test_all_fields_unusable_returns_none(self) -> None:
        self.assertIsNone(_synthesize({**_WELL_FORMED, "fields": [
            {"name": "受診日", "label": "受診日", "type": "date"},  # identifier化できない
            "not a dict",
        ]}))

    def test_provider_errors_are_not_swallowed(self) -> None:
        """Provider障害を「合成できなかった」へ握り潰さない
        (`pipeline_orchestrator.py`の既存方針と揃える)。"""
        with self.assertRaises(RuntimeError):
            EntitySynthesizer(_RaisingProvider()).synthesize(
                _PLAN, user_text="x", domain_name="hospital"
            )


class TestEntitySynthesizerSanitization(unittest.TestCase):
    """壊れた応答を「捨てる」のではなく「安全な形へ直す」ケース。"""

    def test_camel_case_and_spaces_are_normalized_to_snake_case(self) -> None:
        spec = _synthesize({**_WELL_FORMED, "entity_name": "Visit Record"})
        assert spec is not None
        self.assertEqual(spec.name, "visit_record")

    def test_unknown_field_type_falls_back_to_string_instead_of_dropping_the_field(self) -> None:
        """型名を間違えただけで項目ごと失うのは損なので、STRINGへ倒す。"""
        spec = _synthesize({**_WELL_FORMED, "fields": [
            {"name": "note", "label": "メモ", "type": "text", "required": True},
        ]})
        assert spec is not None
        self.assertEqual(len(spec.field_specs), 1)
        self.assertEqual(spec.field_specs[0].field_type, FieldType.STRING)

    def test_choice_without_enough_options_is_demoted_to_string(self) -> None:
        """「根拠のない選択肢を発明しない」既存方針を合成経路でも守る。"""
        spec = _synthesize({**_WELL_FORMED, "fields": [
            {"name": "status", "label": "状態", "type": "choice", "choices": ["のみ"], "required": True},
        ]})
        assert spec is not None
        self.assertEqual(spec.field_specs[0].field_type, FieldType.STRING)
        self.assertEqual(spec.field_specs[0].choices, ())

    def test_duplicate_field_names_are_dropped(self) -> None:
        spec = _synthesize({**_WELL_FORMED, "fields": [
            {"name": "cost", "label": "費用", "type": "number", "required": True},
            {"name": "cost", "label": "費用(再)", "type": "string", "required": True},
        ]})
        assert spec is not None
        self.assertEqual([f.name for f in spec.field_specs], ["cost"])

    def test_reserved_field_names_are_dropped(self) -> None:
        """`records`/`selected`は`ForgeLanguageCompiler`が固定で使う
        State IDであり、衝突すると生成アプリのStateが静かに壊れる。"""
        spec = _synthesize({**_WELL_FORMED, "fields": [
            {"name": "records", "label": "記録", "type": "string", "required": True},
            {"name": "memo", "label": "メモ", "type": "string", "required": True},
        ]})
        assert spec is not None
        self.assertEqual([f.name for f in spec.field_specs], ["memo"])

    def test_field_count_is_capped(self) -> None:
        spec = _synthesize({**_WELL_FORMED, "fields": [
            {"name": f"f{i}", "label": f"項目{i}", "type": "string", "required": True}
            for i in range(30)
        ]})
        assert spec is not None
        self.assertLessEqual(len(spec.field_specs), 8)

    def test_at_least_one_field_is_forced_required(self) -> None:
        """1つもrequiredが無いと、空レコードを無限に追加できてしまう。"""
        spec = _synthesize({**_WELL_FORMED, "fields": [
            {"name": "a", "label": "A", "type": "string", "required": False},
            {"name": "b", "label": "B", "type": "string", "required": False},
        ]})
        assert spec is not None
        self.assertTrue(spec.field_specs[0].required)

    def test_invalid_visual_style_falls_back_to_calm(self) -> None:
        spec = _synthesize({**_WELL_FORMED, "visual_style": "cyberpunk"})
        assert spec is not None
        self.assertEqual(spec.visual_style, "calm")

    def test_missing_label_falls_back_to_the_field_name(self) -> None:
        spec = _synthesize({**_WELL_FORMED, "fields": [
            {"name": "memo", "label": "   ", "type": "string", "required": True},
        ]})
        assert spec is not None
        self.assertEqual(spec.field_specs[0].label, "memo")


class TestEntitySynthesizerNumericBounds(unittest.TestCase):
    """min/max(両方揃った場合のみ`slider`Widgetになる)の扱い。"""

    def _bounds(self, field: dict[str, Any]):
        spec = _synthesize({**_WELL_FORMED, "fields": [field]})
        assert spec is not None
        return spec.field_specs[0].min_value, spec.field_specs[0].max_value

    def test_valid_bounds_on_a_number_field_are_kept(self) -> None:
        self.assertEqual(
            self._bounds({"name": "rating", "label": "満足度", "type": "number",
                          "required": True, "min_value": 1, "max_value": 5}),
            (1.0, 5.0),
        )

    def test_bounds_on_a_non_number_field_are_dropped(self) -> None:
        self.assertEqual(
            self._bounds({"name": "memo", "label": "メモ", "type": "string",
                          "required": True, "min_value": 1, "max_value": 5}),
            (None, None),
        )

    def test_only_one_bound_is_dropped(self) -> None:
        """片方だけでは`slider`にできず、根拠のない上限も発明しない。"""
        self.assertEqual(
            self._bounds({"name": "amount", "label": "金額", "type": "number",
                          "required": True, "min_value": 0}),
            (None, None),
        )

    def test_reversed_bounds_are_dropped(self) -> None:
        self.assertEqual(
            self._bounds({"name": "rating", "label": "評価", "type": "number",
                          "required": True, "min_value": 5, "max_value": 1}),
            (None, None),
        )

    def test_boolean_bounds_are_not_treated_as_numbers(self) -> None:
        """Pythonでは`isinstance(True, int)`がTrueになるため、True/Falseが
        0/1の範囲として採用されないことを明示的に確認する。"""
        self.assertEqual(
            self._bounds({"name": "rating", "label": "評価", "type": "number",
                          "required": True, "min_value": False, "max_value": True}),
            (None, None),
        )


class TestSynthesizedSpecProducesRealApp(unittest.TestCase):
    """合成された`EntitySpec`が、手書きCurated Domainと**同じ経路**を
    通って、実際に使えるForge Language文書になることの確認
    (このモジュールの存在意義そのもの)。"""

    def _compile(self):
        spec = _synthesize(_WELL_FORMED)
        assert spec is not None
        ir = IRGenerator().build_from_spec(spec)
        return ForgeLanguageCompiler().compile(ir, domain_category="hospital", title="通院記録")

    def test_synthesized_spec_compiles_to_a_typed_record_app(self) -> None:
        doc = self._compile().to_json_dict()
        self.assertIn("record_schemas", doc)
        self.assertIn("visit_record", doc["record_schemas"])
        self.assertEqual(
            [f["name"] for f in doc["record_schemas"]["visit_record"]["fields"]],
            ["hospital_name", "visit_date", "cost", "department"],
        )

    def test_synthesized_app_uses_the_full_widget_vocabulary(self) -> None:
        """Checklist(text_field+checklistだけ)ではなく、型に応じた
        Widget(date_field・choice_field)とタブ構成が出ることを確認する。"""
        doc = self._compile().to_json_dict()

        def widget_types(node: dict[str, Any], acc: set[str]) -> set[str]:
            acc.add(node["type"])
            for child in node.get("children", []):
                widget_types(child, acc)
            return acc

        found: set[str] = set()
        for screen in doc["screens"]:
            widget_types(screen["body"], found)
        self.assertIn("tab_view", found)
        self.assertIn("record_list_view", found)
        self.assertIn("date_field", found)
        self.assertIn("choice_field", found)
        self.assertNotIn("checklist", found)

    def test_synthesized_app_gets_design_tokens(self) -> None:
        doc = self._compile().to_json_dict()
        self.assertIn("design_tokens", doc)
        self.assertIn("primary", doc["design_tokens"]["color_scheme"])

    @unittest.skipUnless(
        importlib.util.find_spec("app") is not None or os.path.isdir(
            os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app")
        ),
        "backend/app が無い環境では外部検証をスキップする(forge_ai/自体の必須依存ではない)",
    )
    def test_synthesized_app_passes_the_real_backend_validator(self) -> None:
        """`test_compiler.py`の同種テストと同じ理由。AIが合成した定義
        由来の文書が、本物のValidatorを通ることを確認する(サニタイズが
        不十分だと、ここでidentifierパターン違反等が露見する)。"""
        backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        try:
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return
        result = validate_forge_document(self._compile().to_json_dict())
        self.assertTrue(result.valid, msg=result.to_dict())

    @unittest.skipUnless(
        importlib.util.find_spec("app") is not None or os.path.isdir(
            os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app")
        ),
        "backend/app が無い環境では外部検証をスキップする",
    )
    def test_hostile_field_names_still_produce_a_valid_document(self) -> None:
        """サニタイズを通り抜けた値がValidatorを壊さないことの確認
        (記号・空白・極端に長い名前・重複を同時に投げる)。"""
        backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        try:
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return

        spec = _synthesize({
            "entity_name": "  My-Record!!  ",
            "entity_label": "  ",
            "visual_style": 123,
            "fields": [
                {"name": "Field One", "label": "項目1", "type": "string", "required": True},
                {"name": "field_one", "label": "重複", "type": "string", "required": True},
                {"name": "x" * 200, "label": "長い", "type": "number", "required": False},
                {"name": "状態", "label": "状態", "type": "choice", "choices": ["a", "b"]},
            ],
        })
        self.assertIsNotNone(spec)
        assert spec is not None
        ir = IRGenerator().build_from_spec(spec)
        doc = ForgeLanguageCompiler().compile(ir, domain_category="generic", title="x").to_json_dict()
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class _SynthesisSabotagingProvider:
    """entity_synthesis stageだけ壊れた応答を返し、他のstageは
    `MockProvider`へそのまま委譲するProvider。"""

    def __init__(self, broken_structured: dict[str, Any]) -> None:
        from forge_ai.provider.mock_provider import MockProvider

        self._inner = MockProvider()
        self._broken = broken_structured

    def complete(self, prompt: Prompt) -> ProviderResponse:
        if prompt.stage == "entity_synthesis":
            return ProviderResponse(text="broken", structured=self._broken)
        return self._inner.complete(prompt)


class TestOrchestratorFailsClosedOnSynthesisFailure(unittest.TestCase):
    """合成失敗をChecklist成功へ偽装しないことの確認。

    未解決のRecord/構造要求はexact Capability Gapとして保持する。
    legacy Checklistへの意味変更は安全策ではなく誤成功なので禁止する。
    """

    def _widget_types(self, doc: dict[str, Any]) -> set[str]:
        found: set[str] = set()

        def walk(node: dict[str, Any]) -> None:
            found.add(node["type"])
            for child in node.get("children", []):
                walk(child)

        for screen in doc["screens"]:
            walk(screen["body"])
        return found

    def test_broken_synthesis_fails_closed_instead_of_substituting_checklist(self) -> None:
        from forge_ai.core.pipeline import run_cognitive_pipeline
        from forge_ai.core.orchestration.outcomes import CognitivePipelineFailed

        outcome = run_cognitive_pipeline(
            "買い物リストを作りたい", provider=_SynthesisSabotagingProvider({})
        )
        self.assertIsInstance(outcome, CognitivePipelineFailed)
        self.assertEqual(outcome.reached_stage, "capability_gap")
        self.assertIn("semantic_structure_unresolved", str(outcome.error))
        # 失敗をChecklist文書へ変換して成功扱いしていない。
        self.assertFalse(hasattr(outcome, "ir"))

    def test_successful_synthesis_records_its_source_in_the_decision_trace(self) -> None:
        """成否がDecision Traceから追えること(運用時にどちらの経路を
        通ったか分からないと、品質問題の切り分けができないため)。"""
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        entity_source = [d for d in outcome.context.decision_trace if d.stage == "entity_source"]
        self.assertEqual(len(entity_source), 1)
        self.assertTrue(entity_source[0].decision.startswith("synthesized("))
        self.assertIn("record_list_view", self._widget_types(outcome.ir.to_json_dict()))

    def test_curated_domains_still_report_curated_not_synthesized(self) -> None:
        """Curated Domain Library(手書き定義)は合成に置き換わらない
        ——既存の作り込みを壊していないことの回帰テスト。"""
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline("家計簿をつけたい")
        entity_source = [d for d in outcome.context.decision_trace if d.stage == "entity_source"]
        self.assertEqual(len(entity_source), 1)
        self.assertTrue(entity_source[0].decision.startswith("curated("))


if __name__ == "__main__":
    unittest.main()
