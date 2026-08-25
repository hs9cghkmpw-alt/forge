# Forge Growing AI Architecture

## FORGE-019 revision evidence path

Semantic corrections flow through artifact/version check → typed target resolution → local patch → Validator/Critic → RevisionRecord → REVISION LearningEvent. Lineage stores operation/target/design-role IDs and a local visual-manifest reference, not raw correction text or ArtifactHandle. Export evaluation has a privacy-safe policy-context snapshot. Screenshots are local evidence only, not cloud/training artifacts.

**位置付け: AI / Learning 領域の正式Architecture**
制定 2026-08-24 / 指示書 FORGE-GROWING-AI-ARCHITECTURE-017

---

## 0. この文書の位置と読み方

### 上位文書との関係

| 順位 | 文書 | 関係 |
|---|---|---|
| 1 | `docs/PRODUCT-DIRECTION.md` | **最上位。変更不可。** この文書はそれに従属する |
| 2 | **この文書** | AI / Learning 領域の正式Architecture |
| 3 | `docs/ROADMAP-TO-TARGET.md` | 段取り |

これは PRODUCT-DIRECTION の**変更ではない**。PRODUCT-DIRECTION §5
（Cloud出力はTeacher CandidateでありTruthではない）と §6
（Local AIを後回しにしない／優先順位 Knowledge→Experience→Shadow→
Dataset→LoRA→Benchmark）を、**Forge製アプリ全体へ一般化した**もので
ある。矛盾したら PRODUCT-DIRECTION が勝つ。

### 実装状態の表記（**重要**）

この文書は**設計**である。実装済みのものと、まだ無いものを混ぜない。
各項目に次を付ける。

| 印 | 意味 |
|---|---|
| ✅ | **実装済み**。ファイルを挙げる |
| 🟨 | **部分的**。何が足りないかを書く |
| ⬜ | **未実装**。設計だけ |
| 🚫 | **今回作らない**（017 §25） |

既存コードとの照合結果は
`docs/reports/FORGE-017-ARCHITECTURE-REVIEW-report.md` にある。
**この文書の✅は、そのReviewで実際にファイルを読んで確認したものだけ**
である。

---

## 1. 目的

Forge / Forge製アプリ / その他のForge AI SDK対応アプリ から共通利用
できる、

> **Local Firstで推論し、利用から安全なLearning Signalを得て、
> Global / App / Personal の3層を継続的に改善するAI基盤**

を作る。

### 絶対原則

```
Local First
Privacy First
Learning by Use
Global / App / Personal separation
Provider Independent
Never Train Blindly
Evaluation Before Release
Maintainability First
```

そして Forge の中心命題:

> **AIは意味を決める。Forgeは品質を保証する。**
>
> Cloud output は Teacher Candidate であって Truth ではない。
> Validator / Runtime / User Acceptance / Benchmark 等の Evidence が
> Truth を補強する。

---

## 2. Local First の定義

**Local Only とは定義しない。** 正確には Local First である。

```
Task
 ↓
Local AI が
   ・Capability対応済み
   ・Benchmark基準達成
   ・Latency / Resource 範囲内
 ↓ Yes            ↓ No（または利用者が許可した場合）
Local              Cloud fallback
                     ↓
                   成功結果は Teacher Candidate
                     ↓
                   Local能力改善へ
```

最終目標は、**Cloud fallbackが必要なTask領域を継続的にLocalへ移管する**
こと。Cloudを禁止しないが、Cloud依存にもしない。

### 実装状態

| 要素 | 状態 |
|---|---|
| Provider抽象と `Deployment(LOCAL\|CLOUD)` | ✅ `backend/app/ai/gateway/provider_registry.py` |
| Task別Routing / fallback / Circuit Breaker | ✅ `backend/app/ai/gateway/ai_router.py` |
| Benchmark基準による順位付け（件数・鮮度・dataset同一性・schema成功率のGate） | ✅ `benchmark_evidence.py: ranking_for() / is_usable_for_routing()` |
| **Local Promotion Gate** | ✅ `local_promotion.py`。`AIRouter._order()`から実際に呼ばれる |
| Capability対応判定 | 🟨 `TaskProfile`はあるがLocal能力判定は無い |

### Best Score Wins をやめた（FORGE-017A §7）

当初この文書は「Local優先は`ranking_for()`が同点のときだけ」と書いて
いた。**これは誤りだった**——同点のときだけ効く優先は実質Local First
ではない。Cloudが1点でも高ければ毎回Cloudが選ばれ、Localは永久に
使われない。

かといって「Localだから先」に戻すと、`AIRouter._order()`が実装した上で
退けた失敗（「測っていない品質を賭けてQuotaを節約する」）へ戻る。

**Quality Gate にした。**

```
❌ Best Score Wins
     Local 0.91 vs Cloud 0.93 → 毎回Cloud

✅ Local Meets Product Bar → Local First
     Localが製品として通用する水準を満たすなら、Cloudが上でもLocal
```

