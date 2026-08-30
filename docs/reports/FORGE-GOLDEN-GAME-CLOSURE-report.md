# FORGE Golden Game Closure Report

Date: 2026-08-30

## Verdict

**Golden request gate: PASS.**

Target request:

> 植物を育てながら音を組み合わせるゲームを作りたい

The original failure mode was semantic flattening: a game-like request could collapse into ordinary CRUD/form behavior. The current production generation path now preserves the two behaviors that distinguish this request from a static data tool:

- autonomous deterministic time progression via `simulate.loop` / `simulation_loop`
- interactive simultaneous bundled-audio layering via `interact.audio_mix` / `audio_mixer`

This PASS applies to the request above. It does **not** claim that Forge can export a newly composed audio/image asset. `effect.media_compose` remains intentionally `MISSING` and requests such as 「合成して書き出す」 are surfaced as a capability gap rather than silently treated as the mixer.

## Semantic and planning closure

`simulate.loop` is now an implemented semantic capability backed by an actual Forge Language node and Flutter runtime. Capability planning has a dedicated `simulations` axis, and `CapabilityPlan.to_dict()` now serializes it so Decision Trace / evidence cannot lose the simulation requirement.

Regression: `forge_ai/tests/test_simulation_plan_evidence.py` requires the Golden request to produce `("simulate.loop",)` and serialize it as `["simulate.loop"]`.

The Japanese surface 「合成」 is now mapped to the `combine` activity. A request such as 「音を合成して書き出したい」 therefore requires `effect.media_compose`; it remains visible in `missing` instead of disappearing from the plan.

## Runtime closure

Simulation path:

`Need -> CapabilityPlan.simulations -> simulate.loop -> simulation_loop -> ForgeSimulationEngine -> ForgeSimulationBinding -> ForgeRuntimeState(number) -> simulation_progress`

The engine is deterministic fixed-step logic, receives elapsed time explicitly, bounds catch-up work, and has explicit start/pause/reset semantics. The Flutter lifecycle owns the periodic timer and cancels it on disposal.

Audio path:

`Need -> interact.audio_mix -> audio_mixer -> audioplayers -> bundled WAV assets`

The runtime supports the closed bundled tracks `pulse`, `chime`, and `bass`. Multiple players are independent, so layers can remain active concurrently. Arbitrary user media import is outside this capability and is not claimed.

## Exact production generation proof

The evidence workflow generated the document through the production API wiring, not from a hand-authored fixture. The exact document reported Forge Language version `1.15` and mechanically contained all required runtime widgets:

- `simulation_loop`
- `simulation_progress`
- `audio_mixer`

Workflow log marker:

`FORGE_GOLDEN_DOCUMENT required_widgets=PASS version=1.15`

## Real Chrome audio proof

Workflow run: **33287000678**  
Job: **99191815435**  
Head SHA: `91a38372bc378c966d177c2665f2a98d1398979b`

The probe built a real Flutter Web application so Flutter's generated web plugin registrant initialized the actual `audioplayers_web` backend. Headless Chrome fetched both real bundled files and the application reported success after starting both players:

- `forge_tone_pulse.wav` -> HTTP 200
- `forge_tone_chime.wav` -> HTTP 200
- `/report?status=pass` -> HTTP 204
- marker: `FORGE_AUDIO_E2E compiled_web_two_layers=PASS`

Evidence artifact:

- ID: **9724753751**
- name: `forge-real-chrome-audio-evidence`
- digest: `sha256:d9ba786e41e116a21502b1e90062ed43571ac2a30ead7eb50aef8c2fb4508df1`

This replaced an invalid earlier proof path where `flutter test` could raise `MissingPluginException` because the test harness did not run the application plugin registrant.

## Exact real-Chrome visual proof

Workflow run: **33287242065**  
Job: **99192456927**  
Head SHA: `63902d09e8638c7dce9d79ee0d72e6d65cf27bf2`

The workflow:

1. generated the exact current Golden document through production API wiring;
2. copied that exact JSON into a real Flutter Web build;
3. compiled the checked-in Forge renderer;
4. rendered the application in real headless Chrome;
5. captured a PNG at exactly **390 x 844**;
6. verified the application callback and PNG header/dimensions.

Objective marker:

`FORGE_GOLDEN_VISUAL compiled_web=PASS png_bytes=26857 viewport=390x844`

Evidence artifact:

- ID: **9724821297**
- name: `forge-golden-game-visual-evidence`
- digest: `sha256:fe220d16e553cd0e8e09daa21f1a3201ce5642e5f6f0bf6ca8fe04caeafde77b`
- contains the generated Forge Document, 390x844 PNG, browser callback, and browser/server logs.

An earlier Flutter widget-harness visual probe successfully rendered and wrote a PNG but hung during test-root teardown while the periodic simulation node was active. It was not used as the final PASS criterion. The final proof uses a compiled Flutter Web application in Chrome and has no test-harness teardown dependency.

## Cleanup

One-shot audio/visual workflows, temporary browser evidence entrypoints/server, failed integration-driver experiments, and the superseded widget-harness Golden probe were removed after durable Actions artifacts were produced. Production simulation/audio runtime and their ordinary unit/regression tests remain.

## Remaining boundaries

- `effect.media_compose`: **MISSING**. Exporting/rendering a newly composed audio/image file is not implemented.
- arbitrary user-supplied audio import: not claimed by `interact.audio_mix`.
- physical development-PC execution: **UNVERIFIED from this environment** because the remote session cannot access that machine.

These boundaries do not invalidate the Golden request gate because that request asks for interactive sound combination in a growing game, not exported media composition.
