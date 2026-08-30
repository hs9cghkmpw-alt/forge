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
- Active slice: general reusable logic semantics and runtime binding.
- Execution program: `docs/spec/FORGE-GENERAL-APP-MODE.md`.
- Self-extension basis: `docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md`.

`FORGE-GENERAL-APP-MODE.md` is explicitly **not a new product goal**. It is coverage scaffolding under the canonical invariant. Missing-capability synthesis is cross-cutting and must not be postponed until the end of a phase list.

## Current implementation evidence

### General expression engine

Commit:

- `2abf295132d3f83ced0f65863e651f5b24b37b1b` — `feat: add deterministic general expression engine`
- `5c07ed2fc2ef5b493fb42e20945216c88da70c6a` — `test: lock general expression semantics`

Implemented reusable expression semantics include literal/state references, arithmetic, comparisons, boolean composition, and record aggregates. Expressions are data and fail closed; arbitrary Dart/code execution is not an expression feature.

CI:

- run `33292399951` — **SUCCESS**

### Live Runtime State binding

Commits:

- `8dc9e38bab6aa38b0d6119282911422cfb4b1c86` — `feat: bind general expressions to live runtime state`
- `7574168c76722acc54cbefc5c6e6db16592287e6` — `test: prove live runtime expression binding`

The regression proves that state mutation changes a derived balance and its boolean negative condition using the same reusable expression layer.

CI:

- run `33292752019` — **SUCCESS**

This is **not** a household-budget feature. The household-budget request is only a Golden probe for reusable logic semantics.

## Whole Scan corrections made on 2026-08-30

The first explicit Whole Scan found strategic drift and began correcting it:

1. `PROMPTS/system/core_directive.v1.md` described Forge as a JSON-only UI generator and could imply that undefined types are a permanent product boundary. It is now explicitly subordinate to the canonical product goal and routes missing capabilities toward synthesis/extension rather than silent downgrade.
2. `docs/spec/FORGE-GENERAL-APP-MODE.md` said "next official goal" and placed self-extension at the end of the phase sequence. This could recreate the exact goal-substitution failure the CEO identified. It now states that the product goal never changed and that missing-capability synthesis is cross-cutting from the beginning.
3. `docs/FORGE-WHOLE-SCAN-PROTOCOL.md` now defines **全体スキャン / Whole Scan** as a repository-wide goal-alignment scan plus immediate repair of safe deviations.

See `docs/reports/FORGE-WHOLE-SCAN-20260830-report.md` for findings and remaining drift.

## Current next work

Continue the logic vertical slice without turning it into the goal:

```text
reusable expression
 -> live state binding               DONE / CI green
 -> conditional branch / visibility NEXT
 -> derived value binding
 -> Forge Language representation
 -> validator/parser/compiler wiring
 -> generated-app runtime evidence
```

At every step apply the same challenge:

- Can an unrelated request reuse this capability?
- Are we writing a test-case-specific path?
- If a real request needs a capability that existing primitives cannot express, are we entering synthesis/extension rather than rewriting the request to something easier?

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

Do not reopen that Golden unless a regression occurs, and do not treat its PASS as proof of general software-generation completion.

## Final closure rule

The final branch HEAD after implementation and bookkeeping must pass persistent `.github/workflows/ci.yml`. Do not convert pending/unmeasured evidence into PASS.
