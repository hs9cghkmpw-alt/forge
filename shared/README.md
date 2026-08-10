# shared/

Frontend/Backend双方が参照する、単一の真実源（Single Source of Truth）。

- `schemas/` — JSON UI SchemaのJSON Schema定義。AIの出力形式・Flutterの解釈対象の契約
- `constants/` — 両者で共有すべき定数（例: JSON Schemaのversion文字列など）

ここを変更する場合は、Frontend/Backend双方への影響を`docs/ARCHITECTURE.md`で確認すること。
