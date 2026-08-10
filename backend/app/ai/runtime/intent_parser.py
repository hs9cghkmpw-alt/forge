"""AI Runtime — Intent Parser(FORGE-MILESTONE-004 PHASE1/2)。

**責務定義のみ。実装は含まない。**

## なぜ`AIPlanner.interpret()`(既存、runtime/planner.py)と別に定義したか

`runtime/planner.py`の`AIPlanner`は、「自然言語→Intent」と「Intent→Plan」の
2段階を1つのProtocolにまとめていた(FORGE-MILESTONE-003 D44の判断)。
今回のPHASE1〜PHASE3は、この2段階をそれぞれ独立した設計対象として
明示的に要求している(Intent IR設計 → IntentParser → Planner、と3段階に
分けて記述されている)。

そのため、「自然言語→Intent」だけを担当する`IntentParser`を新たに定義した。
`AIPlanner`は削除・変更していない(既存21件のテストが依存しているため。
後方互換性を維持する)。将来的な実装方針としては、`AIPlanner.interpret()`が
内部で`IntentParser`へ委譲する形にすることを想定しているが、今回はどちらも
Stubのため、委譲関係自体は実装していない(Stub同士を接続しても意味が
無いため。実装フェーズでの検討事項として`docs/spec/AI_RUNTIME.md`へ記録する)。
"""

from __future__ import annotations

from typing import Protocol

from app.ai.foundation.interfaces import IntentIR


class IntentParser(Protocol):
    """自然言語からIntentIRを抽出する契約。UI Schemaは生成しない
    (`AIPlanner.interpret()`と同じ制約)。"""

    def parse(self, natural_language_input: str, conversation_history: tuple[str, ...]) -> IntentIR:
        """natural_language_inputとconversation_historyから、構造化された
        IntentIRを返す。実装はLLM Provider(将来のNative AI含む)へ委譲する
        想定だが、このProtocol自体はProviderの種類を一切知らない。"""
        ...


class StubIntentParser:
    """`IntentParser`の未実装スタブ。呼ばれると`NotImplementedError`を送出する。"""

    def parse(self, natural_language_input: str, conversation_history: tuple[str, ...]) -> IntentIR:
        """未実装。"""
        raise NotImplementedError(
            "StubIntentParser.parse() は未実装です(FORGE-MILESTONE-004 PHASE1/2は"
            "責務定義のみ)。実装にはCEO承認(Native AI接続)が必要です。"
        )
