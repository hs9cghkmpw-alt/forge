# Forge Handoff

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current phase: **R1 Generated App Quality / Growing AI**
- Latest completed implementation before this handoff: **FORGE-020A4 / LEVEL0-PREFLIGHT-GUARD**
- Previous closeout: **FORGE-020A3B / CLOSEOUT-INTEGRITY-AND-CI-RECOVERY**
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
7. latest GitHub HEAD / diff / CI

Do not treat chat output as Source of Truth when GitHub has a newer fact.

---

## What FORGE-020A3B proved

`949ccb699a6a68cc3614e3acb9ed60a9595c3545` closed the main Level 0 integrity holes.
GitHub Actions run `33065820365` was independently observed as **success** before 020A4 began.

Level 0 requires independent evidence for:

- AI structure source (`AI_ENTITY_SYNTHESIS` for the current Level 0 path)
- `structure_provider == LOCAL`
- `structure_task == entity_synthesis`
- AIRouter actually observed `ENTITY_SYNTHESIS`
- `generation_source == LOCAL_AI`
- local deployment
- production Generation Evidence UID
- Validator PASS
- real verification

Cloud/Test Double/deterministic structure must not count as a Local structure-generation run.
Unknown Capability IDs fail loudly, and PARTIAL capabilities are not recorded as full success.

---

## What FORGE-020A4 added

Problem found during independent review: `verify_local_model_level0.py` checked
`domain_resolution` before using a real model, but `generated` alone does not prove the
software-structure job will reach Entity Synthesis. A probe can still be deterministic or
fall back after a rejected synthesis, wasting a slow CPU Local Model run and ending as
`INVALID_PROBE`.

Added:

- `backend/app/ai/gateway/level0_preflight.py`
- `scripts/preflight_local_model_level0.py`
- `backend/tests/test_forge_020a4_level0_preflight.py`
- `docs/evidence/level0-preflight/README.md`
- `docs/reports/FORGE-020A4-LEVEL0-PREFLIGHT-GUARD-report.md`

The preflight uses the real production `/generate` path with `provider=mock` and typed
`GenerationRecord` evidence. It checks that the Need actually reaches and accepts
`ENTITY_SYNTHESIS` under a Test Double before spending a real Local Model call.

**Preflight is not Level 0.** It cannot increment `Real Local Model runs` and cannot prove
the real model can synthesize the structure.

---

## Next operator action — Runtime-capable PC

On whichever PC currently has a real Local Runtime:

```text
# 1. Update the branch safely; preserve any local uncommitted work first.
# 2. Inspect environment.
python scripts/forge_doctor.py

# 3. Cheap structural eligibility check first. No real model is used.
python scripts/preflight_local_model_level0.py

# 4. Only if outcome == eligible_for_real_run, configure the actual runtime/model and run:
python scripts/verify_local_model_level0.py
```

On Windows PowerShell with the previously used Ollama-compatible setup, environment values
must be set for that machine/session before step 4. Do not commit machine-specific paths,
credentials or secrets.

Only an actual Level 0 **PASS** may change `Real Local Model runs` from 0 to 1.
`INVALID_PROBE`, `FAILED`, Test Double, deterministic structure, Cloud structure, or
Design-Intent-only Local calls may not count.

If real Entity Synthesis is rejected, use the closed rejection reason evidence to improve
the synthesis path. **Do not relax the Level 0 gate to manufacture PASS.**

---

## Next implementation task after the real run

If Level 0 passes, independently review the Evidence first. Then move to
**FORGE-020B / Tool-Using Local Agent production wiring**:

`Need → plan → retrieve/tool → generate → build/test → inspect → repair`

Do not turn 020B into a finite Widget/template selector. Existing 020B contract/tests are not
production wiring until the production path actually invokes them and Evidence proves it.

If Level 0 does not pass, stay in 020A and fix the observed structure-generation failure
before 020B.

---

## Known debt to carry forward

During 020A4 review, `GenerationRecord` was observed to contain
`entity_synthesis_attempted`, `entity_synthesis_accepted`, and
`entity_synthesis_rejection_reason`, while the reviewed `GenerationRecord.to_dict()` did not
serialize those three fields. The new Level 0 preflight JSON writes them explicitly, so the
operator diagnosis is preserved, but the generic serializer gap remains.

Next implementation agent should re-check current HEAD and, if still true, add those closed,
privacy-safe fields to the generic Evidence serialization with a regression test. **Do not
store prompt/raw model output/user text.**

---

## Verification / CI rule

A task is not complete because files exist. For every implementation:

1. focused tests
2. backend / forge_ai full tests where supported
3. Flutter analyze/test/build where touched or required
4. GitHub Actions
5. `docs/HANDOFF.md`
6. task report under `docs/reports/`
7. commit/push
8. verify latest remote HEAD and CI

Unsupported machine-specific checks remain **UNVERIFIED**, never silently PASS.

Historical details and older operator notes remain in the dated reports, CHANGELOG and
TECH_DEBT rather than being copied indefinitely into this handoff.
