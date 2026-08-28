"""FORGE-020A4 — Real Local Model Level 0 の**事前適格性確認**。

実モデルを呼ぶ前に、production ``/generate`` を ``provider=mock`` で通し、
その Need が本当に AI Entity Synthesis へ software structure の仕事を渡すかを
型付き Evidence で確認する。

これは Level 0 実測ではない。Test Double の出力は Real Local Model runs に
**絶対に加算しない**。目的は、Curated / deterministic bypass の probe に
数分の実モデル推論を使ってから ``INVALID_PROBE`` と判明する無駄を減らすこと。

PowerShell:

    python scripts/preflight_local_model_level0.py

適格だったら、Runtime がある Execution Host で初めて:

    python scripts/verify_local_model_level0.py

を実行する。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

DEFAULT_LEVEL0_PROBE = "盆栽の水やりの記録をつけたい"
CURATED_TRAP_PROBE = "毎日の支出を記録して合計を見たい"


def _resolution_from_diagnostics(diagnostics: object) -> str:
    if not isinstance(diagnostics, dict):
        return ""
    for entry in diagnostics.get("decision_trace") or ():
        if isinstance(entry, dict) and entry.get("stage") == "domain_resolution":
            return str(entry.get("decision") or "").strip().lower()
    return ""


def _collect(need: str):  # noqa: ANN202
    """mock production run から typed Evidence を集める。

    RealLocalModelRunLog は import すらしない。preflight が実績を増やす経路を
    構造的に持たないためである。
    """
    from fastapi.testclient import TestClient

    from app.ai.gateway.generation_evidence import default_generation_store
    from app.ai.gateway.learning_foundation import default_experience_store
    from app.ai.gateway.level0_preflight import Level0PreflightFacts
    from app.main import app

    generation_store = default_generation_store()
    experience_store = default_experience_store()
    before_generation = len(generation_store.all_records())
    before_experience = len(experience_store.all_records())

    response = TestClient(app).post(
        "/api/v1/ai/generate",
        json={
            "input": {
                "natural_language": need,
                "generation_options": {"provider": "mock"},
            },
        },
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"preflight production request failed: HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    body = response.json()
    result = body.get("result") or {}
    diagnostics = result.get("diagnostics")
    records = generation_store.all_records()
    if len(records) <= before_generation:
        raise RuntimeError("production /generate が GenerationRecord を残していない")
    record = records[-1]

    observed_tasks = tuple(dict.fromkeys(
        item.task
        for item in experience_store.all_records()[before_experience:]
    ))

    facts = Level0PreflightFacts(
        domain_resolution=_resolution_from_diagnostics(diagnostics),
        structure_source=record.structure_source,
        structure_provider=record.structure_provider,
        structure_task=record.structure_task,
        observed_tasks=observed_tasks,
        validator_passed=record.validator_passed,
        generation_evidence_uid=record.uid,
        entity_synthesis_attempted=record.entity_synthesis_attempted,
        entity_synthesis_accepted=record.entity_synthesis_accepted,
        entity_synthesis_rejection_reason=record.entity_synthesis_rejection_reason,
    )
    return facts, record


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="FORGE Level 0 probe preflight（実モデルは呼ばない）",
    )
    parser.add_argument("--need", default=DEFAULT_LEVEL0_PROBE)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    from app.ai.gateway.level0_preflight import evaluate_level0_probe_preflight

    print("=" * 68)
    print("FORGE Local AI — Level 0 Probe Preflight")
    print("実モデルは呼ばない / Real Local Model runs は増やさない")
    print("=" * 68)
    print(f"need: {args.need}")

    try:
        facts, record = _collect(args.need)
        evaluated = evaluate_level0_probe_preflight(facts)
        failure = ""
    except Exception as error:  # noqa: BLE001 — 診断scriptなのでEvidenceへ残す
        evaluated = None
        record = None
        failure = f"{type(error).__name__}: {error}"

    if evaluated is None:
        print(f"✗ preflight error: {failure}")
        payload: dict[str, object] = {
            "task": "FORGE-020A4 Level 0 Probe Preflight",
            "need": args.need,
            "preflight_error": failure,
            "counts_as_real_local": False,
            "real_local_model_runs_changed": False,
            "recorded_at": time.time(),
        }
        exit_code = 1
    else:
        print(f"outcome: {evaluated.outcome.value}")
        for reason in evaluated.reasons:
            print(f"  - {reason}")
        if evaluated.eligible_for_real_run:
            print("✓ 実 Local Model で Level 0 を測る候補として適格")
            print("  ※ これは Level 0 PASS ではない。次に verify_local_model_level0.py を実測する。")
            exit_code = 0
        else:
            print("✗ この Need で実モデルを回す前に probe を見直す")
            exit_code = 2

        # GenerationRecord.to_dict() に synthesis attempt が無い現状でも、
        # Level 0 診断に必要な closed evidence を失わないよう明示的に出す。
        production_evidence = {
            "uid": record.uid if record is not None else "",
            "source": record.source.value if record is not None else "unknown",
            "structure_source": (
                record.structure_source.value if record is not None else "unknown"
            ),
            "structure_provider": (
                record.structure_provider.value if record is not None else "none"
            ),
            "structure_task": record.structure_task if record is not None else "",
            "entity_synthesis_attempted": (
                record.entity_synthesis_attempted if record is not None else False
            ),
            "entity_synthesis_accepted": (
                record.entity_synthesis_accepted if record is not None else False
            ),
            "entity_synthesis_rejection_reason": (
                record.entity_synthesis_rejection_reason if record is not None else None
            ),
            "validator_passed": (
                record.validator_passed if record is not None else False
            ),
        }
        payload = {
            "task": "FORGE-020A4 Level 0 Probe Preflight",
            "need": args.need,
            "preflight": evaluated.to_dict(),
            "production_evidence": production_evidence,
            "known_curated_trap": CURATED_TRAP_PROBE,
            "counts_as_real_local": False,
            "real_local_model_runs_changed": False,
            "meaning": (
                "eligible_for_real_run means the production control flow gives software "
                "structure work to Entity Synthesis under a Test Double. It is not a "
                "Local Model success and does not prove the real model can synthesize it."
            ),
            "recorded_at": time.time(),
        }

    out = pathlib.Path(args.out) if args.out else (
        _ROOT / "docs" / "evidence" / "level0-preflight"
        / f"preflight-{time.strftime('%Y%m%d-%H%M%S')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"evidence: {out}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
