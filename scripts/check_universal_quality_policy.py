#!/usr/bin/env python3
"""Fail when canonical Forge docs reintroduce hardware-dependent quality tiers."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"missing required policy file: {relative}")
    return path.read_text(encoding="utf-8")


def require(relative: str, *phrases: str) -> None:
    content = read(relative)
    for phrase in phrases:
        if phrase not in content:
            raise AssertionError(f"{relative}: missing invariant: {phrase}")


def reject(relative: str, pattern: str, explanation: str) -> None:
    content = read(relative)
    if re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE):
        raise AssertionError(f"{relative}: {explanation}")


def main() -> int:
    require(
        "docs/architecture/FORGE-UNIVERSAL-QUALITY-INVARIANT.md",
        "全員へ同じ高品質基準",
        "同じProduct Quality Contract",
        "無料・有料",
        "Core UX invariants",
    )
    require(
        "AGENTS.md",
        "FORGE-UNIVERSAL-QUALITY-INVARIANT.md",
        "Hardware / Model Profileを品質Tierとして扱わず",
    )
    require(
        "docs/architecture/FORGE-LOCAL-MODEL-QUALITY-AND-QUANTIZATION.md",
        "Hardware Profile（端末性能の分類）は**品質の分類ではなく",
        "同じ Product Quality Contract",
    )
    require(
        "docs/architecture/FORGE-SELF-CONTAINED-DISTRIBUTION.md",
        "全Profileへ同じProduct Quality Contract",
        "低性能 PC だから品質を下げる",
    )
    require(
        "docs/reports/FORGE-ZERO-BUDGET-ZERO-GAP-STRATEGY-20260902.md",
        "Universal Quality Invariant",
        "Hardware / OS / Device / Model / Execution Hostによる品質Gate差: **0件**",
    )
    reject(
        "docs/architecture/FORGE-SELF-CONTAINED-DISTRIBUTION.md",
        r"Low resource PC\s*\n\s*(?:->|→)\s*小型モデル",
        "low-resource hardware is mapped directly to a smaller model",
    )
    reject(
        "docs/reports/FORGE-ZERO-BUDGET-ZERO-GAP-STRATEGY-20260902.md",
        r"Visible degraded state",
        "a degraded output state is presented as the release solution",
    )

    constitution = read("docs/FORGE-CORE-CONSTITUTION.md")
    if "Universal quality invariant." in constitution:
        require(
            "docs/reports/FORGE-CONSTITUTION-CHANGE-PROPOSAL-UNIVERSAL-QUALITY-20260902.md",
            "APPROVED BY CEO / APPLIED",
            "いいよ、すべて承認",
        )
    else:
        require(
            "docs/reports/FORGE-CONSTITUTION-CHANGE-PROPOSAL-UNIVERSAL-QUALITY-20260902.md",
            "AWAITING CEO APPROVAL",
            "Universal quality invariant.",
        )

    print("Universal quality policy alignment: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"Universal quality policy alignment: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
