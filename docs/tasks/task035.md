# Task035 — FORGE-MILESTONE-007 PREPARATION 実物監査(4回目)対応(8点修正、v1.3)

## 依頼内容
CEOが、Blueprintの前回7点修正(Legacy/Cognitive分離・M006認知順序・
Requirements入力・Preliminary/Final分離・Facade分離)を承認した上で、
Outcome生成API・依存注入API・段階数・Confidence計算・文書整合性に
実装ブロッカーが残っていると指摘し、以下8点の修正を求めた。新規
コードは追加しないこと。

1. Outcome Unionを実際に構築可能な形へ直す(Union aliasへのメソッド
   呼び出しを撤回)。
2. Success型と疑似コードを統一する(フィールド重複を解消)。
3. CognitiveDependenciesの注入契約を確定する(`**`展開を撤回)。
4. Cognitive Pipelineの段階数を正式確定する。
5. Domain confidence契約を安全化する。
6. 再計画時のPreliminary候補を扱う規則を確定する。
7. Error Outcomeの生成条件を明記する。
8. 文書を現在仕様へ完全統一する。

## 行ったこと
- `docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`をv1.3として全面
  書き直した。Task3.5でUnion aliasの誤用を修正し、`CognitivePipelineSuccess`
  を`context`・`ir`・`initial_quality`の3フィールドへ簡素化した。
- `CognitiveDependencies`を専用dataclassとして定義し、Orchestratorが
  単一引数として受け取る設計へ修正した。
- 段階数を「14 Transformation Stage + 1 Terminal Outcome + 3 M005
  Post-processing Stage」へ最終確定し、`FORGE_COGNITIVE_ARCHITECTURE_V2.md`
  ・`docs/diagrams/01_cognitive_pipeline.md`・`ADR-008`を一括更新した。
- `DomainClassification`に安全性条件(全0→Generic、同点→margin0)を
  追加し、confidence定義を2案比較の上で決定した。
- Preliminary/Final不一致時の再計画をCognitive Revisionへ一本化し、
  `docs/diagrams/07_template_selection_flow.md`も合わせて更新した。
- `NotImplementedError`の非捕捉を明記し、Provider障害がPlanning失敗へ
  誤分類されないことを保証した。
- Blueprint・報告書を全面書き直し、旧設計の記述を14章
  (Superseded Design History)へ集約した。
- Python全テスト(backend 265件・forge_ai 80件)を再実行し無影響を
  確認、`backend/app/ai/native/`・Flutterの無変更を確認した。

## 変更理由
本Taskは設計文書の修正であり、コードの「変更理由」に相当する記録は
無い。各修正の設計上の理由は、本体の該当節・ADR-008・ADR-009・
Blueprint14章に記録した。
