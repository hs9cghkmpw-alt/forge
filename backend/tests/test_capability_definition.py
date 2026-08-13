"""Declarative Self-Extension PoC のテスト
(FORGE-USER-GUIDED-SELF-EXTENSION-006 §55・§56、2026-08-13新設)。

§56は「Registryへ1行追加しただけで自己拡張したとは言わない」と定めている。
成立条件は:

    Before : 要求Xが表現できない
    Extension: Capability追加
    After  : 同じ要求Xが 表現 → 検証 → コンパイル → 描画 → 使用 できる

このファイルはBefore/Afterを**実際に走らせて**示す。
到達できていない段(描画・使用)については、到達していないことを
テストとして固定する——できていないことを、できたことにしない。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.runtime.capability_definition import (  # noqa: E402
    CapabilityDefinition,
    TrustLevel,
    validate_definition,
)
from app.ai.validators.schema_validator import WIDGET_TYPES_ALL  # noqa: E402

# --- PoCの題材 -------------------------------------------------------------
#
# 「記録を一覧で見つつ、数値の大小を棒の長さでも同時に見たい」。
#
# この形はForge Languageで**表現可能**だが、Capabilityとしては登録されて
# いなかった(view.listとview.barsは別々にしか存在しない)。必要な
# Primitiveは3つともRuntimeに実装済みなので、**新しいDartは1行も要らない**。
_RANKED_LIST = CapabilityDefinition(
    id="composed.ranked_list",
    label_ja="一覧と棒の長さで同時に見る",
    primitive_ids=("view.list", "view.bars", "encoding.length"),
    origin="generated",
)


class TestBeforeAndAfter(unittest.TestCase):
    """§56の成立条件を、段ごとに確認する。"""

    def test_before_the_capability_is_not_in_the_registry(self) -> None:
        """Before: この形はCapabilityとして存在しない。"""
        from app.ai.runtime.capability import CAPABILITY_REGISTRY

        self.assertNotIn("composed.ranked_list", CAPABILITY_REGISTRY)

    def test_after_it_validates_as_composed_and_is_usable(self) -> None:
        """After(表現 → 検証): 既存Primitiveの合成として成立し、
        利用可能と判定される。**新しい実行コードは1行も無い**。"""
        outcome = validate_definition(_RANKED_LIST)
        self.assertIs(outcome.trust, TrustLevel.COMPOSED)
        self.assertTrue(outcome.definition_valid)
        self.assertTrue(outcome.primitives_available)
        self.assertEqual(outcome.rejections, ())

    def test_after_it_names_real_widgets_that_the_runtime_renders(self) -> None:
        """After(コンパイル): 参照するWidget型が、Validatorが知っていて
        Runtimeが実際に描けるものであること。

        ここまでが今回到達した範囲である。`bar_chart`も`record_list_view`も
        既に描画実績があるため、この合成は**描けるはずである**——ただし
        「はず」であり、合成として実機描画した確認まではしていない
        (下の`test_not_yet_verified_end_to_end`参照)。
        """
        outcome = validate_definition(_RANKED_LIST)
        self.assertTrue(outcome.widget_types)
        for widget_type in outcome.widget_types:
            self.assertIn(widget_type, WIDGET_TYPES_ALL)

    def test_not_yet_verified_end_to_end(self) -> None:
        """**到達していない段を、到達していないものとして固定する。**

        §56は「描画」「使用」までを求めている。今回そこへ到達していない
        のは、Compilerがこの合成を選ぶ経路(Solution Shape)をまだ持たない
        ためである。定義が妥当であることと、Compilerがそれを選ぶことは別。

        このテストは「まだ繋がっていない」ことの記録であり、繋がったら
        削除して本物のE2Eへ置き換えること。
        """
        from app.ai.runtime import capability_definition

        self.assertFalse(
            hasattr(capability_definition, "compile_definition"),
            "Compilerへの接続ができたら、このテストを本物のE2Eへ置き換えること",
        )


class TestSafetyGates(unittest.TestCase):
    """§34のThreat Modelのうち、この層が実際に止めるものを確認する。"""

    def test_hallucinated_primitive_is_rejected(self) -> None:
        """§45: AIが存在しないものを提案しても、Platform TruthはRegistry側。

        「AIが言ったから存在する」とは扱わない、が実際に機能すること。
        """
        outcome = validate_definition(CapabilityDefinition(
            id="composed.quantum", label_ja="量子地図",
            primitive_ids=("view.quantum_map", "view.list"),
        ))
        self.assertIs(outcome.trust, TrustLevel.REJECTED)
        self.assertEqual(outcome.rejections[0].code, "unknown_primitive")
        self.assertFalse(outcome.definition_valid)
        self.assertFalse(outcome.production_usable)

    def test_effects_cannot_be_acquired_by_composition(self) -> None:
        """§8: 外部作用は「合成したら手に入る」ものではない。
        ユーザーが欲しいと言っただけで危険Capabilityを有効化しない。"""
        outcome = validate_definition(CapabilityDefinition(
            id="composed.sharing_list", label_ja="共有できる一覧",
            primitive_ids=("view.list", "effect.share"),
        ))
        self.assertIs(outcome.trust, TrustLevel.REJECTED)
        self.assertEqual(outcome.rejections[0].code, "effect_not_composable")

    def test_unimplemented_primitive_yields_candidate_not_usable(self) -> None:
        """**ここが「作れたふり」を防ぐ核心**。定義としては妥当でも、
        必要なPrimitiveが未実装なら使えない。`CANDIDATE`は`usable=False`。"""
        outcome = validate_definition(CapabilityDefinition(
            id="composed.place_ranking", label_ja="場所ごとの多さ",
            primitive_ids=("transform.aggregate", "view.bars", "encoding.length"),
        ))
        self.assertIs(outcome.trust, TrustLevel.CANDIDATE)
        self.assertTrue(outcome.definition_valid, "定義そのものは妥当なはず")
        self.assertFalse(outcome.primitives_available, "未実装Primitiveを含むのに利用可能になっている")
        self.assertFalse(outcome.production_usable)
        self.assertEqual([p.id for p in outcome.missing_primitives], ["transform.aggregate"])
        self.assertIn("未実装", outcome.explain())

    def test_oversized_definition_is_rejected(self) -> None:
        """§28: `super_map_everything`のような巨大Capabilityを作らせない。"""
        outcome = validate_definition(CapabilityDefinition(
            id="composed.everything", label_ja="全部入り",
            primitive_ids=(
                "data.text", "data.number", "data.date", "data.choice",
                "data.bool", "view.list", "view.bars",
            ),
        ))
        self.assertIs(outcome.trust, TrustLevel.REJECTED)
        self.assertEqual(outcome.rejections[0].code, "too_broad")

    def test_definition_without_a_view_is_rejected(self) -> None:
        outcome = validate_definition(CapabilityDefinition(
            id="composed.invisible", label_ja="見えないもの",
            primitive_ids=("data.text", "data.number"),
        ))
        self.assertIs(outcome.trust, TrustLevel.REJECTED)
        self.assertEqual(outcome.rejections[0].code, "no_view")

    def test_empty_definition_is_rejected(self) -> None:
        outcome = validate_definition(CapabilityDefinition(
            id="composed.nothing", label_ja="空", primitive_ids=(),
        ))
        self.assertIs(outcome.trust, TrustLevel.REJECTED)


class TestStagedContract(unittest.TestCase):
    """指摘5の回帰テスト(2026-08-13)。

    「定義として妥当」と「本番のTool生成に使える」を、1つの`usable`で
    表していたため、Compiler未接続・描画未確認のものが「利用可能」と
    読める契約になっていた。段階を分け、**今はどれも本番利用不可**で
    あることを固定する。
    """

    def test_composed_is_not_production_usable(self) -> None:
        outcome = validate_definition(_RANKED_LIST)
        self.assertIs(outcome.trust, TrustLevel.COMPOSED)
        self.assertTrue(outcome.primitives_available)
        self.assertFalse(outcome.compiler_supported, "Compiler未接続なのにTrueになっている")
        self.assertFalse(outcome.runtime_verified, "合成としての描画は未確認")
        self.assertFalse(
            outcome.production_usable,
            "COMPOSEDが本番利用可能と読める契約に戻っている(指摘5の再発)",
        )

    def test_explanation_states_the_limitation(self) -> None:
        """説明文自体が、本番利用不可であることを述べること。"""
        self.assertIn("本番利用は不可", validate_definition(_RANKED_LIST).explain())

    def test_no_definition_is_production_usable_yet(self) -> None:
        """どの定義も、現時点では本番利用へ到達しない。"""
        from app.ai.runtime.semantic_capability import PRIMITIVE_REGISTRY

        implemented_views = [
            p.id for p in PRIMITIVE_REGISTRY.values()
            if p.implemented and p.kind.value == "view"
        ]
        for view_id in implemented_views:
            outcome = validate_definition(CapabilityDefinition(
                id=f"composed.{view_id}", label_ja="試験", primitive_ids=(view_id,),
            ))
            with self.subTest(view=view_id):
                self.assertFalse(outcome.production_usable)


class TestDeterminism(unittest.TestCase):
    """検証は決定的であること(同じ定義なら常に同じ判定)。"""

    def test_same_definition_same_outcome(self) -> None:
        first = validate_definition(_RANKED_LIST)
        second = validate_definition(_RANKED_LIST)
        self.assertEqual(first.trust, second.trust)
        self.assertEqual(first.widget_types, second.widget_types)

    def test_rejection_always_explains_itself(self) -> None:
        """「駄目でした」だけで終わらせない。次に何を直せばよいかを言う。"""
        bad = [
            CapabilityDefinition("a", "x", ("nope",)),
            CapabilityDefinition("b", "x", ("view.list", "effect.share")),
            CapabilityDefinition("c", "x", ()),
            CapabilityDefinition("d", "x", ("data.text",)),
        ]
        for definition in bad:
            with self.subTest(definition=definition.id):
                outcome = validate_definition(definition)
                self.assertIs(outcome.trust, TrustLevel.REJECTED)
                self.assertTrue(outcome.rejections)
                self.assertTrue(outcome.rejections[0].detail)


if __name__ == "__main__":
    unittest.main()
