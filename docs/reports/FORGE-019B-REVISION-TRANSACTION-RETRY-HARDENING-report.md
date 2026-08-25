# FORGE-019B — Revision Transaction / Retry / Provider Evidence Hardening

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `1fa1a2b81e3ded965f3cfd42593a966f3cc4a676`
- Implementation Agent: Claude Code
- **Real Local Model runs: 0**（019Bでは起動しない。正しい状態）
- FORGE-020 は未着手

---

## 0. 一行で

独立レビューの4点は**すべて現在のコードで再現できた**。先に再現テストを
書いて FAIL させてから直した。併せて、直した結果として**元の再現手順が
届かなくなり、atomicity のテストが置物になった**ことを mutation で検出し、
失敗注入テストへ作り直した。

---

## 1. reproduce → root cause → fix

### §1 Revision が atomic ではなかった

**再現**（`TestRevisionIsAtomic`、修正前に FAIL を確認）

```
1回目: /update 成功（idempotency key = K）
2回目: 新しい版・新しい文書・正しいtoken、ただし同じ K
      → Feedback が重複として弾かれる
      → API は 422
      → しかし RevisionRecord と REVISION LearningEvent は残る
```

**root cause**

`_record()` の順序が

```
RevisionRecord.record()   ← ここで observe_evidence() も走る
→ Feedback.record()        ← ここで失敗しうる
→ artifact advance
```

だった。`RevisionEvidenceStore.record()` が Learning Event を**即時**
出すので、後段が落ちると Learning 側まで孤児になる。

残った記録は対応する CORRECTED を持たない。019A §4 で入れた
「Feedback列を join して Dataset 適格性を決める」からは永久に
`NO_FEEDBACK` に見える——**評価されないまま Evidence を汚し続ける**。

**fix — prepare → validate → commit**

```
1. validate : feedback.admit()  … 書く前に「評価を書けるか」を確かめる
2. stage    : revisions.record(..., observe=False)
              ← Learning Event はまだ出さない
3. commit   : Feedback → artifact advance → revisions.publish()
              ← 途中で落ちたら discard() で巻き戻す
```

`publish()` を独立させたのは、**確定してから Learning Event を出す**
ためであり、同時に DB 化したときの差し替え点でもある。

`discard()` は **transaction の巻き戻し専用**である。確定した記録を
消す用途に使ってはならない（docstring に明記）。

---

### §2 Revision そのものが冪等でなかった

**再現**（`TestRevisionRetryReplays`、修正前に FAIL を確認）

```
1. V1 で Revision 成功（サーバは V2 へ進む）
2. 応答が Client へ届かない
3. Client は V1・古い文書・同じキーで再送
4. サーバは stale_version で拒否
```

利用者から見ると「直したのに直っていない」うえ、もう一度押しても永久に
通らない。**通信が切れただけで詰む。**

**fix — `RevisionReplayLog`**

要求の身元がすべて一致したときだけ replay する。

```python
_RequestIdentity(
    artifact_id,                    # 元の生成物
    version_token,                  # 元の版
    document_binding,               # 送られた文書
    change_request_fingerprint,     # 要求文（ハッシュのみ。発話は持たない）
    idempotency_key,
)
```

**キーだけを鍵にしない。** キーだけで replay を返すと、Client が同じ
キーを別の要求へ使い回した瞬間に**別の要求へ以前の結果が返る**
——019A §1 の `document_binding` で塞いだ穴を、冪等性の側から開け直す
ことになる。

同じキーで身元が違えば `idempotency_conflict` で**断る**（fail closed）。
replay も処理もしない——どちらへ倒しても嘘になる。

キーが無ければ replay しない（017A §2 と同じ姿勢）。

> プロセス内メモリのみ。再起動で消えると `stale_version` に戻る
> ——**安全側に壊れる**（二重適用はしない）。

---

### §3 Feedback の idempotency scope が global だった

**再現**（`TestFeedbackIdempotencyIsScoped`、修正前に FAIL を確認）

`FeedbackEventLog._by_idempotency` が raw key だけの dict だったので、
Client が単純な連番キーを使うと**無関係な生成物への評価が「重複」として
捨てられた**。評価が黙って消えるのは、記録の穴として最も悪い部類である
（利用者は言ったつもりで、Forge は聞いていない）。

**fix** — `(evidence uid, idempotency_key)` で判定する。
将来 subject / app の境界を足すときは、この tuple を伸ばす。

