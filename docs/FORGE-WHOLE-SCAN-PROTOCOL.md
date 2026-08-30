# FORGE WHOLE SCAN PROTOCOL

Status: CANONICAL OPERATIONAL PROTOCOL
Term: **全体スキャン / Whole Scan**
Date: 2026-08-30

## Definition

When the CEO says **「全体スキャン」**, the acting Forge agent must not inspect only the current feature or recently changed files.

It means:

> **Scan the repository and active production path broadly against Forge's canonical goal, find drift/contradictions/stale claims/goal substitution, repair every safe and reversible deviation that can be repaired now, and explicitly record anything that remains.**

## Canonical invariant used by Whole Scan

> **持っている能力は組み合わせる。足りない能力は作る。作った能力は検証し、再利用可能な Forge Capability として取り込む。**

Forge must not substitute an easier local milestone for that goal.

The recurring failure mode to detect is:

```text
something looks easy/available
 -> implementation starts there
 -> that local implementation becomes the de facto target
 -> original product goal is silently narrowed
```

This is **goal substitution** and is a defect even if the local implementation is technically correct.

## Whole Scan coverage

At minimum inspect:

1. **Goal hierarchy**
   - `docs/FORGE-CORE-CONSTITUTION.md`
   - `docs/PRODUCT-DIRECTION.md`
   - `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
   - Local AI vision / current state / handoff / roadmap

2. **Agent and prompt instructions**
   - `AGENTS.md`
   - `CLAUDE.md`
   - `.agents/`
   - `.ai/`
   - `PROMPTS/`
   - production AI prompt/config surfaces

3. **Planning / capability system**
   - semantic decomposition
   - capability registry
   - support resolution
   - missing/partial truthfulness
   - extension/synthesis route

4. **Production generation path**
   - natural language intake
   - planner
   - compiler
   - schema/parser/validator
   - runtime
   - generated workspace
   - repair loop
   - evidence

5. **Pattern/template drift**
   - domain templates masquerading as generation
   - one-off Golden-specific runtime paths
   - widget-count or app-count KPI thinking
   - keyword -> fixed-template routing
   - hard-coded domain fallback

6. **Missing-capability behavior**
   - does Forge merely report unsupported and stop?
   - does it silently downgrade the request?
   - does it enter a safe synthesis/extension path?
   - can a validated new capability be promoted and reused later?

7. **Evidence truth**
   - IMPLEMENTED / TESTED / VERIFIED / DESIGNED / MOCK / STUB / UNVERIFIED
   - stale docs vs current code/CI
   - fake PASS / visual unknown / test-double confusion

8. **Architecture health**
   - duplicate implementations
   - dead parallel paths
   - production-unwired components
   - hidden technical debt
   - unsafe privileges / secret leakage / irreversible effects

9. **Goal-backward check for current work**
   - what final user outcome is this work serving?
   - is the current task only an implementation step?
   - are we accidentally treating the step as the destination?

## Required action during Whole Scan

Whole Scan is not a report-only exercise.

For each deviation:

- **FIX NOW** — safe/reversible and enough evidence exists: repair it in the same task.
- **DEFER** — valid but not safely completable now: record exact blocker and next action.
- **ACCEPT** — intentional trade-off consistent with canonical direction: document why.
- **UNKNOWN** — insufficient evidence: do not guess; create the smallest investigation needed.

Do not ask the CEO to approve ordinary reversible repairs. Stop only for Constitution/product-identity changes, destructive/irreversible state, major safety/privacy trade-offs, or other decisions reserved by `AGENTS.md`.

## Completion criteria

A Whole Scan is complete only when:

- findings are classified;
- safe deviations found in the scan are actually repaired;
- tests/CI/evidence are checked where changes affect production behavior;
- stale Source-of-Truth docs are updated or explicitly marked stale;
- remaining gaps are recorded with concrete next actions;
- the final summary distinguishes **what was fixed**, **what remains**, and **what evidence supports the state**.

A Whole Scan must never end with only "everything looks fine" unless the repository evidence genuinely supports that conclusion.
