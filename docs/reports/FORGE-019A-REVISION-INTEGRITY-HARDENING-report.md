# FORGE-019A — Revision Integrity Hardening

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `479c0faaf5e3deacd4f2b29ae029dc0f9578f57a`
- Implementation Agent: Claude Code（前任は Codex）
- Real Local Model runs: **0**（019Aでは起動しない。正しい状態）

---

## 0. 一行で

019は「変更を意味的に扱う」ところまで作ったが、**その記録が本物である
保証**が足りていなかった。独立レビューが挙げた5つのBlocking項目は
**すべて実コードで再現できた**。塞いだ上で、Visual Evidenceの二重
Source of Truthと、Flutterの冪等キーの向きも直した。

**実描画は行えていない（Flutter SDK不在）。視覚確認は `UNVERIFIED`。**

---

## 1. commit

| commit | 内容 |
|---|---|
| `519b2e9` | §1〜§5 + §6（backend） |
| `d31f48c` | §7 Visual Evidence + §8 Flutter |
| （この commit） | 文書 |

変更ファイル: `backend/app/ai/runtime/revision_service.py`（新規）/
`backend/app/ai/gateway/{artifact_feedback,learning_events,revision_evidence}.py` /
`backend/app/routers/ai.py` / `backend/app/schemas/ai.py` /
`scripts/export_revision_visual_fixture.py`（新規）/
`frontend/lib/forge_019a_visual_fixture.dart`（生成物）/
`frontend/lib/{forge_019_visual.dart,shared_widgets/generated_app_host_shell.dart}` /
`docs/visual-evidence/FORGE-019A/*` / テスト各種。

---

## 2. §1 Artifact version と Document identity が結びついていなかった

### 再現

`/update` は `artifact_id`（capability）と `seen_version_token`（世代）
を照合していたが、**`request.forge_document` は照合していなかった**。

```
正しい artifact_id + 正しい version_token + 自分で書いた別のJSON
  → 200 で通り、RevisionRecord が残る
```

### root cause

017A で「Client handle」と「世代」を分けたが、**世代tokenは
「さっきと同じ版か」しか言わない**。中身が同じものかは誰も見ていな
かった。Revision は「その生成物をこう直した」という記録なので、
直した対象が別物なら記録は嘘になる——handle を持っている人が、任意の
JSONを「Forgeが生成したものを直した」ことにできた（Revision lineage
汚染）。

### fix

`ArtifactHandle.document_binding`（プロセス内鍵の HMAC-SHA256）。

`document_fingerprint()`（salt無しsha256）を使わなかったのは、
内容が同じなら誰が作っても同じ値になり、低entropyな内容は総当たりで
言い当てられるからである（017A §4で外へ出すのをやめた理由と同じ）。
鍵はプロセス起動ごとに変わり、保存も送信もしない。

**束縛が無ければ通さない（fail closed）。** 生成時と Revision 後の
両方でその時点の文書へ束縛し直すので、連鎖は切れない。

### Artifact ↔ Document binding proof

`backend/tests/test_forge_019a_revision_integrity.py::TestDocumentBinding`（7件）

- 一致する文書は通る
- **別の文書は `document_binding` で拒否**
- 1文字書き換えただけでも拒否
- 拒否したときは RevisionRecord を1件も残さない
- 束縛値は HTTP レスポンスに現れない
- 変更後の文書へ束縛し直すので連鎖する
- **変更前の文書はもう通らない**

---

## 3. §2 `/converse` の UPDATE だけ旧経路だった

### 再現

`app/routers/ai.py` の UPDATE 分岐が `ForgeOperationEngine` を直接
呼んでいた。`/update` にある Semantic Revision・Document binding・
RevisionRecord・LearningEvent の**どれも通らない**。

**会話がForgeの本線である。** 実機で最もよく使われる直し方だけが
Evidenceを1件も残していなかった。013 で `/generate` と `/update` の
両方に Router 迂回があったのと同じ形——「片方だけ直して終わりにした」。

