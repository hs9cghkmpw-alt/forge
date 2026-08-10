# Architecture

> **実装状況(Task003時点)**: 本章で説明する設計そのものは変更していない。
> `json_ui/`(Frontend)・`ai/validators`・`ai/generators`(Backend)は
> Task003で初めて実コードが入った(それまでは本章の記述のみで実体は無かった)。
> Dart側はClaude環境で`flutter analyze`未実施のため、CEO環境での確認が必要。
> 詳細は `docs/tasks/task003.md`・`docs/DECISIONS.md`・統合レポートを参照。

## 1. 全体像

```
[User] --(会話)--> [AI] --(JSON UI Schema)--> [Flutter Client] --(render)--> [画面]
                       │
                       ▼
                [FastAPI Backend] <---> [Supabase]
```

- ユーザーは会話でアプリを説明する。
- AIは **JSON UI Schema** のみを出力する（コードは書かない）。
- Flutterはこの JSON を解釈し、動的にWidgetツリーを構築する（`json_ui/` モジュール）。
- FastAPIは JSON Schemaの永続化・検証・バージョン管理・AI呼び出しの仲介を担う。
- Supabaseはデータ永続化・認証・ストレージを担う（今フェーズでは未接続）。

## 2. Frontend: Clean Architecture × Feature First

```
frontend/lib/
├── core/                 # 全feature共通の基盤（DI, theme, network, error, utils）
├── json_ui/              # ★JSON→Widget動的レンダリングエンジン（Forgeの心臓部）
│   ├── schema/            # JSON Schemaのdartモデル定義・パーサ
│   ├── widget_registry/   # "type": "button" などをFlutter Widgetにマッピングする辞書
│   └── renderer/          # schemaを受け取りWidgetTreeを構築するレンダラ
├── features/
│   └── _template_feature/ # 新機能を追加する際のひな形（このコピーで機能追加）
│       ├── data/           # datasources / models / repositories(実装)
│       ├── domain/         # entities / repositories(interface) / usecases
│       └── presentation/   # providers(Riverpod) / screens / widgets
├── shared/                # feature横断の非UIロジック（models/extensions/utils）
├── plugins/               # プラグインを受け入れる契約（interfaces/registry）。実装は置かない
└── shared_widgets/        # 複数featureで使う共通UIパーツ
```

### `shared/` と `shared_widgets/` と `core/` の違い

- `core/` — アプリの縦の土台（DI・network・theme等）。業務ロジックを持たない。
- `shared/` — feature横断の**業務寄りロジック**（UIを持たない）。特定featureに依存してはならない。
- `shared_widgets/` — feature横断の**UIパーツ**のみ。ロジックを持たない。

### `plugins/` の位置づけ

`plugins/` はPluginを**受け入れるための契約**（interface・registry）のみを持ち、
Plugin自体の実装は含まない。`json_ui/widget_registry/`（組み込みWidget解決）と
`plugins/registry/`（外部拡張Widget解決）を分離することで、コア機能への影響範囲を限定する。

### レイヤー依存ルール（Clean Architecture）

```
presentation → domain ← data
```

- `domain` は他のどのレイヤーにも依存しない（Flutter SDKにも依存しない純粋Dart推奨）。
- `data` は `domain` のinterfaceを実装する（Repository Pattern）。
- `presentation` は `domain` のusecase/entityのみを参照し、`data` を直接参照しない。
- DIはRiverpodの `Provider` / `AsyncNotifierProvider` を使い、
  `data` の実装を `domain` のinterfaceに束縛する形で `core/di/` に集約する。

### なぜ `json_ui/` を `features/` と分離するか

`json_ui` はどの機能からも使われる「レンダリングエンジン」であり、
特定の業務機能（feature）ではなく **プラットフォームのコア** であるため、
`core` でも `features` でもない独立したトップレベルモジュールとして切り出す。
これにより将来 Plugin / Marketplace がレンダラを拡張する際も
影響範囲を `json_ui` に閉じ込められる。

## 3. Backend: レイヤードアーキテクチャ + Clean Architecture

```
backend/app/
├── routers/         # HTTPエンドポイント定義のみ。ロジックを書かない。
├── services/         # 複数usecaseを跨ぐアプリケーション層（例: AI呼び出しを伴う調整役）
├── domain/            # ★Clean Architectureの中心。フレームワーク非依存。
│   ├── entities/       # 純粋なビジネスデータ（外部I/Oを持たない）
│   ├── repositories/    # リポジトリの**インターフェース**（実装は持たない）
│   └── usecases/        # 1ユースケース=1クラス。entities/repositories(interface)のみに依存
├── repositories/      # domain/repositories のインターフェースを実装する具象（infrastructure層）
├── ai/                 # AI生成・検証・記憶（generators/validators/memory/prompts）
├── plugins/            # プラグインを受け入れる契約（interfaces/registry/sandbox）
├── models/             # DBテーブルに対応するORM/データモデル
├── schemas/            # Pydanticによるリクエスト/レスポンスの型定義（API境界のDTO）
├── core/               # 設定(config)・DIコンテナ・セキュリティ・共通例外
└── middleware/         # 認証・ロギング・エラーハンドリング等の横断的関心事
```

