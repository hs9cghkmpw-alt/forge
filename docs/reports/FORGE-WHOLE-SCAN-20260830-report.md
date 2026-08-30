# Forge Whole Scan Report — 2026-08-30

Status: IN PROGRESS / first repository-wide strategic alignment pass
Branch: `claude/forge-master-handoff-k46jns`

## 1. Canonical invariant

Whole Scan evaluates Forge against one non-negotiable product invariant:

> **持っている能力は組み合わせる。足りない能力は作る。作った能力は検証し、再利用可能な Forge Capability として取り込む。**

The main anti-pattern is **goal substitution**:

```text
easy/local implementation
 -> work concentrates on it
 -> it becomes the de facto goal
 -> original desired outcome is silently narrowed
```

Golden cases, widgets, JSON schemas, solution shapes, GA phases and specific app types are implementation/test surfaces, not the product goal.

## 2. Scope scanned in this pass

Reviewed or sampled:

- canonical product/architecture documents
- `docs/HANDOFF.md`
- `docs/spec/FORGE-GENERAL-APP-MODE.md`
- `docs/AI.md`
- `PROMPTS/system/core_directive.v1.md`
- `backend/app/ai/README.md`
- repository-level README
- runtime state / renderer / state store
- general expression implementation and tests
- `forge_ai/core/ir/solution_shape.py`
- `forge_ai/core/ir/forge_language_compiler.py`
- `forge_ai/core/orchestration/pipeline_orchestrator.py`
- semantic capability planning / semantic roles / capabilities
- solution-shape tests
- CI evidence for the new expression/runtime binding work
- repository search for concrete self-extension / capability-promotion implementation surfaces

This is broader than the current GA-1 feature and intentionally includes strategic docs, prompts and production routing.

## 3. FIX NOW — repaired in this scan

### F1. General App Mode was worded like a new goal

Risk:
- `General App Mode` could be interpreted as a product-direction switch.
- phase ordering could make self-extension look like something postponed until a final phase.

Repair:
- `docs/spec/FORGE-GENERAL-APP-MODE.md` now states it is an **execution program, not a new product goal**.
- missing-capability synthesis is cross-cutting from the beginning.
- Golden requests are explicitly test probes only.

### F2. Core system prompt narrowed Forge to known JSON UI generation

Risk:
- prompt language could train an agent to regard existing schema vocabulary as the permanent product boundary.
- unsupported requirements could be silently downgraded to existing widgets.

Repair:
- `PROMPTS/system/core_directive.v1.md` now inherits canonical direction and says:
  compose what exists; preserve exact gaps; route missing capabilities into synthesis/extension; never fake success with a domain/template fallback.

### F3. AI-layer README described a finite generation boundary

Repair:
- `backend/app/ai/README.md` now describes semantic capability decomposition, composition, exact gaps, extension/synthesis, verification, repair and evidence-backed promotion.

### F4. AI architecture document contained an explicit goal-substitution rule

Finding:
- `docs/AI.md` said the AI only generates JSON and treated that as a product-level absolute.
- more importantly, it explicitly documented that because Forge lacked increment semantics, a counter-shaped request should be represented as `RECORD_CRUD` instead.

This is exactly the failure mode Whole Scan is meant to catch: **missing capability -> nearest available pattern -> original behavior lost**.

Repair:
- `docs/AI.md` now distinguishes the current versioned JSON execution boundary from Forge's product identity.
- `SolutionShape` is labelled a compatibility/implementation layer, not the set of apps Forge can create.
- unsupported `count + 1` semantics must remain an exact capability gap and eventually become a reusable state-transition/increment capability rather than a CRUD substitute.
- build failure must not force a checklist/CRUD result and call it success.

### F5. Handoff did not make the invariant dominant enough

Repair:
- `docs/HANDOFF.md` now starts from the invariant and defines all current engineering slices as subordinate implementation steps.

### F6. Whole Scan itself lacked a persistent definition

Repair:
- created `docs/FORGE-WHOLE-SCAN-PROTOCOL.md`.
- future command **「全体スキャン」** now has a stable repository-wide meaning and requires repair, not report-only review.

## 4. DEFER — code-level deviations found, not yet safely patched

### D1. SolutionShape still contains semantic substitution in active code

File:
- `forge_ai/core/ir/solution_shape.py`

Observed behavior:
- a single number-field entity can be selected as `RECORD_CRUD` because the runtime historically lacked a counter/increment interaction.
- existing tests deliberately lock this behavior.

Why not patch it naïvely:
- `SolutionShape` sees structural `Entity` data, not enough behavioral semantics to determine whether a numeric field means a counter, money amount, score record, duration, measurement, etc.
- changing `number -> counter` would create a different form of template guessing.

Required repair:
1. preserve behavioral intent upstream;
2. add a reusable semantic capability such as generic state transition / increment-decrement rather than a counter-domain special case;
3. let capability support resolution mark it MISSING until production support exists;
4. route MISSING to extension/synthesis;
5. then allow shape/compiler/runtime composition from the semantic plan.

### D2. Compiler has shape-driven fallbacks

File:
- `forge_ai/core/ir/forge_language_compiler.py`

Risk:
- current compile flow still selects a `SolutionShape` from entities and dispatches into fixed compile branches.
- the final default path can fall back to checklist compilation.

