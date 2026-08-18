"""Hero KPI (`metric_view`、Forge Language v1.11) の検査
(FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、TD69、2026-08-17)。

---

## 何が問題だったのか

v1.10でDesign Languageを入れたとき、語彙へ`metric.primary`
——「画面で最も重要な単一のKPI」——を入れた。ところが

* `text`      : Stateの文字列を出すだけ。集計できない
* `bar_chart` : **複数**の値を並べる。単一の主数値にはならない

しかなく、**その役割を持てるWidgetが1つも無かった**。つまり語彙に
「言えるのに作れない言葉」が入っていた。「今月の残高を一番目立たせて」
と言われても出す先が無い、という状態である。

ここでは**語彙とWidgetの対応が実際に成立していること**を、本番の
生成経路（HTTP `/generate`）を通して確認する。
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.ai.validators.schema_validator import (
    WIDGET_TYPES_BY_VERSION,
    validate_forge_document,
)
from app.main import app


def _widgets(widget: dict):
    yield widget
    for child in widget.get("children", []) or ():
        yield from _widgets(child)


class TestTheHeroMetricReachesTheGeneratedApp(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _document(self, text: str) -> dict:
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": text,
                            "generation_options": {"provider": "mock"}}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["result"]["forge_document"]

    def _all_widgets(self, document: dict) -> list[dict]:
        return [w for s in document["screens"] for w in _widgets(s["body"])]

    def test_a_money_app_gets_income_expense_and_balance(self) -> None:
        """v1.12(§2.3)。**単純な合計を「残高」と呼ばない。**

        収入と支出を区別しない合計は、いくら記録しても
        「今いくら残っているか」に答えていない。
        """
        document = self._document("家計の支出をカテゴリ別に管理したい")
        metrics = {w["style_role"]: w for w in self._all_widgets(document)
                   if w["type"] == "metric_view"}
        self.assertEqual(
            set(metrics), {"metric.primary", "finance.income", "finance.expense"},
            "収入・支出・残高が揃っていない",
        )
        balance = metrics["metric.primary"]
        self.assertEqual(balance["label"], "残高")
        self.assertEqual(balance["aggregate"], "sum")
        self.assertEqual(balance["negative_when"], "支出", "支出を負として足していない")
        self.assertEqual(metrics["finance.income"]["filter_value"], "収入")
        self.assertEqual(metrics["finance.expense"]["filter_value"], "支出")

    def test_only_the_balance_is_the_primary_metric(self) -> None:
        """3つとも主KPIにすると「一番大事なもの」が3つになり階層が消える。"""
        document = self._document("家計の支出をカテゴリ別に管理したい")
        primaries = [w for w in self._all_widgets(document)
                     if w.get("style_role") == "metric.primary"]
        self.assertEqual(len(primaries), 1)
        self.assertEqual(primaries[0]["label"], "残高")

    def test_the_role_metric_primary_now_has_an_output_target(self) -> None:
        """**このテストがTD69の本体である。**

        語彙に在るだけの言葉になっていないこと——実際に生成物の中で
        `metric.primary`を持つWidgetが存在すること。
        """
        document = self._document("家計の支出をカテゴリ別に管理したい")
        carriers = [
            w for w in self._all_widgets(document)
            if w.get("style_role") == "metric.primary"
        ]
        self.assertTrue(
            carriers,
            "metric.primary を持つWidgetが生成物に無い。"
            "語彙にあるのに出力先が無い状態へ戻っている。",
        )

    def test_the_hero_metric_comes_before_the_list(self) -> None:
        """**順序に意味がある。**

        「今月いくら使ったか」を知りたい人は一覧を読みたいわけでは
        ない。一覧の下に置くと、主KPIは「一覧のおまけの合計」になる。
        """
        document = self._document("家計の支出をカテゴリ別に管理したい")
        for screen in document["screens"]:
            for widget in _widgets(screen["body"]):
                types = [c["type"] for c in widget.get("children", []) or ()]
                if "metric_view" in types and "record_list_view" in types:
                    self.assertLess(types.index("metric_view"), types.index("record_list_view"))
                    return
        self.fail("metric_viewとrecord_list_viewが同じ親に並んでいない")

    def test_an_app_without_numbers_gets_no_hero_metric(self) -> None:
        """**出せるからといって出さない。**

        件数を数えることはできるが、「習慣が3件ある」は画面で一番
        大きく出すべき数値ではない。根拠のない集計を発明しない。
        """
        document = self._document("毎日の習慣を続けたい")
        self.assertEqual(
            [w for w in self._all_widgets(document) if w["type"] == "metric_view"], [],
            "数値Fieldが無いのに主KPIを発明している",
        )

    def test_the_generated_document_is_valid(self) -> None:
        document = self._document("家計の支出をカテゴリ別に管理したい")
        result = validate_forge_document(document)
        self.assertTrue(result.valid, [e.to_dict() for e in result.errors])


class TestTheSchemaKnowsMetricView(unittest.TestCase):
    def test_metric_view_is_allowed_from_v1_11(self) -> None:
        self.assertIn("metric_view", WIDGET_TYPES_BY_VERSION["1.11"])
        self.assertNotIn("metric_view", WIDGET_TYPES_BY_VERSION["1.10"])

    def _doc(self, metric: dict, version: str = "1.11") -> dict:
        return {
            "version": version,
            "app": {"title": "家計簿"},
            "initial_screen_id": "s1",
            "record_schemas": {
                "expense": {"fields": [
                    {"name": "category", "type": "string", "label": "カテゴリ", "required": True},
                    {"name": "amount", "type": "number", "label": "金額", "required": True},
                ]},
            },
            "screens": [{
                "id": "s1", "title": "家計簿",
                "state": {"records": {"type": "record_list", "value": [], "schema_ref": "expense"}},
                "body": {"type": "column", "id": "root", "children": [metric]},
            }],
        }

    def _errors(self, metric: dict, version: str = "1.11") -> list[str]:
        return [e.to_dict()["rule"] for e in validate_forge_document(self._doc(metric, version)).errors]

    def test_a_well_formed_metric_view_passes(self) -> None:
        self.assertEqual(self._errors({
            "type": "metric_view", "id": "hero", "state_ref": "records",
            "value_field": "amount", "aggregate": "sum", "label": "合計", "unit": "円",
        }), [])

    def test_count_does_not_need_a_value_field(self) -> None:
        self.assertEqual(self._errors({
            "type": "metric_view", "id": "hero", "state_ref": "records", "aggregate": "count",
        }), [])

    def test_sum_without_a_value_field_is_rejected(self) -> None:
        self.assertIn("required", self._errors({
            "type": "metric_view", "id": "hero", "state_ref": "records", "aggregate": "sum",
        }))

    def test_a_non_numeric_value_field_is_rejected(self) -> None:
        """**画面で一番大きく出る数値**なので、bar_chartより踏み込んで
        「実在する数値Fieldか」まで検査する。"""
        self.assertIn("field_type_mismatch", self._errors({
            "type": "metric_view", "id": "hero", "state_ref": "records",
            "value_field": "category", "aggregate": "sum",
        }))

    def test_a_missing_value_field_is_rejected(self) -> None:
        self.assertIn("field_reference_exists", self._errors({
            "type": "metric_view", "id": "hero", "state_ref": "records",
            "value_field": "nonexistent", "aggregate": "sum",
        }))

    def test_group_by_is_not_accepted(self) -> None:
        """受け付ければ「グループが複数あるのに数値は1つ」という、
        表示できない文書が作れてしまう。複数並べたいならbar_chartがある。"""
        self.assertIn("additional_properties", self._errors({
            "type": "metric_view", "id": "hero", "state_ref": "records",
            "value_field": "amount", "aggregate": "sum", "group_by": "category",
        }))

    def test_metric_view_is_rejected_in_v1_10(self) -> None:
        errors = self._errors({
            "type": "metric_view", "id": "hero", "state_ref": "records",
            "value_field": "amount", "aggregate": "sum",
        }, version="1.10")
        self.assertTrue(errors, "v1.10でmetric_viewが通ってしまう")


if __name__ == "__main__":
    unittest.main()
