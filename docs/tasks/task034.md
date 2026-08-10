# Task034 — FORGE-MILESTONE-007 PREPARATION 実物監査(3回目)対応(7点修正)

## 依頼内容
CEOが、M007 Implementation Blueprintの前回4点修正(Facade分離・
Outcome3型Union・Quality責務・Error mapping)を承認した上で、M006
Cognitive Architectureと既存M004 Legacy Protocolの不一致を、既存
Protocolへ無理に合わせる形(実行順序をLegacyに合わせて変更する等)で
解決していたことを指摘し、M007実装開始の承認を保留した。以下7点の
文書修正を求めた。新規コードは追加しないこと。

1. Legacy ProtocolとCognitive Protocolの分離。
2. M006の認知順序(Intentが最初)を維持する。
3. RequirementsをPlannerへ必ず渡す契約にする。
4. Preliminary/Final Template Selectionを実行フローへ明示する。
5. DomainClassificationを実際に算出する契約にする。
6. World ModelへIntentを反映する。
7. 文書を最終状態へ統一する(古い記載の削除・訂正)。

## 行ったこと
- Task4を全面書き換えし、Legacy Protocol(既存、無変更)と、CEO提示の
  シグネチャに基づくCognitive Protocol(新規)を分離した。
- Task3.3の疑似コードを、M006が指定する認知順序(Input Normalization
  →Ambiguity Detection→Cognitive Intent Recognition→Domain
  Classification→World Model Construction→Meaning Model→
  Requirement Extraction→Preliminary Pattern Candidates→Application
  Planning→Final Template Selection→Design Critic→Cognitive
  Revision→Human Confirmation/Escalation→Forge IR Compilation→
  Initial Quality Evaluation)へ正確に合わせて書き直した。
- `CognitivePlannerProtocol.plan()`にrequirementsを必須引数として追加。
- Preliminary Pattern Candidatesを独立した明示的な呼び出しへ変更し、
  ADR-008・`docs/diagrams/01_cognitive_pipeline.md`・
  `07_template_selection_flow.md`を、独立ノードとして描き直した。
- `DomainClassification`を、Intentと各Domainの実際の一致度に基づく
  スコアリング契約(`score_margin`を含む)へ全面書き換えた。
- `CognitiveWorldBuilderProtocol`をDomainとIntentの両方から構築する
  契約へ変更した。
- Boolean Feature Flag・「provider_error等」・「Thin Wrapper化」・
  ディレクトリ数(7→6)等、指摘された古い記載を本文から削除・訂正した。
- Preliminary Pattern Candidatesの独立ノード化に伴い、M004側の段階数が
  13→14へ増え、M006本体の「全16段階」という記載との新たな不一致を
  発見し、CEO確認事項として提示した。
- Python全テスト(backend 265件・forge_ai 80件)を再実行し無影響を
  確認、`backend/app/ai/native/`・Flutterの無変更を確認した。

## 変更理由
本Taskは設計文書の修正であり、コードの「変更理由」に相当する記録は
無い。各修正の設計上の理由は、本体の該当節およびADR-008の追記に
記録した。