Required repair:
- unknown/unrepresentable semantic need must fail closed with an explicit planning/capability-gap result, not become checklist.
- move presentation shape downstream of semantic capability planning.

### D3. Pipeline repair can force a legacy checklist

File:
- `forge_ai/core/orchestration/pipeline_orchestrator.py`

Finding:
- after journey/quality repair failure, a legacy fallback path can use `force_legacy_checklist()` and then repair that result.

Severity: **HIGH strategic drift**.

Why deferred in this pass:
- this is production orchestration and must be changed together with tests and explicit failure/gap semantics; deleting it without checking caller expectations can turn a silent semantic error into an unhandled production failure.

Required repair:
- replace forced checklist fallback with one of:
  - bounded repair of the same semantic requirement;
  - explicit Capability Gap / extension request;
  - typed generation/planning failure.
- add regression test proving an unsupported/non-checklist requirement can never become a successful checklist merely because generation failed.

### D4. Semantic lexicon can lose unsupported behavior before capability planning

Files sampled:
- `forge_ai/core/semantics/roles.py`
- `forge_ai/core/semantics/capabilities.py`
- `forge_ai/core/semantics/capability_plan.py`

Finding:
- capability planning correctly supports MISSING states for recognized needs.
- however, a behavioral need that has no semantic role/capability can disappear before support resolution.
- explicit generic increment/state-transition semantics were not found in the scanned capability surfaces.

Required repair:
- add a general behavior/state-transition semantic representation, not a list of domain-specific keyword patterns.
- ensure unknown-but-material behavior survives normalization as an exact semantic requirement/gap.

## 5. UNKNOWN / evidence boundary

### U1. Automatic self-extension / capability promotion is not yet evidenced as production-complete

Repository searches in this pass did not locate a clear production implementation named around `self_extension` or `capability_registry` that closes this complete loop:

```text
exact missing capability
 -> generated implementation
 -> isolated validation
 -> schema/parser/compiler/runtime wiring as applicable
 -> test/build/runtime/security evidence
 -> registry promotion
 -> reuse by unrelated future request
```

There are strong architecture/spec documents for self-extension, and there are existing generic capability planning mechanisms, but this scan does **not** have enough evidence to mark the complete automatic synthesis-and-promotion lifecycle IMPLEMENTED.

Current truthful status for the full loop: **DESIGNED / PARTIAL, production closure UNVERIFIED**.

Next investigation:
- trace every production path that consumes `capability_plan.missing`;
- identify whether any executor generates extension code/artifacts;
- identify promotion/registry persistence and rollback/provenance;
- create end-to-end evidence before changing status.

## 6. ACCEPT — intentional constraints consistent with the goal

### A1. Expression engine is deliberately not arbitrary code execution

Current GA-1 expression engine is a deterministic, inspectable data AST. This is consistent with Forge because it is a reusable semantic primitive and does not claim to replace extension/synthesis.

### A2. Current Forge Language / JSON validation boundary

Keeping the current runtime fail-closed around versioned schemas is valid. The incorrect part was treating that current boundary as the permanent product goal. Missing capabilities should extend the system through controlled build-time/service/native routes rather than bypass validation.

## 7. Current implementation evidence checked

General expression engine:
- `2abf295132d3f83ced0f65863e651f5b24b37b1b`
- tests: `5c07ed2fc2ef5b493fb42e20945216c88da70c6a`
- CI run `33292399951`: **SUCCESS**

Live runtime expression binding:
- `8dc9e38bab6aa38b0d6119282911422cfb4b1c86`
- tests: `7574168c76722acc54cbefc5c6e6db16592287e6`
- CI run `33292752019`: **SUCCESS**

These prove reusable expression/state behavior only. They do not prove full general software generation or automatic self-extension.

## 8. Remaining documentation drift

### README

Top-level README still describes Forge primarily as:
- conversation -> JSON UI Schema -> renderer;
- AI generates JSON only;
- template vocabulary as a central product description.

This is stale product framing. Setup/history content remains useful, so it should be surgically rewritten rather than discarded.

Classification: **DEFER / documentation repair pending**.

### ROADMAP-TO-TARGET

Historical widget-count / vocabulary-expansion sections need to be explicitly marked implementation history/scaffolding rather than product direction where they still read as target-defining.

Classification: **DEFER / documentation repair pending**.

## 9. Next repair order from the real goal backward

1. Remove production forced-checklist semantic substitution safely, with regression tests.
2. Preserve unknown/material behavioral requirements through semantic planning instead of dropping them.
3. Introduce reusable generic state-transition/increment semantics as a capability, not a counter-app pattern.
4. Trace and close the missing-capability -> synthesis/extension -> verification -> promotion lifecycle.
5. Reframe README and stale roadmap language.
6. Re-run Whole Scan across current production path and CI.
7. Then continue GA-1 conditional rendering/derived binding, treating it strictly as a reusable capability slice.

## 10. Overall assessment

The repository's top-level strategic documents are substantially aligned with the intended Forge, but active legacy code still contains **pattern-substitution escape hatches** that can make the system produce something easy instead of preserving the user's actual requirement.

Therefore this Whole Scan is **not closed** yet.

Most important unresolved defect:

> **Generation/repair failure must never be converted into a successful checklist/CRUD simply because that shape is available.**

That will be the first code-level repair before resuming feature expansion.