`find_by_idempotency_key()` は `evidence_id` 省略時に**何とも一致しない**
——範囲が分からないものを「重複」へ倒さない。

---

### §4 Provider の帰属が実態と違った

**再現**（`TestProviderAttribution`、修正前に FAIL を確認）

局所 patch は Forge の決定的な操作であって **LLM を1回も呼ばない**のに、
レスポンスは会話の Provider（`mock` / `gemini`）を返していた。
全体再生成へ落ちた場合も、Router が fallback した先ではなく会話の
Provider が返り得た。

呼んでもいない Provider の手柄がその成績へ混ざる——**Local Promotion
Gate（017A §7）が読む数字が汚れる**。

**fix**

| 経路 | `revision_provider` |
|---|---|
| 局所 semantic patch | `forge_deterministic`（AIを呼んでいない） |
| 全体再生成 fallback | `bound.last_provider_used`（実際に生成したProvider） |
| 記録し損ね | `unknown`（`forge_deterministic` とは**別物**） |

`RevisionRecord.provider_id` へも入れ、Learning Event へ射影する。
API は `provider`（会話）と `revision_provider`（実際に直した側）を
**分けて**返す。

---

## 2. 直したことで、テストが置物になった（mutation が検出した）

§2 の replay を入れた結果、`TestRevisionIsAtomic` の再現手順
（同じキーで2回目）は **`idempotency_conflict` で先に止まる**ように
なった。transaction の中まで届かない。

mutation B1（transaction boundary を壊す）で **FAILED=0** となり、
これが判明した。**CI が緑でも、そのテストは何も守っていなかった。**

`TestCommitFailureRollsBack` を追加し、commit 相当の段で確実に失敗させて
「partial Evidence が残らない」ことを直接見るようにした。作り直した後の
B1 は 3件 FAIL する。

> これは `CLAUDE.md` §3 の「ガードが実際に効くことを確かめる」が、
> **後から効かなくなる**場合があるという例である。再現手順は、直した
> 内容によって届かなくなることがある。

---

## 3. Atomic transaction design

```
prepare   capability / token / document binding / semantic 解決
validate  feedback.admit()          ← 書く前に断れるものは断る
stage     revisions.record(observe=False)
commit    Feedback → advance → revisions.publish()
rollback  例外時に revisions.discard(staged.ref)
```

### いま保証していること

- commit の途中で落ちたら、**RevisionRecord も REVISION Learning Event
  も残らない**（外から見て何も起きていない）
- artifact の版も進まない

### 保証していないこと（正直に）

`Feedback.record()` が成功した**後**に `advance_to_revision()` が落ちた
場合、CORRECTED の Feedback Event は残る。Feedback Event は追記専用
（017A §2）なので巻き戻せない。

単一プロセスでは `advance_to_revision()` は直前に解決したハンドルを
使うので実質失敗しない。ただし**「絶対に無い」とは書かない**。
DB 化のときにここを transaction へ入れる。

### DB 化するときの移行境界

- `admit()` と `record()` の間に割り込みが無い前提は、**単一プロセス
  だから成り立っている**。DB では両者を1つの transaction に入れる
- `publish()`（Learning Event 送出）は **durable outbox** へ入れ、
  commit 後に別プロセスが流す。transaction 内でネットワーク I/O をしない
- `RevisionReplayLog` は DB の unique key（`_RequestIdentity` 相当）で
  置き換える

---

## 4. Retry / replay contract

| 状況 | 結果 |
|---|---|
| 同じ身元・同じキーの再送 | 以前の結果を replay（`replayed=true`）。Evidence は増えない |
| 同じキー・違う要求 | `idempotency_conflict` で拒否（fail closed） |
| キー無しの再送 | replay しない。版が進んでいれば `stale_version` |
| 別の生成物で同じキー | `idempotency_conflict`（他人の結果を返さない） |
| プロセス再起動後の再送 | replay 記録が消えているので `stale_version`（安全側） |

---

## 5. Production wiring

```
Flutter Host / 会話
  → artifact capability（handle）
  → version token
  → document binding                     019A §1
  → replay 判定 / idempotency conflict     019B §2
  → TargetResolver / 全体再生成fallback
  → Validator + Semantic Design Critic
  → [ validate → stage → commit → publish ]  019B §1
  → RevisionRecord（provider_id 付き）        019B §4
  → CORRECTED FeedbackEvent（scope付き key）  019B §3
  → REVISION LearningEvent
  → 新しい artifact version
```

