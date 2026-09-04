#!/usr/bin/env python3
"""One-shot TD110 Windows probe batch.

Runs all physical-Windows sandbox probes, captures stdout/stderr as ordinary
text (avoiding Windows PowerShell CLIXML stream coercion), writes per-step logs,
and prints one compact failure bundle at the end.
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
class StepResult:
    name: str
    exit_code: int
    log: Path
    output: str


STEPS = (
    ("01-isolation-boundary", "windows_appcontainer_isolation_probe.py"),
    ("02-job-resource-limits", "windows_job_resource_probe.py"),
    ("03-real-toolchains", "windows_toolchain_probe.py"),
)


def _run_step(name: str, script_name: str, run_dir: Path) -> StepResult:
    script = REPO / "scripts" / script_name
    log = run_dir / f"{name}.log"

    print(f"\n=== {name} ===", flush=True)
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = (completed.stdout or "")
    if completed.stderr:
        if output and not output.endswith("\n"):
            output += "\n"
        output += completed.stderr

    log.write_text(output, encoding="utf-8")
    if output:
        print(output, end="" if output.endswith("\n") else "\n")

    status = "PASS" if completed.returncode == 0 else "FAIL"
    print(f"{status}: {name} (exit {completed.returncode})", flush=True)
    return StepResult(name, completed.returncode, log, output)


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(tempfile.gettempdir()) / f"forge-td110-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=== TD110 Windows batch ===")
    print(f"Repo   : {REPO}")
    print(f"Python : {sys.executable}")
    print(f"RunDir : {run_dir}")

    results = [_run_step(name, script, run_dir) for name, script in STEPS]
    failed = [item for item in results if item.exit_code != 0]

    print("\n=== Summary ===")
    for item in results:
        status = "PASS" if item.exit_code == 0 else "FAIL"
        print(f"{status:4}  {item.name:26} exit={item.exit_code}  {item.log}")

    print(f"\nFailed : {len(failed)}")
    print(f"Logs   : {run_dir}")

    if failed:
        print("\n=== COPY FROM HERE ===")
        for item in failed:
            print(f"\n--- {item.name} ---")
            print(item.output, end="" if item.output.endswith("\n") else "\n")
        print("\n=== COPY TO HERE ===")
        return 1

    print("\nTD110 probe batch: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
