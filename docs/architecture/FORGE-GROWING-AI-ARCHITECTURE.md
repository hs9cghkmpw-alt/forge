# Forge Growing AI Architecture

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
| **Benchmark合格Localを同点時に優先する規則** | ⬜ 未実装 |
| Capability対応判定 | 🟨 `TaskProfile`はあるがLocal能力判定は無い |

> **注意（Reviewの発見）**: `AIRouter._order()` は過去に「Local優先」を
> **実装した上で退けた**記録を持つ——「Benchmarkが無いのにLocalを優先
> するのは、測っていない品質を賭けてQuotaを節約しているだけ」。
> したがって Local First は、**`ranking_for()`が順位を返せたときの
> 同点処理としてのみ**入れる。順位が無いときは従来どおり宣言順にする。
> この制約を外すと、過去に一度退けた失敗へ戻る。

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

⬜ 未実装。

**`AIRouter`を拡張して実装する。並列の routing 実装を作らない**
（Review §6）。Forgeは「基盤はあるのに本番では別経路が使われる」を
繰り返しているので、routingの入口は1つに保つ。

### 実装状態

| 層 | 状態 |
|---|---|
| Base Model | ✅ Provider Registry 経由 |
| Forge Global Intelligence | 🟨 語彙は存在する（`design_language.knowledge_entries()` 33 role）が**本番から参照されていない（TD69）**。RAG無し |
| App Intelligence | ⬜ **`app_id`がコードに1箇所も存在しない**（grep実測 0件） |
| Personal Intelligence | ⬜ 未実装 |

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

### フィールド（⬜ 未実装。契約のみ定義）

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

### 🔴 既存の約束との衝突（CEO判断が要る）

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

> `per-user contribution limits` は §6 の識別子の判断に依存する。
> 辿れる識別子が無ければ、この対策は原理的に効かない。**§6とセットで
> 決める必要がある。**

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
| Semantic Patch（局所適用） | ⬜ commit F |
| `/update` から `RevisionRecord` を書く配線 | ⬜ commit F |
| Learning Event への変換 | ⬜ commit E |

> **正直に**: 口はできたが、**利用者が押せるボタンはまだ無い**
> （Flutter側未実装）。現時点で `user_acceptance` が実データで埋まる
> わけではない。

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
Knowledge            ← 🟨 語彙はあるが本番未接続（TD69）
  ↓
Intelligence Resolver ← ⬜ AIRouterを拡張して実装
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
A. MeasureSemantics消失修正            ✅ commit 50b2c3d
B. Feedback / Revision Foundation      ✅ commit fe2664c
C. 残R1 Hardening                      ⬜
D. R2 Forge Knowledge / RAG            ⬜
E. Growing AI Learning Event Foundation ⬜
F. Semantic Design Revision            ⬜
```

**E の型・境界は B〜D を実装するときから意識する。後から全面書き換えに
ならないこと。**

具体的に、C・Dの時点で決めておくべきもの（Review §7）:

1. **`app_id` / `scope` を D の `KnowledgeEntry` 型に含める**
2. **Consentを見る場所だけ D で決める**（実装は E）

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

### 監査で正直に書くこと

* **§4 の答えが「設計上は」である**のは弱い。`app_id` が1箇所も無い
  状態で「分離されている」とは言えない。**Dで型に入れる**ことを
  §24 に具体的な約束として書いた
* **§14 が commit B で前進したが、まだ閉じていない。** 口はあるが
  押すボタンが無い。「実装した」と「使われている」を混同しない
  （PRODUCT-DIRECTION §7）
