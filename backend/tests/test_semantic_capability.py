"""Semantic Capability / Runtime Primitive のテスト
(FORGE-USER-GUIDED-SELF-EXTENSION-006 §29・§54、2026-08-13新設)。

この層の存在意義は「`view.heatmap`が無い」という**誤診**を、
「集計と濃淡と地理描画のうち、地理描画だけが本当に無い」という
正しい診断へ変えることである。テストもそこを固定する。
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import app.ai.runtime.semantic_capability as sc  # noqa: E402
from app.ai.runtime.semantic_capability import (  # noqa: E402
    PRIMITIVE_REGISTRY,
    PrimitiveKind,
    decompose,
)
from app.ai.validators.schema_validator import WIDGET_TYPES_ALL  # noqa: E402


class TestPrimitiveRegistryHonesty(unittest.TestCase):
    """Registryが実装状況について嘘をつかないこと。"""

    def test_implemented_view_primitives_point_at_real_widgets(self) -> None:
        for primitive in PRIMITIVE_REGISTRY.values():
            if not (primitive.implemented and primitive.kind is PrimitiveKind.VIEW):
                continue
            with self.subTest(primitive=primitive.id):
                self.assertTrue(primitive.widget_types)
                for widget_type in primitive.widget_types:
                    self.assertIn(widget_type, WIDGET_TYPES_ALL)

    def test_unimplemented_primitives_explain_what_is_missing(self) -> None:
        """未実装のものには、何が要るのかを書いておく。
        「無い」だけでは、次に何をすればよいか分からない。"""
        for primitive in PRIMITIVE_REGISTRY.values():
            if primitive.implemented:
                continue
            with self.subTest(primitive=primitive.id):
                self.assertTrue(primitive.note, "未実装Primitiveにはnoteが要る")

    def test_transform_primitives_are_not_widgets(self) -> None:
        """集計・絞り込み・並べ替えはWidgetではない。ここを混同していた
        ことが、v1で「Widgetが無い」としか言えなかった原因である。"""
        for primitive in PRIMITIVE_REGISTRY.values():
            if primitive.kind is PrimitiveKind.TRANSFORM:
                with self.subTest(primitive=primitive.id):
                    self.assertEqual(primitive.widget_types, ())


class TestDecompositionDiagnosesTheRealGap(unittest.TestCase):
    """§29の核心: 「heatmapが無い」ではなく、何が無いのかを言えること。"""

    def test_heatmap_decomposes_into_four_different_kinds_of_gap(self) -> None:
        d = decompose("view.heatmap")
        self.assertIsNotNone(d)
        kinds = {p.kind for p in d.missing}
        self.assertIn(PrimitiveKind.TRANSFORM, kinds, "集計が不足として現れていない")
        self.assertIn(PrimitiveKind.ENCODING, kinds, "濃淡が不足として現れていない")
        self.assertIn(PrimitiveKind.VIEW, kinds, "地理描画が不足として現れていない")

    def test_exact_satisfaction_and_renderability_are_separate_questions(self) -> None:
        """指摘6の回帰テスト(2026-08-13)。

        以前の`blocking_missing`は「MissingのうちVIEWだけ」を返していた
        ため、`semantic.ranking_by_group`(集計が未実装・VIEWは既存)で
        **空になり**、問題が無いように読めた。「要求どおり作れない」と
        「何も出せない」は別の問いである。
        """
        heatmap = decompose("view.heatmap")
        self.assertFalse(heatmap.satisfiable_exactly)
        self.assertFalse(heatmap.renderable_at_all, "地理描画が無いので何も出せない")

        trend = decompose("view.line_chart")
        self.assertFalse(trend.satisfiable_exactly, "並べ替えが無いので要求どおりではない")
        self.assertTrue(trend.renderable_at_all, "棒グラフはあるので何かは出せる")
        self.assertTrue(trend.fallback_possible)

    def test_a_missing_transform_still_means_not_satisfiable(self) -> None:
        """VIEWが揃っていても、集計が無ければ要求どおりには作れない。
        ここが以前は空(=問題なし)に見えていた箇所である。"""
        from app.ai.runtime.semantic_capability import (
            _DECOMPOSITION,
            CapabilityDecomposition,
        )

        d = CapabilityDecomposition(
            "semantic.ranking_by_group",
            tuple(PRIMITIVE_REGISTRY[i] for i in _DECOMPOSITION["semantic.ranking_by_group"]),
        )
        self.assertFalse(d.satisfiable_exactly)
        self.assertTrue(d.renderable_at_all)

    def test_trend_is_almost_buildable(self) -> None:
        """「推移を見たい」は、実は並べ替えが無いだけである。
        1語の診断("line_chartが無い")では、この近さが見えない。"""
        d = decompose("view.line_chart")
        self.assertEqual(d.distance, 1)
        self.assertEqual([p.id for p in d.missing], ["transform.sort"])
        self.assertTrue(d.renderable_at_all, "描画は既にある(view.bars)")

    def test_unknown_capability_is_not_guessed(self) -> None:
        """分解表に無いものを推測で分解しない。知らないことは知らないまま
        にしておく方が、それらしい嘘より安全である。"""
        self.assertIsNone(decompose("view.list"))
        self.assertIsNone(decompose("does.not.exist"))


class TestNearestAlternative(unittest.TestCase):
    """§30: 新Capabilityが本当に必要かを最初に疑う。"""

    def test_map_heatmap_has_a_much_closer_alternative(self) -> None:
        """「地図で濃淡」は4個先だが、同じ困りごとに答える
        「場所ごとの集計」は1個先である。**この差が分解の実際の効用**。"""
        d = decompose("view.heatmap")
        self.assertEqual(d.distance, 4)
        alternative = d.nearest_alternative()
        self.assertIsNotNone(alternative)
        semantic_id, remaining = alternative
        self.assertEqual(semantic_id, "semantic.ranking_by_group")
        self.assertEqual(remaining, 1)
        self.assertLess(remaining, d.distance)

    def test_never_suggests_something_further_away(self) -> None:
        for capability_id in ("view.heatmap", "view.map", "view.calendar", "view.line_chart"):
            d = decompose(capability_id)
            alternative = d.nearest_alternative()
            if alternative is not None:
                with self.subTest(capability=capability_id):
                    self.assertLess(alternative[1], d.distance)


class TestLeverageMeasurement(unittest.TestCase):
    """実装して自分の主張を検証した結果を、テストとして固定する。

    レビューv2 §3.4は当初「集計Primitiveを足すと表現の**族**が増える」と
    書いていた。実測はこれを**支持しなかった**(どのPrimitiveも+1個)。
    測定が支持したのは「同じ困りごとへ最も安く到達できる道である」という
    別の事実だった。§22-bisに訂正を記録した。

    主張と測定が食い違ったまま放置されないよう、測定自体をここに残す。
    """

    def _feasible_count(self, registry) -> int:
        count = 0
        for required_ids in sc._DECOMPOSITION.values():
            primitives = [registry[i] for i in required_ids if i in registry]
            if primitives and all(p.implemented for p in primitives):
                count += 1
        return count

    def test_nothing_is_fully_buildable_today(self) -> None:
        """現状、分解表のSemanticは1つも完全には成立しない。
        これは悲観ではなく事実であり、次に何をすべきかの根拠になる。"""
        self.assertEqual(self._feasible_count(PRIMITIVE_REGISTRY), 0)

    def test_no_single_primitive_unlocks_more_than_one_pattern(self) -> None:
        """当初の「族が増える」という主張が、この指標では成り立たないこと。
        将来この前提が変わったら(分解表が育ったら)ここが落ちるので、
        そのとき主張を書き直せる。"""
        base = dict(PRIMITIVE_REGISTRY)
        for primitive_id, primitive in PRIMITIVE_REGISTRY.items():
            if primitive.implemented:
                continue
            trial = dict(base)
            trial[primitive_id] = replace(primitive, implemented=True)
            with self.subTest(primitive=primitive_id):
                self.assertLessEqual(self._feasible_count(trial), 1)

    def test_aggregate_is_the_cheapest_path_to_the_fishing_need(self) -> None:
        """測定が実際に支持した事実。`transform.aggregate`だけを実装すると、
        「よく釣れる場所を知りたい」に答える形が成立する。"""
        trial = dict(PRIMITIVE_REGISTRY)
        trial["transform.aggregate"] = replace(
            PRIMITIVE_REGISTRY["transform.aggregate"], implemented=True
        )
        required = sc._DECOMPOSITION["semantic.ranking_by_group"]
        self.assertTrue(all(trial[i].implemented for i in required))


class TestConversationSurface(unittest.TestCase):
    """§58: 内部語をユーザーへ出さない。"""

    def test_hint_uses_japanese_not_internal_ids(self) -> None:
        from app.ai.runtime.capability import build_hypothesis

        message = build_hypothesis("釣果を色の濃さで地図に出したい").to_message()
        self.assertIn("場所ごとの多さを並べて見る形", message)
        for forbidden in ("semantic.", "transform.", "primitive", "Capability"):
            self.assertNotIn(forbidden, message)

    def test_no_hint_when_there_is_no_closer_alternative(self) -> None:
        """近い代替が無いときに、それらしい文言を作らない。"""
        from app.ai.runtime.capability import build_hypothesis

        message = build_hypothesis("買ったものをカレンダーで見たい").to_message()
        self.assertNotIn("もう少しで作れる", message)


if __name__ == "__main__":
    unittest.main()
