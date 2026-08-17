"""Design Language V1
(FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、2026-08-17)。

---

## 何を守るテストか

Product Direction §3 の分担:

    AIは意味を決める      style_role: "metric.primary"
    Forgeは品質を保証する  それが何px・何色になるか

このファイルが見るのは**backend側の担保**である。

1. 語彙が識別子であって自然言語ではないこと(§6)
2. Validatorが語彙外を通さないこと
3. Compilerが実際にroleを出すこと
4. **最終Documentの事実から**Evidenceへ残ること(§11)
5. `generation_ref`がProduction Pathへ流れること(§3)

Runtimeの見た目(`frontend/lib/json_ui/renderer/design_language.dart`)は
Flutter側のテストが担当する。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.runtime.design_language import (  # noqa: E402
    SEMANTIC_ROLES,
    InvalidSemanticIdentifier,
    design_roles_in,
    is_known_role,
    knowledge_entries,
    role_definition,
    validate_identifier,
)
from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


def _document(*, version: str = "1.10", style_role: object = None) -> dict:
    widget: dict = {"type": "text", "id": "hero", "value": "残高"}
    if style_role is not None:
        widget["style_role"] = style_role
    return {
        "version": version,
        "initial_screen_id": "main",
        "app": {"title": "テスト"},
        "screens": [{
            "id": "main", "title": "画面", "state": {},
            "body": {"type": "column", "id": "root", "children": [widget]},
        }],
    }


class TestTheVocabularyIsAnIdentifierNotProse(unittest.TestCase):
    """**利用者の発話がEvidenceへ混入する経路を塞ぐ**(006 §22 / 014 §6)。

    `design_language_roles`は自由文字列のtupleなので、型だけでは
    「発話全文を入れる」を防げなかった。
    """

    def test_valid_identifiers_pass(self) -> None:
        for raw in ("metric.primary", "finance.income", "surface.elevated",
                    "text.secondary", "shape.pill", "button.primary"):
            with self.subTest(raw=raw):
                self.assertEqual(validate_identifier(raw), raw)

    def test_a_sentence_is_rejected(self) -> None:
        """**これが目的である。** 綺麗さのためではない。"""
        for raw in ("残高を一番目立たせてほしい",
                    "make the balance stand out",
                    "metric primary",
                    "metric.primary という役割"):
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidSemanticIdentifier):
                    validate_identifier(raw)

    def test_uppercase_is_rejected(self) -> None:
        """`metric.primary`と`Metric.Primary`が両方記録されると、
        Evidenceの集計が割れる。**同じものは同じ文字列**にする。"""
        with self.assertRaises(InvalidSemanticIdentifier):
            validate_identifier("Metric.Primary")

    def test_whitespace_and_empty_are_rejected(self) -> None:
        for raw in ("", "  ", "metric. primary", "\nmetric.primary"):
            with self.subTest(raw=repr(raw)):
                with self.assertRaises(InvalidSemanticIdentifier):
                    validate_identifier(raw)

    def test_a_non_string_is_rejected(self) -> None:
        for raw in (None, 42, ["metric.primary"], {"id": "metric.primary"}):
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidSemanticIdentifier):
                    validate_identifier(raw)

    def test_the_error_does_not_dump_the_whole_input(self) -> None:
        """誤って発話が渡ったとき、それを丸ごとログへ流さない。"""
        long_text = "あ" * 500
        with self.assertRaises(InvalidSemanticIdentifier) as raised:
            validate_identifier(long_text)
        self.assertLess(len(str(raised.exception)), 120)

    def test_every_role_id_is_a_valid_identifier(self) -> None:
        """語彙側が自分の規則を破っていないこと。"""
        for role in SEMANTIC_ROLES:
            with self.subTest(role=role.id):
                self.assertEqual(validate_identifier(role.id), role.id)


class TestTheVocabularyIsUsableByLocalAI(unittest.TestCase):
    """§12。Design Languageは「見た目の設定」ではなく、
    **Local AIが将来選ぶ出力言語の一部**である。"""

    def test_every_role_explains_when_to_use_and_when_not_to(self) -> None:
        """`use_when`だけでは足りない。**誤用を止める情報**が要る
        ——`metric.primary`を全数値へ付けると階層が消える。"""
        for role in SEMANTIC_ROLES:
            with self.subTest(role=role.id):
                self.assertTrue(role.meaning.strip(), "意味が書かれていない。")
                self.assertTrue(role.use_when.strip(), "使う条件が書かれていない。")

    def test_the_most_misusable_roles_say_what_to_avoid(self) -> None:
        for role_id in ("metric.primary", "surface.elevated", "button.primary",
                        "finance.income", "state.danger"):
            with self.subTest(role=role_id):
                definition = role_definition(role_id)
                self.assertIsNotNone(definition)
                self.assertTrue(
                    definition.avoid_when.strip(),
                    "誤用しやすいroleに、避ける条件が書かれていない。",
                )

    def test_the_vocabulary_can_be_handed_to_retrieval(self) -> None:
        """RAG本体はまだ無いが、**渡せる形**にしておく。
        後から作ると、語彙と説明が別々に育ってずれる。"""
        entries = knowledge_entries()
        self.assertEqual(len(entries), len(SEMANTIC_ROLES))
        self.assertEqual(
            set(entries[0]), {"id", "category", "meaning", "use_when", "avoid_when"}
        )

    def test_the_vocabulary_stays_small(self) -> None:
        """**語彙を無制限に増やさない**(§7.1)。

        増えるほどAIが選び間違える余地とRuntimeが保証すべき組み合わせが
        増える。この上限は「これ以上増やすなら理由を書け」という意味で
        あって、技術的制約ではない。
        """
        self.assertLessEqual(
            len(SEMANTIC_ROLES), 45,
            "語彙が増えすぎている。既存の組み合わせで表現できないか、"
            "Golden App以外へ一般化するかを先に確かめること。",
        )

    def test_role_ids_are_unique(self) -> None:
        ids = [r.id for r in SEMANTIC_ROLES]
        self.assertEqual(len(ids), len(set(ids)))


class TestTheValidatorGuardsTheVocabulary(unittest.TestCase):
    def test_a_known_role_passes(self) -> None:
        self.assertTrue(validate_forge_document(_document(style_role="metric.primary")).valid)

    def test_an_unknown_role_is_rejected(self) -> None:
        """**未知のroleを通さない。** 自由に増やせると、Runtimeが保証
        できない値が入り、「AIは意味を選ぶ/Forgeが品質を保証する」と
        いう分担が崩れる。"""
        result = validate_forge_document(_document(style_role="でっちあげ.role"))
        self.assertFalse(result.valid)
        self.assertIn("unknown_style_role", [e.to_dict()["rule"] for e in result.errors])

    def test_a_sentence_as_a_role_is_rejected(self) -> None:
        result = validate_forge_document(_document(style_role="残高を目立たせてほしい"))
        self.assertFalse(result.valid)

    def test_style_role_needs_version_1_10(self) -> None:
        result = validate_forge_document(_document(version="1.9", style_role="metric.primary"))
        self.assertFalse(result.valid)
        self.assertIn(
            "field_not_allowed_in_version", [e.to_dict()["rule"] for e in result.errors]
        )

    def test_a_document_without_any_role_is_still_valid(self) -> None:
        """`style_role`は任意。既存文書を壊さない。"""
        self.assertTrue(validate_forge_document(_document()).valid)

    def test_the_check_is_not_per_widget_type(self) -> None:
        """**1箇所で見ていること。**

        type別の`allowed_keys`へ個別に足す形だと、Widgetを1つ追加した
        ときに`style_role`を足し忘れる。実際に複数のtypeで通ることを
        確かめて、共通経路であることを固定する。
        """
        for widget in (
            {"type": "text", "id": "w", "value": "x", "style_role": "text.title"},
            {"type": "button", "id": "w", "label": "追加",
             "action": {"type": "add_item", "target_state_ref": "s", "source_state_ref": "n"},
             "style_role": "button.primary"},
            {"type": "card", "id": "w", "children": [], "style_role": "card.metric"},
        ):
            with self.subTest(widget=widget["type"]):
                doc = _document()
                doc["screens"][0]["body"]["children"] = [widget]
                doc["screens"][0]["state"] = {
                    "s": {"type": "string_list", "value": []},
                    "n": {"type": "string", "value": ""},
                }
                result = validate_forge_document(doc)
                self.assertNotIn(
                    "additional_properties",
                    [e.to_dict()["rule"] for e in result.errors],
                    f"{widget['type']}でstyle_roleが許可されていない。",
                )


class TestEvidenceExtractionUsesTheDocumentNotTheClaim(unittest.TestCase):
    """§11。**AIの自己申告から取らない。最終Documentの事実から取る。**"""

    def test_roles_are_collected_from_the_document(self) -> None:
        doc = _document()
        doc["screens"][0]["body"]["children"] = [
            {"type": "text", "id": "a", "value": "x", "style_role": "metric.primary"},
            {"type": "text", "id": "b", "value": "y", "style_role": "finance.income"},
        ]
        self.assertEqual(design_roles_in(doc), ("finance.income", "metric.primary"))

    def test_duplicates_are_collapsed(self) -> None:
        doc = {"children": [{"style_role": "metric.primary"}] * 10}
        self.assertEqual(design_roles_in(doc), ("metric.primary",))

    def test_the_result_is_deterministic(self) -> None:
        """同じDocumentからは必ず同じ結果。集計が実行ごとにぶれない。"""
        doc = {"a": {"style_role": "text.title"}, "b": {"style_role": "card.list"}}
        self.assertEqual(design_roles_in(doc), design_roles_in(doc))
        self.assertEqual(design_roles_in(doc), ("card.list", "text.title"))

    def test_unknown_values_never_reach_the_evidence(self) -> None:
        """語彙に無い文字列は捨てる。**自由文がEvidenceへ入る経路を
        残さない**(006 §22)。"""
        doc = {"children": [
            {"style_role": "利用者がここに何か書いた"},
            {"style_role": "metric.primary"},
        ]}
        self.assertEqual(design_roles_in(doc), ("metric.primary",))

    def test_prose_that_merely_mentions_a_role_is_not_collected(self) -> None:
        """**キー名だけを見る。** 本文にたまたま`metric.primary`という
        文字列が入っていたものを拾わない。"""
        doc = {"children": [{"type": "text", "value": "metric.primary と書いてある本文"}]}
        self.assertEqual(design_roles_in(doc), ())

    def test_an_empty_document_yields_nothing(self) -> None:
        for doc in ({}, [], None, "文字列", 42):
            with self.subTest(doc=doc):
                self.assertEqual(design_roles_in(doc), ())


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestTheProductionPathCarriesRolesAndRefs(unittest.TestCase):
    """**Compilerが出し、Validatorが通し、Evidenceに残る**まで、
    HTTP APIを叩くだけで確かめる。"""

    def setUp(self) -> None:
        from app.ai.gateway.generation_evidence import default_generation_store  # noqa: PLC0415

        self.client = TestClient(app)
        self.store = default_generation_store()
        self.store.reset()

    def _generate(self, text: str):
        return self.client.post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": text,
                            "generation_options": {"provider": "mock"}}},
        )

    def test_the_compiler_emits_semantic_roles(self) -> None:
        response = self._generate("家計の支出をカテゴリ別に管理したい")
        self.assertEqual(response.status_code, 200, response.text)
        document = response.json()["result"]["forge_document"]
        roles = design_roles_in(document)
        self.assertTrue(
            roles,
            "Compilerがstyle_roleを1つも出していない。Design Languageが"
            "Schemaにあるだけで、生成物へ届いていない。",
        )
        self.assertIn("text.headline", roles)

    def test_the_document_declares_version_1_10(self) -> None:
        document = self._generate("家計の支出をカテゴリ別に管理したい").json()["result"]["forge_document"]
        self.assertEqual(document["version"], "1.10")

    def test_every_emitted_role_is_in_the_vocabulary(self) -> None:
        """Compiler側の綴りとbackend語彙がずれていないこと。

        ずれてもValidatorが`unknown_style_role`で落とすので黙って
        壊れることは無いが、**落ちる前にここで気付く**方がよい。
        """
        document = self._generate("盆栽の水やりの記録をつけたい").json()["result"]["forge_document"]
        for role in design_roles_in(document):
            with self.subTest(role=role):
                self.assertTrue(is_known_role(role))

    def test_the_roles_reach_the_generation_evidence(self) -> None:
        """**§11の本体。** ここが繋がっていないと、Design Languageは
        Local AIの学習素材にならない。"""
        self._generate("家計の支出をカテゴリ別に管理したい")
        records = self.store.all_records()
        self.assertTrue(records)
        self.assertTrue(
            records[0].design_language_roles,
            "生成物のEvidenceにDesign Roleが残っていない。"
            "『どのNeedにどの意味を選んだら受け入れられたか』を"
            "後から学べない。",
        )

    def test_the_generation_ref_reaches_the_pipeline_result(self) -> None:
        """**§3の本体。**

        Storeに記録されただけでは、後からRuntime結果や利用者の承認を
        書けない——「どの生成物へ書くか」を本番が知らないためである。
        R0以前にExperienceで踏んだのと同じ形。
        """
        from app.ai.runtime.prompt_pipeline import PromptPipeline  # noqa: PLC0415

        result = PromptPipeline().run(
            "家計の支出をカテゴリ別に管理したい", engine="forge_ai", provider="mock"
        )
        self.assertIsNotNone(
            result.generation_ref,
            "PipelineRunResultにgeneration_refが載っていない。"
            "記録はされるが、後から評価を書き足す先が分からない。",
        )
        stored = {r.ref for r in self.store.all_records()}
        self.assertIn(
            result.generation_ref, stored,
            "返ってきたrefがStoreの記録と一致しない。",
        )

    def test_the_ref_can_actually_be_used_to_write_feedback_later(self) -> None:
        """**refが「使える」ことまで見る。** 番号が返るだけでは足りない。

        Runtime結果と利用者の承認は、まだ本番から書かれない(UIが無い)。
        書ける**構造**があることを、ここで固定しておく(§4)。
        """
        from app.ai.gateway.generation_evidence import RuntimeOutcome  # noqa: PLC0415
        from app.ai.gateway.learning_foundation import AcceptanceSignal  # noqa: PLC0415
        from app.ai.runtime.prompt_pipeline import PromptPipeline  # noqa: PLC0415

        result = PromptPipeline().run(
            "家計の支出をカテゴリ別に管理したい", engine="forge_ai", provider="mock"
        )
        ref = result.generation_ref
        self.assertEqual(self.store.note_runtime_outcome([ref], RuntimeOutcome.RENDERED), 1)
        self.assertEqual(self.store.note_user_acceptance([ref], AcceptanceSignal.ACCEPTED), 1)
        updated = {r.ref: r for r in self.store.all_records()}[ref]
        self.assertIs(updated.runtime_outcome, RuntimeOutcome.RENDERED)
        self.assertIs(updated.user_acceptance, AcceptanceSignal.ACCEPTED)
        self.assertTrue(
            updated.is_positive_example,
            "Validator合格 + Runtime描画 + 明示承認が揃っても教師候補に"
            "ならない。",
        )


if __name__ == "__main__":
    unittest.main()
