"""AI Runtime — Planner(FORGE-MILESTONE-003 "Analyzer Zero → Native AI Foundation" PHASE6/7/8)。

**重要: このモジュールは責務定義のみ。実装は含まない。**
`AIPlanner`は Protocol であり、具体的な推論ロジック(LLM呼び出し等)は
一切含まない(禁止事項「AI実装したふり」を避けるため、メソッド本体は
存在しないか、呼ばれたら`NotImplementedError`を投げるスタブのみ)。

## `backend/app/ai/foundation/` との関係(重要な設計判断)

このファイル(および`runtime/`配下の他ファイル)は、FORGE-MILESTONE-002で
既に実装済みの`backend/app/ai/foundation/interfaces.py`と概念的に重複する。
具体的には:

| 今回(runtime/) | 既存(foundation/) | 関係 |
|---|---|---|
| `Intent` | `IntentIR` | **同一の型をエイリアスとして再利用**(重複定義しない) |
| `Plan` | `PlanIR` | **同一の型をエイリアスとして再利用** |
| `AIPlanner` | `IntentPlanner` + `ProductPlanner` | 2段階を1つのProtocolへ統合 |

**なぜ複製せず再利用したか**: 「実装中に新しい概念を追加しないこと」
(前回のforge_ai/キックオフ指示書14章と同じ精神)に従い、既存の
`IntentIR`/`PlanIR`という、型として全く同じ責務を持つものを2重に
定義することは、将来の保守性を損なう(どちらが正なのか分からなくなる)と
判断した。詳細は`docs/DECISIONS.md`および`docs/spec/AI_RUNTIME.md`を参照。
"""

from __future__ import annotations

from typing import Protocol

from app.ai.foundation.interfaces import IntentIR, PlanIR

# PHASE8の要求する名前(`Intent`/`Plan`)を、既存のIntentIR/PlanIRの
# 型エイリアスとして提供する(定義の重複を避ける)。
Intent = IntentIR
Plan = PlanIR


class AIPlanner(Protocol):
    """自然言語からIntentへ、IntentからPlanへ、という2段階を1つの契約にまとめた
    Protocol(PHASE7の要求名)。既存の`IntentPlanner`+`ProductPlanner`
    (foundation/interfaces.py)を、Prompt Pipelineから見た「1つの窓口」として
    再定義したもの。

    実装クラスは、内部で`IntentPlanner`/`ProductPlanner`の実装へ委譲してもよいし、
    1つのLLM呼び出しで両方を一度に行ってもよい(実装の自由度は実装側に委ねる。
    これがProtocolを分離する意義である)。
    """

    def interpret(self, natural_language_input: str, conversation_history: tuple[str, ...]) -> Intent:
        """自然言語からIntentを抽出する。UI Schemaは生成しない。"""
        ...

    def plan(self, intent: Intent, available_templates: tuple[str, ...]) -> Plan:
        """IntentからPlanを設計する。Forge Widget語彙は一切含まない
        (Runtimeを知らない。forge_ai/core/planner.pyと同じ原則)。"""
        ...


class StubAIPlanner:
    """`AIPlanner`の未実装スタブ。呼ばれると`NotImplementedError`を投げる
    (PHASE7「実装は禁止。NotImplementedErrorで構いません」に対応)。"""

    def interpret(self, natural_language_input: str, conversation_history: tuple[str, ...]) -> Intent:
        """未実装。"""
        raise NotImplementedError(
            "StubAIPlanner.interpret() は未実装です(FORGE-MILESTONE-003 PHASE6/7は"
            "責務定義のみ)。実装にはCEO承認(Native AI接続)が必要です。"
        )

    def plan(self, intent: Intent, available_templates: tuple[str, ...]) -> Plan:
        """未実装。"""
        raise NotImplementedError(
            "StubAIPlanner.plan() は未実装です(FORGE-MILESTONE-003 PHASE6/7は"
            "責務定義のみ)。実装にはCEO承認(Native AI接続)が必要です。"
        )
