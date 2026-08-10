# AI開発エージェント向け共通コンテキスト

このリポジトリで作業するAIエージェントは、コードを書く前に以下を前提として理解すること。

1. **原則**: プロダクトのAI（`backend/app/ai/`）はJSON UI Schemaのみを生成し、コードを生成しない。
   この原則をコード生成時に混同しないこと（＝あなたがコードを書くこと自体は問題ないが、
   プロダクトのAI機能を実装する際にコード生成をさせる設計を提案しないこと）。
2. **依存の向き**: 常に `presentation/routers → usecase → domain(interface) ← infrastructure` を守る。
   `domain/` にフレームワーク依存（FastAPI, Supabase SDK, Flutter SDK）を持ち込まない。
3. **既存構成の尊重**: 新機能は既存フォルダを壊さず、`_template_feature/`（Frontend）や
   `domain/usecases`（Backend）の型に沿って追加する。
4. **ドキュメント同期**: 仕様を変更したら `docs/ARCHITECTURE.md` 等の関連ドキュメントも同じPRで更新する。
5. **詳細**: `docs/ARCHITECTURE.md` `docs/AI.md` を読んでから作業を開始すること。