`LocalPromotionGate`が実測から判定する。**全条件を満たさなければ通さ
ない**（capability / benchmark実測 / 品質水準 / schema成功率 /
latency / 件数 / 鮮度 / dataset同一性）。1つでも欠けたら通さないのは、
「だいたい満たしている」で通すと何が理由で通ったのか分からなくなる
からである。

> **いま昇格するProviderは0件である。** Localのbenchmark記録が1件も
> 無い（実測）。この配線は**今は何も変えない**——データが入れば効き
> 始める。配線済み・データ待ちの状態にしてある。

---

## 3. Intelligence Layer（4層）

```
Base Model
  + Forge Global Intelligence
  + App Intelligence
  + Personal Intelligence
```

**Global LoRA + App LoRA + Personal LoRA を常に3枚stackする仕様には
しない。** 各層は必要に応じて次のどれかで実現する。

```
Prompt / Policy ・ Knowledge / RAG ・ Memory
Adapter / LoRA ・ Tool ・ Runtime setting
```

Taskごとに最適な組合せを **Intelligence Resolver** が解決する。

### Intelligence Resolver

✅ `IntelligenceContextResolver`（`backend/app/ai/gateway/intelligence_context.py`）。

**`AIRouter`へ詰め込まなかった**（FORGE-017A §8）。「parallel routerを
作らない」は維持しつつ、責務は分ける。

```
IntelligenceContextResolver   ← 何を知っているかを決める
        ↓ resolved context
AIRouter                      ← どのProviderへ投げるかを決める
        ↓
Provider
```

理由は2つ。

1. **`AIRouter`が神クラスになる。** すでにRouting・Circuit Breaker・
   Quota・Latency予算・Experience記録・Local昇格を持っている
   （Maintainability First）
2. **順番が逆になる。** 知識はProvider選択の**前**に決まっていなければ
   ならない。CloudとLocalで渡す知識が変わると「同じ問いに同じ知識で
   答えた」という比較ができず、Benchmarkの前提が崩れる

Resolverは**Provider rankingをしない**（`rank`/`order`/`bind`等が
生えていないことをテストで固定した）。

🟨 いま解決するのは Design Language の知識のみ。Memory / Policy /
Adapter / Tool は未実装。

### 実装状態

| 層 | 状態 |
|---|---|
| Provider / Model 抽象 | ✅ `provider_registry.py` |
| **Local Base Model 統合** | 🟨 Registryに`Deployment.LOCAL`の定義はあるが、統合は未完 |
| **実Local Modelでの生成** | ⬜ **0回。未検証** |
| Forge Global Intelligence | ✅ `knowledge.py` + `intelligence_context.py`。**本番から呼ばれ、Evidenceへ`design_role.metric.primary@v1`の形で残る**（TD69解消） |
| App Intelligence | 🟨 `KnowledgeEntry.app_id` と scope 境界は実装済み。**App固有の知識は0件**、`app_id`を解決する経路も無い |
| Personal Intelligence | 🟨 scopeとして分離済み（Personalは他scopeの検索に現れない）。**Memory / Personal RAG は未実装** |

> **「Base Model = ✅」と書いていたのは過大評価だった**（FORGE-017A §9）。
> Provider抽象があることと、Local Modelで実際に生成できることは別で
> ある。**実Local Modelでの生成は0回**であり、進捗を盛らない。

---

## 4. 優先順位 / Conflict Resolution

```
Safety / Forge Policy
   ↓
App Policy
   ↓
Explicit User Preference
   ↓
Personal Intelligence
   ↓
Forge Global Intelligence
   ↓
Base Model
```

**Personal Intelligence が Safety / App mandatory policy を上書きして
はならない。**

⬜ 未実装（層自体が無いため）。ただし
`AIRouter` の `Sensitivity` / `TaskProfile` は Safety 側の足場として
既にある（✅）。

---

## 5. Learning Event 共通Contract

### 既存Evidenceを捨てない

Forgeには既に**4つの事実の記録**がある。Learning Event はこれらの
**上位契約**であって、置き換えではない。

```
ExperienceRecord … 1回のAI呼び出しの事実          ✅ learning_foundation.py
GenerationRecord … 1つの生成物の事実              ✅ generation_evidence.py
RevisionRecord   … 1回の変更の事実                ✅ revision_evidence.py（016A commit B）
BenchmarkRun     … 1回の測定の事実                ✅ benchmark_evidence.py
```

Learning Event はこれらから**変換して作る**。変換層は1つだけにする。

### 語彙・Local Event・安全境界は実装済み

