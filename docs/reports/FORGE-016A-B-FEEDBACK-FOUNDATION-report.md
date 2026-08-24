# FORGE-016A commit B — Feedback / Revision Foundation

2026-08-24 / branch `claude/forge-master-handoff-k46jns`

指示書: FORGE-016A-HARDENING-AND-FEEDBACK-FOUNDATION §3・§4・§5・§15

---

## 0. 一行で

**「これでいい」をForgeが受け取る口が、本番に1本も無かった。** それを
作った。作っただけでなく、**本番の`/generate`が必ず通る場所**へ置き、
配線を外すとテストが落ちることを確認した。

---

## 1. 何が壊れていたのか（実測）

`AcceptanceSignal`（`accepted` / `corrected` / `abandoned` / `unknown`）も
`GenerationEvidenceStore.note_user_acceptance()`も、011から実装されて
いた。013では`generation_ref`を`PipelineRunResult`へ載せるところまで
直してある。

**しかしHTTP層でそれが止まっていた。**

```
PromptPipeline.run() → PipelineRunResult(generation_ref=7)
                                          ↓
                       _result_dto() が読まずに捨てる
                                          ↓
                       HTTPレスポンスに何も出ない
                                          ↓
     Clientは「どの生成物か」を指せない → note_user_acceptance() が呼べない
```

実際に確認したこと（`git grep generation_ref`）:

* `app/routers/*` に `generation_ref` の出現が **0件**
* `note_user_acceptance` の本番呼び出しが **0件**

結果として`user_acceptance`は本番で永久に`UNKNOWN`であり、明示的な
承認を要求する`GenerationRecord.is_positive_example`は

```python
return (
    self.validator_passed
    and self.user_acceptance.is_positive   # ← 構造上、必ず False
    and self.runtime_outcome is not RuntimeOutcome.FAILED
)
```

**構造上、必ずFalse**だった。「Local AIの教師データを貯める」と書いて
ある仕組みが、貯める口を持っていなかった。

これはForgeが繰り返している「作ったが本番から呼ばれない」の**5例目**
である（TD59 / 007 §10 / 010 Phase B / TD64 / TD69）。

---

## 2. 何を作ったか

### 2.1 `app/ai/gateway/artifact_feedback.py`（新規）

| 型 | 役割 |
|---|---|
| `document_fingerprint(document)` | Documentの世代を表すsha256先頭32桁。正準化してから取る |
| `ArtifactIdentity` | `artifact_id` / `generation_ref` / `revision_ref` / `session_id` / `fingerprint` |
| `ArtifactRegistry` | `artifact_id` → 身元。プロセス内メモリのみ（TD41） |
| `ArtifactFeedbackService` | 「これでいい / 違う」を記録する**唯一のService** |
| `FeedbackRejected` | `unknown_artifact` / `stale_artifact` / `already_recorded` |

### 2.2 `app/ai/gateway/revision_evidence.py`（新規）

`RevisionRecord` / `DesignRevision` / `RevisionEvidenceStore` /
`RevisionOperationKind`。TD68の設計案をProduction型として実装した。

`GenerationRecord`へ`operation`を足す案を採らなかった理由は
モジュールのdocstringに書いた——**1つの型に混ぜると
`validator_passed`の意味がoperationごとに変わる**ため。

### 2.3 `POST /api/v1/ai/feedback`（新規エンドポイント）

```
{"signal": "accepted", "artifact_id": "<不透明なID>", "seen_fingerprint": "<省略可>"}
  → {"recorded": true, "signal": "accepted", "rejected": null}
```

### 2.4 `result.artifact`（レスポンス追加）

`/generate`・`/generate/confirm`・`/converse`(BUILD) の成功レスポンスへ

```json
"artifact": {"artifact_id": "...", "fingerprint": "..."}
```

が付く。

---

## 3. 設計判断（なぜそうしたか）

### 3.1 なぜ`_result_dto()`の中で登録するのか

成功レスポンスを組み立てる経路は3つ（`/generate`・`/generate/confirm`・
`/converse` BUILD）あるが、**どれも最後は`_result_dto()`を通る**。

呼び出し側3箇所に`register()`を書く案は採らなかった。それが
「呼び出し側が忘れずに呼ぶ」設計であり、**Forgeが4回失敗した形**その
ものだからである（`CLAUDE.md` §3）。`_result_dto()`へ置けば、4つ目の
経路を足した人が呼び忘れても登録される。

### 3.2 なぜClientへ内部refを出さないのか

```
❌ {"generation_refs": [7, 8, 9], "signal": "accepted"}
✅ {"artifact_id": "<Forgeが発行した不透明なID>", "signal": "accepted"}
```

任意のrefを信用すると、**利用者が見てもいない生成物へ「受け入れた」を
書ける**。それは学習素材の捏造である。`secrets.token_urlsafe(16)`で
推測できないIDを発行し、Forge自身が解決する。

### 3.3 なぜSessionだけで解決しないのか

