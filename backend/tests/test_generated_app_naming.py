"""**本番の `/generate` が返すアプリ名**を固定する
（Generated UI Quality Gate v2 修正1、2026-08-26）。

---

## なぜ HTTP を叩くのか

`forge_ai/tests/test_naming.py` は `decide_app_name()` の契約を見る。
それだけでは**「作ったが本番から呼ばれない」**を防げない——このリポジトリで
**7回**繰り返した失敗である（TD59 / 007 §10 / 010 Phase B / TD64 / TD69 /
016A / 020A）。

だからここでは本番の HTTP 経路を通し、**返ってきた Document の
`app.title` そのもの**を見る。名付けの配線が外れれば、この2つが落ちる:

* `decide_app_name()` を呼ばなくなった → 要求文が戻ってくる → 落ちる
* 新しい compile 経路を足して名付けを通し忘れた → 落ちる

実際に、Quality Gate v2 の実描画で AppBar に出ていたのは
「毎日の収入と支出を記録して残高を見たい」だった。

## 撮影対象と同じ Need を使う

`scripts/export_quality_gate_fixtures.py` の 8 件と同じものを使う。
**絵とテストが別々の入力を見ていると、絵で見つけた問題をテストで
固定できない。**
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from forge_ai.core.naming import GENERIC_APP_NAME, is_name_like  # noqa: E402

#: Quality Gate v2 の撮影対象（`scripts/export_quality_gate_fixtures.py`）。
QUALITY_GATE_NEEDS: tuple[str, ...] = (
    "毎日の収入と支出を記録して残高を見たい",
    "今日やる作業を登録して、終わったものを消していきたい",
    "子どもが朝の支度をひとつずつチェックできるようにしたい",
    "旅行の写真を日付ごとに残してメモを付けたい",
    "釣った場所を地図に残して魚の種類を記録したい",
    "植物を育てながら音を組み合わせるゲームを作りたい",
    "部署ごとの売上を月別に集計してグラフで比べたい",
    "英単語を出題して、正解率の推移を見たい",
)


def _generate(client: TestClient, need: str) -> dict:
    response = client.post(
        "/api/v1/ai/generate",
        json={"input": {"natural_language": need,
                        "generation_options": {"provider": "mock"}}},
    )
    assert response.status_code == 200, response.text
    return (response.json().get("result") or {}).get("forge_document") or {}


class TestProductionNeverNamesAnAppAfterTheRequestSentence(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_no_generated_app_is_named_after_the_request(self) -> None:
        """**要求文がアプリ名になっていないこと。** これが本丸である。"""
        for need in QUALITY_GATE_NEEDS:
            with self.subTest(need=need):
                title = _generate(self.client, need).get("app", {}).get("title")
                self.assertIsNotNone(title)
                self.assertNotEqual(title, need)

    # **部分一致では判定しない。**
    #
    # 最初この行を `assertNotIn(title, need)` と書いたが、正しい名前が
    # 落ちた——「旅行の写真を…」に対する「旅行」は、要求文の部分文字列で
    # ありながら**良い名前**である。名前が要求と語を共有するのは当たり前で
    # あって、欠陥ではない。
    #
    # 見るべきは出所ではなく**形**である。それは下の
    # `test_every_generated_app_title_is_a_name` が見る。

    def test_every_generated_app_title_is_a_name(self) -> None:
        for need in QUALITY_GATE_NEEDS:
            with self.subTest(need=need):
                title = _generate(self.client, need)["app"]["title"]
                self.assertTrue(is_name_like(title), f"{need} -> {title}")

    def test_screen_titles_are_names_too(self) -> None:
        """AppBar に出るのは `screen.title` である。**そこも見る。**

        第1回の実描画で切れていたのは画面見出しの方だった。
        `app.title` だけ直して満足すると、絵は変わらない。
        """
        for need in QUALITY_GATE_NEEDS:
            with self.subTest(need=need):
                for screen in _generate(self.client, need).get("screens", []):
                    self.assertTrue(
                        is_name_like(screen.get("title")),
                        f"{need} -> {screen.get('title')}",
                    )


class TestNamesComeFromWhatForgeActuallyUnderstood(unittest.TestCase):
    """名前は**理解の結果**である。理解できたものだけ名前を持つ。"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_understood_domains_get_a_real_name(self) -> None:
        expected = {
            "毎日の収入と支出を記録して残高を見たい": "家計簿記録",
            "今日やる作業を登録して、終わったものを消していきたい": "やること",
            "釣った場所を地図に残して魚の種類を記録したい": "釣果記録",
            "買い物リストを作りたい": "買い物リスト",
        }
        for need, name in expected.items():
            with self.subTest(need=need):
                title = _generate(self.client, need)["app"]["title"]
                self.assertEqual(title, name)

    def test_unknown_domains_admit_it_instead_of_echoing_the_request(self) -> None:
        """**分からなかったものは分からないと言う。**

        データ分析・ゲーム・学習は、現在の Forge が Domain として
        理解できていない（`generic` へ落ちる）。そこで要求文を名前に
        すると「理解している」ように見えてしまう。

        これが `新しいアプリ` になるのは**この修正の失敗ではなく、
        TD87（8アプリが3種類の画面にしかならない）の症状**である。
        名前が本物になるのは、Capability Registry を作り直したときである。
        """
        for need in (
            "部署ごとの売上を月別に集計してグラフで比べたい",
            "植物を育てながら音を組み合わせるゲームを作りたい",
            "英単語を出題して、正解率の推移を見たい",
        ):
            with self.subTest(need=need):
                title = _generate(self.client, need)["app"]["title"]
                self.assertEqual(title, GENERIC_APP_NAME)


if __name__ == "__main__":
    unittest.main()
