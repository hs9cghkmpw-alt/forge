# Forge Handoff — current Source of Truth

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current task: **GENERAL APP MODE — GA-1 Logic Core. Natural-language app generation breadth is now the primary roadmap target.**
- Execution spec: `docs/spec/FORGE-GENERAL-APP-MODE.md`.
- Architecture basis: `docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md`.
- Product target: user need -> semantic capability -> runtime primitives -> generated app -> validator/test/build/runtime/visual evidence -> bounded repair; unsupported needs must become explicit Capability Gaps rather than false success.
- First GA-1 Golden acceptance request: `毎月の収入と支出を記録して、残高を自動計算し、残高がマイナスなら警告を表示する家計アプリを作って`.
- GA-1 scope: condition/compare, if/else, derived/computed state, filter/sort/aggregate/arithmetic, event-to-state transitions, compiler/runtime/validator integration.
- Previous Golden game target request: `植物を育てながら音を組み合わせるゲームを作りたい`
- Previous Golden Generated App Quality Gate: **PASS**.
- Exact production-generated Forge Document version for that evidence: **1.15**.
- Required runtime widgets proved in that generated document: `simulation_loop`, `simulation_progress`, `audio_mixer`.
- `simulate.loop`: **IMPLEMENTED** with deterministic fixed-step engine, runtime-state binding, real Flutter lifecycle, visible progress, and serialized CapabilityPlan evidence.
- `interact.audio_mix`: **PARTIAL by design** — simultaneous bundled track playback is implemented and real-Chrome verified; arbitrary user audio import is not claimed.
- `effect.media_compose`: **MISSING** — exporting/rendering a newly composed media asset is still an explicit capability gap.
- Japanese surface `合成` is mapped to semantic activity `combine`; requests such as `音を合成して書き出したい` therefore keep `effect.media_compose` in the missing plan instead of silently collapsing to the mixer.
- Physical/user-PC validation remains **UNVERIFIED from this environment**.

## General App Mode execution rule

Do not try to reach broad app coverage by adding one bespoke Widget per requested app. Prefer reusable Runtime Primitives. The execution order is currently:

1. GA-1 Logic Core
2. GA-2 Navigation + Persistent Data
3. GA-3 External Service Effects
4. GA-5 Rich Presentation
5. GA-4 Device Capabilities
6. GA-6 Media + Game Runtime
7. GA-7 Safe Build-Time Self-Extension

`Capability != Widget`. Semantic needs must decompose to DATA / TRANSFORM / VIEW / ENCODING / EFFECT / SIMULATE primitives. PARTIAL/MISSING truthfulness rules remain mandatory.

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
- Digest: `sha256:bb66c4b1fb38dec4f70783b813b15f16fd7d82f20adee98687d80cded89f6bd9`
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

The previous Golden game request is closed. Do not reopen it unless a regression occurs.

The active next work is GA-1 Logic Core:

1. audit current state/action/expression surfaces and establish the smallest general expression AST rather than domain-specific conditions;
2. add compare + boolean + arithmetic expression evaluation as a pure/deterministic runtime primitive;
3. add derived/computed state and conditional rendering/branching bindings;
4. wire semantic/capability planning and compiler generation for the GA-1 Golden household-budget request;
5. add validator/parser/runtime/compiler tests, then generated-app runtime evidence;
6. only after the GA-1 slice is green move to GA-2 persistence/navigation.

Separate later boundaries remain:

- `effect.media_compose` real export path;
- arbitrary user-supplied audio import;
- physical-PC verification;
- privileged/device effects require explicit policy and real platform evidence.

Final closure rule for every slice: the **last branch HEAD** after bookkeeping/cleanup must pass persistent `.github/workflows/ci.yml`; do not write the final run ID back into this file because doing so creates a newer unverified HEAD.