### fix

`app/ai/runtime/revision_service.py` に `RevisionService` を1つ作り、
両方の入口をそこへ通した。

```
Flutter Host / 会話
  → artifact capability
  → version token
  → document binding            ← §1
  → TargetResolver / 全体再生成fallback
  → Forge Validator
  → Semantic Design Critic
  → RevisionRecord（lineage）
  → CORRECTED FeedbackEvent
  → REVISION LearningEvent
  → 新しい artifact version
```

`ConverseRequest` へ `artifact_id` / `seen_version_token` /
`idempotency_key` を追加した（無いと会話からの変更は受け付けられない）。

### shared RevisionService production wiring proof

`TestBothEntryPointsShareOneService`（9件）。Test Double は
**会話が `next_action="update"` を提案する**ことだけで、Revision の
経路は本番のままである（`mock` は BUILD を提案するので確定的に
踏めない）。

- `/converse` が実際に UPDATE 分岐へ到達している（前提の確認）
- 会話経由で RevisionRecord が残る
- 同じ REVISION / FEEDBACK LearningEvent が出る
- artifact が前進する
- 局所patchであって全体書き直しではない
- **同じ守りが会話側にも効く**（別文書・stale・capability無し）
- `ForgeOperationEngine(` の呼び出しが**router内に1箇所だけ**

---

## 4. §3 本番の RevisionRecord へ偽の Visual Evidence が入っていた

### 再現

```python
visual_evidence_reference="docs/visual-evidence/FORGE-019/manifest.md",
```

が `/update` に**固定で**書かれていた。実利用者がどんな変更をしても、
Golden Finance のスクリーンショットが「その証拠」として紐付いた。

Visual Evidence は「**この変更を実際に描画して目で確かめた**」という
主張である。撮っていないものに撮った証拠を付けるのは検証の偽装であり、
Dataset の品質判断がこれを読むようになったら嘘が選別に効く。

### fix

本番では `None`。実際に render/capture したときだけ
`RevisionEvidenceStore.attach_visual_evidence()` で明示的に付ける。

`TestVisualEvidenceIsNotFabricated`（3件）。

---

## 5. §4 「直してと言われた」だけで教師データ候補になっていた

### 再現

`/update` は Revision 記録時に**元の生成物へ** CORRECTED を書く。
それは「元は外していた」という事実であって、**直した結果が良かったこと
は1つも言っていない**。

`TrainingEligibilityPolicy` は承認を見ていなかったので、
REVISION Event は consent と provenance さえ通れば
DatasetCandidate になった。

```
Generation → CORRECTED → Revision → ACCEPTED      ✅ 正例
Generation → CORRECTED → Revision → （無言）       ❌ 分からない
Generation → CORRECTED → Revision → CORRECTED     ❌ 直しても外した
```

区別せずに正例へ入れると、**「利用者が不満を言った回数」を「うまく
直せた回数」として学習する**。しかも直せなかったケースほど `/update`
が多く呼ばれるので、**下手な直し方ほど教師データに多く残る**という
逆向きの偏りが生まれる。

### fix

`resolve_revision_acceptance()` が **Feedback列をjoinして**判定する。
最後の信号を見るので、`ACCEPTED → CORRECTED` は `RE_CORRECTED` になる。

**Immutable Learning Events は書き換えない。** 後から否定されたときに
取り下げるのは `DatasetCandidate`（Forge の判断）であって、Event
（事実）ではない。判断は後から変わってよいが、事実は変わらない。

### Revision acceptance / Dataset qualification proof

`TestRevisionAcceptanceJoin`（10件）

- 無言 → `NO_FEEDBACK` → `revision_not_accepted` で候補にならない
- ACCEPTED → 候補になりうる
- ACCEPTED → CORRECTED → `RE_CORRECTED` → `revision_re_corrected`
- CORRECTED のみ → 同上
- **既にできていた候補が、後の CORRECTED で REVOKED になる**
- **過去の Feedback Event が書き換えられていない**

