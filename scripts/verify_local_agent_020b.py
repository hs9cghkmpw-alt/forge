"""FORGE-020B real Tool-Using Local Agent verifier.

Run the same verifier on a developer PC or an ephemeral GitHub runner.  The
verifier calls Forge's production HTTP generation endpoint with both real Local
generation and ``agent_mode=verify`` enabled, then fail-closes unless the stored
Generation Episode proves that a real Local provider selected and executed tools
and Forge independently passed Validator verification.

PowerShell example::

    $env:FORGE_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"
    $env:FORGE_LOCAL_MODEL="qwen2.5:7b-instruct"
    python scripts/verify_local_agent_020b.py

The output JSON is evidence, not a training-right grant. Build/test/runtime/visual
remain UNKNOWN in FORGE-020B because this bounded stage only verifies read-only
generation-inspection tools plus the deterministic Forge Validator.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import socket
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

PROBE = "盆栽の水やりの記録をつけたい"


def _runtime_identity(base_url: str, model: str) -> dict[str, object]:
    import httpx

    root = base_url.rstrip("/")
    ollama_root = root[: -len("/v1")] if root.endswith("/v1") else root
    info: dict[str, object] = {
        "reachable": False,
        "backend": "unknown",
        "version": "",
        "model": model,
        "digest": "",
        "quantization": "",
        "error": "",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            tags = client.get(f"{ollama_root}/api/tags")
            if tags.status_code == 200:
                info["reachable"] = True
                info["backend"] = "ollama"
                for entry in tags.json().get("models", []):
                    if entry.get("name") == model or entry.get("model") == model:
                        info["digest"] = str(entry.get("digest") or "")
                        details = entry.get("details") or {}
                        info["quantization"] = str(
                            details.get("quantization_level") or ""
                        )
                        break
                try:
                    version = client.get(f"{ollama_root}/api/version")
                    if version.status_code == 200:
                        info["version"] = str(version.json().get("version") or "")
                except httpx.HTTPError:
                    pass
    except httpx.HTTPError as error:
        info["error"] = f"{type(error).__name__}: {error}"
    return info


def _result_payload(body: dict[str, object]) -> dict[str, object]:
    value = body.get("result")
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--need", default=PROBE)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    base_url = os.environ.get("FORGE_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1")
    model = os.environ.get("FORGE_LOCAL_MODEL", "qwen2.5:7b-instruct")
    runtime = _runtime_identity(base_url, model)

    evidence: dict[str, object] = {
        "schema": "forge.real_local_agent.020b.v1",
        "created_at": time.time(),
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "runtime": runtime,
        "probe": args.need,
        "request": {"generation_provider": "local", "agent_mode": "verify"},
        "http": {},
        "agent": {},
        "episode": {},
        "passed": False,
        "failures": [],
    }
    failures: list[str] = evidence["failures"]  # type: ignore[assignment]

    if not runtime.get("reachable"):
        failures.append("local_runtime_unreachable")
    if not runtime.get("digest"):
        failures.append("model_digest_missing")

    try:
        from fastapi.testclient import TestClient
        from app.ai.learning.episode import (
            Deployment,
            LearningDataProvenance,
            VerificationOutcome,
            default_episode_store,
        )
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/ai/generate",
            json={
                "version": "1.0",
                "input": {
                    "natural_language": args.need,
                    "generation_options": {
                        "provider": "local",
                        "agent_mode": "verify",
                    },
                },
            },
        )
        body = response.json()
        evidence["http"] = {
            "status_code": response.status_code,
            "status": body.get("status"),
        }
        result = _result_payload(body)
        agent = result.get("agent") if isinstance(result, dict) else None
        agent = agent if isinstance(agent, dict) else {}
        evidence["agent"] = agent

        if response.status_code != 200:
            failures.append("production_http_not_200")
        if body.get("status") != "success":
            failures.append(f"production_status_{body.get('status') or 'missing'}")
        if not agent:
            failures.append("agent_summary_missing")
        if agent.get("provider") != "local":
            failures.append("agent_provider_not_local")
        if not agent.get("model"):
            failures.append("agent_model_missing")
        if not agent.get("executed"):
            failures.append("agent_not_executed")
        if agent.get("validator_outcome") != "passed":
            failures.append("agent_validator_not_passed")
        tools = agent.get("tools_used")
        tools = tools if isinstance(tools, list) else []
        if "validate_forge_document" not in tools:
            failures.append("mandatory_validator_tool_missing")
        if not tools:
            failures.append("no_tool_calls_recorded")

        episode_id = str(agent.get("episode_id") or "")
        episode = default_episode_store().get(episode_id) if episode_id else None
        if episode is None:
            failures.append("episode_missing")
        else:
            episode_dict = episode.to_dict()
            evidence["episode"] = episode_dict
            if episode.deployment is not Deployment.LOCAL:
                failures.append("episode_deployment_not_local")
            if episode.provenance is not LearningDataProvenance.LOCAL_AI_OUTPUT:
                failures.append("episode_provenance_not_local_ai_output")
            if not episode.generation_evidence_uid:
                failures.append("generation_evidence_lineage_missing")
            if episode.validator_outcome is not VerificationOutcome.PASSED:
                failures.append("episode_validator_not_passed")
            # 020B must not fabricate checks it does not execute.
            for name in ("build_outcome", "test_outcome", "runtime_outcome", "visual_outcome"):
                value = getattr(episode, name)
                if value is not VerificationOutcome.UNKNOWN:
                    failures.append(f"{name}_must_remain_unknown")
    except Exception as error:  # fail-closed, but preserve diagnostics in evidence
        evidence["exception"] = f"{type(error).__name__}: {error}"
        failures.append("verifier_exception")

    evidence["passed"] = not failures
    out = pathlib.Path(args.out) if args.out else pathlib.Path(
        "docs/evidence/agent020b/agent020b-"
        + time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        + ".json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(f"evidence={out}")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
