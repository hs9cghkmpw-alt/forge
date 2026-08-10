# Task019 — FORGE-MILESTONE-004: Native AI Phase-1（Intent Engine）

## 依頼内容
Forge Native AIの土台(Intent IR設計・IntentParser・Planner・Template
Engine・Template Selector・Language Generator Interface・Repair Loop・
Provider Router・AI Runtime bundle)を、PHASE1〜9として構築することを
依頼された。全てProtocol/Stub定義のみで、AI推論の実装は禁止されている。
14観点以上のArchitecture Reviewも合わせて依頼された。

## 行った変更
既存の`backend/app/ai/foundation/`(FORGE-MILESTONE-002)・
`backend/app/ai/runtime/`(FORGE-MILESTONE-003)を実際に読み直し、
今回の9 PHASEのうち何が既に存在し、何が真に新規かを判断した上で:
- 既存: PHASE3(Planner)・PHASE6(LanguageGenerator)・PHASE7(Repair Loop)は
  既存コンポーネントがそのまま満たしていると判断し、新規実装を追加せず、
  ドキュメントでの対応関係の明記のみ行った。
- 拡張: PHASE1(Intent IR)は既存`IntentIR`の拡張、PHASE8(Provider Router)は
  既存`ProviderRouter`へのエイリアス追加とした。
- 新規: PHASE2(IntentParser)・PHASE4(Template Engine)・PHASE5(Template
  Selector)・PHASE9(NativeAIRuntime bundle)は新規追加した。

## 変更理由
既存資産(foundation/・runtime/)との重複を避けることを最優先した
(DECISIONS.md D50〜D54)。「5年後でも破綻しないアーキテクチャ」という
今回の目的に対し、類似概念の型を複数並立させることは、将来の保守性を
損なうと判断したため。
