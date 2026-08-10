# Forge Template Spec

FORGE-MILESTONE-002 PHASE4で正式導入した「Template」概念をまとめる。

---

## Template と Category の違い

- **Template**: 画面の構造(どのWidgetをどう組み合わせるか)を決める、
  再利用可能な生成関数。パラメータ(タイトル・項目リスト・質問リスト等)を
  受け取り、Forge Language JSONを返す。
- **Category**: 「どのTemplateを、どんなパラメータで呼ぶか」を決める判定ロジック。
  現状はキーワード判定(Mock Generator)。将来、本物のAI(Intent Planner /
  Product Planner)がこの役割を担う想定。

この分離により、新しいCategoryを追加する作業の多くは「既存Templateへ渡す
パラメータを増やす」だけで完結する(Template自体を毎回増やす必要がない)。
実例: FORGE-MILESTONE-002で追加した「家事」Categoryは、既存のChecklist
Templateへ新しいtitle/itemsを渡しただけで、Template自体は変更していない。

---

## 実装済みTemplate(3種)

### Checklist Template
- 場所: `backend/app/ai/generators/templates/checklist_template.py`(Python)、
  `frontend/lib/features/app_generation/data/datasources/templates.dart`(Dart)
- 構造: column → [checklist, row → [text_field, button(add_item)]]
- version: `1.0`(v1.0のWidgetのみで構成されるため)
- FORGE-MERGE-001以来の実績があり、出力構造は変更していない。

### Memo Template(新規)
- 構造: column → [heading, text_field]
- version: `1.1`(heading使用のため)
- チェックリストを持たない、最も単純な自由記述用テンプレート。

### Form Template(新規)
- 構造: 2画面。画面1 = column → [heading, card → [form → [質問Widget...]]]、
  画面2(送信後) = column → [heading, text, button(go_back)]
- version: `1.1`(form/checkbox/card/heading使用のため)
- 質問は`text`(text_field)または`checkbox`として指定できる。
- 初めて`navigate` Actionを実際に使うTemplate(送信 → 別画面遷移)。
- `card`で`form`を視覚的に囲む使い方を実演している。

---

## Category一覧(2026-07-11時点、計12)

`docs/spec/MOCK_GENERATOR_CONTRACT.md`の1〜2章に、キーワード・タイトル・
アイテムの詳細な一覧がある(Python/Dart間で機械比較済み)。

| Category | Template | 新規/既存 |
|---|---|---|
| 買い物・todo・ご飯・家計簿・予定・子ども・ペット・プレゼント・旅行 | Checklist | 既存(FORGE-MERGE-001) |
| 家事 | Checklist | **新規**(PHASE5) |
| アンケート(Survey) | Form | **新規**(PHASE4/5) |
| メモ(Memo) | Memo | **新規**(PHASE4/5) |

---

## 新しいCategoryを追加する手順

1. 既存Templateのどれかで表現できないか検討する(多くの場合、Checklistで足りる)。
2. 表現できる場合: Python(`mock_generator.py`の`_CATEGORIES`)とDart
   (`mock_generation_datasource.dart`の`_kCategories`)の両方へ、
   同じキーワード・同じパラメータでエントリを追加する。
3. 表現できない場合のみ、新しいTemplateを追加する(`templates/`配下)。
4. 追加後、`docs/spec/MOCK_GENERATOR_CONTRACT.md`を更新し、Python/Dart間の
   機械比較を再実行する(TECH_DEBT.md TD10)。
5. キーワードの判定順序に注意する: より具体的なキーワードを、より汎用的な
   キーワード(例:「メモ」)より前に置く(DECISIONS.md D10の衝突回避と同じ考え方)。
