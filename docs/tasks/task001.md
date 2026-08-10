# Task001 — 開発基盤の初期構築

## 依頼内容
- Forgeプロジェクト全体のフォルダ構成の設計・作成
- `frontend/` `backend/` `docs/` `shared/` `database/` `api/` `tests/` `.github/`
- Flutter: Clean Architecture / Feature First / Riverpod / Repository Pattern / DI対応
- FastAPI: routers / services / repositories / models / schemas / core / middleware
- docsにREADME / Architecture / API / Database / AI / Roadmapを作成
- アプリ機能・ログイン・AI・CRUDは作らず、土台のみ作成
- 将来のMarketplace / Plugin / AI Memory / AI Improve / Template / Teamに拡張できる構成にする

## 行った変更
- 上記フォルダ構成一式を作成（`.gitkeep`で空フォルダを保持）
- `README.md`（プロジェクト概要・セットアップ・技術スタック・ディレクトリ説明）を作成
- `docs/`配下に6ドキュメントを作成
- Flutter: `core/` `features/_template_feature/`(domain/data/presentation) `json_ui/` `shared_widgets/`
- FastAPI: `app/routers,services,repositories,models,schemas,core,middleware` + 最小の`main.py`（health checkのみ）
- CI最小構成（`.github/workflows/ci.yml`）、Issueテンプレート

## 変更理由
- JSON UI SchemaによるAI駆動アプリ生成という特性上、`json_ui/`をfeatureからもcoreからも独立させ、
  将来のPlugin/Marketplace拡張の影響範囲を限定できる構成にした。
- 将来機能（Marketplace等）のための空フォルダは作らず、ドキュメント上の配置予定のみ残した
  （中身のない機能フォルダが「実装済みに見える」誤解を避けるため）。
