# ADR-001: Why Hybrid Cognitive Architecture

**Status:** Proposed（設計フェーズ、未実装）
**Ref:** FORGE-MILESTONE-006

## Context

Forge AIをどのアーキテクチャ方式で構築するかを決定する必要があった。
`docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md` 20章で、Rule-Based中心
(Option A)・LLM中心(Option B)・Hybrid(Option C)を10軸で比較した。

既存のforge_ai/(M004)は既にRule-Based中心の実装(Domain Registry、
決定的なWorld/Meaning/Planner/Compilerロジック、`MockProvider`のみで
80テストが動作)であり、ゼロからの選択ではなく既存資産を前提にした判断
だった。

## Decision

**Hybrid Cognitive Architecture(Option C)を採用する。**

決定的なルール・Domain Knowledge・Validatorで判断できることは
すべてRuleで処理し、LLMは曖昧さの解消・候補生成・補助推論という
限定的な役割のみを担う(「Rule Before Prompt」、ADR-003)。

## Alternatives

- **Option A(Rule-Based中心)**: 却下はしない(部分的に採用、Hybridの
  Rule部分がこれに相当)。単独では「未知パターンに弱い」「日本語以外の
  自由記述への対応が手動整備に依存する」という限界がある。
- **Option B(LLM中心)**: 却下。コスト・速度・説明可能性・Provider依存の
  いずれの軸でも劣り、特に「Forgeの基本設計品質がProviderに依存しない」
  という既存の最重要原則(共通指示書)と相容れない。

## Consequences

- Rule部分(Domain Registry・Template評価基準・Critic構造チェック等)の
  実装・保守コストは残る(LLM中心なら不要だったコスト)。
- LLM呼び出しが必要な箇所を明確に線引きする設計・実装規律が今後も
  要求される(境界が曖昧になると徐々にLLM依存が拡大するリスクがある)。
- Provider非依存性・オフライン対応(Mockのみでの動作)を、実装フェーズでも
  継続的にテストで担保する必要がある。

## Revisit Conditions

- 実際の運用で、Rule部分のメンテナンスコストがLLM呼び出しコストを
  大幅に上回ると判明した場合。
- 特定のProviderが極めて低コスト・高精度になり、Provider非依存性を
  多少犠牲にしてもLLM中心へ倒す方が合理的というビジネス判断が
  CEOから示された場合。
