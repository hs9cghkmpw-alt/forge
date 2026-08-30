# Forge Handoff — current Source of Truth

## Canonical product invariant

Forge's goal has **not switched** to a new mode or to a finite app-coverage program.

> **持っている能力は組み合わせる。足りない能力は作る。作った能力は検証し、再利用可能な Forge Capability として取り込む。**

Everything else—Golden apps, widgets, GA phases, schemas, runtime primitives, local models, benchmarks—is an implementation mechanism or test surface under that invariant.

Canonical hierarchy:

1. `docs/FORGE-CORE-CONSTITUTION.md`
2. `docs/PRODUCT-DIRECTION.md`
3. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
4. `docs/LEARNABLE-LOCAL-AI-VISION.md`
5. `docs/FORGE-CURRENT-STATE.md`
6. this handoff

Operational scan term:

- **全体スキャン / Whole Scan** = `docs/FORGE-WHOLE-SCAN-PROTOCOL.md`

## Current branch / active engineering slice

- Branch: `claude/forge-master-handoff-k46jns`
- Active slice: self-extension production loop + GA-1 logic closure.
- Execution program: `docs/spec/FORGE-GENERAL-APP-MODE.md`.
- Self-extension basis: `docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md`.

`FORGE-GENERAL-APP-MODE.md` is **not a new product goal**. Missing-capability synthesis is cross-cutting and must not be postponed until the end of a phase list.

## Determination: map so far is activation, not generation (020E, 2026-08-30)

Ordered explicitly by the CEO before any further self-extension work.

**`view.map` to date is activation of pre-existing shipped code, not
capability generation.** Evidence in repo:

- `BuildTimeCapabilityArtifact(...)` is constructed in **tests only**
  (3 sites); there is **no production construction site**;
- `ExtensionImplementer` is a Protocol; the only implementer injected is a
  test closure;
- `test_self_extension_loop.py` promotes `view.map` through
  `ExtensionRoute.DECLARATIVE` — **no source is generated**;
- the v1.16 map language/validator/parser/registry/runtime/compiler wiring
  was written by earlier human commits and shipped in the repo.

`ManagedBuildTimeImplementer` genuinely proves *verification and intake* of a
given artifact via real subprocesses. It does **not** prove that Forge wrote
the implementation.

Full record: `docs/reports/FORGE-020E-CAPABILITY-ARTIFACT-SYNTHESIS-report.md`.

## The generation stage is now present (but not yet proven end to end)

`forge_ai/core/orchestration/capability_artifact_synthesis.py` fills the gap
between Capability Gap and BUILD_TIME.

- capability-agnostic: takes only a contract pulled mechanically from the
  canonical catalog; a static test forbids capability-id literals in the
  executable code, so `if capability_id == "view.map"` cannot be introduced
  as the general mechanism;
- `known_source_digests` is a **required** argument: source that is
  byte-identical (after whitespace normalisation) to shipped source raises
  `PreexistingSourceError`, so regurgitated repo code cannot be counted as
  generation;
- unusable responses return `None` — implementation without tests, tests
  without implementation, empty output, unsafe paths;
- capability identity comes from the contract, never from model self-report.

**Still unproven:** unseen request → generated source → real build/probe →
PROMOTED → retry → reuse without a second build. Real Local Model runs
remain **0**.

## Self-extension implementation now present

The production architecture now contains these reusable stages:

```text
Capability Gap
 -> CognitivePipelineNeedsExtension
 -> ExtensionCandidate
 -> ExtensionManifest
 -> route-specific implementation
 -> evidence gate
 -> VERIFIED
 -> PROMOTED
 -> executable activation
 -> registry install
 -> original request retry
 -> repeated loop until all gaps close or progress stops
```

Implemented guardrails include:

- unresolved semantics cannot skip decomposition;
- unverified manifests cannot promote;
- sensitive capability promotion requires safety evidence;
- manifest-only promotion is insufficient: executable activation is required;
- BUILD_TIME capabilities require a loaded runtime/build attestation before reuse;
- capability identity may not change during implementation;
- the same unresolved gap after promotion is treated as no progress;
- retry cycles are bounded;
- promoted declarative capabilities can be persisted and integrity-checked on reload.

Relevant production surfaces include:

