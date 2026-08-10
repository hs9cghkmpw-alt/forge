# Forge AI Spec(設計のみ・未実装)

FORGE-MILESTONE-002 PHASE6。**このドキュメントが説明する内容は設計であり、
実装ではない。** 実際にLLMへ接続するコードは存在しない
(`backend/app/ai/foundation/providers.py`の全Providerは
`NotImplementedError`を返すスタブ)。

---

## 最終アーキテクチャ(目標)

```
自然言語
  ↓
Intent Planner ────────┐
  ↓                    │
Product Planner         │  すべて LLMAdapter(交換可能) 経由で
  ↓                    │  Provider(OpenAI/Claude/Gemini/OSS/Forge AI)
Language Generator      │  を呼び出す
  ↓                    │
Validator(実装済み・決定的・非AI)
  ↓ 不合格
Repair Engine ──────────┘
  ↓ 合格
Runtime → 完成アプリ
```

AIはコードを書かない。AIが書くのはForge Language(JSON)だけであり、
Flutter/FastAPI/SQLを一切知らない(FORGE-MERGE-001以来、一貫した原則)。

---

## コンポーネント一覧(`backend/app/ai/foundation/interfaces.py`)

| コンポーネント | 型 | 責務 |
|---|---|---|
| `IntentPlanner` | Protocol | 自然言語 → `IntentIR`(目的・対象ユーザー・制約等) |
| `ProductPlanner` | Protocol | `IntentIR` → `PlanIR`(画面・状態・操作の設計) |
| `LanguageGenerator` | Protocol | `PlanIR` → Forge Language JSON(Draft) |
| `Validator` | (実装済み) | `schema_validator.py`。決定的・非AI |
| `RepairEngine` | Protocol | 不合格文書 → 修復案(最大2回) |
| `Critic` | Protocol | 合格文書の品質評価(score/release_ready/issues) |
| `PluginRouter` | Protocol | Plugin/Action呼び出しの許可判定(Plugin本体は未実装) |
| `Memory` | Protocol | Working/Project/User の3層(FORGE-ARCH-001の設計を継承) |
| `Conversation` | Protocol | 複数ターンの対話履歴管理 |
| `PromptBuilder` | Protocol | IR → 実際のプロンプト文字列 |
| `LLMAdapter` | Protocol | Provider差異を吸収する推論の抽象化 |

`Protocol`(Pythonの構造的部分型)を使っているため、実装クラスは
明示的な継承を必要としない。「このインターフェースの形を満たすクラスなら
何でもよい」という交換可能性を型レベルで表現している。

---

## Provider一覧(`backend/app/ai/foundation/providers.py`、全てスタブ)

`OpenAIProvider` / `ClaudeProvider` / `GeminiProvider` / `OSSProvider` /
`ForgeAIProvider`。全て`LLMAdapter`を満たす形だけ用意し、
`complete_structured()`は呼ばれると必ず`NotImplementedError`を投げる
(「動いたふりをしない」ことをテストで保証している。
`tests/test_ai_foundation.py`参照)。

---

## 今回あえて決めなかったこと

- **実際にどのProviderを最初に使うか**: 「AIモデル戦略」(既存モデル利用の
  推奨)は既に方針として存在するが、具体的な選定はCEO承認事項(外部
  Dependency追加)に該当するため、今回は決定していない。
- **Repair Engineの差分形式**: `docs/DECISIONS.md` D4のまま未確定。
- **Pluginの実体**: `PluginRouter`は「許可判定」のインターフェースのみで、
  実際にPluginを実行する仕組みは無い(禁止事項により今回も未実装)。

---

## 次にAIを実装する際の入り口

1. `LLMAdapter`を実装する最初のProviderを1つ選ぶ(CEO承認事項)。
2. `PromptBuilder`の具体実装を1つ書く(`docs/PROMPTS/`の既存プロンプト資産を
   参照できる)。
3. `IntentPlanner`→`ProductPlanner`→`LanguageGenerator`→Validator→
   `RepairEngine`を実際につなぐオーケストレーション層
   (`backend/app/ai/pipeline.py`のような新規ファイルを想定)を書く。
4. Mock Generatorと同じ`AppGenerationRepository`インターフェースの、
   3つ目の実装(`RealAiAppGenerationRepository`のようなもの)を追加し、
   `AppConfig`に新しいモード切り替えを追加する(既存のMock/HTTP切り替えと
   同じ設計パターンを踏襲できる)。
