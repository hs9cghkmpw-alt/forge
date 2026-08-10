# ADR-005: Why Decision Trace Is Required

**Status:** Proposed（設計フェーズ、未実装）
**Ref:** FORGE-MILESTONE-006

## Context

Forge AIが「なぜこの設計を選んだか」を説明できない場合、CEO・利用者
双方がForgeの判断を信頼・検証できず、Human Override(2.6節、Forgeの
判断は提案であり最終決定は利用者にある)という原則も実効性を持たない。
既存M005 Adapter Contractは`diagnostics`(intent_ir/plan_ir/
conversion_warnings)という形で部分的な説明情報を既に持っている。

## Decision

**全16段階(3章)の重要な判断について、`DecisionTrace`(15章)という
統一構造で理由・根拠・却下した代替案・confidenceを記録することを
必須とする。**

## Alternatives

- **ログ出力(自由形式のテキストログ)に留める**: 却下。自由形式では
  「なぜCheckListではなくFormを選んだか」といった特定の問いに
  機械的に答えられない(検索・集計・UI表示への転用が困難)。
- **最終結果(Application PlanやForge IR)だけを保持し、途中経過は
  破棄する**: 却下。Failure Mode分析(17章)の多くが「どの段階で
  何が起きたか」の追跡を前提にしており、途中経過が無いと原因分析が
  著しく困難になる。また、Learning-Ready Design(16章)が将来
  蓄積を想定するデータの多くもDecision Traceの情報と重なる。

## Consequences

- 各段階の実装が、判断結果だけでなく`reason`・`evidence`・
  `alternatives`も返す設計になる必要があり、各段階の出力型
  (3章の各表)がやや複雑になる。
- Decision Traceの蓄積量が多くなりうる(16段階×複数の判断)。
  実装時、HTTPレスポンスへ含める範囲(既存`diagnostics`相当)と、
  内部ログにのみ残す範囲を分ける設計判断が必要になる(本ドキュメントの
  スコープ外、実装時に決定)。

## Revisit Conditions

- Decision Traceの記録コスト(実装・保守・データ量)が、実際の
  説明可能性向上の価値に見合わないと運用後に判明した場合、記録範囲を
  縮小する(例: blocking issueに関わる判断のみ記録する等)。
