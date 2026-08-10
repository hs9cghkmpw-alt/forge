# plugins/

Forge本体を拡張するプラグインを**受け入れるための契約**の置き場。
Plugin自体の実装コードはここに置かない（Frontend `lib/plugins/` と対称の設計）。

- `interfaces/` — Pluginが実装すべき抽象基底クラス（例: `ForgeBackendPlugin`）
- `registry/` — 実行時にPluginを登録・解決するレジストリ
- `sandbox/` — Pluginを安全に実行するためのサンドボックス境界（将来、任意コード実行を許可する場合の隔離層）

## 設計方針

- Pluginは `domain/repositories` や `ai/` の公開インターフェースを通じてのみForge内部にアクセスできる。
  `domain/entities` やDBへの直接アクセスは許可しない。
- 現フェーズでは契約の型のみを定義し、実際のPlugin読み込み機構・サンドボックス実行は実装しない。
