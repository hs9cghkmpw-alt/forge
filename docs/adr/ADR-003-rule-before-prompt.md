# ADR-003: Why Rule Before Prompt

**Status:** Proposed（設計フェーズ、未実装）
**Ref:** FORGE-MILESTONE-006

## Context

Cognitive Pipelineの各段階(3章)で、LLMにどこまで判断を委ねるかを
決める必要があった。全段階をLLMに任せれば実装は単純だが、既存の
共通指示書・forge_ai/の設計原則(Provider非依存、決定的なValidator、
Mockのみでのテスト容易性)と衝突する。

## Decision

**決定的なルール・Domain Knowledge・Validatorで判断できることは、
LLMへ委譲しない。** LLMは「曖昧さの解消」「候補生成」「補助推論」に
限定する(2.2節)。13章で全16段階をDeterministic/Hybrid/LLM-Assistedに
分類し、Hybrid段階でも「まずRuleでスコアリング・判定し、僅差・
不確実な場合のみLLMを補助的に使う」という順序を統一した。

## Alternatives

- **LLM-First(まずLLMに任せ、Ruleで後検証する)**: 却下。この順序では
  LLMの出力にRuleが「追従」する形になり、Provider間の品質差がそのまま
  最終結果に反映されやすい。Design Critic(11章)がLLM出力を後から
  評価する構造そのものはLLM-Firstに近いが、これは意図的に「Critic」
  という独立した検証段階として設計しており、Planningの主経路
  (Rule-basedスコアリングが第一)とは区別している。
- **段階ごとの分類を設けず、実装時の裁量に任せる**: 却下。
  Provider非依存性・コスト・説明可能性を担保するには、どの段階で
  LLMを呼ぶかを設計時点で明文化し、実装のブレを防ぐ必要がある
  (13章の表がこの明文化にあたる)。

## Consequences

- 各段階でRuleとLLMの境界を明確にコード上でも分離する実装規律が
  求められる(実装時、「ついでにLLMへ全部渡す」という近道を取らない
  ことが、レビュー時の重点確認事項になる)。
- Rule部分(Domain Registry・Template評価基準等)の初期構築・継続的な
  拡充コストが発生する。

## Revisit Conditions

- 特定段階で、Ruleによる判定精度がLLMに大きく劣ると実運用データで
  判明した場合、その段階に限定してLLMの比重を見直す(全段階一律の
  変更ではなく、段階ごとの個別見直しとする)。