`/converse`はBUILD/UPDATEの後に`ConversationStore.discard()`でセッション
を捨てる（本番コードで確認済み）。捨てた後にも「これでいい」は来るので、
セッションだけを頼りにできない。生成物そのものにIDを振り、`session_id`は
付随情報として持つ形にした。

### 3.4 「既に評価済みか」をServiceが覚えない

最初、Service側に「記録済み`artifact_id`の集合」を持つ実装にした。
**やめた。** 同じ事実の写しが2箇所にできると必ずずれる——Storeだけを
resetしたテストでは「Serviceは記録済みと言うがEvidenceは空」になる。

`GenerationEvidenceStore.get(ref)`を足し、**Storeを唯一の真実**にした。

### 3.5 Revision側の`note_user_acceptance()`を生成側と同じ規則にした

最初の実装は無条件上書きだった。`GenerationEvidenceStore`側は
「先に書かれた信号が勝つ / `UNKNOWN`は上書きの理由にならない」である。

**同じ`AcceptanceSignal`という語彙を使いながら規則が違えば、突き合わせた
ときに静かに嘘になる**（011 §5で一度踏んだ形）。揃えた。

---

## 4. 配線破壊試験（`CLAUDE.md` §3）

テストが置物でないことを、**実際に配線を外して**確認した。

| # | 外したもの | 落ちたテスト | 結果 |
|---|---|---|---|
| 1 | `_result_dto()`の`artifact=_artifact_ref(...)` | `test_generate_returns_an_artifact_id` / `test_generate_does_not_expose_internal_refs` | ✅ FAIL |
| 2 | `existing.user_acceptance is not UNKNOWN`検査 | `test_first_signal_wins` | ✅ FAIL |
| 3 | `seen_fingerprint != identity.fingerprint`照合 | `test_stale_artifact_is_rejected` / `test_feedback_with_a_stale_fingerprint_is_rejected` | ✅ FAIL |
| 4 | Revision storeのfirst-wins規則 | `test_revision_acceptance_follows_the_same_first_wins_rule` | ✅ FAIL |
| B | `FeedbackRequest`へ`generation_refs`を足して直接書かせる | `test_feedback_does_not_accept_raw_refs_from_the_client` | ✅ FAIL |
| E | `RevisionRecord`へ`utterance`を足して発話を入れる | `test_a_revision_record_cannot_hold_a_raw_utterance` / `test_serialized_revision_contains_only_identifiers` | ✅ FAIL |

6round全て、外すと落ち、戻すと通った。

---

## 5. Privacy境界（016A §10 / 006 §22）

`RevisionRecord`・`DesignRevision`は**生の発話を型として持てない**。
「入れない運用」ではなく、フィールドが存在しない。テスト
`test_a_revision_record_cannot_hold_a_raw_utterance`が、
`utterance` / `message` / `text` / `prompt` / `raw` / `user_input`という
名前のフィールドが増えていないことを見張る。

`document_fingerprint()`はsha256なので、**指紋から本文は復元できない**。
`test_fingerprint_does_not_contain_the_document_text`が16進数字だけで
あることを確認している。

将来、自然言語Correction Mapping（「もっと浮かせて」→`surface.elevated`）を
Local AIへ学習させる必要が出たら、それは`LanguageTrainingCandidate`と
いう**別契約**（明示同意・非識別化・provenance・`training_use=allowed`・
利用規約確認が前提）で扱う。ここへ混ぜない。**現時点では自動収集も
自動Trainingも行わない。**

---

## 6. 検証区分

| 項目 | 区分 |
|---|---|
| Feedback往復（`/generate` → `/feedback` → Evidence） | **実測**（`TestClient`、`mock` Provider） |
| 配線破壊試験6round | **実測**（実際に外して落ちることを確認） |
| Revision Store（sequence / 鎖 / first-wins / 正例判定） | **実測**（単体） |
| Privacy（型として発話を持てない） | **実測**（`__dataclass_fields__`検査） |
| 実Cloud Providerでの往復 | **未検証**（実APIは呼んでいない。§5 quota方針） |
| Flutter側の👍ボタン | **未実装**（このcommitはBackendのみ） |

---

## 7. テスト

`backend/tests/test_artifact_feedback.py` — 37件、全て通る。

```
backend  : 1304 passed, 16 skipped
forge_ai :  521 passed
ruff（変更ファイル）: All checks passed
```

---

## 8. まだ無いもの（正直に）

* **Flutter側**が`artifact_id`を保持して`/feedback`を叩く実装。
  Backendの口はできたが、**利用者が押せるボタンはまだ無い。**
  現時点で`user_acceptance`が実データで埋まるわけではない。
* `RevisionRecord`を**書く本番経路**。型とStoreはできたが、
  `/update`から`RevisionRecord`を残す配線はcommit F（Semantic Design
  Revision）で入れる。今は`ArtifactIdentity.revision_ref`が常に`None`。
* `ArtifactRegistry`はプロセス内メモリのみ。再起動で消える（TD41と同じ
  制約）。永続化はGrowing AI Architecture（017）のLearning Event
  Contractと合わせて決める。