| | 状態 |
|---|---|
| `LearningEventType`（構想どおりの広さ・`is_emitted_today`付き） | ✅ `learning_contract.py` |
| `LearningTaskId`（namespaced・自由文禁止・全ForgeTaskをmapping） | ✅ 同上 |
| `IntelligenceScope` / `DataResidency` / `ContributionTarget` | ✅ 同上 |
| **`LearningEvent`本体と単一Projector** | ✅ `learning_events.py` |
| **Cloud収集権限とTraining権限の分離** | ✅ FORGE-018A |
| **Cloud Network送信 / durable outbox** | ⬜ 未実装 |

> **Event種類をEvidence Storeの型に固定しない**（FORGE-017A §5）。
> `build` / `compile` / `test` / `runtime` / `crash` / `tool_result` は
> **まだemitしないが、構想から消さない**。「未実装」と「作らないことに
> した」は違う。テストが「構想にあった種類が消えていないこと」を見張る。
>
> **`task_type`を`ForgeTask`だけに固定しない**（§6）。`ForgeTask`はAI
> Routingの語彙で4値しかない。`flutter.build`はAIを呼ばないので
> `ForgeTask`になりようがないが、Learning Eventとしては事実である。

### フィールド（⬜ `LearningEvent`本体は未実装。契約のみ）

```
schema_version
event_id
event_type
task_type                     ← 既存 ForgeTask をそのまま使う

scope: global | app | personal
app_id

pseudonymous_install_id       ← §6・Review §4-1 の判断が要る

provider_id / deployment      ← 既存 ProviderDefinition
base_model_id / base_model_version
adapter_id / adapter_version

forge_ai_version
forge_language_version        ← 既存 GenerationRecord が持つ
knowledge_version
prompt_policy_version

capability_ids                ← 既存 GenerationRecord.capabilities
design_role_ids               ← 既存 design_language_roles

accepted                      ← 既存 AcceptanceSignal
retry_count                   ← 既存名 repair_attempts に寄せる

validator_result / runtime_result / build_result / test_result
latency_ms / token_usage

consent_snapshot_id
privacy_policy_version
sanitizer_version

training_use: allowed | forbidden | unknown
provenance

artifact_ref                  ← 既存 ArtifactIdentity.artifact_id（B）

created_at
```

> **名前を新しく作らない。** `retry_count`ではなく既存の
> `repair_attempts`、`validator_result`ではなく`validator_passed`へ
> 寄せる。Forgeの`repair`は「Validator不合格→修復」という具体的な意味を
> 持ち、`retry`より情報量が多い（Review §3）。

---

## 6. 識別子 — `anonymous` と呼ばない

継続的に同一人物/端末へ紐付け可能なら、**厳密な anonymous ではない。**
`pseudonymous_install_id` 等の名称にする。

**「名前を消したから匿名」とは扱わない。**

### ✅ 決着（FORGE-017A §11、2026-08-24）

**二層化を正式採用した。** OPEN-DECISIONS 判断項目 F はこれで閉じる。

```
Local Evidence（既存3 Record）    cross-session identityを持たない。いまのまま
        ↓ Consentを通ったEventだけ
Cloud Learning Event             pseudonymous contributor identity を持つ
```

**ただし、client-generated install ID だけを Poisoning 防止の Truth に
しない。** 端末側で生成したIDは端末側で作り直せるので、それだけを
「1人あたりの投稿数」の根拠にすると、作り直すだけで制限を外せる。

将来は **server-issued contributor token** または
**authenticated pseudonymous subject** を使う。rotation / revocation /
deletion に対応する。

> **`pseudonymous ID` を持っただけで Sybil 対策が済んだとは言わない**
> （017A §18-10）。IDは「数えられるようにする」だけで、
> 「作り直せない」ことは保証しない。

⬜ いずれも未実装（commit E）。ここにあるのは決定と、決定の理由である。

---

### 判断の経緯（既存の約束との衝突）

既存コードには明文がある（`learning_foundation.py`、
`ExperienceRecord.ref` のdocstring）:

> セッションIDでも利用者IDでもない、**Store内の位置**である
> （§22「セッションを跨いで個人を辿れる識別子を持たない」）。

`GenerationRecord` / `RevisionRecord` も同じ姿勢で作ってある。017 §5 が
`pseudonymous_install_id` を必須にすることは、**方針の転換**である。

#### 推奨する形（二層化）

```
Local Evidence（既存3 Record）    識別子を持たない。いまのまま
        ↓ Consent + Sanitize を通ったときだけ
Learning Event（Cloudへ出るもの）  pseudonymous_install_id を持つ
```

Consentを出していない利用者のローカル記録は**性質が変わらない**。
辿れる識別子は「外へ出すと決めたものにだけ付く」。§9「OFFでも基本
Forge / Local AI / Personal Memory が使えること」と整合する。

**→ `docs/OPEN-DECISIONS.md` の判断項目 F。**

### 併せて設計するもの（⬜ 未実装）

rotation / deletion / retention / unlinking / アカウント削除時の処理。

---

## 7. Learning Artifact

