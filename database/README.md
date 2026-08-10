# database/

Supabase (Postgres) のスキーマ管理。

- `migrations/` — スキーマ変更を連番SQLファイルで管理（Supabase CLI運用を想定）
- `seeds/` — 開発用ダミーデータ投入スクリプト
- `policies/` — Row Level Security (RLS) ポリシーをコードとして管理

詳細方針は `docs/DATABASE.md` を参照。
