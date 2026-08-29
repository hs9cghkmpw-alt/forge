#!/usr/bin/env python3
"""FORGE-020D/020E real Flutter repair + runtime probe.

Materialize an isolated generated Flutter app, inject one deterministic failing test,
repair only that generated workspace, then require fresh Flutter test, Web build, and
Flutter runtime-smoke observations to pass. Repair/model text cannot declare success;
CommandRunner exit codes decide.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Backend imports live under ROOT/backend while forge_ai is a top-level package at ROOT.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.agent.flutter_generated_workspace import (  # noqa: E402
    materialize_flutter_generated_workspace,
)
from app.ai.agent.generated_repair import run_generated_repair_episode  # noqa: E402
from app.ai.agent.generated_verification import GeneratedWorkspaceVerifier  # noqa: E402
from app.ai.learning.episode import EpisodeOutcome, GenerationEpisode  # noqa: E402

_FAILING_TEST = """import 'package:flutter_test/flutter_test.dart';

void main() {
  test('FORGE-020D intentional pre-repair failure', () {
    expect(1, 2);
  });
}
"""

_PASSING_TEST = """import 'package:flutter_test/flutter_test.dart';

void main() {
  test('FORGE-020D repaired generated workspace', () {
    expect(1, 1);
  });
}
"""

_RUNTIME_TEST = """import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/main.dart';

void main() {
  testWidgets('generated app entrypoint runs in Flutter widget runtime', (tester) async {
    await tester.pumpWidget(const GeneratedForgeApp());
    await tester.pump();
    expect(find.byType(GeneratedForgeApp), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
"""


def _write_evidence(evidence: dict[str, object]) -> None:
    rendered = json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2)
    print(rendered)
    raw_path = os.getenv("FORGE_020D_EVIDENCE_PATH", "").strip()
    if raw_path:
        path = pathlib.Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")


def main() -> int:
    if shutil.which("flutter") is None:
        print("flutter executable not found", file=sys.stderr)
        return 2

    document = {
        "version": "1.0",
        "initial_screen_id": "home",
        "screens": [
            {
                "id": "home",
                "title": "FORGE-020D probe",
                "body": {"type": "text", "text": "repair probe"},
            }
        ],
    }

    with tempfile.TemporaryDirectory(prefix="forge-020d-") as temp:
        workspace = materialize_flutter_generated_workspace(
            root=pathlib.Path(temp) / "generated-app",
            runtime_template_root=ROOT / "frontend",
            forge_document=document,
        )
        probe_path = "test/forge_020d_repair_probe_test.dart"
        runtime_probe_path = "test/forge_020e_runtime_probe_test.dart"
        workspace.sandbox().write_text(probe_path, _FAILING_TEST)
        workspace.sandbox().write_text(runtime_probe_path, _RUNTIME_TEST)

        verifier = GeneratedWorkspaceVerifier(
            workspace=workspace,
            commands={
                "prepare": ("flutter", "pub", "get"),
                "run_test": (
                    "flutter",
                    "test",
                    probe_path,
                    "--reporter",
                    "compact",
                ),
                "run_build": ("flutter", "build", "web", "--debug"),
                "run_runtime": (
                    "flutter",
                    "test",
                    runtime_probe_path,
                    "--reporter",
                    "compact",
                ),
            },
            timeout_seconds=600.0,
        )
        episode = GenerationEpisode(task_id="forge.generated.flutter.repair.020d")

        def repair(latest, round_index: int) -> None:
            if latest.attempt.failure_code != "test_failed" or round_index != 1:
                raise RuntimeError(
                    f"unexpected repair request: {latest.attempt.failure_code}/{round_index}"
                )
            workspace.sandbox().write_text(probe_path, _PASSING_TEST)

        result = run_generated_repair_episode(
            episode=episode,
            verifier=verifier,
            repair_action=repair,
            max_repair_rounds=1,
        )

        evidence = {
            "schema": "forge.generated_flutter_repair.020e.v1",
            "artifact_fingerprint": workspace.artifact_fingerprint,
            "verification_count": len(result.verifications),
            "initial_failure_code": result.initial.attempt.failure_code,
            "initial_test": result.initial.attempt.test.value,
            "initial_build": result.initial.attempt.build.value,
            "initial_runtime": result.initial.attempt.runtime.value,
            "final_test": result.final.attempt.test.value,
            "final_build": result.final.attempt.build.value,
            "final_runtime": result.final.attempt.runtime.value,
            "final_visual": result.final.attempt.visual.value,
            "outcome": result.report.outcome.value,
            "rounds": result.report.rounds,
            "repair_succeeded": episode.repair_succeeded,
            "repair_rounds": [item.to_dict() for item in episode.repair_rounds],
        }
        _write_evidence(evidence)

        passed = (
            result.report.outcome is EpisodeOutcome.SUCCEEDED
            and result.report.rounds == 1
            and len(result.verifications) == 2
            and result.initial.attempt.failure_code == "test_failed"
            and result.initial.attempt.build.value == "unknown"
            and result.initial.attempt.runtime.value == "unknown"
            and result.final.attempt.test.value == "passed"
            and result.final.attempt.build.value == "passed"
            and result.final.attempt.runtime.value == "passed"
            and result.final.attempt.visual.value == "unknown"
            and episode.repair_succeeded
        )
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
