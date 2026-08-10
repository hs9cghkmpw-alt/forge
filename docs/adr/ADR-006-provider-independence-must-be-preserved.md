# ADR-006: Why Provider Independence Must Be Preserved

**Status:** Proposed（設計フェーズ、未実装）
**Ref:** FORGE-MILESTONE-006

## Context

Forgeプロジェクト共通指示書の一貫した原則(「Forgeは特定のChatGPT/
Claude/Geminiを前提にしない」)、および既存M004/M005実装(forge_ai/の
`AIProvider` Protocol、M005の`LLMAdapter`・`ProviderRouter`、5種の
Provider名+Mock)がこの原則を体現している。M006のCognitive Pipeline
設計でも、この原則を弱めないことを確認する必要があった。

## Decision

**OpenAI/Claude/Gemini/OSS/Mockのどれを利用しても、Forgeの基本設計
品質が大きく変わらない構造を維持する(2.5節)。** 具体的には:

1. LLMが関与する段階を、Rule Before Prompt(ADR-003)により最小化する。
2. LLM呼び出しは、既存の`Prompt`(forge_ai/)・`LLMAdapter`
   (`complete_structured(prompt: str, response_schema: dict) -> dict`、
   M005)という、特定ベンダーのSDK型に依存しない最小契約を維持する。
3. Design Critic(11章)の評価軸のうち、決定的チェック(Deterministic
   checks)で判定できるものを優先し、LLM semantic reviewは補助に留める。

## Alternatives

- **特定Providerの高度な機能(Function Calling、特定モデル専用の
  プロンプト最適化等)を前提にした設計にする**: 却下。特定Provider
  専用の最適化は、他Providerでの品質低下・Provider切替時の手戻りを
  招く。Mockのみでの動作(既存forge_ai/の80テスト・M005の246テストが
  Mockのみで実行できている実績)を維持できなくなる。
- **Provider非依存性をLLM呼び出し段階のみの制約とし、Critic・
  Confidence Model等の下流ロジックはLLM出力形式に強く依存してよい
  とする**: 却下。下流ロジックがLLM出力形式に依存すると、結局
  Provider切替時に下流も含めた広範な修正が必要になり、非依存性の
  実質的な効果が薄れる。

## Consequences

- LLM呼び出しのたびに、Provider固有の追加機能を活用する誘惑を
  実装時に断つ必要がある(コードレビュー上の継続的な注意点)。
- 一部のProviderが持つ高度な機能(例: 構造化出力の保証)を活用
  できないことによる、実装の複雑化(LLM応答のパース・検証を
  Forge側で担う必要がある)。

## Revisit Conditions

- 全ての主要Provider(OpenAI/Claude/Gemini/OSS)が収斂した共通の
  高度機能を持つに至った場合、その機能を「最小契約」に組み込むかを
  再検討する。
