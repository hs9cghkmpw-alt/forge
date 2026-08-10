# ADR-004: Why Cognitive Revision Is Separate From Schema Repair

**Status:** Proposed（設計フェーズ、未実装）
**Ref:** FORGE-MILESTONE-006

## Context

M004/M005には既に「Schema Repair」(`forge_ai.repair.repair_engine.
RepairEngine`、Validator不合格時にJSONを修正するループ)が存在する。
M006では新たに「Design Critic」による設計品質評価と、それに基づく
「Self-Revision Loop」(12章)を導入する。両者は「何かを繰り返し直す」
という表面上の類似性があり、混同・統合のリスクがあった。

## Decision

**Cognitive RevisionとSchema Repairを、明確に別のループとして設計する
(混同しない)。**

| | Cognitive Revision | Schema Repair |
|---|---|---|
| 対象 | `ApplicationPlan`(IR化前) | Forge IR(JSON化後) |
| 基準 | 設計として良いか(Design Critic) | 仕様上正しいか(Validator) |
| 実行順序 | Forge IR Compilationより前 | Forge IR Compilationより後 |
| カウンタ | 独立(12.4節) | 独立(既存M005のまま) |

## Alternatives

- **単一の「修正ループ」として統合する**: 却下。対象(Plan vs IR)も
  評価基準(設計品質 vs 仕様適合性)も異なるものを1つのループに
  統合すると、「今何を直そうとしているか」の説明可能性(2.4節)が
  下がる。また、既存M005で発見した「Repair二重ループ問題」
  (`docs/DECISIONS.md` D59)と同種の実装ミス(片方のループが
  もう片方の内部リトライと掛け合わさり、想定以上の試行回数になる)
  を、統合によってかえって誘発しやすくなると判断した。
- **Cognitive RevisionをSchema Repairの前段階として、同じ
  `RepairEngine`クラスへ機能追加する**: 却下。`RepairEngine`は
  `ForgeIRDocument`(IR型)を扱う設計であり、`ApplicationPlan`
  (Plan型)を扱わせるには型境界を壊す必要がある。M005 Adapter
  Contract策定時に確立した「型を無理に統合しない」原則
  (`ADAPTER_CONTRACT_V1.md` 2章)と一貫させる。

## Consequences

- 実装時、2つの独立したループ・カウンタ・上限値を管理する必要がある
  (実装コストは統合より高いが、既存M005の教訓を踏まえた必要なコスト)。
- テスト設計上も、Cognitive RevisionとSchema Repairそれぞれについて
  独立した「上限到達で停止する」契約テストが必要になる(17.12節)。

## Revisit Conditions

- 実装後、2つのループの責務が実運用上ほとんど重複すると判明した場合
  (現時点ではDesign CriticとValidatorの評価対象が明確に異なるため、
  この可能性は低いと考える)。
