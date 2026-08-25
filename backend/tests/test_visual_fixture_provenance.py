"""Visual Evidence の After が**本番の出力である**ことの回帰
（FORGE-019A §7）。

---

## 何を直したテストか

019のVisual Evidenceは、Before と After の**両方をDartに手で書いて**
いた。つまり

    Backendが実際に作るAfter   ←→   スクリーンショットの元になるAfter

が別々のSource of Truthだった。Revisionのロジックを直しても絵は変わら
ないので、「この画像がその変更の証拠です」と言えない。**絵と実装が
ずれても誰も気付かない。**

`scripts/export_revision_visual_fixture.py`が Before を本番の
`RevisionService`へ通してAfterを書き出すようにした。このテストは
**いま生成し直したものと、commitされているものが一致するか**を見る。
実装が変わって絵が古くなれば、CIが落ちる。

## 併せて見つかったこと

019のBefore fixtureは、**本番のValidatorに通らない文書だった**
（`negative_when`に`sign_field`が無い）。Dart側は`fromJson`が通ることしか
見ておらず、Validatorは呼んでいなかった。つまり不正な文書のスクリーン
ショットを証拠として出していた。生成スクリプトがBeforeもValidatorへ
通すようにした。
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from export_revision_visual_fixture import (  # noqa: E402
    BEFORE,
    DART_FIXTURE,
    INTENT,
    OUTPUT_DIR,
    produce,
    render_dart,
)

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


class TestTheVisualFixtureComesFromProduction(unittest.TestCase):
    def setUp(self) -> None:
        self.produced = produce()

    def test_the_before_document_passes_the_production_validator(self) -> None:
        """**019はここが通っていなかった。**"""
        result = validate_forge_document(BEFORE)
        self.assertTrue(result.valid, [e.to_dict() for e in result.errors])

    def test_the_after_document_passes_the_production_validator(self) -> None:
        result = validate_forge_document(self.produced["after"])
        self.assertTrue(result.valid, [e.to_dict() for e in result.errors])

    def test_the_committed_after_matches_what_production_produces(self) -> None:
        """**絵と実装がずれたらCIが落ちる。**"""
        committed = json.loads((OUTPUT_DIR / "after.json").read_text(encoding="utf-8"))
        self.assertEqual(
            committed, self.produced["after"],
            "commitされているAfterが、いまの本番RevisionServiceの出力と違う。"
            "`python scripts/export_revision_visual_fixture.py`で作り直すこと。",
        )

    def test_the_committed_before_matches_the_scenario(self) -> None:
        committed = json.loads((OUTPUT_DIR / "before.json").read_text(encoding="utf-8"))
        self.assertEqual(committed, BEFORE)

    def test_the_dart_fixture_matches_the_generated_content(self) -> None:
        """Dart側も生成物であること。**手で書き換えたら落ちる。**"""
        expected = render_dart(BEFORE, self.produced["after"], self.produced["provenance"])
        self.assertEqual(
            DART_FIXTURE.read_text(encoding="utf-8"), expected,
            "frontend/lib/forge_019a_visual_fixture.dart が生成物と一致しない。"
            "手で編集せず、生成スクリプトを走らせること。",
        )

    def test_the_provenance_names_the_actual_operation(self) -> None:
        provenance = self.produced["provenance"]
        self.assertEqual(provenance["revision_mode"], "local_semantic_patch")
        self.assertEqual(provenance["semantic_operation"], "select_primary_metric")
        self.assertEqual(provenance["intent"], INTENT)
        self.assertTrue(provenance["validator_passed"])
        self.assertTrue(provenance["critic_passed"])

    def test_the_revision_actually_changes_the_hierarchy(self) -> None:
        """**Before と After が同じなら、絵は何も証明していない。**"""
        before_children = BEFORE["screens"][0]["body"]["children"]
        after_children = self.produced["after"]["screens"][0]["body"]["children"]
        self.assertNotEqual(before_children, after_children)

        def role(children, widget_id):  # noqa: ANN001, ANN202
            return next(c["style_role"] for c in children if c["id"] == widget_id)

        self.assertEqual(role(before_children, "balance"), "metric.secondary")
        self.assertEqual(role(after_children, "balance"), "metric.primary")
        self.assertEqual(role(before_children, "income"), "metric.primary")
        self.assertEqual(role(after_children, "income"), "finance.income")

    def test_unrelated_widgets_are_untouched(self) -> None:
        """局所適用であること。触っていない場所は1バイトも変わらない。"""
        before_children = BEFORE["screens"][0]["body"]["children"]
        after_children = self.produced["after"]["screens"][0]["body"]["children"]
        changed = {"income", "balance"}
        for before_widget, after_widget in zip(before_children, after_children, strict=True):
            if before_widget["id"] not in changed:
                with self.subTest(widget=before_widget["id"]):
                    self.assertEqual(before_widget, after_widget)

    def test_the_fixture_carries_no_artifact_handle(self) -> None:
        """**失効するIDを証拠へ焼き込まない**（017A §3）。"""
        dumped = (OUTPUT_DIR / "provenance.json").read_text(encoding="utf-8")
        for forbidden in ("artifact_id", "version_token", "document_binding", "handle"):
            self.assertNotIn(forbidden, dumped)


if __name__ == "__main__":
    unittest.main()
