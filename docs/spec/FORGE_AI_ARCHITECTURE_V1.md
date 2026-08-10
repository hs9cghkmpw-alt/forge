# Forge AI Architecture v1.0 — Architecture Decision Record (ADR)

**Status: ACCEPTED — RESPONSIBILITY BOUNDARIES FROZEN**
**Interface Contract: PROVISIONAL**
**日付:** 2026-07-14　**Ref:** FORGE-MILESTONE-004(Architecture Freeze)

CEOレビュー「M004は実装マイルストーンではなく、Architecture Freeze
マイルストーンとして整理する」に基づき作成した。

**凍結済み(Frozen)の範囲**: マイルストーン番号の割り当て(1章)、
各実装の責務境界(4章)、依存方向の原則(6章)。これらの変更には
CEO承認が必要。

**未凍結(Provisional)の範囲**: 以下は本ADRでは確定していない。
今後の設計・実装で決定する。

- Intent / Plan / Forge IRの共有型(forge_ai/の型とbackend/app/ai/
  foundation/の型を統合するのか、変換アダプタを設けるのか)
- M004↔M005間のAdapter API(呼び出し方、エラーハンドリングの形)
- HTTP API契約(エンドポイント形式、リクエスト/レスポンススキーマ)
- エラー伝播形式(M004内の例外をM005・HTTP層でどう表現するか)
- Provider実装方式(実LLM接続時、どのProviderをどう実装するか)

これらが未確定なままである理由は、まだ実際の接続作業(M005が
M004を呼び出すコード)を書いていないためであり、時期尚早な設計を
避けるための意図的な判断である。

---

## 1. マイルストーン番号の重複解消(最優先事項)

**問題**: 「FORGE-MILESTONE-004」という名前が、時系列の異なる2つの
内容に対して使われていた。

**決定**: CEO提案の通り、以下へ確定する。

| 新番号 | 名称 | 内容 | 対応する既存実装 |
|---|---|---|---|
| **M004** | Forge AI Core | Domain/World/Meaning/Intent/Planner(+Compiler/Repair/Quality) | `forge_ai/` |
| **M005** | Backend AI Integration | Intent Parser/Planner/Critic/Repair/ContextBuilder/ProviderRouter/TemplateEngine/TemplateSelector/PromptPipeline(すべてProtocol + Stub) | `backend/app/ai/runtime/` |
| **M006以降** | (未定、Experimental) | ルールベースのIntent認識・Planning・Template選択 | `backend/app/ai/native/` |

**旧「FORGE-MILESTONE-004: Native AI Phase-1（Intent Engine）」
(2026-07-13付、`docs/reports/FORGE-MILESTONE-004-report.md`)は、
本ADR確定をもって「FORGE-MILESTONE-005」として読み替える。**
過去の記録(CHANGELOG.md・DECISIONS.md D50〜D55・TECH_DEBT.md
TD20〜TD22)は書き換えず、本ADRを正規の参照先として残す
(3章「過去記録の扱い」参照)。

---

## 2. 時系列(Q1への回答: forge_ai/はいつ作られたか)

実際のファイルシステムのタイムスタンプを根拠に再構成した時系列
(推測ではなく、`ls -la --time-style=full-iso`の実行結果)。

```
2026-07-12 05:12 - 10:38
  forge_ai/ 作成
  依頼: 「FORGE PROJECT — AI実装チーム キックオフ指示書」
  内容: Domain Model・World Model・Meaning Model・Intent Model・
        Planner・Compiler・Repair Engine・Quality Engine・
        Provider Interface・Mock Provider・Prompt Builder・Contracts
  → 本ADRにより「M004: Forge AI Core」として正式命名

        │
        ▼

2026-07-13 00:56 - 02:49
  backend/app/ai/runtime/ 第1波
  依頼: 「FORGE-MILESTONE-003(v2): Analyzer Zero → Chrome
        Verification → Native AI Foundation」PHASE6〜9
  内容: AIPlanner・AICritic・AIRepair・AIContextBuilder・
        ProviderRouter・PromptPipeline(Protocol + Stub、
        backend/app/ai/foundation/の型IntentIR/PlanIR/CriticResult
        を再利用)

        │
        ▼

2026-07-13 09:04 - 09:07
  backend/app/ai/runtime/ 第2波
  依頼: 旧「FORGE-MILESTONE-004: Native AI Phase-1（Intent Engine）」
  内容: IntentParser・TemplateEngine・TemplateSelector・
        NativeAIRuntime(bundle)・ProviderRouterへのnative/localエイリアス追加
  → 本ADRにより「M005: Backend AI Integration」として正式命名

        │
        ▼

2026-07-13 09:46 - 09:47 (M005作業の直後、同一セッション内と推測)
  backend/app/ai/native/ 作成
  依頼: 不明(正規のM005報告書に記載が無い)
  内容: intent_recognizer.py・rule_based_planner.py・
        rule_based_template_selector.py(ルールベース)
  → 本ADRにより「Experimental、M006以降」の扱いとする

        │
        ▼

2026-07-14
  forge_ai/を「今回の依頼(Domain/World/Meaning/Intent/Planner)」の
  正式提出物として採用しようとしたところ、M004番号の重複が判明
  → 本ADR(Architecture Freeze)作成
```

