# Forge Whole Scan Report — 2026-08-30/31

Status: **CLOSED — first strategic repository-wide pass**
Branch: `claude/forge-master-handoff-k46jns`

## 1. Canonical invariant

Whole Scan evaluates Forge against one non-negotiable product invariant:

> **持っている能力は組み合わせる。足りない能力は作る。作った能力は検証し、再利用可能な Forge Capability として取り込む。**

The prohibited anti-pattern is goal substitution:

```text
easy implementation
 -> concentration on that implementation
 -> implementation becomes de facto goal
 -> user's original desired outcome is silently narrowed
```

Golden cases, templates, widgets, SolutionShape, JSON schemas and GA phases are implementation/test surfaces only.

## 2. Strategic defects repaired in this pass

### Product-boundary wording

Corrected or demoted stale wording in:

- `PROMPTS/system/core_directive.v1.md`
- `PROMPTS/templates/generate_ui_schema.v1.md`
- `README.md`
- `docs/AI.md`
- `docs/spec/FORGE-GENERAL-APP-MODE.md`
- `docs/HANDOFF.md`

The current Forge Language/JSON boundary is a safety/runtime boundary, not the permanent product capability ceiling.

### Silent Checklist substitution

Production now has `capability_gate.py` and `CapabilityGapError`.

Invariant:

```text
explicit StructuralMode.CHECKLIST
 -> legacy checklist compiler allowed

RECORD_ENTITY unresolved
 -> Capability Gap

UNKNOWN unresolved
 -> Capability Gap

Capability Gap
 -> CognitivePipelineNeedsExtension
 -> never successful Checklist/CRUD merely because those are available
```

`pipeline_orchestrator.py` catches `CapabilityGapError` before generic planning failure and returns `CognitivePipelineNeedsExtension` with structured extension candidates.

### SolutionShape demotion

`forge_ai/core/ir/solution_shape.py` is a legacy downstream representation chooser only. It is not the product-level catalog of what Forge can build.

### Self-extension production skeleton

The following lifecycle is implemented as reusable orchestration surfaces:

```text
Capability Gap
 -> ExtensionCandidate
 -> ExtensionManifest
 -> route selection
 -> implementation
 -> evidence gate
 -> VERIFIED
 -> PROMOTED
 -> executable activation
 -> registry install
 -> original request retry
 -> repeat for remaining gaps
```

Implemented controls include:

- unresolved semantics require decomposition;
- unverified manifests cannot promote;
- sensitive capability requires safety evidence;
- manifest-only promotion cannot masquerade as executable support;
- capability identity cannot change during implementation;
- BUILD_TIME support requires loaded build/runtime attestation;
- same gap after promotion = no progress;
- retries are bounded;
- declarative promoted capability persistence uses integrity checking.

Relevant files:

- `extension_plan.py`
- `extension_manifest.py`
- `extension_activation.py`
- `extension_registry.py`
- `extension_cycle.py`
- `self_extension_loop.py`
- `declarative_extension.py`
- `declarative_activation.py`
- `extension_store.py`
- `build_time_extension.py`

Regression `test_self_extension_loop.py` proves multi-gap requests must acquire every remaining gap before completion.

## 3. GA-1 reusable logic closure

GA-1 is connected through the generated-document path:

```text
GA-1 Python logic model
 -> ForgeIRDocument.logic
 -> generated JSON `logic`
 -> Backend Validator
 -> Dart ForgeDocument parser
 -> ForgeLogicRuntime
 -> Renderer visible_when
```

Implemented reusable semantics:

- literal/state references
- arithmetic
- comparisons
- boolean composition
- aggregates
- derived values
- conditional visibility

Derived values are evaluated from current mutable state and are not copied into a second mutable Source of Truth.

Validator is fail-closed:

- `logic` only for v1.15+;
- unknown operators/kinds rejected;
- bounded expression depth;
- bounded entry count;
- aggregate field references constrained to valid context.

Key commits:

- `2abf295132d3f83ced0f65863e651f5b24b37b1b`
- `8dc9e38bab6aa38b0d6119282911422cfb4b1c86`
- `ebe90998c321cbd886dbdbae8b486b641791e3a7`
- `a83396ed3f7b1e21c48118a9c75d4049101db472`

## 4. CI evidence

Canonical run `33328203164` on head `8e3c87616ef3f5ab9b9cad594b46cc609bda7c87` was **SUCCESS** through GA-1 validator integration.

The final descendant after Whole Scan cleanup and removal of the temporary cleanup workflow was head:

- `47aed8cc4da14f845f27696f003ddf8109cef0a8`

Canonical run `33333810005` on that head is **SUCCESS**:

- backend + forge_ai Python 3.11: PASS
- backend + forge_ai Python 3.12: PASS
- backend smoke: PASS
- Flutter analyze: PASS
- Flutter tests: PASS
- Flutter Web build: PASS

This satisfies the closure rule for the first Whole Scan engineering pass.

## 5. Final scan findings

### Production repair/fallback review

Current compilation path was re-read after prior repairs. The active branch contains an explicit capability plan before structural compilation, and only explicit CHECKLIST may enter the legacy compiler. `CapabilityGapError` returns `CognitivePipelineNeedsExtension` rather than a successful substitute.

The old Whole Scan statement that production still force-converted repair failure into a successful checklist is stale for the current branch and is superseded by this report.

### `ir_generator.py` stale comments

Historic wording that described `None` as permission to fall back to Checklist was removed. `IRGenerator` is now documented as a downstream representation component; product-level substitution/extension decisions remain upstream in Capability Plan and Self-Extension.

### Repair semantic-erasure boundary

No current evidence in the inspected production orchestration supports declaring a non-checklist requirement successful by deleting its required capability. The invariant remains: repair may fix representation/build/runtime faults, but may not erase required semantics to obtain green validation. Future repair implementations must receive an explicit regression when introduced or modified.

## 6. Truthful remaining limitation

The self-extension architecture is substantially implemented, but **one real unseen natural-language request has not yet been evidenced end-to-end as a production artifact proving all of:**

```text
unseen user request
 -> exact gap discovery
 -> generated reusable capability implementation
 -> real verification evidence
 -> promotion
 -> loaded activation
 -> automatic retry of original request
 -> generated product
 -> runtime behavior evidence
 -> later unrelated reuse
```

Unit/integration contracts prove each major orchestration boundary, including multi-gap progression and BUILD_TIME load attestation. That is not the same as a full unseen-request product E2E, so full autonomous generative-software completion remains unclaimed.

## 7. Whole Scan closure decision

The **first strategic Whole Scan is CLOSED**.

Closure means:

- the highest-risk goal-substitution escape hatches found in this pass are repaired;
- current architecture preserves Capability Gap rather than silently rewriting the need;
- Self-Extension has a reusable, evidence-gated promotion/retry path;
- GA-1 is a reusable capability slice rather than a domain template;
- the final engineering descendant before this closure bookkeeping passed canonical CI.

Closure does **not** mean:

- Forge is finished;
- every possible capability exists;
- full autonomous self-extension has been proven for arbitrary unseen requests;
- GA-2+ is complete.

## 8. Next work after closure

1. Produce a true unseen-request Self-Extension E2E evidence artifact.
2. Strengthen `ExtensionEvidence` from booleans toward concrete artifact/CI/runtime evidence references.
3. Continue GA-2 persistent data/navigation as reusable capabilities.
4. Re-run Whole Scan whenever a new fallback, repair path, privileged effect, generated-code route, or capability promotion mechanism is added.
