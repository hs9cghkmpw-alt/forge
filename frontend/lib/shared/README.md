# shared/

複数featureを横断して再利用される**UIを持たないコード**の置き場。

`core/` との違い: `core/`はアプリ基盤（DI・network等の"縦の土台"）、
`shared/`は業務寄りだが特定featureに属さない**横断的な値・ロジック**
（例: 複数featureで使う共通Entityの拡張、共通DTO変換ロジック）。
`shared_widgets/` との違い: `shared_widgets/`はUI（Widget）専用、
`shared/`はUIを持たないロジック専用。

- `models/` — feature横断で使う共有データモデル（domain entityではない、表示用DTO等）
- `extensions/` — 共通の拡張メソッド（例: `DateTime`, `String`の拡張）
- `utils/` — feature横断のヘルパー関数（`core/utils/`より一段業務寄り）

## 依存ルール
`shared/` は `core/` に依存してよいが、特定の `features/<x>/` には依存してはならない。
逆方向（featureがsharedを使う）は許可する。