### 依存ルール（Clean Architecture）

```
routers → services → usecases(domain) → repositories(interface, domain)
                                                  ↑
                                     repositories(実装, infrastructure)
                       usecases → entities(domain)
```

- **`domain/`は他のどのレイヤーにも依存しない**（FastAPI・Supabase SDKへの参照を持たない、純粋なPython）。
  Frontendの `domain/`（他レイヤーに依存しない）と対称の設計。
- `usecases/` は `repositories/` の**インターフェース**にのみ依存し、
  具象実装（`app/repositories/` = infrastructure層）を知らない。
- 具象の `app/repositories/` が `domain/repositories/` のインターフェースを実装し、
  `core/di.py`（今後追加）で束縛する（Dependency Inversion）。
- `services/` はusecaseの「上」に位置し、複数usecaseの調整や `ai/` 呼び出しなど
  ユースケース単体では閉じないアプリケーション固有の処理を担う。
- `routers` はリクエストの受け取り・レスポンス整形のみ。ビジネスロジックを持たない。
- `core` に設定・DI・共通エラーを集約し、他レイヤーが循環依存しないようにする。

### なぜ `services/` を残しつつ `domain/usecases/` を追加したか

`services/` だけでは「1機能の業務ロジック」と「複数機能にまたがる調整・外部API呼び出し」が
同じ層に混在しやすい。`usecases/` を切り出すことで、
- `usecases/` = 単一の業務ルール（テストしやすい、フレームワーク非依存）
- `services/` = usecase群の組み合わせ・AI連携等のアプリケーション固有ロジック
と役割を分離し、将来DB基盤やAI基盤を差し替える際の影響範囲を `repositories/` `ai/` に限定できる。

### `ai/` と `plugins/` を独立レイヤーにした理由

- `ai/`: 「AIはJSONのみを返しコードを書かない」という製品原則（`docs/AI.md`）を、
  `services/` に埋没させず独立したモジュールとして構造的に強制するため。
- `plugins/`: 将来のサードパーティ拡張が `domain/` や `models/` へ直接アクセスしないよう、
  contractのみを公開する層として`services/`から分離した。

## 4. Shared / API / Database

- `shared/schemas/` — JSON UI SchemaのJSON Schema定義（Frontend/Backend双方が参照する単一の真実源）。
- `api/openapi/` — FastAPIが生成するOpenAPI仕様の保存先。フロント側の型生成にも利用可能。
- `database/migrations/` — Supabaseのスキーマ変更を時系列で管理。
- `database/policies/` — Row Level Security (RLS) ポリシーを明示的にコードで管理。

## 5. 将来拡張ポイント（設計のみ・実装なし）

| 拡張機能 | Frontend配置 | Backend配置 |
|---|---|---|
| Marketplace | `features/marketplace/` | `routers/marketplace.py`, `services/marketplace_service.py` |
| Plugin | `json_ui/widget_registry/` にプラグイン登録の口を用意 | `services/plugin_service.py`（サンドボックス実行を想定） |
| AI Memory | `features/ai_memory/` | `services/memory_service.py` + Supabase `memories` テーブル |
| AI Improve | `features/ai_improve/` | `services/improve_service.py`（既存JSON Schemaの差分提案） |
| Template | `features/template/` | `services/template_service.py` |
| Team | `features/team/` | `services/team_service.py` + RLSでworkspace境界を管理 |

いずれも `_template_feature/` の構造をコピーして追加する前提のため、
現時点でこれらのfeatureフォルダは作成していない（実体のない空のfeatureを増やさない）。

## 6. メタディレクトリ（プロダクトコードではないが必要な資産）

名前が似ていて混同しやすいため、役割を明確に区別する。

| ディレクトリ | 何であるか | 誰が読むか |
|---|---|---|
| `PROMPTS/` | AIが**実行時に読み込む**プロンプト本文（実行資産） | `backend/app/ai/prompts/` のコード |
| `docs/prompts/` | プロンプトの設計意図・変更理由・評価基準（ドキュメント） | 人間（エンジニア） |
| `.ai/` | このリポジトリを開発するAIエージェント**全員に共通**のプロジェクトコンテキスト | AI開発エージェント（Claude Code等） |
| `.agents/` | **役割ごとに異なる**AI開発エージェントの定義（プレースホルダー） | AI開発エージェント（Claude Code等） |
| `docs/tasks/` | 依頼タスクごとの変更履歴（何を・なぜ変更したか） | 人間・AI双方 |

- `PROMPTS/` と `docs/prompts/` の違いは「実行資産」か「その資産についての説明」かの違いであり、
  `docs/README.md` にあるDocs as Source of Truthの原則に従い、仕様（プロンプト本文）を
  変更する際は`PROMPTS/`を先に更新し、`docs/prompts/`にその理由を残す運用とする。
- `.ai/` と `.agents/` の違いは「共通」か「役割別」かの違い。単一のAIエージェントのみで
  開発する場合は `.ai/CONTEXT.md` だけで十分であり、`.agents/` は複数エージェント運用時に使う。
