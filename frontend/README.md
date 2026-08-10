# frontend/

Flutterクライアント。Clean Architecture + Feature First + Riverpod構成。

- `lib/core/` — DI・テーマ・定数・network・エラー処理など全feature共通の基盤
- `lib/json_ui/` — ★JSON UI SchemaをWidgetツリーに変換する動的レンダリングエンジン（Forgeの中核）
- `lib/features/_template_feature/` — 新機能追加用のひな形。新feature追加時はこのフォルダをコピーする
- `lib/shared_widgets/` — 複数featureで共有するUIパーツ

## 新しいfeatureを追加する手順
1. `lib/features/_template_feature/` を `lib/features/<feature_name>/` としてコピー
2. `domain` → `data` → `presentation` の順に実装（依存の向きを守る）
3. Riverpod providerを `presentation/providers/` に定義し、`core/di/` から参照させる
