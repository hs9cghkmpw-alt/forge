# core/

全featureが依存してよい唯一のインフラ層。逆に、ここは `features/` や
`plugins/` に依存してはならない（依存は常に内向き）。

- `di/` — Riverpodによる依存性注入の集約ポイント
- `theme/` — Material3テーマ定義
- `constants/` — アプリ全体の定数
- `network/` — Dioクライアント等のHTTP基盤
- `error/` — 共通例外・Failureモデル
- `utils/` — 汎用ユーティリティ関数