なお `ProjectionContext` の既定（`local_only` / `personal` /
`contribution=none`）では収集そのものが許可されないため、
§4の判定へ到達させるにはテスト側で権利のある文脈を作る必要があった。
**既定が fail closed であること自体は正しい。**

---

## 6. §5 全体再生成fallbackがlineageを1件も残していなかった

### 再現

局所操作へ落とせない要求は `ForgeOperationEngine` へ流れ、
RevisionRecord も Feedback も LearningEvent も artifact 前進も
**1つも起きなかった**。「Revisionが起きた事実」が消えていた。

### fix

同じ `RevisionService` を通す。`patch_mode=full_regen_fallback` と
`fallback_reason` で区別し、**Critic を通していないものを
`critic_passed=true` と報告しない**。

### FULL_REGEN fallback lineage proof

`TestFullRegenKeepsLineage`（9件）。AIの答えだけを Test Double にし、
Router→RevisionService→capability照合→Validator→RevisionRecord→
Feedback→LearningEvent→artifact前進の**経路は本番のまま**。

- RevisionRecord が残り `patch_mode=full_regen_fallback`
- 局所patchのふりをしない（`semantic_operation=None` /
  `critic_passed=false`）
- なぜ落ちたかが残る
- REVISION / FEEDBACK LearningEvent が出る
- **変更後の文書へ束縛し直す**（連鎖が切れない）
- 偽 Visual Evidence を書かない
- 承認が無ければ教師データ候補にならない
- capability 無し／別文書は fail closed

---

## 7. 併せて見つけた欠陥（レビュー指摘外）

### 7.1 何も変えない変更が記録されていた

生成直後の家計簿は**残高が既に主KPI**なので、「残高を目立たせて」は
変えるものが1つも無い。それを成功として記録すると、**直していないのに
「直して受け入れられた」**という嘘の教師信号を作れてしまう——§4が防ご
うとしているものを、さらに悪い形で起こす。

変更が0件なら記録せず `no_change` で断る。

### 7.2 019 の Before fixture は Validator に通らない文書だった

`negative_when` を持ちながら `sign_field` が無かった。Dart 側は
`ForgeDocument.fromJson` が通ることしか見ておらず、Validator は呼んで
いなかった。**つまり019のスクリーンショットは不正な文書を描いたもの**
である。生成スクリプトが Before も Validator へ通すようにした
（通らなければ生成が止まる）。

### 7.3 mock の全体再生成出力はスイート順序に依存する

単体で連続実行すると 4/4 で 200 だが、フルスイート内では 422 になる
ことがあった。§5のテストは AI の答えを Test Double にして依存を外した。
**原因は未特定（TD として残す）。**

---

## 8. §7 Visual Evidence lineage proof

019 は Before / After の**両方を手書き**していた。

```
Backend が実際に作る After   ←→   スクリーンショットの元になる After
```

が別々の Source of Truth だったので、実装を直しても絵が変わらない
——その絵は変更の証拠にならない。

`scripts/export_revision_visual_fixture.py` が Before を**本番の
`RevisionService` へ通して** After を書き出す。手書きは Before だけ。

```
docs/visual-evidence/FORGE-019A/before.json      手書きの入力（唯一）
docs/visual-evidence/FORGE-019A/after.json       本番の出力
docs/visual-evidence/FORGE-019A/provenance.json  どの操作の絵か
frontend/lib/forge_019a_visual_fixture.dart      生成物（Flutterが読む）
```

`backend/tests/test_visual_fixture_provenance.py`（9件）が
「いま生成し直したものと commit されているものが一致するか」を見る。
**実装が変わって絵が古くなれば CI が落ちる。**

Provenance（本番が返した事実）:

