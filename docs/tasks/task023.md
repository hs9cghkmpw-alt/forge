# Task023 — Forge AI Architecture v1.0 (Architecture Freeze)

## 依頼内容
CEOレビューにより、前回のFORGE-MILESTONE-004提出(forge_ai/の検証・
採用)が「マイルストーン管理」の観点で問題があると指摘された。
具体的には「FORGE-MILESTONE-004」という名前が、forge_ai/と
「Native AI Phase-1」という2つの異なる内容に使われていたこと。

CEOから以下の指示を受けた。「M004を実装マイルストーンではなく、
Architecture Freezeマイルストーンとして整理してください。forge_ai・
backend/app/ai/runtime・backend/app/ai/nativeの責務境界を明文化し、
今後どこに何を実装するかをArchitecture Decision Recordとして固定して
ください。また、『FORGE-MILESTONE-004』の番号重複を解消し、時系列・
責務・依存関係を一枚で理解できるアーキテクチャ図を作成してください。」

また、次の3点への回答も求められた。
1. forge_ai/はいつ作られたのか、どの依頼に対応しているのか(時系列)。
2. Native AIとの責務境界図。
3. User → forge_ai → backend runtime → Forge Runtime の接続図。

## 行ったこと
- `docs/spec/FORGE_AI_ARCHITECTURE_V1.md`(新規、ADR)を作成し、
  M004=forge_ai/、M005=backend/app/ai/runtime/(旧Native AI Phase-1)、
  M006以降=backend/app/ai/native/(Experimental)という番号整理を確定した。
- 実際のファイルタイムスタンプを調査し、時系列を実証的に再構成した
  (推測ではなく`ls -la --time-style=full-iso`の実行結果に基づく)。
- 責務境界図・接続図を作成した(現状は全区間未接続であることを明記)。
- `backend/app/ai/runtime/README.md`・`backend/app/ai/native/README.md`・
  `docs/spec/NATIVE_AI_STATUS_NOTE.md`・`forge_ai/docs/DESIGN_DECISIONS.md`
  (D7)を更新した。
- 過去の記録(CHANGELOG Task019・DECISIONS D50〜D55・TECH_DEBT
  TD20〜TD22・旧報告書)は書き換えず、本ADRを正典として参照する
  運用へ変更した。

## 変更理由
CEOの指摘通り、前回の提出は「新規コード無し」であるにもかかわらず
「M004提出」と称していた点が不正確だった。今回は実装ではなく
設計文書(ADR)の作成であることを明確にし、そのように報告する。
