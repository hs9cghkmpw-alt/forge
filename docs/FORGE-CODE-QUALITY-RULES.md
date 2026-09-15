# Forge Code Quality Rules

## Status

**MANDATORY PROJECT RULE**

These rules apply to all Forge software created from this point forward.

## Primary Rule: No Spaghetti Code

Forge must be designed and implemented for long-term maintenance.

Code that merely works is not sufficient. Code must also be understandable, testable, replaceable, and maintainable.

### Prohibited patterns

- large functions that perform multiple unrelated responsibilities
- modules that mix domain rules, I/O, presentation, persistence, and orchestration without a clear boundary
- hidden global mutable state
- duplicated business logic
- copy-and-paste implementations of the same semantic rule
- unclear control flow created only to shorten code
- excessive nesting when responsibilities can be separated
- circular dependencies that can be avoided by proper layering
- magic values or undocumented protocol strings when a stable contract is required
- silent fallback behavior that hides invalid states
- broad exception handling that masks real failures
- temporary hacks promoted into permanent architecture without review
- dead code and obsolete compatibility paths left without justification
- tests that depend on network or external services when deterministic local tests are possible

## Required Design Properties

Every substantial Forge component should have:

1. one clearly defined responsibility
2. an explicit public contract
3. minimal dependencies
4. deterministic behavior where the contract permits it
5. machine-readable failure behavior where appropriate
6. focused tests for its contract
7. documentation of non-obvious design decisions
8. a clear boundary to adjacent layers
9. a replacement/migration path when the component is temporary
10. evidence that the implementation satisfies its intended behavior

## Separation of Concerns

Forge layers must not collapse into one another merely for convenience.

Examples:

- Core semantics must not depend on UI code.
- Core semantics must not depend on AI providers.
- Validation must not silently perform unrelated execution.
- Execution must not contain presentation logic.
- Persistence must not define domain semantics merely because it owns storage.
- AI interpretation must not be treated as Core truth without deterministic validation.

## Function and Module Size

There is no arbitrary line-count limit. Size is judged by responsibility and cognitive complexity.

If a function or module becomes difficult to explain in one clear sentence, review whether responsibilities should be split.

Do not split code mechanically into tiny fragments merely to satisfy a size rule. The goal is coherent boundaries, not fragmentation.

## Dependency Discipline

Dependencies must flow in an intentional direction.

A lower layer must not silently acquire knowledge of higher layers.

Before adding a dependency, ask:

- Why is it required?
- Which layer owns the concept?
- Can the dependency be inverted or represented by a contract?
- Does it make testing harder?
- Does it create a future migration obstacle?

## Duplication Policy

Do not duplicate a semantic concept simply because an existing implementation is inconvenient.

Before creating a new representation, determine whether the concept should be:

- reused
- redesigned and replaced
- referenced only as prior art
- retired

This follows the Forge quality-first reuse policy.

## Error Handling

Errors must be explicit.

Do not use silent fallback behavior to make tests pass or hide architectural problems.

Where a stable contract exists, errors should be machine-readable and testable.

## Testing Rule

Every meaningful behavior added to Forge should have an appropriate verification method.

Preferred order:

1. deterministic unit test
2. integration test where a boundary requires it
3. runtime test
4. real-device test where relevant
5. visual/UX evaluation where relevant

A passing test does not automatically prove architectural quality.

## Review Gate

Before committing a substantial component, review at minimum:

- correctness
- maintainability
- readability
- separation of concerns
- dependency direction
- determinism
- error behavior
- testability
- extensibility
- Forge architectural fit

If a design is difficult to maintain, do not preserve it merely because it currently works.

## Refactoring Rule

Refactoring is part of implementation, not a later luxury.

When implementation reveals a structural problem, fix the structure before extending the feature if the problem would otherwise become a dependency for future code.

Do not perform unrelated mass rewrites. Refactor by bounded unit with tests before and after.

## Temporary Development Technology

Flutter, Python, FastAPI, Supabase, existing operating systems, existing AI runtimes, and other current development technologies may be used as temporary development footholds.

Their presence must not justify poor internal Forge architecture.

Where a future Forge-owned replacement is intended, the dependency and migration boundary must remain explicit.

## GitHub Record Requirement

All Forge-created work must ultimately be recorded in GitHub.

The record includes:

- design
- source code
- tests
- experiments
- failures
- fixes
- verification results
- architectural decisions
- research/learning notes when relevant
- resume points
- real-device verification
- handoff documentation

Development loop:

**Design → Implement → Test → Verify → Record → Commit → Push → Continue**

## Non-Negotiable Quality Principle

> Forge must never accept "it works" as the complete definition of quality.

The target is software that remains understandable and maintainable as Forge grows over years.
