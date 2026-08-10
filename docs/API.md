# API設計方針

> 現フェーズではエンドポイントは実装しない。ここでは「今後実装する際に従うルール」を定義する。

## 1. 基本方針

- REST + JSON。将来的にAI応答のストリーミングが必要な箇所のみ SSE/WebSocket を検討。
- バージョニングはURLパスで行う: `/api/v1/...`
- レスポンス形式を統一する:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

エラー時:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "APP_GENERATION_FAILED",
    "message": "人が読めるメッセージ"
  }
}
```

## 2. ルーティング命名規則

- リソース単位で `routers/` にファイルを分ける（例: `routers/apps.py`, `routers/auth.py`）。
- 1 router = 1 リソースグループ。ビジネスロジックは書かず `services` を呼ぶだけにする。
- 将来のリソース例（未実装・命名のみ予約）:
  - `/api/v1/apps` — 生成されたアプリ（JSON Schema）のCRUD
  - `/api/v1/ai/generate` — 会話→JSON Schema生成
  - `/api/v1/auth` — 認証
  - `/api/v1/marketplace` — Marketplace（将来）
  - `/api/v1/teams` — Team（将来）

## 3. 認証（今フェーズでは未実装）

- SupabaseのJWTをFastAPI側の `middleware/` で検証する構成を想定。
- `core/security.py` にトークン検証ロジックを集約し、routersからは
  依存性注入 (`Depends(get_current_user)`) の形でのみ利用する。

## 4. OpenAPI / 契約管理

- FastAPIの自動生成OpenAPIスキーマを `api/openapi/openapi.json` にエクスポートする運用とする。
- Flutter側の型・DTOはこのOpenAPIから将来的にコード生成することを検討（手動同期による齟齬を防ぐ）。

## 5. エラーハンドリング方針

- 例外は `core/exceptions.py` に集約したカスタム例外クラスを使う。
- `middleware/` でキャッチし、統一レスポンス形式に変換する。
- スタックトレースなどの内部情報はレスポンスに含めない（ログにのみ出力）。
