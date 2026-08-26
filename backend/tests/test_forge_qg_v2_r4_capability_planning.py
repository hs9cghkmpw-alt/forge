"""**Need から作られる構造が Need ごとに違うこと**
（GENERATED-UI-QG-V2-R4 / TD87・TD89、2026-08-26）。

---

## 何を再現しているのか

Quality Gate v2 の第1〜3回で、実描画・目視により2つの事実が出た。

1. **8アプリが3種類の画面にしかならない**（TD87）。写真 / データ分析 /
   学習 / ゲーム / 作業記録 / 子ども向けの6つが**構造的に同一**の
   checklist になる。第3回では analytics / game / study の PNG が
   **全 viewport でバイト単位一致**した。
2. **Domain 判定が外れる**（TD89）。「子どもが朝の支度をチェック」が
   `child_growth`（体重・身長）になり、「旅行の写真を残す」が
   `travel`（持ち物リスト）になる。

原因は同じ1つである。現在の本番経路が

```
Need → keyword → Domain → Template/Compiler → checklist
```

へ**圧縮**されており、**1つの単語がアプリ全体を決めている**。
「子ども」という語が出ただけで、記録するものまで体重・身長になる。

## このテストが要求する経路

```
Need
  → Semantic Role Extraction   （誰が / 何を / 何の文脈で / 何を見たいか）
  → Capability Decomposition
  → Capability Plan
  → IR Generation / Synthesis
  → Forge Language
  → Validator
  → Renderer
```

**専用 Template を作って通してはならない**（`kids_template` 等の禁止）。
Need ごとに Plan が違い、その結果として IR が違う、という順序でなければ
「8種類の Need に対応した」ことにならない。

## 先に書いて、落ちることを確かめた

修正前にこのファイルを走らせ、下の3クラスがすべて FAIL することを
確認している（`docs/reports/` の R4 report に記録）。
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

KIDS_NEED = "子どもが朝の支度をひとつずつチェックできるようにしたい"
PHOTO_NEED = "旅行の写真を日付ごとに残してメモを付けたい"
ANALYTICS_NEED = "部署ごとの売上を月別に集計してグラフで比べたい"
GAME_NEED = "植物を育てながら音を組み合わせるゲームを作りたい"
STUDY_NEED = "英単語を出題して、正解率の推移を見たい"


def _generate(client: TestClient, need: str) -> dict:
    response = client.post(
        "/api/v1/ai/generate",
        json={"input": {"natural_language": need,
                        "generation_options": {"provider": "mock"}}},
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _document(client: TestClient, need: str) -> dict:
    return _generate(client, need)["forge_document"]


def _labels(node: object) -> set[str]:
    """文書に現れる**利用者に見える文字列**を全部集める。"""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"label", "title", "value", "text", "placeholder"} and isinstance(value, str):
                found.add(value)
            found |= _labels(value)
    elif isinstance(node, list):
        for value in node:
            found |= _labels(value)
    return found


def _structure_signature(document: dict) -> tuple:
    """**構造の指紋。** 文字列を除いた「形」だけを取り出す。

    名前や例示が違うだけのものを「違う構造」と数えないため、
    widget の型・入れ子・画面数・record schema の形だけを見る。
    """
    def shape(node: object) -> object:
        if isinstance(node, dict):
            kind = node.get("type")
            children = node.get("children")
            if kind is not None:
                return (str(kind), tuple(shape(c) for c in children or ()))
            return tuple(sorted(
                (k, shape(v)) for k, v in node.items() if k not in {"id", "label", "title"}
            ))
        if isinstance(node, list):
            return tuple(shape(v) for v in node)
        return type(node).__name__

    schemas = document.get("record_schemas") or {}
    return (
        len(document.get("screens") or ()),
        tuple(shape(s.get("body")) for s in document.get("screens") or ()),
        tuple(sorted(
            (name, tuple(sorted(f.get("type", "") for f in (spec.get("fields") or []))))
            for name, spec in schemas.items()
        )),
    )


class TestChildIsAnActorNotADomain(unittest.TestCase):
    """再現1: 「子ども」という語だけで child_growth を選ばない（TD89）。"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_the_morning_routine_app_is_not_a_growth_record(self) -> None:
        """**「朝の支度」のアプリに体重・身長が出てはならない。**

        実測（第3回）: `child_growth` が選ばれ、「こどもの成長」という
        名前で「体重測定」「身長測定」が並んでいた。
        """
        labels = _labels(_document(self.client, KIDS_NEED))
        for wrong in ("体重", "身長"):
            self.assertFalse(
                any(wrong in label for label in labels),
                f"朝の支度のアプリに『{wrong}』が出ている: {sorted(labels)}",
            )

    def test_the_domain_is_not_pinned_to_child_growth(self) -> None:
        """**actor が Domain 選択を支配していないこと。**

        最初この検査を `entity_source` の trace で書いたが、この Need は
        `ir is None` の経路（legacy checklist）へ落ちるので
        `entity_source` の行がそもそも出ず、**何も検査せずに通っていた**。
        置物だったので、必ず出る `domain_classification` を見るように
        書き直した。
        """
        result = _generate(self.client, KIDS_NEED)
        trace = (result.get("diagnostics") or {}).get("decision_trace") or []
        classified = next(
            (e.get("decision", "") for e in trace
             if e.get("stage") == "domain_classification"), None,
        )
        self.assertIsNotNone(classified, "domain_classification が記録されていない")
        self.assertNotIn(
            "child_growth", str(classified),
            "actor（子ども）が Domain 選択を支配している",
        )

    def test_the_child_is_recognised_as_an_actor(self) -> None:
        """**「子ども」は actor である。** 記録対象ではない。

        実測: `meaning_extraction=actors=()` で、`child` は
        `entities`（記録するもの）に入っていた。だから体重・身長が出る。
        """
        result = _generate(self.client, KIDS_NEED)
        trace = (result.get("diagnostics") or {}).get("decision_trace") or []
        meaning = next(
            (str(e.get("decision", "")) for e in trace
             if e.get("stage") == "meaning_extraction"), "",
        )
        self.assertNotIn("actors=()", meaning, f"actor が1つも取れていない: {meaning}")


