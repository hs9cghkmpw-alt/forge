# ADR-002: Why Domain Before UI

**Status:** Proposed（設計フェーズ、未実装）
**Ref:** FORGE-MILESTONE-006

## Context

Forgeが自然言語からアプリを設計する際、「まず画面を考える」か「まず
対象領域(Domain)・世界(World)・意味(Meaning)を理解してから画面を
考える」かという、設計順序の選択があった。既存のforge_ai/(M004)は
既に`Domain → World → Meaning → Intent → Planner → Compiler`という
順序を実装しており(D1〜D7で確定済み)、本Milestoneはこの順序を前提に
Cognitive Pipeline(3章)を設計した。

## Decision

**Domain/World/Meaningの理解を、画面構成の検討より必ず先に行う
(Meaning Before UI、2.3節)。** World Modelは画面・Widget・ボタンという
概念を一切知らない設計とする(6章)。

## Alternatives

- **UI-First(先に画面候補を出し、後からデータモデルを補う)**: 却下。
  この順序では「なぜこの画面が必要か」という説明可能性(2.4節)が
  弱くなり、Template選択(10章)がDominant user action等の意味的な
  評価基準ではなく、表層的なキーワードマッチに寄ってしまうリスクが
  ある。Mock Generator(既存のキーワードマッチ方式)がまさにこの
  UI-First的な設計であり、それをAI Coreでも繰り返さないための
  意図的な差別化でもある。
- **World ModelにUI関連情報(推奨Widget等)を混在させる**: 却下。
  World Modelの再利用性(同じWorldから複数のTemplate候補を評価できる、
  10章)を損なうため、World ModelとTemplate Selectionの責務を分離した。

## Consequences

- World Model構築(6章)とTemplate Selection(10章)の間に、Meaning
  Model・Requirement Extraction・Application Planningという複数の
  中間段階が必要になり、パイプラインが長くなる(3章の16段階)。
- 各段階の契約(入力/出力)を明確に定義する必要があり、設計コストは
  UI-Firstより高い(本ドキュメント自体がそのコストの一部)。
- 既存forge_ai/の`World`型(Actor/WorldObject/Relationship/Ruleの
  4フィールド)を、Events/States/Permissionsを含む8フィールドへ拡張する
  必要が生じる(6.1節)。これは後方互換な追加として実装可能(既存の
  `IntentIR`/`PlanIR`拡張と同じ手法)。

## Revisit Conditions

- Domain/World/Meaningの分離が、実装・保守コストに対して十分な
  説明可能性・品質向上をもたらしていないと、実装後の計測で判明した場合。