- `forge_ai/core/orchestration/extension_plan.py`
- `extension_manifest.py`
- `extension_activation.py`
- `extension_registry.py`
- `extension_cycle.py`
- `self_extension_loop.py`
- `declarative_extension.py`
- `declarative_activation.py`
- `extension_store.py`
- `build_time_extension.py`

The multi-gap regression in `forge_ai/tests/test_self_extension_loop.py` proves that a request needing more than one missing capability is not completed after acquiring only the first gap.

## GA-1 logic vertical slice

GA-1 is now wired through the generated document path rather than existing only as a standalone expression helper.

```text
Python GA-1 Logic model
 -> ForgeIRDocument.logic
 -> generated JSON `logic`
 -> Backend Validator
 -> Dart ForgeDocument parser
 -> ForgeLogicRuntime
 -> Renderer `visible_when`
```

Implemented reusable semantics:

- literal/state references
- arithmetic and comparison
- boolean composition
- aggregate operations
- derived values computed from current mutable state
- conditional widget visibility

Derived values are not copied into mutable state, so they do not create a second Source of Truth.

Validator behavior is fail-closed:

- `logic` is accepted only for Forge Language v1.15+;
- unknown expression kinds/operators are rejected;
- aggregate field references are constrained to their valid context;
- expression depth and logic-entry count are bounded.

Key commits:

- `2abf295132d3f83ced0f65863e651f5b24b37b1b` — deterministic expression engine
- `8dc9e38bab6aa38b0d6119282911422cfb4b1c86` — runtime state binding
- `ebe90998c321cbd886dbdbae8b486b641791e3a7` — document/parser/renderer GA-1 wiring
- `a83396ed3f7b1e21c48118a9c75d4049101db472` — backend GA-1 validator

## Whole Scan status

The first Whole Scan corrected the highest-risk strategic drift:

- legacy JSON-only/product-boundary wording was demoted;
- undefined requirements may not be rewritten into convenient templates;
- only an explicitly planned CHECKLIST may enter the legacy checklist compiler;
- unresolved RECORD_ENTITY / UNKNOWN structure becomes Capability Gap;
- Capability Gap is a first-class `CognitivePipelineNeedsExtension` outcome, not generic failure;
- `SolutionShape` is a downstream legacy representation chooser, not the product capability catalog;
- self-extension is evidence-gated and retry-oriented rather than a claim-only registry;
- stale comments/docstrings that still describe automatic checklist fallback are being removed as part of final scan cleanup.

See `docs/reports/FORGE-WHOLE-SCAN-20260830-report.md` for the full scan record.

## CI evidence

Canonical CI run `33328203164` on head `8e3c87616ef3f5ab9b9cad594b46cc609bda7c87` completed successfully:

- backend + forge_ai Python 3.11: PASS
- backend + forge_ai Python 3.12: PASS
- backend smoke: PASS
- Flutter analyze/test/web build: PASS

A later documentation/comment-cleanup HEAD must receive its own canonical CI before being called green.

## Existing Golden game closure remains valid

Previous Golden request:

> `植物を育てながら音を組み合わせるゲームを作りたい`

Durable evidence remains in:

- `docs/reports/FORGE-GOLDEN-GAME-CLOSURE-report.md`
- `docs/evidence/golden/forge-golden-game-closure-20260830.json`

Truth status remains:

- `simulate.loop`: IMPLEMENTED
- `interact.audio_mix`: PARTIAL
- `effect.media_compose`: MISSING
- physical/user-PC verification: UNVERIFIED

Do not treat that Golden as a template or as proof of general software-generation completion.

## Next engineering target after this scan pass

Do not expand patterns for their own sake. Continue from the real goal backward:

1. prove one real unseen request end-to-end through `Gap -> extension -> promotion -> retry -> working generated product` with runtime evidence;
2. convert boolean extension evidence flags into stronger evidence references/artifact identities where practical;
3. continue GA-2 persistent data/navigation and later capabilities only as reusable primitives;
4. rerun Whole Scan whenever new capability routes or fallbacks are introduced.

## Final closure rule

A branch state is green only when persistent `.github/workflows/ci.yml` passes for that exact descendant HEAD. Pending/unmeasured evidence is never PASS.
