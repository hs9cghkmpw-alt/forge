# CHANGELOG

## 2026-08-25 — FORGE-019C/020 Revision Atomic Closure + Local Generative Intelligence Foundation

独立レビューが 019B へ挙げた A/B/C/D は**すべて実コードで再現できた**。
再現テストを先に書いて FAIL させてから直した。

### 019C

- **§3.1 advance 失敗で partial Evidence が残る問題を閉じた。** 019B は
  「CORRECTED だけ残る」を仕様として書いていた（追記専用の log は
  巻き戻せないという理由）。**しかし追記していなければ巻き戻す必要も無い**
  ——「CAS で版を進めてから追記する」順序にした。落ちうる段が追記より前に
  来たので、Rejected な Revision は RevisionRecord 0 / FeedbackEvent 0 /
  LearningEvent 0 / 版 0 / replay 0 になる。
- **§3.2 投影の失敗が確定済み Revision を巻き戻す問題を閉じた。**
  `LearningProjectionOutbox`（in-memory v1）を追加。commit → pending →
  retry。`(型名, uid)` で入口を絞るので retry で二重投影しない。
  **IN-MEMORY / NOT DURABLE。**
- **§4 `RevisionUnitOfWork`** を新設（prepare / stage / commit / project）。
  `project()` は lock の外で呼ぶ——ネットワークI/Oを logical transaction へ
  押し込まない。
- **§5 Feedback staging。** `prepare_event` / `commit_event` /
  `discard_staged_event`。追記専用の契約は1文字も緩めていない。
  `ArtifactFeedbackService.admit()` は**削除**（`prepare()` へ置き換えた
  結果、本番から呼ぶ経路が無くなったため）。
- **§7 Artifact CAS + per-artifact lock。** `version_token` /
  `evidence uid` / `document_binding` の3値すべてを照合。
  **`expected` を渡さない呼び出しも conflict**（fail closed）。
  lock は生成物ごとで、使用中だけ保持する（無限増殖しない）。
- **§8 Replay Log の予約。** `find → conflicting_key → remember` は
  check-then-act だった。`begin()` で予約を取り、同じ論理要求を同時に
  2本本処理させない。**失敗は覚えない**（失敗を replay しない）。
- **§9 意味的操作の正直さ。** `SemanticOperationKind` は7件を宣言して
  いるが、本番で自然言語から到達できるのは **1件だけ**
  （`select_primary_metric`）。`set_design_role` は engine_only、
  残り5件は reserved（型が無い）。分類し忘れは例外にする。
  本番は commit の前に `require_production_supported()` を通る。

### 020（実 Local Model が要らない部分）

- **Agent**: `permission.py`（4段。知らない道具は FORBIDDEN）/
  `sandbox.py`（実体path正規化・`.env`/`.git`/鍵の拒否・一覧にも出さない）/
  `tools.py`（ToolCall は道具名と引数だけ。secret を伏せる）/
  `untrusted.py`（Web本文は包みを解かないと取り出せない）/
  `web.py`（search / fetch / browser）/ `toolset.py`（組み立ては1箇所。
  登録済みコマンドのみ）/ `loop.py`（予算付き Repair Loop）
- **Learning**: `episode.py`（本番配線済み）/ `teacher.py`（Teacher を
  Truth にしない）/ `gym.py`（training と held-out を分離）/
  `novel_benchmark.py`（held-out 以外は構築時に拒否。専用template の run は
  Novel として数えない）/ `dataset_builder.py`（TEST_DOUBLE / UNKNOWN を
  正例にしない）/ `knowledge_acquisition.py`（ジャンル名を拒否）/
  `adapter.py` / `self_extension.py`
- **`docs/GENERATIVE-SOFTWARE-DIRECTION.md`** を新設（`PRODUCT-DIRECTION.md`
  は変更していない）
- **`scripts/capture_visual_evidence.py`** を追加（cross-platform）

### 実バグ

- Permission policy の途中へ docstring を書いたら Python の文字列連結で
  隣の key と繋がり、**`http_post` が表から消えていた**。key の形を検査する
  テストを追加した。

### Real Local Model runs: 0

Ollama / llama.cpp / torch 未インストール、GPU 無し、かつ
`huggingface.co` / `ollama.com` が network policy で拒否される（実測）。
**Mock を Real Local として数えていない。**

### Visual Review: 実施

019A/019B は `UNVERIFIED` だったが、その理由（「Flutter SDK が無い」）は
**誤りだった**——`/opt/flutter` に Flutter 3.44.9 stable が入っている。
実描画・撮影・目視まで行った（`docs/visual-evidence/FORGE-019C/`）。

### Tests（LOCAL）

backend 1,706 passed / 16 skipped、forge_ai 521 passed、
Flutter test 514 passed、`flutter analyze` No issues、
`flutter build web --debug` 成功、backend smoke 成功。
behavior guards 178 / static protocol checks 8 /
**real source mutation rounds 22（全 KILLED）**。

## 2026-08-25 — FORGE-019B Revision Transaction / Retry / Provider Evidence

独立レビューの4点は**すべて現在のコードで再現できた**。先に再現テストを
書いて FAIL させてから直した。

- **§1 Revision を atomic にした。** Feedback が失敗すると API は 422 を
  返すのに RevisionRecord と REVISION Learning Event は残っていた。孤児の
  記録は 019A §4 の join から永久に `NO_FEEDBACK` に見える——評価されない
  まま Evidence を汚し続ける。prepare → validate → stage → commit →
  publish にし、落ちたら巻き戻す。Learning Event は**確定してから**出す。
- **§2 Revision そのものを冪等にした。** 応答が届かなかった Client の
  再送が `stale_version` で**永久に通らなかった**（通信が切れただけで
  詰む）。要求の身元（生成物・版・文書・要求文のハッシュ・キー）が全一致
  したときだけ replay する。キーだけでは返さない——別要求へ以前の結果を
  返すのは、019A §1 で塞いだ穴を冪等性の側から開け直すことになる。
  同じキーで内容が違えば `idempotency_conflict` で断る（fail closed）。
- **§3 Feedback の冪等キーを生成物ごとに分けた。** global dict だった
  ので、Client が連番キーを使うと**無関係な生成物への評価が黙って消えた**。
- **§4 Provider の帰属を実態に合わせた。** LLM を1回も呼ばない局所patchが
  会話の Provider 名を名乗っていた。`forge_deterministic` と、実際に生成
  した Provider を分けて返す。呼んでもいない Provider の手柄が混ざると、
  Local Promotion Gate（017A §7）が読む数字が汚れる。

### 直したことで、テストが置物になった

§2 の replay により §1 の再現手順が `idempotency_conflict` で先に止まる
ようになり、**transaction の中まで届かなくなった**。mutation B1 で
FAILED=0 となって判明し、失敗注入テストへ作り直した。

`CLAUDE.md` §3 の「ガードが実際に効くか確かめる」は、**後から効かなく
なる**ことがある、という実例である。

### その他

- `AGENTS.md` へ **Agent Execution Policy** と
  **GitHub Handoff / No Manual Copy-Paste** を恒久ルールとして追加
- Evidence の数字を今回の実測へ合わせた（古い数字をコピーしない）

backend 1,520 passed / 16 skipped、forge_ai 521 passed。
behavior guards 80 / static protocol checks 6 / mutation rounds 9。
CI（run `32877978227`）4 job すべて success。
実描画は **UNVERIFIED**（Flutter SDK 不在）。Real Local Model runs = 0。

## 2026-08-25 — FORGE-019A Revision Integrity Hardening

独立レビューが挙げた5つのBlocking項目は**すべて実コードで再現できた**。

- **§1 Document binding.** `artifact_id` と `version_token` が正しければ
  **別のDocument**でも通っていた。handle を持っている人が任意のJSONを
  「Forgeが生成したものを直した」ことにできた（Revision lineage 汚染）。
  プロセス内鍵の HMAC で束縛し、無ければ通さない（fail closed）。
  束縛は Client にも Learning Event にも出さない。
- **§2 単一の RevisionService.** `/converse` の UPDATE だけが旧
  `ForgeOperationEngine` へ直接流れ、記録が1件も残らなかった。会話が
  Forgeの本線なので、**実機で最もよく使われる直し方だけがEvidenceを
  持っていなかった**。両方の入口を1つの Service へ通した。
- **§3 偽の Visual Evidence.** 本番の RevisionRecord へ FORGE-019 の
  manifest パスが固定で入っていた。本番は `None` にし、実際に撮った
  ときだけ明示的に付ける。
- **§4 Revision acceptance の join.** 「直してと言われた」だけで教師
  データ候補になっていた。区別せずに入れると「利用者が不満を言った
  回数」を「うまく直せた回数」として学習し、しかも**下手な直し方ほど
  多く残る**。Feedback列をjoinして判定する。記録は書き換えず、後から
  否定されたら DatasetCandidate を REVOKED にする。
- **§5 fallback の lineage.** 全体再生成が Evidence を1件も残していな
  かった。同じ Service を通し、局所patchのふりもしない。
- **§6 guard の数え方.** source-string check を behavior guard へ書き
  換えた。behavior 56 / static 6 / real source mutation 10。
- **§7 Visual Evidence.** After の手書きをやめ、本番の `RevisionService`
  から生成する。commit された絵と実装がずれれば CI が落ちる。
- **§8 Flutter の冪等キー.** 再送のたびに別のキーになっていた（意味が
  正反対）。同じ操作は同じキー、成功したら捨てる。

レビュー指摘外で見つけたもの:

- **何も変えない変更が記録されていた。** 直していないのに「直して
  受け入れられた」という嘘の教師信号を作れてしまうので、`no_change`
  で断るようにした。
- **019 の Before fixture は本番の Validator に通らない文書だった。**
  つまり019のスクリーンショットは不正な文書を描いたもの。

backend 1,496 passed / forge_ai 521 passed。
Flutter 一式と実描画は **UNVERIFIED**（この環境に SDK が無い）。

## 2026-08-25 — FORGE-019

- Added typed semantic target resolution and local primary-metric patching to production `/update`.
- Added artifact concurrency, Revision/Learning/Feedback wiring, and evaluation policy snapshots.
- Added Flutter feedback/correction host controls and retained artifact identity.
- Added preview/capture scripts, inspected Golden Finance screenshots, visual tests, and AGENTS visual policy.

バージョンではなくTaskごとに記録する(`docs/tasks/`と対応。詳細な差分は各taskNNN.mdを参照)。

## Task088 — FORGE-018A Learning Boundary Hardening + Agent Protocol（2026-08-25）

独立Reviewで再現したCollection/Training権限混同、Event provenance型違反、
process-global Consent/Context、Consent routing/retention/deploymentの穴を修正。
Local projectionとsubject-scoped exportを分離し、Dataset Candidateを本当に
Training eligibleなEventだけへ限定した。観測障害は診断を残しつつ利用者の
成功処理を壊さない。root `AGENTS.md`へ全Agent共通Protocolを追加した。

詳細: `docs/reports/FORGE-018A-LEARNING-BOUNDARY-HARDENING-report.md`

## Task087 — FORGE-018 Growing AI Learning Event Foundation（2026-08-25）

既存EvidenceをSource of Truthのまま、単一`LearningEventProjector`からLocal
Learning Event、Consent/Sanitizer/Eligibility、Cloud Export判定、Dataset
Candidate lineageまでProduction接続した。HTTPでAI_CALL / GENERATION /
FEEDBACK（ACCEPTED→CORRECTEDの2件）を実測。既定はConsent全OFF・Local-onlyで、
Supabase/Auth/RLS/server identity未実装のためCloud送信は0件・fail closed。

詳細: `docs/reports/FORGE-018-GROWING-AI-LEARNING-EVENT-FOUNDATION-report.md`

## Task086 — 017A Learning Contract Hardening + 残R1 + R2 Knowledge（2026-08-24）

CEOのReview（FORGE-017A）で commit B の契約に4つの穴が指摘された。
**全て正しかった。** 塞いだ上で、残R1 HardeningとR2 Knowledgeまで進めた。

### commit（すべて独立にpush・CI）

| | 内容 |
|---|---|
| `b61b36d` | Revision training provenance（§1） |
| `d163e6f` | Feedback Event + Handle/EvidenceId/VersionToken分離（§2-§4） |
| `2db1fcd` | Learning Contract語彙 + Local Promotion Gate（§5-§7,§10） |
| `a514a37` | Semantic Critic誤検知2件 + `/converse` Golden E2E（§14） |
| `e40c861` | Forge Knowledge + Intelligence Context Resolver（§8,§15） |

### 塞いだ穴

1. **由来不明/Test DoubleのRevisionが教師データになっていた。**
   `source`を見ていなかったので、既定の`UNKNOWN`のまま「利用者が受け
   入れた」だけでTraining Candidateになった。`TEST_DOUBLE`が特に悪く、
   テストは`mock`で大量に走るので**実運用よりテストの方が「正例」を
   多く生む**状態だった
2. **Feedbackの時系列を捨てていた。** 「最初は良いと言ったが使ってみたら
   直した」は、最初から`CORRECTED`だったものとまるで意味が違う（前者は
   「一見よく見えるが実際には外している」）。追記専用のEventにした
3. **失効するハンドルを系譜のIDにしていた。** さらにそれはBearer
   Capabilityなので、Cloudへ載せると記録を見た人が誰でも評価を書き
   換えられる。3つのIDへ分けた
4. **内容ハッシュをClientへ返していた。** 同じ内容なら誰が作っても同じ
   値になるので利用者を跨いだ突き合わせに使え、低entropyな内容は総当たり
   で言い当てられる。**内容と無関係なランダムtoken**にした

### 契約を構想から縮小しない（§5・§6）

`LearningEventType`は`build`/`compile`/`test`/`runtime`/`crash`/
`tool_result`まで持ち、`is_emitted_today`で「いま作れるか」を分ける。
**実装が無いものを「未実装」として持つのと、構想から消すのは違う。**

`LearningTaskId`を`ForgeTask`と分けた。`flutter.build`はAIを呼ばない
ので`ForgeTask`になりようがない。全`ForgeTask`がmappingされていること
をテストが強制する。

### Local Firstの矛盾を Quality Gate で解消（§7）

「Qualified Local → Local」と「Local優先は同点時だけ」は矛盾していた。
**Best Score Wins をやめた**——同点のときだけ効く優先は実質Local First
ではない。`LocalPromotionGate`が「製品として通用する水準か」を実測から
判定し、満たしたものだけを前へ出す。`AIRouter._order()`から実際に呼ぶ。

**いま昇格するProviderは0件**（Localのbenchmark記録が無い）。配線済み・
データ待ち。

### Semantic Critic の誤検知2件（両方とも再現してから直した）

* 単一であるべきroleを**文書全体**で数えていた。別画面がそれぞれ主KPIを
  1つ持つ正しい設計が弾かれ、**画面が増えるほど誤検知が増える**形だった
* finance と state の併用を無条件に誤りにしていた。家計簿は
  `finance.expense`（お金の向き）と`state.danger`（予算超過）を正当に
  両方使う。本当の誤りは**同じ値**に両方の意味を持たせること

### Knowledge が本番から呼ばれるようになった（TD69解消）

`knowledge_entries()`は014から存在したが本番から1度も呼ばれていなかった。
`IntelligenceContextResolver`を作り、**Provider選択の前に**解決して
`GenerationRecord.knowledge_references`へ`design_role.metric.primary@v1`
の形で残す。本文は残さない。

`KnowledgeEntry`は最初から`scope`/`app_id`/`status`/`version`/
`provenance`を持つ。**`app_id`はコードに1箇所も無かった** — ここが最初。
scope境界は**構造**である（Global検索がPersonalを返す経路が無い）。

Resolverは`AIRouter`へ詰め込まなかった（§8）。Provider rankingもしない。

### 判断F決着

**仮名IDは二層化を採用。** Consentを通ったEventにだけ付ける。ただし
client-generated install IDだけをPoisoning防止のTruthにしない
（作り直せる）。**IDを持っただけでSybil対策が済んだとは言わない。**

### 進捗を盛らない訂正（§9）

Architectureの「Base Model = ✅ Provider Registry」は過大評価だった。
Provider抽象があることと、Local Modelで実際に生成できることは別である。
**実Local Modelでの生成は0回**として訂正した。

### 配線破壊試験 24round

全roundで、外すと落ち、戻すと通ることを確認した（一覧はreport §9）。

### テスト

backend 1407 passed / forge_ai 521 passed。
新規: `test_learning_contract.py` 16 / `test_local_promotion.py` 20 /
`test_knowledge.py` 25。`test_artifact_feedback.py` は 45→67。

### 文書

* `docs/reports/FORGE-017A-LEARNING-CONTRACT-HARDENING-report.md`（新規）
* `docs/architecture/FORGE-GROWING-AI-ARCHITECTURE.md`（§2,§3,§5,§13,§14,§18,§19,§22,§24,§26）
* `docs/spec/LEARNING-EVENT-V1.md` / `docs/OPEN-DECISIONS.md`（F決着）/
  `docs/ROADMAP-TO-TARGET.md` / `docs/HANDOFF.md`

## Task085 — Growing AI Architecture を正式Architectureとして統合（2026-08-24、実装なし）

CEOから FORGE-GROWING-AI-ARCHITECTURE-017 が来た。**§27のArchitecture
Reviewを先に実施してから**、正式Architectureとして記録した。実装は無い。

### Reviewで分かったこと（実コードを読んだ）

**017の要素の約4割は、既に別の名前で実装済みだった。**

| 017の要素 | 既存 |
|---|---|
| Provider Interface | `ProviderDefinition` / `Deployment(LOCAL\|CLOUD)` |
| Task Router | `AIRouter` + `TaskProfile` + `ForgeTask` |
| Evaluation | `BenchmarkRun` / `Verification` / `ranking_for()` |
| provenance / training rights | `TrainingProvenance`（UNKNOWNを既に通さない） |
| artifact_ref / fingerprint | `ArtifactIdentity` / `document_fingerprint()`（commit B） |
| accepted | `AcceptanceSignal` |

→ **新しい階層を上に積まず、既存を Growing AI の構成部品として
名付け直す**方針にした。`ForgeEvalStore`や`IntelligenceRouter`のような
並列実装を作らない線引きをReport §6に明文化した。

### 本当に無かったもの（5つ）

1. Learning Event共通Contract
2. **Global / App / Personal の境界**——`app_id`がコードに**1箇所も無い**（grep実測0件）
3. Consent（module自体が無い）
4. Retention / Deletion / Dataset Lineage
5. Intelligence Resolver

### 見つかった衝突（3件）

* 🔴 **§6の仮名IDは、既存の明文の約束と衝突する。**
  `ExperienceRecord.ref`のdocstringが「セッションを跨いで個人を辿れる
  識別子を持たない」と宣言している。017 §5はそれを必須にする。
  **方針の転換なので黙って入れず、OPEN-DECISIONS Fとして起票した**
  （推奨: 二層化。Consentを通って外へ出るEventにだけ付ける）
* 🟡 §2 Local First と、`AIRouter._order()`が**実装した上で退けた**
  「Local優先」。docstringに「Benchmarkが無いのにLocalを優先するのは、
  測っていない品質を賭けてQuotaを節約しているだけ」とある。
  → **`ranking_for()`が順位を返せたときの同点処理としてのみ**入れる
* 🟡 §7の「全ユーザー共通で単純hashするのは避ける」は、
  **commit Bで実装した`document_fingerprint()`に当たる**（salt無しsha256）。
  現状はプロセス内専用で実害無し。Learning Eventへ載せるときは
  event-scopedなsalt/HMACの別関数にする

### C・Dへの申し送り（後で全面書き換えにしないため）

1. **DのKnowledgeEntry型に`scope`と`app_id`を含める**
2. **Consentを見る場所だけDで決める**（実装はE）

### 新規文書

* `docs/architecture/FORGE-GROWING-AI-ARCHITECTURE.md`（正式Architecture）
* `docs/reports/FORGE-017-ARCHITECTURE-REVIEW-report.md`（§27 Review）
* `docs/spec/LEARNING-EVENT-V1.md`（契約のみ・未実装）

`INTELLIGENCE-LAYERS-V1.md`は**書かなかった**。Architecture §3以上に
書けることが実装前には無く、重複した文書は保守負債になるため（§1
Maintainability First）。

### 更新

`docs/ROADMAP-TO-TARGET.md`（位置付けと実装順A〜F）/
`docs/OPEN-DECISIONS.md`（判断項目F）/ `docs/HANDOFF.md`

### 実装状態の表記を徹底した

Architecture文書の全項目に ✅実装済み / 🟨部分的 / ⬜未実装 /
🚫今回作らない を付けた。**✅はReviewで実際にファイルを読んで確認した
ものだけ**である（017 §26「実装していないものを実装済みと書かない」）。

## Task084 — 016A commit B: Feedback / Revision Foundation（2026-08-24）

**「これでいい」をForgeが受け取る口が、本番に1本も無かった。** それを作った。

### 実測した欠陥

`AcceptanceSignal`も`note_user_acceptance()`も011から実装済み。013で
`generation_ref`を`PipelineRunResult`へ載せるところまで直してあった。
**しかしHTTP層でそれが止まっていた**——`app/routers/`に`generation_ref`の
出現が0件、`note_user_acceptance`の本番呼び出しが0件。

結果、`user_acceptance`は本番で永久に`UNKNOWN`であり、明示的な承認を
要求する`is_positive_example`は**構造上、必ずFalse**だった。「教師データを
貯める」と書いてある仕組みが、貯める口を持っていなかった。

「作ったが本番から呼ばれない」の**5例目**（TD59 / 007 §10 / 010 Phase B /
TD64 / TD69）。

### 入れたもの

* `app/ai/gateway/artifact_feedback.py` — `ArtifactRegistry` /
  `ArtifactFeedbackService` / `document_fingerprint()` / `FeedbackRejected`
* `app/ai/gateway/revision_evidence.py` — `RevisionRecord` /
  `DesignRevision` / `RevisionEvidenceStore`（TD68の設計をProduction型へ）
* `POST /api/v1/ai/feedback` — 評価を書く**唯一の口**
* `result.artifact = {artifact_id, fingerprint}` を成功レスポンスへ
* `GenerationEvidenceStore.get(ref)`
* `DesignDecisionSource.USER_CORRECTION`（`is_ai_evidence`から除外）

### 主な設計判断

* **登録は`_result_dto()`の中**。成功レスポンスの経路3つが全てここを通る。
  呼び出し側3箇所に書く案は採らなかった——それが4回失敗した形（`CLAUDE.md` §3）
* **Clientへ内部refを出さない**。任意のrefを信用すると、見てもいない
  生成物へ「受け入れた」を書ける＝学習素材の捏造。`secrets.token_urlsafe(16)`
* **Serviceは「記録済み」を覚えない**。写しが2箇所にできるとずれる。
  `store.get(ref)`でEvidence自身に聞く
* Revision側の`note_user_acceptance()`を生成側と同じ規則（first-wins /
  `UNKNOWN`は上書きしない）へ揃えた。同じ語彙で規則が違うと静かに嘘になる

### 配線破壊試験 6round

外した配線 → 落ちたテスト、全て確認済み（詳細はreport §4）。うち2つは
指示書§15指定の break B（任意refを許す）/ break E（生の発話を入れる）。

### まだ無いもの

Flutter側の👍ボタン、`/update`から`RevisionRecord`を書く配線、
`ArtifactRegistry`の永続化。**現時点で`user_acceptance`が実データで
埋まるわけではない。**

### テスト

`backend/tests/test_artifact_feedback.py` 37件。
backend 1304 passed / forge_ai 521 passed。

### 文書

* `docs/reports/FORGE-016A-B-FEEDBACK-FOUNDATION-report.md`（新規）

## Task082 — 「伝えたらデザインを直す」の設計（2026-08-18、実装なし）

CEOから最優先方針が来た。**実装はせず、設計案・依存関係・実装順・
テスト戦略までを作った**（CEO指示）。

### 方針

> ユーザーが見た画面に対して普通の日本語で指摘すると、
> その意図を理解してデザインを直せること

見た目の便利機能ではなく、
`User Correction → Revision Evidence → Forge Knowledge → Local AI Improvement`
を閉じる経路として設計する。閉ループの最重要の辺（TD65）がここで繋がる。

### 調査で分かった既存資産

実コードを読んで確認した。土台の多くは既にある。

* **widget単位のrole適用**（`screen.styleRoles[node.id]`）
  → 「このカードだけ」が実現できる
* **`RevisionRecord`の設計**（TD68）→ 型の設計は済んでいる
* `classify_correction` の3段判定（態度→対比→対象）
* `AcceptanceSignal` / `note_user_acceptance()`
* Design Language 33 role・軸ごとの検証・Semantic Design Critic

### 見つかった致命的な欠け2件

1. **`apply_update()`がDesign Languageを知らない。** プロンプトに
   `style_role`が一言も無く、AIにJSON全体を書き直させている。
   「残高を目立たせて」の結果、支出のKPIが落ちてもValidatorは構造しか
   見ないので通る
2. **承認を受けるHTTP口が1つも無い。** `note_user_acceptance()`は実装済み
   なのに呼ぶ口が無い——「作ったが呼ばれない」の状態

### 主な設計判断

* **全体書き直しをやめ Semantic Patch（局所適用）にする。** AIに返させる
  のはDocumentではなく意味の変更指示（target/axis/from/to）。触っていない
  場所は1バイトも変わらないので、残高が消える事故が構造的に起きない
* 対象/不満/望む変化 の3段に分ける（「もっとシンプルに」は複数軸を動かす）
* 対象特定はAIにwidget idを選ばせ、存在しないidはUNCLEARへ倒して聞き返す
  （**曖昧なまま全体へ適用しない**）
* 色は`#RRGGBB`を書かせず、意味の色に`strong/normal/soft`の強度を持たせる案
  （CEO判断待ち）
* Evidenceは生の発話を持たず、`complaint_kind`/`delta`という閉じた識別子
* 実装順は**承認の口を最初に**（単独で閉ループが1本繋がるため）

### 016の整理

016（P0バグ4件 + R2 Knowledge/RAG）は未着手のまま。前回の応答が
API 529 Overloadedで着手前に中断したためで、押し忘れではない。
独立してcommit/push/CIまで到達できる**7単位へ分割**した。
016はDesign Revisionの土台になるので捨てない。

### 新規文書

* `docs/spec/DESIGN-REVISION-PROPOSAL.md`
* `docs/tasks/FORGE-016-STATE.md`
* `docs/OPEN-DECISIONS.md`
* `docs/HANDOFF.md` を全面更新（ChatGPTが最初に見る固定パス）

---

## Task081 — R1 Design Language の閉じ込め(2026-08-17、FORGE-R1-CLOSURE-015)

指摘された穴を**すべて再現してから**直した。推測でPatchしたものは無い。

### §2 NUMBERだからSUM、を廃止（実バグ）

本番経路で実際にこれが出ていた。

```
読書記録  rating(評価5段階) → 評価の合計
釣果記録  size(サイズcm)   → 魚のサイズの合計
```

「数値である」ことと「足すと意味のある量である」ことは別なのに、型だけで
後者を推測していた。`MeasureSemantics`（additive/averageable/level/
extremum/identifier/unknown）をIRへ導入し、性質から集計を引く。
**unknownはHero KPIを作らない**——倒した瞬間に上の2件が復活する。

