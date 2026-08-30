# FORGE GENERAL APP MODE

Status: EXECUTION PROGRAM / NOT A NEW PRODUCT GOAL
Date: 2026-08-30

## Positioning

General App Mode is **not a goal switch**. It is an implementation program under the already-canonical Forge goal in `docs/FORGE-CORE-CONSTITUTION.md`, `docs/PRODUCT-DIRECTION.md`, and `docs/GENERATIVE-SOFTWARE-DIRECTION.md`.

The invariant is:

> **持っている能力は組み合わせる。足りない能力は作る。作った能力は検証し、再利用可能な Forge Capability として取り込む。**

Do not replace that invariant with a finite list of app types, widgets, templates, Golden cases, or hand-written domain paths.

## Product target

Forge receives a natural-language need, understands the actual desired outcome, decomposes it into semantic capabilities, composes existing capabilities where possible, synthesizes genuinely missing capabilities when necessary, verifies the result, repairs failures, and reaches a usable tool.

```text
Need / desired outcome
  -> semantic understanding
  -> capability decomposition
  -> existing capability reuse + composition
  -> missing capability synthesis when required
  -> generated software / Forge Document / workspace
  -> validator
  -> test
  -> build
  -> runtime probe
  -> visual / behavioral / effect evidence where applicable
  -> bounded repair
  -> reverify
  -> usable tool
  -> validated new capability promotion for reuse
```

The user-facing destination approaches "say what you need and it becomes usable software". Internally, Forge must never fake unsupported, unsafe, permission-blocked, or unverified behavior.

## Definition of Done

A General App Mode slice is PASS only when its production path closes with objective evidence. A Golden request is a **test case**, never the product goal and never permission to add a bespoke implementation that only passes that request.

If an unsupported need is encountered, the correct path is not merely to report a gap and stop forever:

```text
unsupported need
  -> exact missing capability
  -> confirm it is genuinely missing rather than already composable
  -> safety / trust / permission classification
  -> choose extension route
       composition
       declarative capability
       generated build-time extension
       service adapter
       native / privileged adapter
  -> isolated implementation
  -> schema / validator / parser / compiler / runtime wiring as applicable
  -> tests / build / runtime / security evidence
  -> provisional capability
  -> evidence-backed promotion
  -> reusable capability available to future unrelated requests
```

If the capability cannot safely or technically be created yet, retain an explicit Capability Gap. Never silently rewrite the user need into something easier.

## Capability development areas

The following GA areas are **coverage scaffolding**, not the boundary of what Forge may create and not a fixed sequential checklist.

### GA-1 Logic Core

Reusable deterministic semantics for behavior:

- condition / compare
- if / else
- derive / computed state
- filter
- sort
- aggregate
- arithmetic
- boolean composition
- event -> state transition
- reusable rule definitions

Acceptance examples are probes only:

- "残高が0未満なら警告を出す"
- "未完了だけ表示する"
- "カテゴリ別に合計する"
- "複数の入力値から派生値を計算する"

### GA-2 Navigation + Persistent Data

- multi-screen navigation with parameters
- local persistent storage
- schema migration/versioning
- search/query
- relation/reference between records
- structured import/export

### GA-3 External Service Effects

- HTTP/API request
- authenticated service adapters
- file upload/download
- share
- notification
- email/webhook-style outbound adapters

Effects require observable destination/policy, secret isolation, timeout/retry boundaries, and confirmation for irreversible operations where required.

### GA-4 Device Capabilities

- camera
- microphone
- location
- file picker
- clipboard
- sensors where supported

OS permission and capability safety must remain explicit.

### GA-5 Rich Presentation

- image
- icon
- animation
- grid
- canvas/scene
- map
- richer charts
- responsive layouts
- theme/design composition

Prefer reusable encoding/layout primitives over app-specific widgets.

### GA-6 Media + Game Runtime

- user media import
- audio editing/composition/export
- image composition/export
- video/media timeline where justified
- input events
- collision/hit testing
- sprite/scene primitives
- deterministic game state
- save/load

### GA-7 Self-Extension Hardening / Promotion

**Self-extension is not postponed until GA-7.** Missing-capability synthesis is a cross-cutting requirement from the beginning.

GA-7 means hardening and automating the extension lifecycle itself: isolation, generated implementation contracts, promotion rules, rollback, provenance, compatibility, security, and repeated-evidence gates.

A capability may become IMPLEMENTED only after the applicable production bindings and evidence exist. AI self-report is never sufficient.

## Architecture rule

`Capability != Widget` and `Golden Case != Product Goal`.

```text
User Need
 -> Semantic Capability
 -> Runtime Primitive(s) and/or generated extension
    DATA
    TRANSFORM
    VIEW
    ENCODING
    EFFECT
    SIMULATE
 -> Forge Language / generated workspace binding
 -> platform/runtime implementation
 -> evidence
 -> capability registry promotion when genuinely reusable
```

A new implementation must be challenged with:

1. Is this only for one named app/domain/test case?
2. Could the same semantic capability serve an unrelated request?
3. Are we adding a pattern because it is easy instead of creating the missing general capability?
4. If existing primitives cannot express the need, did we actually enter synthesis/extension rather than silently downgrade the request?

If the answer reveals goal substitution, redesign before calling the slice complete.

## Truthfulness rule

- PARTIAL is not IMPLEMENTED.
- Interactive audio mixing is not media export.
- Widget/browser harness evidence is not real-device evidence.
- Visual UNKNOWN is not PASS.
- A privileged-effect UI is not an implemented effect.
- A Capability Gap is not a successful alternative app.
- A Golden test passing through bespoke code is not evidence of general generation ability.

## Execution strategy

Current engineering attention starts with GA-1 because logic primitives unlock many compositions, but this is an implementation choice, not a redefinition of Forge.

There is **no rule that GA-1 must be exhausted before a missing capability from another area may be synthesized**. The governing rule is goal-backward planning:

> Start from the real target, compose what exists, create what is missing, verify, and retain reusable capability.

Current first vertical slice:

```text
expression
 -> live state binding
 -> conditional branch / derived value
 -> UI visibility/value binding
 -> compiler generation
 -> backend validation
 -> Flutter runtime
 -> regression test
 -> generated-app evidence
```

First Golden probe:

> `毎月の収入と支出を記録して、残高を自動計算し、残高がマイナスなら警告を表示する家計アプリを作って`

This probe must not introduce a household-budget-specific runtime path. It passes only if the same logic/branching capabilities are reusable for unrelated needs.