**Raw conversation をデフォルトでCloudへ送らない。** ⬜ 未実装。

Artifact upload は次を全て満たした場合のみ:

```
explicit consent  +  local sanitization  +  training_use確認
```

Artifactが持つもの:

```
artifact_type / sanitizer_version / provenance
content_hash（後述）/ training_use / quality_state
```

### 🟡 指紋についての注意（Reviewの発見）

016A commit Bで実装した `document_fingerprint()` は **salt無しのsha256**
である。現時点ではプロセス内の世代照合にしか使っておらず、Cloudへ出ない
ので実害は無い。

しかし **Learning Event に載せると、同じDocumentを作った別々の利用者が
同じ値を持つ**——横断で突き合わせられる識別子になる。017 §7 が
「全ユーザー共通で単純hashする設計は避ける」と言っているのは、まさに
この形である。

**Learning Eventへ載せる指紋は、event-scoped な salt / HMAC を通した
別関数にする。** `document_fingerprint()` は「ローカル世代照合専用」と
して残す。

---

## 8. Privacy Pipeline

```
端末側:
Raw → Secret Detection → PII Detection → Policy Filtering
    → Data Minimization → Sanitization → Learning Event → Cloud

Cloud側（再度）:
Schema Validation → Secret Scan → PII Scan
```

**Client sanitization だけを信用しない。**

### いまある強い保証（✅）

Forgeの既存Evidence型は、**本文を型として持てない**。

* `ExperienceRecord` … 自由文字列欄が無い
* `GenerationRecord` … 識別子と検証結果だけ
* `RevisionRecord` … `utterance`/`message`/`text`等のフィールドが**存在しない**
  （`backend/tests/test_artifact_feedback.py` が名前の混入を見張る）

これは「入れない運用」ではなく**型の制約**であり、Data Minimization の
一部が既に効いていることを意味する。

### 無いもの（⬜）

Learning Event 経路の Secret Detection / PII Detection / Sanitizer。
生成物向けの `OutputSafetyChecker`（✅）と入力向けの
`scan_for_injection()`（✅）はあるが、**用途が違う**ので流用しない。

---

## 9. Consent

⬜ **module自体が存在しない。**

最低限、次を分離した設定にする。

```
匿名/仮名利用統計 ・ AI回答評価 ・ 修正Semantic Event
Sanitized Artifact ・ Code Diff ・ Crash/Runtime telemetry
```

**OFFでも、基本Forge / Local AI / Personal Memory・RAG が使えること。**
Consent Snapshot を Event に紐付ける。

---

## 10. Data Deletion / Retention

⬜ 未実装。設計として最低限決めること。

* Learning Event / Artifact / Dataset Candidate / Rejected sample の retention
* 利用者が Learning 提供を撤回した場合の**将来送信停止**
* 削除要求時の Event / Artifact / Dataset Candidate の扱い

### 曖昧にしないこと

> **既にTraining済みのWeightについて、完全なUnlearningを保証できるとは
> 言わない。**

保証できないなら「できない」と書く。代わりに **Dataset lineage を残す**
ことで、「どのDatasetがどのAdapterへ入ったか」を後から辿れるようにする。

---

## 11. Dataset Lineage

⬜ 未実装（`dataset_hash` ✅ は既にあるが lineage ではない）。

Training Dataset は必ず次を追跡可能にする。

```
dataset_version / source_event_ids / source_artifact_ids
sanitizer_version / filter_version / quality_rule_version / created_at
```

**Current Adapter が、どのDataset / どのBase Model / どのTraining Config
から作られたか再現可能にする。**

---

## 12. Training Provenance / Terms

Dataset Candidate は `source/provider` / `model` / `terms_reviewed` /
`training_use` を持つ。

> **UNKNOWN は Weight Training へ入れない。**
> **Cloud Provider output を無条件で学習データにしない。**

### いまある実装（✅）

`TrainingProvenance` と `ModelProvenance.may_be_used_where_provenance_matters`
が既に「`UNKNOWN`を通さない」を実装している
（`learning_foundation.py`）。docstring に

> `UNKNOWN`は**通さない**。「分からないなら止める」であって、
> 「分からないなら大丈夫」ではない。

とある。017 §12 はこの姿勢の一般化である。

`TrainingProvenance`（**Modelがどう育ったか**）と `training_use`
（**そのデータを学習に使ってよいか**）は**別物**なので、統合しない。

---

## 13. Global Learning Pipeline

⬜ 未実装（🚫 §25 で今回作らない部分を含む）。

```
Learning Events
 → Schema Validation → Consent Validation → Secret/PII re-scan
 → Dedup → Spam detection → Poisoning detection
 → Trust / Quality scoring
 → Dataset Candidate
 → Automatic Eval → optional Human Review
 → Versioned Dataset
 → Training                        🚫 §25
 → Candidate Adapter               🚫 §25
 → Forge Eval → Regression → Release Gate
 → Signed Release                  🚫 §25
```

