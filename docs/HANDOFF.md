# Forge Handoff — current Source of Truth

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current completed task: **FORGE-020A5 — Real Local Level 0 Closeout**
- 020A5 product fix SHA: `9e515c03f56cd49eb4b0a6d0440a53e15501adc5`
- Real-run trigger SHA: `b0a9fe64c18bf264bbb7c199336aafa913d5460d`
- Normal CI on real-run trigger: run `33219195713` = **SUCCESS**, all four jobs green
- Genuine real Local Level 0: run `33219195627` = **SUCCESS / PASS**
- Durable passing evidence: `docs/evidence/level0/level0-20260828-230922.json`
- GitHub Actions evidence artifact: id `9704599776`, digest `sha256:b25e85df4b0115db0b824cb83f71b05bd493dabfad9a2038c69d84984b8d9e17`
- Real Local Model runs: **1**
- Baseline-ready runs: **1**
- 020A5 cleanup workflow: run `33219996032` = **SUCCESS**
- Cleanup commit: `3bcf1a5683f4f06d66b80f9de1d3c55f6d6ad997`
- One-off 020A5 apply/repair/real-run/closeout workflow machinery: **removed**
- `.github/workflows/` after cleanup: only normal `ci.yml`
- Golden Generated App Quality Gate: **FAIL** from the latest visual review. No new visual-quality run was performed in 020A5; do not rewrite it to PASS.

Detailed closeout report: `docs/reports/FORGE-020A5-REAL-LOCAL-LEVEL0-CLOSEOUT-report.md`

## What is now proven

A real open-weight Local model has generated software structure through Forge's production path without a curated/deterministic structural substitute and without Forge repairing the model's Entity structure before capability evidence was counted.

Real execution evidence:

- runtime: Ollama `0.33.2`
- model: `qwen2.5:7b-instruct`
- model digest: `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e7047ca97d631a0b697e`
- quantization: `Q4_K_M`
- probe Need remained `domain_resolution=generated`
- `generation_source=local_ai`
- `structure_source=ai_entity_synthesis`
- `structure_provider=local`
- `structure_task=entity_synthesis`
- observed tasks include `entity_synthesis` and `cognitive_stage`
- `structured_output_mode=json_schema`
- raw Entity strict contract PASS
- Entity sanitizer repairs: none
- Forge Validator PASS
- production Generation Evidence UID: `04cb5545745940e8a4d85be4a674deb8`
- verification: REAL
- `counts_as_real_local=true`
- `ready_for_baseline=true`
- Level 0 verifier exit code: 0

This closes the prior state that said “Real Local Model runs = 0 / NOT YET EXECUTED”.

## 020A5 contract alignment

The first real GitHub-hosted qwen run failed closed because its raw Entity output needed `identifier_normalized`. That was correctly not counted as model ability. The run exposed that Prompt, provider JSON schema and strict evidence were not deriving all structural limits from one contract.

020A5 added the canonical provider-independent contract at:

`forge_ai/core/semantics/entity_contract.py`

Current structural limits:

- identifier: `^[a-z][a-z0-9_]*$`
- fields: 1–6
- choice values: 2–6

PromptBuilder, provider schema and strict evidence consume the same contract. Product-side sanitization may be more permissive for robustness, but repaired outputs do not become positive raw-model evidence.

020A5 verification before the real rerun:

- provider-schema focused tests: 7 passed
- Entity-contract evidence tests: 8 passed
- real-structure integrity tests: 6 passed
- Level 0 preflight tests: 13 passed
- Local model path tests: 51 passed
- full `forge_ai`: 593 passed
- full backend: 1913 passed, 17 skipped, 1 warning

## Level 0 integrity rule remains fail-closed

A Local structural run counts only when the evidence proves all required facts, including:

1. a real Local deployment/model was used;
2. the actual structure provider was Local;
3. the actual structural stage was `entity_synthesis`;
4. the structure source was AI Entity Synthesis rather than curated/deterministic fallback;
5. an accepted structured-output mode was recorded;
6. the raw model Entity contract passed;
7. no Forge Entity sanitizer repair was needed;
8. the generation traversed the production path and Validator;
9. durable Generation Evidence exists;
10. verification is REAL.

Cloud structure, Test Double structure, deterministic structure, curated fallback, unknown output mode, repaired model structure, missing Evidence, or provider/source/task mismatches must continue to fail this gate.

## What is not proven yet

- The latest Generated App Quality Golden Gate remains **FAIL**; Level 0 success does not override visual/product-quality evidence.
- Browser/Playwright visual inspection was not part of this real-model run.
- The real runner recorded 0 MB VRAM; no GPU performance claim is supported by this run.
- One successful Level 0 episode is not enough to promote an SFT/QLoRA/preference dataset sample or adapter without future eligibility, privacy/training-rights and benchmark gates.
- The full Local software agent loop `think -> search/retrieve -> build -> run -> inspect -> repair` is not yet production-wired.

These are **next-stage product capabilities**, not unfinished 020A5 cleanup.

## Source of Truth to read first

1. `docs/PRODUCT-DIRECTION.md`
2. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
3. `docs/LEARNABLE-LOCAL-AI-VISION.md`
4. `docs/MACHINE-INDEPENDENT-POLICY.md`
5. `docs/reports/FORGE-020A5-REAL-LOCAL-LEVEL0-CLOSEOUT-report.md`
6. `docs/evidence/level0/level0-20260828-230922.json`
7. latest GitHub HEAD / diff / CI

Chat-only status is never the Source of Truth when GitHub has newer evidence.

## Next task — FORGE-020B Tool-Using Local Agent production wiring

Do not create a disconnected agent demo. Wire the existing Local provider into a production agent loop:

`Need -> plan -> retrieve/tool -> generate -> build/test -> inspect -> repair`

020B implementation must preserve the existing evidence/provenance boundary and prepare the trajectory for Generation Episodes:

- typed tool request / result / error contracts;
- permission/safety boundary before side-effecting tools;
- production wiring through existing provider/router paths;
- deterministic build/test/runtime observations as objective evidence;
- explicit repair attempt lineage;
- no model self-confidence as success truth;
- no dedicated app/game widgets as the generative ceiling;
- future web/browser tools must treat retrieved pages as untrusted data, not instructions.

The long-term target remains a **Generative Software Engine**, not a finite widget/template selector.

## Persistent product / AI rules

- No permanent development PC or permanent agent assumption. GitHub + committed Markdown are the baton.
- Environment-specific checks that cannot run are `UNVERIFIED`, never fabricated PASS.
- Cloud/teacher output is a candidate, not truth. Validator/build/test/runtime/visual/user evidence determines eligibility.
- Generation Episodes / Dataset JSONL must preserve model output, Forge repairs, final artifact, provider/model/tool provenance, objective scores, consent/training-rights and lineage.
- Forge-repaired outputs must not be labeled positive SFT/preference/QLoRA examples for model behavior that failed.
- No uncontrolled online weight update from one user event.
- Missing capability must eventually flow through controlled Self-Extension: spec -> sandbox process -> generate -> build -> test -> security/runtime/visual verification -> temporary capability -> evidence-backed promotion.

## Completion / handoff rule

Implementation completion requires code + focused/full tests + relevant frontend checks + GitHub Actions + task report + this handoff + pushed remote state. Exact evidence and `UNVERIFIED` items must be recorded. Do not leave chat as the only record.