AI合成経路でもAIが閉じた6択から選ぶ（Promptに「迷ったらunknown」）。

### §2.3/§9/§11 お金の出入りを意味として表す

`MonetaryFlow`をIRへ。Curated `household_budget`に`entry_type`（収支）を
足した。**それまで収入と支出を区別できず**、いくら記録しても
「今いくら残っているか」に答えられなかった。Templateを増やしたのではなく
既存Domainのデータモデルの欠落を埋めた。

`metric_view`へ絞り込み(filter_*)と符号付け(sign_*)を追加（v1.12、
**Widget型は増やさない**）。自然言語「毎日の収入と支出を記録したい。
今月の残高を一番目立たせたい。」から、残高(metric.primary)/収入
(finance.income)/支出(finance.expense)まで到達するE2Eを追加。

### §3 Design Criticへ semantic_design 軸

**「roleがある」だけを評価しない。** 10個すべてがmetric.primaryでも
roleは存在する——それは階層が消えた状態である。乱立・被覆不足・
持ち上げすぎ・finance と state の混同をblocking/mediumで言う。

実装直後の破壊試験で**外してもテストが落ちなかった**（置物だった）。
`test_semantic_design_critic.py`を追加して直した。

### §4 AI選択とFallbackをEvidenceで分離

`DesignRoleDecision(axis, role, source=ai|fallback|deterministic|…)`。
それまで最終role一覧しか残らず、**Forgeの既定値をAIの成功例として
学習する**経路が開いていた。型で分けた。

### §5 forge_ai→backend 逆依存の解消

`forge_ai/core/pipeline.py`が遅延importでbackendを呼び、失敗を握り
潰していた。**同じコードがProductionとstandaloneで別の振る舞い**を
していた。`DesignLanguageGuidance`契約を作り、backendが注入する形へ。
構文木で`app.*` importが無いことを検査する。

### §6/§7/§8 roleを実際の視覚差へ

* `metric_view`の数値Textが明示styleを持ち、**DefaultTextStyleが効いて
  いなかった**（`metric.primary`を付けても描画は変わっていない）
* `button.primary`/`secondary`が同じElevatedButtonで**区別できなかった**
* 意味の色が固定値で、**Darkで沈んでいた**

`ForgeRoleScope`でbuilderへroleを先に渡し、FilledButton/OutlinedButton
へ分岐。`ForgeSemanticColors`（ThemeExtension）でLight/Dark対応。
TD73として「1箇所で被せれば全Widgetに効く、は成立しない」を記録。

### §10 Visual Structure Evidence

主KPI数・被覆率・階層深さ等の決定的な事実をEvidenceへ。
**`VisualQuality`と名付けなかった**——測れていないものを測ったことに
しない。Criticと同じ関数で測る（食い違いを作らない）。

### §12/§13

`knowledge_candidates()`（代替候補とfallbackを持つ）。TD70の4案比較と
推奨（Local AIへ寄せる案が本命、cacheは繋ぎ）。

### 検証区分

* **実測**: backend 1258 passed / forge_ai 521 passed、配線破壊試験7件
* **Test Double**: AIの答え（実Cloud APIは呼んでいない）
* **未検証**: Flutter（当環境にSDK無し、CI待ち。新規17件）

詳細: `docs/reports/FORGE-R1-CLOSURE-015-report.md`

---

## Task080 — APIキーの扱いの説明と、Live Test選択の実バグ修正(2026-08-17、TD72)

CEOの「さっきのAPIはどこかに使った？試験するならどうやる？」に答える
過程で、実バグを1件見つけて直した。

### 鍵の監査（記憶ではなく検査）

リポジトリ全文 / Git全履歴（1998オブジェクト） / `backend/.env` /
作業用一時フォルダ、いずれも該当なし。疎通確認はCONNECT段階で403に
なっており、**鍵はネットワークへ送信されていない**（TLSトンネルが
張られていないので、Authorizationヘッダを送る段まで到達しない）。

### TD72: Live Testが廃止済みの`cloud`を見ていた

`_live_provider_id()`が固定の名前`("gemini", "cloud")`から選んでいた。
`cloud`は011で廃止済みの名前なので、**第二Cloudを設定してもLive Testは
Geminiしか叩かず、新しいProviderは黙ってSKIPされていた**。

* Registryが実際に持っているものから選ぶよう変更
* `FORGE_LIVE_PROVIDER`で狙って指名できるようにした
* 指名したのに叩けない場合は黙ってSKIPせず、欠けている変数名を挙げて失敗

**この誤りは実APIを呼ばないと表に出なかった**ので、選択ロジックの検査を
`FORGE_LIVE_TEST`の外へ出した（常時実行、実API 0回、6件）。旧実装へ
戻すと3件落ちることを確認済み。

### CEO向けの手順書

`docs/API-KEY-TEST-GUIDE.md`（新設）。段階0〜4、HTTPステータス別の
読み方、OpenAIに無料枠が無いこと、安全のルールまで。

---

## Task079 — 追加Cloud Providerの配線を実測で確認(2026-08-17、TD67)

CEOからAPIキーを受け取ったのを機に、「設定だけでCloud Providerを
増やせる」という**設計上の主張**を、実際に動かして確かめた。

`FORGE_EXTRA_PROVIDERS`で足したProviderが、Registryに拾われ、環境変数
から解決され、**実際に`POST /v1/chat/completions`をBearer認証で送る**
ところまでを、localhostのOpenAI互換偽サーバで確認した。

**コード変更は1行も要らなかった。** 011 §1（Protocol駆動でAdapterを
共有する）が実際に効いていることの確認でもある。

* `backend/tests/test_extra_cloud_provider.py`（7件、新設）
* 配線破壊試験3件（追加Provider検出 / 予約語保護 / 設定欠落時の除外）

**検証区分**: Forge側の配線 = 実測（Test Double） /
実エンドポイント = **未検証**。TD67は半分だけ解消。この開発環境は
`api.openai.com`へegress禁止（403）で、実APIは1回も呼べていない。

---

## Task078 — R1残件クローズ: Design Intent と Hero KPI(2026-08-17、TD69)

Task077で **R1 = NO-GO** とした理由は2件あり、その両方を閉じた。

### 1. AIがDesign Roleを選ぶようになった

Cognitive Pipelineへ `design_intent` 段を追加。軸ごとの**閉じた
選択肢**をAIへ提示し、1つ選ばせる。値（px・色）は一切聞かない。

```
screen_density → density.compact | density.normal | density.relaxed
list_surface   → surface.card    | surface.elevated
```

Forge側は**軸ごとに**検証する。`metric.primary` は語彙として正しいが
`screen_density` の答えとしては誤りなので通さない。外れた場合・AIを
呼べなかった場合は既定値へ落ち、落ちた軸を `fallback_axes` に残す
——「AIが選んだ」と「Forgeが既定で埋めた」がEvidence上で混ざらない。

Task077で `knowledge_entries()` を作りながら**誰も呼んでいなかった**
——「作ったが本番から呼ばれない」の5回目になりかけていた。配線破壊
試験6件で、外すと落ちることを確認した。

### 2. Hero KPI Widget (`metric_view`、Forge Language v1.11)

Task077は `metric.primary` を語彙へ入れながら、**その役割を持てる
Widgetを1つも作っていなかった**。「今月の残高を一番目立たせて」と
言われても出す先が無い状態だった。

`bar_chart` との違いは**グループ化しない**こと（常に値が1つ）。
`group_by` は敢えて受け付けない。集計は既存のTRANSFORM層
（`aggregateAll()`）が行い、Widgetは所有しない。

* 0件のとき **「0」と書かない** — 「合計0円」と「記録が無い」は違う
* **一覧より前**に置く — 後ろだと「一覧のおまけの合計」になる
* 数値Fieldが無いEntityには**何も置かない** — 出せるからといって出さない

TD37（Validator・Runtime・Registryの不一致で4種が描画不能だった実バグ）
の再発防止として、Validator / Compiler / Flutter Runtime / Capability
Registry の4層を同じcommitで更新した。配線破壊試験6件で確認。

### 訂正

Task077のTD69に「WidgetはR3/R5の範囲だから今回は足さない」と書いたが、
**誤りだった**。`metric.primary` の出力先が無いこと自体がR1の未達で
あり、混ざりようがない。

### 新たな負債（TD70）

Design Intentにより **Curated生成のAI呼び出しが 0回 → 1回**になった。
Gemini実測枠は1日20回/Model（TD66）なので無視できない。それでも
入れたのは、Curatedだけ外すと最もよく使われる経路でDesign Language
が効かないため。

### 検証区分

* **実測**: backend 1182 passed / forge_ai 521 passed、生成Documentの
  v1.11 Validator通過
* **Test Double**: Design IntentのAI選択（provider差し替え）
* **未検証**: Flutter（この環境にSDKが無く未実行、CI待ち）、実Cloud API

詳細: `docs/reports/FORGE-R1-HERO-METRIC-AND-DESIGN-INTENT-report.md`

---

## Task077 — R1入口 + Design Language V1(2026-08-17、FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014)

### §2 GenerationSourceを実Providerの事実から決める(P0・実バグ)

013は`domain_resolution == "generated"`を無条件に`CLOUD_AI`へ写して
いた。しかし`generated`が言っているのは「決定的なCurated生成では
なかった」だけで、**誰が作ったかは言っていない**。

実害は2つ。Local AIが構造を作るようになると実績が丸ごとCloud AIの
成績になる。そして**現に、Mock生成がCLOUD_AIとして記録されていた**
——013のテスト自身が`assertIn(CLOUD_AI, ...)`と書いてその誤りを
固定していた。

Registryの`deployment`/`test_only`をSingle Source of Truthにした。
`test_only`を**先に**見る(mockは`deployment=local`なので、順序を
逆にするとLocal AIの実績を水増しする)。`TEST_DOUBLE`を追加し、
Cloudにも Localにも混ぜない。

### §3 generation_refをProduction Pathへ流す(P0)

013は`record()`の戻り値を捨てていた。記録はされるが、後から
Runtime結果や利用者の承認を書こうとしても「どの生成物へ書くか」を
本番が知らない——R0以前にExperienceで踏んだのと同じ形である。
`PipelineRunResult.generation_ref`まで流した。

なお`ConversationSession`へ持たせる案は**撤回した**——BUILD後に
セッションを破棄するので、置いても必ず捨てられる。「あるが誰も
使えない」を作らない。

### §4 Runtime/User Acceptanceを嘘で埋めない

`UNKNOWN`のままにした。書ける**構造**だけ先に作り、テストで固定。

### §5 UPDATE/Revision Evidenceの設計判断(TD68)

3案を比較して案A(別Record + 関係)を採用。実装はR2。
「混ぜない」と「取らない」は別である、を明記した。

### §6 Semantic Identifier境界

自由文を弾く。`metric.primary`は通し、「残高を目立たせてほしい」は
弾く。大文字も弾く(`Metric.Primary`と両方記録されると集計が割れる)。

### §7〜§11 Design Language V1

33 role。Schema v1.10 / Validator / Compiler / Runtime / Evidence抽出
まで接続。**Widgetは1つも増えていない**——増えたのは意味付けである。

`style_role`の検査は**1箇所**(`_check_widget_schema`冒頭)。type別の
`allowed_keys`へ配ると、Widgetを足すたびに書き忘れる。Runtime側も
`_build()`の1箇所で被せる。

Evidence抽出は**最終Documentの事実から**行う(AIの自己申告からでは
なく、Repair後の確定版から、決定的に、重複を潰し、語彙外は捨てる)。

### 未達(TD69、正直な申告)

* **Hero KPI Widgetが無い**ので`metric.primary`をCompilerが出せない。
  Golden Finance E2Eは完全には成立していない
* **Conversationへ語彙を渡していない**——AIはまだroleを選んでいない。
  今出ているroleは全てCompilerが構造から決めたもの。**R1の核心の
  残件**であり、R2の最初にやる

配線破壊試験: 4パターンすべてで対応するテストが落ちることを確認。

## Task076 — Pre-R1 Integrity Gate(2026-08-17、FORGE-PRE-R1-INTEGRITY-GATE-013)

R1(Design Language)へ入る前に、実機バグ・Evidence設計・文書の事実関係・
CIの穴を閉じる。ChatGPTによる独立監査の指摘を、**そのまま肯定せず
現HEADで再現してから**扱った。

### §1 CORS — 指摘は再現せず。ただし回帰テストは追加した

指摘は「`allow_origin_regex`が二重escapeされており、実機で既にCORS障害を
踏んでいる」だった。**現HEAD(`02c559c`)では再現しない。** 実コードは
raw stringで正しく書かれており、`git log -p`を全履歴で追っても二重escape
された版は一度も存在しない。HTTPレベルで叩いても期待どおり動いた。

ただし**HTTPレベルで確かめるテストが1つも無かった**のは事実なので、
`test_cors_contract.py`を追加した。regexを指摘された二重escape形へ戻すと
実際に3件落ちる——つまり**指摘の懸念自体は正当**だった(状態が違っただけ)。

### §2 空optional env — 再現。報告より影響が広かった

`.env.example`をコピーすると入る`FORGE_GROQ_TIMEOUT_SECONDS=`(値なし)で
`float("")`が`ValueError`になる。**`ProviderRouter`は起動時に全Providerを
構築するので、1つ空なだけでForge全体が起動しない。**

`app/core/env_settings.py`を作り、未設定/空/whitespaceは既定値、
壊れた値と範囲外は`ConfigurationError`という契約にした。**生の
`float(os.environ...)`が再び現れたら落ちるsource scan**も置いた
——共通関数があるだけでは、次にProviderを足す人が同じ書き方をする。

なお全角数字`３０`は「弾かれるはず」と想定してテストを書いたが落ちな
かった。Pythonの`float()`は全角も`1_000`も**意図どおりの値**に解釈する。
私の想定が間違っていたので、その事実をテストに残した。

### §3 TD65の事実関係を訂正

「Curated DomainはAIを1回も呼ばない」「Experienceが1件も出ない」は
**測った範囲より広い主張**だった。測り直した:

| 経路 | 生成stageのAI呼び出し | Experience |
|---|---|---|
| `/generate`(Curated) | 0回 | 0件 |
| `/converse`(製品の通常経路) | 0回 | **1件**(会話ステップ) |

会話は`ConversationEngine`自身がAIを呼ぶ。欠けていたのは**生成物に
ついてのEvidence**だった。TECH_DEBT / STATUS / ROADMAP / R0 report /
HANDOFF の該当箇所を訂正した。

### §4 Curatedを消さずに学習ループへ載せる(第4案を実装)

3択でCEO判断待ちにしていたが、**第4の案を設計して実装した**。

「1回のAI呼び出しの記録」(`ExperienceRecord`)とは別に、
「1つの生成物の記録」(`GenerationRecord`)を持つ。`source = curated |
cloud_ai | local_ai | composition`で由来を区別するので、**AIを呼ばずに
作った成功例も同じ形のEvidence**として並ぶ。

学習データを作るためだけにCuratedへAIを通すのは本末転倒である
——速く・安定・無料な経路を、記録の都合で遅く不安定に有料にすることに
なる。**記録の形が実行の形を歪める**のは設計として逆立ちしている。

Production配線済み(`PromptPipeline`の生成完了地点)。実測:

```
{"source":"curated",  "domain":"household_budget", "ai_calls":0}
{"source":"cloud_ai", "domain":"diary",            "ai_calls":1}
```

由来は`domain_resolution`の決定から読む。**AI呼び出し0回だからCurated、
とは推測しない**——推測で由来を埋めると学習側が由来を信用できなくなる。

### §5 TD66を実測/推論/未検証に分離

実測は「観測した1 Modelの`quotaValue`が20」「`quotaId`が
`PerProjectPerModel`」の2点だけ。「3 Modelで60回」「1日20アプリで止まる」
は推論である。とくに**「枠は鍵ごとに独立」は`PerProject`という実測と
整合していなかった**ので訂正した。枠を消費する追加検証はしていない。

### §6 「Groqはコード変更不要」の断定を訂正(TD67)

設計上そうなっているのは事実だが、実APIは一度も呼んでいない。
「接続時にコード変更が不要」は**未証明**である。

### §7 CIを拡張

* `flutter build web --debug` を追加(analyze/testが通ってもWeb buildは
  落ちうる)
* **backend smoke job**を追加——uvicornを実際に起動し、`/health` 200、
  localhost Originのpreflight 200 + header一致、外部Originの拒否を見る。
  **空のoptional envを設定した状態で起動**するので、§2の実バグもCIを
  すり抜けない

### §8 Documentation drift

「Claudeのサンドボックスにfastapiが無いため一度もimport・実行できて
いない」という古い注記が5ファイルに残っていた。全てCIで実行されている
ので訂正した。歴史は消さず、現在状態を誤読させない形にした。
`security.py`のJWT未実装のように**今も有効な制限**は、そのまま残した。

## Task075c — 報告をmdで残す運用を確立(2026-08-17、CEO指示)

CEO指示: 「今後は報告事項をmdファイルにして同時にプッシュするように。
ChatGPTが同じGitHubを見て確認するので。」

このリポジトリは**複数のAI(Claude / ChatGPT)が同じGitHubを見て**
作業する。チャットの内容は他方から見えないので、**チャットにしか
無い情報は存在しないのと同じ**である。

* `docs/HANDOFF.md`(新規) — **パス固定の最新申し送り。**
  作業のたびに上書き更新して同じpushに含める。CEOへの依頼を一番上に
  置き、やったこと/今の状態/次にやること/未解決が自己完結して読める
* `CLAUDE.md`(新規) — AIエージェント向けの恒久ルール。§1が今回の指示。
  併せて、過去に繰り返した失敗(作ったが本番から呼ばれない・ガードが
  置物・分からないものを楽観側へ倒す)を明文化した
* `README.md` / `docs/README.md` — HANDOFFへの導線を先頭に置いた

**APIキーの依頼もHANDOFFへ書いた**(Gemini無料枠1日20回/Modelの実測値と、
Groq/Cerebras/OpenRouterの取得手順、コード変更不要であること)。

## Task075b — 文書の抜けを埋める(2026-08-17)

CEOから「やったことはmdファイルにあるのか」と確認を受けて監査した
結果、**会話でしか報告していないもの**が3つあった。会話は残らないので、
文書へ落とした。

* `docs/reports/FORGE-ROADMAP-R0-report.md`(新規) — R0 / 011 §7 / R0.1
* `docs/reports/FORGE-AI-FOUNDATION-011-report.md`(新規) — 011の7点＋
  報告項目。**会話で口頭報告しただけで文書化していなかった**
* **TD65** — Curated DomainはAIを1回も呼ばずに生成される(実測)。
  Product Direction §4に触れる形であり、Local AIへの影響が大きい
  (この経路からEvidenceが1件も出ない)。判断待ちとして記録
* **TD66** — Gemini無料枠は1日20回/Model(429本文の実測値)
* `docs/ROADMAP-TO-TARGET.md` — R2.5(Curated判断)を追加、R0の実施結果と
  発見を反映
* `FORGE-AI-FOUNDATION-010-report.md` をリポジトリ直下から
  `docs/reports/` へ移動(前回の置き場所ミス)

## Task075 — AI連携の失敗を直す(2026-08-17、FORGE-ROADMAP R0.1)

CEOが実際に使ったところAI連携が失敗した。再現したら**6回中6回失敗**
していた。原因は3つ重なっていた。

### 1. 環境 — 既定Modelが混んでいた

同時刻に実測(同じ鍵・同じPayload・各3回):

    gemini-flash-latest        [200, 503, 503]   ← Forgeの既定
    gemini-flash-lite-latest   [200, 200, 200]
    gemini-3.5-flash           [200, 200, 200]

