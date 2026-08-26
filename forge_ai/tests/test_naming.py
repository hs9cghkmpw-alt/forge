"""アプリ名の契約（Generated UI Quality Gate v2 修正1）。

`forge_ai/core/naming.py` が何を名前として認め、何を認めないか。

**このテストは「文を名前にしない」ことを固定する。** 実描画で
AppBar に「毎日の収入と支出を記録して残高を見たい」と出ていたのが
出発点である（`docs/reports/GENERATED-UI-QUALITY-GATE-V2-report.md`）。
"""

from __future__ import annotations

import unittest

from forge_ai.core.naming import (
    GENERIC_APP_NAME,
    MAX_APP_NAME_LENGTH,
    AppName,
    NameSource,
    decide_app_name,
    domain_label_for,
    is_name_like,
)

#: Quality Gate v2 で実際に AppBar へ出ていた文字列（実測）。
#: **1つでも通れば、この修正は効いていない。**
SENTENCES_SEEN_IN_PRODUCTION: tuple[str, ...] = (
    "毎日の収入と支出を記録して残高を見たい",
    "今日やる作業を登録して、終わったものを消していきたい",
    "子どもが朝の支度をひとつずつチェックできるようにしたい",
    "旅行の写真を日付ごとに残してメモを付けたい",
    "釣った場所を地図に残して魚の種類",
    "植物を育てながら音を組み合わせるゲーム",
    "部署ごとの売上を月別に集計してグラフで比べたい",
    "英単語を出題して、正解率の推移を見たい",
)

#: 名前として通ってよいもの（実際に Forge が出す値）。
REAL_NAMES: tuple[str, ...] = (
    "買い物リスト", "家計簿記録", "釣果記録", "やること",
    "こどもの成長", "日記", "在庫", "旅行", "メモ",
)


class TestSentencesAreNotNames(unittest.TestCase):
    def test_every_sentence_seen_in_production_is_rejected(self) -> None:
        for sentence in SENTENCES_SEEN_IN_PRODUCTION:
            with self.subTest(sentence=sentence):
                self.assertFalse(is_name_like(sentence))

    def test_real_names_are_accepted(self) -> None:
        for name in REAL_NAMES:
            with self.subTest(name=name):
                self.assertTrue(is_name_like(name))

    def test_empty_is_not_a_name(self) -> None:
        for value in ("", "   ", None):
            self.assertFalse(is_name_like(value))

    def test_too_long_is_a_description_not_a_name(self) -> None:
        self.assertFalse(is_name_like("あ" * (MAX_APP_NAME_LENGTH + 1)))
        self.assertTrue(is_name_like("あ" * MAX_APP_NAME_LENGTH))

    def test_punctuation_means_it_is_not_one_noun_phrase(self) -> None:
        for value in ("買い物、メモ", "買い物。", "買い物？", "買い物!"):
            with self.subTest(value=value):
                self.assertFalse(is_name_like(value))


class TestInternalIdentifiersAreNotNames(unittest.TestCase):
    """#29「内部識別子を出さない」と同じ穴。**3度目**なので固定する。"""

    def test_lowercase_ascii_identifiers_are_rejected(self) -> None:
        for value in ("item", "task", "fish_record", "transaction", "entry1"):
            with self.subTest(value=value):
                self.assertFalse(is_name_like(value))

    def test_a_human_written_latin_name_is_not_rejected(self) -> None:
        """大文字を含むものは人が付けた名前でありうる。弾きすぎない。"""
        self.assertTrue(is_name_like("Todo"))


class TestDecideAppName(unittest.TestCase):
    def test_ai_name_wins_when_it_is_a_name(self) -> None:
        decided = decide_app_name(
            ai_title="家計簿", entity_label="取引記録", domain_label="家計簿",
        )
        self.assertEqual(decided, AppName(text="家計簿", source=NameSource.AI))

    def test_falls_through_to_entity_when_ai_returned_a_sentence(self) -> None:
        decided = decide_app_name(
            ai_title="毎日の収入と支出を記録して残高を見たい",
            entity_label="家計簿記録", domain_label="家計簿",
        )
        self.assertEqual(decided.text, "家計簿記録")
        self.assertIs(decided.source, NameSource.ENTITY)

    def test_falls_through_to_domain_when_entity_label_is_an_identifier(self) -> None:
        decided = decide_app_name(
            ai_title="買い物リストを作りたいです", entity_label="item", domain_label="買い物",
        )
        self.assertEqual(decided.text, "買い物")
        self.assertIs(decided.source, NameSource.DOMAIN)

    def test_admits_it_could_not_name_the_app(self) -> None:
        """**分からなかったときに要求文で取り繕わない。**"""
        decided = decide_app_name(
            ai_title="部署ごとの売上を月別に集計してグラフで比べたい",
            entity_label="item", domain_label=None,
        )
        self.assertEqual(decided.text, GENERIC_APP_NAME)
        self.assertIs(decided.source, NameSource.GENERIC)
        self.assertFalse(decided.named_by_understanding)

    def test_named_by_understanding_is_true_only_when_actually_named(self) -> None:
        for source in (NameSource.AI, NameSource.ENTITY, NameSource.DOMAIN):
            self.assertTrue(AppName(text="家計簿", source=source).named_by_understanding)
        self.assertFalse(
            AppName(text=GENERIC_APP_NAME, source=NameSource.GENERIC).named_by_understanding
        )

    def test_the_result_is_always_a_name(self) -> None:
        """どの入り方をしても、返るものは名前の形をしている。"""
        for sentence in SENTENCES_SEEN_IN_PRODUCTION:
            with self.subTest(sentence=sentence):
                decided = decide_app_name(ai_title=sentence, entity_label=sentence)
                self.assertTrue(is_name_like(decided.text), decided)


class TestDomainLabel(unittest.TestCase):
    def test_known_domains_have_japanese_names(self) -> None:
        self.assertEqual(domain_label_for("task_management"), "やること")
        self.assertEqual(domain_label_for("household_budget"), "家計簿")
        self.assertEqual(domain_label_for("shopping"), "買い物")

    def test_generic_is_not_a_name(self) -> None:
        """**generic は「分からなかった」である。** 名前で隠さない。"""
        self.assertIsNone(domain_label_for("generic"))

    def test_unknown_category_does_not_crash(self) -> None:
        self.assertIsNone(domain_label_for("no_such_domain"))
        self.assertIsNone(domain_label_for(None))
        self.assertIsNone(domain_label_for(""))


if __name__ == "__main__":
    unittest.main()