`/update` と `/converse` の UPDATE は**同じ `RevisionService`** を通る
（019A §2）。

---

## 6. Tests

| | 結果 |
|---|---|
| backend | **1,520 passed / 16 skipped** |
| forge_ai | **521 passed** |
| ruff（変更ファイル） | All checks passed |
| flutter analyze / test / build web | push 後の CI で確認 |

新規: `backend/tests/test_forge_019b_revision_transaction.py`（24件）

> **§6 の指示どおり、数字は今回の実測を使っている。** 019A の報告は
> `1496 passed / 16 skipped` だったが、CI の実ログは
> `1495 passed / 17 skipped` だった（`FORGE_DEFAULT_PROVIDER=mock` の
> 有無で skip 条件が1件変わる）。**古い数字をコピーしていない。**
> CI 実測は push 後に追記する。

### guard の分類（3種類を混ぜずに数える）

| 種類 | 数 |
|---|---|
| **behavior guards** | **80** |
| **static protocol checks** | **6** |
| **real source mutation rounds** | **9** |

---

## 7. Mutation（実際にソースを壊して確認）

| # | 壊したもの | FAILED |
|---|---|---|
| B1 | transaction boundary（stage + rollback）を壊す | 3 |
| B1b | rollback だけ外す（stage は維持） | 3 |
| B2 | `admit()` の事前検査を外す | 1 |
| B3 | retry replay を返さない | 3 |
| B4 | idempotency scope を global へ戻す | 1 |
| B5 | provider attribution を会話Provider固定へ戻す | 3 |
| B6 | 同じキーの scope 検査を外す（キーだけで replay） | 4 |
| B7 | document binding を迂回する（019A の守り） | 4 |
| B8 | 確定前に Learning Event を出す（`observe=True`） | 2 |

**全 round で、壊すと落ち、戻すと通ることを確認した。**

B1・B2 は**最初の実行で FAILED=0 だった**（§2 参照）。テストを作り直して
から再実行している。

---

## 8. Visual Evidence

**この作業環境には Flutter SDK が無い。** 019B はバックエンドの
transaction / 冪等性 / Provider 帰属の変更であり、生成物の見た目
（role・レイアウト）は変えていない。

- `docs/visual-evidence/FORGE-019A/` の Before/After は**そのまま有効**
  （After は本番の `RevisionService` が返した文書であり、019B でも
  同じ結果になることを `test_visual_fixture_provenance.py` が確認する）
- **実描画を人が見ることは、019A から引き続き `UNVERIFIED`**

`flutter analyze` / `test` / `build web` は CI が実行する。

---

## 9. UNVERIFIED

- **実描画を人が見ること**（この環境に Flutter SDK が無い）
- 実 Cloud Provider での往復（実APIを呼んでいない）
- 複数プロセス / 再起動を跨いだ replay（プロセス内メモリのため、
  仕様として `stale_version` へ戻る）
- `advance_to_revision()` が落ちた場合の完全な atomicity（§3）

**019B を完全 GO とは主張しない**（実描画未確認のため、§7 の規定どおり）。

---

## 10. Remaining debt

- `ArtifactRegistry` / Evidence / outbox / `RevisionReplayLog` は
  **プロセス内メモリ**。再起動で capability も replay 記録も消える
- `document_binding` の鍵はプロセス内。複数プロセス構成では共有されない
- Auth / subject binding / RLS / server-issued contributor identity /
  durable outbox / Supabase Learning tables は未実装
- **`evaluate_for_export()` を本番から呼ぶ経路が無い。** DatasetCandidate
  は現状テストからしか生まれない
- mock の全体再生成出力がスイート順序に依存する（原因未特定）。
  019B の fallback テストは Provider の応答を固定して依存を外した
- 019 の Visual Evidence PNG は不正な Before から撮られている（019A §7.2）

---

## 11. Next task

**FORGE-020 — Real Local Model Runtime + Benchmark + Local Promotion
Gate v1。** 019B が独立レビューで GO になってから着手する。

019B で `revision_provider` を正しくしたことは 020 の前提でもある
——Local Promotion Gate は Provider 別の実測を読むので、**呼んでもいない
Provider の手柄が混ざっていると昇格判断が壊れる**。
