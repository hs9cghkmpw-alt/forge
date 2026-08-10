# AI設計方針

## 1. 大原則

**AIはコードを一切生成しない。AIが生成するのはJSON UI Schemaのみ。**

理由:
- コード生成は実行環境・セキュリティリスク・ビルド管理が複雑になる。
- JSONに制約することで、Flutter側で安全にサンドボックス的に解釈・検証できる。
- JSONはバージョン管理・差分比較・AIによる自己改善（AI Improve）と相性が良い。

## 2. 責務分担

| 主体 | 責務 |
|---|---|
| AI | 会話の意図を解釈し、JSON UI Schemaを生成・修正する |
| Backend (FastAPI) | AI呼び出しの仲介、生成されたJSONの検証・保存・バージョン管理 |
| Frontend (Flutter) | JSON UI Schemaを解釈し、Widgetツリーとしてレンダリングする |

AIは **JSON Schemaという「契約」の中でのみ自由** であり、
契約外の出力（任意コード・任意ファイル操作など）は許可しない。

## 3. JSON UI Schema の設計方針（概略）

- `shared/schemas/` にJSON Schema（JSON Schema仕様）として定義し、Frontend/Backend双方が同じ定義を参照する。
- v1で確定した実際の最小構造(Task003。`shared/schemas/ui_schema.v1.json`参照。
  以前ここにあった例は`screen`が単数・`"type": "screen"`付きだったが、実装したv1とは
  形が異なっていたため、実際のSchemaに合わせて更新した):

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

`screen`はWidgetのtype一覧には含まれない(`text`/`text_field`/`button`/`column`/`row`/
`checklist`の6種類のみ)。`screens`は配列であり、`initial_screen_id`が最初に表示する
画面を指す。詳細は `docs/DECISIONS.md` D2・D3、統合レポート「Forge Language v1」章を参照。

- Backendは受け取ったJSONを `shared/schemas/` の定義に対してバリデーションしてから保存する。
- Flutterの `json_ui/widget_registry/` が `"type"` の値をキーにWidgetを解決する
  （未知の`type`は安全に無視 or フォールバックWidgetを表示）。

## 4. AIの安全境界

- AIの出力は必ずJSON Schemaバリデーションを通過させる（Backend側の責務）。
- バリデーションに失敗したJSONはユーザーに返さず、再生成 or エラー表示にフォールバックする。
- AIに外部実行権限・ファイルシステムアクセス・任意コード実行権限を与えない。

## 5. 将来機能との関係

- **AI Memory**: 過去の会話・生成履歴を `ai_conversations` / `ai_memories` に保存し、
  次回生成時のコンテキストとして利用する（今フェーズでは未実装）。
- **AI Improve**: 既存の `app_versions` を比較し、UI/UX改善のJSON差分を提案する機能。
  「生成」と「改善提案」は別サービス (`services/generation_service.py` /
  `services/improve_service.py`) として分離する想定。