**事実と推測の区別**: 各実装のタイムスタンプ・ファイル内容は実際に
確認した事実。「どの依頼に対応するか」は、タイムスタンプの前後関係と
各実装のコード内コメント・ドキュメント(D50〜D55等)を突き合わせた
推定であり、100%の確証ではない(Claude側は該当する依頼文そのものを
現在の会話履歴からは参照できていないため)。

---

## 3. 過去記録の扱い

CHANGELOG.md・docs/DECISIONS.md(D50〜D55)・TECH_DEBT.md(TD20〜TD22)・
`docs/reports/FORGE-MILESTONE-004-report.md`は、**書き換えない**
(歴史的記録として残す)。ただし、いずれも本ADR公開後は「M005に
対応する記録」として読み替えることを、各ファイルの該当箇所に
注記として追加する(4章のファイル一覧参照)。

新しい報告・ドキュメントでは、今後「M004」はForge AI Core
(`forge_ai/`)のみを指すこと。

---

## 4. 責務境界(Q2への回答)

```
┌─────────────────────────────────────────────────────────────┐
│ M004: forge_ai/ (Forge AI Core)                                │
│ Status: 実装済み・80テスト合格・スタンドアロン                  │
│                                                                  │
│ 責務: 自然言語 → Domain/World理解 → Meaning抽出 → Intent構築    │
│      → Application Plan → Forge IR(JSON互換の中間表現)         │
│                                                                  │
│ 依存: なし(Backend/Runtime/実LLMに一切依存しない)               │
│ Provider: forge_ai独自のAIProvider Protocol + MockProvider      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ (概念的な関係のみ。コード上は未接続)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ M005: backend/app/ai/runtime/ (Backend AI Integration)          │
│ Status: Protocol + Stub・221+テストの一部として検証済み         │
│                                                                  │
│ 責務: FastAPI Backend内から呼び出し可能な形で、Intent/Planner/  │
│      Critic/Repair/ContextBuilderをProtocol定義する。           │
│      ProviderRouterで複数Provider名(openai/claude/gemini/oss/   │
│      forge_ai/native/local)を解決する「窓口」の役割。           │
│      PromptPipelineが Intent→Plan→JSON→Validator→Critic→Repair  │
│      というフローを実際にオーケストレーションする(ただし各段階は │
│      Stubなので、実行するとNotImplementedErrorになる)。         │
│                                                                  │
│ 依存: backend/app/ai/foundation/(IntentIR/PlanIR/CriticResult型)│
│      backend/app/ai/validators/(schema_validator、実際に稼働)   │
│ Provider: 5+2種類のProvider名を解決可能(実装はすべてStub)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ (未接続)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ M006以降: backend/app/ai/native/ (Experimental)                 │
│ Status: 由来不明・正規報告書に記載なし・Experimental扱い        │
│                                                                  │
│ 責務: 未確定。現状はルールベースのIntent認識・Planning・        │
│      Template選択を試行したコードが存在する。                  │
│                                                                  │
│ 制約: 本ADR確定後、CEO承認を得るまで、このディレクトリへの      │
│      追加実装・他モジュールからの参照は行わないこと。           │
└─────────────────────────────────────────────────────────────┘
```

**判断基準(今後どこに何を実装するか)**:

- **forge_ai/(M004)へ実装するもの**: Backend/Runtime/実LLMに依存しない、
  純粋なCognitive Engineロジック(Domain定義の追加、Meaning抽出精度の
  改善、Planner/Compilerのロジック改善等)。
- **backend/app/ai/runtime/(M005)へ実装するもの**: FastAPI Backendとの
  統合が前提の処理(実際のHTTPエンドポイントからの呼び出し、実際の
  Provider接続、Validatorとの実結合)。
- **backend/app/ai/native/へは、CEO承認なしに実装しないこと**
  (M006以降、責務未確定のため)。

---

## 5. 接続図(Q3への回答)

**重要な前提**: 以下すべて、現時点(2026-07-14)でこの経路は一切
接続されていない(概念上のつながりであり、実際にHTTP呼び出しや関数
呼び出しで繋がっているわけではない)。現在実際に動いているのは、
`MockAppGenerationRepository`経由のMock Generator(Forge Language
JSON確定パターン)のみである。

CEOレビュー対応: 「処理の概念的な順序」と「実行時の呼び出し方向」が
1つの図に混在していたため、以下3種類へ分離した。**これらは互いに
矛盾しない**(データが流れる論理的な順序と、コードが呼び出される
方向は別の軸である)。

### 5.1 Conceptual Pipeline(データが辿る論理的な段階)

「何のために何をするか」という処理段階の順序。**誰が誰を呼ぶかは
示していない。**

