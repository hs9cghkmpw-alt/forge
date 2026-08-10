# Mock Generator Contract(Python版 × Dart版)

FORGE-RUNTIME-002 Task 8。TECH_DEBT.md TD10(Python/Dart二重管理)を解消はしないが、
両者の出力が食い違わないよう、期待される構造をここに固定する。
どちらかを変更する場合は、必ずもう片方とこのドキュメントの3つを同時に更新すること。

---

## 1. Python版とDart版の差分(2026-07-11、機械比較で検証済み)

`backend/app/ai/generators/mock_generator.py` の `_CATEGORIES` と
`frontend/lib/features/app_generation/data/datasources/mock_generation_datasource.dart`
の `_kCategories` を、キーワード・タイトル・アイテムの3項目について
プログラムで突き合わせた。

**結果: 9カテゴリ全件、キーワード・タイトル・アイテムとも完全一致。差分は0件。**

(比較方法: Python側は`_CATEGORIES`を実際にimportして値を取得、Dart側は正規表現で
ソースから`MockCategory(...)`ブロックを抽出し、両者をフィールド単位で比較した。)

---

## 2. 9カテゴリの期待構造一覧

| # | 判定キーワード | タイトル | アイテム数 |
|---|---|---|---|
| 1 | 買い物, スーパー, 食材, shopping | 買い物メモ | 5 |
| 2 | todo, タスク, やること, 仕事 | Todo | 3 |
| 3 | ご飯, 晩ご飯, 夕食, 献立 | 今日のご飯メモ | 4 |
| 4 | 家計簿, 家計, 貯金, 支出 | 家計簿 | 4 |
| 5 | 予定, スケジュール, schedule | 今日の予定 | 3 |
| 6 | 子ども, こども, 子供 | 子どもの持ち物チェック | 5 |
| 7 | ペット, pet | ペットのお世話チェック | 4 |
| 8 | プレゼント, ギフト, gift | プレゼントのアイデア | 3 |
| 9 | 旅行, 持ち物, パッキング, 出張 | 旅行の持ち物チェック | 5 |

判定順序は上記の番号順(#6・#7が#9より先。「持ち物」キーワードによる
誤分類を避けるため。DECISIONS.md D10参照)。この順序を変更しないこと。

---

## 3. Widget type一覧(固定)

Runtimeの`ForgeWidgetRegistry.withBuiltins()`(`frontend/lib/json_ui/widget_registry/
widget_registry.dart`)が登録しているtypeと、Mock Generatorが出力するtypeは
以下の6種類に固定する。

```
text, text_field, button, column, row, checklist
```

Mock Generator(Python版・Dart版とも)が出力してよいのはこの6種類のみ。
新しいtypeを追加する場合は、Widget追加そのものがLanguage変更を伴うため、
別途の依頼として扱うこと(今回のFORGE-RUNTIME-002では追加していない)。

---

## 4. 必須props一覧(固定)

生成される文書の構造は以下で固定する(Forge Language v1のサブセット)。

```
{
  "version": "1.0",
  "app": { "title": string },
  "initial_screen_id": "generated_screen",
  "screens": [{
    "id": "generated_screen",
    "title": string,
    "state": {
      "new_item_text": { "type": "string", "value": "" },
      "items": { "type": "checklist", "value": [ChecklistItem, ...] }
    },
    "body": {
      "type": "column", "id": "root_column",
      "children": [
        { "type": "checklist", "id": "list_view", "state_ref": "items", "empty_state_text": "アイテムはまだないよ" },
        { "type": "row", "id": "add_row", "children": [
          { "type": "text_field", "id": "add_field", "state_ref": "new_item_text", "placeholder": "アイテムを追加" },
          { "type": "button", "id": "add_button", "label": "追加",
            "action": { "type": "add_item", "target_state_ref": "items", "source_state_ref": "new_item_text" } }
        ]}
      ]
    }
  }]
}
```

---

## 5. item ID規則(固定)

チェックリスト項目のIDは `item_{1始まりの連番}` とする(例: `item_1`, `item_2`, ...)。
この規則により、Mock Generatorが生成する範囲では項目ID重複は構造上発生しない
(連番が保証されるため)。ユーザーが`add_item`で追加する項目のIDは、
Runtime側(`ForgeRuntimeState.addChecklistItem`)がタイムスタンプベースで生成する
別方式であり、Mock Generatorの連番とは名前空間が異なる
(既知の制約はKNOWN_ISSUES.md参照)。

---

## 6. 今回発見した不一致

**無し。** 1章の機械比較により、現時点でPython版とDart版に差分が無いことを確認した。
