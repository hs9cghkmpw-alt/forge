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
  → production POST /api/v1/ai/generate
  → Validator
  → GenerationRecord(source=LOCAL_AI)
```

**ここまでが Level 0 である**（020A1 で範囲を限定した、2026-08-26）。

## Level 0 と Level 0.5 を分けた理由

以前この docstring は `BenchmarkRun` と `LocalPromotionGate` まで
Level 0 の完成条件に並べていた。**それは配線されていないし、
1件の成功で語れるものでもない。**

| | 何を証明するか | 必要なもの |
|---|---|---|
| **Level 0** | 経路が通る（E2E Runtime 証明） | 有効な probe 1件 |
| **Level 0.5** | どれくらい使えるか（Baseline） | 重みの同一性 + 複数件 |

Level 0.5 では **1件成功しただけで PROMOTED にしない**。
`LocalPromotionGate` が evidence 不足で `NOT PROMOTED` を返すのは
**正常な結果**であって失敗ではない。

Level 0.5 は `ready_for_baseline`（`model_digest` がある実行）だけを
入力にする。名前しか無い実行は「どの重みの成績か」が言えないので
Benchmark へ入れない。

小型 Q4 モデルで構わない。**強いモデルは Level 0.5 の話である。**

## probe は Curated へ落ちてはならない（020A1）

既定だった「毎日の支出を記録して合計を見たい」は `household_budget` の
**Curated Domain Library** へ解決される（実測:
`domain_resolution=curated`）。Curated 経路は**AI を1回も呼ばずに**
決定的に文書を作るので、Runtime が動いていなくても HTTP 200 が返り、
Validator も通る。

つまりあの probe では、**Local Model が仕事をしたかどうかを一切
測れない**。

この script は合成が要る probe を使い、実行の**前と後**に
`domain_resolution` を確認する。Curated へ落ちた場合は
`Level0Outcome.INVALID_PROBE`——**Local Model の FAIL ではなく、
測定の不成立**として扱う。

## 使い方（実機側）

```
# Forge の repositoryで（PowerShell）
$env:FORGE_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"
$env:FORGE_LOCAL_MODEL="qwen2.5:7b-instruct"
python scripts/verify_local_model_level0.py