---

### `unguessable != authorized`（FORGE-017A §13）

`ArtifactHandle.handle` は推測できないが、**Bearer Token である**。
持っている人が評価を書ける。

現時点はLocal APIなので大規模なAuthは要らない。しかし
**「opaque IDだから認可済み」とは書かない**。Cloud / 複数利用者へ
広げる際は、次と必ず結びつける。

```
artifact ownership   その生成物は誰のものか
app boundary         どのAppの文脈か
subject boundary     誰が評価しているのか
```

⬜ 未実装（現時点で必要ない）。**契約として先に書いておく**のは、
後から「今までopaqueで足りていた」を根拠に省略されないためである。

---

## 14. Poisoning対策

⬜ 未実装。**単純多数決にしない。**

```
per-user contribution limits
duplicate suppression
suspicious cluster detection
validator / runtime evidence weighting
accepted だけを絶対Truthにしない
malicious correction detection
holdout evaluation
```

**1ユーザーが大量Eventを送って Global Intelligence を偏らせられないこと。**

> `per-user contribution limits` は §6 の識別子に依存する。§6は
> **二層化で決着した**（Consentを通ったEventにだけ仮名IDを付ける）。
>
> ただし **client-generated install ID だけを Truth にしない**
> ——端末側で作り直せるので、作り直すだけで制限を外せる。
> server-issued contributor token / authenticated pseudonymous subject
> が要る。**IDを持っただけでSybil対策が済んだとは言わない。**

### 既にある姿勢（✅）

`BenchmarkEvidenceStore.ranking_for()` は「Test Doubleで測った数字を
弾く」「dataset_hashが一致するものだけを比べる」を実装している。
**「測っていないもので本番の経路が決まらない」**という考え方は既に
コードに入っている。Poisoning対策はこれの拡張として作る。

---

## 15. Evaluation

Forge Eval を **Task単位**で持つ。

```
Schema / Forge Language / UI Design / Design Revision
Validator Repair / Runtime Repair / Flutter / API
Security / Refactor / Tool use / Regression
```

**Current vs Candidate** で比較する。

> **aggregate score だけで Release しない。**
> Task ごとの重大 Regression を Gate にできるようにする。

### 実装状態

| 要素 | 状態 |
|---|---|
| Task別のBenchmark記録（`ForgeTask`単位） | ✅ `BenchmarkRun.task` |
| 実測/Test Double/未検証 の区別 | ✅ `Verification` |
| Dataset同一性の照合 | ✅ `dataset_hash` |
| 個別Gate（件数・鮮度・schema成功率） | ✅ `unusable_reason()` |
| Current vs Candidate 比較 | ⬜ |
| Task別Regression Gate | ⬜ |

**`BenchmarkEvidenceStore` を拡張する。`ForgeEvalStore` を別に作らない。**

---

## 16. Adapter Release

🚫 今回作らない（§25）。Interface のみ定義する。

```
adapter_version / base_model_compatibility / minimum_runtime_version
hash / signature / release_channel / rollback_target
```

配信は `internal → canary → limited → stable`。
**壊れたAdapterを全端末へ一斉配布しない。**

---

## 17. Personal Intelligence

⬜ 未実装。**原則Local。**

対象: Memory / Personal RAG / Preference / Project rule / Personal Adapter。

* 暗号化・削除可能性を検討する
* **Personal data を Global Learning へ自動投入しない**
* Globalへ提供する場合は**別Consent + Sanitization**を通す

---

## 18. App Intelligence

⬜ 未実装。**`app_id` がコードに1箇所も無い**（grep実測 0件）。

* App-specific knowledge を Global へ無条件混入しない
* **`app_id` を強い境界にする**
* **`app_id` を Client の自己申告で信用しない**（FORGE-017A §12）
* App の RAG / Prompt / Policy / Adapter / Eval を分離可能にする
* **Generic に有用と判定された知識のみ** Global Dataset Candidate へ昇格可能

> **実装順への影響**: Knowledge/RAG（016A commit D）で `KnowledgeEntry`
> を作るなら、**その時点で `scope` と `app_id` を型に含める。**
> 後から全Entryへ遡って付けるのは全面書き換えになる（017 §24
> 「後から全面書き換えにならないこと」）。

---

## 19. Design Revision との統合

現在設計中の

```
User Correction → Semantic Patch → RevisionRecord → ACCEPTED / CORRECTED
```

を、Growing AI Architecture の**最初の高品質 Learning Event source**と
して扱う。

```
before:      surface.card
correction:  complaint=too_flat, delta=emphasis_up
after:       surface.elevated
acceptance:  ACCEPTED
      ↓
Learning Event Candidate
```

**raw utterance は通常Eventへ入れない。**

### 実装状態

