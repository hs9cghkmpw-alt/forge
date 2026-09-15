# Forge Runtime v0.1 Design

**Status:** DESIGN DRAFT — IMPLEMENTATION NOT STARTED  
**Date:** 2026-09-15  
**Predecessor:** Forge Core v0.1  

## 1. Purpose

Forge Runtime is the execution environment above Forge Core and below future Forge Language/compiler, application, and UI layers.

Its job is not to replace Core. Its job is to provide the controlled environment in which Core operations can be invoked, composed, observed, and eventually connected to Forge-owned language/runtime facilities.

Core answers:

> "Is this valid, and what deterministic state transition does it produce?"

Runtime answers:

> "How is that operation invoked, what capabilities are available to it, how is its lifecycle managed, and how are its result and evidence carried to the next layer?"

The final Forge architecture keeps physical hardware as the only external boundary. Python and other existing technologies may be used as temporary bootstrap implementations, but they are not Runtime architecture dependencies.

## 2. Architectural Position

```text
Human / AI / Meaning / Domain
            |
            v
     Forge App / UI / API
            |
            v
   Forge Language / Compiler
            |
            v
     +------------------+
     |  Forge Runtime   |
     |                  |
     | Invocation       |
     | Lifecycle        |
     | Capabilities     |
     | Resource access  |
     | Scheduling       |
     | Result/evidence  |
     +------------------+
            |
            v
     +------------------+
     |    Forge Core    |
     | Value / State    |
     | Operation        |
     | Validation       |
     | Execution        |
     | Result / Error   |
     | Evidence         |
     +------------------+
            |
            v
  Future Forge-owned OS / devices
            |
            v
       Physical hardware
```

Important dependency direction:

```text
Language / App / UI
        ↓
     Runtime
        ↓
      Core
        ↓
   lower platform
```

Core must not depend upward on Runtime.

## 3. Core → Runtime Boundary

The Runtime consumes the public Core contract. It must not reach into Core implementation details.

### Runtime may provide

- a valid Core `State` input
- a Core `Operation`
- explicit Runtime context/capabilities
- invocation identity
- lifecycle information
- controlled resource access outside Core
- scheduling decisions
- result/evidence transport

### Runtime must not provide implicitly

- hidden mutable global state
- current time directly inside Core execution
- random values directly inside Core execution
- network access directly inside Core execution
- database access directly inside Core execution
- AI/provider calls directly inside Core execution
- UI state directly inside Core execution

If such information is needed, Runtime must represent it as an explicit boundary input/capability rather than allowing Core to discover it implicitly.

## 4. Responsibility Split

### 4.1 Core owns

- typed values
- deterministic state
- operation semantics
- validation
- atomic state transition
- stable Core errors
- Core result
- deterministic evidence
- Core invariants

### 4.2 Runtime owns

- invocation lifecycle
- admission of execution requests
- execution context
- capability boundaries
- sequencing of operations
- controlled resource access
- cancellation/lifecycle state
- result/evidence propagation
- Runtime-level errors
- isolation between executions
- future scheduling/concurrency model

### 4.3 Runtime does not own

- natural-language interpretation
- UI rendering
- prompt construction
- AI model selection
- product-specific visual design
- Core operation semantics
- hidden persistence inside Core

These belong to layers above or beside Runtime.

## 5. Invocation Model

The first Runtime invocation must be explicit and inspectable.

Conceptually:

```text
RuntimeRequest
  |
  +-- invocation_id
  +-- operation
  +-- initial_state
  +-- declared_capabilities
  +-- execution_metadata
  |
  v
Runtime admission
  |
  v
Core validation/execution
  |
  v
RuntimeResult
  +-- invocation identity
  +-- Core result
  +-- lifecycle outcome
  +-- propagated evidence
```

Runtime v0.1 should not invent a general-purpose workflow engine. One invocation of one Core operation is the smallest useful unit.

## 6. Lifecycle

Runtime v0.1 lifecycle:

```text
CREATED
   ↓
ADMITTED
   ↓
EXECUTING
   ↓
COMPLETED
```

Failure/cancellation paths must be explicit:

```text
CREATED → REJECTED
ADMITTED → CANCELLED
EXECUTING → FAILED
```

The lifecycle state must be represented as data rather than inferred from logs or exception text.

A Runtime lifecycle state must never be confused with Core domain state.

## 7. Capability Model

A capability is an explicit permission for Runtime-level access to a resource or effect.

Examples for future versions:

- clock/time
- randomness
- filesystem
- storage
- network
- device I/O
- process/service interaction

v0.1 should define the boundary but implement only the minimum capability set required by the first invocation slice.

Critical rule:

> A capability must be explicitly declared and passed. Runtime must not smuggle environmental authority into Core.

This creates a path from the current deterministic Core toward a future full Runtime without weakening Core's determinism contract.

## 8. Deterministic vs Environment-Dependent Work

Forge must distinguish two classes of execution.

### Deterministic Core execution

```text
same State + same Operation
        ↓
   same Core Result
```

### Environment-dependent Runtime execution

```text
Runtime context / capabilities
        ↓
possibly environment-dependent observation
        ↓
explicit input to Core or Runtime-level result
```

Time, network responses, device readings, random values, and external storage are Runtime concerns. They must not silently alter Core behavior.

## 9. State and Resource Boundary

Core state represents deterministic state relevant to the operation.

Runtime resources represent things outside that deterministic state, such as:

- files
- sockets
- devices
- clocks
- processes
- external services

The Runtime must not automatically place arbitrary resources into Core state.

Instead:

```text
External resource
      ↓
Runtime adapter/capability
      ↓
explicit value/input
      ↓
Core operation
```

