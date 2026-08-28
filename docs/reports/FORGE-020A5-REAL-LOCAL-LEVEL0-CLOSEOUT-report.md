# FORGE-020A5 — Real Local Level 0 Closeout

## Verdict

**PASS. FORGE-020A Real Local Model Level 0 is now closed with one genuine, unrepaired Local structural generation through the Forge production path.**

This is not a claim that the Local model has reached the final Forge generative-software target. It proves the narrower Level 0 milestone: a real open-weight Local model can generate software structure for a non-curated Need through the production provider/router/generation/Validator/Evidence path, with provenance strong enough to distinguish model ability from deterministic/curated fallback and Forge repair.

- Branch: `claude/forge-master-handoff-k46jns`
- 020A5 product fix commit: `9e515c03f56cd49eb4b0a6d0440a53e15501adc5`
- real-run trigger commit: `b0a9fe64c18bf264bbb7c199336aafa913d5460d`
- normal CI on trigger commit: run `33219195713` = **SUCCESS**
- real Local Level 0 workflow: run `33219195627` = **SUCCESS**
- durable passing evidence: `docs/evidence/level0/level0-20260828-230922.json`
- GitHub Actions artifact: `forge-020a-real-level0-evidence`, artifact id `9704599776`, digest `sha256:b25e85df4b0115db0b824cb83f71b05bd493dabfad9a2038c69d84984b8d9e17`
- Real Local Model runs: **1**
- Baseline-ready runs: **1**

## Why 020A5 was needed

The first real GitHub-hosted `qwen2.5:7b-instruct` run correctly failed closed. The model answered the Entity Synthesis stage, but its raw structural output required `identifier_normalized`; Forge could repair it into a valid product artifact, but that repaired result is not evidence that the model itself satisfied the structural contract.

That run exposed a contract-alignment defect: Prompt, provider JSON schema and strict-evidence evaluator did not derive all structural limits from one canonical definition. 020A5 therefore introduced `forge_ai/core/semantics/entity_contract.py` as the provider-independent structural contract and wired the same constraints into the Prompt, provider schema and strict-evidence evaluation.

Canonical constraints at closeout:

- identifier: `^[a-z][a-z0-9_]*$`
- fields: 1–6
- choice values: 2–6

Product-side sanitization may remain more permissive for robustness. **Robustness after repair and raw-model capability evidence remain separate facts.**

## 020A5 verification before the real run

The one-shot product-fix workflow completed successfully before removing its own temporary apply machinery.

- focused provider schema contract: **7 passed**
- focused Entity contract evidence: **8 passed**
- focused real structure integrity: **6 passed**
- focused Level 0 preflight: **13 passed**
- focused Local model path: **51 passed**
- full `forge_ai`: **593 passed**
- full backend: **1913 passed, 17 skipped, 1 warning**
- syntax / `git diff --check`: PASS

The focused suite includes the same-category mutation that a `choice` with seven values cannot masquerade as strict raw-model success merely because the broader product sanitizer can accept it.

## Genuine real-model execution

GitHub Actions run `33219195627` installed and started a real Ollama runtime on an ephemeral Linux runner, pulled the real open-weight model and invoked the existing Forge Level 0 verifier.

Runtime evidence:

- backend: `ollama`
- runtime version: `0.33.2`
- model: `qwen2.5:7b-instruct`
- model digest: `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e7047ca97d631a0b697e`
- quantization: `Q4_K_M`
- model family from Ollama metadata: `qwen2`
- parameter size from Ollama metadata: `7.6B`
- runner Python: `3.12.14`
- runner RAM recorded by Forge: `15989 MB`
- runner VRAM recorded by Forge: `0 MB`
- preflight: `eligible_for_real_run`

Probe Need:

`盆栽の水やりの記録をつけたい`

The probe remained `domain_resolution=generated`, not a curated trap.

## End-to-end production-path proof

The passing run recorded:

- HTTP production generation success: yes
- provider: `local`
- deployment: `local`
- generation source: `local_ai`
- structure source: `ai_entity_synthesis`
- structure provider: `local`
- structure task: `entity_synthesis`
- observed tasks: `entity_synthesis`, `cognitive_stage`
- structured output mode: `json_schema`
- raw Entity strict contract: PASS
- Entity sanitizer repairs: **none**
- structured output: valid
- Forge Validator: PASS
- durable Generation Evidence UID: `04cb5545745940e8a4d85be4a674deb8`
- verification: `real`
- `counts_as_real_local`: `true`
- `ready_for_baseline`: `true`
- measured end-to-end generation latency: `165214.7 ms`

The verifier's final result was:

- Level 0: **PASSED**
- Real Local Model runs: **1**
- Level 0.5-ready runs: **1**
- verifier process exit code: `0`

## Integrity interpretation

This PASS is materially stronger than “the Local provider returned HTTP 200”. It would not count if any of the following were true:

- deterministic or curated structure actually decided the software shape;
- Cloud or Test Double produced the structure;
- `generation_source` merely claimed Local while `structure_provider` was not Local;
- the actual structural task was not `entity_synthesis`;
- structured-output provenance were unknown / unacceptable;
- raw schema/contract failed and Forge repaired it;
- Validator did not pass;
- production Evidence UID were absent;
- verification were not REAL.

The earlier failed/invalid probes remain useful negative evidence and are not rewritten as successes.

## CI closeout

Normal CI run `33219195713` on `b0a9fe64c18bf264bbb7c199336aafa913d5460d` completed **SUCCESS** with all four jobs green:

1. frontend (Flutter): analyze, tests, web build — PASS
2. backend + forge_ai Python 3.12 — PASS
3. backend + forge_ai Python 3.11 — PASS
4. backend smoke / CORS — PASS

## What this does not prove

Do not inflate this Level 0 result beyond its evidence.

- Generated App Quality Golden Gate remains **FAIL** from the latest visual-quality review; no new visual quality run was performed here.
- This runner had no GPU/VRAM evidence suitable for GPU performance claims.
- Browser/Playwright visual inspection was not part of this real Level 0 run.
- One successful episode is **not** sufficient to promote a QLoRA/SFT/preference dataset example or adapter by itself. Future Dataset Builder must use objective eligibility, provenance, privacy/training-rights and benchmark gates.
- This does not prove the future `think -> search/retrieve -> build -> run -> inspect -> repair` autonomous Local Agent loop. That is the next architecture stage.

## 020A completion and next task

FORGE-020A has now crossed its real-runtime milestone and should not remain blocked on “run a real model once”.

Next implementation task is **FORGE-020B — Tool-Using Local Agent production wiring**.

Target production loop:

`Need -> plan -> retrieve/tool -> generate -> build/test -> inspect -> repair`

020B must use the existing Local provider and evidence contracts rather than creating a parallel demo path. Tool calls, outcomes and repairs must be recordable into the future Generation Episode contract so that successful and failed trajectories can later feed RAG/Skill extraction/Dataset Builder and, only after objective gates, training.

## Cleanup

Cleanup is complete.

- Temporary 020A5 apply/repair workflows and helper scripts are absent.
- The one-off real-model workflow `.github/workflows/forge-020a-real-level0.yml` is removed after durable evidence was committed.
- The one-shot closeout workflow removed itself after success.
- Closeout workflow run `33219996032` = **SUCCESS**.
- Cleanup commit: `3bcf1a5683f4f06d66b80f9de1d3c55f6d6ad997`.
- `.github/workflows/` now contains only the normal `ci.yml` workflow.
- Reusable verification tools `scripts/preflight_local_model_level0.py` and `scripts/verify_local_model_level0.py` remain intentionally; they are verification infrastructure, not temporary machinery.
