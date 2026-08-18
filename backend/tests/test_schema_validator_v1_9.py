"""Forge Language v1.9(bar_chartの集計)のValidatorテスト
(FORGE-USER-GUIDED-SELF-EXTENSION-006 Phase 4、2026-08-13新設)。

v1.9は**新しいWidget型を追加しない**。`bar_chart`へ`group_by`/`aggregate`を
足しただけである。Widgetを増やさずに表現の幅が増えたのは、足したものが
表示ではなく**データ変換**(TRANSFORM層)だからである。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.validators.schema_validator import (  # noqa: E402
    BAR_CHART_AGGREGATES,
    validate_forge_document,
)


def _doc(chart: dict, version: str = "1.9") -> dict:
    return {
        "version": version,
        "initial_screen_id": "s1",
        "record_schemas": {
            "catch": {
                "fields": [
                    {"name": "place", "type": "string", "label": "場所", "required": True},
                    {"name": "size", "type": "number", "label": "サイズ", "required": True},
                ]
            }
        },
        "screens": [{
            "id": "s1", "title": "釣果",
            "state": {"records": {"type": "record_list", "value": [], "schema_ref": "catch"}},
            "body": {"type": "column", "id": "root", "children": [chart]},
        }],
    }


def _chart(**props) -> dict:
    return {"type": "bar_chart", "id": "c1", "state_ref": "records", **props}


class TestAggregateAccepted(unittest.TestCase):
    def test_group_by_with_count_needs_no_value_field(self) -> None:
        """countは数えるだけなので値Fieldが要らない。ここを必須のままに
        すると、Compilerが意味の無いFieldを埋めることになる。"""
        result = validate_forge_document(_doc(_chart(group_by="place", aggregate="count")))
        self.assertTrue(result.valid, [e.to_dict() for e in result.errors])

    def test_group_by_defaults_to_count(self) -> None:
        result = validate_forge_document(_doc(_chart(group_by="place")))
        self.assertTrue(result.valid, [e.to_dict() for e in result.errors])

    def test_sum_and_average_accept_a_value_field(self) -> None:
        for op in ("sum", "average"):
            with self.subTest(op=op):
                result = validate_forge_document(
                    _doc(_chart(group_by="place", aggregate=op, value_field="size"))
                )
                self.assertTrue(result.valid, [e.to_dict() for e in result.errors])


class TestAggregateRejected(unittest.TestCase):
    def test_sum_without_value_field_is_rejected(self) -> None:
        result = validate_forge_document(_doc(_chart(group_by="place", aggregate="sum")))
        self.assertFalse(result.valid)
        self.assertTrue(any("value_field" in e.path for e in result.errors))

    def test_unknown_aggregate_is_rejected(self) -> None:
        """未知の集計方法を黙ってcountへ倒さない。書き間違いが
        検出されないまま動くのが最も危ない。"""
        result = validate_forge_document(
            _doc(_chart(group_by="place", aggregate="median", value_field="size"))
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("aggregate" in e.path for e in result.errors))

    def test_aggregate_without_group_by_is_rejected(self) -> None:
        """集計方法だけ指定してグループ化キーが無いのは、ほぼ確実に
        書き間違いである。黙って無視すると利用者が気づけない。"""
        result = validate_forge_document(
            _doc(_chart(aggregate="sum", value_field="size", label_field="place"))
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("aggregate" in e.path for e in result.errors))

    def test_group_by_must_be_an_identifier(self) -> None:
        result = validate_forge_document(_doc(_chart(group_by="not an identifier!")))
        self.assertFalse(result.valid)

    def test_group_by_must_reference_a_real_field(self) -> None:
        """存在しないFieldで「集計できたつもり」にさせない。
        ここを検査しないと、実行時に静かに空のグラフが出るだけで、
        なぜ何も出ないのかが分からない。"""
        result = validate_forge_document(_doc(_chart(group_by="nonexistent")))
        self.assertFalse(result.valid)
        self.assertTrue(
            any(e.path.endswith("/group_by") and e.rule == "field_reference_exists"
                for e in result.errors),
            [e.to_dict() for e in result.errors],
        )


class TestBackwardCompatibility(unittest.TestCase):
    """v1.9はproperty-onlyの追加である。既存文書の扱いは変わらない。"""

    def test_v1_6_style_chart_still_valid(self) -> None:
        result = validate_forge_document(
            _doc(_chart(value_field="size", label_field="place"), version="1.6")
        )
        self.assertTrue(result.valid, [e.to_dict() for e in result.errors])

    def test_non_aggregating_chart_still_requires_both_fields(self) -> None:
        """`group_by`が無い場合、value_field/label_fieldは従来どおり必須。
        緩めた範囲を、集計する場合だけへ正確に限定していることの確認。"""
        for props in ({"value_field": "size"}, {"label_field": "place"}):
            with self.subTest(props=props):
                result = validate_forge_document(_doc(_chart(**props)))
                self.assertFalse(result.valid)

    def test_no_new_widget_type_was_added(self) -> None:
        from app.ai.validators.schema_validator import WIDGET_TYPES_BY_VERSION

        self.assertEqual(
            WIDGET_TYPES_BY_VERSION["1.9"], WIDGET_TYPES_BY_VERSION["1.8"],
            "v1.9はWidget型を増やしていないはず(足したのはデータ変換)",
        )


class TestRuntimeContractIsShared(unittest.TestCase):
    """TD37と同じ形の事故(Validatorは通るがRuntimeが解釈できない)を防ぐ。"""

    def test_aggregate_values_match_the_flutter_enum(self) -> None:
        """`BAR_CHART_AGGREGATES`とDart側`ForgeAggregateOp`を突き合わせる。
        **実際のDartソースを読んで**確認する——コメントでの申し合わせは
        破られるが、これは破られたら落ちる。"""
        import pathlib
        import re

        dart = pathlib.Path(__file__).resolve().parents[2] / (
            "frontend/lib/json_ui/runtime/forge_aggregate.dart"
        )
        if not dart.exists():
            self.skipTest("frontend/ が無い環境ではスキップ")
        source = dart.read_text(encoding="utf-8")
        block = re.search(r"enum ForgeAggregateOp \{(.*?)\n\}", source, re.S)
        self.assertIsNotNone(block, "ForgeAggregateOpのenum定義が見つからない")
        names = set(re.findall(r"^\s{2}(\w+)[,;]", block.group(1), re.M))

        # v1.11(FORGE-R1-CLOSURE-015)以降、**Widgetによって許す集計が違う**。
        #
        #   bar_chart   : count / sum / average      （複数の値を並べる）
        #   metric_view : + max / min / latest       （単一の値だから意味を持つ）
        #
        # Dartのenumは両方の和集合を持つ。だから「enum == BAR_CHART」では
        # なく、**Validatorが許すものがenumに全部あるか**を見る
        # (Validatorが通すのにRuntimeが解釈できない、がTD37の事故)。
        from app.ai.validators.schema_validator import METRIC_VIEW_AGGREGATES

        self.assertEqual(
            names, METRIC_VIEW_AGGREGATES,
            "Validatorが許す集計方法と、Runtimeが解釈できる集計方法が食い違っている",
        )
        self.assertTrue(
            BAR_CHART_AGGREGATES < METRIC_VIEW_AGGREGATES,
            "bar_chartが許す集計はmetric_viewの真部分集合であるべき",
        )


if __name__ == "__main__":
    unittest.main()
