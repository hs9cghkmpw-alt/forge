# FORGE-020A3 / CAPABILITY-COMPOSITION-AND-TYPED-PROVENANCE Report

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `01c45421749905bb553c84dabed56c757173e5fd`
- Final HEAD: commit containing this report
- Date: 2026-08-27

## Implementation / production wiring

`CognitiveContext` carries typed `StructureProvenance(source, provider, task)` and
`EntitySynthesisAttempt`. Actual curated, deterministic-plan and accepted synthesis
branches write it at structure creation. Production Evidence reads only this typed value;
`entity_source` remains diagnostic and cannot change Evidence truth.

`forge_ai/core/semantics/capabilities.py` is canonical. The backend adapter rejects
duplicate ids, ids missing from the canonical catalog, and missing widget bindings for
implemented capabilities that require them. forge_ai does not import backend.

Combination PlanShape values were removed. `StructuralMode` is orthogonal to fields,
views, interactions, effects, runtime behaviors, partial and missing ids. The required
reproduction retains `view.list`, `view.total`, `view.group_compare`, and `view.trend`.
Typed capability usage includes `record.entity` and every field capability.

Critical missing capabilities use the existing `needs_confirmation` result and explicitly
say the request is not yet built as requested. Privacy-safe Evidence is written. Entity
synthesis rejection uses a closed enum at empty-output, invalid-identifier and no-valid-
fields boundaries; raw model output is never stored. Self-Extension/QLoRA were not started.

Level 0.5 accepts CPU benchmarks. GPU/VRAM are performance/model-size Evidence, not gates.

## Verification / mutation

- Reproduction: PASS; all four views retained.
- forge_ai full: **569 passed**; focused semantic/entity suite: **64 passed**;
  FORGE-020A3 focused mutation suite: **3 passed**.
- compileall and `git diff --check`: PASS.
- Guards cover duplicate canonical/adapter ids, unknown adapter ids, missing required
  bindings, second/third view drop and view shadowing, and typed provenance wiring.
- backend attempt: **1289 tests ran; 45 import errors** because active Python lacks existing
  dependencies (`pytest`, `httpx`, `fastapi`). No package was installed. Backend full and
  Ruff are **UNVERIFIED**.
- Flutter analyze and `--no-pub` produced no output and did not finish; interrupted.
  Flutter tests/build web are **UNVERIFIED**.
- Browser/Playwright and Real Local Model: **UNVERIFIED**; absent and not installed.
- UI/renderer/generated appearance did not change; visual capture is out of scope.

## GitHub / CI / next task

- Implementation commit: `8ca31a7e02db767bf64c51ace3156c0ab9181e93`.
- Push: PASS. Post-push `git fetch origin`: PASS. Implementation local/remote HEAD:
  equal. Working tree after implementation commit: clean.
- GitHub commit API: commit and diff observed. Workflow runs/status checks returned zero
  entries for this SHA, so CI is **UNVERIFIED (run not observed)**, not green.

Next task is independent review and dependency-complete verification without weakening
Level 0 truth.
