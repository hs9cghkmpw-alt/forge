# FORGE-019A Visual Evidence Manifest

- Task: FORGE-019A Revision Integrity Hardening
- Branch: `claude/forge-master-handoff-k46jns`
- Scenario: Golden Finance — 「残高をもっと目立たせて」
- Viewport: 390 × 844

## この manifest が 019 と違うところ

**After を手で書くのをやめた**（019A §7）。

019 は Before / After の両方を `frontend/lib/forge_019_visual.dart` へ
手で書いていた。つまり

    Backend が実際に作る After   ←→   スクリーンショットの元になる After

が別々の Source of Truth だった。Revision のロジックを直しても絵は
変わらないので、**その絵は変更の証拠にならない**。

019A では `scripts/export_revision_visual_fixture.py` が Before を
本番の `RevisionService` へ通して After を書き出す。

    docs/visual-evidence/FORGE-019A/before.json      手書きの入力（唯一）
    docs/visual-evidence/FORGE-019A/after.json       本番の出力
    docs/visual-evidence/FORGE-019A/provenance.json  どの操作の絵か
    frontend/lib/forge_019a_visual_fixture.dart      生成物（Flutterが読む）

`backend/tests/test_visual_fixture_provenance.py` が「いま生成し直した
ものと commit されているものが一致するか」を見る。実装が変わって絵が
古くなれば **CI が落ちる**。

## Provenance（本番が返した事実）

| | |
|---|---|
| intent | 残高をもっと目立たせて |
| revision_mode | `local_semantic_patch` |
| semantic_operation | `select_primary_metric` |
| semantic_target | screen `home` / widget `balance` / identity `balance` |
| patch_mode | `local_semantic_patch` |
| validator_passed | true |
| critic_passed | true |
| forge_language_version | 1.12 |

局所差分は2箇所だけである。

    balance : metric.secondary → metric.primary
    income  : metric.primary   → finance.income

`expense` / 見出し / 取引一覧は**1バイトも変わらない**（テストで固定）。

## 019 の Before が Validator に通っていなかった

019A で見つけた。手書きの Before は `negative_when` を持ちながら
`sign_field` が無く、**本番の Validator に通らない文書**だった。
Dart 側は `ForgeDocument.fromJson` が通ることしか見ておらず、Validator は
呼んでいなかったので気付けなかった。

つまり **019 のスクリーンショットは、不正な文書を描いたもの**である。
生成スクリプトが Before も Validator へ通すようにした（通らなければ
生成が止まる）。

## 実描画の状態 — UNVERIFIED

**この作業環境には Flutter SDK が無い。** したがって 019A では

- `flutter test`
- `flutter analyze`
- `flutter build web`
- ブラウザでの実描画とスクリーンショット取得

を**実行できていない**。AGENTS.md の規定どおり、実描画を自分で見て
いない以上、視覚確認の結果は `UNVERIFIED` とする。

代わりに用意したもの:

- `revision-preview.html` — 本番の `after.json` と、実コードの
  role 実装値（`design_language.dart`）・テーマ定数
  （`forge_theme.dart`）から起こした作図。**Flutterのスクリーン
  ショットではない**ことをページ内で明示している
- 019 の `finance-before.png` / `finance-after-balance-emphasis.png`
  は Codex が実描画で撮ったものだが、上記のとおり**Validator に通らない
  Before** から撮られている。差し替えは実描画できる環境で行う

## 次に実描画する人がやること

1. `python scripts/export_revision_visual_fixture.py`
2. `scripts/start_dev.ps1` で backend + Flutter preview を起動
3. `scripts/capture_forge_019_visual.ps1` で 390×844 の before/after を取得
4. 画像を開いて overlap / overflow / clipping / alignment / spacing /
   hierarchy / mobile usability / primary metric visibility を確認
5. 問題があれば直して再取得し、この manifest の UNVERIFIED を更新する
