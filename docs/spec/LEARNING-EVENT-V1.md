# Learning Event V1（語彙は実装済み・Event本体は未実装）

2026-08-24 / 017 §5、**FORGE-017A §5・§6・§10で改訂**

> **語彙（`LearningEventType` / `LearningTaskId` / `IntelligenceScope` /
> `DataResidency` / `ContributionTarget`）は実装済み**
> （`backend/app/ai/gateway/learning_contract.py`）。
> **`LearningEvent`本体を組み立てて送る経路は未実装**（commit E）。
> `docs/architecture/FORGE-GROWING-AI-ARCHITECTURE.md` が上位。
> 実装状況はそちらの✅/🟨/⬜表記を見ること。

---

## 1. なぜ「上位契約」なのか

Forgeには既に**4つの事実の記録**がある。Learning Event はこれらを
**置き換えない**。変換して作る。

```
ExperienceRecord … 1回のAI呼び出し    ✅ backend/app/ai/gateway/learning_foundation.py
GenerationRecord … 1つの生成物        ✅ backend/app/ai/gateway/generation_evidence.py
RevisionRecord   … 1回の変更          ✅ backend/app/ai/gateway/revision_evidence.py
BenchmarkRun     … 1回の測定          ✅ backend/app/ai/gateway/benchmark_evidence.py
```

置き換えない理由は2つある。

1. **粒度が違う。** 1つの生成物に対してAI呼び出しは0〜N回ある
   （Curated Domainは生成stageでAIを1回も呼ばない）。1つの型へ潰すと、
   どちらかの母数が壊れる
2. **意味が違う。** `validator_passed` は生成では「作れたか」、変更では
   「壊さなかったか」である。013で `/update` を `GenerationRecord` から
   除外した理由がこれで、B でも `RevisionRecord` を別型にした

---

## 2. フィールド

### 2.1 識別と版

| field | 型 | 由来 | 備考 |
|---|---|---|---|
| `schema_version` | str | ⬜ 新規 | このEvent契約の版 |
| `event_id` | str | ⬜ 新規 | 不透明。連番にしない |
| `event_type` | enum | ✅ `LearningEventType` | **Evidence Storeの型に固定しない**（下記） |
| `task_type` | `LearningTaskId` | ✅ | `ForgeTask`は**AI Routingの語彙**なので別に持ち、mappingする（下記） |
| `created_at` | float | ✅ `recorded_at` | |

### 2.2 境界（**Dで型に入れる**）

| field | 型 | 由来 | 備考 |
|---|---|---|---|
| `scope` | enum | ⬜ 新規 | `global` / `app` / `personal` |
| `app_id` | str \| None | ⬜ 新規 | **コードに1箇所も無い**（grep実測0件）。App Intelligenceの境界の起点 |

> **後から付けられない。** Knowledge/RAG（commit D）で `KnowledgeEntry`
> を作る時点で `scope` と `app_id` を持たせる。後から全Entryへ遡ると
> 全面書き換えになる（017 §24）。

### 2.3 識別子（🔴 判断待ち）

| field | 型 | 状態 |
|---|---|---|
| `pseudonymous_contributor_id` | str \| None | ⬜ **二層化を採用**（017A §11、判断F決着） |

```
Local Evidence（既存3 Record）  cross-session identityを持たない。いまのまま
        ↓ Consentを通ったEventだけ
Cloud Learning Event           pseudonymous contributor identity を持つ
```

Consentを出していない利用者のローカル記録は**性質が変わらない**
（017 §9「OFFでも基本Forge / Local AI / Personal Memory が使えること」）。

> **client-generated install ID だけを Poisoning 防止の Truth にしない**
> （017A §11）。端末側で作り直せるので、作り直すだけで制限を外せる。
> 将来は **server-issued contributor token** または
> **authenticated pseudonymous subject** を使い、
> rotation / revocation / deletion に対応する。
>
> **IDを持っただけでSybil対策が済んだとは言わない。**

### 2.4 モデルとProvider

| field | 由来 |
|---|---|
| `provider_id` | ✅ `ExperienceRecord.provider` |
| `deployment` | ✅ `ProviderDefinition.deployment`（`local` / `cloud`） |
| `base_model_id` / `base_model_version` | 🟨 `ExperienceRecord.model` はあるが version は無い |
| `adapter_id` / `adapter_version` | ⬜ Adapterが存在しない |

### 2.5 Forgeの版

| field | 由来 |
|---|---|
| `forge_language_version` | ✅ `GenerationRecord.forge_language_version` |
| `forge_ai_version` | ⬜ |
| `knowledge_version` | ⬜ |
| `prompt_policy_version` | ⬜ |

### 2.6 内容（**識別子だけ**）

| field | 由来 |
|---|---|
| `capability_ids` | ✅ `GenerationRecord.capabilities` |
| `design_role_ids` | ✅ `design_language_roles` / `DesignRoleDecision` |
| `artifact_ref` | ✅ **`ArtifactEvidenceId`**（`kind` + `uid`） |
| `knowledge_references` | ✅ `GenerationRecord.knowledge_references`（`design_role.metric.primary@v1`） |

