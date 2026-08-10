# Task025 — FORGE-MILESTONE-005: Backend AI Integration Adapter Contract

## 依頼内容
CEOが提示したロードマップ(M003.1完了→M004 Architecture Freeze完了→
M005 Backend AI Integration→M006 Forge AI Pipeline→M007 LLM Adapter→
M008 Repair Engine→M009 Quality Engine→M010 Native AIβ)に基づき、
M005実装の前段として「Adapter Contract」を固定することを依頼された。

具体的には、Adapter Contract・Shared Types(統合orAdapter変換の決定)・
Error Contract・Provider Contract・HTTP Contract・Validator Position・
Sequence Diagram(4種類)・ADR(理由・却下案・将来拡張)の8項目を
Architecture Decision Recordとしてまとめること。実装(コード追加)は
禁止され、設計のみが求められた。

## 行ったこと
`docs/spec/ADAPTER_CONTRACT_V1.md`を新規作成し、依頼された8項目全てを
文書化した。特に、forge_ai/(M004)とbackend/app/ai/foundation/
(M005が使用)の間で概念的に対応する5組の型を実際に比較し
(Intent/IntentIR、Plan・ScreenPlan/PlanIR・ScreenPlan、
ForgeIRDocument/dict、RepairResult/RepairResult、
QualityScore/CriticResult)、それぞれについて統合するかAdapterで
変換するかを理由付きで決定した。

設計の過程で、forge_ai.RepairEngineの内部リトライループとM005の
外側リトライループが組み合わさると最大4回の修復試行が発生する
「二重ループ問題」を発見し、対応方針を記録した(詳細はDECISIONS.md D59)。

## 変更理由
実装前に型・エラー・Provider・HTTP・Validator順序の契約を固定する
ことで、CEOの言う「後戻りがほぼ発生しない」M005実装を可能にする
ことを目的とした。新規コードは一切追加していない
(実装開始禁止の指示を厳守)。
