# Forge Language Spec

`shared/schemas/`配下のJSON Schemaファイルが正式な定義(このドキュメントは
それを人間が読みやすくまとめた副次的な参照)。矛盾があればSchemaファイルを正とする。

- v1.0: `ui_schema.v1.json`(凍結。docs/spec/LANGUAGE_FREEZE.md参照)
- v1.1: `ui_schema.v1.1.json`(FORGE-MILESTONE-002 PHASE1で追加)

---

## バージョニング方針

`docs/spec/LANGUAGE_FREEZE.md`を参照。要点: v1.0は6 Widgetのまま凍結し、
v1.1は6 Widgetを追加した(Minorバンプ、後方互換)。**文書のversionフィールドは
「その文書が実際に必要とする最小バージョン」を表す**。v1.0の6種だけで
組み立てられる文書は、v1.1環境で生成されたものでも`"version": "1.0"`と
申告してよい(実際、Checklist Templateはこの原則に従い`1.0`を返す)。

---

## Widget一覧(v1.1時点、計12種)

### v1.0由来(凍結・変更しない)

| type | 必須props | 補足 |
|---|---|---|
| `text` | `value` | `state_ref`があれば表示内容をStateから取る |
| `text_field` | `state_ref` | `placeholder`は任意 |
| `button` | `label`, `action` | |
| `column` | `children` | 最大60件 |
| `row` | `children` | 最大20件 |
| `checklist` | `state_ref` | チェック状態を持つ項目リスト。トグル/削除はWidget組み込み挙動(Action化しない。DECISIONS.md D3) |

### v1.1新規(FORGE-MILESTONE-002 PHASE1)

| type | 必須props | 補足 |
|---|---|---|
| `heading` | `value` | `level`(1 or 2、既定1)。画面内の構造的な見出し |
| `checkbox` | `label`, `state_ref` | boolean stateへの単一ON/OFF。トグルはWidget組み込み挙動(checklistと同じ設計方針) |
| `card` | `children`(1件以上) | 視覚的にまとまった塊。構造はcolumnと同じ |
| `list` | `state_ref` | string_list型stateの読み取り専用箇条書き(TECH_DEBT.md TD7を解消) |
| `divider` | (なし) | 区切り線。最も単純なWidget |
| `form` | `children`(1件以上), `submit_label`, `submit_action` | 入力Widgetを束ね、1つの送信操作に集約する |

---

## Action一覧(4種、v1.0から追加なし)

`navigate` / `go_back` / `set_value` / `add_item`。v1.1でも新しいAction typeは
追加していない(`form.submit_action`も既存4種のいずれかを使う。多くの場合`navigate`)。

**Widget組み込み挙動として扱い、Action化していないもの**:
`checklist`のトグル・削除、`checkbox`のトグル。理由はDECISIONS.md D3参照
(実行時にしか決まらない対象(どの項目がタップされたか)をAIが静的に
書けないため)。

---

## State型一覧(4種、v1.0から追加なし)

`string` / `boolean` / `string_list` / `checklist`。v1.1で新設した`list`
Widgetにより、`string_list`型が初めて表示可能になった(それまではTECH_DEBT.md
TD7の通り宣言だけできて表示手段が無かった)。

---

## Template一覧(FORGE-MILESTONE-002 PHASE4)

「Template」は画面の構造を決める再利用可能な生成ロジック、「Category」は
「どのTemplateを、どんなパラメータで呼ぶか」を決める判定ロジック
(自然言語のキーワード判定、将来的には本物のAIのIntent Planner/Product Planner
が担う部分)。詳細はdocs/spec/TEMPLATE_SPEC.md参照。

| Template | 使用Widget | version | 対応Category(2026-07-11時点) |
|---|---|---|---|
| Checklist | column/checklist/row/text_field/button | 1.0 | 買い物・todo・ご飯・家計簿・予定・子ども・ペット・プレゼント・家事・旅行 |
| Memo | column/heading/text_field | 1.1 | メモ |
| Form | column/heading/card/form/checkbox/text_field/button/text | 1.1 | アンケート(Survey) |

---

## 既知の未解決事項

- `docs/DECISIONS.md` D4: 差分編集方式(JSON Patch等)は今回も決定していない
  (今回は新規生成のみで、既存文書の編集は縦の一本のスコープ外のため)。
- Card Widgetは今のところForm Template内でのみ実際に使われている(独立した
  Categoryとしての明確な自然表現が見つからなかったため。将来的な拡張点)。
