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

## Physical-PC checkpoint — 2026-08-31

A real Windows PC at ぱすとらる was used to continue Forge verification. The durable checkpoint is:

- `docs/evidence/PHYSICAL-EXECUTION-CHECKPOINT-20260831.md`

Observed session results:

- `flutter analyze`: **PASS / clean**
- `flutter test`: **PASS — 546 tests**
- `flutter build web`: **PASS**
- `flutter run -d chrome`: **BLOCKED before successful app startup**
- actual Chrome-rendered app: **UNVERIFIED**
- manual visual/behavioral interaction: **NOT EXECUTED**

Current physical blocker: Flutter SDK / web SDK path resolution through Puro. An observed path was shaped like:

```text
../../../.puro/envs/stable/flutter/bin/cache/flutter_web_sdk/
```

Important evidence boundary: the exact local checkout SHA used for that physical run was **not durably captured**, so the next session must run `git rev-parse HEAD` before attaching the physical results to a specific commit.

**Resume from here, do not repeat completed work by default:** start a PowerShell transcript, capture branch/HEAD and Flutter environment identity (`where.exe flutter`, `flutter --version`, `flutter doctor -v`), fix the Puro/Flutter SDK path issue, then rerun `flutter run -d chrome`. Only after the app visibly loads should physical runtime be marked PASS. After base startup succeeds, continue into the self-extension -> acquired capability -> real Flutter/Dart runtime path.

## Self-extension: what the build pipeline now actually proves (020E-2/3)

`SynthesizingBuildTimeImplementer` is the **production** `ExtensionImplementer`.
Until it existed, the only implementer ever injected into `extension_cycle` was
a test closure.

Proven with **real subprocesses** (no fake builder/loader):

```
test           python -m unittest discover   exit 0
build          python -m compileall -q .     exit 0
runtime_probe  python probe.py               exit 0   stdout: "runtime probe ok"
-> manifest promoted, promotion_blockers empty, activation loaded
```

Negative proof: a failing generated test, a failing probe, or source that does
not compile all leave the manifest **unpromoted with `activation is None`**;
later phases do not run after an earlier phase fails; an unsupported host
language is refused rather than defaulted to Python; regurgitated shipped
source raises `PreexistingSourceError`.

Capability prerequisites are now **declared in the canonical catalog**
(`CapabilityDefinition.required_fields`) instead of branching on a capability
name in the planner. The former `if "view.map" in directly_requested:` branch is
gone — an acquired capability could never have that branch written for it, so it
could never stand on its own. This is **not** permission to geocode: the map
capability declares explicit numeric latitude/longitude, and a place name alone
still produces no coordinate fields.

**Still unproven — do not read this as a completed self-extension E2E:**

| Item | State |
|---|---|
| That a **real model** authored the generated source | **UNPROVEN.** The provider here is a Test Double; the implementation string is supplied by the test |
| Natural-language request -> acquisition -> retry -> reuse | **PROVEN** (real build; `capability_plan` consults the registry on retry) |
| Acquired capability can contribute a widget to the generated document | **PROVEN at compiler/document-emission level.** Compiler capability-name branching is gone and a registered contribution can emit its widget through the production IR/compiler path |
| Validator PASS for a genuinely acquired/new widget | **UNPROVEN** |
| Flutter runtime rendering evidence for a genuinely acquired/new widget | **UNPROVEN** |
| Second different request reuses without a second build | **PROVEN** (synthesis=1, build=1, provider_calls=1 across two different requests) |
| Real model authorship runs for `capability_implementation` | **0** |

Evidence: `docs/evidence/SELF-EXTENSION-BUILD-PIPELINE-20260831.md`.

Next real bottlenecks — there are **two**, not one:

1. **Real model authorship.** Executing the `capability_implementation` stage
   against a real model. Plumbing and gates are in place; what is missing is a
   machine that can run one (`docs/MACHINE-INDEPENDENT-POLICY.md`).
2. **The acquired capability must be renderable by the Dart runtime.**
   The compiler-side `if "view.map"` branch is **now gone** (020E-5): widget
   emission is declaration-driven, and an acquired capability can register its
   own contribution, which was verified. `view.map` output is unchanged down to
   property order. What remains is that a declaration only says *which widget to
   emit* — whether the Dart runtime can **render** a genuinely new widget still
   requires rebuilding the Flutter side through BUILD_TIME. That is untouched.

   While doing this a coverage hole surfaced: removing the shipped map
   declaration left **all 1984 backend tests and all forge_ai tests passing**,
   i.e. the `view.map` emission path had never been tested at all. It is now.

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

**Still unproven:** real-model-authored unseen capability source -> real build/probe ->
PROMOTED -> retry -> real Flutter runtime rendering -> reuse without a second build.

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

Canonical CI run `33340554937` on head `c2ec1529ce1c3eb97d456dc667a03cd1a3ee1ac7` completed successfully
(4/4 jobs):

- backend + forge_ai Python 3.11: PASS
- backend + forge_ai Python 3.12: PASS
- backend smoke: PASS
- Flutter analyze/test/web build: PASS

Earlier green heads in this slice: `33340416175` (`8ea7fc9d`), `33339800860` (`d8a9341`), `33339385724` (`83683e1`), `33339175463` (`5827f2d`),
`33338884887` (`2fba6f1`), `33328203164` (`8e3c876`).

A later HEAD must receive its own canonical CI before being called green.

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

1. **Finish the current physical-PC startup checkpoint first:** fix the Puro/Flutter SDK path issue and get `flutter run -d chrome` to a visibly rendered app while preserving the transcript and exact Git SHA.
2. **Then prove one real unseen request end-to-end** through `Gap -> extension -> promotion -> retry -> working generated product`, including Validator and real Flutter/Dart runtime evidence.
3. Convert boolean extension evidence flags into stronger evidence references/artifact identities where practical.
4. Continue GA-2 persistent data/navigation and later capabilities only as reusable primitives.
5. Rerun Whole Scan whenever new capability routes or fallbacks are introduced.

## Final closure rule

A branch state is green only when persistent `.github/workflows/ci.yml` passes for that exact descendant HEAD. Pending/unmeasured evidence is never PASS.