```
Natural Language
    ↓
Domain / World 理解
    ↓
Meaning 抽出
    ↓
Intent 構築
    ↓
Application Plan
    ↓
Forge IR(JSON)
    ↓
Validation
    ↓
Rendered UI
```

### 5.2 Runtime Call Graph(実行時、誰が誰を呼び出すか)

**実行時の基本方向は、M005(Backend AI Integration)がM004
(Forge AI Core)を呼び出す構造である。** M004がM005を呼び出すことは
無い(M004はスタンドアロンなライブラリであり、HTTPやBackendの
存在を知らない)。

```
Flutter
    │ HTTP Request
    ▼
Backend HTTP Handler(未実装、/api/v1/ai/generate相当)
    │ 呼び出す
    ▼
M005: backend/app/ai/runtime/prompt_pipeline.py の PromptPipeline
    │ 呼び出す(ライブラリ依存として。今回は未接続、6.1参照)
    ▼
M004: forge_ai/core/pipeline.py の run_pipeline()
    │ 戻り値(Forge IR / dict)
    ▲
M005: 戻り値を受け取り、次に…
    │ 呼び出す(既に実装済み、実際に動作するimport)
    ▼
Validator: backend/app/ai/validators/schema_validator.validate_forge_document()
    │ 戻り値(ValidationResult)
    ▲
M005: HTTP Responseを構築
    │ HTTP Response
    ▼
Flutter(受信・描画)
```

### 5.3 Source-code Dependency Direction(importの方向)

```
backend/app/ai/runtime/ (M005)
    │ import する(実装済み、実際に確認済み)
    ├──▶ backend/app/ai/foundation/ (IntentIR・PlanIR・CriticResult等)
    └──▶ backend/app/ai/validators/schema_validator (実際に動作するValidator)

backend/app/ai/runtime/ (M005)
    │ import する(未実装。今回のADRではPROVISIONAL、6.1参照)
    └──▶ forge_ai/ (M004)

forge_ai/ (M004)
    │ import する
    └──▶ (Python標準ライブラリのみ。backend/・M005への依存は無い)
```

**確認方法**: `grep -rn "forge_ai" backend/app/ai/runtime/*.py`を実行
すると、コメントおよびProvider名の文字列("forge_ai")としての言及は
あるが、実際の`import forge_ai...`という行は存在しないことを確認できる
(2026-07-14時点で実行して確認済み)。同様に`grep -rn "^from app\.|^import app\." backend/app/ai/runtime/*.py`
を実行すると、`app.ai.foundation.*`・`app.ai.validators.schema_validator`
への実際のimportが確認できる。

**現在実際に動いている経路(参考、上図とは別)**:

```
User → HomeScreen(Flutter) → MockAppGenerationRepository
     → MockGenerationDataSource(Dart、キーワードマッチング)
     → Forge Language JSON(確定パターン、AI推論なし)
     → ForgeDocument.fromJson → Renderer → 画面表示
```

この経路にはforge_ai/・backend/app/ai/runtime/のいずれも関与しない。

---

## 6. Freeze後の変更ルール

### 6.1 未凍結(PROVISIONAL)の項目 — 実装時に決定すること

冒頭のStatusで示した通り、以下は本ADRでは確定していない。
M005がM004を実際に呼び出すコードを書く際に、CEO承認を得た上で
決定すること。

- **Intent / Plan / Forge IRの共有型**: `forge_ai/`の`Intent`/
  `ApplicationPlan`/`ForgeIRDocument`と、`backend/app/ai/foundation/`の
  `IntentIR`/`PlanIR`は、現状は別々の型として存在する。統合するか、
  変換アダプタを設けるかは未決定。
- **M004↔M005 Adapter API**: M005からM004の`run_pipeline()`等を
  どう呼び出すか(直接import、サブプロセス、その他)は未設計。
- **HTTP API契約**: `/api/v1/ai/generate`相当のエンドポイントの
  リクエスト/レスポンス形式は未設計。
- **エラー伝播形式**: M004内で発生した例外を、M005・HTTP層で
  どう表現するかは未設計。
- **Provider実装方式**: 実LLM接続時、`AIProvider`/`LLMAdapter`
  Protocolをどう実装するか(Provider1つずつ実装するのか、共通の
  アダプタ層を作るのか)は未設計。

### 6.2 凍結済み(FROZEN)の変更ルール

本ADR確定後、以下を守ること。

1. `forge_ai/`・`backend/app/ai/runtime/`・`backend/app/ai/native/`の
   責務(4章)を変更する場合は、本ADRを更新してから実施する。
2. 「M004」という名前は、今後`forge_ai/`(Forge AI Core)のみを指す。
3. `backend/app/ai/native/`への追加実装は、CEO承認を得てから行う。
4. forge_ai/とbackend/app/ai/runtime/の型統合(TD16、継続課題)は、
   本ADRの4章で示した責務境界を前提に設計すること
   (どちらか一方を単純に「正」として片方を廃止するのではなく、
   forge_ai/はスタンドアロンなCognitive Engine、backend/app/ai/runtime/は
   Backend統合層、という役割分担を維持する設計を優先する)。
