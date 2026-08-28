# FORGE-020A4B — STAGE-AWARE STRUCTURE ROUTING

- Date: 2026-08-28
- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `09d61ffe1b4f58fd42b896d9ded555059ecdef70`
- Start HEAD CI: GitHub Actions run `33173168856` = **success**
- Implementation agent: ChatGPT
- Real Local Model runs before task: **0**

## 1. Why this task exists

FORGE-020A4 added a strict Level 0 preflight rather than spending minutes on a real Local
Model before discovering that software-structure generation never reached the measured AI
stage.

The production integration test then exposed two blockers instead of hiding them:

### Blocker A — Test Double nested schema mismatch

The backend deterministic `MockLLMAdapter` handled arrays generically as scalar values.
For Entity Synthesis, the response schema requires:

`fields: array<object>`

but the actual Test Double returned string values. `EntitySynthesizer` therefore discarded
all fields and recorded:

`entity_synthesis_rejection_reason = no_valid_fields`

The final structure then fell back to a non-AI path.

### Blocker B — AIRouter task attribution was too coarse

`PromptPipeline` bound one adapter as `ForgeTask.COGNITIVE_STAGE` for the entire Cognitive
Pipeline. Entity Synthesis was physically called, but Experience evidence still recorded only
`COGNITIVE_STAGE`.

020A3B correctly requires an actual observed `ForgeTask.ENTITY_SYNTHESIS` for Level 0.
Therefore the old wiring could not honestly satisfy the gate.

The correct response is to fix the wiring, not weaken the gate.

---

## 2. Architecture chosen

### Stage-aware routing belongs at `ForgeAIProviderBridge`

`forge_ai` must remain backend-independent. It knows stage names but not backend AIRouter
implementation details.

The Bridge is already the boundary where:

`forge_ai Prompt → backend LLMAdapter/AIRouter`

is converted.

Therefore 020A4B keeps one AIRouter and one request-local BoundAdapter, but changes the task
seen by that adapter for the specific call:

- `entity_synthesis` → `ForgeTask.ENTITY_SYNTHESIS`
- current remaining stages → `ForgeTask.COGNITIVE_STAGE`

The task is restored in `finally`.

This avoids:

- a second router;
- direct Provider calls;
- backend imports inside `forge_ai`;
- global/shared mutable task state.

### Test Double schema repair also belongs at the Bridge boundary

The Bridge owns the response schema and knows which actual provider answered.

For production preflight, the deterministic Test Double must preserve nested JSON shape so
the downstream Entity Synthesizer / IR / Validator wiring can be exercised.

020A4B therefore repairs schema shape recursively **only when**
`last_provider_used == "mock"`.

It does not repair Local/Cloud/Gemini output.

That distinction is critical. A real Local Model that emits invalid structure must fail;
Forge must not invent fields after the fact and count them as Local generation.

---

## 3. Implementation

### `backend/app/ai/runtime/forge_ai_provider_bridge.py`

Added stage → task mapping:

```text
entity_synthesis -> ENTITY_SYNTHESIS
otherwise        -> COGNITIVE_STAGE
```

For the request-local BoundAdapter:

1. remember original task;
2. switch only when required;
3. call normal `complete_structured()`;
4. restore original task in `finally`.

Added recursive Test Double schema-shape repair for:

- object
- array
- string / enum
- boolean
- integer
- number

It is guarded by the **actual provider used**, exact `mock` match.

### `backend/tests/test_forge_020a4_level0_preflight.py`

The temporary diagnostic assertion that expected `SYNTHESIS_REJECTED` is removed only because
the production wiring is now required to fix the cause.

The default generated probe must now prove the full Test Double control path:

- generated domain resolution
- AI Entity Synthesis structure source
- Test Double structure provider
- `structure_task=entity_synthesis`
- `ENTITY_SYNTHESIS` actually observed
- `COGNITIVE_STAGE` still observed for other stages
- attempted + accepted synthesis
- Validator PASS
- durable Generation Evidence UID
- preflight `eligible_for_real_run`

The known Curated trap remains rejected.

### `backend/tests/test_forge_020a4b_bridge_routing.py`

Added focused mutation guards:

1. Entity Synthesis uses `ENTITY_SYNTHESIS`.
2. The BoundAdapter task is restored afterward.
3. Non-structure stages remain `COGNITIVE_STAGE`.
4. Exception paths restore the task.
5. `local` output is not repaired by the Test Double schema guard.

Mutation meaning:

- map Entity Synthesis back to COGNITIVE → fail;
- remove task restoration → fail;
- remove nested Test Double repair → fail;
- apply mock repair to Local → fail.

---

## 4. What this does NOT prove

This task does not run a real Local Model.

It does not prove Qwen can generate an acceptable Entity Spec.

It does not increase:

`Real Local Model runs: 0`

The Test Double is a control for production wiring only.

Level 0 still requires a real open-weight model on a Runtime-capable Execution Host, using the
production path, with typed structure provenance, AIRouter task evidence, Validator PASS and
durable Generation Evidence.

---

## 5. Verification

Before commit:

- Python syntax of changed/new Python files checked.
- Start HEAD exact CI checked: `33173168856` = success.

After implementation commit:

- focused test: delegated to GitHub Actions
- forge_ai full tests: delegated to GitHub Actions
- backend full tests Python 3.11/3.12: delegated to GitHub Actions
- backend smoke: delegated to GitHub Actions
- Flutter CI: delegated to GitHub Actions
- final implementation CI: **PENDING**

This report must be amended with the exact implementation SHA and exact CI run after GitHub
finishes.

---

## 6. Next action after green CI

On a machine with the actual Local Runtime:

```text
python scripts/forge_doctor.py
python scripts/preflight_local_model_level0.py
```

Expected control result:

`eligible_for_real_run`

Only then configure that machine's actual Local Runtime/model and run:

```text
python scripts/verify_local_model_level0.py
```

For the previously used Ollama-compatible host, the intended first model remains
`qwen2.5:7b-instruct`.

Only real **PASS** changes Local runs 0 → 1.

Do not:

- relax structure provenance;
- treat HTTP 200 as proof;
- count Design Intent-only Local use;
- count deterministic Capability Plan output;
- repair real Local output into a passing structure.

If the real Local model fails, keep the exact closed failure evidence and improve the
generation path.

---

## 7. Carry-forward debt

### Generic GenerationRecord serializer

Re-check and fix separately if still present:

`GenerationRecord.to_dict()` previously omitted:

- `entity_synthesis_attempted`
- `entity_synthesis_accepted`
- `entity_synthesis_rejection_reason`

These are closed privacy-safe fields. Do not add prompt/raw output/user text.

### Legacy Mock outside Bridge

020A4B makes the **production Bridge/Test Double path** schema-faithful. Direct calls to the
legacy backend Mock outside the Bridge remain shallow. This is not a general model-quality
upgrade and must not be described as one.

---

## 8. Product-direction check

No dedicated application Widget/template was added.

This task strengthens the measurable generative path:

`Need → AI structure stage → AIRouter task evidence → IR → Validator → durable Evidence`

and preserves the long-term direction:

`think → build → run → inspect → repair`

with Real Local generation measured independently from deterministic Forge machinery.
