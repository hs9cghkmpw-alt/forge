"""Golden Test(FORGE-MILESTONE-003.1、CEOレビュー対応)。

CEOレビュー:「Action Contract Testは良いが、Golden Testも欲しい。
JSONを固定化する。shopping.json、hospital.json、memo.json...毎回比較。
Generator変更で壊れたら即検出。」への対応。

`tests/golden/*.json`に、Mock Generatorの現在の出力を凍結したものを
1カテゴリ1ファイルで保存している。本テストは、Mock Generatorを
再実行した結果を、この凍結済みJSONと**バイト単位で完全一致**するか
比較する。1文字でも変われば即座に検出する(意図した変更であれば、
`tests/golden/`のファイルを更新した上でこのテストを合格させる、という
運用を想定する)。

注記:「hospital」はForge Mock Generatorの実カテゴリ名ではない
(`forge_ai/`側のDomain名の一つであり、Mock Generatorとは別システム)。
Mock Generatorの実際の12カテゴリ全件をGolden化した
(shopping/todo/dinner/budget/schedule/child/pet/gift/household/travel/
survey/memoの12ファイル)。
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.generators.mock_generator import generate_forge_document  # noqa: E402

_GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")

# tests/golden/*.json を生成した際に使った、カテゴリ名→トリガーフレーズの対応。
# ここを変更する場合は、tests/golden/配下のJSONも合わせて再生成すること。
CATEGORY_PHRASES: dict[str, str] = {
    "shopping": "買い物メモを作って",
    "todo": "todoリストを作って",
    "dinner": "今日の晩ご飯を考えるメモを作って",
    "budget": "家計簿をつけるメモを作って",
    "schedule": "今日の予定リストを作って",
    "child": "子どもの持ち物チェックを作って",
    "pet": "ペットのお世話チェックリストを作って",
    "gift": "プレゼントのアイデアリストを作って",
    "household": "家事のチェックリストを作って",
    "travel": "旅行の持ち物チェックを作って",
    "survey": "満足度アンケートを作って",
    "memo": "メモを作って",
}


def _load_golden(name: str) -> dict:
    path = os.path.join(_GOLDEN_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _serialize(doc: dict) -> str:
    """golden fileの生成時(sort_keys=True, indent=2)と全く同じ形式で
    シリアライズする(比較の前提を一致させるため)。"""
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


class TestGoldenFiles(unittest.TestCase):
    def test_all_golden_files_exist(self) -> None:
        for name in CATEGORY_PHRASES:
            path = os.path.join(_GOLDEN_DIR, f"{name}.json")
            self.assertTrue(os.path.isfile(path), f"golden file が無い: {path}")

    def test_regenerated_output_matches_golden_exactly(self) -> None:
        """本体: Mock Generatorを再実行し、凍結済みJSONとバイト単位で
        一致するかを検証する。カテゴリごとにsubTestで独立に報告する。"""
        for name, phrase in CATEGORY_PHRASES.items():
            with self.subTest(category=name):
                actual = generate_forge_document(phrase)
                expected = _load_golden(name)
                self.assertEqual(
                    actual, expected,
                    msg=(
                        f"'{name}' カテゴリの生成結果がgolden fileと一致しません。"
                        f"意図した変更であれば tests/golden/{name}.json を更新してください。"
                    ),
                )

    def test_golden_files_are_deterministic_across_repeated_calls(self) -> None:
        """Mock Generatorは決定的であるべき(同じ入力から常に同じ出力)。
        golden比較の前提そのものを検証する。"""
        for name, phrase in CATEGORY_PHRASES.items():
            with self.subTest(category=name):
                first = generate_forge_document(phrase)
                second = generate_forge_document(phrase)
                self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
