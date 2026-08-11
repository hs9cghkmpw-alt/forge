# ADR-014: Conversation Engine Wraps the Existing Cognitive Pipeline, Does Not Replace It

**Status:** Accepted（2026-08-11、FORGE-PRODUCT-VISION-002対応）
**Ref:** `docs/spec/FORGE_PRODUCT_VISION_002_CONVERSATIONAL_ARCHITECTURE.md`

## Context

CEOより、Forgeの製品思想を「アプリ生成AI」から「困りごとを話すと道具が
生まれるAI」へ更新する指示があった。中心的な新機能は、複数ターンの
会話を通じて要件を理解し、ASK(質問)かBUILD(生成)かを判断する
Conversation Engineである。

この新機能をどこに実装するかには、大きく2つの選択肢があった:

1. `forge_ai/core/orchestration/pipeline_orchestrator.py`(既存の
   Cognitive Pipeline)自体を拡張し、複数ターンの会話状態を内部で
   持たせる。
2. Cognitive Pipelineは一切変更せず、その手前に立つ薄い意思決定層
   (Conversation Engine)を`backend/app/ai/runtime/`配下に新設し、
   「聞くか、作るか」を決めた上で、作る場合は既存の`PromptPipeline.
   run()`(ひいては`run_cognitive_pipeline()`)を1回呼ぶだけに留める。

## Decision

**選択肢2を採用する。** Conversation EngineはCognitive Pipelineの
「外」に立つ。会話の各ターンで最大1回、`GeminiProvider.
complete_structured()`を直接呼び、構造化された`NeedModel`と
`next_action`(ASK/BUILD)を得る。BUILDと判定された場合のみ、会話全体を
要約した1つの自然文(`build_brief`)を、既存の`PromptPipeline.run()`へ
そのまま渡す。Cognitive Pipeline内部(Meaning/Intent/Domain分類/
Planner/Compiler/Validator/Repair/Critic)は一切変更しない。

## Alternatives

- **Cognitive Pipeline自体を会話対応に拡張する**: 却下。
  `run_cognitive_pipeline()`は「1回の自然文入力→1回のIR」という
  ステートレスな契約の上に、ADR-005(Decision Trace必須)・ADR-007
  (Confidence)・ADR-009(Facade分離)という複数のADRが積み上がって
  おり、この契約自体を「複数ターンの会話」へ拡張すると、影響範囲が
  Cognitive Pipeline全体(既に1000件超のPythonテストが依存する領域)
  に及ぶ。指示書26章「既存実装を大量に壊して一気に全面改修しない」
  という制約に反する。
- **Conversation EngineがForge Language・Widget知識を持ち、
  会話から直接Forge Documentを組み立てる**: 却下。Domain分類・
  Entity定義・Widget Registryとの整合性という、既にCognitive
  Pipelineが解決済みの問題を二重実装することになる。指示書20章
  「既存責務と統合できるなら新しいModuleを乱立させないこと」に反する。

## Consequences

- Conversation Engineは「聞くか作るか」の判断と、会話→自然文への
  要約(build_brief生成)という、狭い責務だけを持つ。Forge Language・
  Validator・Domain知識は一切持たない(既存資産の完全再利用)。
- 既存の`POST /api/v1/ai/generate`・`/generate/confirm`は無変更のまま
  併存する。新しい`POST /api/v1/ai/converse`は追加のみのエンドポイント
  であり、既存Frontendの動作に影響しない(後方互換)。
- 会話の質(NeedModelの精度、Question Policyの賢さ)は、Cognitive
  Pipeline側の改善とは独立してイテレートできる(責務分離の直接的な
  利益)。
- 逆に、Conversation EngineがCognitive Pipelineの内部状態(例:
  Ambiguity Report、Domain Classification)を活用したくなった場合、
  `build_brief`という1本の自然文を経由した**間接的な**受け渡ししか
  できない(Cognitive Pipeline内部の中間結果に直接アクセスできない)。
  これは意図的なトレードオフである——将来、会話の質を上げるために
  中間結果への直接アクセスが必要になった場合、改めてこのADRを
  見直す。

## Revisit Conditions

- Conversation Engineの`build_brief`要約だけでは、Cognitive
  Pipeline側のDomain分類・Ambiguity Detectionの精度が実運用で
  不足すると判明した場合(例: 会話で明確に伝えた情報が、要約の過程で
  失われ、Domain誤分類やneeds_confirmationの再発を招くケースが
  頻発する場合)。
- Forming Operation(UPDATE、`docs/spec/
  FORGE_PRODUCT_VISION_002_CONVERSATIONAL_ARCHITECTURE.md` B.4)を
  実装する段階で、既存Forge Documentの部分編集がCognitive Pipeline
  側の型(`ForgeIRDocument`等)と密接に絡む場合、責務境界の引き直しが
  必要になる可能性がある。
