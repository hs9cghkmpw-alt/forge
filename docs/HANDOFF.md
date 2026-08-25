# Forge Handoff

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `479c0faaf5e3deacd4f2b29ae029dc0f9578f57a`
- Implementation Agent: Claude Code（前任は Codex）
- Current phase: R1 Generated App Quality / Growing AI
- Current task: **FORGE-019A Revision Integrity Hardening — 実装完了、CI確認待ち**
- Real Local Model runs: **0**（019Aでは起動しない。正しい状態）

---

## 何をしたか

独立レビューが挙げた5つのBlocking項目は、**すべて実コードで再現できた**。
塞いだ上で、Visual Evidence の二重 Source of Truth と Flutter の冪等キー
の向きも直した。

| § | 穴 | 直した形 |
|---|---|---|
| 1 | handle と token が正しければ**別のDocument**でも通った | `document_binding`（プロセス内鍵のHMAC）。無ければ通さない |
| 2 | `/converse` の UPDATE だけ旧経路で、記録が1件も残らなかった | `RevisionService` を1つ作り両方の入口を通した |
| 3 | 本番の RevisionRecord へ**偽のVisual Evidence**が固定で入っていた | 本番は `None`。実際に撮ったときだけ明示的に付ける |
| 4 | 「直してと言われた」だけで教師データ候補になった | Feedback列をjoinして判定。記録は書き換えない |
| 5 | 全体再生成fallbackが lineage を1件も残さなかった | 同じ Service を通す。局所patchのふりはしない |
| 6 | mutation に source-string check が混ざっていた | behavior guard へ書き換え、3種類を別々に数える |
| 7 | Visual Evidence の After が手書きで、実装とずれても気付けなかった | 本番の `RevisionService` から生成する |
| 8 | Flutter の冪等キーが**再送のたびに変わって**いた | 同じ操作は同じキー。成功したら捨てる |

### レビュー指摘外で見つけたもの

- **何も変えない変更が記録されていた。** 生成直後の家計簿は残高が既に
  主KPIなので「残高を目立たせて」は変えるものが無い。それを成功として
  記録すると、直していないのに「直して受け入れられた」という嘘の教師
  信号を作れてしまう。`no_change` で断るようにした
- **019 の Before fixture は本番の Validator に通らない文書だった**
  （`negative_when` に `sign_field` が無い）。Dart 側は `fromJson` が
  通ることしか見ていなかった。**019のスクリーンショットは不正な文書を
  描いたもの**である

---

## Production wiring

```
Flutter Host / 会話
  → artifact capability（handle）
  → version token（世代）
  → document binding（中身の身元）      ← 019A §1
  → TargetResolver / 全体再生成fallback
  → Forge Validator
  → Semantic Design Critic
  → RevisionRecord（lineage）
  → CORRECTED FeedbackEvent
  → REVISION LearningEvent
  → 新しい artifact version
  → Flutter render
```

`/update` と `/converse` の UPDATE は**同じ `RevisionService`** を通る。
`ForgeOperationEngine` の呼び出しが router 内に1箇所だけであることを
テストで固定した。

---

## Tests / Evidence

| | 結果 |
|---|---|
| backend | **1,496 passed / 16 skipped** |
| forge_ai | **521 passed** |
| ruff（変更ファイル） | All checks passed |
| flutter test / analyze / build web | **UNVERIFIED**（この環境にSDKが無い） |
| CI 4 job | push 後に確認する |

| guard の種類 | 数 |
|---|---|
| behavior guards | **56** |
| static protocol checks | **6** |
| real source mutation rounds | **10** |

10 round すべてで、ソースを壊すと落ち、戻すと通ることを確認した
（一覧は report §10）。

---

## Visual

- `docs/visual-evidence/FORGE-019A/` — Before/After/provenance の JSON は
  **本番の `RevisionService` が出したもの**。commit されている After が
  いまの出力と一致するかを `test_visual_fixture_provenance.py` が見る
  ので、実装が変わって絵が古くなれば **CI が落ちる**
- `revision-preview.html` — 本番の `after.json` と実コードの role 実装値・
  テーマ定数から起こした作図

### Visual Review は UNVERIFIED

**この環境に Flutter SDK が無く、実描画を見ていない。** AGENTS.md の
「実描画を見ていなければ `UNVERIFIED`」「PNGを生成しただけを Visual
Review と呼ばない」に照らし、**作図を作っただけの今回も Visual Review
とは呼べない**。

実描画できる環境でやること: `python scripts/export_revision_visual_fixture.py`
→ `scripts/start_dev.ps1` → `scripts/capture_forge_019_visual.ps1` →
画像を開いて overlap / overflow / clipping / alignment / spacing /
hierarchy / mobile usability / primary metric visibility を確認。

---

## UNVERIFIED

- Flutter 一式（test / analyze / build web / 実描画・撮影）
- 実 Cloud Provider での往復（実APIを呼んでいない）
- ブラウザ自動操作で `/update → render → feedback` を1セッションで回すこと
- Runtime outcome は `UNKNOWN` のまま（描画できた事実を RevisionRecord へ
  結びつける認証付きコールバックが無い）

---

## Technical Debt

- `ArtifactRegistry` / Evidence / outbox は**プロセス内メモリ**。再起動で
  capability が失効し、Revision の連鎖が切れる
- `document_binding` の鍵はプロセス内。複数プロセス構成では共有されない
- Auth / subject binding / RLS / server-issued contributor identity /
  durable outbox / Supabase Learning tables 未実装
  （`unguessable != authorized` のまま）
- **`evaluate_for_export()` を本番から呼ぶ経路が無い。** DatasetCandidate
  は現状テストからしか生まれない
- mock の全体再生成出力がスイート順序に依存する（原因未特定）
- 019 の PNG が不正な Before から撮られている。差し替えが要る

---

## Next task

**FORGE-020 — Real Local Model Runtime + Benchmark + Local Promotion
Gate v1。** 019A が独立レビューで GO になってから着手する。

Local Promotion Gate 自体は 017A で配線済み（`AIRouter._order()` から
呼ばれる）だが、**昇格する Provider は現在0件**である——実測が1件も
無いため。020 でそこへ実データを入れる。

## Next three moves

1. push した HEAD / diff / tests / CI を独立レビューで確認する
2. Flutter のある環境で `flutter analyze` / `test` / `build web` と
   実描画・撮影を行い、`docs/visual-evidence/FORGE-019A/manifest.md` の
   UNVERIFIED を更新する
3. GO が出たら FORGE-020 へ進む
