# Task002 — Clean Architecture強化 と AI開発体制まわりの追加

## 依頼内容
- 既存構成は壊さず、以下を追加する:
  - `frontend/lib/core/`（既存）/ `frontend/lib/plugins/` / `frontend/lib/shared/`
  - `backend/app/core/`（既存）/ `backend/app/ai/` / `backend/app/plugins/`
  - `docs/prompts/` / `docs/tasks/`
  - `.ai/` / `.agents/` / `PROMPTS/`
- Domain Layer / UseCase / Entity / Repository Interfaceの配置を含めたClean Architectureへ修正

## 行った変更
- **Backend**: `app/domain/{entities,repositories,usecases}` を新設。
  `domain/repositories` はインターフェースのみを置き、既存の `app/repositories/` を
  その**実装（infrastructure）置き場**として役割を再定義（既存フォルダは削除・移動していない）。
- **Backend**: `app/ai/{generators,validators,memory,prompts}` を新設し、
  「AIはJSONのみ返す」という原則をコード構造上でも担保する層を用意。
- **Backend**: `app/plugins/{interfaces,registry,sandbox}` を新設（Plugin受け入れ契約のみ）。
- **Frontend**: `lib/plugins/{interfaces,registry}`、`lib/shared/{models,extensions,utils}` を新設。
  `shared_widgets/`（UI専用）とは明確に役割分離。
- **Meta**: `PROMPTS/`（実行時プロンプト資産）、`docs/prompts/`（プロンプト設計ドキュメント）、
  `docs/tasks/`（本ファイルのようなタスク履歴）、`.ai/`・`.agents/`（AI開発エージェント設定）を新設。
- `README.md` / `docs/ARCHITECTURE.md` を更新し、新しいレイヤー・フォルダの依存関係を明記。

## 変更理由
- Task001時点ではBackendに明確な「Domain Layer」が存在せず、`services/repositories`に
  ビジネスルールと外部技術依存が同居しうる状態だった。`domain/`を切り出すことで
  Frontend側と対称なClean Architecture（entities / repository interface / usecase）を実現し、
  DB・AI基盤の差し替え耐性とテスト容易性を高めた。
- AI関連コードを`services/`直下に混在させず`ai/`として独立させたのは、
  「AIはコードを書かずJSONのみ返す」という製品原則をディレクトリ構造でも強制するため。
- `PROMPTS/`・`docs/prompts/`・`.ai/`・`.agents/`は目的が異なる（実行時資産 / 設計ドキュメント /
  開発支援AIの設定）ため、あえて分離した。詳細は本回答末尾の説明を参照。
