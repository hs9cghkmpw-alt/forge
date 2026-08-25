# Forge Handoff

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `1fa1a2b81e3ded965f3cfd42593a966f3cc4a676`
- Implementation Agent: Claude Code
- Current phase: R1 Generated App Quality / Growing AI
- Current task: **FORGE-019B Revision Transaction / Retry / Provider Evidence Hardening**
- 直前: FORGE-019A（`1fa1a2b` まで、CI 4 job green）
- Real Local Model runs: **0**（019Aでは起動しない。正しい状態）

---

## 何をしたか（019B）

独立レビューの4点は**すべて現在のコードで再現できた**。先に再現テストを
書いて FAIL させてから直した。

| § | 穴 | 直した形 |
|---|---|---|
| 1 | Feedback が失敗しても RevisionRecord と Learning Event が残った（孤児） | prepare → validate → stage → commit → publish。落ちたら巻き戻す |
| 2 | 応答が届かなかった再送が `stale_version` で**永久に通らなかった** | 要求の身元が全一致したときだけ replay。キーだけでは返さない |
| 3 | 別の生成物で同じ冪等キーを使うと**評価が黙って消えた** | `(evidence uid, key)` で判定 |
| 4 | LLMを呼んでいない局所patchが会話のProvider名を名乗った | `forge_deterministic` / 実際に生成したProviderを分けて返す |

### 直したことで、テストが置物になった

§2 の replay を入れた結果、§1 の再現手順（同じキーで2回目）は
`idempotency_conflict` で先に止まるようになり、**transaction の中まで
届かなくなった**。mutation B1 で FAILED=0 となって判明した。

失敗注入テスト（`TestCommitFailureRollsBack`）へ作り直した。

> `CLAUDE.md` §3 の「ガードが実際に効くか確かめる」は、**後から
> 効かなくなる**ことがある、という実例である。

### 019A で入れたもの（前タスク、参考）

document binding / 単一 RevisionService / 偽 Visual Evidence の除去 /
Revision acceptance の join / fallback の lineage。

## Production wiring

```
Flutter Host / 会話
  → artifact capability（handle）
  → version token
  → document binding                        019A §1
  → replay 判定 / idempotency conflict        019B §2
  → TargetResolver / 全体再生成fallback
  → Validator + Semantic Design Critic
  → [ validate → stage → commit → publish ]   019B §1
  → RevisionRecord（provider_id 付き）         019B §4
  → CORRECTED FeedbackEvent（scope付き key）   019B §3
  → REVISION LearningEvent
  → 新しい artifact version
  → Flutter render
```

`/update` と `/converse` の UPDATE は**同じ `RevisionService`** を通る。

### transaction が保証すること／しないこと

commit の途中で落ちたら、RevisionRecord も REVISION Learning Event も
残らず、版も進まない。

**ただし** `Feedback.record()` の成功後に `advance_to_revision()` が
落ちた場合、CORRECTED の Feedback Event は残る（追記専用のため巻き戻せ
ない）。単一プロセスでは直前に解決したハンドルを使うので実質失敗しない
が、**「絶対に無い」とは書かない**。DB 化のときにここを transaction へ
入れる（移行境界は 019B report §3）。

## Tests / Evidence

| | 結果 |
|---|---|
| backend | **1,520 passed / 16 skipped**（今回の実測） |
| forge_ai | **521 passed** |
| ruff（変更ファイル） | All checks passed |
| CI 4 job（run `32877978227` / `c8e5a06`） | **すべて success** |
| flutter analyze / test / build web | **success（CI）** |

> **数字は今回の実測を使っている。** 019A の報告は `1496/16` だったが、
> CI の実ログは `1495/17` だった（`FORGE_DEFAULT_PROVIDER=mock` の有無で
> skip 条件が1件変わる）。古い数字をコピーしない。

| guard の種類 | 数 |
|---|---|
| behavior guards | **80** |
| static protocol checks | **6** |
| real source mutation rounds | **9**（019B分） |

9 round すべてで、ソースを壊すと落ち、戻すと通ることを確認した
（一覧は 019B report §7）。うち B1・B2 は**最初 FAILED=0 だった**ので
テストを作り直してから再実行している。

---

## Visual

- `docs/visual-evidence/FORGE-019A/` — Before/After/provenance の JSON は
  **本番の `RevisionService` が出したもの**。commit されている After が
  いまの出力と一致するかを `test_visual_fixture_provenance.py` が見る
  ので、実装が変わって絵が古くなれば **CI が落ちる**
- `revision-preview.html` — 本番の `after.json` と実コードの role 実装値・
  テーマ定数から起こした作図

### Visual Review は UNVERIFIED

CI で `flutter analyze` / `test` / `build web` は通っている
（run `32815471451`）。しかし **CI はビルドとテストが通ることしか
言っていない**——画面を開いて overlap / overflow / clipping /
alignment を目で確かめてはいない。

この環境に Flutter SDK が無いため、**実描画を人が見ていない**。
AGENTS.md の「実描画を見ていなければ `UNVERIFIED`」「PNGを生成した
だけを Visual Review と呼ばない」に照らし、**作図を作っただけの今回も
Visual Review とは呼べない**。

実描画できる環境でやること: `python scripts/export_revision_visual_fixture.py`
→ `scripts/start_dev.ps1` → `scripts/capture_forge_019_visual.ps1` →
画像を開いて overlap / overflow / clipping / alignment / spacing /
hierarchy / mobile usability / primary metric visibility を確認。

---

## UNVERIFIED

- **実描画を人が見ること**（この環境に Flutter SDK が無い）。
  019B はバックエンドの変更で見た目は変えていないが、規定どおり
  実描画を見ていない以上 `UNVERIFIED` とする。
  **したがって 019B を完全 GO とは主張しない**
- 実 Cloud Provider での往復（実APIを呼んでいない）
- 複数プロセス / 再起動を跨いだ replay（プロセス内メモリのため、
  仕様として `stale_version` へ戻る＝安全側）
- `advance_to_revision()` が落ちた場合の完全な atomicity

## Technical Debt

- `ArtifactRegistry` / Evidence / outbox / **`RevisionReplayLog`** は
  プロセス内メモリ。再起動で capability も replay 記録も消える
- `document_binding` の鍵はプロセス内。複数プロセス構成では共有されない
- Auth / subject binding / RLS / server-issued contributor identity /
  durable outbox / Supabase Learning tables 未実装
- **`evaluate_for_export()` を本番から呼ぶ経路が無い。** DatasetCandidate
  は現状テストからしか生まれない
- mock の全体再生成出力がスイート順序に依存する（原因未特定）
- 019 の Visual Evidence PNG が不正な Before から撮られている

## Next task

**FORGE-020 — Real Local Model Runtime + Benchmark + Local Promotion
Gate v1。** 019B が独立レビューで GO になってから着手する。

019B で `revision_provider` を正しくしたことは 020 の前提でもある
——Local Promotion Gate は Provider 別の実測を読むので、**呼んでもいない
Provider の手柄が混ざっていると昇格判断が壊れる**。

Local Promotion Gate 自体は 017A で配線済み（`AIRouter._order()` から
呼ばれる）だが、**昇格する Provider は現在0件**である——実測が1件も
無いため。020 でそこへ実データを入れる。

## Next three moves

1. push した HEAD / diff / tests / CI を独立レビューで確認する
2. Flutter のある環境で `flutter analyze` / `test` / `build web` と
   実描画・撮影を行い、`docs/visual-evidence/FORGE-019A/manifest.md` の
   UNVERIFIED を更新する
3. GO が出たら FORGE-020 へ進む