> **`ArtifactHandle.handle`を`artifact_ref`にしてはいけない**
> （FORGE-017A §3）。あれは失効するBearer Capabilityであり、系譜のID
> ではない。Cloudへ載せると、記録を見た人が誰でも評価を書き換えられる。

> **ここに本文は入らない。** 利用者の発話も、生成されたDocumentの本文も、
> Providerの生出力も、この契約では表現できない。既存3 Record と同じ
> Privacy境界（006 §22）を上位契約でも保つ。

### 2.7 結果

| field | 由来 | 備考 |
|---|---|---|
| `accepted` | ✅ `AcceptanceSignal` | `accepted`/`corrected`/`abandoned`/`unknown` |
| `repair_attempts` | ✅ 既存名 | 017は`retry_count`だが**既存名に寄せる**。Forgeの`repair`は「Validator不合格→修復」で情報量が多い |
| `feedback_events` | ✅ `ArtifactFeedbackEvent`（追記専用） | **時系列そのものがEvidence**。1つのfieldに潰さない（017A §2） |
| `validator_result` | ✅ `validator_passed` (bool) | |
| `runtime_result` | ✅ `RuntimeOutcome` | `rendered`/`failed`/`unknown` |
| `build_result` / `test_result` | ⬜ | |
| `latency_ms` | ✅ | |
| `token_usage` | ⬜ | |

### 2.8 Consent と利用可否

| field | 状態 |
|---|---|
| `consent_snapshot_id` | ⬜ Consent module自体が無い |
| `privacy_policy_version` | ⬜ |
| `sanitizer_version` | ⬜ |
| `training_use` | ⬜ `allowed` / `forbidden` / `unknown` |
| `provenance` | 🟨 `TrainingProvenance`(✅) と**隣接するが別物** |

> `TrainingProvenance` は**Modelがどう育ったか**、`training_use` は
> **そのデータを学習に使ってよいか**。統合しない。

---

## 3. 既定値の向き

**分からないものを楽観側へ倒さない**（`CLAUDE.md` §3）。

| field | 既定 | 楽観側へ倒すと何が起きるか |
|---|---|---|
| `accepted` | `unknown` | 沈黙が「承認」になり、教師データが捏造される |
| `training_use` | `unknown` | 使ってはいけないデータがTrainingへ入る |
| `provenance` | `unknown` | 出所不明のModelが「検証済み」になる |
| `runtime_result` | `unknown` | 「確かめていない」が「落ちなかった」になる |
| `scope` | **既定を作らない（必須）** | Personal がGlobalへ混ざる |

`unknown` は **Weight Training へ入れない**（017 §12、既存
`ModelProvenance.may_be_used_where_provenance_matters` と同じ規則）。

---

## 4. 変換層は1つだけ

```
ExperienceRecord ─┐
GenerationRecord ─┼→ [変換層 1つ] → LearningEvent → (Consent/Sanitize) → Cloud
RevisionRecord   ─┤
BenchmarkRun     ─┘
```

**入口を複数作らない。** 016A commit B で `ArtifactFeedbackService` を
「評価を書く唯一のService」にしたのと同じ理由である——入口が増えるたびに
記録の意味が経路ごとにずれ、集計が静かに嘘になる。

---

## 5. まだ書けないもの

* Event の永続化先（Supabase `learning_events`）のschema
  → §23。**現在段階でStage 3インフラを作らない**
* Sanitizer の具体的な検出規則
  → Consent と一緒に決める（commit E）
* `event-scoped fingerprint` の算法
  → salt/HMACのkey管理を決めてから。`document_fingerprint()`（salt無し）
    を**そのまま流用しない**（Architecture §7）。
    なお017A §4で、**Clientへ返す世代tokenは内容と無関係なランダム値**
    へ変えた（`new_version_token()`）。内容ハッシュはもう外へ出ない
* `pseudonymous_contributor_id` の発行主体
  → server-issued token を採る方針だけ決まっている（017A §11）

---

## 6. Production実装（FORGE-018、2026-08-25）

`backend/app/ai/gateway/learning_events.py`がこの契約のProduction型である。
AI_CALL / GENERATION / FEEDBACKを既存Evidenceから単一Projectorでemitする。
REVISIONはProjector対応のみでHTTP Production配線はFORGE-019。

Consent/Sanitizer/Eligibility/Retention/Dataset Candidate/Cloud Envelope境界を
実装した。既定はPersonal + Local-only + contribution none + training unknown +
Consent全OFF。raw本文fieldとClient handle/version tokenは型に存在しない。

Cloud EnvelopeはLocal Eventと別型で、trusted server-issued identityが無ければ
作られない。Production identity providerとSupabase送信は未実装なので、
現時点のCloud送信は0件である。
