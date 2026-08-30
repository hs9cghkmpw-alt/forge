# AI設計方針

> **位置づけ（2026-08-30 全体スキャンで修正）**
>
> この文書は Forge の **AI実装・安全境界** を説明する。Forgeそのものの最終目標を
> 「既知のJSON UIを生成すること」へ狭めてはならない。上位のSource of Truthは
> `FORGE-CORE-CONSTITUTION.md` → `PRODUCT-DIRECTION.md` →
> `GENERATIVE-SOFTWARE-DIRECTION.md`。
>
> **不変条件:** 持っている能力は組み合わせる。足りない能力は作る。作った能力は
> 検証し、再利用可能な Forge Capability として取り込む。

## 1. 大原則

現在の主要な安全実行経路では、LLMが任意コードを直接Runtimeへ注入するのではなく、
**versioned Forge Language / JSON UI Schema** を生成し、Validator・Compiler・Runtimeを
通して実行する。この境界は重要な安全装置である。

ただし、これは **現在の実行方式** であって Forge の生成力の上限ではない。
既存Languageでユーザー要求を表現できない場合は、要求を近い既存Widget/Templateへ
黙って変換するのではなく、正確な Capability Gap を保持し、安全な self-extension /
build-time extension / service adapter / native adapter 等の経路で必要能力を作る。

JSONに制約する利点:
- 現行Runtimeでは実行対象を検査・制限できる。
- version管理・差分比較・再現性・AI Improveと相性が良い。
- 任意コードの即時実行より、Validator/Test/Evidenceのゲートを置きやすい。

## 2. 責務分担

| 主体 | 責務 |
|---|---|
| AI / Planner | 会話の意図を解釈し、必要Capabilityを分解し、既存能力のcompositionと不足能力を区別する |
| Capability / Extension層 | 不足Capabilityを明示し、安全な生成・拡張経路を選ぶ |
| Backend (FastAPI) | AI呼び出し、versioned artifact検証、保存、version管理、policy enforcement |
| Compiler / Validator | Semantic/IRを実行可能Languageへ落とし、契約違反をfail-closedにする |
| Frontend / Runtime | 検証済みForge Languageを解釈して実行する |

AIは、現行JSON経路では **Schemaという契約の中でのみ自由** である。
契約外の能力が必要なときはSchemaを捏造して突破せず、extension経路へ上げる。

## 3. Forge Language / JSON UI Schema の設計方針（概略）

- `shared/schemas/` にversioned JSON Schemaを定義し、Frontend/Backendが同じ契約を参照する。
- v1時点の最小構造例:

```json
{
  "version": "1.0",
  "app": { "title": "買い物メモ" },
  "initial_screen_id": "shopping_list",
  "screens": [
    {
      "id": "shopping_list",
      "title": "買い物メモ",
      "state": {
        "items": { "type": "checklist", "value": [] }
      },
      "body": {
        "type": "column",
        "id": "root",
        "children": [
          { "type": "checklist", "id": "list", "state_ref": "items" }
        ]
      }
    }
  ]
}
```

この例やv1 vocabularyは **製品境界ではない**。後続versionですでに拡張されており、
未知要求に対してv1の6 Widgetへ無理に押し込む根拠にしてはならない。

- Backendは生成artifactを対応するSchemaに対してvalidationしてから保存/実行する。
- Flutterのregistryは`type`を解決し、未知typeを直接実行しない。
- 必要なtype/semantic capabilityが無ければ、「別の既知typeで代用して成功」ではなく
  Capability Gap → extension設計 → applicable bindings + test/build/runtime evidence → promotionとする。

## 4. AIの安全境界

- 現行Forge Language出力は必ずValidatorを通す。
- validation失敗を成功扱いしない。
- model自己申告だけでCapabilityをIMPLEMENTEDへ昇格しない。
- AIに無制限の外部実行・filesystem・secret・不可逆操作権限を与えない。
- 新能力を作る場合も、隔離・allowlist/policy・permission・test・evidenceを経る。
- `PARTIAL` / `MISSING` / `MOCK` / `STUB` / `UNVERIFIED`を`IMPLEMENTED` / `PASS`へ言い換えない。

## 5. 将来機能との関係

- **AI Memory**: 過去の会話・生成履歴を、privacy/policyに従って次回生成のcontextへ利用する。
- **AI Improve**: 既存artifact/versionを比較し、改善・repairを提案/実行する。
- **Self Extension**: 既存Capabilityのcompositionで満たせない意味要求を、exact gapとして保持し、
  安全に能力生成・実装・検証・再利用可能化する。これは「最後にやる別機能」ではなく、
  Forge本来の生成力に必要な横断要件である。