This prevents OS, storage, and network concepts from leaking into the Kernel contract.

## 10. Error Model

There are two distinct error domains.

### Core errors

Stable machine-readable Core errors defined by the Core contract.

### Runtime errors

Errors concerning invocation/lifecycle/environment, for example:

- INVALID_RUNTIME_REQUEST
- CAPABILITY_DENIED
- INVOCATION_NOT_FOUND
- INVOCATION_CANCELLED
- RESOURCE_UNAVAILABLE
- RUNTIME_INVARIANT_VIOLATION

Runtime must preserve the original Core error rather than rewriting it into an opaque Runtime error.

Conceptually:

```text
RuntimeResult
├── lifecycle outcome
├── core result
│   ├── success
│   └── CoreError
└── RuntimeError (only when Runtime itself fails)
```

## 11. Evidence Propagation

Evidence is a first-class boundary object.

Runtime must not claim that an operation succeeded merely because invocation returned normally.

The evidence chain should distinguish:

```text
AI/adapter claim
      ↓
Runtime admission
      ↓
Core validation
      ↓
Core execution
      ↓
Core evidence
      ↓
Runtime lifecycle/evidence
```

Future quality systems can therefore determine what was requested, what was admitted, what Core actually verified, and what Runtime actually completed.

## 12. Isolation and Atomicity

Core already guarantees atomic state transition for its v0.1 execution slice.

Runtime adds a higher-level isolation requirement:

> One invocation must not accidentally mutate another invocation's state or lifecycle data.

v0.1 should therefore avoid shared mutable global runtime state.

A future concurrent Runtime may introduce scheduling and worker isolation, but concurrency must not be added merely for architectural appearance.

## 13. Storage Boundary

Storage is outside Core.

Runtime v0.1 should not embed a database abstraction prematurely.

The intended future direction is:

```text
Runtime
  ↓
Storage capability
  ↓
Forge-owned storage subsystem
```

A temporary Python/in-memory implementation is acceptable for bootstrap testing, but the contract must not depend on a third-party database.

## 14. Time, Network, and I/O

These are Runtime capabilities, not Core dependencies.

### Time

Runtime owns access to clocks. Core receives time only if time is intentionally modeled as an explicit operation input.

### Network

Runtime owns network access. Network responses become explicit Runtime observations or inputs; Core never opens a network connection.

### I/O

Runtime owns device/file/process interaction until the future Forge OS provides Forge-owned interfaces.

## 15. Future Forge Language / Compiler Integration

The Runtime must not be designed around Python syntax.

Future flow:

```text
Forge Language source
       ↓
Forge Compiler
       ↓
Runtime instruction / invocation representation
       ↓
Forge Runtime
       ↓
Forge Core
```

Therefore Runtime v0.1 contracts must be language-neutral where practical.

Python is only the bootstrap implementation language for learning and validation.

## 16. Module Structure

The first implementation should remain small and separated by responsibility.

Proposed shape:

```text
forge_runtime/
├── __init__.py
├── request.py       # Runtime invocation request
├── lifecycle.py     # invocation lifecycle state
├── context.py       # explicit runtime context/capabilities
├── result.py        # Runtime result and error propagation
├── executor.py      # orchestration only
├── errors.py        # Runtime errors
└── tests/
```

No module should become a universal manager.

In particular, `executor.py` must orchestrate; it must not accumulate Core semantics, storage logic, network logic, UI behavior, or AI logic.

## 17. Anti-Spaghetti Rules

The Runtime implementation must follow the Forge code-quality rules.

Additional Runtime-specific rules:

1. Lifecycle state must not be encoded as scattered booleans.
2. Capability checks must not be duplicated throughout execution code.
3. Runtime errors must not be represented by parsing exception strings.
4. Core execution must be called through one explicit boundary.
5. Resource adapters must not modify Core internals.
6. No global singleton runtime state.
7. No operation-ID branching inside the Runtime executor.
8. No UI/HTTP/database imports in Core-facing modules.
9. Each module has one clear responsibility.
10. Tests must be able to run without network access.

## 18. v0.1 Scope

The first executable Runtime slice should be deliberately small:

```text
RuntimeRequest
    ↓
Admission
    ↓
Lifecycle: CREATED → ADMITTED → EXECUTING
    ↓
Core invocation
    ↓
Lifecycle: COMPLETED / FAILED
    ↓
RuntimeResult + propagated Core Evidence
```

It should demonstrate:

- explicit invocation identity
- explicit initial Core state
- explicit Core operation
- lifecycle state
- Core result propagation
- Core error preservation
- Runtime error separation
- no shared mutable global state
- deterministic tests
- no network/database/UI/AI dependency

Do not implement scheduling, persistence, networking, plugin systems, or a general workflow engine in v0.1 unless a testable requirement proves they are necessary for this slice.

## 19. Quality Gate Before Runtime Expansion

Runtime v0.1 must not expand until it demonstrates:

- lifecycle correctness
- Core boundary correctness
- Core error preservation
- Runtime error separation
- evidence preservation
- invocation isolation
- deterministic tests for the deterministic path
- explicit capability boundaries
- no prohibited dependencies
- clear module responsibilities
- no spaghetti branching
- understandable implementation by the developer
- GitHub checkpoint with implementation, tests, failures, fixes, and evidence

## 20. Review Decision

This document is a design baseline, not permission to add every future Runtime feature.

Implementation must begin with the smallest executable slice in Section 18.

Before implementation, this design must pass a strict review for:

- architecture
- responsibility boundaries
- determinism
- security/isolation
- maintainability
- extensibility
- testability
- future Forge Language compatibility
- future Forge OS compatibility
- migration away from bootstrap technologies

Only after that review should `forge_runtime/` be created.
