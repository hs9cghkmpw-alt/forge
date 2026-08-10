"""Mock Generator v2 の新規カテゴリ・新規Template のテスト(PHASE5/9)。

Household(家事)・Survey(アンケート、Formテンプレート)・Memo(メモ、
Memoテンプレート)の3つが正しく動作し、既存カテゴリと衝突しないことを検証する。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.generators.mock_generator import generate_forge_document  # noqa: E402
from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


class TestHouseholdCategory(unittest.TestCase):
    def test_household_keyword_produces_household_checklist(self):
        doc = generate_forge_document("今日の家事リストを作って")
        self.assertEqual(doc["app"]["title"], "今日の家事")
        self.assertEqual(doc["version"], "1.0")  # Checklistテンプレートはv1.0のみで構成される
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_household_does_not_collide_with_budget_category(self):
        """「家事」と「家計簿」はどちらも「家」で始まるが、誤分類しないことを確認する。"""
        household_doc = generate_forge_document("掃除のチェックリストを作って")
        self.assertEqual(household_doc["app"]["title"], "今日の家事")
        budget_doc = generate_forge_document("家計簿をつけたい")
        self.assertEqual(budget_doc["app"]["title"], "家計簿")


class TestSurveyCategory(unittest.TestCase):
    def test_survey_keyword_produces_form_template(self):
        doc = generate_forge_document("満足度アンケートを作って")
        # FORGE-MILESTONE-003でコメント欄にvalidation(max_length)を追加したため、
        # v1.1からv1.2へ更新した(validationはv1.2専用プロパティ)。
        self.assertEqual(doc["version"], "1.2")
        self.assertEqual(len(doc["screens"]), 2, "Formテンプレートは送信先画面を含め2画面のはず")
        self.assertEqual(doc["screens"][0]["id"], doc["initial_screen_id"])

    def test_survey_document_is_valid(self):
        doc = generate_forge_document("アンケートを作って")
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_survey_contains_form_and_card_widgets(self):
        doc = generate_forge_document("survey")
        body = doc["screens"][0]["body"]
        types_found = {w["type"] for w in _flatten(body)}
        self.assertIn("form", types_found)
        self.assertIn("card", types_found)
        self.assertIn("checkbox", types_found)
        self.assertIn("heading", types_found)

    def test_survey_submit_navigates_to_thanks_screen(self):
        doc = generate_forge_document("アンケートを作って")
        form_widget = next(w for w in _flatten(doc["screens"][0]["body"]) if w["type"] == "form")
        self.assertEqual(form_widget["submit_action"]["type"], "navigate")
        target = form_widget["submit_action"]["target_screen_id"]
        self.assertIn(target, [s["id"] for s in doc["screens"]])


class TestMemoCategory(unittest.TestCase):
    def test_memo_keyword_produces_memo_template(self):
        doc = generate_forge_document("メモを作って")
        self.assertEqual(doc["version"], "1.1")
        body = doc["screens"][0]["body"]
        types_found = [w["type"] for w in _flatten(body)]
        self.assertEqual(types_found.count("text_field"), 1)
        self.assertIn("heading", types_found)
        # Memoはチェックリストを持たない(買い物メモ等と違う構造であることの確認)
        self.assertNotIn("checklist", types_found)

    def test_memo_does_not_steal_shopping_memo(self):
        """「買い物メモ」の「メモ」に反応して、買い物カテゴリを奪わないことを確認する
        (カテゴリ判定順序でメモを最後に置いていることの回帰テスト)。"""
        doc = generate_forge_document("買い物メモを作って")
        self.assertEqual(doc["app"]["title"], "買い物メモ")
        body = doc["screens"][0]["body"]
        types_found = [w["type"] for w in _flatten(body)]
        self.assertIn("checklist", types_found, "買い物メモは引き続きchecklist構造であるべき")

    def test_memo_document_is_valid(self):
        result = validate_forge_document(generate_forge_document("ノートを作って"))
        self.assertTrue(result.valid, msg=result.to_dict())


class TestAllCategoriesStillProduceValidDocuments(unittest.TestCase):
    """12カテゴリ(既存9 + 新規3)全てが、拡張後のValidatorでも合格することを確認する。"""

    def test_all_categories_valid(self):
        phrases = [
            "買い物メモを作って", "todoリストを作って", "今日の晩ご飯を考えるメモを作って",
            "家計簿をつけるメモを作って", "今日の予定リストを作って", "子どもの持ち物チェックを作って",
            "ペットのお世話チェックリストを作って", "プレゼントのアイデアリストを作って",
            "旅行の持ち物チェックを作って", "家事のチェックリストを作って",
            "満足度アンケートを作って", "メモを作って",
            "", "適当な入力文字列123",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                doc = generate_forge_document(phrase)
                result = validate_forge_document(doc)
                self.assertTrue(result.valid, msg=f"input={phrase!r} -> {result.to_dict()}")


def _flatten(widget: dict) -> list[dict]:
    result = [widget]
    for child in widget.get("children", []):
        result.extend(_flatten(child))
    return result


if __name__ == "__main__":
    unittest.main()
