#!/usr/bin/env python3
"""Frozen Final Holdout の runner。**問題本体は Repository に無い。**

---

## 何をするものか

RC Freeze 後に独立生成された Holdout 問題集合（Repository の外）を受け取り、
凍結した Release Candidate に対して 1 回だけ走らせ、**結果だけ**を
`docs/evidence/holdout/results/` へ残す。

```text
python3 scripts/holdout_runner.py \
    --manifest /path/outside/repo/holdout.jsonl \
    --rc-git-sha <40 hex> \
    --created-by "ceo" \
    --out docs/evidence/holdout/results/rc-<sha8>.json
```

## いま実行できないこと

Holdout 問題集合はまだ存在しない（RC Freeze 前だから）。この runner は
**形を先に固定するため**にある。形が後から決まると、集めた結果を作り直す
ことになる。

## 開発 Agent が作った Holdout は Holdout ではない

`--created-by` が開発 Agent を指す場合、この runner は**拒否する**。
自分で作った問題を自分で解いて 99% と言うのは証明ではない。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALLOCATION = ROOT / "docs" / "evidence" / "holdout" / "family_allocation.json"
SCORING_CONTRACT_VERSION = "1.0"

#: この名前で作られた Holdout は受け付けない。
_FORBIDDEN_CREATORS = {"claude", "agent", "dev", "developer", "development-agent"}


def wilson_lower_bound(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    if trials <= 0:
        return 0.0
    phat = successes / trials
    denom = 1.0 + z * z / trials
    centre = phat + z * z / (2 * trials)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * trials)) / trials)
    return (centre - margin) / denom


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=pathlib.Path,
                        help="Repository の外にある Holdout 問題集合（JSONL）")
    parser.add_argument("--rc-git-sha", required=True)
    parser.add_argument("--created-by", required=True,
                        help="誰が作ったか。開発 Agent なら拒否する")
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--executed-at", required=True)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()

    if args.created_by.strip().lower() in _FORBIDDEN_CREATORS:
        print(
            f"created_by={args.created_by!r} は開発 Agent である。"
            "自分で作った問題を自分で解いた結果は Holdout ではない。",
            file=sys.stderr,
        )
        return 2

    if not args.manifest.exists():
        print(f"Holdout 問題集合が見つからない: {args.manifest}", file=sys.stderr)
        print(
            "RC Freeze 前はこれが正常である。**この runner は形を先に固定する"
            "ためにあり、いま結果を作るためのものではない。**",
            file=sys.stderr,
        )
        return 3

    if not ALLOCATION.exists():
        print(f"Family 割り当て表が無い: {ALLOCATION}", file=sys.stderr)
        return 4

    try:
        resolved = args.manifest.resolve()
        resolved.relative_to(ROOT)
    except ValueError:
        pass
    else:
        print(
            f"Holdout 問題集合が Repository の中にある: {resolved}。"
            "開発 Agent が読める場所に置いた時点で Holdout ではない。",
            file=sys.stderr,
        )
        return 5

    per_capability: dict[str, dict] = defaultdict(
        lambda: {"episodes": 0, "successes": 0, "hard_gate_violations": 0}
    )
    with args.manifest.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            episode = json.loads(line)
            for capability_id in episode.get("proves", []):
                bucket = per_capability[capability_id]
                bucket["episodes"] += 1
                bucket["successes"] += int(bool(episode.get("task_completed")))
                bucket["hard_gate_violations"] += int(episode.get("hard_gate_violations", 0))

    capabilities = []
    for capability_id, bucket in sorted(per_capability.items()):
        capabilities.append({
            "capability_id": capability_id,
            "episodes": bucket["episodes"],
            "successes": bucket["successes"],
            "wilson_lower_bound_95": wilson_lower_bound(
                bucket["successes"], bucket["episodes"]
            ),
            "hard_gate_violations": bucket["hard_gate_violations"],
        })

    result = {
        "provenance": {
            "rc_git_sha": args.rc_git_sha,
            "holdout_manifest_sha256": sha256_of(args.manifest),
            "family_allocation_sha256": sha256_of(ALLOCATION),
            "created_at": args.created_at,
            "created_by": args.created_by,
            "executed_at": args.executed_at,
        },
        "scoring_contract_version": SCORING_CONTRACT_VERSION,
        "capabilities": capabilities,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"結果だけを書いた（問題本体は残していない）: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