| 要素 | 状態 |
|---|---|
| `RevisionRecord` / `DesignRevision` / Store | ✅ 016A commit B |
| ACCEPTED / CORRECTED を受ける口（`POST /api/v1/ai/feedback`） | ✅ 016A commit B |
| `DesignDecisionSource.USER_CORRECTION`（AIの成功例と混ぜない） | ✅ 016A commit B |
| 型として raw utterance を持てないこと | ✅ テストで固定 |
| **評価の時系列**（`ArtifactFeedbackEvent`、追記専用） | ✅ 017A §2 |
| **由来不明/Test Doubleを教師にしない** | ✅ 017A §1 |
| Handle / EvidenceId / VersionToken の分離 | ✅ 017A §3・§4 |
| Semantic Patch（局所適用） | ⬜ commit F |
| `/update` から `RevisionRecord` を書く配線 | ⬜ commit F |
| Learning Event への変換 | ⬜ commit E |

> **正直に**: 口はできたが、**利用者が押せるボタンはまだ無い**
> （Flutter側未実装）。現時点で `user_acceptance` が実データで埋まる
> わけではない。

---

## 19A. Revision Integrity（FORGE-019A、2026-08-25）

Design Revision を「最初の高品質 Learning Event source」として扱う以上、
**その記録が本物であること**が前提になる。019A で3つの前提を固めた。

### 1. 変更は「その生成物への変更」でなければならない

```
artifact capability（handle）  誰が直そうとしているか
version token（世代）          いつの版を見ているか
document binding（中身の身元）  それは本当にその生成物か   ← 019A
```

束縛はプロセス内鍵の HMAC。**Client にも Learning Event にも出さない。**
無ければ通さない（fail closed）。

これが無いと、handle を持っている人が任意のJSONを「Forgeが生成した
ものを直した」ことにできる——**Global Dataset を汚す最短経路**である
（§12 の `app_id` を信用しない、と同じ性質の穴）。

### 2. 変更の入口は1つ

`/update` と `/converse` の UPDATE は同じ `RevisionService` を通る。
019 では会話（本線）だけが旧経路を通り、Evidence を1件も残していな
かった。**二重 Architecture にしない**（§21 と同じ規律）。

全体再生成 fallback も同じ経路を通る。局所patchのふりはしない。

### 3. 「不満を言われた」は「うまく直せた」ではない

```
Generation → CORRECTED → Revision → ACCEPTED      ✅ 正例
Generation → CORRECTED → Revision → （無言）       ❌
Generation → CORRECTED → Revision → CORRECTED     ❌
```

区別せずに正例へ入れると、**下手な直し方ほど教師データに多く残る**
（直せないほど `/update` が呼ばれるため）。Feedback 列を join して
判定し、**記録は書き換えない**——取り下げるのは `DatasetCandidate`
（Forgeの判断）であって Event（事実）ではない。

### 実装状態

| | |
|---|---|
| Document binding | ✅ `artifact_feedback.py` |
| 単一 `RevisionService` | ✅ `app/ai/runtime/revision_service.py` |
| fallback の lineage | ✅ |
| Revision acceptance の join | ✅ `learning_events.py` |
| Visual Evidence を本番出力から生成 | ✅ `scripts/export_revision_visual_fixture.py` |
| **`evaluate_for_export()` の本番呼び出し** | ⬜ **無い。** DatasetCandidate は現状テストからしか生まれない |
| 永続化 / Auth / subject binding | ⬜ プロセス内メモリのまま |

---

## 20. Language Training Dataset は別契約

将来 Local AI へ「もっと浮かせて」→ `surface.elevated` という
**自然言語Mapping**を学習させるには入力文章が要る。

**通常のSemantic Learning Event と分ける。**

`LanguageTrainingCandidate` は次を全て満たしたものだけ:

```
explicit consent ・ de-identification ・ provenance
training_use = allowed ・ terms reviewed
```

> **現時点で自動収集・自動Training は禁止。** ⬜ 未実装（意図的に）。

---

## 21. Forge AI Runtime

Application が `ollama.generate()` / `gemini.generate()` 等を**直接
呼ばない**。

```
Forge AI SDK
  ↓
Forge AI Runtime
  ↓
Task Router          ← ✅ 既存 AIRouter
  ↓
Knowledge            ← ✅ 本番から呼ばれ、Evidenceへ版付きで残る
  ↓
Intelligence Resolver ← ✅ IntelligenceContextResolver（別クラス）
  ↓
Provider Interface   ← ✅ 既存 ProviderDefinition / Adapter
```

**既存 Provider Registry / Router を捨てず拡張する。**

> Forgeは「Provider直呼びの近道」を過去に塞いだ実績がある
> （010 Phase B: `/generate`・`/update` のRouter迂回を閉じ、
> anti-bypass regression テストを置いた）。同じ規律をSDK層でも保つ。

---

## 22. Learning SDK

