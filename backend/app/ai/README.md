# ai/

AIによるJSON UI Schema生成・検証・改善提案を担うモジュール。
「AIはコードを書かずJSONだけ返す」という大原則（`docs/AI.md`参照）をコードレベルで担保する層。

- `generators/` — 会話 → JSON UI Schema を生成する処理（LLM API呼び出しを含む）
- `validators/` — 生成されたJSONを `shared/schemas/` のJSON Schemaに対して検証する処理
- `memory/` — AI Memory機能のための会話履歴・長期記憶の読み書き（将来のAI Memory機能の実体）
- `prompts/` — 実行時にコードから読み込むプロンプトテンプレートの参照ロジック
  （プロンプトの**本文**は `PROMPTS/` に置き、ここは読み込み・組み立てロジックのみを持つ）

## 依存ルール

- `ai/` は `domain/entities` を参照してよいが、`routers/` や `services/` からは
  `ai/` の公開インターフェース（例: `generate_ui_schema()`）のみを呼び出す。
- `ai/validators/` は生成物を弾く最終防衛ラインであり、ここを通らないJSONはユーザーに返さない
  （`docs/AI.md` の安全境界と対応）。
