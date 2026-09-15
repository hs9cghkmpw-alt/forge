# Forge Runtime v0.1 Design Review

**Date:** 2026-09-15  
**Reviewed design:** `docs/FORGE-RUNTIME-V0.1-DESIGN.md`  
**Decision:** PASS WITH BOUNDARY TIGHTENING

## Review conclusion

The Runtime v0.1 design is architecturally sound enough to implement the smallest executable slice, but four boundaries must be made explicit before implementation:

1. Core invocation must cross a narrow Runtime-owned port/interface rather than coupling the executor to Core implementation modules.
2. Runtime capabilities must be represented as immutable, explicit data in v0.1 even if no environmental capability is implemented yet.
3. Lifecycle transitions must be centralized and validated; executor code must not mutate lifecycle state directly.
4. Cancellation is a future lifecycle capability. v0.1 should define the terminal state vocabulary but not implement asynchronous cancellation unless required by a test.

These tightenings prevent the first Runtime implementation from becoming an implicit service locator, global context, or workflow engine.

## 1. Architecture review — PASS

Dependency direction is correct:

`Language/App/UI → Runtime → Core → lower platform`

Core does not depend upward on Runtime. Runtime is an orchestration layer rather than a second semantic kernel.

## 2. Responsibility review — PASS

Core retains deterministic operation semantics, validation, atomic transition, result, errors, and evidence.

Runtime retains invocation lifecycle, admission, context/capabilities, isolation, and result propagation.

No duplicated semantic layer is required.

## 3. Determinism review — PASS

The design correctly prevents time, randomness, network, storage, AI, and UI state from entering Core implicitly.

Runtime may observe the environment, but environmental information must become explicit data before it can influence Core.

## 4. Security/isolation review — PASS WITH TIGHTENING

The capability model is correct in principle. v0.1 must make capability declarations immutable and explicit so authority cannot be silently expanded during execution.

No global singleton runtime state is permitted.

## 5. Lifecycle review — PASS WITH TIGHTENING

Lifecycle is data, not logs or exception text.

For v0.1, the valid state machine is:

```text
CREATED → ADMITTED → EXECUTING → COMPLETED
                         |
                         +------→ FAILED
```

`REJECTED` is a terminal admission outcome. `CANCELLED` remains reserved for a future explicit cancellation mechanism and must not be faked by v0.1.

## 6. Core boundary review — REQUIRED TIGHTENING

The executor must not directly depend on the internal implementation shape of `forge_core`.

Introduce a narrow invocation port conceptually equivalent to:

```text
CoreInvoker
    invoke(state, operation)
        ↓
    Core Result + Evidence
```

The v0.1 Python implementation may adapt the existing Core implementation behind this boundary. This preserves the architectural contract while avoiding premature duplication.

## 7. Result/evidence review — PASS

Runtime must preserve Core results and evidence without rewriting Core errors into generic Runtime errors.

Runtime may add its own lifecycle/invocation evidence.

## 8. Scope review — PASS

The design correctly rejects premature scheduling, persistence, networking, plugin systems, and workflow engines.

One invocation of one Core operation is the correct first Runtime unit.

## 9. Maintainability review — PASS

The proposed module split is small and responsibility-oriented.

`executor.py` remains orchestration only.

No operation-ID branching, no universal manager, no shared mutable singleton, and no exception-string protocol are permitted.

## 10. Future compatibility review — PASS

The contract is sufficiently language-neutral for future Forge Language/Compiler integration and does not require Python concepts to become permanent architecture.

It also preserves a clean path toward a Forge-owned OS while allowing temporary bootstrap technologies.

## 11. Decision

**APPROVED FOR IMPLEMENTATION after the four boundary tightenings above are reflected in the design.**

The next implementation unit is not a full Runtime. It is the minimal invocation path with explicit request, lifecycle, immutable context/capabilities, narrow Core invocation port, result/error propagation, and tests.

No additional Runtime features should be introduced until its quality gate passes.
