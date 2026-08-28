# FORGE-020A4 — LEVEL0 PREFLIGHT GUARD

- Date: 2026-08-28
- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD reviewed: `949ccb699a6a68cc3614e3acb9ed60a9595c3545`
- Implementation agent: ChatGPT
- Previous task: `FORGE-020A3B / CLOSEOUT-INTEGRITY-AND-CI-RECOVERY`

## 1. Independent review of 020A3B

`949ccb6` and GitHub Actions run `33065820365` were independently checked before
starting this task. The run completed **success**. 020A3B materially closed the earlier
false-PASS hole by requiring structure source, provider and task independently for Level 0;
it also stopped unknown Capability IDs from silently becoming MISSING and prevented PARTIAL
capabilities from being recorded as full successes.

`Real Local Model runs` remains **0**. No real model was executed in this task.

## 2. Remaining operational hole found

`verify_local_model_level0.py` already checked `domain_resolution` before spending a real
model call, but that is not sufficient.

A Need can be `domain_resolution=generated` and still fail to measure Local structure
generation because:

1. a deterministic Capability Plan makes the software structure before the model;
2. Entity Synthesis is attempted but rejected and a fallback wins;
3. the expected structure task/provider was not actually observed.

The previous real Qwen runs demonstrated this class of failure: HTTP 200 and Validator PASS
can still end as `INVALID_PROBE` when the Local Model did not own the structure.

For a CPU-only 7B model this can waste minutes per attempt. The verifier was strict enough
**after** the run, but did not reject obviously unsuitable probes **before** the run.

## 3. Implemented: typed Level 0 Probe Preflight

Added:

- `backend/app/ai/gateway/level0_preflight.py`
- `scripts/preflight_local_model_level0.py`
- `backend/tests/test_forge_020a4_level0_preflight.py`
- `docs/evidence/level0-preflight/README.md`

The command:

```text
python scripts/preflight_local_model_level0.py
```

runs production `/api/v1/ai/generate` with `provider=mock`, then evaluates typed production
Evidence. It never imports or writes `RealLocalModelRunLog`.

`ELIGIBLE_FOR_REAL_RUN` requires all of the following in the Test Double control run:

- `domain_resolution=generated`
- `structure_source=AI_ENTITY_SYNTHESIS`
- `structure_provider=TEST_DOUBLE`
- `structure_task=ForgeTask.ENTITY_SYNTHESIS.value`
- AIRouter observation includes `ENTITY_SYNTHESIS`
- Entity Synthesis was attempted **and accepted**
- production `GenerationRecord.uid` exists
- Validator passed

This means only:

> production control flow gives software-structure work to Entity Synthesis for this Need.

It does **not** mean Local Model success. It does **not** increment Real Local Model runs.
The real next step remains `scripts/verify_local_model_level0.py` on a Runtime-capable host.

## 4. Failure taxonomy

Preflight outcomes are explicit:

- `eligible_for_real_run`
- `curated_bypass`
- `deterministic_bypass`
- `synthesis_rejected`
- `wrong_provider`
- `wrong_task`
- `validation_failed`
- `unobservable`

A synthesis rejection includes only the existing closed rejection reason code. No model raw
output, prompt or generated document body is written to the preflight evidence.

## 5. Tests / mutation guards

The new tests guard these failure modes:

- curated probe cannot be eligible;
- deterministic structure cannot be eligible;
- rejected Entity Synthesis stays a rejection and exposes the closed reason code;
- CLOUD or LOCAL cannot masquerade as the mock preflight provider;
- `ENTITY_SYNTHESIS` task must be both attributed and observed;
- lookalike task strings do not pass;
- missing Generation Evidence UID does not pass;
- Validator failure does not pass;
- serialized preflight result has no Need/raw-output/prompt field;
- production integration checks the default probe reaches mock Entity Synthesis;
- the known household-budget Curated trap is rejected.

The CI run for the final implementation/doc HEAD must be checked after handoff commit. Do not
mark this task complete if the latest 4-job CI is not all green.

## 6. Important debt discovered during review

`GenerationRecord` contains:

- `entity_synthesis_attempted`
- `entity_synthesis_accepted`
- `entity_synthesis_rejection_reason`

but the currently reviewed `GenerationRecord.to_dict()` does **not** serialize those three
fields. The new preflight JSON writes them explicitly so Level 0 diagnosis is not lost, but
this is still a generic Evidence serialization gap.

Next implementation agent should fix that separately with a privacy-safe regression test,
unless the serializer contract has changed by then. Do not store raw model output while
fixing it.

## 7. Product-direction check

This change does not add a Widget/template or narrow Forge generation. It improves the
measurement loop around Forge-owned Local AI:

`Need → production path → structure ownership Evidence → real Local measurement`.

It also keeps Execution Host independence: preflight can run on a machine without Ollama;
the actual Level 0 run remains on whichever machine currently has a real Local Runtime.

The mobile product goal in `docs/PRODUCT-DIRECTION.md` remains unchanged: Client location and
Execution Host location are independent.

## 8. Next handoff

1. Verify latest GitHub Actions: all four jobs must be green.
2. On a Runtime-capable Execution Host, pull latest branch.
3. Run `python scripts/forge_doctor.py`.
4. Run `python scripts/preflight_local_model_level0.py` first.
5. Only if it returns `eligible_for_real_run`, configure the real runtime/model and run
   `python scripts/verify_local_model_level0.py`.
6. PASS alone may change `Real Local Model runs` from 0 to 1. INVALID_PROBE/FAILED may not.
7. If real Entity Synthesis is rejected, use the closed rejection reason evidence; do not
   relax the Level 0 gate to manufacture a PASS.
8. After real Level 0 is proven, review 020B Tool-Using Local Agent production wiring. Do not
   skip the actual Level 0 evidence milestone.
