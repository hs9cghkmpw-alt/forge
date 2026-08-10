# plugins/

Forge本体を拡張するサードパーティ/内製プラグインの「差し込み口」。
Plugin自体の実装はここに置かず、Pluginを**受け入れるための契約**のみを置く。

- `interfaces/` — Pluginが実装すべき抽象クラス/契約（例: `ForgeWidgetPlugin`）
- `registry/` — 実行時にPluginを登録・解決するレジストリ（`json_ui/widget_registry/`と連携）

## 設計方針
- `json_ui/widget_registry/` は組み込みWidgetの解決を担当し、
  `plugins/registry/` は**外部から追加されたWidget/振る舞い**の解決を担当する。
  両者を分離することで、コア機能とプラグイン機能の境界を明確にする。
- 現フェーズでは契約の型のみ定義し、実際のPlugin読み込み機構は実装しない。
