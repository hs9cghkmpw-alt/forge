"""AI Runtime — Repair(FORGE-MILESTONE-003 PHASE6/7/8)。

**責務定義のみ。実装は含まない。**

`RepairResult`は、既存の`RepairEngine`(foundation/interfaces.py)が
`dict[str, Any]`を直接返していたのに対し、Prompt Pipelineが「何件直せたか」
「あと何件残っているか」「最終的に成功したか」を型で判定できるようにするための
**新規追加**の構造化型である(既存に同名・同義の型が無いため、これは
`planner.py`/`critic.py`のような単純な再利用ではなく、正当な新規追加)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.ai.foundation.interfaces import RepairEngine as _ExistingRepairEngineProtocol  # noqa: F401 (関係性の明示用)
from app.ai.validators.schema_validator import ValidationResult


@dataclass(frozen=True)
class RepairResult:
    """Repair 1回分の結果。`RepairEngine.repair()`(foundation側、既存)が
    返す生の`dict`を、Prompt Pipelineが判定しやすい形へ構造化したもの。
    """

    document: dict[str, Any]
    attempt: int
    fixed_issue_count: int
    remaining_issue_count: int
    success: bool  # remaining_issue_count == 0 と同値だが、明示的に持たせる


class AIRepair(Protocol):
    """Validator不合格時に最小差分で修復する契約(PHASE7の要求名)。
    既存の`RepairEngine`(foundation/interfaces.py)と同じ入力(document/errors/attempt)
    を受け取るが、戻り値を`RepairResult`(構造化)にした点が異なる。
    """

    def repair(self, document: dict[str, Any], errors: ValidationResult, attempt: int) -> RepairResult:
        """documentとValidationResultから、構造化されたRepairResultを返す。
        共通指示書6.5節の方針(最大2回、JSON Patchに近い最小差分)を踏襲する。
        """
        ...


class StubAIRepair:
    """`AIRepair`の未実装スタブ。"""

    def repair(self, document: dict[str, Any], errors: ValidationResult, attempt: int) -> RepairResult:
        """未実装。"""
        raise NotImplementedError(
            "StubAIRepair.repair() は未実装です(FORGE-MILESTONE-003 PHASE6/7は"
            "責務定義のみ)。実装にはCEO承認(Native AI接続)が必要です。"
        )