Google自身が「一時的だ」と言う503("Spikes in demand are usually
temporary")。

### 2. 設計 — 一時的な失敗でも1回しか試さなかった

§20「同じProviderを二度試さない」を、一時的な失敗にも当てていた。
恒久的な失敗(鍵が無い・未実装)には正しいが、一時的な失敗に当てると
**混雑がそのまま「AIが使えません」になる**。`ErrorKind.is_transient`と
`another_model_may_work`で分けた。

### 3. 設計 — ProviderにModelが1つしか無かった

`ProviderDefinition.models`は「診断とBenchmarkのため」でRoutingには
使っていなかった。「別Modelなら通る」という事実が実行へ反映される
経路が無かった。

**Provider Identityは増やしていない。** `gemini-flash-latest`と
`gemini-flash-lite-latest`を別Providerにすれば既存の巡回だけで済むが、
それは011 §1が禁じた形である——同じ鍵・同じ枠を共有する2つを別
Providerにすると、枠切れを片方で学習してももう片方が同じ枠へ突っ込み、
Circuit BreakerもBenchmarkも単位がずれる。Modelは**Provider内部の
実行選択肢**として扱い、Providerの外から見た振る舞いは変えていない。

### 実測の結果、もう1つ分かったこと(枠はModel単位)

429の本文を読んだ:

    "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
    "quotaValue": 20

**Modelごとに1日20回**である。`QuotaScope`を宣言として追加し、
`PER_MODEL`と実測で分かっているProviderに限り、枠切れでも別Modelへ
進むようにした。既定は`UNKNOWN`で**進まない**——分からないものを
楽観側へ倒さない。

### 文言も直した

枠切れと障害を同じ「しばらく待ってからもう一度お試しください」で
案内していた。1日単位の枠切れに対しては嘘になる(5分後も同じ結果)。
打つ手が違うものを同じ文言で案内しない。

### 実機確認

    修正前  /converse 0/6 成功
    修正後  /converse 6/6 成功、/generate 3/3 成功

配線を1つずつ外して、対応するテストが落ちること・戻すと通ることを
確認した。**最初に書いた「枠が不明なら賭けない」テストは、配線を
壊しても落ちなかった**(候補が1つしか無いProviderで測っていたため
偶然通っていた)。テストの方を書き直した。

### 未解決として残すもの

`gemini-2.0-flash`は404(提供終了)を実測したのでRegistryと
`KNOWN_MODEL_PROVENANCE`から外した。

無料枠1日20回/Modelという上限そのものは、Model fallbackでは
解決できない(3 Modelで60回/日)。実運用には**2つ目のCloud Provider**
が要る——枠は鍵ごとに独立しているため、これはProviderを増やす以外に
方法が無い。

## Task074b — CI(GitHub Actions)を導入(2026-08-17、FORGE-AI-FOUNDATION-011 §7)

`.github/workflows/ci.yml`。backend(Python 3.11/3.12)・forge_ai・
Flutter(`analyze --fatal-infos --fatal-warnings` + `test`)。

**実APIは呼ばない。** `FORGE_LIVE_TEST`を設定しないので
`test_live_api.py`は自分でSKIPする(010 Phase Iの既定)。CIにAPIキーを
置かないので、無料枠を消費せず(§38)、Secretが漏れる経路が最初から
存在しない(§14〜18の境界をCIでも保つ)。

Python 3.13を入れていないのは好みではなく、`requirements.txt`が
書いているとおり pydantic 2.7.4 / supabase 2.5.1 が3.13のwheelを
出していないためである。

初回実行(run #1、commit 32087d5)で3ジョブとも green。
backend 3.11 / backend 3.12 / frontend(Flutter analyze + test)。
`flutter analyze --fatal-infos --fatal-warnings`も通っており、
STATUS.mdが書いていた「analyze 0件」がCIで固定された。

## Task074 — Experienceを本番から記録する(2026-08-17、FORGE-ROADMAP R0)

Product Direction §7が「完成扱いしてはならない」と名指しした状態
——**ExperienceStoreはあるがProductionから記録されない**——を解消した。
Widget追加は0件。

**同じ形の失敗が4回続いていた。** `ModelGateway`(TD59)、
`classify_correction`(007 §10)、`/generate`・`/update`のRouter迂回
(010 Phase B)、`ExperienceStore`(TD64)。いずれも基盤は作ったが
本番から呼ばれておらず、共通しているのは「呼び出し側が忘れずに呼ぶ」
設計だったことである。**忘れずに呼ばれる保証が無いものは忘れられる。**

そこで記録地点を`AIRouter.generate()`——本番のAI呼び出しが必ず通る
唯一の入口(Phase Bの Anti-Bypass Regression が証明済み)——に置いた。
Endpointが増えても、記録を書き忘れることができない。成功だけでなく
**全Provider失敗も記録する**(成功だけ貯めると「Providerは常に上手く
いっている」という記録になる)。

呼び出し時点では分からない事実は、後から書き足す形にした。1回の
AI呼び出しについて事実が揃う時刻は3つに分かれている——Provider・
latencyは直後、Validatorの合否は生成の終わり、**利用者が承認したか
訂正したかは次のターン**。最後のものがProduct Direction §5の言う
「正しさの根拠」の本命であり、呼び出し時点で全部揃う前提にすると、
一番価値のある信号だけが永久に記録されない。

* `ExperienceRecord.ref`(不透明な通し番号)で書き足し先を指す
* `note_generation_outcome()` — Validatorの合否・repair回数
* `note_acceptance()` — 利用者の承認/訂正。**先に書かれた信号が勝つ**
  (後から来る弱い信号で「訂正された」を消さない)
* 会話の`accept`/`clarify`/`rewind`を、`ConversationStore`が
  **前ターンの記録へ**書き足す(011 §5の分離が、ここで初めて
  本番の値として現れる)

**実機で実バグを1つ見つけた。** 実Providerで確認したところ、Geminiの
記録が`{"provider": "gemini", "model": ""}`になっていた。
`GeminiProvider`だけがModel名をprivate属性にしていてRouterから読めて
いなかった。Providerだけ分かってModelが分からない記録は、Model入れ替えの
前後を区別できず学習素材にならない。`model`プロパティを公開し、回帰
テストを追加した(未設定の汎用Cloud枠は対象外——呼べないものが名乗ら
ないのは矛盾ではない)。

**配線が置物でないことを確認した**(010と同じ手順)。5箇所の配線を
1つずつ外して、それぞれ対応するテストが落ちること・戻すと通ることを
確認している。最初に書いた`/update`のテストは配線を外しても通って
しまったので、テストの方を直した。

実機確認: 実Gemini(`gemini-flash-latest`)で`/converse`を実行し、
`{"provider":"gemini","model":"gemini-flash-latest",
"structured_output_valid":true}`が記録されること、利用者の発話が
記録に含まれないことを確認した。Gemini側の503(高負荷)で失敗した
往復も記録されており、失敗の記録も動いている。

**残っている制限**(TD64): 永続化していない(プロセス内メモリ、TD41と
同じ)・`ABANDONED`は一度も書かれない(セッション放棄を検出していない)・
Privacy Policy(TD60)は未完成。

## Task073 — AI Foundation 統合(2026-08-14、FORGE-AI-FOUNDATION-010)

**Phase Bの監査で実バグを発見した。** `FORGE_DEFAULT_PROVIDER=mock`を
設定した状態で`/converse`を呼ぶと、レスポンスは`provider: "mock"`,
`simulated: true`と返しながら、**実際には利用者の入力を実Geminiへ
送っていた**(Router内部の状態`gemini available successes=1`で確認)。
原因は、Routerが`FORGE_DEFAULT_PROVIDER`を読んでいなかったことと、
レスポンスの`provider`欄が「選ばれるはずだった名前」から作られていて
実際に答えたProviderと無関係だったこと。「Silent Mock fallback禁止」の
裏返しで、**Silent Cloud送信**の方が害が大きい。

**同じ配線漏れの3例目も見つかった。** Router経由になっていたのは
`/converse`の会話ステップだけで、`/generate`・`/generate/confirm`・
`/update`・`/converse`のBUILD経路は`ProviderRouter.resolve()`を直接
呼んでいた。すべて塞ぎ、`ModelGateway`(本番未使用の重複層)を削除した。

回帰テストの作り方も変えた。「Routerを呼んでいるか」ではなく
**「Routerを通らない経路が存在しないこと」**を測る——前者は
「Routerも呼び、かつ別経路でも呼んでいる」を見逃す。この回帰テストが
置物でないことも確認した(迂回を再導入すると4件落ち、戻すと通る)。

**Provider Registry(Phase C)**: Providerの知識が3箇所に散っていたのを
`provider_registry.py`へ集約。「実装があること」と「設定があること」を
別に判定するので、鍵を設定しても未実装Providerは候補にならない。

**Secret境界(Phase D)**: `.gitignore`が`.env`と`backend/.env`の完全一致
2件しか見ておらず、`.env.local`等が素通りしていた。Registryが持つのは
環境変数の**名前**だけで、値は読まない・保持しない・出力しない。
実値がソースに混入したら落ちる検査も追加(鍵形式の文字列を仕込んで
落ちることを確認済み)。

**汎用OpenAI互換Adapter(Phase E)+ 証拠順の失敗分類(Phase G)**:
HTTP往復・JSON抽出・再試行はLocalに固有ではないので共通化した。
失敗の分類は**構造化エラー → HTTPステータス → ヘッダ → 本文 →
文字列マッチ**の順で、文字列は最後にしか使わない。逆順だと
「429という明確な事実があるのに、文言にrate limitが無いからUNKNOWN」
が起きる。429 + `insufficient_quota`は枠切れであって流量制限ではない。

**2つ目のCloud枠(Phase H)**: 環境変数3つでOpenAI互換Cloudが
Routingへ載る。特定Providerのbase_urlを書かなかったのは、この開発環境が
Provider公式ドキュメントへegress禁止で**公式に確認できなかった**ため
(未検証のものを「実装済み」として並べない)。TD62として記録した。

**Live API Test(Phase I)**: `FORGE_LIVE_TEST=1`のときだけ走る。
実API呼び出しは全体で最大2回(§38)。**実行して3件passを確認した
(実Gemini)。REAL検証である。**

**Benchmark基盤(Phase J)**: 数字は測定条件を必ず携える。とくに
`Verification`(REAL / DOUBLE / FIXTURE / UNVERIFIED、既定はUNVERIFIED)が
本番経路への関門で、**Test Doubleで測った数字はRoutingへ流れない**。
`AIRouter._order()`へ配線済みだが、実測記録が0件のため現状は宣言順
(TD63)。

**Local AI学習の境界(Phase K)**: `ExperienceRecord`は発話・生成物・
応答本文を入れられるフィールドが**そもそも無い**。「気を付ける」運用は
いずれ破られるので型で塞いだ。Shadow Modeは設計のみ、Provenanceの
既定は`UNKNOWN`。収集も学習も行っていない(TD64)。

**テスト(実測)**: backend 989(skip 16、うち3件はLive)/ forge_ai 521。

## Task072 — Quota-Aware AI Router(2026-08-13、FORGE-QUOTA-AWARE-AI-ROUTER-008)

> このエントリはTask073の作業中に**記載漏れに気付いて追記した**
> (2026-08-14)。Task072の実装自体は2026-08-13に完了・commit済みで
> あり、CHANGELOGへの記載だけが抜けていた。

Geminiの無料枠が切れるとForgeが使えなくなる、という問題への対応。
Providerを増やすだけでは解決せず、「今どれが使えるか」を判断する層が要る。

**失敗を種類で分ける**(`ai_errors.py`): 現行実装は`except Exception`で
すべての失敗を同じものとして扱っており、400(schema不正)でも全Providerを
巡回してQuotaだけを減らしていた。`ErrorKind`11種を「次に何をすべきか」で
分類し、`INVALID_REQUEST`だけは他Providerを試さない(Forge側の誤りなので
相手を変えても直らない)。

**枠切れは故障ではない**(`provider_state.py`): `QUOTA_EXHAUSTED`を
Circuit Breakerの失敗カウントに入れない。枠切れは`reset_at`まで待てば
直るが、故障はcooldown後に試さないと分からない。復帰条件が違うものを
同じ仕組みで扱うと、どちらの理由で除外されているか分からなくなる。

**Quota不明を無制限と扱わない**: `QuotaKnowledge.UNKNOWN`を正面から持ち、
楽観にも悲観にも倒さない。

**並べ替えをしない判断**: 当初は「Local優先」「失敗が少ない順」で
並べ替えていたが、テストを走らせて2つの問題が出た——(1)1回失敗した
Providerが即座に後回しになるので連続失敗が積み上がらず**Circuit Breakerが
発動しない**、(2)Benchmarkが無いのにLocalを優先するのは**測っていない
品質を賭けてQuotaを節約している**だけ。健全性は「除外」でのみ表す形に
した。

**禁止事項の遵守**(§46): API Key複数化によるRate Limit回避、MockへのSilent
Production Fallback、全Providerへの無制限Retry、Side Effect処理の
無条件Retry、いずれも実装していない。

## Task071 — Conversation Foundation 是正(2026-08-13、FORGE-CONVERSATION-FOUNDATION-007)

**再監査の結果、指摘の多くは前回(Task070)で修正済みだった**。現物で1件ずつ
確認し、本当に残っていた4件を修正した。差異は報告済み。

**残っていた問題1: 追加要求が「分からない」に落ちる**。
「いいけど脈拍も追加したい」が`UNCLEAR`になっていた。「脈拍」が
Capability Registryに無いためだが、**語彙へ足すのは対症療法**である
(次は「血糖値」で同じことが起きる)。正しい理解は§37の区別にある——
「脈拍」はProduct Spec(記録する項目)であって、Platform Capability
(数値を記録できるか)ではない。追加マーカーを独立した信号として持ち、
名詞は`SolutionHypothesis.spec_notes`へ保持して`build_brief`まで運ぶ。
**能力は増えないが、ユーザーが言ったことは失われない。**

**残っていた問題2: TrustとExecution Readinessが同じenum**(§17)。
`CANDIDATE`(=Primitive未実装)は信頼度ではなく実行可否だった。
`TrustLevel`(CORE/COMPOSED/REJECTED)と`ExecutionReadiness`
(INVALID→DEFINED→PRIMITIVES_READY→COMPILABLE→RUNTIME_VERIFIED)へ分離。
「合成のみで安全」かつ「まだCompilerが選べない」が同時に表せるようになった。

**残っていた問題3: 「作れない」が2値**(§19)。
`CapabilityAvailability`(EXACT / FALLBACK / BLOCKED)を追加。
代替を出せるのか、何も出せないのかで、ユーザーへ返す言葉が変わる。

**残っていた問題4: Golden Flowが1本の流れとして無い**(§23)。
3ターン(提示 → View訂正 → 承認 → BUILD)をE2Eで固定した。

**Documentation**: v1レビューの冒頭へ「結論はv2が上書きしている」旨を
明記。撤回したのは「Product Goal自体が成立しない」という部分だけで、
「Runtime任意Dart Hot Plugは不採用」は今も有効、と区別して書いた。
Semantic Capability Architectureの状態を`PoC / partial integration`へ訂正。

**テスト(実測)**: backend 870(skip 13)/ forge_ai 521 / Flutter 476、
`flutter analyze` 0件。

## Task070 — CEOレビュー指摘6件の修正(2026-08-13、FORGE-USER-GUIDED-SELF-EXTENSION-006 レビュー)

いずれも**再現してから**原因を特定した。5件は「症状」ではなく
**構造上の誤り**が原因だった。

1. **会話Phaseの不在**: Capability層を「CONFIRMの後、ASKの前」という
   **行の位置**で差し込んでいたため、BLOCKINGな未知が残っていても仮説が
   先に出た。`ConversationPhase` + `select_phase()`を新設し、優先順位を
   SAFETY → HYPOTHESIS_REPLY → PROBLEM_DISCOVERY → CAPABILITY → BUILD
   としてデータで表現した。
2. **導出値をフィールドに保存していた**: `missing`を保存し部分更新して
   いたため、訂正していない層のMissingが消えた。プロパティ化して層から
   毎回導出する——更新漏れという不具合の形そのものを無くした。
3. **語の出現と変更意図の混同**: 「うん、地図でいい」の「地図」は合意の
   対象であって変更要求ではない。stance(否定/肯定)→ 対比 → 対象、の
   3段階へ再設計。ACCEPT判定を先頭へ動かすだけでは
   「うん、でも地図じゃなくて一覧がいい」を取りこぼす。
4. **Semantic Architectureの状態表記**: TRANSFORM/ENCODINGは分解にのみ
   使われ、訂正の対象にできない。「移行済み」ではなく
   「補助的PoCとして接続済み」へ訂正(v2 §21-bis)。
5. **`usable`が強すぎた**: 「定義として妥当」と「本番で使える」を1語で
   表していた。`definition_valid` / `primitives_available` /
   `compiler_supported` / `runtime_verified` / `production_usable`へ分離。
   **今はどの定義もproduction_usableへ到達しない**。
6. **`blocking_missing`の混同**: 「要求どおり作れない」と「何も出せない」を
   混ぜていた。`satisfiable_exactly` / `renderable_at_all` /
   `fallback_possible`へ分離。

**Documentation drift**: STATUS/TD55の「Capability自動追加=不採用」は、
v2の「Product Goalは捨てない」と矛盾していた。撤回対象を
「実行中のDart注入」に限定して書き直した。「地理描画だけが本当に無い」も
不正確(4つとも未実装、違うのは種類)だったため精密化した。

**テスト**: forge_ai 521 / backend 852(skip 13) / Flutter 455、analyze 0件。
指摘1〜3・5・6それぞれに回帰テストを追加した。

## Task069 — Stateful User Correction / Semantic Capability / Declarative Extension(2026-08-13、FORGE-USER-GUIDED-SELF-EXTENSION-006)

**Architecture Review v2**(`docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md`):
v1は「Flutterが動的コード実行不可 → Self-Extensionは成立しない」と結論して
いたが、これは**Goal 1(実行中のDart注入)にしか当てはまらない**推論だった。
Self-Extensionを「安全な方法で自身の能力を増やす」と定義し直した上で、
Composition / Declarative / Build-Time / Service / Native の5分類で成立可否を
判定した。任意コード生成は引き続き不採用。

**Stateful User Correction(§53、最優先)**: `classify_correction()`と
`revise_hypothesis()`は**テストからしか呼ばれておらず**、Sessionに仮説を
保持する状態も無かった(監査で確認)。訂正のたびに最新発話から作り直して
いたため、「魚とサイズと場所を記録して地図で見たい」→「違う、色を濃く」で
**記録項目が消えていた**(再現済み)。Sessionが仮説を持ち、訂正された層
だけを差し替えるようにした。§39のCase A〜EをE2Eで固定。

**Semantic Capability分解(§29・§54)**: Runtime監査で、`bar_chart`が
集計しないこと・派生状態の仕組みが無いことを確認した。「heatmapが無い」は
誤診であり、実際は集計(TRANSFORM)・濃淡(ENCODING)・地理描画(VIEW)の
3種類が別々に不足していた。v1の3層に`TRANSFORM`と`ENCODING`を足した。
「地図で濃淡」は4個先だが、同じ困りごとに答える「場所ごとの集計」は1個先。

**自分の主張を1つ訂正**: 「集計Primitiveを足すと表現の族が増える」を実測
したところ、どのPrimitiveも+1個で、**主張は支持されなかった**。測定が支持
したのは「ユーザーの要求へ最も安く到達できる道である」という別の事実。
§22-bisに記録し、測定自体をテストとして残した。

**Declarative Extension PoC(§55)**: 新Capabilityを**コードではなくデータ**
として追加し、決定的Validatorで検査する仕組み。捏造Primitive・外部作用の
合成獲得・巨大Capability・未実装Primitiveをすべて拒否する。
**`CANDIDATE`は`usable=False`**——「作れたふり」をしない。
Compiler接続(描画・使用)へは到達していないため、**自己拡張したとは
報告しない**(§56の基準)。

**テスト**: forge_ai 521 / backend 840(skip 13) / Flutter 455、analyze 0件。

## Task068 — Mock品質・Silent Mock禁止・Capability検出(2026-08-13、FORGE-HANDOFF-LOCAL-AI-UX-004 §9/§35 / FORGE-ARCHITECTURE-REVIEW-AND-IMPLEMENT-005 §32)

**Mock品質(§35)**: `MockLLMAdapter`が全ての文字列を`"mock_result"`で
埋めていたため、生成Toolのチェックリストに`mock_result` `plan` `screens`が
項目として並んでいた。ユーザーの実発話から決定的にもっともらしい日本語を
組み立てるようにした(買い物→牛乳・卵・パン)。話題照合は**プロンプト全体**に
対して行う——compile段のプロンプトには生の発話が無いため(実行して確認)。

**内部識別子の露出**: 確認文が「「Shopping」「Diary」「Generic」のどちらに
近いか」だった。`Domain.label_ja`/`user_facing_name`を追加し、GENERIC
(内部の受け皿)を候補から除外、3候補への「どちら」を「どれ」へ修正。

**タイトルが説明文だった(Provider非依存の実バグ)**: `/converse`導入後、
Pipelineへ渡るのは`build_brief`(Forgeが書いた説明文)なので、`Intent.goal`
経由でアプリ名が「買い物で何買うかを記録・管理するための道具」になっていた。
Geminiでも同じ問題が起きていた。既存の`title_seed`へユーザー自身の言葉を
渡すようにした(Domain判定は引き続き全文を使う)。

**Silent Mock fallbackの禁止(§9)**: 既定Providerが無条件に`"mock"`だった
ため、`GEMINI_API_KEY`設定済みでもProvider名を送らないクライアント
(Flutterは送っていない)へ黙ってMockを返していた——**実機でMockが出た
原因はこれ**。既定解決を`FORGE_DEFAULT_PROVIDER`→`gemini`→`mock`へ変更し、
レスポンスが`provider`/`simulated`を自己申告、Flutter側がバナーとバッジで
明示する。Mockの品質向上はこの問題の解決ではなく、**模擬と分かること**が
解決である(TD54)。

**Capability Vertical Slice(005 §32)**: 「地図で見たい」のような作れない
要求を検出し、作れないことを名指しした上で作れる形を仮説として提示、訂正を
CorrectionTarget(DATA/VIEW/EFFECT/PROBLEM)で分類する層を追加
(`capability.py`)。**Capability自動追加は採用しない**——Flutterが動的
コード実行不可のため物理的に成立しない(TD55、`FORGE-SELF-EXTENSION-ARCH-REVIEW.md`)。
安全判定(CONFIRM)が先、Capabilityの話は後という順序を明示的に固定した。
既存50セッションで挙動が1件も変わらないことを回帰確認済み。

**flutter analyze 77件 → 0件**: 同じSDK(3.44.9)を用意して実際に走らせた。
`dart fix`で17件、strict-inference由来の未型付けリテラル57件、
speech_to_text 7.xの`localeId`非推奨1件、他2件。

**Python環境(§004)**: `requirements.txt`に対応Python(>=3.11,<3.13)と
その理由(pydantic 2.7.4 / supabase 2.5.1が3.13のwheelを出していない)を
記録。`verify.ps1`は範囲内のインタプリタを選び、依存インストールが失敗
したらbackendテストへ進まない(import errorの山をテスト失敗として報告しない)。

**テスト**: forge_ai 521 / backend 802(skip 13) / Flutter 455、
`flutter analyze` 0件。

## Task067 — TD45解消・ASK Loop対策・Model Gateway(2026-08-12、FORGE-QUALITY-AI-INDEPENDENCE-003)

**Phase B(TD45)**: Domain Resolutionが「Curated定義が存在する」だけで
採用していた問題を解消。判定材料は既にコード内にあった
(`matched_concepts`が空=動詞だけで選ばれたDomain)ため、新しい閾値は
導入していない。血圧・読書等がgeneratedへ、日記・家計簿等はcuratedの
まま。Regression 20ケース追加(TD49)。

**Phase C(ASK Loop)**: 「分からない」「任せる」への無限ASK経路を、
Strategy Escalation(ASK→REPHRASE→OFFER_DEFAULT→SHRINK_SOLUTION)で
解消。高リスクだけはSTOP(勝手に仮定しない)。`repeated_question_count`の
定義も「同じkeyを同じ段で」へ修正(TD50)。

**Phase E〜I(Gemini非依存化)**: 既存`LLMAdapter`は十分だったため
作り直さず、不足4点(Task概念・計測・Fallback・Routing)だけを埋める
`ModelGateway`を追加。`LocalModelProvider`(OpenAI互換、Ollama固定
ではない)とProvider Benchmark harness、Impact分類データセット16ケースを
実装(TD51)。

**実行して見つけた実バグ1件**: `BenchmarkReport.winner()`が正答率0%の
`mock`を勝者に選んでいた(適合率の下限しか見ていなかった)。

**未達**: 実モデルでのLocal実行(§31 最低条件E)。サンドボックスは
`huggingface.co`がネットワークポリシーで拒否・GPU無しのため、モデル重みを
取得できない。手順は`docs/development/LOCAL_MODEL_SETUP.md`。

**Phase D(Scripted Conversation Set、§26)**: 50セッションのデータ
セットを追加(明確10/曖昧10/分からない5/任せる5/どっちでもいい5/
無関係5/途中変更3/UPDATE 4/高リスク3)。**実行した時点でPolicyの
実バグを3件検出**した:

1. 委任(「任せる」)検出が`OFFER_DEFAULT`を返し続け、段が永久に
   上がらなかった(15セッションで繰り返し質問、縮退が一度も発動せず、
   2セッション未決着)。
2. BUILD経路で`strategy`を渡し忘れ、縮退した事実が記録に残らなかった
   (`solution_shrink_count`が常に0)。
3. 委任判定が最新発話のみで、「任せる」→「うん」で委任が忘れられていた。

修正後: 平均質問数1.54→**1.20**、繰り返し質問17→**0**、縮退0→**20**、
未決着2→**0**。

**テスト**: 新規Python 45件。forge_ai 519件・Backend 773件、全green。

## Task066 — ニーズに合わせて「解の形」を選ぶ(2026-08-12、CEO「常にニーズに合わせた最適解を出せるようにして」)

Conversation Readiness(Task065)で「いつ作るか」は判断できるように
なったが、「**何を**作るか」は固定だった。`ForgeLanguageCompiler`は
Entityの中身に関わらず常に3タブCRUD(追加/一覧/編集 + フォーム +
record_list_view)を出力しており、買い物メモが欲しい人にも釣果記録と
同じ重さの道具を渡していた。

**実装**: `forge_ai/core/ir/solution_shape.py`(新規)。Entityの
フィールド構成から解の形を決定的に選ぶ。`CHECKLIST`(並べて消す、
1画面・タブ無し)と`RECORD_CRUD`(従来の3タブ)の2形。
`checklist`Stateの1項目`{id, text, done}`で情報を落とさず表現しきれる
場合(文字列1つ、または文字列1つ+真偽値1つ)だけ`CHECKLIST`にする
——形を軽くすることと情報を捨てることは別、という線引きを明示した。

あわせて`build_entity_synthesis_prompt()`を「項目は3〜6個」から
「本当に必要な数だけ。1個で足りるなら1個」へ変更した(形の選択だけ
直しても、合成が常に5項目返すのでは`CHECKLIST`に到達しないため)。

**Curated Domainへの影響はゼロ**(手作り7定義は全て4〜5 Fieldで条件に
非該当、回帰テスト化済み)。

**テスト**: 新規15件(`test_solution_shape.py`)。forge_ai 510件・
Backend 733件・Flutter 451件、全green。`CHECKLIST`出力が実物の
Backend Validatorを通ることを確認。

**未確認**: 実機Geminiでの`CHECKLIST`到達(無料枠の上限に到達したため
実行できず)。`RECORD_CRUD`側は実機確認済み。詳細はTECH_DEBT.md TD48。

## Task065 — Conversation Readiness / CONFIRM / 「はい、どうぞ」体験(2026-08-12、FORGE-CONVERSATION-READY-001)

Conversation Engineを、単なるターン制会話から「情報充足度・不確実性・
リスクを見てASK/BUILD/UPDATE/CONFIRMを決めるエンジン」へ進化させた。

**中心的な修正**: ターン数による強制BUILDの廃止。以前は
`force_ready = (not unknown_important) or (user_turn_count >= MAX_CONVERSATION_TURNS)`
で、重要な未知が残っていても3ターンでBUILDへ倒れていた。加えて監査で、
`if force_ready or llm_action in ("build","update")`という、より深刻な
経路が見つかった——**LLMが"build"と言えば未知の有無に関わらず常に
BUILD**していた。両方を廃止し、Readinessによる決定的な判断へ置き換えた
(詳細はDECISIONS.md D66・D67、TECH_DEBT.md TD46)。

**新設**:
* `conversation_policy.py` — Readiness / Question / Confirm / Build失敗
  分類の4つの決定的なPolicy。LLMを一切知らない純粋関数群。
* `ConversationReadiness`(5値)・`UnknownItem`(impact + reason)・
  `SafeAssumption`(value + reason)・`DecisionContext`(System Facts)。
* `conversation_metrics.py` — 構造化メトリクス。生の会話本文は保存せず、
  session_idもハッシュ化する。
* CONFIRMの正式統合(`ConverseConfirmResponse`、会話の1ターンとして返す)。
* BUILD失敗時のASKフォールバック(理解段階の失敗のみ。Validator/Repair
  の失敗はユーザーの情報不足として見せない)。
* 「はい、どうぞ」Moment(Frontend、合計1.5秒の3発話)。
* `ConversationConfirm`(Flutter側のOutcome)。

**発見・修正した実バグ2件**:
1. `MockLLMAdapter`に`"boolean"`の分岐が無く、文字列`"mock_result"`へ
   落ちていた。`bool()`変換が常にTrueになり、mock providerでの会話が
   **毎回CONFIRMへ倒れる**症状としてテストが検出した(既知の`"number"`
   バグと同種の見落とし)。
2. `/converse`導入以降、Cognitive Pipelineへ渡るのが長い`build_brief`に
   なったため、80文字超のタイトルが生成され、Validatorの`string_length`
   違反でBUILDが失敗していた(Repairでは直らない)。実機Geminiで再現・
   確認し、`clamp_title()`で全経路のタイトルを1〜80文字へ収めた。

**テスト**: 新規Python 84件(`test_conversation_policy.py` 40件・
`test_conversation_golden.py` 20件・`test_conversation_readiness_http.py`
12件・engine拡張ほか)。Conversation Golden Testは、最終JSONではなく
**会話そのもの**(質問回数・聞くべきことを聞いたか・繰り返し質問・
CONFIRMの正しさ)を評価する。forge_ai 495件・Backend 733件・
Flutter 451件、全green。

**ドキュメント**: docs/AI.md 6章(Readiness/Question Policy/Safe
Assumption/Build Failure Fallback)、docs/ARCHITECTURE.md 7章
(Conversation層の責務境界)、docs/ROADMAP.md Phase 7、
DECISIONS.md D66-D68、STATUS.md(新設)。

## Task064 — 作れるアプリの自由度: Entity定義をAIが合成できるようにした(2026-08-12、CEO「つくれるアプリの自由度をあげたい。トップレベルまで」)

**天井の正体**: `IRGenerator`は、記録するデータの型(Entity・Field・
型・選択肢)を`_ENTITY_DEFINITIONS`という手書きdictから引いており、
そこに載っている7 Domain(実機到達可能なのはTD39により5つ)だけが
型付きCRUDアプリ(タブ・record_list_view・日付ピッカー・選択肢・
スライダー・グラフ・編集・削除)になり、それ以外の依頼は例外なく
Checklist(文字列が並ぶだけ)へ落ちていた。つまり「作れるアプリの
種類」の上限は、Widget語彙数でもAIの賢さでもなく、**人手で書いた
Domain数(5)そのもの**だった。

**実装**: `forge_ai/core/ir/entity_synthesizer.py`(新規)。Curated
Domain Libraryに無いDomainについて、記録する1件分のデータ構造をAIに
設計させ、手書きテーブルと同じ表現(`EntitySpec`/`FieldSpec`、公開名へ
改名)で`IRGenerator.build_from_spec()`(公開)へ渡す。以降の経路は
合成と手書きを一切区別しない。AIの出力は決定的に検証・サニタイズし、
使えなければ`None`を返して従来のChecklistへ安全に落ちる(失敗しても
以前より悪くならない)。付随して`entity_synthesis` stageを
`PromptBuilder`・`MockProvider`・`ForgeAIProviderBridge`へ追加した。

**テスト**: `forge_ai/tests/test_entity_synthesizer.py`(新規34件、
大半は壊れた/悪意ある応答に対するサニタイズの確認)。forge_ai/側489件・
Backend側645件、全green。Golden file 7件を差分確認のうえ更新
(6件はDecision Trace追加のみ、1件はForm2画面→record CRUD 1画面)。

**ライブ確認**(実機Gemini): 「スーパーで買うものをメモしておきたい」→
`shopping_item`(item_name/quantity/estimated_price/store_name/
is_purchased)、「会議の議事録を残したい」→ `meeting_minutes`
(title/meeting_date/participants/summary/action_items)で3タブCRUD。
いずれも以前はChecklistにしかならなかった依頼である。Frontend側の
変更は不要だった(Flutter Runtimeは既に同じ形へ対応済みのため)。

**未解消として記録した重要な発見**: 「毎日の血圧を記録したい」は
Domain分類が`diary`(Curated)へ寄るため、Curated優先の原則により
手書きdiary定義(title/content/mood/date)が使われ、合成より悪い結果に
なる。優先順位の変更はCurated 5 Domainの回帰リスクがあるため今回は
見送り、TECH_DEBT.md TD45へ次の一手の案とともに記録した。

## Task063 — 生成アプリの視覚品質: design_tokens(配色テーマ)を全Domainへ拡大(2026-08-12、CEO「アプリストアレベルの品質にするにはどうすればいいか」)

CEOから「widgetの充実が良いのか、生成できるAIが良いのか、実際に
作られるアプリのクオリティをアプリストアにあるようなレベルにする
にはどうすればいいか、めちゃくちゃ考えて、多次元レベルで色々な
角度から疑って、これだ！って答えが出たら実装してみて」という指示を
受け、Widget語彙・生成AIの精度・視覚的デザイン品質の3方向を検討した
結果、「`design_tokens`(配色・角丸・余白のテーマ)という、Product
Quality Sprint1で既に実装・Flutter側の描画対応も完了していた資産が、
Curated Domain Library(5 Domain)にしか適用されておらず、実際に
生成されるアプリの大半(shopping・survey・travel等、legacy
`Compiler`経路の10 Domain)はFlutter既定のMaterial配色のままだった」
という取りこぼしが、最もレバレッジの高い改善だと判断した(詳細は
TECH_DEBT.md TD44)。

**実装**: `_DESIGN_TOKEN_PRESETS`を`forge_ai/core/ir/
forge_language_compiler.py`から`forge_ai/core/compiler.py`(循環
import回避のため、こちらが単一の定義元)へ移動し、`design_tokens_
for_style()`・`design_tokens_for_domain()`(新設、Domain→visual_style
マップ経由でプリセットを選ぶ)として再構成。`Compiler.compile()`の
Checklist経路・Form Template経路の両方に適用した。付随して、
`design_tokens`がValidator上v1.5以降専用のため、両経路のversionを
"1.0"/"1.2"から"1.5"へ引き上げた(使用Widget/Action/State型は
上位互換の範囲内、挙動は不変)。Flutter側の変更は不要(Sprint1の
実装がversion/Domain非依存のため)。

**テスト**: `forge_ai/tests/test_compiler.py`に`TestCompilerDesign
TokensByDomain`(新規4件)を追加、既存version固定値アサーション10件を
更新。forge_ai/側451件・Backend側645件、全てgreen。uvicorn+curlで
`/api/v1/ai/generate`をライブ確認: 「買い物リストを作りたい」
(shopping)が`#D68C45`、「満足度アンケートを作りたい」(survey)が
`#5C6470`という異なる配色で、実際のSchema Validatorを通過して
返ることを確認した。

## Task062 — FORGE-PRODUCT-VISION-002続き: フロントエンド統合(2026-08-11、同日中、CEO「自由度はどれくらいなのだろう？今最新で与えている情報を優先にしてほしい」)

report.mdで「CEO確認が必要」として保留していたフロントエンド統合
(Home画面の文言変更、Inspiration Cardsの遷移先変更)について、CEOから
指示書28章の確認事項リストのどれにも実際には当てはまらない(可逆な
UI/ロジック変更)という指摘を受け、保留を撤回して実装した。

### 実装
`HomeScreen`の見出しを「困ってることある？」的な文言へ変更し(design
doc C.1、Space)、送信の遷移先を単発生成の`GenerationFlowScreen`
(無変更のまま残す)から新設`ConversationFlowScreen`(複数ターンの
会話、`/converse`)へ切り替えた。`GeneratedAppHostShell`へ「ここを
変える」ボタンを追加し(`StatefulWidget`化)、Held画面(Home・My Apps
から開いたアプリ)からUPDATE(TD40)へ戻れるようにした
(design doc C章、Held→Forming→Held)。

### Widget Testで発見・修正した実バグ
`ConversationTurnRequest`(Riverpod `.family`のキャッシュキー)を
`_sessionId`から毎回組み立て直していたため、ASKレスポンス処理の
副作用で、ユーザーがまだ何も送っていないのに同じ発話でもう一度
`/converse`を呼んでしまう実バグを発見した。目視では気づけない種類の
バグ(結果は`_handledCurrentTurn`ガードで画面に反映されないため)で、
実際のGemini会話であれば無駄な往復とBackend側の会話履歴の重複を
招いていた。リクエストを`_sendReply()`時にのみ確定するスナップショット
方式へ変更して修正した。詳細はTECH_DEBT.md TD43参照。

### テスト
新規Dart 8件、既存E2E/Widget Testの追従修正を含め、Dart側全447件が
green。`flutter analyze`は0エラー。

## Task061 — FORGE-PRODUCT-VISION-002続き: /converseと/updateを結線(2026-08-11、同日中、CEO「自由度はどれくらいなのだろう？今最新で与えている情報を優先にしてほしい」)

report.mdで「次の一手」として残していた、「`/converse`内で新しい問題か
既存ツールへの変更要求かを判定する」を実装した。CEOから、フロントエンド
統合等を「CEO確認事項」として保留していた判断について、指示書の文面に
過度に慎重になっていたと指摘を受け、可逆な変更として直ちに実施した。

### 実装
`ConversationEngine.step()`が`has_existing_tool: bool`引数を受け取り、
`True`の場合のみ`next_action="update"`を選びうる(LLMの自己申告を
鵜呑みにしない決定的上書きルールは既存方針を踏襲)。`ConverseRequest`へ
`current_document`(任意)追加。`update`と判定された場合、既存の
`ForgeOperationEngine.apply_update()`(TD40)へそのまま委譲する。

### 実機確認の過程で発見・修正した実バグ3件
1. `/converse`のProvider呼び出しに例外処理が一切無く、Gemini APIの
   レート制限時に親切な日本語メッセージが失われ汎用500エラーへ落ちて
   いた(修正: `ProviderError`への変換を追加)。
2. `MockLLMAdapter`がJSON Schemaの`"number"`型を処理しておらず、
   `ConversationEngine`の`confidence`フィールドで`float("mock_result")`
   という実クラッシュが発生していた(修正: `"number"`分岐を追加)。
3. 新規テストファイルが`app.main`をFeature Flag設定前にimportし、
   `test_workspace_router.py`・`test_folder_router.py`を巻き込んで
   壊すテスト分離バグを発見・修正した。

いずれも実際に`uvicorn`+`TestClient`/`curl`を叩いて初めて表面化した
もので、Unit Testだけでは検出できなかった(TD37と同じ教訓の再確認)。

### 検証
新規Python 20件、既存backend全テストと合わせ645件、全てgreen。
`/converse`のエラー変換自体はライブGemini経由で正しく動作することを
確認したが、Gemini無料枠の**日次クォータ**をこのセッションの検証作業
(TD37以降、多数のライブ呼び出し)で使い切っており、「実際にGeminiが
会話中でupdateを自発的に選ぶ」ところまでのライブE2E確認は完了できな
かった(正直な申告、TD42参照)。分岐ロジック自体は`test_conversation_
engine.py`のFakeProviderテストで確認済み、`apply_update()`本体は
Task060で既にライブ確認済み。

## Task060 — FORGE-PRODUCT-VISION-002続き: Forming Operation(UPDATE)実装(2026-08-11、同日中、CEO「実装できたの？できるまでやって」)

Task059でTD40(UPDATE=生成後に会話で「育てる」機能)を「Gemini
`responseSchema`の再帰制約が未検証」という理由で設計のみに留めていた
ところ、CEOから「実装できたの？できるまでやって」という指示を受け、
同日中に技術検証・実装・実機確認まで完了させた。

### 技術検証
`responseSchema`へ「type: object」とだけ渡し`properties`を書かない形
(Forge DocumentのWidget木のような、再帰的で事前に形を確定できない
構造)を実機で試したところ、その部分が**空オブジェクトで返ってくる**
ことを確認した(既存データを丸ごと失う、深刻な失敗モード。懸念は
正しかった)。`responseSchema`を送らずフリーフォームJSON生成にすると、
既存構造を維持しながら要素を追加できることも確認し、こちらを採用。

### 実装
`GeminiProvider.complete_structured()`が`response_schema={}`の場合に
`responseSchema`送信自体を省略するよう拡張(既存の非空schema呼び出しは
無変更、回帰テストで確認)。新規`ForgeOperationEngine.apply_update()`
(`backend/app/ai/runtime/forge_operation.py`)が、Validator不合格時に
1回だけエラー内容をプロンプトへ追記して再生成する(最大2回、無限
リトライ禁止の既存方針を踏襲)。新規`POST /api/v1/ai/update`追加。

### 実機確認
`/converse`で生成した3件の買い物チェックリスト(牛乳・食パン・卵)に
「よく買うものを上に置きたい。カテゴリ分けもしたい。」を`/update`で
適用。1回目はValidator不合格、2回目(Repair往復1回)で合格。既存3件を
正しく3つのcategory別checklistへ分割・再配置し、対応する追加ボタンも
生成した。指示書6・16・18章の例がそのまま動くことを確認した。

新規Python 9件(`test_forge_operation.py`)+`GeminiProvider`回帰テスト
2件、既存backend全テストと合わせ633件、全てgreen。詳細はTECH_DEBT.md
TD40の追記・`docs/reports/FORGE-PRODUCT-VISION-002-report.md`参照。

## Task059 — FORGE-PRODUCT-VISION-002: Conversation Engine(2026-08-11、CEO「『アプリを作るAI』から『困りごとを話すと道具が生まれるAI』への製品思想更新」)

CEOより、Forgeの製品思想を「アプリ生成AI」から「困りごとを話すと道具が
生まれるAI」へ更新する指示書を受けた。現物監査(Phase A)・設計
(Phase B〜D、`docs/spec/FORGE_PRODUCT_VISION_002_CONVERSATIONAL_
ARCHITECTURE.md`・ADR-014)・実装(Phase E)まで一気通貫で対応した。

### 監査結果
「Space/Forming/Held」は新規語彙(既存に無し)。既存の`needs_
confirmation`は「ASK」の原型として既に存在するが単発の脇道。
Confidence計算基盤(ADR-007)は既に成熟。「UPDATE」(生成後に会話で
育てる)はバックエンドに一切存在しない、最大のギャップと確認した。

### 実装(ADR-014: Cognitive Pipelineを一切変更せず、外側に薄い意思決定層を追加)
新規`ConversationEngine`(`backend/app/ai/runtime/conversation_
engine.py`)が、1ターンにつき1回の`complete_structured()`呼び出しで
ASK/BUILDを判定する。LLMの自己申告を鵜呑みにせず、`unknown_important`
が空・ターン数上限到達の場合は決定的にBUILDへ倒す。BUILDと判定した
場合、会話全体を要約した`build_brief`を既存の`PromptPipeline.run()`へ
そのまま渡す(Forge Language・Validator知識は持たない、既存資産の
完全再利用)。新規`POST /api/v1/ai/converse`エンドポイント追加、既存
`/generate`・`/generate/confirm`は無変更(後方互換)。

### テスト・実機確認
新規Python 21件(`test_conversation_store.py`12件・
`test_conversation_engine.py`9件)、既存backend全624件・forge_ai全451件
が引き続きgreen。`uvicorn`+実Geminiで3つの会話を実際に流し、
「買い物で忘れる」→1ターンでBUILD、「薬を飲むのを忘れる」→既存
Pipeline側のプライバシー検出が発火(ConversationEngine自身の質問より
先に安全側で止まった、正直な評価は報告書参照)、「忘れっぽくて
困ってる」→2ターンでASK→BUILDといういずれも指示書の理想例に近い
形で動作することを確認した。

### 未実装・CEO確認事項
UPDATE(Forming Operation、生成後に会話で育てる)は、Gemini
`responseSchema`の再帰制約が未検証というリスクを正直に申告し、設計のみに
留めた(TD40)。フロントエンドの主要導入体験(Home画面文言・
Inspiration Cardsの遷移先)の変更は、指示書28章「製品思想そのものを
変更する判断」に該当するため実装せず、CEO確認事項として明示した。
詳細は`docs/reports/FORGE-PRODUCT-VISION-002-report.md`参照。

## Task058 — Widget Vocabulary Expansion 第3弾: slider(FORGE-AI-QUALITY-001続き、2026-08-11、CEO「要は、一気に検証を進めたい。なので、壊れてる?って機能でもどんどん追加してくれ。あとでなおす。」)

TD34(v1.6)・TD36(v1.7)に続く、Widget Vocabulary Expansion第3弾。
上限・下限が決まった数値入力(reading_logの「評価(5段階)」等)を、
`text_field`への自由入力ではなく専用の`slider`Widget(Flutter標準の
`Slider`)で表現できるようにした。既存の"number"型state(v1.2で導入
済みだが、これまで消費するWidgetが1つも無かった)をそのまま使い、
新しいstate型は追加していない。

### 実装
`Field`(`ir_types.py`)へ`min_value`/`max_value`を追加、reading_logの
`rating`Fieldへ`min_value=1, max_value=5`を設定。`schema_validator.py`
へv1.8のスキーマ検証を追加(`backend/tests/test_schema_validator_v1_8.py`
14件)。`forge_language_compiler.py`の`_build_field_inputs()`へslider
分岐を追加、ドキュメントversionを"1.8"へ(`test_forge_language_compiler.py`
へ`TestForgeLanguageCompilerV1_8WidgetVocabularyExpansion`6件を追加)。
Dart側は`ForgeSliderWidgetNode`・`buildSlider()`
(`widget_registry_v1_8.dart`)・`ForgeRuntimeState.setNumber()`を新設。

### TD37の教訓の適用
`widget_registry_core.dart`の`typeNameOf()`(sealed classの網羅的
switch式)へ、`ForgeSliderWidgetNode`のクラス定義を書いた直後に
対応するcaseを追加した(TD37で発見した「Widgetノードは追加したのに
描画の入口へケースを足し忘れ、一度も描画できない」という再発防止)。
同じ理由で複製switchを持つテスト専用ファイル
(`mock_generator_renderer_contract_test.dart`)も同時に更新した。
`flutter analyze`で0エラーを確認。

### 検証結果
新規Widget Test(`v1_8_widget_vocabulary_expansion_test.dart`、4件)で、
sliderを実際に`ForgeDocumentView`経由で描画・ドラッグ操作・Recordへの
反映まで確認した。Dart側は全439件(既存435件+新規4件)、Python側は
backend 606件・forge_ai 451件が通ることを確認した。

### TD39: sliderのライブ検証で発見した、無関係の重大な既存バグ
`uvicorn`+実Geminiで`reading_log`ドメインのアプリ生成を試みたところ、
「読んだ本を記録して評価をつけたい」が`diary`ドメインへ分類され、
reading_log固有のスキーマが一度も使われないことが判明した。調査の結果、
`SUPPORTED_DOMAIN_CATEGORIES`に含まれる7 Domainのうち`todo`・
`reading_log`の2つは、実際の分類結果である`DomainCategory` Enumに
対応するメンバーが存在せず、**実機の生成パイプラインからは構造的に
到達不可能**であることが分かった(直接`domain_category`を指定する
テスト・スクリプトからしか到達できない)。sliderの唯一のトリガーが
reading_logの`rating`Fieldであるため、現状sliderは実機生成では
一度も出力され得ない。修正には`DomainCategory`Enumと分類器の語彙
拡張という別範囲の作業が必要なため、このセッションでは発見・記録に
留めた(CEOの「あとでなおす」の範囲内と判断)。詳細はTECH_DEBT.md
TD38・TD39参照。

## Task057 — Flutter SDKを実際に取得し、Dart側を初めて実機検証(FORGE-AI-QUALITY-001続き、2026-08-11、CEO「出し惜しみせず、完璧を求めてくれ」)

これまで数セッションにわたり「ClaudeのサンドボックスにFlutter SDKが
無く、ネットワークも無いため検証不可能」という前提でDart側の全実装を
未検証のまま報告してきたが、実際に到達性を調べ直したところ
`storage.googleapis.com`(Flutter公式配布元)・`pub.dev`が到達可能
であることが判明。Flutter SDK(stable 3.44.9)を実際にダウンロード・
展開し、`flutter pub get`・`flutter analyze`・`flutter test`を
このセッションで初めて実行できた。

### TD37: 4種の新規Widgetが、実は一度も描画できていなかった(発見・修正)
`flutter analyze`を実行した結果、`widget_registry_core.dart`の
`typeNameOf()`(Widget描画の入口となる、sealed classの網羅的switch式)
に、TD34・TD36で追加した`choice_field`・`bar_chart`・`date_field`・
`tab_view`の4ケースが1つも登録されていない、コンパイルエラー
(`non_exhaustive_switch_expression`)を発見した。Backend側のpytestは
「正しいJSONを生成できているか」しか検証しておらず、「実際にFlutterで
描画できるか」は検証範囲外だったため、これまで一度も気づけなかった。
`typeNameOf()`へ4ケースを追加して修正。

副次的に、このセッションとは無関係な既存バグ3件も発見・修正した:
`shared_preferences_app_library_repository.dart`(TD30)の型エラー、
E2Eテスト2件のFinderが2026-08-10のUI再デザイン(ElevatedButton→
InkWell+DecoratedBoxのグラデーションCTA)に追従していなかった問題、
Widget Test 1件のスクロール漏れ。

### 検証結果
新規Widget Test(`v1_6_v1_7_widget_vocabulary_expansion_test.dart`、
9件)を`ForgeDocumentView`経由の実描画で新設し、choice_field/
bar_chart/date_field/tab_viewそれぞれが実際に動作することを確認した
(date_fieldは実際に`DatePickerDialog`を開いて日付を選ぶところまで)。
既存のDartテスト全件を含め、435件が通ることを確認した(Python側
1024件と合わせて合計1459件)。KNOWN_ISSUES.mdへFlutter SDKの
セットアップ手順を記録し、次回セッション以降も再現できるようにした。
詳細はTECH_DEBT.md TD37参照。

## Task056 — Widget Vocabulary Expansion 第2弾(FORGE-AI-QUALITY-001続き、2026-08-11、CEO「全て実装してくれ。確認もしなくて良い、ゴールは示している。つくってくれ。」)

前回「次に効果が大きいのは画像対応と、複数画面・ナビゲーション」と
述べた候補について、確認を挟まず実装を進めた。

**調査の結果、複数画面によるNavigator遷移は見送った**: Flutter
Runtimeを読んだところ、画面遷移のたびに独立した新しい
`ForgeRuntimeState`が生成される設計であり、素朴に複数`screens`へ
分割すると「一覧画面」と「追加画面」で`records`Stateが同期せず、
「追加したはずのデータが一覧に出てこない」壊れたアプリを生成して
しまうことが分かった。検証手段(Flutter SDK)が無い中でこの種の
不具合を生む実装を確認無しで進めるべきではないと判断し、見送った
(TECH_DEBT.md TD36に詳細記録)。

### TD36: `date_field`/`tab_view`の2 Widget追加(v1.7)
新規パッケージ依存を追加せず、Runtime側の制約内で安全に実装できる
2種を追加した。

* `date_field`: カレンダー選択(`showDatePicker()`)。TD33の
  placeholder応急処置を置き換える。
* `tab_view`: 単一画面内の「追加」「一覧」「編集」を、`divider`
  区切りの縦積みから、タブ切り替えへ変更。`TabBarView`
  (`PageView`ベース、`SingleChildScrollView`内で高さ無制限になり
  レイアウトエラーになりうる)は避け、選択中のタブだけをその場に
  描画する自作の切り替えロジックで実装した。

Python側は新規テスト29件(schema_validator側19件+compiler側10件)を
追加した上で全テスト1024件(回帰なし)を確認し、`uvicorn`起動+HTTP
経由でhousehold_budget・fishing_log等を再生成、`version: "1.7"`・
`tab_view`(3タブ)・`date_field`が正しく反映されていることを確認した。

Dart側は既存Widget実装と同じパターンを踏襲したが、Flutter SDK不在に
より未検証。詳細はTECH_DEBT.md TD36参照。

## Task055 — TD35根本原因の特定・修正(FORGE-AI-QUALITY-001続き、2026-08-11、CEO「バグは今後見つかったら徹底的に無くして」)

Task054で「未解決」として記録したTD35(実`uvicorn`経由の一部
リクエストが誤った「APIキー未設定」エラーで失敗する)を、CEOの
指示を受けて再調査し、根本原因を特定・修正した。

**真の原因は2つの独立した事実の組み合わせだった**:

1. `backend/.env`を実際に読み込むコードがどこにも存在しなかった
   (`python-dotenv`は`requirements.txt`の依存にあったが、呼び出し
   箇所が無かった)。
2. household_budget等IR経由の7 Domainは`ForgeLanguageCompiler`が
   完全に決定的で、Geminiを一切呼び出さない設計だった。そのため
   `.env`が読み込まれていない状態でも「成功」して見えており、
   実際にGeminiを呼ぼうとする`GENERIC`/Legacy Domain(「やること
   リスト」等)だけが、読み込まれていないキーの不在に突き当たって
   いた。

**訂正**: この発見に伴い、Task054で「実際にGemini APIで生成した」と
記録していたTD34の検証記述を訂正した——household_budget等の検証は
HTTP/Validatorレイヤーの配線確認としては有効だったが、Gemini接続
そのものの確認にはなっていなかった。

**修正**: `backend/app/main.py`の先頭へ`load_dotenv()`を追加。新規
テスト2件(サブプロセスでの実接続確認+ソースレベルの軽量回帰)を
追加し、全996件(回帰なし)を確認。手動でのexport無しの、まっさらな
シェルから`uvicorn`を起動し、以前は確実に失敗していた「やること
リストを作って」等が、実際にGemini経由のバラエティのある文言で
成功することを実機確認した。詳細はTECH_DEBT.md TD35参照。

## Task054 — Widget Vocabulary Expansion(FORGE-AI-QUALITY-001続き、2026-08-11、CEO「凍結宣言をすべて解除します。ひきつづきすすめて。」)

CEOから「いまの生成できるアプリはテキストとチェックボックスぐらいの
機能しか持たせられないってこと?ゴールはわかってる?」という直接的な
問いを受け、Widget Registryが14種のままであること、`docs/spec/
LANGUAGE_FREEZE.md`が実は一度も正式に凍結宣言されていなかったこと
(2章のFreeze条件が未達成のまま)、それにより製品自身の例文
(「収支をグラフで見たい」)すら実現不可能な約束になっていたことを
報告。CEOから凍結解除の明示的な承認を得て着手した。

### TD34: `choice_field`/`bar_chart`の2 Widget追加(v1.6)
新規パッケージ依存を追加せず、Flutter標準Widgetのみで実現できる2種を
追加した。

* `choice_field`: ドロップダウン選択(`DropdownButtonFormField`)。
  TD33のplaceholder応急処置を置き換える。
* `bar_chart`: `record_list`の数値Fieldを棒グラフ表示(1 Record =
  1本の棒、集計は行わないPhase1最小実装)。

Python側(`schema_validator.py`のVersion "1.6"新設、
`forge_language_compiler.py`のWidget出力ロジック)は、新規テスト33件
(schema_validator側21件+compiler側12件)を追加した上で全テスト995件
(回帰なし)を確認し、さらに`uvicorn`起動+HTTP経由で
`household_budget`(「収入や支出を記録して、月ごとの収支をグラフで
見たい」という例文そのもの)・`fishing_log`・`inventory`を再生成、
実際に`choice_field`(有効なoptions付き)・`bar_chart`(正しい
value_field/label_field)がJSONへ反映されていることを確認した。
**訂正(Task055)**: この検証は当初「実際にGemini APIで生成した」と
記録していたが、これは不正確だった——household_budget等の検証は
HTTP/Validatorレイヤーの配線確認としては有効だが、Gemini接続そのものの
確認にはなっていなかった。詳細はTask055・TECH_DEBT.md TD35参照。

Dart側(`forge_document.dart`へのWidget Node追加、新規
`widget_registry_v1_6.dart`)は、既存Widget実装と同じパターンを踏襲して
実装したが、このセッションを通じて一貫している既知の制限
(Flutter SDK不在)により未検証。詳細はTECH_DEBT.md TD34参照。

### TD35(新規発見): 実`uvicorn`経由の一部リクエストが誤った「APIキー未設定」エラーで失敗する → **Task055で根本原因を特定・解消**
TD34の実機検証中に偶然発見。当初は根本原因未特定として記録したが、
Task055で解消した(詳細はTask055参照)。

## Task053 — バグハント(FORGE-AI-QUALITY-001続き、2026-08-11、CEO「がっつしバグ全部探して潰していってよ」)

指示を受け、Backend/forge_ai側で実際に検証できる範囲を体系的に洗い直した。

### TD32: Repair Loopが本番経路で呼ばれてはいたが、一度も実際に修正できていなかった
TD17(Repair Engine)の記述を訂正する過程で発見。`to_repair_issues()`が
`ValidationIssue.category`(4値の大分類)を渡していたが、`RepairEngine.
_try_fix()`は具体的なルール名で判定していたため一致せず、Repair Loopは
「毎回呼ばれるが何も直せない」状態だった。加えて、想定していた2つの
「既知パターン」自体、実際のValidatorには存在しないルールだったことも
判明した。`e.rule`を渡すよう修正し、実在する`string_length`(app.title
パス限定)への対応を追加。本物のValidatorを使った回帰テストで確認した。
詳細はTECH_DEBT.md TD32参照。

### TD33: record_list系Domainのchoice/date型Fieldが、有効な入力形式を一切示さないまま高確率で入力を弾いていた
`household_budget`・`inventory`・`diary`を実際にGemini APIで生成し、
JSONの中身を1フィールドずつ確認して発見。choice型Field(カテゴリ・
気分等)はplaceholderがFieldラベルのみで、Dart Runtime側
(`ForgeFieldValueParser._parseChoice()`)は選択肢との完全一致を要求する
ため、素直な入力の大半が送信後に初めて弾かれる設計だった。同じ調査で
date型Fieldも同様の問題(YYYY-MM-DD形式の指定がどこにも無い)を発見した。
いずれも既存の`text_field`+`placeholder`のみで(新しいWidget型を追加
せず)選択肢・形式を事前に示すよう修正した。回帰テスト4件を追加、実際に
4 Domain(household_budget/inventory/diary/fishing_log)で実機確認した。
詳細はTECH_DEBT.md TD33参照。

### ドキュメントの棚卸し
同じ手法で他の「未実装」表記も確認し、TD20(Output Safety)・
TD21(Prompt Injection Guard)・TD22(スキーマバージョン管理)が実は
実装・実機確認済みなのに「解消済み」マークを付け忘れていたことも発見・
訂正した。

### 全テスト
forge_ai・backend込み全体で965 passed, 12 skipped(回帰なし)。

### 確認したが問題無しと判断した箇所
- IR経由の5 Domain(household_budget/habit_tracking/inventory/
  fishing_log/diary)を実際にGemini APIで再生成し、いずれも
  `valid: true`であることを確認した。
- Number型Fieldの検証・エラーメッセージは十分自明(「数字で入力して
  ください」)であり、choice/date同様の事前ヒント追加は不要と判断した。
- 「checklist item idの重複が検出されない」という既知のギャップ(TD5)
  は、実際のCompilerが常に連番で一意なIDを生成するため実害が無い
  ことを再確認した(理論上の制限として記録済みのまま据え置き)。

## Task052 — 信頼性面の実機調査(FORGE-AI-QUALITY-001続き、2026-08-11、CEO「進められるところをどんどん進めてください」)

Task051(ローカル永続化)がCEO確認待ちの間、検証可能なBackend/forge_ai側の
品質改善を継続した。多数の多様なプロンプト(曖昧な入力・複数意図混在・
ニッチなジャンル・個人情報寄り・記号のみ等15件)を実際に`uvicorn`+実Gemini
APIへ連続送信し、クラッシュ・不適切なエラー表示が無いか確認した。
クラッシュは無かったが、2件を発見・修正した。

### TD31: Gemini無料枠のレート制限(429)が生のエラーJSONのまま表示されていた
プロンプトを連続送信した際に実際に429(無料枠のレート制限、実測20回程度)
が発生し、`"RESOURCE_EXHAUSTED"`等のGoogle API固有の英語技術用語が
そのままユーザー向けエラーメッセージに出ることを確認した。429の場合のみ、
原因と対処法がわかる日本語の案内文言を先頭に出すよう修正した(生の詳細は
末尾に残す)。回帰テスト1件を追加。

### TD17の記述訂正
「Repair EngineはStub/Mockでまだ実際に呼ばれない」という記述が、実際には
`prompt_pipeline.py`の本番経路が`forge_ai.repair.repair_engine.RepairEngine`
を実際に呼び出しているという実態と食い違っていたため訂正した(削除せず、
2026-08-11追記として旧記述の下に残した)。

### TD32: Repair Loopが本番経路で呼ばれてはいたが、フィールド取り違えで実際は一度も修正できていなかった
TD17を訂正する過程で発見した、より深刻な実バグ。`forge_ai_adapter.py`の
`to_repair_issues()`が`ValidationIssue.category`(4値の大分類:
syntax/schema/semantic/runtime_safety)を`RepairIssue.category`へ渡して
いたが、`RepairEngine._try_fix()`は具体的なルール名(`"string_length"`
等、実際には`ValidationIssue.rule`に入っている)で判定していたため、
一度も一致せず、Repair Loopは「毎回呼ばれるが何も直せない」状態だった。
加えて、既知パターンとして想定していた`"missing_app_title"`・
`"empty_checklist_state"`自体、実際のValidatorには存在しないルールだった
ことも判明した(app.title欠落・checklist空はどちらも正常な状態として
許容されている)。`category=e.rule`への修正、および実在する
`"string_length"`(app.titleパス限定)への対応を追加し、本物の
Validatorを使った回帰テストで確認した。

### 副次的な発見(バグではないと判断したもの)
「植物の水やり記録」「ペットの餌やり記録」「映画鑑賞記録」等、専用Domainが
存在しないニッチな入力はdiary(日記)Domainへ分類された。専用Domainが
無い以上、diaryへのフォールバックは妥当な挙動と判断し、対応不要とした
(新しいDomainを追加するかどうかは、より大きなスコープ判断のため今回は
見送った)。

## Task051 — AI生成アプリのローカル永続化(FORGE-AI-QUALITY-001続き、2026-08-11、CEO「アプリストアで人気レベルのアプリをつくれるようなクオリティにするには」)

CEOから「考えて考えて疑って考えて疑って考えてから実装して」という指示を
受け、実装前に実コードを調査して根拠を積み上げた。結論: 「app store
品質」に必要な要素のうち、**最も致命的だったのは見た目の作り込みでは
なく、生成したアプリの状態(チェックリストの中身・家計簿の記録等)が
アプリを閉じるたびに消えるという、そもそもの実用性の欠如だった**
(`ForgeStateStore`がメモリ内Mapのみで永続化していないことをコードで
確認。`KNOWN_ISSUES.md`に既に記録されていた既知の意図的スコープ外
だった)。

Backendの`apps`/`app_versions`テーブル+Supabaseというサーバー側同期
(ROADMAP.md Phase3の元々の想定)はCEO側の外部サービス設定が必要なため
見送り、既存の`shared_preferences`(アプリ定義の保存に既に使っている
仕組み)を実行時Stateにも拡張する、ローカル永続化を実装した。

* `ForgeStateValue`(`forge_document.dart`)へ`toJson()`を追加
  (`fromJson()`と対称)。
* `mergePersistedState()`: 保存済みの実行時Stateを、文書の初期値へ
  安全にマージ(型不一致・破損データは黙って無視して初期値へ
  フォールバックする、多重防御)。
* `AppLibraryRepository`/`SharedPreferencesAppLibraryRepository`へ
  `loadRuntimeState`/`saveRuntimeStateForScreen`/`deleteRuntimeState`
  を追加。
* `ForgeScreenView`が状態変化(`notifyListeners`)のたび自動保存する
  よう配線(My Apps・ホーム画面の「最近のアプリ」・履歴・生成直後の
  プレビューの計4箇所)。

Unit Test 2ファイル(`toJson`/`mergePersistedState`のround-trip・境界
値テスト、および新規Repositoryメソッドのテスト)を追加。**Flutter SDKが
この環境に無いため、構文レビューと括弧バランスの機械チェックのみで、
実行は一切できていない。CEO環境での`flutter test`実行が必須。**
詳細は`TECH_DEBT.md` TD30・`KNOWN_ISSUES.md`参照。

### 今回あえて着手しなかったこと(優先順位の根拠)
「app store品質」に必要な他の要素(Widget語彙の拡充・画像/アイコン
対応・アニメーション・オフライン対応の強化・実機/実ブラウザでの検証・
App Store申請要件)も検討したが、いずれも「そもそも入力したデータが
消える」という土台の欠陥よりは優先度が低いと判断し、後回しにした。
次に着手するとすれば、実機での動作確認(この永続化機能を含む)が
最優先。

## Task050 — 生成品質の実機調査・修正(FORGE-AI-QUALITY-001、2026-08-11、CEO「生成できるアプリのクオリティを最大限にしたい」)

CEOが提示した4方向(色々なジャンルで実際に生成→不具合修正/
primary_concept選定の見直し/Design Critic評価範囲拡大/Widget・
Template種類の拡充)のうち、まず最優先(CEO推奨)の「実際に生成して
不具合を見つけて直す」を実施した。日本語プロンプト11件を`uvicorn`+
実Gemini APIへ実際に投げ、出力(Domain分類・タイトル・初期データ)を
1件ずつ確認し、2つの実バグを発見・修正した。詳細は`TECH_DEBT.md`
TD26・TD27参照。

### TD26: Checklist系Domain(10種)で、初期データが常に画一的な
決め打ち値になっていた
`forge_ai/core/compiler.py`の`Compiler.compile()`が、Provider(Gemini)の
応答から`title`しか読み取っておらず、初期データは静的テーブル
(`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`)のみに依存していた。「満足度
アンケート」も「習い事の満足度アンケート」も常に同じ`['最初の質問']`に
なる、という不具合を実機で再現した。`build_compile_prompt()`・
`_RESPONSE_SCHEMAS["compile"]`・`Compiler.compile()`の3箇所を修正し、
Providerが返す`example_items`(依頼内容に即した具体例)を静的テーブルより
優先するようにした(MockProvider・既存の実LLM未接続テストは
`example_items`を返さないため、既存動作への影響は無い)。修正前後を
実機で比較し、「満足度アンケートを作って」の初期データが
`['最初の質問']`→実際の質問文3件に変わったことを確認した。

### TD27: 「通院記録」「勤怠」がdiary Domainへ誤分類されていた
`forge_ai/core/lexicon.py`の`CONCEPT_KEYWORDS`に「通院」「勤怠」の
エントリが無く、`ACTION_KEYWORDS`の「記録」→`add_entry`(diaryの
action)のみが一致してしまうため、hospital/attendance Domainを差し置いて
diaryへ誤分類されていた(実機で確認・再現)。2エントリを追加し、
それぞれ正しくhospital(Privacy確認フローへ合流)・attendance
(既存のstatus概念共有によるDomain確認フローへ合流)へ分類されるように
なったことを実機で確認した。

### テスト
`forge_ai/tests/test_compiler.py`へ`TestCompilerProviderExampleItems`
(4件)、`forge_ai/tests/test_v03_domain_inference_golden.py`へ
`CONFIRMATION_CASES`2件+専用の回帰テスト1件を追加。forge_ai全408件・
backend込み全944件が回帰なしで通ることを確認した。

### primary_concept選定メカニズムの一般化(TD24続き)
CEOが選んだ4方向のうち「『主役となる概念』の選び方自体を直す」に
対応した。全15 Domainの`typical_concepts`を精査し、「先頭Conceptが
Domain判定のトリガーに過ぎず主役には不向き」という問題を持つのは
travelの`"destination"`のみと確認した上で、travel専用だった
Concept名の直書き許可リスト(`_PREFER_AS_PRIMARY_WHEN_MENTIONED`)を、
`DomainConcept.primary_candidate: bool = True`という一般的なDomain
定義側メタデータへ置き換えた(`domain_model.py`・
`planning/application_planner.py`)。選定ルール自体は変えず、将来
別Domainで同種の問題が見つかった場合に`application_planner.py`側の
変更無しで対応できるようにした、という位置づけ(「言及された概念を
無条件に優先する」という、より野心的な汎用化は、"price"のような
属性概念が誤って昇格するリスクを実際に確認したため見送った)。
新たにtravelの`accommodation`が主役になるケース(「ホテルと観光地を
管理したい」)が解消し、実機で確認した。詳細は`TECH_DEBT.md` TD24
「2026-08-11(2回目)追記」参照。

### Design Critic評価範囲の拡大(8軸→10軸)
CEOが選んだ4方向のうち「Design Criticの評価範囲を広げる」に対応した。
Action Completeness(データを持つ画面に操作可能なActionが無い場合を
検出)・State Completeness(data_entitiesが空、または画面のkey_elements
がdata_entitiesに含まれない孤立データを検出)の2軸を追加した。残り4軸
(Domain Consistency/Error Recovery/Explainability/Runtime Safety)は、
`DesignCritic.evaluate()`の既存3引数(plan/template_selection/
requirements)だけでは機械的に判定できない情報を要するため見送った
(シグネチャ拡張は呼び出し元への影響範囲を確認できておらずスコープ外)。
現在の実装では新2軸ともほぼ常に満点になる(既存のNavigation Coherence
軸と同種の、将来の複数画面Plan拡張に備える防御的な評価軸)ことを
正直に記録した上で、回帰テスト4件を追加。詳細は`TECH_DEBT.md` TD28参照。

### Templateの種類拡充(Widget Registry変更なし)
CEOが選んだ4方向の最後「Widget・Templateの種類を増やす」を調査した
結果、最大の発見は「新Widgetが必要」ではなく、**既存のTemplate
Selectorの選定結果が、そもそもCompile段階へ一度も渡されていなかった**
ことだった(`TD29`参照)。`TemplateSelector`は"form"等11種類を本格的な
スコアリングで選んでいたが、`pipeline_orchestrator.py`がその結果を
`Compiler.compile()`へ渡し忘れていたため、選定に関わらず常にChecklist
単一画面が生成されていた(「満足度アンケート」がform Templateを
選びながら実際にはChecklistになっていた根本原因)。

`Compiler.compile()`へ`template`引数を追加して配線し、`template==
"form"`の場合のみ、既存のMock Generator(`form_template.py`・
`templates.dart`)と同一形状の2画面Form(heading→card→form→
text_field*N→送礼画面)を生成するようにした。新しいWidget種別は
一切追加していない(`form`/`heading`/`card`は既にWidget Registry
v1.1で実装・テスト済み)。残り9種のTemplate(tracker/calendar/memo等)
は、実際に選ばれる頻度・必要性を見極めた上で次回以降に判断する。

Golden Test(`04_survey.json`)を意図的に更新(1画面→2画面)。回帰
テスト8件を追加。実機Geminiで「満足度アンケートを作って」を再実行し、
実際の質問文3件がそれぞれ独立したtext_fieldとして生成され、本物の
Backend Validatorに通り、Design Criticがrelease_ready=trueになる
ことを確認した。

### 残タスク
CEOが選んだ4方向すべてに着手した(#8色々なジャンルで生成→修正、
#9個別バグ修正、#10 primary_concept一般化、#11 Design Critic拡張、
#12 Template配線)。今回スコープ外にしたものは各TD(TD26〜TD29)に
将来課題として記録済み。

## Task049 — TD24深掘り修正・TD22/TD21/TD20実装・音声入力（2026-08-11、CEO「すべてお願い」）

CEOから提示された3つの残課題(TD24の続き、TD20〜22、音声入力)を
すべて実施した。

### TD24(travel belongings、続き)
前回(Task048近辺)の`_prioritize_explicitly_mentioned_concepts()`だけでは
不十分だった(forge_ai自身のGolden Testが検出)。原因は
`compiler.py`の`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`に`"belongings"`の
エントリが無く、raw識別子がそのまま漏れていたこと。エントリを追加し、
Mock・実Gemini経由の両方で「パスポート」「着替え」「歯ブラシ」
「充電器」が正しく生成されることを実測で確認した。

### TD22(IRバージョニング)
`IntentIR`・`PlanIR`・`Template`へ`schema_version: str = "1.0"`を追加
(既定値付き、後方互換)。Migrationは実装していない(2つ目のバージョンが
実際に必要になるまで、というTD22自身の対応方針どおり)。

### TD21(Prompt Injection Guard)
新規`forge_ai/prompt/injection_guard.py`。英語・日本語・混在入力に対応し、
「developer modeを有効にして」のような、英語フレーズ直後に日本語が続く
ケースでのUnicode単語境界問題(Pythonの`\b`が失敗する)をASCII境界の
正規表現で回避した。`prompt_pipeline.py`の「forge_ai/を3つに限り
直接importしてよい」という既存の制約を守るため、新規の薄いAdapter
(`backend/app/ai/runtime/injection_scan.py`)経由で`routers/ai.py`から
呼び出す設計にした。検出のみ、ブロックはしない。実際にGemini経由で
`Ignore previous instructions`+`developer modeを有効にして`を含む
リクエストを送り、`injection_report.detected=true`(`status`は
`success`のまま)を確認した。

### TD20(Output Safety Checker)
新規`backend/app/ai/runtime/output_safety.py`(forge_ai/には依存しない)。
最終Forge Document内の**全ての文字列値**を走査し(特定のフィールド名に
限定しない)、クレジットカード番号・暗証番号・パスワード等のPII収集を
示唆するキーワードと照合する。検出のみ、ブロックはしない。実際にGemini
へ「クレジットカード番号と暗証番号を記録するアプリを作って」と依頼し、
生成されたapp titleに含まれる該当語を`safety_report`が正しく検出
(`safe: false`、high severity 6件)することを確認した。

### 音声入力(speech_to_text)
`speech_to_text: ^7.0.0`を新規追加(CEO承認済み)。
`voice_input_provider.dart`(`VoiceInputController`)+
`home_screen.dart`の`_VoiceInputButton`(マイクボタン)。**このアプリは
`android/`・`ios/`フォルダを一度も`flutter create`していないため
(`web/`のみ存在)、Web(Chrome)でのみ動作する想定。** 素の
`StatefulWidget`+`setState`で実装した(このアプリで実績の無い
`StateNotifierProvider`パターンを、検証不能なコードにさらに重ねる
リスクを避けるため)。

**この音声入力実装だけは、一切検証できていない**(Flutter SDK・
マイク・ブラウザ音声認識APIのいずれもClaude環境に無い)。パッケージの
バージョン解決・実際のAPIシグネチャ一致は未確認。TD25として記録。

既存テスト`home screen does not show a microphone icon...`
(「マイク未実装のためアイコン無し」という前提のテスト)は、前提が
変わったため更新した(プロフィール非表示の確認と、マイクボタンが
存在することの確認に分割)。

### 実際に実行したテスト・結果
```
$ python -m pytest backend forge_ai -q
939 passed, 12 skipped   (Flutter変更は影響なし、回帰確認のみ)
```
Flutter側(音声入力を含む今回の全変更)はClaude環境で`flutter analyze`/
`flutter test`いずれも未実行。CEO環境での実行が必須。

詳細は`TECH_DEBT.md`(TD20〜TD25)・
`docs/reports/FORGE-AI-CONNECT-001-report.md`参照。

## Task048 — FlutterからGeminiを選べるトグルを追加（2026-08-11）

CEOから「ガンガン進んでー」との指示を受け、`docs/reports/
FORGE-AI-CONNECT-001-report.md`に残っていた「Flutterアプリ側にGeminiを
選ぶUIが無い」という既知の限界に対応した。

### 追加・変更
- `ai_generation_api.dart`: `generate()`に`{String? provider}`を追加し、
  指定時のみ`generation_options: {engine: "forge_ai", provider: ...}`を
  リクエストボディへ含める(未指定時はBackend既定のmockのまま、既存の
  リクエスト形状を変えない)。
- `AppGenerationRepository`(interface)・`ApiAppGenerationRepository`・
  `MockAppGenerationRepository`・`GenerateAppUseCase`・
  `GenerationRequest`・`GenerationFlowScreen`に`provider`パラメータを
  一貫して追加(Mock実装は受け取るが無視、コメントで理由を明記)。
- `selectedAiProviderProvider`(新規`StateProvider<String?>`):
  ホーム画面で選ばれているProvider。永続化はしない(「設定より会話」
  というForge Constitution第三原則を踏まえ、専用の設定画面ではなく
  ホーム画面ヘッダーの小さなピル型トグルにした。アプリ再起動で既定の
  mockへ戻る、意図的な設計)。
- `_ProviderToggle`(新規Widget、`home_screen.dart`): タップで
  Mock⇔Geminiを切り替える。Flutter側がMock Mode(`--dart-define=
  USE_MOCK_GENERATION=true`)でビルドされている場合は、Backendへ接続
  しないため非表示にする。

### 実際に実行したテスト・結果
- `backend`・`forge_ai`のPythonスイートは今回の変更(Flutterのみ)の
  影響を受けないため、回帰確認として再実行: `917 passed, 12 skipped`
  (変更なし、影響が無いことの確認)。
- `api_app_generation_repository_test.dart`へ新規テスト2件を追加し、
  `provider`指定時/未指定時でリクエストボディの`generation_options`が
  意図通りになることを検証する(Dio Interceptorでリクエストボディを
  実際にキャプチャして比較する形。**Claude環境にFlutter SDKが無いため、
  このテスト自体は一度も実行できていない**。CEO環境での実行が必須)。
- 影響範囲の`grep`調査: `AppGenerationRepository`を実装するクラスが
  他に無いこと、既存テストが`generate('text')`を1引数のみで呼んでいて
  (`provider`は省略可能な名前付き引数のため)壊れないことを確認済み。

### 既知の限界
- 本Task全体(Flutterコード)は、Claude環境にFlutter/Dart SDKが無いため
  一度も`flutter analyze`/`flutter test`で実行できていない。手動での
  全文読み直し・import整合性確認・括弧の対応関係チェックのみ実施。

## Task047 — FORGE-AI-CONNECT-001: Gemini実機確認（Task046の同日追記）（2026-08-10）

Task046完了後、CEOがGoogle AI Studioで取得した実際のAPIキーをこの
セッション内で共有してくれたため、`backend/.env`へ設定(Gitには
コミットしていない)し、実際のGemini APIへ接続して動作確認した。

### 分かったこと・直したこと
- 既定モデルにしていた`gemini-2.0-flash`は実際には**`429`エラー**
  (無料枠のトークン上限が`0`)で使えなかった。
- 次に試した`gemini-2.5-flash`・`gemini-2.5-flash-lite`も**`404`エラー**
  (「新規ユーザーには提供終了」)で使えなかった。
- `gemini-flash-latest`(常に最新のFlash系モデルを指すエイリアス)で
  初めて成功した。既定モデルをこれに変更した。
- `uvicorn`を実際に起動し、`POST /api/v1/ai/generate`へ
  `generation_options.provider: "gemini"`を指定して2パターン
  (「買い物リストを作って」「旅行の持ち物チェックリストを作って」)を
  実行し、いずれも`status: "success"`・`diagnostics.provider_used:
  "gemini"`・Validator通過のForge Language JSONが返ることを確認した。

### 見つかった別の課題(未着手、記録のみ)
「旅行の持ち物チェックリスト」への応答で、生成された項目が
「京都旅行」「沖縄旅行」「温泉旅行」という**旅行先**になっており、
本来期待される「パスポート」等の**持ち物**になっていなかった。Gemini
自体は正しく応答しており、forge_aiのCognitive Engine側(travel domainの
Template解釈)に改善余地があることが、今回初めて実データで見つかった。
今回はスコープ外として着手していない。

### 変更
- `backend/app/ai/foundation/providers.py`: 既定モデルを
  `gemini-2.0-flash`→`gemini-flash-latest`へ変更。docstringに実機確認の
  経緯を記録。
- `TECH_DEBT.md` TD15・`GETTING_STARTED.md`・
  `docs/reports/FORGE-AI-CONNECT-001-report.md`(9章として追記)・
  `2026-08-10-SESSION-REVIEW-SUMMARY.md`を、実機確認済みの内容へ更新。

### 実際に実行したテスト・結果
```
$ cd backend && python -m pytest -q
526 passed, 12 skipped(モデル名変更後も回帰無し)

$ curl -X POST http://127.0.0.1:8123/api/v1/ai/generate ... (provider: gemini)
実際に2回成功(内容は本CHANGELOG本文・レポート参照)
```

**APIキーの取り扱いについて**: CEOがチャット上でAPIキーを共有する際、
最初の2回はGoogleのOAuth関連コード(`AQ.`から始まるが別物)を誤って
貼ってしまったため、正しいAPIキーの取得手順(「APIキーの詳細」画面の
「APIキー」欄からコピー)を案内し直した。実際のキーの値は、このファイル・
コミットメッセージ・レポートのいずれにも含めていない
(`backend/.env`のみに存在し、`.gitignore`で除外済み)。

## Task046 — FORGE-AI-CONNECT-001: GeminiProvider実装（2026-08-10）

CEOから「無料で使える外部AI接続を先に実装したい。課金なしで」という
依頼を受け、`AskUserQuestion`で選択肢(Gemini無料枠 / ローカルLLM /
共通部分のみ)を確認したところ「Gemini無料枠(外部API)を先に」との
回答を得たため実装した。TD15(AI Provider 5種すべて未実装スタブ)の
一部解消でもある。

### 追加
- `backend/app/ai/foundation/providers.py`の`GeminiProvider`を、
  `_UnimplementedProvider`継承のスタブから実装へ変更。Google公式の
  Gemini REST API(`generateContent`エンドポイント、
  `responseMimeType: "application/json"` + `responseSchema`による
  Structured Output)を、既存の`httpx`(新規パッケージ追加なし)で
  直接呼び出す。APIキーは`GEMINI_API_KEY`環境変数から読む。
- `backend/tests/test_gemini_provider.py`(新規、7テスト、実際に
  `pytest`で実行しPASS確認済み)。`httpx.MockTransport`でリクエスト
  構築・レスポンス解析・エラー処理を検証。
- `backend/.env.example`(新規)。`GEMINI_API_KEY`の取得方法・設定方法を
  記載。
- `.gitignore`へ`.env`/`backend/.env`を追加(APIキーを誤ってコミット
  しないため)。

### 変更
- `backend/tests/test_ai_foundation.py`・`backend/tests/test_ai_runtime.py`:
  「Providerは全部NotImplementedErrorを投げる」という既存テストから
  `gemini`を除外し、代わりに`gemini`が`RuntimeError`(APIキー未設定時)を
  投げることを確認するテストを追加。
- `TECH_DEBT.md` TD15: 一部解消(gemini実装済み、他4種は未実装のまま)
  として更新。
- `GETTING_STARTED.md`: Gemini APIキーの設定方法(3.6節)・curlでの
  呼び出し方(6.1節)・トラブルシューティング項目を追加。

### 既知の限界(重要)
- **実際のGemini APIへの呼び出しは一度も行っていない**。Claudeの
  サンドボックスにAPIキーが無いため、検証はUnit Test(モックした
  HTTPレスポンス)のみ。CEO環境で実際のキーを設定して初めて実証される。
- **Flutterアプリ側にGeminiを選ぶUIはまだ無い**。現状は`curl`等で
  APIを直接叩く場合のみGeminiを指定できる(`generation_options.
  provider: "gemini"`)。Flutter側の設定UIは別Taskとして扱う。
- openai/claude/oss/forge_ai(Provider名としての)は引き続き未実装。

### 実際に実行したテスト・結果
```
$ python -m pytest backend -q
526 passed, 12 skipped(変更前518 passed、新規8件追加)
$ ruff check backend/app/ai/foundation/providers.py backend/tests/test_gemini_provider.py \
    backend/tests/test_ai_foundation.py backend/tests/test_ai_runtime.py
新規ファイル・変更箇所はエラー0件(既存の無関係なwarning 5件のみ、対応済みTask044/045と同じ既存分)
```

詳細は`docs/reports/FORGE-AI-CONNECT-001-report.md`参照。

## Task045 — GETTING_STARTED.md新設・README.md Mock/Live Mode既定値の訂正（2026-08-10）

CEOから「レビュー用のまとめ」「GitHubから実行までの初心者向けガイド」を
依頼されたため作成した。ガイドを書く過程で、`README.md`の「Frontend
セットアップ」section 3が実コードと食い違っていることを発見したため、
あわせて訂正した。

### 追加
- `GETTING_STARTED.md`(新規、リポジトリ直下): GitHubからのclone〜Backend
  起動〜Frontend起動〜動作確認までを1つずつ説明する、前提知識を仮定しない
  ガイド。Backend部分の手順は実際に実行して確認済み。Frontend部分は
  Flutter SDKが無いため未実行(その旨を明記)。
- `2026-08-10-SESSION-REVIEW-SUMMARY.md`(新規、リポジトリ直下):
  2026-08-10のセッション全体(リポジトリ復元・PHASE0監査・
  FORGE-UI-REFRESH-002)をレビューしやすいよう1箇所にまとめたもの。

### 修正(README.md)
- 「Mock Modeが既定」という記述が、実際の`frontend/lib/core/config/
  app_config.dart`(既定値は`USE_MOCK_GENERATION=false`、**Live Modeが
  既定**)と食い違っていたため訂正した。
- 「Live Modeにするには`--dart-define=FORGE_MOCK_MODE=false`」という
  記述も、実際のフラグ名(`USE_MOCK_GENERATION`)と異なる旧フラグ名を
  案内していたため訂正した。
- ドキュメント一覧表へ`GETTING_STARTED.md`を追加。

## Task044 — FORGE-UI-REFRESH-002: Sparkleブランド・ダーク生成中画面（2026-08-10）

CEOから新しいUIモックアップ画像(✦マークのSparkleロゴ、紫→青グラデーション、
「AIが考えている最中」向けのダーク画面、チェックリスト形式の生成中演出)が
共有され、「あなたの最善で選んでよし。エラーは都度解消してくれ」という
指示を受けたため、確認を挟まず実装した。

### 追加
- `frontend/lib/shared_widgets/forge_sparkle_mark.dart`(新規)。モックアップの
  "✦"ロゴを、実際の画像アセットが無いため`CustomPainter`でベクター描画する
  Widget。新規アセット・新規パッケージ依存は追加していない。
- `ForgeTheme`(`forge_theme.dart`)へ、ホーム画面・生成中画面専用の
  ダークパレット(`consoleBackground`等)と、ブランドグラデーション
  (`gradientStart`/`gradientEnd`/`brandGradient`)を追加。すべての新規配色は
  WCAG AAコントラスト比を計算した上で選定した(ファイル内コメント参照)。
  既存の`background`/`ink`/`accent`等は変更・削除していない。

### 変更
- `home_screen.dart`: ダーク配色化、`ForgeMark`→`ForgeSparkleMark`、
  送信ボタンのグラデーション化、`forgeExampleItems`を使ったクイック候補
  チップの追加(「例を見る」→「もっと例を見る」に改名、Bottom Sheet自体は
  変更なし)。**音声入力は引き続き未実装のため、モックアップにあるマイク
  アイコンは採用していない**(実装していない機能をあるように見せない、
  というFORGE v0.2 P5の既存方針を踏襲)。
- `generation_flow_screen.dart`: 生成中画面(`_GeneratingView`)を、
  1行だけのメッセージ切り替えから、全段階を並べたチェックリスト表示
  (完了=チェック、現在=スピナー、未到達=薄いドット)へ変更し、ダーク配色
  にした。完成画面(`_CompletionView`)はSparkleロゴ・グラデーションボタンに
  更新したが、配色自体は既存のlightなテーマのまま据え置いた(CEO提示
  モックアップ自体が画面ごとに意図的に配色を切り替えているため、
  `MaterialApp`全体のダークモード切り替えとしては実装していない)。
  確認画面(`_ConfirmationView`)・エラー画面(`_GenerationErrorView`)は
  未変更。
- テスト3件(`test/features/.../home_screen_test.dart`・
  `test/e2e/kids_checklist_generation_flow_test.dart`・
  `test/e2e/survey_form_validation_flow_test.dart`)を、上記の文言変更・
  新規チップによる`find.text()`の曖昧化に合わせて更新した(過去の
  FORGE-UI-REFRESH-report.md 2章と同じ種類の問題を、今回は実装と
  同じセッション内で先回りして修正した)。

### 既知の未達成事項
- Claudeのサンドボックスに Flutter/Dart SDK が無いため、`flutter analyze`・
  `flutter test`・`flutter build`のいずれも実行できていない
  (実行結果は一度も見ていない)。実装は既存パターン(既存の
  `RUNTIME-003`ボタン幅バグの回避パターン等)を踏襲し、括弧・波括弧の
  対応関係やimportの整合性は手動で確認したが、**CEO環境での実行結果
  待ち**。詳細は`docs/reports/FORGE-UI-REFRESH-002-report.md`参照。

## Task043 — Confidence Model Review（設計レビューのみ、コード変更なし）（2026-07-22）

Task042をEvaluation Phase Completeとして終了したことを受け、後続の
設計課題を独立したTaskとして開始した。今回はコード変更を一切行わず、
設計レビュー資料のみを作成した。

- confidenceとuncertaintyを概念として分離できるか検討した。
- `score_margin`の扱いについて3案(overall_confidenceへ統合・独立
  シグナルとして保持・第三要素として扱う)を比較した。
- 低confidence領域のGolden Test候補(intentのみ低い・domainのみ低い・
  score_marginのみ低い・privacy由来・permission由来・ambiguous
  entity由来を含む)を提案した。
- Task042-3(複数候補保持)との責務分離を、confidence・
  uncertainty・multiple candidate planningの3観点で整理した。

詳細は`docs/tasks/task043.md`・`FORGE-TASK043-CONFIDENCE-MODEL-
REVIEW.md`参照。

## Task042 — ADR-007実装 Task042-1: ConfidenceRecord・overall_confidence導入（2026-07-21）

**Status: Evaluation Phase Complete(2026-07-22)。Phase Cは開始しない。
後続はTask043として独立させた。**

ADR-007(Confidence Must Affect Control Flow)の実装第1段階。
`ConfidenceRecord{value, basis}`・`OverallConfidence`(intent/domain
confidence必須、entity/planning/template confidenceは将来拡張用に
任意)を新設し、`compute_overall_confidence()`で計算した値を
DecisionTraceへ**観測専用**で記録するようにした。既存の確認要求判定
ロジック(`_should_escalate_for_low_confidence()`等)は1行も変更して
いない。

新しいDecisionTraceステージの追加により、Golden Test6件が
`decision_trace_stages`の不一致で失敗する状態を発見し、他のフィールド
(Domain・Template・Success判定等)が一切変わっていないことを確認した
上で、golden fileを意図した変更として更新した。

CEOから、Task042-2は「ADRの閾値への単純置換ではなく、既存シグナルを
内部要素として残しつつ比較実験できる状態を作る」方針が明示されており、
次はその詳細設計に進む。Task042-3(複数ApplicationPlan候補保持)は
規模が大きいため、独立マイルストームとして切り出すかを別途判断する。

詳細は`docs/tasks/task042.md`・`FORGE-TASK042-ADR007-INVESTIGATION-
PLAN.md`参照。

**追記(同日)**: CEOレビューでTask042-1が承認され、Task042-2着手前の
追加対応として、`DecisionTrace`へ`confidence_observation`
(`OverallConfidence`オブジェクトそのもの)を保持するフィールドを
追加した(`reason`文字列を構文解析せずに`overall_confidence`・
`available_components`・`intent_confidence`・`domain_confidence`・
各`basis`へ直接アクセスできるようにするため)。テスト4件追加(計18件)。
続けてTask042-2の詳細設計(単純置換ではなく、Shadow Judgmentによる
比較可能な移行案)を`FORGE-TASK042-2-DESIGN-PROPOSAL.md`として提出、
コード変更はまだ行っていない。

**追記2(同日、Phase B実装完了)**: 設計提案が承認され、
`ShadowJudgment`(現行モデルとoverall_confidenceモデルの判定・
不一致分類・risk_classification・thresholds_usedを構造化して保持)を
実装した。`_should_escalate_for_low_confidence()`は、判定ロジックの
実体を`confidence.compute_legacy_escalation_reasons()`へ切り出した
薄いラッパーへリファクタリングしたが、**返す`bool`値は完全に同一**
(全テストで確認済み)。Golden Test全42件を実際にPipelineへ通した
比較の結果、**一致率100%**(不一致0件)だった。詳細は
`docs/tasks/task042.md`・`FORGE-TASK042-2-SHADOW-COMPARISON-
REPORT.md`参照。forge_ai 390件・backend 400件、全て合格。

**追記3(2026-07-22、比較データの訂正)**: Evaluation Report作成中に、
比較対象抽出コードのタプル順序バグ(複雑入力6件で実際の入力文の
かわりにケース名文字列を使っていた)を発見・修正した。一致率100%
という結論は変わらないが、修正後は42件全てが`high_confidence`/
`medium_band`に分類され、**低confidence領域は現在のGolden Test
corpusで一切検証できていない**ことが判明した。詳細は
`docs/tasks/task042.md`追記3参照。

## Task041 — Template Selector監査・CI統合・完全性チェック・設計改善提案（2026-07-21）

**Status: 実装済み・CI実行待ち**(`forge-ai-test`がGitHub Actions上で
実際に成功したことを確認するまで完了扱いにしない)。

CEOから`household_budget`のPreliminary/Final不一致(確認要求ループ)の
報告を受け調査した結果、報告された不具合は既にFORGE v0.3時点で修正
済みであることが判明した(CEOの手元のワークツリーが古い状態だった)。
この説明にCEOが納得した上で、「同種の再発防止」を本命として以下を
実施した。

- `DomainCategory`全14カテゴリと`_DOMAIN_TO_PRELIMINARY`を監査し、
  未登録が無いことを確認した。golden test 36件全てが1件も
  Preliminary/Final不一致を起こさないことも確認した。
- `household_budget`固有の回帰テスト4件・全Domain登録監査テスト
  1件を追加した。
- `_DOMAIN_TO_PRELIMINARY`の完全性を、**モジュール読み込み時に自動
  検証する**仕組みを追加した(欠落があれば`import`の瞬間に
  `RuntimeError`、テストの実行有無に依存しない。当初
  `AssertionError`を使っていたが、`python -O`実行下でも無効化
  されないことを型としてより明確に示すため、CEO指摘によりRuntime
  Errorへ修正した——実際には明示的な`raise`文だったため`-O`による
  無効化は元々発生していなかったが、型名の誤解を避けるための修正)。
- `forge_ai/tests/`(360件)がCIから一度も実行されていなかったことを
  発見し、`.github/workflows/ci.yml`へ`forge-ai-test`ジョブを新設
  した。
- `differs_from_preliminary`が真偽値であり「著しく異なる」という
  程度を表現できていないという設計ギャップについて、
  `docs/adr/ADR-013-template-selection-mismatch-severity.md`として
  設計改善案(未実装、Runtime変更なし)をまとめた。

詳細は`docs/tasks/task041.md`・`FORGE-TEMPLATE-SELECTOR-AUDIT-
report.md`・`FORGE-TEMPLATE-SELECTOR-CI-HARDENING-report.md`・
`FORGE-TEMPLATE-SELECTOR-CI-HARDENING-PATCH1-report.md`参照。

## Task040 — Forge UI刷新: CEO提示モックアップへのUI反映（2026-07-17）

CEOが提示したUIモックアップ(ホーム画面→「例を見る」→入力反映→生成中→
完成→生成されたアプリ、の6ステップフロー)を、実際のForge Flutterアプリへ
反映した。生成の仕組み(Mock/HTTP Repository・Renderer・Runtime)自体は
変更していない。

### 状況
作業開始時点で、テーマ・ホーム画面・例選択Bottom Sheet・生成フロー画面が
既に2026-07-16付でモックアップに合わせて更新済みだった。本セッションでは
これらを検証した上で、UI変更によって実際に壊れていた既存E2Eテスト2件を
発見・修正した。

### 修正内容
`test/e2e/kids_checklist_generation_flow_test.dart`・
`test/e2e/survey_form_validation_flow_test.dart`が、いずれも旧UI
(「これで作る」ボタン→Confirm画面→「この内容で作ります」ボタン)を
前提にしたまま残っており、新しいHomeScreen(Confirm画面を経由せず直接
GenerationFlowScreenへ進む設計)に対して実行すると確実に失敗する状態
だった。新しいUI操作(直接入力→丸い送信ボタン→生成中画面→完成画面→
「アプリを開く」)に合わせて更新した。Mock Generatorが受け取る文言・
返す結果は変更していない。

### 本セッションで発見・修正した自己修正
`survey_form_validation_flow_test.dart`の編集時、置換範囲の指定が
不十分で旧内容の末尾が重複して残ってしまった(brace/paren数の機械的な
確認で発見)。該当部分を削除して修正した。

### 未実行の検証(正直な申告)
Claudeのサンドボックスに Dart SDK が無いため、`flutter analyze`・
`flutter test`とも一度も実行できていない。CEO環境での実行が必須。

### 既知の状態
`confirm_screen.dart`・`generated_app_screen.dart`が新フローから
参照されなくなり孤立している(削除はしていない)。詳細は
`FORGE-UI-REFRESH-report.md`参照。

## Task039 — FORGE-MILESTONE-007 Phase 1.2: Meaning Model導入（2026-07-16）

Meaning ModelをCognitive Pipelineへ正式接続し、複雑な修飾条件
(共有・写真/気分・期限/優先度・在庫低下・回答後一覧・毎週月曜日)を
含む6入力の意味を構造化して、Requirement Extraction・Application
Planning・Decision Traceへ実際に反映した。複数画面化・新規Domainには
進んでいない。

### 実装内容
- `SemanticUnit`/`ExtractedMeaning`(Cognitive専用、Legacy
  `meaning_model.py`とは別型)を新設。
- `CognitiveMeaningExtractor`を実装(Actor/Entity/Action/Constraint/
  Preference/Temporal/State/Evidence spanを決定的なキーワード辞書で抽出)。
- `RequirementExtractorProtocol.extract()`をBlueprint本来の3引数
  (meaning, world, intent)へ復元。
- `Requirement.derived_from`(既定値"world")を新設し、Meaning由来の
  要件を区別。
- `ApplicationPlanner`が、Meaning由来のmandatory要件のtarget_ref/
  operation_refを実際にdata_entities/required_actionsへ反映するよう拡張。
- `DesignCritic`へ`intent_meaning_fidelity`軸(8軸目)を追加。

### 実装中に発見・修正した設計上の問題
Meaning由来かどうかを区別せず全てのmandatory要件のtarget_ref/
operation_refを自動反映すると、Phase 1.1で検証した「Planへ実際に
反映されていない要件はunassignedのままになる」という機械判定機能が
無意味になってしまう問題を発見した。`derived_from`フィールドを追加し、
Meaning由来の要件のみを自動反映の対象とすることで解決した。

### 検証
```
Forge AI tests: 192 PASS(既存164件維持+新規28件)
Backend tests: 265(248 PASS + 17 SKIP、無影響)
```
CEO指定の複雑入力6例・既存6例、計12例全てで`CognitivePipelineSuccess`
に到達し、Meaning由来の情報が実際にPlanへ反映されることを確認した。

## Task038 — FORGE-MILESTONE-007 Phase 1.1(残修正)実物監査対応（2026-07-16）

CEOがForge AI 156件・Backend 265件の全合格を確認した上で、Meaning
Model・複数画面化へ進む前の残修正4点(Preliminary/Final不一致判定の
一元化・Decision Trace記録・Requirement割当の実データ判定・
Privacy/Accessibility方針統一)を求めた。**独立監査の結果、4点とも
既に正しく実装・テスト済みであることを確認した。**

### 確認結果
1. `TemplateSelector.select_final()`が`differs_from_preliminary`を
   自ら設定しており、Orchestrator側の上書きは存在しない。Revision
   ループも`while`文で不一致が続く限り繰り返す設計になっている。
2. `preliminary_template_selection`・`final_template_selection`・
   `design_critic`・`cognitive_revision`の4段階全てでDecision Trace
   が記録されている。
3. `Requirement.target_ref`/`operation_ref`(後方互換)が追加され、
   `ApplicationPlanner`が文字列の偶然一致ではなく機械的な参照整合性
   のみで割当判定していることを、専用テストで確認した。
4. `design_critic.py`のdocstringと実装が、Privacy mandatory/
   Accessibility mandatory=high・blocking、Accessibility
   non-mandatory=medium・non-blockingという方針で完全に一致している。

### 本セッションで発見・修正した軽微な冗長コード
Cognitive Revisionループ内で`design_critic.evaluate()`が同一入力に
対して連続2回呼ばれ、2回目の結果が使われていなかった(決定的な
Criticのため動作結果への影響は無いが、無駄な呼び出し)。削除した。

### 検証
```
Forge AI tests: 164 PASS(前回156件から8件増加)
Backend tests: 265(248 PASS + 17 SKIP、無影響)
```
CEO指定6例全てで、Domain/Template判定・release_ready=Trueを維持し、
Decision Trace件数が2件→5件(Template Selection・Critic・
Revisionの記録追加分)に増えたことを確認した。

## Task037 — FORGE-MILESTONE-007 Phase 1.1: 契約精度・品質評価・UX改善（2026-07-16）

CEOの実物監査(139/265件全合格を確認済み)で指摘された7点を修正した。
新しいDomain・大規模機能は追加せず、既存Minimal Sliceの契約精度・
品質評価・ユーザー体験の改善に限定した。

### 修正内容
1. 実装位置づけを「Blueprint v1.3の実装」から「M007 Phase 1 Minimal
   Cognitive Slice」へ訂正(Meaning Model未実装、実装済み13段階を明記)。
2. `run_cognitive_pipeline()`へ`provider`を正式な引数として復元し、
   Compilerへ実際に注入されることをテストで確認した。
3. Template Selectionの同点解決を、Preliminary候補優先→Dominant
   action一致数→Data lifecycle一致数→genericの順で決定的にした
   (辞書登録順への暗黙の依存を解消)。
4. Validation既定を「エラーにせず何もしない」1件から、空入力時の
   無視(既存M005教訓)と、必須項目未達成時の理由表示・入力保持・
   修正方法明示・フォーカス移動という5件へ分割した。
5. `CriticReport`へ`implemented_checks_score`・`coverage_ratio`・
   `evaluated_axes`・`unevaluated_axes`を追加し、score=1.00がアプリ
   全体の品質1.00を意味しないことを明示した。未割当のmandatory要件・
   Privacy要件はrelease_readyをblockingし、単一画面のnavigation不要と
   複数画面でのnavigation_edges欠落を区別した。
6. `intent_extraction_confidence`・`domain_coverage`・`score_margin`の
   3指標を明示的に組み合わせるHuman Confirmation判定へ変更した。

### 実装中に発見した実バグ
「data」カテゴリの要件が常に未割当扱いになっており、指摘5の
mandatory-blockingルールを適用すると6例全てが`NeedsConfirmation`へ
落ちてしまう問題を発見した。実際には単一画面のkey_elementsが
data_entities全てを含むため実質的に充足されており、
`application_planner.py`の割当判定漏れが原因だった。修正済み。

### 検証
```
Forge AI tests: 156 PASS(既存139件維持+新規17件)
Backend tests: 265(248 PASS + 17 SKIP、無影響)
```
CEO指定6例全てで、Domain/Template判定結果を変えずに
`CognitivePipelineSuccess`へ到達し、Critic/Qualityスコアが正直な値
(implemented_checks_score=0.93、coverage_ratio=0.50)になることを確認した。

## Task036 — FORGE-MILESTONE-007 第一段階実装: Cognitive Pipeline最小実装（2026-07-15）

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3を実装契約として、
既存`run_pipeline()`を無変更のまま、`run_cognitive_pipeline()`という
独立したFacadeでCognitive Pipelineの最小実装を行った。

### 実装開始前に発見・修正した重大な不具合
着手時点でforge_ai/既存80テストのうち3件が失敗していた。原因は
`DomainCategory`へTASK_MANAGEMENT/SURVEY/SCHEDULEを追加した際、
対応する`Domain`定義本体(`_BUILTIN_DOMAINS`)への追加が漏れていた
ため。3つのDomain定義を追加し修正した(最優先で対応)。

### 新規実装(18項目)
Cognitive型・Protocol・Context・Dependencies・Outcomes(3型Union)・
Error Model・Input Normalization・簡易Ambiguity Detection(2分類)・
簡易Intent Recognition(日本語キーワード辞書)・Domain Classification
(実スコアリング)・World Model Construction(Domain+Intent)・
Requirement Extraction(第一段階簡略化、2引数)・Preliminary/Final
Template Selection(11 Family対応)・簡易Application Planning・
最小Design Critic(4軸)・Revision Engine・CognitiveOrchestrator・
run_cognitive_pipeline() Facade・Unit/Integration/Golden Test(56件)。

### 検証(実行結果)
```
forge_ai tests: 139 PASS(既存80件維持+新規56件+Domain拡張3件)
backend tests: 265(248 PASS + 17 SKIP、無影響)
```
CEO指定6例(買い物・タスク管理・日記・アンケート・予定・在庫)全てで
`CognitivePipelineSuccess`に到達することを実際に実行して確認した。

### 既知の制限
Meaning Model未実装(Requirement Extractorは2引数)。Ambiguity
Detection・Design Criticは一部の分類/評価軸のみ実装。複数画面
Application Planning未対応。詳細は`FORGE-MILESTONE-007-PHASE1-report.md`
参照。

## Task035 — FORGE-MILESTONE-007 PREPARATION 実物監査(4回目)対応(8点修正、v1.3)（2026-07-15）

CEOが、前回の7点修正(Legacy/Cognitive分離・M006認知順序・Requirements
入力・Preliminary/Final分離・Facade分離)を承認した上で、Outcome生成
API・依存注入API・段階数・Confidence計算・文書整合性に実装ブロッカーが
残っていることを指摘した。以下8点を修正し、Blueprintをv1.3として
全面書き直した。**新規コードは追加していない。**

### 修正内容
1. `CognitivePipelineOutcome`(Union型エイリアス)へ`.success(...)`等の
   メソッド呼び出しをする疑似コードを撤回。対応する具体的なdataclassを
   直接構築する形へ修正(型として成立しない疑似コードだった)。
2. `CognitivePipelineSuccess`を`context`・`ir`・`initial_quality`の
   3フィールドへ簡素化し、`CognitiveContext`と情報を重複保持しない
   設計へ変更。
3. `CognitiveDependencies`を専用dataclassとして定義し、`**`展開
   (dataclassは非対応)をやめ、単一引数として渡す設計へ修正。
4. 段階数を「14 Transformation Stage + 1 Terminal Outcome(M004側)+
   3 M005 Post-processing Stage」へ最終確定。「16段階」という表記を
   撤回し、`FORGE_COGNITIVE_ARCHITECTURE_V2.md`・関連図2件・ADR-008を
   一括更新した。
5. `DomainClassification`に安全性条件(全スコア0→Generic確定、同点→
   score_margin=0.0)を追加。confidenceの2定義案を比較し、Intentの
   情報をどれだけ説明できたかを測る式を採用(単純な相対比較は過大評価
   リスクがあるため却下)。raw_score/normalized_scoreを区別する
   `DomainCandidate`型を新設。
6. Preliminary/Final Template Selection不一致時の再計画を、Cognitive
   Revisionへ一本化(同じ入力でPlannerを再実行する設計は、決定的な
   実装なら無意味なため撤回)。
7. `NotImplementedError`をCognitiveOrchestrator内で捕捉しない設計へ
   変更し、Provider障害が`CognitivePipelineFailed`(planning_error相当)
   へ誤って吸収されないことを保証した。
8. Blueprint・報告書を全面書き直し、旧設計の記述を本文から分離して
   14章(設計の変遷、Superseded Design History)へ集約した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task034 — FORGE-MILESTONE-007 PREPARATION 実物監査(3回目)対応(7点修正)（2026-07-15）

CEOが、前回の4点修正(Facade分離・Outcome3型Union・Quality責務・
Error mapping)を承認した上で、既存Legacy Protocolへ無理に合わせる形で
M006とM004の不一致を解決していた点を指摘し、実装開始承認を保留した。
以下7点の追加修正を行った。**新規コードは追加していない。**

### 修正内容
1. Legacy Protocol(既存、無変更)とCognitive Protocol(新規、
   `CognitiveIntentRecognizerProtocol`等)を完全に分離(Task4)。
2. M006の認知順序(Intent→Domain→World→Meaning)を、Legacy Protocolの
   都合で変更せず維持(Task3.3)。
3. `CognitivePlannerProtocol.plan()`にrequirementsを必須引数として
   追加し、渡し忘れを型レベルで防止(Task3.3・4.2)。
4. Preliminary Pattern CandidatesをOrchestratorが明示的に呼び出す
   独立ノードへ変更(Application Planner内部への隠蔽を廃止、Task3.3、
   ADR-008一部訂正、`docs/diagrams/01`・`07`を更新)。
5. `DomainClassification`を、Intent由来のconcept/actionと各Domainの
   実際の一致度に基づくスコアリング契約へ全面書き換え。
   `score_margin`フィールドを追加(Task4.3)。
6. `CognitiveWorldBuilderProtocol.build(classification, intent)`が
   DomainとIntentの両方からWorldを構築する契約へ変更(Task4.4)。
7. Boolean Feature Flag・「provider_error等」・「Thin Wrapper化」・
   「7つの新設サブディレクトリ」(実際は6つ)等の古い記載を本文から
   削除・訂正。

### 本セッションでの追加発見
Preliminary Pattern Candidatesを独立ノード化した結果、M004側の段階数が
13→14へ増加し、M006本体の「全16段階」という記載と、更新後の図
(17ノード)との間に新たな数の不一致が生じた。CEO確認事項として提示した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task033 — FORGE-MILESTONE-007 PREPARATION 実物監査対応(4点修正)（2026-07-15）

CEOがImplementation Blueprintを実コードと突き合わせて監査し、
ディレクトリ構成・Immutable Context・単一Orchestrator・依存規則・
段階Migration・テスト方針は承認の上、実装開始前に4点の修正を求めた。
**新規コードは追加していない。**

### 修正内容
1. `needs_confirmation`を既存`PipelineResult`(7フィールド必須)へ
   ダミー値経由で変換する設計を撤回。`run_pipeline()`(既存、無変更)
   とは別に`run_cognitive_pipeline() -> CognitivePipelineOutcome`
   (Success/NeedsConfirmation/Failedの3独立dataclass Union)という
   新Facadeへ分離した。Boolean Feature Flag方式は撤回(ADR-009新設)。
2. 既存Protocol(`IntentBuilderProtocol.build()`等)が`process(context)`
   統一メソッドを持たないことを確認し、Orchestrator疑似コードを
   実際のメソッド名で呼ぶ形へ書き直した。
3. Initial Quality(M004、Repair前)/Final Quality(M005、Repair後の
   既存実装済みロジック)の責務分担を明記した。
4. 「未捕捉CognitiveErrorはprovider_error等へ分類される」という不正確な
   記述を、既存`prompt_pipeline.py`の実際の例外捕捉順序
   (NotImplementedError→provider_error、それ以外の Exception→
   planning_error)に基づき訂正した。ConfirmationRequiredが例外として
   Orchestrator外へ漏れないよう、主要経路を例外を使わない直接returnへ
   変更した。

### 本セッションでの追加発見
既存`IntentBuilderProtocol.build(meaning, world)`のシグネチャと、
M006 3章の掲載順(Intent Recognition→Domain→World→Meaning)の間に
実行順序の食い違いがあることを発見し、Task3の疑似コードでデータ依存に
従った実行順(Domain→World→Meaning→Intent)へ明確化した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task032 — FORGE-MILESTONE-007 PREPARATION: Implementation Blueprint（2026-07-15）

M006(Cognitive Architecture v2.0、CEO承認済み)を実装可能な設計へ
落とし込む「Implementation Blueprint」を作成した。**新規コードは
0行(Python/Dartとも無変更)。**

### 成果物
- `docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`(新規、約710行)。
  Task1(ディレクトリ設計)〜Task9(Migration Plan)の9タスクを全て記述。
- `docs/diagrams/10_m007_dependency_graph.md`(新規、依存図)。

### 設計の要点
- **既存ファイルは一切移動しない**: `forge_ai/core/`直下の既存7ファイル
  (domain_model/world_model/meaning_model/intent_model/planner/
  compiler/pipeline)は位置を変えず、M006の新規認知能力は
  `core/`配下の新設7サブディレクトリ(input_processing/understanding/
  planning/critic/confirmation/orchestration、+既存core/)へ追加する。
- **Cognitive Context**: Immutable(frozen dataclass)、`with_*`
  メソッド経由でのみ「更新」(実質は新インスタンス生成)。
- **Pipeline Orchestrator**: 16段階の実行順序を知る唯一のコンポーネント。
  各モジュールは互いを呼ばず、依存規則(Task5)で同階層間の直接import
  も禁止する。
- **Feature Flag方式のMigration**: `run_pipeline()`へ
  `use_cognitive_pipeline: bool = False`を追加するのみとし、既定Falseに
  より既存M005・既存80テストへの影響をゼロにする設計とした。
  Rollbackはフラグを触らないだけで完了する。
- **Error Model**: forge_ai/側`PlanningError`とM005側
  `pipeline_errors.PlanningError`が名前は同じだが別クラスであることを
  明記し、階層関係(段階レベル詳細 vs HTTPカテゴリ集約)として設計した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task031 — FORGE-MILESTONE-006 実物監査(2回目)対応(4点修正)（2026-07-15）

CEOがM006成果物(main spec・ADR7件・図9件・例6件)を実物監査し、Hybrid
方式・Decision Trace・Cognitive Revision/Schema Repair分離・M004/M005
責務境界は承認の上、正式確定前に4点の文書修正を求めた。**新規コードは
追加していない(設計文書のみ)。**

### 修正内容
1. Cognitive Pipelineの段階数不一致(「全16段階」と記載しながら実際は
   14段階)を解消。Design Critic後に「Cognitive Revision」「Human
   Confirmation / Escalation」を独立段階として追加し、真の16段階へ統一。
2. Confidence/Ambiguityの優先順位を統一。「Privacy/Safety/Permission
   関連HIGH ambiguity→confidence不問で必ず確認」「Domain confidence
   <0.5→原則確認」「低リスクかつ可逆的な場合のみGeneric仮設計」という
   3段階順位へ整理し、旧来の矛盾する2閾値(0.3/0.5)を0.5/0.8の2閾値へ
   簡素化。
3. Ambiguity Detection失敗時の「ambiguities=()で楽観継続」を廃止し、
   `detection_status="failed"`/`overall_severity="unknown"`を新設。
   Privacy/Health/Welfare等は確認・安全停止、低リスク時のみwarning付き
   限定継続へ分岐。
4. Application Planning/Template Selectionの隠れた循環依存を解消。
   Application Planningの内部フェーズとして「Preliminary Pattern
   Candidates」を新設し、Template Selectionを「Final Template
   Selection」として再定義(ADR-008新設)。不一致時の再計画はCognitive
   Revisionとカウンタを共有し、新たな独立ループを作らないことを明記。

### 本セッションでの追加確認
ADR新設(7→8件)に伴う表記漏れ2箇所(0章・21章)を発見・修正した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task030 — FORGE-MILESTONE-006: Cognitive Architecture v2.0 設計（2026-07-15）

「M006で扱う『Forgeがどう考えるか』を実装前に設計・固定する」という
Architecture Design Onlyの依頼に基づき、以下を新規作成した。
**新規コードは0行(Python/Dartとも無変更)。**

### 成果物
- `docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md`(新規、約960行):
  Cognitive Pipeline(16段階、各9項目で定義)・Domain Model(12 Domain、
  保存方式比較)・World Model(Events/States/Permissions追加)・Meaning
  Model・Requirement Extraction・Planner・Template Selection(11
  Template Family)・Design Critic(14評価軸)・Self-Revision Loop
  (Schema Repairとの責務分離)・LLM使用方針(全16段階の分類)・
  Confidence Model・Decision Trace・Learning-Ready Design・Failure
  Modes(14種)・M004/M005責務境界・Native扱い・3方式比較(Rule-Based/
  LLM中心/Hybrid、Hybrid採用)・完了条件・自己レビュー。
- `docs/adr/ADR-001`〜`ADR-007`(7件): Hybrid採用・Domain Before UI・
  Rule Before Prompt・Cognitive RevisionとSchema Repairの分離・
  Decision Trace必須化・Provider Independence維持・Confidence の
  制御フロー反映、それぞれの理由・却下案・影響・見直し条件。
- `docs/diagrams/01`〜`09`(Mermaid、9件): Cognitive Pipeline・Module
  Responsibility・Runtime Call Sequence・Decision Trace Flow・
  Revision Loop・Domain Knowledge Flow・Template Selection Flow・
  Confidence Escalation Flow・M004/M005 Boundary。
- `docs/examples/01`〜`06`(6件): 買い物リスト・家計簿・日記・満足度
  アンケート・福祉支援記録・病院予約。福祉支援記録は、Privacy起因の
  HIGH Ambiguityによりパイプラインが確認要求で停止する例として
  意図的に選定した(他5例はApplication Planまで到達)。

### 検証
新規コードを追加していないため、Python(backend 265件・forge_ai 80件)・
Flutterとも無影響。実行して確認した。

## Task029 — FORGE-MILESTONE-005 実物監査(3回目)対応（2026-07-14）

CEOがCEO環境で`Ran 265 tests / FAILED (failures=2)`を報告。原因は、
前回追加したFix 1(Engine/Provider許可リスト化)により、未知の
engine/provider文字列がPydantic入力層で拒否されるようになった結果、
2件の既存テストが「許可リスト導入前の古い経路」を期待したままに
なっていたこと。**コード本体は変更していない**(テストの期待値・
名前・コメントのみ修正)。

### 修正
- `test_unsupported_engine_returns_error_envelope` →
  `test_unknown_engine_string_is_rejected_by_pydantic_before_reaching_pipeline`
  へ改名。期待値を`category=planning_error`から
  `category=request_error, sub_reason=schema_invalid, HTTP 422`へ修正。
- `test_unregistered_provider_returns_provider_error` →
  `test_unknown_provider_string_is_rejected_by_pydantic_before_reaching_pipeline`
  へ改名。同様に`category=provider_error, sub_reason=unavailable`から
  `category=request_error, sub_reason=schema_invalid, HTTP 422`へ修正。
- `test_unimplemented_provider_returns_provider_error`(`provider=
  "openai"`)を、`status_code=503`・`sub_reason=unavailable`まで
  明示的に検証するよう強化。

### 確定した契約
```
未知のengine/provider文字列 → request_error / schema_invalid / HTTP 422
既知だが未実装のprovider     → provider_error / unavailable / HTTP 503
```

### 検証(統一済み件数)
```
Backend tests: 265(248 PASS + 17 SKIP、Claude環境)
Forge AI tests: 80 PASS
python -m compileall backend forge_ai: exit code 0
```
`docs/reports/FORGE-MILESTONE-005-report.md`を、過去3回の監査を
通じて蓄積した古い件数表記(255/9件等)を整理した最終版へ全面更新した。

## Task028 — FORGE-MILESTONE-005 実物監査(2回目)対応（2026-07-14）

CEOがHTTP層を含めて実機検証(Backend 255/255・HTTP 9/9・forge_ai 80/80・
Python compile PASS)した上で、正式完了前に3点の修正+軽微な修正1点を
指摘された。

### Fix 1: Engine/Providerの公開HTTP APIレベルでの許可リスト化
`GenerationOptionsDTO`の`engine`/`provider`を`str`から`Literal`へ変更。
`engine: Literal["forge_ai"] | None`、
`provider: Literal["mock", "openai", "claude", "gemini", "oss"] | None`。
Router内部の`ProviderRouter`は`native`/`local`/Provider名としての
`forge_ai`を後方互換のため引き続き解決できるが、HTTP経由ではこれらを
受理しない(Pydanticが422で弾く)。

### Fix 2: Plan変換時の情報消失(unclassified_diagnostics)を修正
`plan_ir_from_application_plan()`の戻り値を`PlanIR`から
`PlanConversionResult(plan_ir, warnings)`へ変更。以前は
presentation conceptと判定してdata_neededから除外した要素の警告を
変数に貯めるだけでどこにも返していなかった。`Diagnostics`・
`DiagnosticsDTO`へ`conversion_warnings`を追加し、HTTPレスポンス経由で
確認できるようにした。

### Fix 3: HTTP公開APIのmax_repair_attempts上限を2回に制限
`Field(default=None, ge=0, le=10)`だったものを`le=2`へ修正。M005契約
「Repair最大2回・Validator最大3回」との矛盾を解消。0/1/2は許可、
3以上はHTTP入力層で422になる(境界テストを追加)。

### 軽微な修正
`prompt_pipeline.py`・`forge_ai_adapter.py`の冒頭docstringが「このファイル
だけがforge_aiを直接importする」という、実コードと矛盾する(両ファイルとも
forge_aiを直接importする)自己矛盾した記述だったため、正確な記述へ修正した。

### 変更したテスト
- `test_forge_ai_adapter.py`: `PlanConversionResult`型変更に伴い
  `TestPlanAdapter`の6件を`result.plan_ir.X`形式へ更新、新規2件
  (`warnings`が返ることの確認)を追加(計18件)。
- `test_http_api.py`: Fix1(3件)・Fix3(3件)・Fix2(1件)の新規7件を追加
  (計17件、Claude環境ではfastapi未インストールのためスキップ継続)。

### 検証
```
$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.025s
OK (skipped=17)

$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 80 tests in 0.015s
OK
```
248件(backend、HTTP17件を除く)+80件(forge_ai)=328件を実行・全合格
確認した。HTTP17件はCEO環境での再実行が必要(前回9件は実機PASS済み、
今回追加した7件は未検証)。

## Task027 — FORGE-MILESTONE-005: Backend AI Integration Implementation（2026-07-14）

Adapter Contract v1.1に基づき、M004(forge_ai/)とM005(backend/app/ai/
runtime/)を実際に接続する実装を行った。

### 新規/変更ファイル
- `backend/app/ai/runtime/forge_ai_adapter.py`(新規): Intent/Plan/
  RepairIssue/RepairResult/Quality の5つのAdapter関数。CEO指摘4
  (actions_needed固定)・5(key_elements誤分類)への対応を含む。
- `backend/app/ai/runtime/forge_ai_provider_bridge.py`(新規):
  `ForgeAIProviderBridge`。forge_ai.AIProvider Protocolを満たしながら
  M005のLLMAdapterへ委譲する。
- `backend/app/ai/foundation/providers.py`(変更): `MockLLMAdapter`を
  新規実装(指示書「実装するProviderはMockのみ」)。他4 Provider
  (OpenAI/Claude/Gemini/OSS)はStubのまま維持。
- `backend/app/ai/foundation/interfaces.py`(変更): `PlanIR`へ
  `unassigned_actions: tuple[str, ...] = ()`を後方互換で追加。
- `backend/app/ai/runtime/provider_router.py`(変更): `mock`を登録
  (8名前目)、`default_provider_name()`を`"forge_ai"`から`"mock"`へ修正。
- `backend/app/ai/runtime/pipeline_errors.py`(新規): Error Contract
  5分類(+ HTTPリクエスト層用の`request_error`)の例外階層。
- `backend/app/ai/runtime/prompt_pipeline.py`(全面書き換え): 旧
  Protocol注入方式を廃止し、Facade方式
  (`forge_ai.core.pipeline.run_pipeline()`を1回呼ぶ)へ全面改訂。
  Repair Loop(`RepairEngine(provider, max_iterations=1)`)・
  Repair後Quality再評価を実装。
- `backend/app/schemas/ai.py`(全面書き換え): Request/Response/
  Error Envelopeのpydanticモデル。
- `backend/app/routers/ai.py`(全面書き換え): `POST /api/v1/ai/generate`
  をPromptPipeline経由の実装へ更新。
- `backend/app/exception_handlers.py`(新規): `RequestValidationError`・
  `ForgeAIPipelineError`・`Exception`の3種の例外ハンドラ。共通Error
  Envelopeへ統一。JSON構文エラー(400)とスキーマエラー(422)を
  `type == "json_invalid"`で判定。
- `backend/app/main.py`(変更): 例外ハンドラの登録。
- `scripts/verify.ps1`(変更): `pip install -r requirements.txt`
  ステップを追加(HTTPテストがfastapi/pydantic無しでは自己スキップ
  するため、CEO環境で実際にテストが走るようにする)。

### 新規テスト(実行・検証済み、HTTPのみ未検証)
- `backend/tests/test_forge_ai_adapter.py`(新規16件、実行・全合格): 
  Adapter関数群の単体テスト。CEO指摘4・5の回帰テストを含む。
- `backend/tests/test_ai_runtime.py`(PromptPipeline部分を全面書き換え):
  `unittest.mock`でrun_pipeline/validate_forge_document/RepairEngine/
  QualityEngineを制御し、Facade呼び出し1回・Repair Loop・二重ループ
  防止(`max_iterations=1`の検証)・Quality再評価を検証。
- `backend/tests/test_http_api.py`(既存、1箇所の実装ミスを修正):
  `test_unsupported_engine_returns_error_envelope`が期待していた
  HTTP 200を422へ修正(実際のルーター実装は`ProviderError`以外
  すべて422を返すため、200という期待値が誤りだった)。

### 実行結果(事実)
```
$ python -m unittest discover -s backend/tests -p "test_*.py"  # repoルートから
Ran 255 tests in 0.022s
OK (skipped=9)
```
9件はHTTPテスト(`test_http_api.py`)で、fastapi/pydanticがClaude
環境に無いため自己スキップした(エラーではない)。それ以外の246件は
実行・全合格を確認した。

### 未検証事項(正直な申告)
- HTTP層(`schemas/ai.py`・`routers/ai.py`・`exception_handlers.py`・
  `main.py`・`test_http_api.py`)は、Claude環境に`fastapi`・`pydantic`が
  インストールできない(ネットワーク不可、実際に`pip install`を
  試行し失敗を確認済み)ため、**一度も実行できていない**。
  構文は`ast.parse`で静的に確認したのみ。
- JSON構文不正(400)とスキーマ不正(422)の判定
  (`_is_json_syntax_error`、`type == "json_invalid"`という判定基準)
  は、Pydantic v2の一般的な既知の挙動に基づく推測であり、実行確認
  できていない。CEO環境での実機確認が必要。

## Task026 — Adapter Contract v1.1(CEO実コード監査の6指摘に対応）（2026-07-14）

CEOが`ADAPTER_CONTRACT_V1.md`(v1.0)を実コードと突き合わせて監査し、
「Concrete type flow: FAIL」「Pipeline ownership: FAIL」を含む判定を
受けた。以下6点を修正した。**新規コードは追加していない(文書修正のみ)。**

### 最重要修正(FAIL判定の解消)
1. **型境界の修正**: `forge_ai.Compiler.compile()`が`ApplicationPlan`
   しか受け取れず、v1.0の「ApplicationPlan→PlanIR変換→Compilerへ渡す」
   という設計は型エラーになることを、実際にソースを確認して認めた。
   CEO推奨の「粗粒度Facade方式」(`forge_ai.core.pipeline.run_pipeline()`
   を1回だけ呼ぶ)へ全面的に設計変更した。この関数は既に存在しており、
   新規実装は不要だった。
2. **パイプライン所有者の一本化**: M004(`run_pipeline()`)を認知・
   設計パイプラインの唯一の所有者とし、M005(`PromptPipeline`)は
   HTTP/Provider選択/Validator/Repair制御/エラー変換/Diagnostics/
   Response整形に責務を限定した。

### その他の修正
3. Forge IR境界を「dict[str, Any]の型一致」ではなく「Validator合格
   済みdictのみ」へ訂正。
4. `Intent.required_actions`を`actions_needed=()`固定で破棄していた
   問題を修正。`PlanIR`に`unassigned_actions`フィールドを追加する
   必要性を明記(次フェーズの実装課題)。
5. `key_elements`を無条件で`data_needed`へ写す設計を修正し、
   データ実体/ユーザー操作/画面表現概念の3分類方針を追加。
6. HTTP Contractで`engine`(forge_ai)と`provider`(mock等)を分離し、
   Provider既定値を`"forge_ai"`から`"mock"`へ修正。
7. HTTPエラーコードを400(JSON構文不正のみ)/422(スキーマ・型・
   意味的失敗)へ統一。

### 検証
新規コードを追加していないため、Python 224件(backend)+80件
(forge_ai)は無影響。実行して合格を再確認した。

## Task025 — FORGE-MILESTONE-005: Backend AI Integration Adapter Contract（2026-07-14）

CEOロードマップ(M004完了→M005 Adapter Contract→M005実装→M006 Pipeline→
M007 LLM Adapter→M008 Repair→M009 Quality→M010 Native AIβ)に基づき、
M005実装の前段としてAdapter Contractを設計した。**実装は一切行っていない
(設計のみ)。**

### 成果物
`docs/spec/ADAPTER_CONTRACT_V1.md`(新規、約580行)。以下を含む。

- **Shared Types決定**(5ペア): Intent(Adapter変換)・Plan/ScreenPlan
  (Adapter変換)・Forge IR(dictで既に共通、Adapter不要)・RepairResult
  (Adapter変換)・QualityScore/CriticResult(Adapter変換)。
- **設計フェーズで発見した重要なリスク**: forge_ai.RepairEngine(内部で
  最大2回リトライ)をそのままM005のAIRepairとして使うと、M005外側の
  リトライ(最大2回)と掛け合わさり、最大4回の修復試行が発生する
  「二重ループ問題」を発見した。共通指示書6.5節「修正回数の上限」を
  静かに破る実装ミスになりかねない箇所であり、実装着手前に発見できた。
  対応方針(forge_ai.RepairEngineをmax_iterations=1で構築する)を記録した。
- **Error Contract**: 5分類(validation/planning/provider/runtime/
  unexpected)+HTTPステータス対応+provider_errorのsub_reason細分化。
- **Provider Contract**: forge_ai.AIProvider(Prompt型)とM005の
  LLMAdapter(文字列+schema)の関係を整理。後者を実LLM接続の正規契約とし、
  前者はBridge経由で接続する設計とした(統合しない)。
- **HTTP Contract**: `POST /api/v1/ai/generate`のRequest/Response/
  Error/Version形式。
- **Validator Position**: 既存`prompt_pipeline.py`の実装済みフロー
  (Repair前後で必ず検証、Criticより必ず先)を正式な契約として確定。
- **Sequence Diagram**: Conceptual Flow・Runtime Call Sequence・
  Dependency Diagram・Adapter Boundaryの4種類。

### 検証
新規コードを追加していないため、Python 224件(backend)+80件
(forge_ai)は無影響。実行して合格を再確認した。

## Task024 — Forge AI Architecture v1.0 修正(CEOレビュー3点対応)（2026-07-14）

CEOによる`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`実物監査を受け、
確定前に3点を修正した。新規コードは追加していない(文書修正のみ)。

### 修正内容
1. **接続図の分離**: 「概念的な処理順序」と「実行時の呼び出し方向」が
   1つの図に混在していた問題を修正。Conceptual Pipeline(5.1)・
   Runtime Call Graph(5.2)・Source-code Dependency Direction(5.3)の
   3種類へ分離した。実行時の基本方向はM005(Backend AI Integration)が
   M004(Forge AI Core)を呼び出す構造であることを明記(以前は逆方向に
   読める図だった)。実際に`grep`でM005→M004のimportがまだ存在しない
   (未接続)ことを確認した上で図を作成した。
2. **過去記録へのM005読み替え注記**: `docs/DECISIONS.md`(D50〜D55、
   ブロック注記+各見出しへ`(→ M005)`タグ)・`TECH_DEBT.md`(TD20〜TD22、
   同様)・`docs/reports/FORGE-MILESTONE-004-report.md`(冒頭に注記)・
   `CHANGELOG.md`(Task019、注記)へ、歴史的記録を変更せず注記のみ追加した。
3. **ADR Statusの精緻化**: 「Status: FROZEN」を「Status: ACCEPTED —
   RESPONSIBILITY BOUNDARIES FROZEN」「Interface Contract: PROVISIONAL」
   へ修正。Intent/Plan/Forge IRの共有型・M004↔M005 Adapter API・HTTP API
   契約・エラー伝播形式・Provider実装方式の5点を、未凍結(実装時に
   決定する)項目として明示した(6.1章新設)。

### 検証
新規コードを追加していないため、Python 224件(backend)+80件
(forge_ai)は無影響。実行して合格を再確認した。

## Task023 — Forge AI Architecture v1.0 (Architecture Freeze)（2026-07-14）

CEOレビュー「M004は実装マイルストーンではなく、Architecture Freeze
マイルストーンとして整理してください」に基づき対応した。

### 実施内容
- `docs/spec/FORGE_AI_ARCHITECTURE_V1.md`(新規、ADR)を作成し、以下を確定。
  - **M004 = forge_ai/(Forge AI Core)のみ**。旧「FORGE-MILESTONE-004:
    Native AI Phase-1」は**M005(Backend AI Integration)**として正式に読み替え。
  - `backend/app/ai/native/`は**M006以降・Experimental**とし、
    CEO承認なしに変更しないことを確定。
  - 実際のファイルタイムスタンプ調査による時系列(forge_ai/: 7/12、
    backend/app/ai/runtime/第1波: 7/13早朝、第2波: 7/13午前、
    backend/app/ai/native/: 7/13午前、第2波の直後)を記録。
  - 責務境界図(forge_ai/ vs backend/app/ai/runtime/ vs
    backend/app/ai/native/)を作成。
  - 接続図(User → forge_ai → backend runtime → Validator → Forge
    Runtime)を作成。現時点では**全区間が未接続**であることを明記。
- `backend/app/ai/runtime/README.md`・`backend/app/ai/native/README.md`
  を更新し、新しいマイルストーン番号(M005・M006以降)を反映。
- `docs/spec/NATIVE_AI_STATUS_NOTE.md`・`forge_ai/docs/DESIGN_DECISIONS.md`
  (D7)を更新し、番号重複が解消されたことを記録。

### 過去記録の扱い
CHANGELOG.md Task019・docs/DECISIONS.md D50〜D55・TECH_DEBT.md
TD20〜TD22・`docs/reports/FORGE-MILESTONE-004-report.md`は書き換えず、
歴史的記録として残した(本ADRを正典として参照する運用へ変更)。

### 新規コードは無し
本Taskは設計文書(ADR)の作成のみであり、`forge_ai/`・
`backend/app/ai/runtime/`・`backend/app/ai/native/`のPythonコードは
一切変更していない。

## Task022 — FORGE-MILESTONE-004: Forge AI v0.1 (Cognitive Engine) 正式提出（2026-07-14）

「FORGE-MILESTONE-004を開始してください。Domain Model・World Model・
Meaning Model・Intent Model・Plannerを実装してください」という依頼を
受けた。この依頼内容と完全に一致する実装(`forge_ai/`)が既に存在し
80テスト全合格の状態だったため、ゼロから再実装せず、既存実装を
検証・強化した上でM004の正式提出物として採用した(詳細は
`forge_ai/docs/DESIGN_DECISIONS.md` D6)。

### 重要な発見: 「FORGE-MILESTONE-004」という名前の重複
`docs/reports/FORGE-MILESTONE-004-report.md`という、同じ名前で
異なる内容(2026-07-13付「Native AI Phase-1（Intent Engine）」、
`backend/app/ai/runtime/`拡張、D50〜D55・TD20〜TD22で記録済み)の
報告書が既に存在することを確認した。前回のFORGE-MILESTONE-003.1で
このファイル群を「由来不明」と報告していたが、実際には正規の記録が
あったため、その報告を訂正した。

### 実施内容
- `forge_ai/`全ソースファイル(20件)のimport文を再監査し、LLM SDK・
  Flutter・Backend APIへの依存が無いことを再確認。
- `py_compile`で構文エラー0件、`ast`静的解析で型ヒント・Docstring
  100%を再確認。
- 80件のUnit Testを再実行し、全件合格を再確認。
- `docs/spec/NATIVE_AI_STATUS_NOTE.md`を更新(訂正を含む)。

### 未解決のまま残した点
- `forge_ai/`と「Native AI Phase-1」(`backend/app/ai/runtime/`)の
  統合方針、および名前の重複整理はCEO判断事項として残す。
- `backend/app/ai/native/`の由来は依然未確認。

## Task021 — FORGE-MILESTONE-003.1 CEO実機再検証フィードバック対応（2026-07-13）

CEOがCEO環境で実際に`flutter analyze`(PASS)・`flutter build web`(PASS)・
`flutter test`(2件失敗)・`scripts/verify.ps1`(Python exit 9009)を
検証した結果を受けて対応した。

### 修正
- `ForgeStateStore._coerce()`: 「対象キーが存在しない場合、valueの
  実行時型から新規State作成する」という分岐を削除。Forge Languageの
  契約上、state_refは事前宣言されている前提であり、存在しないキーへの
  `set_value`/`set_state`は`ActionResultKind.invalidTarget`として
  失敗すべきだった。この分岐により、CEO実機の`flutter test`で
  `action_result_kind_test.dart`の2件(`set_value`単体・composite経由)が
  失敗していた。既存の`write()`呼び出し箇所が全てこの分岐に依存して
  いないことを確認した上で削除。
- `scripts/verify.ps1`: `python`を固定で呼んでいたため、`py`のみが
  PATHにある環境でexit code 9009(コマンドが見つからない)になっていた。
  `py`を優先し、無ければ`python`にフォールバックする方式へ変更。

### 未検証事項
- 上記修正後の`flutter test`・`scripts/verify.ps1`の実際の再実行は、
  Claude環境にFlutter SDK・PowerShellが無いため行えていない。
  修正内容は手動トレースで期待結果と一致することを確認済み。
  CEO環境での再検証が必要。

## Task020 — FORGE-MILESTONE-003.1 CEOレビュー対応（2026-07-13）

FORGE-MILESTONE-003.1レポートへのCEOレビュー(6項目+メタ指摘)に対応した。

### 修正
- レポート内の確率的表現(「十中八九」)を削除し、「最も可能性が高い仮説」
  という断定しない表現へ統一。
- `ActionResult`に`ActionResultKind`(success/noOp/invalidTarget/
  invalidSource/validationError/runtimeError)を追加し、全8 Action種別
  (navigate/go_back/set_value/toggle_state/reset_state/add_item/
  submit_form/composite)がこの共通enumへ収束するよう統一した。
  既存の`success`/`reason`フィールドは後方互換のため無改変。
  `test/json_ui/runtime/action_result_kind_test.dart`(新規15件)で検証。
- `scripts/verify.ps1`: 最終サマリーをPASS/FAIL/WARNINGの3区分にし、
  `flutter devices`チェックを追加(Chrome未検出時は`-RunChrome`を
  安全にWARNINGスキップ)。
- `backend/tests/test_golden_mock_generator.py`・`tests/golden/*.json`
  (12カテゴリ)を新設。Mock Generator出力を凍結し、変更を即検出する
  Golden Testを追加(実際に1文字改変して検出することを確認済み)。
- `backend/app/ai/runtime/README.md`・`backend/app/ai/native/README.md`
  を新設し、Experimental/Not connectedのステータスをディレクトリ単位で明示。

### 分離
- Native AI / MILESTONE-004関連の話題をM003.1レポートから分離し、
  `docs/spec/NATIVE_AI_STATUS_NOTE.md`として独立させた
  (CEOレビュー「別章ではなく別Issue・別Taskとして切り離す」に対応)。

### テスト
- Python: 224件(既存221件 + Golden Test 3件)、実行・全合格を確認。
- Dart: 新規15件(action_result_kind_test.dart)、Claude環境では未実行。

## Task019 — FORGE-MILESTONE-004: Native AI Phase-1（Intent Engine）（2026-07-13）

> **【2026-07-14注記】** 「FORGE-MILESTONE-004」は現在「M005: Backend AI
> Integration」として読み替える。正典は`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`。

CEO実測(Flutter Test 223 PASS、Runtime基盤完成)を前提に、Forge Native AIの
土台(PHASE1〜9、いずれも設計・Stubのみ、AI推論は未実装)を構築した。
今回はPython(backend/)のみ変更し、Flutter/Dartは一切変更していない。

### 既存資産との重複を避けた設計判断(詳細はDECISIONS.md D50〜D54)
- `IntentIR`(既存)を拡張(entities/platform/complexity/category/
  output_type追加)。新しいIntent型は作らず、後方互換性を維持した。
- `IntentParser`(新規)を、既存`AIPlanner`とは別に追加。`AIPlanner`は
  変更していない。
- `Template`/`TemplateRegistry`(新規): 既存3 Template(checklist/memo/
  form)を構造化メタデータでカタログ化。新規Template実装は追加していない。
- `TemplateSelector`(新規、Stub)。
- `ProviderRouter`へ`native`/`local`エイリアスを追加(新規Provider実装は
  追加していない)。
- `NativeAIRuntime`(新規): 全構成要素を束ねるbundle。
  `is_fully_stubbed()`で「動いたふり」をしていないことを機械的に検証可能。

### テスト
- `tests/test_native_ai_phase1.py`(新規27件)、実行・全合格。
- 既存の`test_all_five_providers_registered`を`test_all_seven_provider_names_registered`
  (7件)へ更新(エイリアス追加に伴う、カバレッジ拡張目的の変更)。
- Python合計: backend 221件・forge_ai 80件、実行・全合格を確認。

### ドキュメント
- `docs/spec/AI_RUNTIME.md`更新。`TECH_DEBT.md` TD20〜TD22追加
  (Output Safety・Prompt Injection・IRバージョニングの未設計を記録)。

### 未実施
- 実際のAI推論(全コンポーネントがStubのまま)。
- Flutter側の変更・検証(今回はPythonのみ)。

## Task018 — FORGE-MILESTONE-003.3: add_item_regression_test.dart 誤検知修正（2026-07-13）

CEO実測(backend Python 192 PASS・forge_ai 80 PASS・flutter analyze警告0・
flutter build web PASS・Chrome起動PASS)のうち、`flutter test`1件のみ失敗。
`add_item_regression_test.dart`の「空白のみ入力」テストが、
`expect(find.text('   '), findsNothing)`でチェックリスト誤追加を判定していたが、
Flutterの`find.text()`はTextField内部のEditableTextの現在値ともマッチするため、
`emptySource`時にクリアされず残る入力欄自身の`"   "`を誤検出していた
(Runtimeの誤りではなくテストコードの誤検知)。判定方法を`ListTile`件数の
前後比較へ変更し修正した。変更対象は当該テストファイルのみ。

## Task017 — FORGE-MILESTONE-003.2: verify.ps1 Encoding Fix（2026-07-13）

CEO実機で`scripts/verify.ps1`が文字化けにより構文エラーで起動しなかった
問題を修正した。**今回はverify.ps1(および関連するREADME記述)のみを
変更し、他は一切変更していない。**

- **根本原因(実際にバイト列を検証して確定)**: ファイルはBOM無しの
  正しいUTF-8だったが、Windows PowerShell 5.1はBOM無し`.ps1`を
  システムのANSIコードページ(日本語Windowsでは既定Shift_JIS)で
  読み込むため、UTF-8の日本語部分が文字化けし構文エラーになった。
- **修正**: `verify.ps1`から日本語を排し英数字のみのメッセージへ変更、
  UTF-8 BOM付きで保存する二重対策を実施。
- `README.md`の該当セクションへ、上記の原因と対策を明記。

## Task016 — FORGE-MILESTONE-003.1: Runtime State Contract Fix & Final Quality Closure（2026-07-13）

CEO実機でChrome起動・複数カテゴリ操作を実施した結果、8カテゴリで生成
成功を確認した一方、家計簿カテゴリの追加操作で`add_item_failed`という
Runtime Errorが実機発生した。根本原因を特定・修正し、全12カテゴリの
Action契約を監査、検証スクリプトを新設した。

### PHASE1〜2: add_item_failedの根本原因と修正
- **根本原因**: 生成JSON自体は完全に正しかった(実際に生成・Validator確認済み)。
  `ForgeStateStore.addChecklistItem()`が、「target/sourceのState参照が
  無効(契約違反)」と「sourceのテキストが空(ユーザーが未入力のまま追加を
  押しただけの正常操作)」を同じ`false`として返し、Dispatcherが両方を
  同一の`add_item_failed` ERRORとしてログしていたことが原因と判断した。
- `AddChecklistItemOutcome`列挙型(`added`/`emptySource`/`targetMissing`/
  `sourceMissing`)を新設し、正常操作(空入力)ではERRORを出さず、
  契約違反のみをERROR扱いにするよう修正した(全カテゴリ共通の一般契約
  として修正。家計簿だけの特別扱いはしていない)。

### PHASE3〜6: 契約監査・テスト
- `backend/tests/test_all_categories_action_contract.py`(新規4件):
  全12カテゴリについて、Validatorとは独立したロジックでAction参照の
  実在性・型一致を再検証。
- `frontend/test/json_ui/add_item_regression_test.dart`(新規4件)・
  `forge_state_store_test.dart`拡張: add_itemの全4アウトカムを単体・
  E2Eレベルで検証。

### PHASE8: Web警告の整理
- `web/index.html`: `mobile-web-app-capable`タグ追加、明示的な
  `viewport`タグを削除(Flutter Webが自動挿入するため、明示すると
  Chrome Console警告が出ることをWeb検索で確認)。
- `flutter/lifecycle channel`警告はFlutter Engine自体の既知の起動時
  タイミング警告(複数の無関係プロジェクトで同一報告を確認)であり、
  コード側での対応不可と判断・文書化。

### PHASE9〜10: 技術的負債
- TD18(Noto Font未同梱)・TD19(計算アプリ等がGeneric fallbackへ落ちる
  実態)を`TECH_DEBT.md`へ追加。

### PHASE12: 検証スクリプト
- `scripts/verify.ps1`・`scripts/verify.bat`新設。Python Test〜
  flutter build webまでを1コマンドで実行し、失敗しても止まらず
  最後にサマリー表示する。Claude環境では未実行(README.md参照)。

### テスト
- Python: 192件(188 + 4新規)、実行・全合格を確認。
- Dart: 静的カウントで新規8件追加。Claude環境では未実行。

## Task015 — FORGE-MILESTONE-003: Analyzer Zero → Chrome Verification → Native AI Foundation（2026-07-12）

CEO実測(Python 167 PASS・**Flutter Test 212 PASS**・Web Build PASS・
Runtime/Chrome/Mock Generator/Language v1.2/Widget v1.1/E2E 全PASS)を受けて、
残る`flutter analyze`警告3件の解消と、Forge Native AI Foundationの構築を行った。

### PHASE1: Analyzer完全ゼロ対応
- `forge_runtime_state.dart`: 未使用import(`forge_form_validator.dart`)を
  自動検出ツールで発見・削除。
- `ForgeStateStore({})`(8箇所、`forge_state_store_test.dart`・
  `forge_action_dispatcher_test.dart`)・`readChecklist`のswitch式・
  `_validationErrors`関連2箇所・`v1_1_widgets_test.dart`の`state ?? {}`に、
  Map/Setの構文的あいまいさを避けるための明示的型引数を追加。

### PHASE6〜9: AI Runtime Foundation(backend/app/ai/runtime/）
- `prompt_pipeline.py`(新規): Natural Language → Intent → Plan → JSON →
  Validator → Critic → Repair → Final JSON のフローを実装。
  `planner.py`・`critic.py`・`repair.py`・`context_builder.py`・
  `provider_router.py`(いずれも既存、責務定義+Stubのみ)と組み合わせる。
- `tests/test_ai_runtime.py`(新規、21件): 型の重複防止・Stubが例外無く
  成功しないことの確認・ProviderRouterの実ルーティング・
  PromptPipelineのRepair Loop(最大試行回数)を検証。

### PHASE10: ドキュメント
- `docs/spec/AI_RUNTIME.md`・`PROMPT_PIPELINE.md`・`NATIVE_AI_ROADMAP.md`新設。

### テスト
- Python: 188件(167 + 21新規)、実行・全合格を確認。
- Dart: CEO実測212件PASS(Claude環境では未実行)。

### 既知の未達成事項
- PHASE1修正後の`flutter analyze`結果はClaude環境で未検証。
- Native AI(forge_ai/との接続)は未実装(意図通り、TD16参照)。

## Task014 — FORGE-MILESTONE-003: Stateful Runtime Foundation（2026-07-11）

Forge Language v1.2を新設(v1.0/v1.1は無改変で凍結維持)。State Store・
Action Dispatcher・Form Validationを正式なRuntime契約として導入した。

### 追加(Language v1.2)
- State型`number`。
- Action型5種: `set_state`/`toggle_state`/`reset_state`/`submit_form`/`composite`
  (v1.0/v1.1の`navigate`/`go_back`/`set_value`/`add_item`は維持)。
- `text_field`/`checkbox`への`validation`プロパティ(6ルール種別)。

### 追加(Dart Runtime、`json_ui/runtime/`新設)
- `ForgeStateStore`: 単一のState Store。汎用read/write + 型別便利メソッド。
- `ForgeActionDispatcher`: 全Actionの一元的な入口。`ActionResult`を返す。
  composite最大10件・ネスト最大3段。
- `ForgeFormValidator`: 6種の検証ルールを実装。

### 変更
- `ForgeRuntimeState`: 内部実装をRuntime層への委譲に置き換えた
  (既存の公開APIは無改変)。
- `forge_renderer.dart`: `navigationDepth`による無限遷移防止、診断ログ
  (`ForgeLogger`)を追加。
- `widget_registry_v1_1.dart`: checkboxはtoggle_state経由に統一、formの
  送信ボタンはsubmit_form経由に変更(Validation実行の要)、text_field/
  checkboxにエラーメッセージ表示を追加。
- Mock Generator(Python/Dart both): Survey Templateのコメント欄に
  `max_length` validationを追加(v1.1→v1.2へバージョン更新)。

### テスト
- Python: 135 → **167件**(v1.2 Schema/Action 32件を追加)。
- Dart: 165 → **211件(静的カウント予測。実行未検証)**。State Store・
  Action Dispatcher・Form Validator単体テスト(40件)、State Binding Widget Test
  (5件)、Survey Form ValidationのE2Eテスト(1件)を新規追加。

### 既知の未達成事項
- 今回追加・変更した全コードについて、Claude環境では`flutter analyze`・
  `flutter test`・`flutter build web`のいずれも実施できていない。

## Task013 — FORGE-MILESTONE-002.2: Web Platform Files Inclusion（2026-07-11）

CEOがFORGE-MILESTONE-002.1提出物で`flutter build web`を実行したところ、
`frontend/web/`が存在せず`This project is not configured for the web`で
失敗した(ZIP内に`frontend/web/`が無いことも確認された)。方針を修正し、
`web/`一式をClaude側で追加した。

### 追加(新規、`frontend/web/`)
- `index.html`・`manifest.json`: Flutter公式ドキュメント
  (`docs.flutter.dev/platform-integration/web/initialization`、Flutter 3.44.0
  向け記述として確認)を根拠に手書き。`flutter_bootstrap.js`は含めていない
  (`flutter build web`がビルド時に自動生成することを公式ドキュメントで確認済み)。
- `favicon.png`・`icons/Icon-192.png`・`icons/Icon-512.png`・
  `icons/Icon-maskable-192.png`・`icons/Icon-maskable-512.png`:
  Pillowで生成した有効なPNGファイル(ForgeThemeのaccent色+「F」)。

### 方針の変更点
- 従来「プラットフォームファイルは捏造しない」としていた方針を、`web/`に限り
  変更した。理由は`docs/development/FLUTTER_VALIDATION.md`に明記(`.metadata`
  等の不透明なSDK内部情報とは異なり、`web/index.html`・`manifest.json`は
  公開されたテンプレートであり、Web検索で現行版を確認できたため)。
- `android/`・`ios/`・`windows/`・`linux/`・`macos/`・`.metadata`は
  引き続きCEO環境での生成が必要(方針変更なし)。

### 差分監査
- `pubspec.yaml`・`analysis_options.yaml`・`lib/main.dart`・既存テスト・
  Language/Runtime/Validator/AI Foundationのコードは1バイトも変更していない
  ことを確認した(`frontend/web/`配下のみ新規追加)。
- Python 135件を再実行し、無影響であることを再確認した。

### 既知の未達成事項
- 実際に`flutter build web`が成功するかはClaude環境で検証できていない。

## Task012 — FORGE-MILESTONE-002.1: Analyze Zero-Issue Fix & Final Closure（2026-07-11）

CEO実機実測(Python 135/135 PASS・**Flutter Test 166/166 PASS**・Web Build PASS・
`flutter analyze` 3 issues found)を受けて、残る3件のみを最小修正した。

### 修正
- `mock_generation_datasource.dart:47`: `prefer_const_constructors`。
  `FormTemplateParams(...)`の引数が全てcompile-time constantだったため
  `const`化した(`questions`リストにも明示的型引数`<FormQuestion>[...]`を付与)。
- `mock_app_generation_repository.dart:27`: `inference_failure_on_instance_creation`。
  `Future.delayed(...)` → `Future<void>.delayed(...)`(戻り値未使用のため`void`が正しい)。
- `v1_1_widgets_test.dart:94`: `inference_failure_on_collection_literal`。
  空リスト`[]` → `<String>[]`(string_list state値としての実際の型に合わせた)。
- Task 4監査で発見した同種1件: `forge_document.dart`の`?? const []`にも
  明示的型引数`<String>[]`を追加(念のための対応、影響範囲は限定的)。
  他に`Future.delayed(`の無型引数呼び出しは無いことを確認済み。

### 既知の未達成事項
- 上記4件の修正により`flutter analyze`が`No issues found!`になるはずだが、
  Claude環境にDart SDKが無く実行できていない。CEO再実行での確認が必要。

## Task011 — FORGE-MILESTONE-002: Forge Language v0.3 + AI Foundation（2026-07-11）

CEOから「Checklist専用デモからの卒業」を目的とした一括マイルストーンとして依頼。
途中報告無しで完遂した(依頼書の方針通り)。

### 判明した事実(CEO実機実測、依頼書冒頭で共有)
- FORGE-RUNTIME-003完了報告: `flutter analyze` No issues found!、
  `flutter test` 103/103 PASS、Chrome実機でHome→Confirm→Generated Screen→
  チェックリスト操作まですべて成功。Mock Mode成功。

### PHASE1: Forge Language v1.1(6 Widget追加)
- `shared/schemas/ui_schema.v1.1.json`新設。v1.0(凍結)は変更せず、
  heading/checkbox/card/list/divider/formの6種を追加。
- Widget追加に伴いAction/State型は追加していない(既存4種/4型で表現)。

### PHASE2: Runtime再編
- `widget_registry_core.dart`新設(Registry機構をWidget実装から分離)。
- `widget_registry_v1_1.dart`新設(v1.1の6 Widget実装)。
- v1.0の6 Widget実装(`widget_registry.dart`)はロジック無変更。
- 新Widget追加時、既存ファイルに触れず新規ファイル+登録1行で完結する手順を確立
  (`docs/spec/RUNTIME_SPEC.md`)。

### PHASE3: Validator拡張
- `schema_validator.py`をv1.0/v1.1の2バージョン対応へ書き換え。
  v1.0文書がv1.1専用Widgetを使うと不合格になる(version gating)。
  既存120件のテストは無改変のまま全て合格を維持。

### PHASE4: Template System
- `docs/spec/TEMPLATE_SPEC.md`。Checklist(既存を再構成)・Memo(新規)・
  Form(新規、2画面・navigate実演・card実演)の3Template。

### PHASE5: Mock Generator v2
- Python/Dart双方をTemplate方式へ書き換え。家事/アンケート/メモの3
  カテゴリを追加(計12カテゴリ)。既存9カテゴリの出力は完全に無変更
  (回帰テストで確認)。

### PHASE6: AI Foundation(設計のみ)
- `backend/app/ai/foundation/interfaces.py`: IntentPlanner/ProductPlanner/
  LanguageGenerator/RepairEngine/Critic/PluginRouter/Memory/Conversation/
  PromptBuilder/LLMAdapterのProtocol定義。
- `backend/app/ai/foundation/providers.py`: OpenAI/Claude/Gemini/OSS/
  ForgeAIの5Providerスタブ(全て`NotImplementedError`)。

### テスト
- Python: 97 → **135件**(v1.1 Widget 23件・Mock Generator v2 10件・
  AI Foundation 5件を追加)。
- Dart: 95 → **165件(静的に数え上げた予測値。D36参照)**。最終検証パスで
  `mock_generator_renderer_contract_test.dart`(FORGE-RUNTIME-002由来)に
  sealed classの非網羅switchという実バグ(v1.1 Widget型がswitch式に
  反映されておらず、コンパイルエラーになる状態)を発見・修正し、
  対象カテゴリも8→11種類へ拡張した(`docs/DECISIONS.md` D36)。
  いずれもClaude環境では未実行、CEO環境での`flutter test`実行で確定値を確認する必要がある。

### ドキュメント
- 新設: `docs/spec/LANGUAGE_SPEC.md`・`RUNTIME_SPEC.md`・`TEMPLATE_SPEC.md`・
  `AI_SPEC.md`。
- 更新: `README.md`・`docs/ROADMAP.md`・`docs/DECISIONS.md`・`TECH_DEBT.md`。

### 既知の未達成事項
- 今回追加した全コードの`flutter analyze`/`flutter test`/Chrome実機確認は
  Claude環境で未実行。CEO確認が必須(FORGE-MILESTONE-002-report.md参照)。

## Task010 — FORGE-RUNTIME-003: Infinite Width Button Constraint Fix（2026-07-11）
### 修正(根本原因)
- `core/theme/forge_theme.dart`: `elevatedButtonTheme.minimumSize`を
  `Size.fromHeight(56)`(実質`Size(double.infinity, 56)`)から`Size(0, 56)`へ。
  Row内の`ElevatedButton`が`BoxConstraints forces an infinite width`で
  描画に失敗していた根本原因(CEO実機のスタックトレースで確定)。
- `home_screen.dart`: 送信ボタンを`SizedBox(width: double.infinity)`で
  明示的に全幅化(テーマ側の暗黙の全幅化が無くなったため)。
### 追加
- `test/json_ui/button_layout_regression_test.dart`(Button×8レイアウト
  シナリオの回帰テスト)。
### 訂正
- FORGE-RUNTIME-002で行った3つの修正(内側Columnのmain AxisSize・
  ListTileへのKey付与・GestureDetectorからIconButtonへの変更)は、
  **今回の根本原因ではなかった**ことが確定した。無条件に元へ戻してはいないが
  (それぞれ独立して妥当な改善のため)、「原因修正」ではなく「付随改善」として
  記録を訂正した(`docs/DECISIONS.md` D26追記・D29参照)。
### 既知の未達成事項
- 修正後の`flutter analyze`/`flutter test`/実機Chrome確認はClaude環境で未実行。

## Task009 — FORGE-RUNTIME-002: Generated Screen Rendering Fix（2026-07-11）
### 修正
- `widget_registry.dart`の`_buildChecklist`: 内側Columnに`mainAxisSize: min`を
  明示、各ListTileに`ValueKey`を付与、leadingを`GestureDetector+Icon`から
  `IconButton`へ変更(CEO実機で確認された「本文空白」「RenderBox例外らしき
  ログ」への対応。根本原因は完全なスタックトレースが無く断定していない)。
### 追加
- `test/e2e/kids_checklist_generation_flow_test.dart`(Home→Confirm→生成→
  チェックリスト操作までの1本のテスト)。
- `test/.../mock_generator_renderer_contract_test.dart`(8カテゴリ×8観点=64件、
  「Schemaとして有効」だけでなく「現行Rendererで描画可能」を検証)。
- `docs/spec/MOCK_GENERATOR_CONTRACT.md`(Python/Dart版Mock Generatorの
  期待構造を固定。機械比較で差分0件を確認)。
### 判明した事実(CEO実機実測)
- Mock Modeでのナビゲーション(Home→Confirm→Generated Screen遷移)は成功。
  MOCKバッジ表示・Backend接続エラー無し、いずれも確認済み。
- Generated Screenの本文(チェックリスト)が空白で表示される不具合を確認。
- Console/PowerShellログに「Cannot hit test a render box that has never
  been laid out」に類するRenderBox関連の出力を確認(完全なスタックトレース
  は未取得)。
### 既知の未達成事項
- 修正後の`flutter analyze`/`flutter test`/実機Chrome確認はClaude環境で未実行。
- 根本原因の完全な特定には至っていない(3点の対処療法的修正を適用)。
- TD10(Python/Dart二重管理)は今回も解消済みにしていない。

## Task008 — FORGE-RUNTIME-001: Runtime Mock Mode & First Interactive Experience（2026-07-11）
### 追加
- `core/config/app_config.dart`(`mockMode`設定、既定でBackend不要)。
- `core/utils/forge_logger.dart`(構造化ロギング、新規パッケージ依存なし)。
- `data/datasources/mock_generation_datasource.dart`(Mock GeneratorのDart移植)。
- `data/repositories/mock_app_generation_repository.dart`。
- 画面右上のMOCK/LIVE Badge(`main.dart`、Flutter標準`Banner`を流用)。
- `test/.../mock_generation_datasource_test.dart`(実質23件のテストケース)。
- `docs/development/FLUTTER_VALIDATION.md`にMock Mode節を追記。
### 変更
- `data/repositories/app_generation_repository_impl.dart` →
  `http_app_generation_repository.dart`(`HttpAppGenerationRepository`に改名)。
  エラーメッセージを簡潔化(開発者向け詳細はログへ)。
- `presentation/providers/app_generation_provider.dart`: Http/Mockの
  DI切り替えに対応。
- `generated_app_screen.dart`: 生成中もAppBar(戻るボタン)を表示。
- `confirm_screen.dart`: ボタン連打防止。
- `README.md`: セットアップ手順をCEO実測ベースへ更新、Mock/Live切替方法を追記。
### 既知の未達成事項
- 今回追加した変更後の`flutter analyze`/`flutter test`はClaude環境で未実行。
  CEOの再実行結果待ち。
- Mock Generatorのロジックは引き続きPython/Dartの二重管理(TECH_DEBT.md TD10)。

## Task007 — FORGE-MERGE-005: Flutter Analyze Zero-Issue Fix（2026-07-11）
### 修正
- `home_screen.dart`・`confirm_screen.dart`・`forge_renderer.dart`の
  `MaterialPageRoute`3箇所に明示的な型引数`<void>`を付与
  (CEO実機の`flutter analyze`で検出されたWarning 3件への対応)。
  Repository全体を`MaterialPageRoute`で検索し、この3箇所以外に無いことを確認済み。
### 判明した事実(CEO実機実測)
- `flutter test`: **7/7 PASS**(FORGE-MERGE-003〜004で追加した全テストが合格)。
- `flutter analyze`: Error 0、Warning 3(`MaterialPageRoute`型引数、上記で対応)。
### 既知の未達成事項
- 修正後の`flutter analyze`/`flutter test`はClaude環境で未実行。CEOの再実行結果待ち。
- 現行テストスイートはNavigator.pushの実遷移を直接検証していない(技術的負債として記録)。

## Task006 — FORGE-MERGE-004: Flutter Analyze Fix & Repository Completion（2026-07-11）
### 修正
- `home_screen.dart`: 非推奨の`withOpacity(0.6)`を`withValues(alpha: 0.6)`へ置換
  (CEO実機の`dart analyze`/`flutter analyze`で検出されたinfo 1件への対応)。
- `test/features/.../home_screen_test.dart`: `find.text()`によるTextField内容確認を
  `TextField.controller.text`の直接確認へ変更(finderの一意性が断定できなかったため)。
- `ci.yml`: Flutterバージョン指定を根拠のない暫定値(3.22.0)からCEO実機の
  実測値(3.44.5)へ更新。
### 追加
- `docs/development/FLUTTER_VALIDATION.md`(プラットフォーム構成方針・パス/シェル
  注意事項・検証履歴)。
- `docs/reports/`(過去レポートFORGE-MERGE-001〜003の永続保存)。
### 判明した事実(CEO実機実測)
- 環境: Flutter 3.44.5 / Dart 3.12.2 / Windows 10 / `C:\forge_verify\frontend` / cmd.exe。
- `flutter clean`・`flutter pub get`・`dart analyze`・`flutter analyze`は成功
  (info 1件のみ)。
- `flutter test`は、テスト未反映の旧ローカルRepositoryで実施されたため、
  7件のテスト自体の合否は未検証のまま。
- Web/Windows Buildはプラットフォーム未生成のため未実施(Windowsは追加で
  Visual Studio C++ Desktop開発ツールも未導入)。
### 訂正した過去の記述
- FORGE-MERGE-003で最有力候補としていた`package_config.json`解決エラー説は、
  裏付ける証拠が得られなかった。
- Analysis Server crashは、ASCIIパス+cmd.exe経由の実行で再現しなくなった
  (原因はパス文字種・シェルの一方または両方の可能性が高いが未確定)。
  詳細は`docs/reports/FORGE-MERGE-003-report.md`冒頭の訂正注記を参照。

## Task005 — FORGE-MERGE-003: Flutterプロジェクトとしての成立性（2026-07-11）
### 追加
- `frontend/analysis_options.yaml`(新設。flutter_lintsを実際に有効化)。
- `frontend/test/`配下にテスト3ファイル・7件(smoke_test.dart・home_screen_test.dart・
  forge_fallback_widget_test.dart)。
### 判明した事実
- CEO実測により、`frontend/`が一度も`flutter create`を通っていないことが確定
  (android/ios/windows/linux/macos/web/.metadataがすべて欠如)。
- `flutter analyze`がFormatExceptionでAnalysis Server crash、`flutter test`は
  テスト不在、`flutter build windows`はDesktop Project未構成で失敗。
### 既知の未達成事項
- FormatExceptionの根本原因は未確定(優先順位付き候補のみ)。CEOからの追加情報
  (エラー全文・スタックトレース)待ち。
- `windows/`等プラットフォームフォルダの生成は意図確認待ちのため未実施。

## Task004 — FORGE-MERGE-002: Foundation Hardening（2026-07-11）
### 追加
- Validatorテストを26件→97件へ拡張(`test_schema_validator_extended.py`)。
- `docs/spec/RENDERER_API.md`(Renderer公開API一覧・互換性ポリシー)。
- `docs/spec/LANGUAGE_FREEZE.md`(Language versioning方針)。
- `TECH_DEBT.md`(技術的負債8項目)。
### 修正
- `widget_registry.dart`: Row内の全widgetを一律Expandedにしていた不具合を修正
  (text_fieldのみExpanded)。
- `forge_renderer.dart`: const付与漏れ1件。
### 既知の未達成事項
- `flutter analyze`/`flutter test`はClaude環境で未実行(Dart SDK無し)。CEO確認必須。

## Task003 — FORGE-MERGE-001: Prototype統合と最初の縦の一本（2026-07-11）
### 追加
- Forge Language v1(`shared/schemas/ui_schema.v1.json`)を確定。
- Validator(`schema_validator.py`)・Mock Generator(`mock_generator.py`)を新設。
- `POST /api/v1/ai/generate` エンドポイント。
- Flutter Runtime(`json_ui/`: schema/widget_registry/renderer)。
- Prototype v0.1.3のHome/Confirm画面を移植、Tool画面をGeneratedAppScreenへ置換。
- `docs/DECISIONS.md`・`KNOWN_ISSUES.md`(リポジトリ直下)を新設。
### 修正
- Inspiration Cards 8種類のうち6種類が生成ロジック未対応だった不具合(3→8カテゴリへ拡張)。
- `confirm_screen.dart`の古い音声入力言及コメントを削除。
- `docs/AI.md`のSchema例を実装したv1に合わせて修正。
### 既知の未達成事項
- Dart/FastAPI層はClaude環境で未実行。

## Task001〜Task002 — Foundation初期構築（2026-07-07、Claude以前の作業）
### 追加
- Clean Architecture / Feature First / レイヤードアーキテクチャに基づく
  ディレクトリ構成一式。
- `docs/`配下の設計文書6件(README/Architecture/API/Database/AI/Roadmap)。
- FastAPI最小構成(`/health`のみ)・Flutter最小構成(プレースホルダー画面)。
- `.ai/`・`.agents/`・`PROMPTS/`・`docs/tasks/`・`docs/prompts/`。
### 備考
本CHANGELOGはTask003(FORGE-MERGE-001)の監査時点で遡って記録したものであり、
Task001・Task002当時にリアルタイムで書かれたものではない。詳細は
`docs/tasks/task001.md`・`task002.md`を参照。