| | |
|---|---|
| intent | 残高をもっと目立たせて |
| revision_mode | `local_semantic_patch` |
| semantic_operation | `select_primary_metric` |
| semantic_target | screen `home` / widget `balance` |
| validator_passed | true |
| critic_passed | true |

局所差分は2箇所だけ:

```
balance : metric.secondary → metric.primary
income  : metric.primary   → finance.income
```

---

## 9. §8 Flutter Feedback の冪等性

### 再現

```dart
'idempotency_key': 'flutter-accepted-${DateTime.now().microsecondsSinceEpoch}'
```

**再送のたびに別のキー**になっていた。冪等キーの目的は「同じ操作が
二度届いたことをサーバが見分けられるようにする」ことなので、毎回変える
のは意味が正反対である。通信が不安定なだけで評価が何件も積まれる。

### fix

同じ操作の再送では同じキーを使い、**成功したら捨てる**。あとで利用者が
もう一度評価したときは別の操作なので新しいキーになる（017A §2 で
時系列は事実として残るようにしてある）。修正要求は**要求文が変われば
別の操作**として扱う。

### GeneratedAppHostShell の State

修正成功後に artifact を新しい版へ差し替えている（既存の挙動）。
ここを忘れると続けて直そうとしたときに必ず `stale_artifact` で弾かれる
——「一度直したら二度目が通らない」形で壊れるので、なぜ必要かを
コメントで残した。

---

## 10. §6 guard の数え方（3種類を分けて数える）

019 は「mutation 15/15」と報告していたが、中身は3種類が混ざっていた。
とくに **source-string check** が問題で、
`assertIn("revisions.record(RevisionRecord(", source)` は

* その行をコピーしてコメントアウトしても通る
* 実装を別モジュールへ移しただけで（振る舞いが正しくても）落ちる

という、どちらの向きにも嘘をつく検査だった。実際 019A で
`RevisionService` へ移したとき、振る舞いは正しいのに落ちた。

04・05・06 を **behavior guard** へ書き換え、10・15 は性質上 static
なので名前で明示した（`test_10_static_...`）。cwd 依存の相対パス
（`Path("../AGENTS.md")`）も直した。

| 種類 | 数 |
|---|---|
| **behavior guards** | **56** |
| **static protocol checks** | **6** |
| **real source mutation rounds** | **10** |

### real source mutation rounds（実際にソースを壊して確認）

| # | 壊したもの | FAILED |
|---|---|---|
| M1 | document binding 検査を外す | 4 |
| M2 | `binds()` を常に True にする | 4 |
| M3 | `visual_evidence_reference` を固定値へ戻す | 3 |
| M4 | revision acceptance の join を外す | 2 |
| M5 | fallback を RevisionService から外す | 7 |
| M6 | `/converse` を旧 ForgeOperationEngine 直呼びへ戻す | 1 |
| M7 | `no_change` 検査を外す | 1 |
| M8 | stale token 検査を外す | 2 |
| M9 | advance 時に文書を渡さない | 2 |
| M10 | Visual fixture の After を手書きへずらす | 1 |

**全roundで、壊すと落ち、戻すと通ることを確認した。**

---

## 11. Evidence 件数（本番経路1往復あたり）

局所 Revision 1回で残るもの:

| | 件数 |
|---|---|
| RevisionRecord | 1 |
| FeedbackEvent（CORRECTED） | 1 |
| LearningEvent | 2（REVISION / FEEDBACK） |
| DatasetCandidate | **0**（承認が無いため。§4） |

利用者が「これでOK」と言った後:

| | 件数 |
|---|---|
| FeedbackEvent | 2（CORRECTED / ACCEPTED） |
| LearningEvent | 3 |
| DatasetCandidate | 1（収集の権利がある文脈のとき） |

その後さらに「やっぱり違う」:

| | 件数 |
|---|---|
| FeedbackEvent | 3（追記のみ。過去は不変） |
| DatasetCandidate | 1 だが `REVOKED` |

---

## 12. テスト / CI

