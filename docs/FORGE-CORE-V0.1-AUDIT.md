# Forge Core v0.1 — Implementation Audit

**Date:** 2026-09-15  
**Status:** AUDIT BASELINE  
**Branch:** `claude/forge-master-handoff-k46jns`

## 1. Purpose

This audit determines what the current `forge_ai/core` implementation should become in Forge Core v0.1.

The criterion is **quality first**. Existing code is not retained merely because it works, and it is not discarded merely because it is old. Each component is evaluated as:

- **REUSE** — retain and improve where necessary.
- **REBUILD** — keep useful knowledge, but redesign/reimplement the mechanism.
- **REFERENCE** — keep as historical/learning material, without making new code depend on it.
- **RETIRE** — remove from the future Core path when safe.

## 2. First audit result

### Domain Model — REUSE / REFINEMENT

`Domain`, `DomainConcept`, and the registry provide a useful separation between a problem domain and UI. This is compatible with Forge's intent-to-software direction.

**Required refinement:** establish a stricter boundary between domain description, runtime data, and generated presentation.

### World Model — REBUILD / REFINEMENT

`World` already separates actors, objects, relationships, rules, events, states, and permissions. The structure is useful, but the current builder contains heuristic domain-to-world construction and must not become the final semantics of Forge.

**Required refinement:** separate declarative world knowledge from executable runtime state and from inferred hypotheses.

### Meaning Model — REBUILD

`ExtractedMeaning` is a useful boundary, and provider injection is good. However, the current implementation delegates extraction directly to an `AIProvider` and accepts structured output with limited Core-level semantics.

**Decision:** preserve the boundary and data provenance idea; redesign the formal meaning representation and validation contract.

### Intent Model — REBUILD

`Intent` contains useful concepts such as goal, required concepts/actions, constraints, success conditions, prohibited behaviors, confidence, and evidence. However, `IntentBuilder` currently relies directly on an AI provider and has optimistic fallbacks such as `add_item` / `item`.

**Decision:** preserve the concept of intent and evidence, but make the formal Core intent model provider-independent and explicitly distinguish candidate intent from validated intent.

### IR — STRONG REUSE / REBUILD AS A FORMAL CONTRACT

The existing IR direction is the strongest reusable foundation found so far. `ir_types.py` explicitly aims to be platform-independent and independent of Planner/Compiler implementation details. It already contains typed fields, validation rules, measurement semantics, entities, and view intent.

**Required refinement:** consolidate the IR family into one clearly versioned Core contract. Existing feature-specific additions must not silently become permanent Core semantics.

### Design Intent — REUSE OUTSIDE THE CORE

`DesignIntent` correctly demonstrates an important Forge rule: AI may choose from a closed vocabulary, Forge validates the choice, and fallback provenance is recorded. This is valuable for the quality system.

**Decision:** retain as an upper-layer design/quality capability, not as Core's fundamental semantic model.

### Compiler — REBUILD / MOVE TOWARD FORMAL BACKEND BOUNDARY

The existing Compiler contains valuable experience and explicit honesty about legacy/template limitations. It is not suitable as the final Core compiler contract because it still contains legacy Checklist behavior, hard-coded examples, visual presets, and compatibility behavior.

**Decision:** keep it as implementation evidence and transitional infrastructure. The future Forge Compiler should consume a stable Forge IR contract and produce a target artifact through a defined backend boundary.

### Critic / Confirmation — REUSE AS QUALITY LAYERS

These concepts align strongly with Forge's quality-first constitution: Forge must doubt its own output and return uncertainty to the user when needed.

**Decision:** keep them outside the minimal semantic Core and connect them through explicit evidence/validation interfaces.

## 3. Important finding

The current repository already contains significant Forge architecture. Therefore the correct next step is **not** to build a toy Core beside it.

The next implementation should instead extract a clean, deterministic kernel from the strongest existing concepts while preventing legacy behavior from defining the future architecture.

## 4. Core boundary to implement

```text
Candidate Model
    ↓
Core Model
    ↓
Validation
    ↓
Deterministic State / Operation Semantics
    ↓
Result + Error
    ↓
Evidence
```

AI, prompts, UI, HTTP, database, Flutter, and external providers remain outside this kernel.

## 5. First implementation target

Do not start by implementing the entire existing `forge_ai/core`.

First create the smallest high-quality deterministic kernel with:

1. explicit value/model types;
2. a formal validation contract;
3. explicit operation semantics;
4. deterministic state transition;
5. structured result/error;
6. evidence sufficient to reproduce and inspect execution;
7. tests that define the contract.

The shopping-list scenario may be used to exercise this kernel, but no shopping-specific concept belongs in the kernel.

## 6. Quality gate before implementation expands

The kernel must pass all of the following before adding AI or UI concerns:

- no duplicated semantic model;
- no implicit fallback that invents user intent;
- invalid input is rejected explicitly;
- state changes are deterministic;
- errors are structured and inspectable;
- execution can be reproduced;
- tests describe behavior rather than implementation details;
- Core has no dependency on an AI provider;
- Core has no dependency on Flutter, HTTP, database, or UI schema;
- boundary to future Runtime/Language is explicit;
- code can be explained by the implementer.

## 7. Immediate next step

The next work unit is to define the **Core Kernel Contract** before writing implementation code.

That contract will specify:

- what a valid Core value is;
- what an operation is;
- what state transition means;
- what validation guarantees;
- what Result/Error/Evidence contain;
- which responsibilities deliberately remain outside Core.

Only after that contract is approved should the user implement the first PowerShell-driven code unit.
