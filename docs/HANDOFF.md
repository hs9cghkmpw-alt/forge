# HANDOFF UPDATE — FORGE-020A4C Real Structure Integrity Gate

**Current task:** FORGE-020A4C — separate raw Local model contract ability from Forge repair ability.

- Base SHA: `e659181427224242458561a06a32af01b8295023`.
- Base CI run `33175691427`: SUCCESS / 4 jobs green.
- Implementation: contract-repair evidence + structured-output mode provenance + fail-closed Level 0 gate + serializer diagnosis + mutation-oriented tests.
- Mock preflight proves wiring only. It is not semantic/model-quality evidence.
- Normal product sanitization remains; repaired output can still make a usable app, but **cannot count as Real Local Level 0**.
- Real Local Model runs: **0** until a genuine unrepaired strict-contract Local structural run passes.
- **Do not run real Qwen Level 0 until this task's exact-SHA CI is green.**
- Detailed report: `docs/reports/FORGE-020A4C-REAL-STRUCTURE-INTEGRITY-report.md`.

### Next operator checklist
1. Read this HANDOFF and the 020A4C report before editing.
2. Verify branch HEAD and exact-SHA CI; do not trust chat-only claims.
3. If green, use a real Local runtime machine for preflight, then Qwen Level 0.
4. Preserve the distinction: model contract -> Forge repairs -> final artifact.
5. Never promote Forge-repaired output as an AI positive in future Dataset/JSONL/SFT/preference/QLoRA work.

---

# Forge Handoff

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current phase: **R1 Generated App Quality / Growing AI**
- Latest implementation in this handoff: **FORGE-020A4B / STAGE-AWARE-STRUCTURE-ROUTING**
- Previous diagnostic task: **FORGE-020A4 / LEVEL0-PREFLIGHT-GUARD**
- Golden Quality Gate: **FAIL**（既存理由。PASSへ書き換えていない）
- **Real Local Model runs: 0**
- Mobile access is a product-level goal: `docs/PRODUCT-DIRECTION.md` §9
- Detailed history is in task reports; this file intentionally stays short and current.

## Source of Truth to read first

1. `docs/PRODUCT-DIRECTION.md`
2. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
3. `docs/LEARNABLE-LOCAL-AI-VISION.md`
4. `docs/MACHINE-INDEPENDENT-POLICY.md`
5. `docs/reports/FORGE-020A3B-CLOSEOUT-report.md`
6. `docs/reports/FORGE-020A4-LEVEL0-PREFLIGHT-GUARD-report.md`
7. `docs/reports/FORGE-020A4B-STAGE-AWARE-STRUCTURE-ROUTING-report.md`
8. latest GitHub HEAD / diff / CI

Do not treat chat output as Source of Truth when GitHub has a newer fact.

---

## What was independently verified before 020A4B

Start HEAD:

`09d61ffe1b4f58fd42b896d9ded555059ecdef70`

GitHub Actions run:

`33173168856`

was independently observed as **completed / success** before 020A4B implementation started.

020A4 had already proven that a cheap Test Double production run can reveal an unsuitable
Level 0 probe before spending a slow real Local Model call.

It also measured two real blockers:

1. backend `MockLLMAdapter` flattened `fields: array<object>` into strings, so
   Entity Synthesis ended as `no_valid_fields`;
2. `PromptPipeline` bound the whole Cognitive Pipeline as `COGNITIVE_STAGE`, so even a real
   Entity Synthesis call was not observed by AIRouter as `ENTITY_SYNTHESIS`.

Those facts were kept as failures rather than weakening the Level 0 gate.

---

## What FORGE-020A4B changes

### 1. Stage-aware AIRouter attribution

`backend/app/ai/runtime/forge_ai_provider_bridge.py` now maps:

- `entity_synthesis` → `ForgeTask.ENTITY_SYNTHESIS`
- all other current Cognitive stages → `ForgeTask.COGNITIVE_STAGE`

The existing request-local BoundAdapter is switched only for the call and restored in
`finally`, including exception paths.

This does **not** create a second router. AIRouter remains the only AI execution exit.

### 2. Test Double nested-schema fidelity at the Bridge boundary

The existing backend Mock can produce shallow values for nested JSON Schema. The Bridge now
repairs schema shape **only when the actual provider used is exactly `mock`**.

The repair is recursive for object/array/scalar shapes and is intended only to make the Test
Double exercise the same downstream Entity Synthesizer / IR / Validator wiring.

