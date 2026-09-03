#!/usr/bin/env python3
"""121 能力 Matrix が、**書けるより高い状態を主張していない**ことを機械に見させる。

---

## なぜ機械に見させるのか

Matrix は人が書く表である。人が書く表は、締切が近づくと甘くなる。
「だいたい実装した」を `IMPLEMENTED`、「1 回通った」を `99_PROVEN` と
書いた瞬間、121 項目の合計は意味を失う。

したがって**主張の形式**だけは機械が検査する。中身の正しさは人が見る。

## 検査する規則

| 規則 | 理由 |
|---|---|
| `IMPLEMENTED` 以上は `implementation_evidence` のパスが実在すること | 「作った」の根拠が Repository に無いなら作っていない |
| `VERIFIED` 以上は `episodes >= 1` | 動かしていないものを検証済みと言わない |
| `99_PROVEN` は Wilson 95% 信頼下限 >= 0.99 | 1 回成功を 99% と言わない |
| `99_PROVEN` は `episodes >= 300` | n=10 で 100% は 99% の証明にならない |
| `HARD_GATE_PROVEN` は Hard Gate 項目にだけ許す | 99% 項目に Hard Gate の語を使わない |
| Wilson 下限は再計算して一致すること | 表に書いた数字が計算と合わない事態を防ぐ |
| 総数が 121 であること | 分母を後から変えない |

`--summary` で人間向けの集計を出す。CI は戻り値だけを見る。
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "evidence" / "capability_matrix" / "capabilities.json"

EXPECTED_TOTAL = 121

ORDER = [
    "NOT_ASSESSED",
    "NOT_STARTED",
    "DESIGNED",
    "PARTIAL",
    "IMPLEMENTED",
    "VERIFIED",
    # Human Evidence が要る Capability の踊り場。
    #
    # **Human 0 人は Implementation blocker ではない**（CEO 指示 2026-09-04）。
    # 自動・内部検証まで終わり、あとは人間の評価だけ、という状態を
    # `99_PROVEN` と混ぜずに置ける段を用意する。ここで止まっている
    # Capability は「作業が止まっている」のではなく「募集待ち」である。
    "PRE_HUMAN_READY",
    "99_PROVEN",
    "HARD_GATE_PROVEN",
]

#: Human Evidence を必要としない Capability が `PRE_HUMAN_READY` を
#: 名乗るのは意味が無い（人を待っていないため）。
HUMAN_EVIDENCE_MARKER = "human_evidence_required"

#: `99_PROVEN` を名乗るのに最低限必要な独立 Episode 数。
#:
#: n=10 で 10 勝しても Wilson 95% 下限は 0.72 程度にしかならない。
#: 0.99 を下限で超えるには数百件が要る——**そこを緩めない**ための下限。
MIN_EPISODES_FOR_99 = 300


def wilson_lower_bound(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    """95% Wilson 信頼下限。**平均ではなく下限で判定する。**"""
    if trials <= 0:
        return 0.0
    phat = successes / trials
    denom = 1.0 + z * z / trials
    centre = phat + z * z / (2 * trials)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * trials)) / trials)
    return (centre - margin) / denom


def _rank(status: str) -> int:
    return ORDER.index(status) if status in ORDER else -1


def check(manifest: dict) -> list[str]:
    problems: list[str] = []
    capabilities = manifest.get("capabilities", [])

    if len(capabilities) != EXPECTED_TOTAL:
        problems.append(
            f"能力数が {len(capabilities)} 件。**分母を後から変えない**"
            f"（{EXPECTED_TOTAL} 件で固定）"
        )

    seen: set[str] = set()
    for entry in capabilities:
        cid = entry.get("capability_id", "<no id>")
        if cid in seen:
            problems.append(f"{cid}: Capability ID が重複している")
        seen.add(cid)

        status = entry.get("implementation_status", "")
        if status not in ORDER:
            problems.append(f"{cid}: 未知の implementation_status {status!r}")
            continue
        rank = _rank(status)

        evidence = entry.get("implementation_evidence") or []
        if rank >= _rank("IMPLEMENTED"):
            if not evidence:
                problems.append(
                    f"{cid}: {status} を名乗るのに implementation_evidence が空。"
                    "**根拠の無い『作った』は作っていない**"
                )
            for path in evidence:
                if not (ROOT / path).exists():
                    problems.append(
                        f"{cid}: implementation_evidence のパスが実在しない: {path}"
                    )

        measured = entry.get("measured") or {}
        episodes = int(measured.get("episodes") or 0)
        successes = int(measured.get("successes") or 0)

        if successes > episodes:
            problems.append(f"{cid}: successes({successes}) > episodes({episodes})")

        if rank >= _rank("VERIFIED") and episodes < 1:
            problems.append(
                f"{cid}: {status} を名乗るのに episodes が 0。"
                "**動かしていないものを検証済みと言わない**"
            )

        recorded_lb = measured.get("wilson_lower_bound_95")
        if episodes > 0:
            actual_lb = wilson_lower_bound(successes, episodes)
            if recorded_lb is None:
                problems.append(f"{cid}: episodes があるのに Wilson 下限が未記録")
            elif abs(float(recorded_lb) - actual_lb) > 1e-6:
                problems.append(
                    f"{cid}: Wilson 下限の記録 {recorded_lb} が再計算 "
                    f"{actual_lb:.6f} と一致しない"
                )
        elif recorded_lb is not None:
            problems.append(
                f"{cid}: episodes が 0 なのに Wilson 下限 {recorded_lb} が入っている"
            )

        if status == "99_PROVEN":
            if episodes < MIN_EPISODES_FOR_99:
                problems.append(
                    f"{cid}: 99_PROVEN に episodes={episodes} は足りない"
                    f"（最低 {MIN_EPISODES_FOR_99}）。**n が小さい 100% は 99% の証明ではない**"
                )
            if recorded_lb is None or float(recorded_lb) < 0.99:
                problems.append(
                    f"{cid}: 99_PROVEN なのに Wilson 95% 下限が {recorded_lb}（0.99 未満）"
                )

        if status == "PRE_HUMAN_READY" and not entry.get("human_evidence_required"):
            problems.append(
                f"{cid}: Human Evidence を要求しない Capability が PRE_HUMAN_READY を"
                "名乗っている（人を待っていないなら VERIFIED から先へ進める）"
            )

        is_hard_gate = bool((entry.get("target_contract") or {}).get("hard_gate"))
        if status == "HARD_GATE_PROVEN" and not is_hard_gate:
            problems.append(
                f"{cid}: Hard Gate 項目ではないのに HARD_GATE_PROVEN を名乗っている"
            )

        if rank >= _rank("PARTIAL") and not entry.get("zero_budget_approach"):
            problems.append(
                f"{cid}: {status} なのに zero_budget_approach が空。"
                "**どの 0 円代替方式で満たすのかを書く**"
            )

        if status == "NOT_ASSESSED" and rank_has_claim(entry):
            problems.append(
                f"{cid}: NOT_ASSESSED なのに実績値が入っている（評価したなら状態を上げる）"
            )

    return problems


def rank_has_claim(entry: dict) -> bool:
    measured = entry.get("measured") or {}
    return bool(measured.get("episodes")) or bool(entry.get("implementation_evidence"))


def summarise(manifest: dict) -> str:
    capabilities = manifest["capabilities"]
    by_status = Counter(c["implementation_status"] for c in capabilities)
    lines = [
        f"総数: {len(capabilities)}",
        f"Hard Gate 項目: {sum(1 for c in capabilities if c['target_contract']['hard_gate'])}",
        "",
        "Implementation Status:",
    ]
    for status in ORDER:
        if by_status.get(status):
            lines.append(f"  {status:<18} {by_status[status]:>4}")
    lines += [
        "",
        f"99_PROVEN:        {by_status.get('99_PROVEN', 0)}",
        f"HARD_GATE_PROVEN: {by_status.get('HARD_GATE_PROVEN', 0)}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true", help="人間向けの集計も出す")
    args = parser.parse_args()

    if not MATRIX.exists():
        print(f"Capability matrix が見つからない: {MATRIX}", file=sys.stderr)
        return 1

    manifest = json.loads(MATRIX.read_text(encoding="utf-8"))
    problems = check(manifest)

    if args.summary:
        print(summarise(manifest))
        print()

    if problems:
        print("Capability matrix integrity: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("Capability matrix integrity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