🚫 今回作らない（§25）。Contract のみ定義する。

将来 Forge / Forge-generated App / External App が共通 Learning Event
Contract を使う。ただし

> **SDK利用アプリが任意Eventを Global Training へ直接流せる構造は禁止。**

Learning Cloud 側で schema / consent / provenance / quality / trust を
**必ず検証する**。

### `app_id` は検証対象である（FORGE-017A §12）

Event payload の中の `app_id` を**そのまま信用しない**。信用すると、
External App が

```
app_id = "forge"
```

と名乗って Global Dataset を汚せる。将来は
**registered app identity / SDK credential / server-side mapping**
から解決する。

### Trust Tier（設計候補）

```
forge_core          Forge自身
forge_generated     Forgeが作ったApp
registered_external 登録済みの外部App
untrusted           それ以外
```

Tierによって、Global Dataset へ寄与できるかどうかを変える。

---

## 23. Supabase 初期構成

初期は Supabase を利用してよい。

```
learning_events ・ learning_artifacts ・ datasets ・ dataset_members
model_versions ・ adapter_releases ・ eval_runs ・ consent_snapshots
```

### 実装状態

Supabase 接続そのものは ✅ 存在する（`app/repositories/supabase_*.py`、
`app/core/di.py`）。ただし **workspace / folder 用のみで、AI/Learning の
テーブルは1つも無い。**

**現在段階で Stage 3 インフラを作らない**（§23）。

---

## 24. 現行016との関係

既存の 016 / Design Revision 作業を**破棄しない**。順序:

```
A.  MeasureSemantics消失修正             ✅ 50b2c3d
B.  Feedback / Revision Foundation       ✅ fe2664c
A1. Revision training provenance         ✅ b61b36d（017A §1）
A2. Feedback Event + ID分離              ✅ d163e6f（017A §2-§4）
A3. Learning Contract + Local Gate       ✅ 2db1fcd（017A §5-§7, §10）
C.  残R1 Hardening                       ✅ a514a37（017A §14）
D.  R2 Forge Knowledge / RAG             ✅ e40c861（017A §8, §15）
E.  Growing AI Learning Event Foundation ⬜
F.  Semantic Design Revision             ⬜
```

**E の型・境界は B〜D を実装するときから意識する。後から全面書き換えに
ならないこと。**

Review §7 が「C・Dの時点で決めておくべき」とした2件は、**Dで実際に
入れた**。

1. ✅ **`app_id` / `scope` を `KnowledgeEntry` 型に含めた。**
   `IntelligenceScope` / `DataResidency` / `app_id` を持ち、
   scope境界は**構造として**分かれている（Global検索がPersonalを
   返す経路が無い）
2. 🟨 **Consentを見る場所**は`DataResidency`として型に置いた。
   Consent module 自体は E

---

## 25. 今回すぐ実装しないもの

🚫 Cloud Training / LoRA Training / GPU Worker / Model Registry本格版 /
Adapter OTA配信 / Personal LoRA / Global Learning SDK公開

**ただし Interface / Event Contract / Version / Privacy境界は先に定義する。**

---

## 26. 自己監査（017 §28）

| # | 問い | 答え |
|---|---|---|
| 1 | Local Firstか | はい。ただし §2 の「Benchmarkの中でだけ効く」制約付き |
| 2 | Cloudを禁止していないか | していない。fallbackを明示的に許可 |
| 3 | Cloud依存にもなっていないか | Teacher Candidate 止まり。Truthにしない（PRODUCT-DIRECTION §5） |
| 4 | Global/App/Personalが分離されているか | **設計上は。実装は⬜**（`app_id`が0件） |
| 5 | Personal dataがGlobalへ漏れないか | 自動投入を禁止。別Consent + Sanitization（§17）。**未実装** |
| 6 | Learning Eventとraw dataを混同していないか | していない。§5は識別子のみ。§20で別契約に隔離 |
| 7 | ConsentがEvent単位で追跡可能か | `consent_snapshot_id`で設計。**未実装** |
| 8 | Training rightsが確認可能か | `training_use` + `TrainingProvenance`(✅)。UNKNOWNは通さない |
| 9 | Poisoning耐性を考慮しているか | §14。**ただし §6 の識別子判断に依存する**と明記した |
| 10 | Dataset lineageが残るか | §11で設計。**未実装** |
| 11 | Candidateを評価せず配信していないか | §13 Release Gate。**未実装**（🚫 §25） |
| 12 | Rollback可能か | §16 `rollback_target`。🚫 今回作らない |
| 13 | Base/Adapter互換性を管理できるか | §16 `base_model_compatibility`。🚫 今回作らない |
| 14 | Local AI改善へ本当に繋がるか | commit Bで**評価を受ける口が初めて本番に通った**。ただしFlutter側のボタンが無いので、まだ実データは入らない |
| 15 | Generated App Quality改善と分離していないか | **分離していない（意図的）。** PRODUCT-DIRECTION §2「2つの軸を分離しない」に従う |
| 16 | 既存Forge Architectureを重複実装していないか | Review §6 で線引きを明文化した。AIRouter / BenchmarkEvidenceStore / Provider Registry は**拡張**する |
| 17 | 実装都合で最終構想を縮小していないか | 縮小していない。未実装は⬜として残し、「無い」と書いた |

