# FORGE-017 Architecture Review — Growing AI Architecture vs 既存コード

2026-08-24 / 指示書 FORGE-GROWING-AI-ARCHITECTURE-017 §27

> §27:「正式化前に既存コードと照合し、既にあるもの / 部分的にあるもの /
> 無いもの / 名前が違うだけで同じもの / 今回案と衝突するもの を一覧化する。
> **新しい巨大parallel architectureを作らない。**」

このReviewは**実コードを読んで書いた**。推測で「あるはず」「無いはず」と
書いていない箇所は、ファイルと行を挙げている。

---

## 0. 結論を先に

**017の要素の約4割は、既に別の名前で実装済みである。**

Growing AI Architectureを新しい階層として**上に積むのではなく**、
既存の `Provider Registry` / `AI Router` / 3つのEvidence Store /
`Benchmark Evidence` を**Growing AIの構成部品として名付け直す**のが
正しい。名前を揃えるだけで、017の Provider Interface / Task Router /
Evaluation / Provenance はほぼ埋まる。

**本当に無いのは5つ**である。

1. Learning Event共通Contract（scopeを持つもの）
2. Global / App / Personal の**境界そのもの**（`app_id`がコードに1箇所も無い）
3. Consent（module自体が存在しない）
4. Retention / Deletion / Dataset Lineage
5. Intelligence Resolver

そして**衝突が3件**ある（§4）。うち1件は「黙って進めてはいけない」種類の
ものである。

---

## 1. 既にあるもの（新規実装不要。名前を揃えるだけ）

| 017の要素 | 既存の実装 | 場所 |
|---|---|---|
| §21 Provider Interface | `ProviderDefinition` / `Protocol` / `Deployment(LOCAL\|CLOUD)` / `StructuredOutputMode` / Auto Discovery | `backend/app/ai/gateway/provider_registry.py` |
| §21 Task Router | `AIRouter` + `TaskProfile` + `ForgeTask` | `backend/app/ai/gateway/ai_router.py` |
| §21 Provider独立 | Protocol と identity を分離済み（011-1） | 同上 |
| §5 `provider_id` / `deployment` / `base_model_id` | `ExperienceRecord.provider` / `.model`、`ProviderDefinition.deployment` | `learning_foundation.py:234` |
| §5 `accepted` | `AcceptanceSignal(ACCEPTED\|CORRECTED\|ABANDONED\|UNKNOWN)` | `learning_foundation.py:121` |
| §5 `validator_result` | `validator_passed` | `learning_foundation.py` / `generation_evidence.py` |
| §5 `latency_ms` | `ExperienceRecord.latency_ms` | 同上 |
| §5 `retry_count` | `repair_attempts` | 同上 |
| §5 `design_role_ids` | `design_language_roles` / `DesignRoleDecision` | `generation_evidence.py:316` |
| §5 `capability_ids` | `GenerationRecord.capabilities` | `generation_evidence.py:336` |
| §5 `artifact_ref` | `ArtifactIdentity.artifact_id`（**016A commit Bで実装**） | `artifact_feedback.py` |
| §7 `content_hash / fingerprint` | `document_fingerprint()`（B）/ `dataset_fingerprint()` | `artifact_feedback.py` / `benchmark_evidence.py:84` |
| §12 provenance / training rights | `TrainingProvenance` / `ModelProvenance.may_be_used_where_provenance_matters` | `learning_foundation.py:97,330` |
| §12 UNKNOWNをTrainingへ入れない | 既に`UNKNOWN`を**通さない**実装 | `learning_foundation.py:338` |
| §15 Evaluation | `BenchmarkRun` / `Verification` / `is_usable_for_routing()` | `benchmark_evidence.py:190` |
| §15 aggregateだけでReleaseしない | `ranking_for()`が件数・鮮度・dataset同一性・schema成功率を個別Gate | `benchmark_evidence.py:296` |
| §14 「実測でないものをRoutingへ流さない」 | `Verification.REAL`以外を弾く | `benchmark_evidence.py` |
| §8 生成物のPII/危険表現scan | `OutputSafetyChecker` | `app/ai/runtime/output_safety.py` |
| §8 入力のInjection scan | `scan_for_injection()` | `app/ai/runtime/injection_scan.py` |
| §19 Design Revision | `RevisionRecord` / `DesignRevision` / `RevisionEvidenceStore`（**B**） | `revision_evidence.py` |
| §19 ACCEPTED/CORRECTED | `POST /api/v1/ai/feedback`（**B**） | `app/routers/ai.py` |
| §23 Supabase接続の型 | Repository + DI パターンが既にある（workspace/folder） | `app/repositories/supabase_*.py` / `app/core/di.py` |

### 特筆: §5のLearning Eventのフィールドは、**すでに3つの型に分散して存在する**

```
ExperienceRecord  … 1回のAI呼び出しの事実（provider/model/latency/structured_output）
GenerationRecord  … 1つの生成物の事実（domain/validator/roles/capabilities/visual_structure）
RevisionRecord    … 1回の変更の事実（base_generation_ref/design_revisions/sequence）
BenchmarkRun      … 1回の測定の事実（dataset_id/dataset_hash/verification/rates）
```