Critical boundary:

- `mock` may be repaired for Test Double fidelity;
- `local`, Cloud, Gemini, or any real provider output is **never repaired by this guard**;
- a broken real Local structure must remain broken and fail Level 0.

This prevents Forge-generated fallback values from manufacturing a Real Local PASS.

### 3. Production E2E must prove both fixes together

`backend/tests/test_forge_020a4_level0_preflight.py` now requires the default generated probe
to produce:

- `domain_resolution=generated`
- `structure_source=AI_ENTITY_SYNTHESIS`
- `structure_provider=TEST_DOUBLE`
- `structure_task=entity_synthesis`
- `ENTITY_SYNTHESIS` observed in AIRouter Experience
- `COGNITIVE_STAGE` still observed for non-structure stages
- Entity Synthesis attempted + accepted
- Validator PASS
- durable Generation Evidence UID
- `eligible_for_real_run`

The curated household-budget trap must still be rejected.

`backend/tests/test_forge_020a4b_bridge_routing.py` additionally guards:

- dedicated task switching;
- restoration to `COGNITIVE_STAGE`;
- no task leakage after exceptions;
- no Test Double repair for `local` provider output.

If any one of these assertions is relaxed merely to make CI green, the Level 0 integrity
contract is broken.

---

## Verification state for 020A4B

- Source syntax was checked before commit.
- Production E2E and full repository tests are delegated to GitHub Actions because this
  ChatGPT execution environment does not have the repository runtime/dependencies.
- Latest implementation CI: **PENDING**.
- Real Local Model execution: **NOT RUN**.
- Real Local Model runs remain **0**.

The task report must be updated with the exact final implementation SHA and CI run before
020A4B is called fully closed.

---

## Next operator action — Runtime-capable PC

After the final 020A4B CI is green, on whichever PC currently has the Local Runtime:

```text
# Preserve unknown local work first; then update this branch safely.
python scripts/forge_doctor.py

# Cheap Test Double control. Expected after 020A4B:
python scripts/preflight_local_model_level0.py
# outcome == eligible_for_real_run

# Only then configure the actual Runtime/model for that machine/session.
# Example for the previously used Ollama OpenAI-compatible runtime:
$env:FORGE_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"
$env:FORGE_LOCAL_MODEL="qwen2.5:7b-instruct"

python scripts/verify_local_model_level0.py
```

Only an actual real-model **PASS** may change `Real Local Model runs` from 0 to 1.

`INVALID_PROBE`, `FAILED`, Test Double, deterministic structure, Cloud structure, or
Design-Intent-only Local calls may not count.

If the Local model produces a bad Entity Spec, keep the failure evidence and improve the
model/prompt/retrieval path. **Do not add a Local-output repair that invents a passing
structure.**

---

## Next implementation task after real Level 0

If Level 0 passes, independently review the Evidence first. Then move to:

**FORGE-020B / Tool-Using Local Agent production wiring**

Target loop:

`Need → plan → retrieve/tool → generate → build/test → inspect → repair`

This must remain a Generative Software Engine path, not a finite Widget/template selector.

If Level 0 does not pass, remain in 020A and fix the observed Local structure-generation
failure before 020B.

---

## Known debt to carry forward

### GenerationRecord generic serialization

`GenerationRecord` contains:

- `entity_synthesis_attempted`
- `entity_synthesis_accepted`
- `entity_synthesis_rejection_reason`

but the previously reviewed generic `GenerationRecord.to_dict()` did not serialize those
three fields.

The Level 0 preflight writes the closed diagnosis fields explicitly, so operator diagnosis is
not lost, but the generic Evidence serializer gap remains.

Fix separately with a privacy-safe regression test. Do **not** store prompt, raw model output,
or user text.

### Mock implementation boundary

020A4B guarantees nested-schema fidelity at the **production Bridge/Test Double boundary**.
The legacy `MockLLMAdapter` implementation itself remains a shallow deterministic Mock when
called directly outside that Bridge. Do not misreport this as a general LLM-quality upgrade.

---

## Verification / handoff rule

A task is not complete because files exist. For every implementation:

1. focused tests
2. backend / forge_ai full tests where supported
3. Flutter analyze/test/build where required
4. GitHub Actions
5. `docs/HANDOFF.md`
6. task report under `docs/reports/`
7. commit/push
8. verify latest remote HEAD and latest CI for that exact SHA

Unsupported machine-specific checks remain **UNVERIFIED**, never silently PASS.
