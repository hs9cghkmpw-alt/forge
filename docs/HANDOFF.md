# Forge Handoff — current Source of Truth

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current completed task: **FORGE-020A4C — Real Structure Integrity Gate**
- Final implementation SHA: `b29d7504b184edaac4944eb42fffec4ab8587c7b`
- 020A4C closeout workflow: **run `33217747922` = SUCCESS**
- Closeout verification:
  - focused 020A4C / production-path tests: PASS
  - `forge_ai`: **592 passed**
  - backend: **1906 passed, 17 skipped, 1 warning**
  - syntax / `git diff --check`: PASS
  - one-shot apply/finalize/fix workflow and helper scripts: **removed before final implementation commit**
- Golden Quality Gate: **FAIL** for the previously recorded Generated App Quality reasons; do not rewrite this to PASS without a new visual-quality run.
- Real Local Model runs: **0**
- Real `qwen2.5:7b-instruct` Level 0: **NOT YET EXECUTED**. Do not claim success until real production-path evidence says so.

Detailed report: `docs/reports/FORGE-020A4C-REAL-STRUCTURE-INTEGRITY-report.md`

## What 020A4C now guarantees

Real Local Level 0 is a claim about **model structural ability**, not merely final app validity.
The evidence path now separates:

`raw model contract -> Forge repairs -> final artifact`

A Local structural run may count only when all required provenance is present and the raw Entity Synthesis output:

1. came from the Local provider on the actual `ENTITY_SYNTHESIS` task;
2. used an accepted schema mode (`strict_json_schema` or `json_schema`);
3. satisfied the Entity model contract before Forge repair;
4. required no Forge Entity sanitizer repair;
5. traversed the production generation path and Validator;
6. has durable Generation Evidence and REAL verification.

`JSON_OBJECT`, prompt-only JSON, unknown mode, repaired output, deterministic structure, Cloud structure, Test Double structure, curated output, and Design-Intent-only Local calls cannot be promoted to a Real Local Level 0 PASS.

Product robustness remains separate: Forge may still repair a model result to produce a usable app. That repaired artifact is **not** positive model-training evidence.

## Independent skeptical-closeout findings already fixed

The first 020A4C implementation was not accepted merely because focused tests were green. Full review found and closed:

- optional `required` omission being misclassified as a repair;
- Prompt max-6-fields vs sanitizer max-8-fields allowing 7/8 fields to masquerade as strict model success;
- legacy RealLocal passing fixtures lacking the new fail-closed contract evidence;
- Privacy guard not yet classifying structured-output mode as a closed identifier;
- mechanical Markdown quoting damage in `CHANGELOG.md` / `TECH_DEBT.md`.

The final closeout then ran the full suites successfully before committing `b29d7504...`.

## Source of Truth to read first

1. `docs/PRODUCT-DIRECTION.md`
2. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
3. `docs/LEARNABLE-LOCAL-AI-VISION.md`
4. `docs/MACHINE-INDEPENDENT-POLICY.md`
5. `docs/reports/FORGE-020A4C-REAL-STRUCTURE-INTEGRITY-report.md`
6. latest GitHub HEAD / diff / CI

Chat-only status is never the Source of Truth when GitHub has newer evidence.

## Next execution gate — real Local Level 0

On whichever machine currently has a real Local runtime and model, first update this branch safely and preserve unknown local changes. Then run:

```text
python scripts/forge_doctor.py
python scripts/preflight_local_model_level0.py
```

Preflight must be `eligible_for_real_run`. Only then configure the real runtime/model for that session, for example:

```text
FORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
FORGE_LOCAL_MODEL=qwen2.5:7b-instruct
```

and run:

```text
python scripts/verify_local_model_level0.py
```

Only a genuine unrepaired schema-contract Local structural PASS may change **Real Local Model runs 0 -> 1**. If it fails, retain the failure evidence and fix the observed model/prompt/retrieval problem. Do not weaken the gate or add a Local-output repair merely to manufacture PASS.

## What follows after genuine Level 0

After independently reviewing the real-model evidence, proceed to **FORGE-020B — Tool-Using Local Agent production wiring**.

Target loop:

`Need -> plan -> retrieve/tool -> generate -> build/test -> inspect -> repair`

This remains a **Generative Software Engine** path. Widgets/components/templates are primitives, not the ceiling of software generation.

## Persistent product / AI rules

- No permanent development PC or permanent agent assumption. GitHub + committed Markdown are the baton.
- Environment-specific checks that cannot run are `UNVERIFIED`, never fabricated PASS.
- Cloud/teacher output is a candidate, not truth. Objective Validator/build/test/runtime/visual/user evidence decides eligibility.
- Generation Episodes / Dataset JSONL must preserve model output, Forge repairs, final artifact, provider/model/tool provenance, objective scores, consent/training-rights and lineage.
- Forge-repaired outputs must not be labeled as positive SFT/preference/QLoRA examples for the model behavior that failed.
- No uncontrolled online weight update from one user event.
- Missing capability must eventually flow through controlled Self-Extension: spec -> sandbox process -> generate -> build -> test -> security/runtime/visual verification -> temporary capability -> evidence-backed promotion.

## Completion / handoff rule

For implementation tasks, completion requires code + focused/full tests + relevant frontend checks + GitHub Actions + task report + this handoff + pushed remote state. Exact evidence and `UNVERIFIED` items must be recorded; do not leave chat as the only record.