class TestTravelIsAContextNotTheSubject(unittest.TestCase):
    """再現2: 「旅行」は文脈であって、作るものではない（TD89）。"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_the_photo_diary_is_not_a_packing_list(self) -> None:
        """実測（第3回）: 「旅行」という名前で充電器・着替え・歯ブラシ。"""
        labels = _labels(_document(self.client, PHOTO_NEED))
        for wrong in ("充電器", "着替え", "歯ブラシ", "持ち物"):
            self.assertFalse(
                any(wrong in label for label in labels),
                f"写真の記録アプリに『{wrong}』が出ている: {sorted(labels)}",
            )

    def test_what_gets_recorded_is_photo_date_and_memo(self) -> None:
        """**recorded_data は写真・日付・メモである。**"""
        document = _document(self.client, PHOTO_NEED)
        labels = " ".join(sorted(_labels(document)))
        for expected in ("写真", "日付", "メモ"):
            self.assertIn(expected, labels, f"記録対象『{expected}』が無い: {labels}")


class TestDifferentNeedsProduceDifferentStructures(unittest.TestCase):
    """再現3: analytics / game / study が同一の checklist になる（TD87）。"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_analytics_game_and_study_are_not_the_same_app(self) -> None:
        signatures = {
            key: _structure_signature(_document(self.client, need))
            for key, need in (
                ("analytics", ANALYTICS_NEED),
                ("game", GAME_NEED),
                ("study", STUDY_NEED),
            )
        }
        self.assertEqual(
            len(set(signatures.values())), 3,
            "3つの全く違う Need が同じ構造になっている（TD87）",
        )

    def test_all_eight_needs_do_not_collapse_into_three_shapes(self) -> None:
        """**8つの Need が3種類の画面にならないこと。**

        第1〜3回の実測: tracker(21型) / tracker(20型) / checklist(7型)
        の3種類しか出てこなかった。
        """
        needs = (
            "毎日の収入と支出を記録して残高を見たい",
            "今日やる作業を登録して、終わったものを消していきたい",
            KIDS_NEED, PHOTO_NEED,
            "釣った場所を地図に残して魚の種類を記録したい",
            GAME_NEED, ANALYTICS_NEED, STUDY_NEED,
        )
        shapes = {_structure_signature(_document(self.client, n)) for n in needs}
        self.assertGreaterEqual(
            len(shapes), 5,
            f"8つの Need が {len(shapes)} 種類の構造にしかならない（TD87）",
        )


if __name__ == "__main__":
    unittest.main()
