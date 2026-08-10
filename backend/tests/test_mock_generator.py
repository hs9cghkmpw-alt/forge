"""mock_generator.py のテスト。

最重要なのは test_every_category_output_passes_validator と
test_every_inspiration_card_phrase_maps_correctly: 生成器の出力を実際に
schema_validator に通し、Flutterが無い(=レンダラーを実行できない)このサンドボックス内でも
「生成 → 検証」の経路が本当に繋がることをEnd-to-Endに近い形で確認する。

実行方法:
    cd backend
    python -m unittest tests.test_mock_generator -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.generators.mock_generator import generate_forge_document  # noqa: E402
from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


class TestMockGeneratorOutputShape(unittest.TestCase):
    def test_shopping_keyword_produces_shopping_list(self):
        doc = generate_forge_document("買い物メモを作って")
        self.assertEqual(doc["app"]["title"], "買い物メモ")
        items = doc["screens"][0]["state"]["items"]["value"]
        self.assertEqual([i["text"] for i in items], ["卵", "牛乳", "食パン", "野菜", "洗剤"])

    def test_empty_input_falls_back_to_generic_list(self):
        doc = generate_forge_document("   ")
        self.assertEqual(doc["app"]["title"], "新しいリスト")

    def test_unmatched_input_uses_input_as_title(self):
        doc = generate_forge_document("犬の名前を考える")
        self.assertEqual(doc["app"]["title"], "犬の名前を考える")
        items = doc["screens"][0]["state"]["items"]["value"]
        self.assertEqual([i["text"] for i in items], ["最初のアイテム"])


class TestAllEightInspirationCardsMapCorrectly(unittest.TestCase):
    """home_screen.dart の _inspirationCards 8件それぞれの実フレーズで検証する。
    (監査時点でこのうち6件が汎用Fallbackに落ちていた既知のギャップの回帰テスト)
    """

    CASES = [
        ("今日の晩ご飯を考えるメモを作って", "今日のご飯メモ"),
        ("買い物メモを作って", "買い物メモ"),
        ("旅行の持ち物チェックを作って", "旅行の持ち物チェック"),
        ("家計簿をつけるメモを作って", "家計簿"),
        ("今日の予定リストを作って", "今日の予定"),
        ("子どもの持ち物チェックを作って", "子どもの持ち物チェック"),  # 「持ち物」衝突の回帰テスト
        ("ペットのお世話チェックリストを作って", "ペットのお世話チェック"),
        ("プレゼントのアイデアリストを作って", "プレゼントのアイデア"),
    ]

    def test_each_card_phrase_maps_to_expected_title(self):
        for phrase, expected_title in self.CASES:
            with self.subTest(phrase=phrase):
                doc = generate_forge_document(phrase)
                self.assertEqual(doc["app"]["title"], expected_title)

    def test_kids_checklist_is_not_misclassified_as_travel(self):
        # 「持ち物」が旅行キーワードでもあるため、判定順を間違えると壊れる回帰テスト
        doc = generate_forge_document("子どもの持ち物チェックを作って")
        items = doc["screens"][0]["state"]["items"]["value"]
        self.assertIn("オムツ", [i["text"] for i in items])
        self.assertNotIn("パスポート", [i["text"] for i in items])


class TestMockGeneratorOutputAlwaysValidates(unittest.TestCase):
    """生成 → Validator の経路そのものを検証する(擬似End-to-Endテスト)。"""

    def test_every_category_output_passes_validator(self):
        sample_inputs = [
            "買い物メモを作って", "todoリストを作って", "今日の晩ご飯を考えるメモを作って",
            "家計簿をつけるメモを作って", "今日の予定リストを作って", "子どもの持ち物チェックを作って",
            "ペットのお世話チェックリストを作って", "プレゼントのアイデアリストを作って",
            "旅行の持ち物チェックを作って", "", "適当な入力文字列123",
        ]
        for raw in sample_inputs:
            with self.subTest(raw=raw):
                doc = generate_forge_document(raw)
                result = validate_forge_document(doc)
                self.assertTrue(result.valid, msg=f"input={raw!r} -> errors={result.to_dict()}")

    def test_output_item_ids_are_unique_and_well_formed(self):
        doc = generate_forge_document("旅行の持ち物チェックを作って")
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


if __name__ == "__main__":
    unittest.main()