017 §5は**この4つの上位契約**であって、置き換えではない。§5自身が
「これらを捨てない。Learning EventのSourceとして利用する」と書いている
のと一致する。

---

## 2. 部分的にあるもの

| 017の要素 | いまの状態 | 足りないもの |
|---|---|---|
| §2 Local First | `Deployment.LOCAL`はある。だが**Routingに Local優先は無い**（§4-1参照） | Benchmark合格Local を同点時に優先する規則 |
| §2 「Benchmark基準達成ならLocal」 | `is_usable_for_routing()`（件数≥N / 鮮度 / dataset_hash / schema成功率）が`ranking_for()`から呼ばれ、実際に効いている | Capability対応判定・Latency予算との統合 |
| §3 Knowledge | `design_language.knowledge_entries()`が33 role分の語彙を返す | **本番から呼ばれていない（TD69）。** RAGも無い |
| §5 `schema_version` | 各Recordに無い。`GenerationRecord.forge_language_version`だけある | Event自体のschema versioning |
| §7 Artifact | `artifact_id` + `fingerprint`はB で実装 | `artifact_type` / `sanitizer_version` / `quality_state` / Upload経路 |
| §8 Privacy Pipeline | **型で本文を持てない**という強い保証がある（`ExperienceRecord`は自由文字列欄が無い） | Secret Detection / PII Detection / Sanitizer が Learning Event 経路に無い |
| §13 Global Pipeline | `BenchmarkEvidenceStore`が「使える根拠か」を判定する形は同じ | Dedup / Spam / Poisoning / Trust scoring が無い |
| §23 Supabase | workspace/folderのみ。**AI/Learningは1テーブルも無い** | `learning_events`等 |

---

## 3. 名前が違うだけで同じもの（**新しい名前を作らないこと**）

| 017の名前 | 既存の名前 | 判断 |
|---|---|---|
| Task Router | `AIRouter` | **既存名を使う。** 別名の型を作らない |
| Provider Interface | `ProviderDefinition` / Adapter | 既存名を使う |
| Evaluation / Forge Eval | `BenchmarkRun` / `BenchmarkEvidenceStore` | 既存を拡張する |
| `retry_count` | `repair_attempts` | **既存名に寄せる。** Forgeの`repair`は意味が具体的（Validator不合格→修復）で、`retry`より情報量が多い |
| `validator_result` | `validator_passed` | 既存名。boolのままで良い |
| `training_use` | `TrainingProvenance`と**隣接するが別物** | 分けて持つ。前者は**データの利用可否**、後者は**Modelの育ち方** |
| `event-scoped fingerprint` | `document_fingerprint()` / `dataset_fingerprint()` | **§4-3の指摘あり。そのままでは使えない** |

---

## 4. 衝突するもの（**3件。うち1件はCEO判断が要る**）

### 🔴 4-1. §6 `pseudonymous_install_id` は、既存の明文の制約と衝突する

既存コードに、**次の明文がある**（`learning_foundation.py:264`、
`ExperienceRecord.ref`のdocstring）:

> セッションIDでも利用者IDでもない、**Store内の位置**である
> （§22「セッションを跨いで個人を辿れる識別子を持たない」）。
> プロセスを跨いで意味を持たず、記録が捨てられれば無効になる。

`GenerationRecord` / `RevisionRecord` も同じ姿勢で作ってある。
**「同一人物/端末を跨いで辿れる識別子を持たない」は、いまのForgeの
設計上の約束である。**

017 §5・§6は `pseudonymous_install_id` を**必須フィールド**として要求
する。これは Global Learning（1端末が大量Eventで偏らせるのを防ぐ
§14 per-user contribution limits）に**必要**であり、017としては正しい。

しかし**方針の変更である**。「名前を消したから匿名」ではないと §6 自身が
言っているとおり、これは
「辿れる識別子を持たない」→「仮名で辿れる識別子を持つ」
への転換であり、**黙って入れてはいけない。**

**推奨**: 二層にする。

```
Local Evidence（いまの3 Record）  … 識別子を持たない。従来どおり
        ↓ Consent + Sanitize を通ったときだけ
Learning Event（Cloudへ出るもの） … pseudonymous_install_id を持つ
```

こうすると、Consentを出していない利用者のローカル記録は
**いまと同じ性質のまま**であり、辿れる識別子は「外へ出すと決めた
ものにだけ付く」。§9「OFFでも基本Forge / Local AI / Personal Memory
が使えること」とも整合する。

**→ `docs/OPEN-DECISIONS.md` の判断項目Fとして起票した。**

### 🟡 4-2. §2 Local First と、`AIRouter._order()` が明示的に退けた「Local優先」

`ai_router.py:355` のdocstringに、**実装して考え直した記録**がある:

> **Local優先は根拠が無い**。§5は「固定ルールで決め打ちせずBenchmarkで
> 決定する」と明示している。Benchmarkが無いのにLocalを優先するのは、
> **測っていない品質を賭けてQuotaを節約している**だけで、Product
> Qualityを壊しうる。

017 §2はこれと**矛盾しない**——§2も「Capability対応済み・Benchmark基準
達成・Latency範囲内**なら**Local」と条件付きだからである。

ただし**現状の`_order()`にはLocal優先が1行も無い**ので、017 §2を満たす
には規則を足す必要がある。足し方を誤ると、上のdocstringが警告した状態
（測っていない品質でRoutingが決まる）に戻る。

**推奨**: `ranking_for()`が**順位を返せたときの同点処理**としてのみ
Local優先を入れる。順位が無い（＝測っていない）ときは従来どおり宣言順。
「Local Firstは Benchmark の中でだけ効く」という形にする。

### 🟡 4-3. §7の指摘は、**016A commit Bで実装した`document_fingerprint()`に当たる**

§7:

> `original_output_hash` / `corrected_output_hash` を全ユーザー共通で
> 単純hashする設計は避ける。

`document_fingerprint()` は **salt無しのsha256** である。

現時点では**プロセス内でしか使っておらず、Cloudへ出ない**（世代照合
専用）ので実害は無い。しかし017 §5がこれを Learning Event に載せると、
**同じDocumentを作った別々の利用者が同じ値を持つ**——横断で突き合わせ
られる識別子になる。

**推奨**: Learning Eventへ載せる指紋は、`document_fingerprint()`を
そのまま使わず、**event-scopedなsalt/HMAC**を通した別関数にする。
名前も分ける（`document_fingerprint()` = ローカル世代照合専用、と
docstringに明記する）。

---

## 5. 無いもの（新規に作る。ただし小さく）

| # | 無いもの | 017 | 備考 |
|---|---|---|---|
| 1 | Learning Event共通Contract | §5 | 既存4 Recordの**上位**。置き換えない |
| 2 | `scope` (global/app/personal) と `app_id` | §5 §17 §18 | **`app_id`はコードに1箇所も無い**（grep済み）。境界の起点 |
| 3 | Consent | §9 | module自体が無い |
| 4 | Sanitizer / Secret・PII Detection（Learning経路） | §8 | 生成物用の`OutputSafetyChecker`はあるが別用途 |
| 5 | Retention / Deletion | §10 | 無い |
| 6 | Dataset Lineage | §11 | `dataset_hash`はあるが lineage は無い |
| 7 | Poisoning対策 | §14 | 無い |
| 8 | Intelligence Resolver | §3 | **AIRouterを拡張する。並列に作らない** |
| 9 | Adapter Release | §16 | §25で「今回作らない」 |
| 10 | Learning SDK | §22 | §25で「今回作らない」 |

---

## 6. 「巨大parallel architectureを作らない」ための具体的な線引き

| してよいこと | してはいけないこと |
|---|---|
| `AIRouter`に Intelligence Resolver の責務を足す | `IntelligenceRouter`という別の routing 実装を作る |
| 既存3 RecordをLearning Eventへ**変換する**層を1つ作る | 既存3 Recordを捨てて新しいRecordへ書き換える |
| `BenchmarkEvidenceStore`にTask別Eval を足す | `ForgeEvalStore`を別に作る |
| `ProviderDefinition`に capability 判定を足す | 新しいProvider抽象を作る |
| `document_fingerprint()`とは別に salted 版を足す | 既存を黙ってsalted版に差し替える（世代照合が壊れる） |

---

## 7. 実装順への影響（017 §24との整合）

017 §24の順序（A→B→C→D→E→F）は**変えない**。ただしReviewの結果、
**C・Dの時点で決めておかないと後で全面書き換えになるもの**が2つある。

1. **`app_id` / `scope`をいつ型へ入れるか。**
   D（Knowledge/RAG）でKnowledgeEntryを作るなら、その時点で
   `scope: global | app | personal` を持たせないと、後から全Entryへ
   遡って付けることになる。**Dの型定義に含める。**

2. **Consent境界の位置。**
   Dで作るKnowledgeが Personal RAG を含むなら、Consentの有無で
   参照範囲が変わる。**「Consentを見る場所」だけDで決め、実装はEで
   良い**（インタフェースを先に置く、017 §25と同じ姿勢）。

---

## 8. 検証区分

| 項目 | 区分 |
|---|---|
| §1〜§3 の既存実装の同定 | **実測**（該当ファイルを読み、行を挙げた） |
| `app_id`が存在しないこと | **実測**（`grep -rn "app_id" backend forge_ai` = 0件） |
| `_order()`にLocal優先が無いこと | **実測**（`ai_router.py:355-405`を読んだ） |
| `knowledge_entries()`が本番から呼ばれないこと | **実測**（TD69、呼び出し元0件） |
| `document_fingerprint()`がsalt無しであること | **実測**（自分が書いたコード） |
| §4-1 の推奨（二層化）が実際に機能するか | **未検証**（設計案。実装していない） |
