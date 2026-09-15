# Forge Core v0.1 Quality Fix Review

## Date

2026-09-15

## Purpose

Core v0.1 is not accepted as complete merely because the initial 33-test slice passed. This checkpoint fixes the semantic ambiguities found during the quality review before the Core contract is extended.

## Decisions

### 1. `set_value` semantics

`set_value` in v0.1 means **replace the value of an existing target**.

It does not create a missing target.

A future creation operation must have a separate explicit semantic contract rather than silently expanding `set_value` into upsert behavior.

### 2. Validation owns input-contract checks

Validation is responsible for:

- supported operation ID
- required target existence
- required operation arguments

Execution receives a validated operation and should not repeat ordinary input validation.

Execution may retain defensive invariant checks for conditions that should be impossible after successful validation.

### 3. Unsupported operation handling

An unsupported operation is rejected as `INVALID_OPERATION` before target lookup. This prevents an invalid operation from being misreported as `NOT_FOUND` merely because its target is also absent.

### 4. Evidence does not require state mutation

A successful operation may legally produce a state identical to the input state. Therefore `state_before_id != state_after_id` is not a Core invariant.

Evidence records that the state result was observed; it does not claim that every successful operation must change state.

### 5. Operation extensibility boundary

v0.1 keeps exactly one supported operation ID and a small explicit supported-ID set. A generalized Operation Registry is intentionally deferred until there are enough operation semantics to justify that abstraction.

The implementation must not grow into a long `if/elif` chain when additional operations are introduced. That future boundary is a mandatory refactoring point.

### 6. State identity

The current identity mechanism remains deterministic for the Python v0.1 implementation. A cross-language canonical serialization contract is a future Core boundary and is not introduced prematurely.

## Quality Gate

Before the next Core capability is added, the following must be true:

- `set_value` semantics are explicit
- validation and execution responsibilities are separated
- unsupported operations produce stable errors
- successful no-op execution is valid
- failed execution preserves the original state
- evidence reflects observable facts without overclaiming mutation
- deterministic tests cover these rules
- no AI, network, database, UI, or OS dependency is introduced
- the implementation remains small and maintainable

## Next Resume Point

Run the full local Core test suite on the updated tree, review the resulting test count and failures, then perform a second quality audit. Only after that should the next Core contract be designed.
