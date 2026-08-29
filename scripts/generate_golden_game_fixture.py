#!/usr/bin/env python3
"""Generate the exact current Golden-game Forge Document through production HTTP wiring."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for path in (ROOT, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

NEED = "植物を育てながら音を組み合わせるゲームを作りたい"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate_golden_game_fixture.py OUTPUT.json")
    output = pathlib.Path(sys.argv[1])
    response = TestClient(app).post(
        "/api/v1/ai/generate",
        json={
            "input": {
                "natural_language": NEED,
                "generation_options": {"provider": "mock"},
            }
        },
    )
    response.raise_for_status()
    body = response.json()
    if body.get("status") != "success":
        raise RuntimeError(f"golden generation did not succeed: {body}")
    result = body["result"]
    if not result["validation"]["valid"]:
        raise RuntimeError("golden generated document did not pass validator")
    gap = result.get("capability_gap")
    if gap and gap.get("blocks_completion"):
        raise RuntimeError(f"golden generation still has a critical capability gap: {gap}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result["forge_document"], ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "generated",
        "version": result["forge_document"].get("version"),
        "output": str(output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
