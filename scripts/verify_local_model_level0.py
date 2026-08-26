"""FORGE Local AI **Level 0** の実測 (Vision §39、2026-08-26)。

---

## 何を証明するための script か

CEO 決定（2026-08-26）により、Level 0 の実測は**開発 container ではなく、
インターネットへ通常接続できる別の実機**で行う。

証明したいのは**能力**ではない。次の経路が端から端まで通ることである。

```
Local Runtime (Ollama / llama.cpp)
  → LocalModelProvider
  → Provider Registry
  → AIRouter
  → Forge pipeline
  → Validator
  → Evidence (GenerationRecord)
  → BenchmarkRun
  → LocalPromotionGate が読める形
```

小型 Q4 モデルで構わない。**強いモデルは Baseline Benchmark の話であり、
Level 0 の話ではない。**

## 使い方（実機側）

```
# 1. Runtime を起動しておく（例）
ollama serve
ollama pull qwen2.5:1.5b-instruct

# 2. Forge の repository で
export FORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export FORGE_LOCAL_MODEL=qwen2.5:1.5b-instruct
python scripts/verify_local_model_level0.py

# 結果は docs/evidence/level0/<timestamp>.json へ書かれる
```

`--out` で出力先を変えられる。`--need` で課題文を変えられる。

## この script が数えない実行

`RealLocalModelRun.counts_as_real_local` が `False` のものは
**Real Local Model runs に加算しない**。理由は JSON へ全部書き出す。

* Provider が Mock / Test Double
* Runtime を特定できていない
* 重みの識別子が取れていない
* **Forge の本番経路（GenerationRecord）を通っていない**
* 構造化出力・Validator が通っていない

> 偽サーバを立てて騙すことまでは防げない。**防げないと書いておく**方が、
> 「検証済み」と言い切るより誠実である。だから `runtime_backend` /
> `model_digest` / `host_id` を記録として残す——偽るなら記録に嘘を書く
> しかない形にする。

## 開発 container で走らせた場合

Runtime が居ないので `Level0Outcome.FAILED` になり、理由に
「Runtime へ接続できない」が入る。**それが正しい状態である**
（Vision の Level 0 は UNVERIFIED のまま）。
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

_DEFAULT_NEED = "毎日の支出を記録して合計を見たい"


def _probe_runtime(base_url: str, model: str, timeout: float) -> dict[str, object]:
    """Runtime の身元を訊く。**推論の前に、何が動いているかを確かめる。**

    OpenAI 互換の `/v1/models` と、Ollama 固有の `/api/tags` の両方を試す。
    Ollama は digest（重みの識別子）を返すので、取れたら使う。
    """
    import httpx

    info: dict[str, object] = {
        "backend": "unknown", "version": "", "digest": "", "quantization": "",
        "reachable": False, "error": "",
    }
    root = base_url.rstrip("/")
    ollama_root = root[: -len("/v1")] if root.endswith("/v1") else root

    try:
        with httpx.Client(timeout=timeout) as client:
            # -- Ollama か（digest と quantization が取れる） --------------
            try:
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
                        ver = client.get(f"{ollama_root}/api/version")
                        if ver.status_code == 200:
                            info["version"] = str(ver.json().get("version") or "")
                    except httpx.HTTPError:
                        pass
            except httpx.HTTPError:
                pass

            # -- OpenAI 互換 `/v1/models` ----------------------------------
            if not info["reachable"]:
                models = client.get(f"{root}/models")
                if models.status_code == 200:
                    info["reachable"] = True
                    info["backend"] = "openai_compatible_other"
                    for entry in models.json().get("data", []):
                        if entry.get("id") == model:
                            # llama-server 等は digest を返さないことがある。
                            info["digest"] = str(
                                entry.get("digest") or entry.get("id") or ""
                            )
                            break
    except httpx.HTTPError as error:
        info["error"] = f"{type(error).__name__}: {error}"
    return info


def _host_facts() -> dict[str, object]:
    """どの実機で測ったか。**container と実機を混ぜない。**"""
    facts: dict[str, object] = {
        "host_id": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "ram_total_mb": 0,
        "vram_total_mb": 0,
    }
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        facts["ram_total_mb"] = int(pages * size / (1024 * 1024))
    except (ValueError, OSError, AttributeError):
        pass
    return facts


def main() -> int:  # noqa: PLR0915 — 手順書としての読みやすさを優先する
    parser = argparse.ArgumentParser(description="FORGE Local AI Level 0 実測")
    parser.add_argument("--need", default=_DEFAULT_NEED)
    parser.add_argument("--out", default="")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    from app.ai.gateway.benchmark_evidence import Verification
    from app.ai.gateway.generation_evidence import GenerationSource
    from app.ai.gateway.learning_events import Deployment
    from app.ai.gateway.local_model_evidence import (
        Level0Outcome,
        LocalRuntimeBackend,
        RealLocalModelRun,
        default_real_local_run_log,
    )
    from app.ai.gateway.tasks import ForgeTask

    base_url = os.environ.get("FORGE_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1")
    model = os.environ.get("FORGE_LOCAL_MODEL", "qwen2.5:1.5b-instruct")
    host = _host_facts()

    print("=" * 66)
    print("FORGE Local AI — Level 0 実測")
    print("=" * 66)
    print(f"  host      : {host['host_id']}  ({host['platform']})")
    print(f"  base_url  : {base_url}")
    print(f"  model     : {model}")
    print(f"  need      : {args.need}")
    print()

    # --- 1. Runtime の身元 -------------------------------------------
    probe = _probe_runtime(base_url, model, timeout=15.0)
    print("[1/3] Runtime を確認")
    if not probe["reachable"]:
        print(f"      ✗ 接続できない: {probe['error'] or base_url}")
        print()
        print("      Runtime が起動していない可能性がある。例:")
        print("        ollama serve")
        print(f"        ollama pull {model}")
    else:
        print(f"      ✓ backend={probe['backend']} version={probe['version'] or '-'}")
        print(f"        digest={probe['digest'] or '(取得できず)'}"
              f" quantization={probe['quantization'] or '(取得できず)'}")
    print()

    # --- 2. 本番経路で1件生成する ------------------------------------
    print("[2/3] Forge の本番経路で生成（provider=local）")
    generation_uid = ""
    generation_source = None
    validator_passed = False
    structured_ok = False
    latency_ms = 0.0
    failure = ""

    try:
        from fastapi.testclient import TestClient

        from app.ai.gateway.generation_evidence import default_generation_store
        from app.main import app

        before = len(default_generation_store().all_records())
        client = TestClient(app)
        started = time.perf_counter()
        response = client.post(
            "/api/v1/ai/generate",
            json={
                "input": {
                    "natural_language": args.need,
                    "generation_options": {"provider": "local"},
                },
            },
        )
        latency_ms = (time.perf_counter() - started) * 1000.0

        if response.status_code == 200:
            result = response.json()["result"]
            structured_ok = bool(result.get("forge_document"))
            validator_passed = bool((result.get("validation") or {}).get("valid"))
            records = default_generation_store().all_records()
            if len(records) > before:
                generation_uid = records[-1].uid
                # **決定的な検査。** 200 が返っても、作ったのが Curated なら
                # Local Model の成果ではない（実測でそうなった）。
                generation_source = records[-1].source
            print(f"      ✓ HTTP 200  ({latency_ms:.0f} ms)")
            print(f"        validator_passed={validator_passed}"
                  f" evidence_uid={generation_uid or '(無し)'}")
            print(f"        generation_source="
                  f"{generation_source.value if generation_source else '(無し)'}"
                  "   ← local_ai でなければ Local Model は動いていない")
        else:
            failure = f"HTTP {response.status_code}: {response.text[:200]}"
            print(f"      ✗ {failure}")
    except Exception as error:  # noqa: BLE001 — 失敗も結果として残す
        failure = f"{type(error).__name__}: {error}"
        print(f"      ✗ {failure}")
    print()

    # --- 3. 数えてよいかを判定する -----------------------------------
    backend_map = {
        "ollama": LocalRuntimeBackend.OLLAMA,
        "openai_compatible_other": LocalRuntimeBackend.OPENAI_COMPATIBLE_OTHER,
    }
    run = RealLocalModelRun(
        provider="local",
        model=model,
        task=ForgeTask.FORGE_LANGUAGE_UPDATE,
        runtime_backend=backend_map.get(
            str(probe["backend"]), LocalRuntimeBackend.UNKNOWN,
        ),
        runtime_version=str(probe["version"]),
        model_digest=str(probe["digest"]),
        quantization=str(probe["quantization"]),
        # **実際に LOCAL で走ったときだけ LOCAL と書く。**
        deployment=Deployment.LOCAL if probe["reachable"] else Deployment.UNKNOWN,
        latency_ms=latency_ms,
        structured_output_ok=structured_ok,
        validator_passed=validator_passed,
        generation_evidence_uid=generation_uid,
        generation_source=generation_source or GenerationSource.UNKNOWN,
        host_id=str(host["host_id"]),
        ram_total_mb=int(host["ram_total_mb"]),
        vram_total_mb=int(host["vram_total_mb"]),
        # 実測として記録してよいのは、実際に往復できたときだけ。
        verification=Verification.REAL if probe["reachable"] else Verification.UNVERIFIED,
    )
    recorded = default_real_local_run_log().record(run)

    print("[3/3] Real Local Model run として数えてよいか")
    if recorded.counts_as_real_local:
        print("      ✓ 数える")
    else:
        print("      ✗ 数えない。理由:")
        for reason in recorded.why_not_counted():
            print(f"        - {reason}")
    print()

    outcome = default_real_local_run_log().level0()
    evidence = {
        "task": "FORGE-020A Level 0",
        "level0_outcome": outcome.value,
        "real_local_model_runs": default_real_local_run_log().count(),
        "host": host,
        "runtime_probe": probe,
        "generation_failure": failure,
        "run": recorded.to_dict(),
        "recorded_at": time.time(),
    }

    out = pathlib.Path(args.out) if args.out else (
        _ROOT / "docs" / "evidence" / "level0"
        / f"level0-{time.strftime('%Y%m%d-%H%M%S')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )

    print("=" * 66)
    print(f"  Level 0                : {outcome.value.upper()}")
    print(f"  Real Local Model runs  : {evidence['real_local_model_runs']}")
    print(f"  evidence               : {out}")
    print("=" * 66)
    if outcome is not Level0Outcome.PASSED:
        print()
        print("  Level 0 は未到達のまま。docs の UNVERIFIED を変えないこと。")
    return 0 if outcome is Level0Outcome.PASSED else 1


if __name__ == "__main__":
    raise SystemExit(main())
