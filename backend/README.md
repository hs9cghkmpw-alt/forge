# backend/

FastAPI製バックエンド。レイヤードアーキテクチャ（routers → services → repositories → models）。

- `app/routers/` — HTTPエンドポイント定義のみ。ロジックを持たない
- `app/services/` — ビジネスロジック本体
- `app/repositories/` — Supabase/DBアクセスの抽象化
- `app/models/` — DBテーブルに対応するデータモデル
- `app/schemas/` — Pydanticのリクエスト/レスポンス型
- `app/core/` — 設定・DI・セキュリティ・共通例外
- `app/middleware/` — 認証・ロギング・エラーハンドリング等

新しいリソースを追加する際は、`routers/`, `services/`, `repositories/`, `schemas/` に
同名ファイルを一貫した命名で追加する（例: `apps.py` を4層すべてに用意）。