| | 結果 |
|---|---|
| backend | **1,496 passed / 16 skipped** |
| forge_ai | **521 passed** |
| ruff（変更ファイル） | All checks passed |
| flutter test | **UNVERIFIED**（SDK不在） |
| flutter analyze | **UNVERIFIED**（SDK不在） |
| flutter build web | **UNVERIFIED**（SDK不在） |
| CI 4 job | この commit の push 後に確認する |

---

## 13. Visual Before/After と Visual Review

### 出力

- `docs/visual-evidence/FORGE-019A/revision-preview.html`
  本番の `after.json` と、実コードの role 実装値
  （`json_ui/renderer/design_language.dart`）・テーマ定数
  （`core/theme/forge_theme.dart`）から起こした作図
- 019 の PNG は残してあるが、**Validator に通らない Before から
  撮られている**（§7.2）

### Claude 自身の Visual Review — UNVERIFIED

**この環境に Flutter SDK が無いため、実描画を見ていない。**
AGENTS.md の規定どおり `UNVERIFIED` とする。「PNGを生成しただけ」を
Visual Review と呼ばない、という規定に照らせば、**作図を作っただけの
今回も Visual Review とは呼べない**。

作図の上で確認できた範囲（構造的な所見であり、実ピクセルではない）:

- 階層は3段に割れている（36px/w700 → 16px/w600 → 13.5px）
- 数字は tabular figures 指定で桁ぶれしない
- 支出は `expense` トークンであり `error` とは別（家計簿が
  エラーに見えない）
- **弱点**: 収入と支出が同じ字サイズで並ぶので、
  「収入 − 支出 = 残高」という関係が見た目から読めない（今回の対象外）

---

## 14. 二軸の進捗

**A. Generated App Quality** — 変更が「その生成物への変更」であること
が保証され、会話からの変更も同じ品質検査（Validator + Semantic Design
Critic）を通るようになった。何も変えない変更は断るようになった。

**B. Forge-owned Local AI / Growing AI** —
`revision → feedback → later acceptance → LearningEvent →
Dataset candidate` の信頼性が固まった。**「不満を言われた回数」を
「うまく直せた回数」として学習する経路を塞いだ**のが最大の前進である。

**Real Local Model runs = 0**（FORGE-020 まで起動しない）。

---

## 15. UNVERIFIED

- **Flutter 一式**（test / analyze / build web / 実描画・撮影）
  — この環境に SDK が無い
- **実 Cloud Provider での往復** — 実APIを呼んでいない
- ブラウザ自動操作で `/update → render → feedback` を1つのセッション内
  で回すこと（019からの持ち越し）
- Runtime outcome は `UNKNOWN` のまま。描画できた事実を
  RevisionRecord へ結びつける認証付きコールバックが無い

---

## 16. Technical Debt

- `ArtifactRegistry` / Evidence / outbox は**プロセス内メモリ**のまま。
  再起動で capability が失効し、Revision の連鎖が切れる
- `document_binding` の鍵はプロセス内。複数プロセス構成では束縛が
  共有されない
- Auth / subject binding / RLS / server-issued contributor identity /
  durable outbox / Supabase Learning tables は未実装
  （`unguessable != authorized` のまま）
- `evaluate_for_export()` を**本番から呼ぶ経路が無い**。DatasetCandidate
  は現状テストからしか生まれない
- mock の全体再生成出力がスイート順序に依存する（§7.3、原因未特定）
- 019 の PNG が不正な Before から撮られている。実描画できる環境で
  差し替えが要る

---

## 17. Next Task

**FORGE-020 — Real Local Model Runtime + Benchmark + Local Promotion
Gate v1。**

019A が GO になってから着手する。Local Promotion Gate 自体は 017A で
配線済み（`AIRouter._order()` から呼ばれる）だが、**昇格する Provider
は現在0件**である——実測が1件も無いため。020 でそこへ実データを入れる。
