# Forge Core Kernel Contract v0.1

Status: DESIGN FROZEN FOR IMPLEMENTATION
Date: 2026-09-15

## 1. Purpose

Forge Core is the smallest software layer that can represent a meaningful operation, validate it, execute it deterministically, and expose an observable result with evidence.

Core must not depend on an AI provider, UI framework, HTTP, database, prompt, generated-app implementation, or operating system API.

Final Forge architecture keeps physical hardware as the only external boundary. Existing software may be used temporarily during development, but it is not part of the final Core contract.

## 2. Boundary

```text
Outside Core
  Human / AI / Meaning / Domain adapters
          |
          v
  +-----------------------------+
  |       Forge Core            |
  |                             |
  |  Value / State              |
  |  Operation                  |
  |  Validation                 |
  |  Execution                  |
  |  Result / Error             |
  |  Evidence                   |
  +-----------------------------+
          |
          v
Outside Core
  Runtime / Language / UI / Storage / OS
```

Core does not know how an operation was requested or how its result is displayed or persisted.

## 3. Canonical Core Concepts

### 3.1 Value

A typed, immutable value used by Core state and operations.

Requirements:
- explicit type
- deterministic equality
- no UI semantics
- no provider-specific representation
- invalid values are rejected rather than silently repaired

### 3.2 State

The complete deterministic state relevant to a Core execution.

Requirements:
- immutable input state
- explicit state transition
- no hidden mutable global state
- state can be compared before/after execution

### 3.3 Operation

A request to transform one valid Core state into another.

Minimum contract:
- operation identifier
- target/entity identifier
- named arguments
- preconditions
- deterministic transition

Core does not contain natural-language actions such as `add_item` as its semantic foundation. Those names may be adapters above Core.

### 3.4 Validation

Validation occurs before execution.

Validation must answer:
- Is the operation structurally valid?
- Are referenced values valid?
- Are required preconditions satisfied?
- Is the requested transition allowed?

A validation failure must prevent execution.

### 3.5 Result

Every execution returns an explicit result.

A successful result contains:
- resulting state or state delta
- operation identity
- observable outcome

A failed result contains:
- stable error code
- human-readable explanation
- no partially applied state

### 3.6 Error

Errors are data, not uncontrolled exceptions at the Core boundary.

Initial categories:
- INVALID_VALUE
- INVALID_OPERATION
- PRECONDITION_FAILED
- STATE_CONFLICT
- NOT_FOUND
- PERMISSION_DENIED
- INTERNAL_INVARIANT_VIOLATION

The exact taxonomy may expand, but callers must never need to parse exception text to understand a Core failure.

### 3.7 Evidence

Evidence records what Core actually verified.

Minimum fields:
- operation id
- validation outcome
- execution outcome
- state-before identity
- state-after identity when successful
- deterministic verification facts

Evidence must distinguish:
- claimed by an AI/adapter
- accepted by Core validation
- actually executed by Core

## 4. Determinism

Given the same valid input state and the same operation, Core must produce the same result.

No randomness, current time, network, AI provider, environment variable, UI state, or hidden global state may affect Core v0.1 execution.

If nondeterminism is eventually required, it must enter through an explicit Runtime boundary and be represented as an input to Core.

## 5. Transaction Rule

Core execution is atomic for v0.1:

```text
validate
  |
  +-- failure --> Error + unchanged state
  |
  v
execute against isolated candidate state
  |
  +-- invariant failure --> Error + unchanged state
  |
  v
commit candidate state
  |
  v
Result + Evidence
```

No partially applied operation may escape the Core boundary.

## 6. Invariants

The first implementation must enforce at least these invariants:

1. Invalid operations never mutate committed state.
2. Successful operations produce a valid state.
3. The same input produces the same output.
4. State transitions are observable.
5. Error codes are stable and machine-readable.
6. Core has no AI/provider dependency.
7. Core has no UI/runtime/database dependency.
8. Core does not silently invent missing semantic information.
9. Core does not expose internal implementation details as user-facing semantics.
10. Tests can execute Core without network access.

## 7. Relationship to Existing Forge Code

Existing `forge_ai/core` is treated as source material, not as an automatic final implementation.

- `Domain` / `DomainRegistry`: upper semantic layer candidate; not Core Kernel state.
- `World`: semantic context layer; outside Kernel.
- `Meaning`: interpretation layer; outside Kernel.
- `Intent`: request interpretation layer; outside Kernel.
- `forge_ai/core/ir`: strong candidate for the stable contract between semantic planning and compilation, but must not be allowed to leak UI/backend assumptions into Kernel.
- `DesignIntent`: product/design semantic layer; outside Kernel.
- `Compiler`: compilation boundary; outside Kernel.
- `Critic` / `Confirmation`: quality and dialogue layers; outside Kernel.

This prevents the existing `forge_ai/core` package name from being mistaken for the final Forge Kernel.

## 8. First Implementation Scope

The first executable Core slice is intentionally small but architecturally real:

```text
Typed Value
   -> State
   -> Operation
   -> Validation
   -> Atomic Execution
   -> Result
   -> Evidence
```

Use a generic record collection as the first test fixture. A shopping list is only a test scenario; it is not Core semantics.

The implementation must be independent of AI and Flutter.

## 9. Quality Gate Before Expansion

Do not proceed to Core v0.2 until v0.1 demonstrates:

- deterministic unit tests
- invalid-operation rejection
- atomicity on failure
- before/after state observability
- stable errors
- no external service dependency
- clear module boundaries
- understandable implementation by the developer
- GitHub checkpoint with tests and evidence

## 10. Next Work Unit

Create the first Forge-owned Core package as a new isolated implementation area rather than modifying the existing `forge_ai/core` immediately.

The implementation should be small enough to understand completely and strong enough to become the future Kernel contract.

After the slice passes its quality gate, existing `forge_ai/core` components will be migrated or retired one by one according to the A/B/C/D audit.
