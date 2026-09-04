#!/usr/bin/env python3
"""One-shot physical Windows validation for TD110 production integration.

Runs the real probe batch, the production sandbox escape corpus, the complete
forge_ai suite (including Self-Extension), and a backend regression.  All child
processes run with FORGE_SANDBOX_ALLOW_POLICY_ONLY removed so a missing/broken
Windows OS backend cannot be hidden by the CI-only weaker mode.

PASS output is intentionally compact.  Failed step logs are bundled at the end
so the physical-PC operator can paste one result back for diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Step:
    name: str
    argv: tuple[str, ...]
    cwd: Path


@dataclass(frozen=True)
class Result:
    step: Step
    exit_code: int
    log: Path
    output: str
    seconds: float


def _run(step: Step, run_dir: Path, env: dict[str, str]) -> Result:
    import time

    print(f"\n=== {step.name} ===", flush=True)
    started = time.monotonic()
    completed = subprocess.run(
        list(step.argv),
        cwd=str(step.cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    seconds = time.monotonic() - started
    output = (completed.stdout or "")
    if completed.stderr:
        if output and not output.endswith("\n"):
            output += "\n"
        output += completed.stderr
    log = run_dir / (step.name.replace(" ", "_").replace("/", "_") + ".log")
    log.write_text(output, encoding="utf-8")

    status = "PASS" if completed.returncode == 0 else "FAIL"
    print(f"{status}: {step.name} (exit {completed.returncode}, {seconds:.1f}s)")
    return Result(step, completed.returncode, log, output, seconds)


def main() -> int:
    if os.name != "nt":
        print("Windows-only validation")
        return 2

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(tempfile.gettempdir()) / f"forge-td110-production-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    python = Path(sys.executable).resolve()
    env = os.environ.copy()
    env.pop("FORGE_SANDBOX_ALLOW_POLICY_ONLY", None)
    env["PYTHONUTF8"] = "1"

    steps = (
        Step(
            "01 TD110 physical probes",
            (str(python), str(REPO / "scripts" / "windows_td110_batch.py")),
            REPO,
        ),
        Step(
            "02 production escape corpus",
            (
                str(python),
                "-m",
                "unittest",
                "discover",
                "-s",
                "forge_ai/tests",
                "-p",
                "test_sandbox_escape_corpus.py",
                "-v",
            ),
            REPO,
        ),
        Step(
            "03 full forge_ai Self-Extension suite",
            (
                str(python),
                "-m",
                "unittest",
                "discover",
                "-s",
                "forge_ai/tests",
                "-p",
                "test_*.py",
            ),
            REPO,
        ),
        Step(
            "04 backend regression",
            (
                str(python),
                "-m",
                "pytest",
                "backend/tests",
                "-q",
            ),
            REPO,
        ),
    )

    print("=== Forge TD110 production validation ===")
    print(f"Repo   : {REPO}")
    print(f"Python : {python}")
    print(f"Logs   : {run_dir}")
    print("Policy-only fallback: DISABLED")

    results = [_run(step, run_dir, env) for step in steps]
    failed = [item for item in results if item.exit_code != 0]

    print("\n=== Summary ===")
    for item in results:
        status = "PASS" if item.exit_code == 0 else "FAIL"
        print(
            f"{status:4}  {item.step.name:38} "
            f"exit={item.exit_code:<4} {item.seconds:7.1f}s"
        )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    dirty = status.stdout.strip()
    print(f"\nWorking tree clean: {not bool(dirty)}")
    if dirty:
        print(dirty)

    if failed:
        print(f"\nFailed: {len(failed)}")
        print("\n=== COPY FROM HERE ===")
        for item in failed:
            print(f"\n--- {item.step.name} ---")
            # Preserve enough context for one-shot diagnosis without dumping
            # tens of thousands of passing unittest lines.
            text = item.output
            if len(text) > 30000:
                text = "...[earlier output truncated]...\n" + text[-30000:]
            print(text, end="" if text.endswith("\n") else "\n")
        print("\n=== COPY TO HERE ===")
        return 1

    print("\nTD110 production validation: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