## 6. Conversation Readiness / Question Policy(FORGE-CONVERSATION-READY-001、2026-08-12)

「どこまで聞いたら作るのか」を決める層。実装は
`backend/app/ai/runtime/conversation_policy.py`と`conversation_engine.py`。

### 6.1 大原則: LLM Proposal < Deterministic System Facts

会話の判断において、**LLMの自己申告は単独では決して根拠にならない**。
ASK/BUILD/UPDATE/CONFIRMはForge側のsystem factsから決定する。

| System Fact | 帰結 |
|---|---|
| `has_existing_tool == False` | LLMが`update`と言ってもUPDATE不可 |
| blocking unknownあり | 原則BUILD不可 |
| external side effectあり | CONFIRM必須 |
| destructive actionあり | CONFIRM必須 |
| Validator blocking error | BUILD完了扱いにしない |

### 6.2 Conversation Readiness

| 値 | 意味 | Action |
|---|---|---|
| `BUILD_READY` | 重要な未知が無い | BUILD / UPDATE |
| `SAFE_TO_ASSUME` | 残る未知はLOW以下等 | BUILD / UPDATE(仮定を記録) |
| `NEEDS_QUESTION` | 聞くべき未知がある | ASK |
| `NEEDS_CONFIRMATION` | 外部作用・不可逆操作 | CONFIRM |
| `INSUFFICIENT_INFORMATION` | blocking未解消 | ASK(**BUILDしない**) |

### 6.3 Question Policy / Safe Assumption

blocking/highのみ質問し、lowはSafe Assumption候補、cosmeticはDesign Systemへ任せる。
聞かずに決めたことは`key` / `value` / `reason`を記録する。

### 6.4 MAX_CONVERSATION_TURNS

閾値は「無理にBUILDする上限」ではなく質問戦略を変える目安。blockingは未解消のままBUILDしない。

### 6.5 Build Failure Fallback

BUILD後のPipeline失敗を、ユーザー要求を別の簡単なToolへ変更して隠してはならない。

- 理解段階の不足ならASKへ戻す。
- generation/validation/repair失敗ならrepair/extension/gapへ進む。
- Provider障害は追加質問で直るふりをしない。
- **既知のchecklistやCRUDへ強制fallbackして「作れた」扱いにするのは禁止。**

## 7. Solution Shape — 現在の互換層と是正方針

`forge_ai/core/ir/solution_shape.py` は現在のCompilerへpresentation shapeを渡すための
**互換・実装層**であり、Forgeが作れるものの一覧ではない。

過去の設計では Entity Field から既知shapeへ分類し、Runtimeにincrementが無いカウンタ要求を
`RECORD_CRUD`で代用する方針があった。**これはcanonical directionと不整合であり、全体スキャンでstrategic driftとして認定した。**

正しい原則:

```text
semantic need
 -> exact capability
 -> existing composition if supported
 -> otherwise Capability Gap
 -> synthesis / extension
 -> validation/evidence
 -> reusable capability promotion
```

したがって`count + 1`が無いなら「RECORD_CRUDで代用」が最終仕様ではない。
`interact.increment` / generic state transition等の意味Capabilityを保持し、既存Runtimeで表現できなければ
MISSINGとしてextensionへ渡す。Entity shapeだけではbehavioral intentを判定できないため、
単純に「number fieldならcounter」とする修正もしない。

既存SolutionShapeは段階的にSemantic Capability / IR主導のcompositionへ置き換える。
Golden testや一個のdomain専用分岐を追加して逃げない。

## 8. Model Gateway / Provider独立性

Forge Brain → Model Gateway → Provider(Gemini / Local / Mock)

Providerは交換可能で、上位logicは特定providerを製品前提にしない。JSON parse失敗等を成功扱いにしない。

## 9. Scripted Conversation / Benchmark

Scripted conversationやGolden datasetは品質評価の**試験面**であり、製品目標やtemplate一覧ではない。
未知要求を失わず必要Capabilityを保持し、unsupportedなら正確にgapへ落とせるかも評価対象にする。

## 10. 全体スキャンとの関係

今後「全体スキャン」では本ファイルも対象とし、以下を検出する:

- JSON/Widget/ShapeをForgeの最終目的と誤記していないか
- unsupportedを近いtemplateへ縮小していないか
- failure時にknown shapeへfail-openしていないか
- missing capabilityがsemantic layerで消えていないか
- self-extensionがproduction pathへ未接続なのに実装済み扱いしていないか

詳細: `docs/FORGE-WHOLE-SCAN-PROTOCOL.md`