### FORGE-017A の自己監査（§18の14項目）

| # | 問い | 答え |
|---|---|---|
| 1 | RevisionのUNKNOWN/TestDoubleを教師にしていないか | ✅ §1で塞いだ。生成側と同じ4条件 |
| 2 | Feedbackの時間順を捨てていないか | ✅ §2で追記専用にした |
| 3 | Client handleをDataset IDへ流用していないか | ✅ §3で分離。Eventにハンドルが現れないことをテストで固定 |
| 4 | ephemeral IDをCloud lineageへ使っていないか | ✅ `uid`（記録に貼り付く永続ID）を使う |
| 5 | Local Firstが実際にLocal Firstか | ✅ Quality Gateにした。ただし**昇格0件**（実測が無い） |
| 6 | 未測定Localを楽観的に優先していないか | ✅ 未測定・Test Doubleは通さない |
| 7 | AIRouterを神クラス化していないか | ✅ Resolverを別クラスにした |
| 8 | PersonalとCloud eligibilityを混ぜていないか | ✅ 2軸に分けた |
| 9 | app_idをClient自己申告で信用しているか | ⬜ **まだ解決経路が無い**。契約として§22に書いた |
| 10 | pseudonymous IDだけでSybil対策完了と言っていないか | ✅ 言っていない（§14に明記） |
| 11 | ForgeTaskで外部Learning Taskを表現していないか | ✅ `LearningTaskId`を分けた |
| 12 | 元の構想からEvent種類を削っていないか | ✅ 構想どおりの広さ。テストが見張る |
| 13 | Local AI実モデル0回を「Base Model実装済み」と呼んでいないか | ✅ §3で訂正した |
| 14 | Generated App QualityとLearning Loopを両方進めているか | ✅ Cで品質（Critic誤検知2件）、A/Dで学習側 |

### 監査で正直に書くこと

* **§5 の Local First は「実際にLocal Firstか」に✅を付けたが、
  昇格するProviderは0件である。** 規則は正しくなったが、動いている
  ものは何も無い。「配線済み・データ待ち」であって「効いている」では
  ない
* **§9 が未解決である。** `app_id`をClientから受ける経路がまだ無いので
  「信用していない」とも言えない（受けていないだけ）。SDKを公開する
  前に必ず要る
* **Flutter側の👍ボタンが無い。** Backendの口は揃ったが、
  `user_acceptance`が実データで埋まるわけではない。「実装した」と
  「使われている」を混同しない（PRODUCT-DIRECTION §7）

---

## 27. FORGE-018実装状態（2026-08-25）

`LearningEventProjector` / `LearningEventService`をProductionへ接続した。
既存Evidenceは置換せず、全Storeの記録直後が単一変換入口を通る。

実装済み: AI_CALL / GENERATION / FEEDBACK、Local Event、6カテゴリConsent
（既定OFF）、Learning Sanitizer、中央Eligibility、Retention Policy、
Cloud Envelope境界、Dataset Candidate lineage、Learning Artifact契約。

安全上未実装: Supabase送信、durable outbox、Auth/RLS、Production
server-issued contributor identity、Object Storage。ProductionのCloud送信は
0件・fail closed。Test DoubleでEnvelope構築までのみ実証した。

## 28. FORGE-018A Learning Boundary Hardening（2026-08-25）

独立Reviewで、Collection RightsとTraining Rightsの混同、Model用
`TrainingProvenance`のEvent流用、process-global Consent/Context、全Eventを
Rejected Dataset Candidateと呼ぶ曖昧さを再現した。

Local projectionとsubject-scoped export phaseを分離し、`CloudExportPolicy`と
`TrainingEligibilityPolicy`を独立させた。Event由来は閉じた
`LearningDataProvenance`、Provider deploymentはRegistryをSource of Truthと
する。Curated/Test DoubleはLocal AI実績へ数えない。

Consentはimmutable snapshot履歴となり、Event Type別の中央routingを通る。
撤回は新snapshotを追記し、旧snapshotの将来利用を拒否、未送信Outboxを削除、
未学習Dataset CandidateをREVOKED化する。RetentionはLocal Event、Export
Decision/Evaluation、Outbox、Dataset Candidate、Learning Artifactへ適用する。

Evidence Storeからの観測はProduction配線を維持しつつ、Projector障害を
診断counterへ記録して利用者の成功処理を壊さない。Cloud Network送信、
durable storage、既学習weightのunlearningは引き続き未実装である。
