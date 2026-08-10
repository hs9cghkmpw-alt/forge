# Database設計方針（Supabase）

> 現フェーズではテーブルは作成しない。将来の設計がぶれないための方針のみ定義する。

## 1. 方針

- SupabaseはPostgres + Auth + Storage + Realtimeをフル活用する。
- スキーマ変更は必ず `database/migrations/` にSQLファイルとして残す（Supabase CLIのマイグレーション運用）。
- 命名規則: テーブル名は複数形スネークケース（例: `apps`, `app_versions`, `users`）。

## 2. 想定コアテーブル（未作成・設計メモ）

| テーブル | 役割 |
|---|---|
| `users` | Supabase Auth連携のユーザープロファイル |
| `apps` | ユーザーが生成したアプリのメタ情報 |
| `app_versions` | アプリのJSON UI Schemaのバージョン履歴（イミュータブル） |
| `ai_conversations` | AIとの会話ログ（AI Memoryの基礎データ） |
| `ai_memories` | 会話から抽出された長期記憶（将来のAI Memory機能） |
| `templates` | 再利用可能なアプリ雛形（将来のTemplate機能） |
| `marketplace_listings` | 公開・販売されるアプリ/テンプレート（将来のMarketplace機能） |
| `teams` / `team_members` | チーム・組織管理（将来のTeam機能） |
| `plugins` | インストール可能なプラグイン定義（将来のPlugin機能） |

`app_versions` を `apps` から分離しているのは、JSON Schemaの変更履歴を
イミュータブルに保持し、AI Improveが「差分提案」を行えるようにするため。

## 3. Row Level Security (RLS)

- 全テーブルでRLSを有効化することを前提とする。
- ポリシーは `database/policies/` にSQLとして明示的に管理し、コンソールで直接編集しない。
- Team機能実装時は `team_id` ベースのポリシーに拡張できるよう、
  早い段階から `owner_id` に加えて `team_id (nullable)` カラムを想定しておく。

## 4. マイグレーション運用

```
database/
├── migrations/   # 001_init.sql, 002_add_apps_table.sql ...（連番管理）
├── seeds/         # 開発用のダミーデータ投入スクリプト
└── policies/      # RLSポリシー定義（テーブルごとにファイル分割）
```
