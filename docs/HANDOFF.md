# Forge Handoff — current Source of Truth

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current task: **Golden game closure complete; preserve evidence and keep ordinary CI green.**
- Golden target request: `植物を育てながら音を組み合わせるゲームを作りたい`
- Golden Generated App Quality Gate for that request: **PASS**.
- Exact production-generated Forge Document version: **1.15**.
- Required runtime widgets proved in the generated document: `simulation_loop`, `simulation_progress`, `audio_mixer`.
- `simulate.loop`: **IMPLEMENTED** with deterministic fixed-step engine, runtime-state binding, real Flutter lifecycle, visible progress, and serialized CapabilityPlan evidence.
- `interact.audio_mix`: **PARTIAL by design** — simultaneous bundled track playback is implemented and real-Chrome verified; arbitrary user audio import is not claimed.
- `effect.media_compose`: **MISSING** — exporting/rendering a newly composed media asset is still an explicit capability gap.
- Japanese surface `合成` is mapped to semantic activity `combine`; requests such as `音を合成して書き出したい` therefore keep `effect.media_compose` in the missing plan instead of silently collapsing to the mixer.
- Physical/user-PC validation remains **UNVERIFIED from this environment**.

## Golden closure evidence

Durable summary:

- `docs/reports/FORGE-GOLDEN-GAME-CLOSURE-report.md`
- `docs/evidence/golden/forge-golden-game-closure-20260830.json`

### Real Chrome audio

- Workflow run: `33287000678` = **SUCCESS**
- Job: `99191815435`
- Evidence artifact: `9724753751`
- Digest: `sha256:d9ba786e41e116a21502b1e90062ed43571ac2a30ead7eb50aef8c2fb4508df1`
- Objective marker: `FORGE_AUDIO_E2E compiled_web_two_layers=PASS`
- Both bundled `pulse` and `chime` WAV assets returned HTTP 200 and remained layered in the compiled Flutter Web application.

### Exact real-Chrome visual

- Workflow run: `33287242065` = **SUCCESS**
- Job: `99192456927`
- Evidence artifact: `9724821297`
- Digest: `sha256:fe220d16e553cd0e8e09daa21f1a3201ce5642e5f6f0bf6ca8fe04caeafde77b`
- Production-generation marker: `FORGE_GOLDEN_DOCUMENT required_widgets=PASS version=1.15`
- Visual marker: `FORGE_GOLDEN_VISUAL compiled_web=PASS png_bytes=26857 viewport=390x844`
- Artifact contains the exact generated Forge Document, 390x844 PNG, browser callback, and browser/server logs.

The final visual proof does **not** use the earlier Flutter widget-test harness. That harness could render and write a PNG but hung during teardown while a periodic simulation node was alive. The accepted evidence compiles the exact generated document into a real Flutter Web application and renders it in real headless Chrome, avoiding that harness-specific lifecycle artifact.

## Capability planning truth

`CapabilityPlan` has orthogonal `views`, `interactions`, `effects`, and `simulations` axes. `CapabilityPlan.to_dict()` serializes `simulations`, and `forge_ai/tests/test_simulation_plan_evidence.py` locks the Golden request to:

```text
simulations == ("simulate.loop",)
to_dict()["simulations"] == ["simulate.loop"]
```

This prevents the simulation requirement from being requested internally and then disappearing from Decision Trace / evidence.

## Prior agent/runtime milestones preserved

### FORGE-020B — real Tool-Using Local Agent

- GitHub-hosted real Ollama/Qwen run `33227448429`: **SUCCESS / PASS**
- Durable evidence: `docs/evidence/agent020b/agent020b-20260829-015345.json`
- Artifact: `9707382693`
- Digest: `sha256:b76d0184c3eac34a3c801a8382c716e8fc530622c731d7d406eef35a2b6cd469`
- Physical-PC leg: **UNVERIFIED**

### FORGE-020D/020E — objective generated repair/runtime

- Real generated Flutter repair/runtime run `33236863659`: **SUCCESS / PASS**
- Durable evidence: `docs/evidence/agent020d/forge-020d-real-evidence-20260829.json`
- Artifact: `9710186190`
- Digest: `sha256:bb66c4b1fb38dec4f70783b813b15f16fd530622c731d7d406eef35a2b6cd469`
- Objective trajectory: `test fail -> repair -> test pass -> build pass -> runtime pass`
- The old episode's visual outcome remains historically `unknown`; it is not rewritten. The later Golden-specific compiled-Web visual proof above is a separate evidence run.

Reports:

- `docs/reports/FORGE-020B-TOOL-USING-LOCAL-AGENT-report.md`
- `docs/reports/FORGE-020D-GENERATED-REPAIR-LOOP-report.md`

## Cleanup state

Completed one-shot work has been removed from the branch:

- temporary simulation-evidence patch workflow
- temporary Chrome-audio workflow
- temporary Golden-visual workflow
- temporary audio/Golden browser entrypoints
- temporary same-origin browser evidence server
- superseded browser widget/integration harnesses
- superseded widget-harness Golden render probe
- temporary dev dependencies added only for those discarded harnesses

Persistent production runtime, ordinary unit/regression tests, durable reports/evidence, and the reusable production Golden fixture generator remain.

## Remaining boundaries / next work

The Golden request itself is closed. Do not reopen it unless a regression occurs. The remaining work belongs to later capabilities and product hardening:

1. `effect.media_compose` — implement real exported media composition only when Forge has an actual safe runtime/renderer path; do not claim the interactive mixer satisfies export.
2. Arbitrary user-supplied audio import — separate capability/safety design if required.
3. Physical-PC verification — run only from the actual machine and preserve evidence before marking PASS.
4. Continue ordinary product roadmap after final branch CI is green.

Final closure rule: the **last branch HEAD** after bookkeeping/cleanup must pass persistent `.github/workflows/ci.yml`; the exact final run ID is reported externally rather than written back into this file, because writing it would create a newer unverified HEAD.