# 結果は docs/evidence/level0/<timestamp>.json へ書かれる
```

`--out` で出力先を変えられる。`--need` で課題文を変えられる。

## この script が数えない実行

`RealLocalModelRun.counts_as_real_local` が `False` のものは
**Real Local Model runs に加算しない**。理由は JSON へ全部書き出す。

* Provider が Mock / Test Double
* Runtime を特定できていない
* **Forge の本番経路（GenerationRecord）を通っていない**
* **文書を作ったのが Curated Domain Library だった**（020A1）
* **記録した Task が、実際に AIRouter を通った Task と違う**（020A1）
* 構造化出力・Validator が通っていない

重みの digest が無い実行は**数える**（020A1で変更）。Level 0 が証明
するのは経路であって重みの同一性ではない。`weight_identity` が
`UNVERIFIED` になり、**Level 0.5 へは進めない**という形で受け止める。

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

#: **Level 0 専用の probe**（020A1、2026-08-26）。
#:
#: 満たすべき条件:
#:
#: * どの Curated Domain にも当たらない（`domain_resolution=generated`）
#: * Entity をAI合成しないと作れない
#: * deterministic Capability PlanだけではEntity/Fieldを組めない
#:
#: 実測（`provider=mock` で確認）:
#: `domain_resolution=generated` / `entity_source=synthesized(generic)`。
#:
#: **「毎日の支出を…」を使ってはならない。** `household_budget` の
#: Curated へ落ち、AI が1回も呼ばれないまま HTTP 200 が返る。
LEVEL0_PROBE = "盆栽の水やりの記録をつけたい"

#: 使ってはいけない probe。**理由ごと残す**——消すと同じ罠を踏む。
CURATED_TRAP_PROBE = "毎日の支出を記録して合計を見たい"


def _probe_runtime(base_url: str, model: str, timeout: float) -> dict[str, object]:
    """Runtime の身元を訊く。**推論の前に、何が動いているかを確かめる。**

    OpenAI 互換の `/v1/models` と、Ollama 固有の `/api/tags` の両方を試す。
    Ollama は digest（重みの識別子）を返すので、取れたら使う。
    """
    import httpx

    info: dict[str, object] = {
        "backend": "unknown", "version": "",
        # **名前と重みのハッシュを分ける**（020A1）。
        "model_id": "", "digest": "", "quantization": "",
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
                            info["model_id"] = str(
                                entry.get("model") or entry.get("name") or ""
                            )
                            # Ollama は本物の重みハッシュを返す。
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
                            info["model_id"] = str(entry.get("id") or "")
                            # **`id` を digest 扱いしない**（020A1）。
                            # `id` はただの名前である。同じ名前で中身の
                            # 違う重みを配ることは誰にでもできる。
                            # llama-server 等は digest を返さない——
                            # そのときは**空のままにする**。
                            info["digest"] = str(entry.get("digest") or "")
                            break
    except httpx.HTTPError as error:
        info["error"] = f"{type(error).__name__}: {error}"
    return info


def _resolution_from_diagnostics(diagnostics: object) -> str:
    """`decision_trace` の `domain_resolution` 段の判断を読む（020A1）。

    `"curated"` なら **Curated Domain Library が決定的に作った**——
    AI は1回も呼ばれていない。
    """
    if not isinstance(diagnostics, dict):
        return ""
    for entry in diagnostics.get("decision_trace") or ():
        if isinstance(entry, dict) and entry.get("stage") == "domain_resolution":
            return str(entry.get("decision") or "").strip().lower()
    return ""


def _structure_from_diagnostics(diagnostics: object) -> str:
    """`decision_trace` の `structure_source` 段（020A2 §3）。"""
    if not isinstance(diagnostics, dict):
        return ""
    for entry in diagnostics.get("decision_trace") or ():
        if isinstance(entry, dict) and entry.get("stage") == "structure_source":
            return str(entry.get("decision") or "").strip().lower()
    return ""


def _structure_source_of(value: str):  # noqa: ANN201
    """観測した文字列を backend の enum へ写す。**未知は UNKNOWN。**"""
    from app.ai.gateway.capability_evidence import (  # noqa: PLC0415
        GenerationStructureSource,
    )

    try:
        return GenerationStructureSource(value)
    except ValueError:
        return GenerationStructureSource.UNKNOWN


def _domain_resolution_of(need: str) -> str:
    """**Local Model を呼ぶ前に** probe の解決先を確かめる（020A1）。

    Domain 解決はキーワードによる決定的な処理であり、どの Provider を
    使っても同じ結論になる。だから `mock` で先に確かめてよい——
    **確かめるために Local Model の枠を1回使う必要は無い。**

    ここで作った文書は捨てる。`GenerationRecord` は1件増えるが、
    本番の実行は `uid` で識別するので取り違えない。
    """
    try:
        from fastapi.testclient import TestClient  # noqa: PLC0415

        from app.main import app  # noqa: PLC0415

        response = TestClient(app).post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": need,
                            "generation_options": {"provider": "mock"}}},
        )
        if response.status_code != 200:
            return ""
        return _resolution_from_diagnostics(
            (response.json().get("result") or {}).get("diagnostics")
        )
    except Exception:  # noqa: BLE001 — 事前確認の失敗で計測を止めない
        return ""


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
    # Windows PowerShellの既定CP932で、説明文中のem dash等が原因になって
    # Runtime probeより前に停止しないようにする。Evidence JSONはUTF-8。
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="FORGE Local AI Level 0 実測")
    parser.add_argument("--need", default=LEVEL0_PROBE)
    parser.add_argument("--out", default="")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    # Runtime probeとproduction Providerで同じ待ち時間を使う。既定Provider
    # 120秒だけ先に切れると、scriptの--timeout=180が名目値になる。
    os.environ.setdefault("FORGE_LOCAL_TIMEOUT_SECONDS", str(args.timeout))

    from app.ai.gateway.benchmark_evidence import Verification
    from app.ai.gateway.generation_evidence import GenerationSource, StructureProvider
    from app.ai.gateway.learning_events import Deployment
    from app.ai.gateway.local_model_evidence import (
        CURATED_DOMAIN_RESOLUTION,
        Level0Outcome,
        LocalRuntimeBackend,
        RealLocalModelRun,
        WeightIdentity,
        default_real_local_run_log,
    )
    from app.ai.gateway.tasks import ForgeTask

    base_url = os.environ.get("FORGE_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1")
    model = os.environ.get("FORGE_LOCAL_MODEL", "qwen2.5:7b-instruct")
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
    print("[1/4] Runtime を確認")
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

    # --- 1.5 probe が Curated へ落ちないことを**先に**確かめる -------
    #
    # **Local Model を呼ぶ前に確かめる。** Curated へ落ちる probe だと、
    # Runtime が動いていようがいまいが 200 が返る。測定にならない。
    print("[2/4] probe が Curated へ落ちないか（実行前）")
    pre_resolution = _domain_resolution_of(args.need)
    if pre_resolution == CURATED_DOMAIN_RESOLUTION:
        print(f"      ✗ '{args.need}' は Curated Domain Library へ解決される。")
        print("        この probe では Local Model が仕事をしたか測れない。")
        print(f"        Level 0 用の probe: {LEVEL0_PROBE}")
    else:
        print(f"      ✓ domain_resolution={pre_resolution or '(観測できず)'}")
    print()

    # --- 2. 本番経路で1件生成する ------------------------------------
    print("[3/4] Forge の本番経路で生成（provider=local）")
    generation_uid = ""
    generation_source = None
    structure_provenance = None
    structure_provider = None
    structure_task = ""
    entity_synthesis_strict_contract_passed = False
    entity_synthesis_repairs: tuple[str, ...] = ()
    structured_output_mode = ""
    validator_passed = False
    structured_ok = False
    latency_ms = 0.0
    failure = ""
    post_resolution = ""
    post_structure = ""
    observed_tasks: tuple[object, ...] = ()

    try:
        from fastapi.testclient import TestClient

        from app.ai.gateway.generation_evidence import default_generation_store
        from app.ai.gateway.learning_foundation import default_experience_store
        from app.main import app

        before = len(default_generation_store().all_records())
        # **AIRouter を通った Task を観測するための起点**（020A1）。
        # `ExperienceRecord.task` は AIRouter 自身が残す事実であり、
        # この script の主張ではない。
        experience_before = len(default_experience_store().all_records())
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

        # **主張ではなく観測。** 実際に AIRouter を通った Task を読む。
        observed_tasks = tuple(dict.fromkeys(
            record.task
            for record in default_experience_store().all_records()[experience_before:]
        ))

        if response.status_code == 200:
            result = response.json()["result"]
            structured_ok = bool(result.get("forge_document"))
            validator_passed = bool((result.get("validation") or {}).get("valid"))
            post_resolution = _resolution_from_diagnostics(result.get("diagnostics"))
            post_structure = _structure_from_diagnostics(result.get("diagnostics"))
            records = default_generation_store().all_records()
            if len(records) > before:
                generation_uid = records[-1].uid
                # **決定的な検査。** 200 が返っても、作ったのが Curated なら
                # Local Model の成果ではない（実測でそうなった）。
                generation_source = records[-1].source
                structure_provenance = records[-1].structure_source
                # **「誰が作ったか」を別に持ってくる**（020A3B §3）。
                # `AI_ENTITY_SYNTHESIS` は「AI が作った」までしか
                # 言っていない——Cloud が作った実行も同じ値である。
                structure_provider = records[-1].structure_provider
                structure_task = records[-1].structure_task
                entity_synthesis_strict_contract_passed = (
                    records[-1].entity_synthesis_strict_contract_passed
                )
                entity_synthesis_repairs = records[-1].entity_synthesis_repairs
                structured_output_mode = (
                    records[-1].entity_synthesis_structured_output_mode
                )
            print(f"      ✓ HTTP 200  ({latency_ms:.0f} ms)")
            print(f"        validator_passed={validator_passed}"
                  f" evidence_uid={generation_uid or '(無し)'}")
            print(f"        generation_source="
                  f"{generation_source.value if generation_source else '(無し)'}"
                  "   ← local_ai でなければ Local Model は動いていない")
            print(f"        structure_provider="
                  f"{structure_provider.value if structure_provider else '(無し)'}"
                  "   ← local でなければ Local Model の実績ではない")
            print(f"        structure_task={structure_task or '(無し)'}"
                  "   ← entity_synthesis でなければ構造を作っていない")
            print(f"        domain_resolution={post_resolution or '(観測できず)'}"
                  "   ← curated なら測定不成立")
            print(f"        structure_source={post_structure or '(観測できず)'}"
                  "   ← ai_entity_synthesis でなければ Level 0 ではない")
            print("        observed_tasks="
                  + (", ".join(x.value for x in observed_tasks) or "(AIを1回も呼んでいない)"))
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
    # **実際に通った Task を記録する**（020A1）。
    #
    # 以前ここは `ForgeTask.FORGE_LANGUAGE_UPDATE` を定数で書いていた。
    # `/generate` が通すのは `ForgeTask.COGNITIVE_STAGE` である
    # （`prompt_pipeline.py` の `bind(ForgeTask.COGNITIVE_STAGE, ...)`）。
    # Task ごとに Routing も評価も分ける設計なので、**別の Task の成績
    # として集計される**——存在しない実績が生まれる。
    #
    # 観測できた Task の**最初の1つ**を主張として置き、観測結果ごと
    # 残す。一致しなければ `why_not_counted()` が落とす。
    attributed_task = observed_tasks[0] if observed_tasks else ForgeTask.COGNITIVE_STAGE
    run = RealLocalModelRun(
        provider="local",
        model=model,
        task=attributed_task,  # type: ignore[arg-type]
        observed_tasks=observed_tasks,  # type: ignore[arg-type]
        domain_resolution=post_resolution or pre_resolution,
        # **「Local Model が構造を作った」を Provider 名から推定しない**
        # （020A2 §3）。決定的な Capability Plan が構造を組み、
        # Design Intent だけ Local を呼んだ実行は Level 0 ではない。
        # **Evidence Store の記録を優先する。** Decision Trace は
        # リクエスト単位の表示物であり、残る側ではない。取れなければ
        # trace から拾う（どちらも無ければ UNKNOWN のまま）。
        structure_source=(
            structure_provenance or _structure_source_of(post_structure)
        ),
        runtime_backend=backend_map.get(
            str(probe["backend"]), LocalRuntimeBackend.UNKNOWN,
        ),
        runtime_version=str(probe["version"]),
        model_id=str(probe["model_id"]) or model,
        # **名前を digest 扱いしない**（020A1）。取れなければ空のまま。
        model_digest=str(probe["digest"]),
        quantization=str(probe["quantization"]),
        # **実際に LOCAL で走ったときだけ LOCAL と書く。**
        deployment=Deployment.LOCAL if probe["reachable"] else Deployment.UNKNOWN,
        latency_ms=latency_ms,
        structured_output_ok=structured_ok,
        validator_passed=validator_passed,
        generation_evidence_uid=generation_uid,
        generation_source=generation_source or GenerationSource.UNKNOWN,
        # **構造を作った Provider と stage を、推測せずそのまま運ぶ**
        # （020A3B §3）。取れなければ既定（NONE / 空）のままにする——
        # 「記録し損ね」を「Local だった」へ倒さない。
        structure_provider=structure_provider or StructureProvider.NONE,
        structure_task=structure_task,
        entity_synthesis_strict_contract_passed=(
            entity_synthesis_strict_contract_passed
        ),
        entity_synthesis_repairs=entity_synthesis_repairs,
        structured_output_mode=structured_output_mode,
        host_id=str(host["host_id"]),
        ram_total_mb=int(host["ram_total_mb"]),
        vram_total_mb=int(host["vram_total_mb"]),
        # 実測として記録してよいのは、実際に往復できたときだけ。
        verification=Verification.REAL if probe["reachable"] else Verification.UNVERIFIED,
    )
    recorded = default_real_local_run_log().record(run)

    print("[4/4] Real Local Model run として数えてよいか")
    if recorded.counts_as_real_local:
        print("      ✓ 数える")
    else:
        print("      ✗ 数えない。理由:")
        for reason in recorded.why_not_counted():
            print(f"        - {reason}")
    print(f"      weight_identity   : {recorded.weight_identity.value}")
    if recorded.weight_identity is WeightIdentity.UNVERIFIED:
        print("        （Runtime が重みのハッシュを返さない。**名前は"
              "digest ではない。** Level 0 は通りうるが Level 0.5 は不可）")
    print(f"      ready_for_baseline: {recorded.ready_for_baseline}"
          "   ← Level 0.5（Baseline Benchmark）へ進めるか")
    print()

    outcome = default_real_local_run_log().level0()
    evidence = {
        "task": "FORGE-020A Level 0",
        "level0_scope": (
            "Runtime → LocalModelProvider → Provider Registry → AIRouter → "
            "production /generate → Validator → GenerationRecord("
            "source=local_ai, structure_provenance=local_ai)"
        ),
        "level0_outcome": outcome.value,
        "real_local_model_runs": default_real_local_run_log().count(),
        # **Level 0.5 は別**（020A1）。BenchmarkRun / LocalPromotionGate は
        # Level 0 の完成条件から外した。1件の成功では PROMOTED にしない。
        "baseline_ready_runs": len(default_real_local_run_log().baseline_ready_runs()),
        "probe": {
            "need": args.need,
            "domain_resolution_before": pre_resolution,
            "domain_resolution_after": post_resolution,
            "is_curated_trap": pre_resolution == CURATED_DOMAIN_RESOLUTION,
            "structure_source_after": post_structure,
            "level0_probe_recommended": LEVEL0_PROBE,
            "known_curated_trap": CURATED_TRAP_PROBE,
        },
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
    print(f"  Level 0.5 へ渡せる実行  : {evidence['baseline_ready_runs']}")
    print(f"  evidence               : {out}")
    print("=" * 66)
    if outcome is Level0Outcome.INVALID_PROBE:
        print()
        print("  **測定が成立していない。** Local Model の失敗ではない。")
        print("  Software structureをCurated/決定的経路が作ったため、Local Model")
        print("  のstructure generationを測れていない。Level 0は据え置く。")
        print(f"  Level 0 用の probe: {LEVEL0_PROBE}")
    elif outcome is not Level0Outcome.PASSED:
        print()
        print("  Level 0 は未到達のまま。docs の UNVERIFIED を変えないこと。")
    # **INVALID_PROBE と FAILED を同じ終了コードにしない。**
    # 「測れなかった」と「測ったら駄目だった」を CI で区別できるように。
    if outcome is Level0Outcome.PASSED:
        return 0
    return 2 if outcome is Level0Outcome.INVALID_PROBE else 1


if __name__ == "__main__":
    raise SystemExit(main())
