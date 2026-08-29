# Forge Handoff — current Source of Truth

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current task: **FORGE-020B — Tool-Using Local Agent production wiring**
- 020B production wiring commit: `763fa326ad8b497db5d0fdb9a56bd57ed7d49710`
- 020B evidence-integrity hardening: `1780adcebcbde34bfbb145d924826b9c603520c3`
- 020B provenance / production-entry hardening: `4a09d71a850b322e9ba0f77a6ee01486c734d413`
- Learning-contract fix for `ForgeTask.AGENT_STEP`: `6dab22f27a1007b67438cf9ce91f207ae129d274`
- Normal CI for `6dab22f...`: run `33222716256` = **SUCCESS**, all four jobs green
  - backend + forge_ai Python 3.11: SUCCESS
  - backend + forge_ai Python 3.12: SUCCESS
  - backend smoke (startup + CORS): SUCCESS
  - frontend Flutter analyze/test/web build: SUCCESS
- `.github/workflows/` remains normal `ci.yml` only.
- **Real Ollama + qwen2.5:7b-instruct Tool-Using Agent episode: UNVERIFIED / NOT YET EXECUTED for 020B.**
- Golden Generated App Quality Gate remains **FAIL** from the latest visual review. 020B CI success does not change that result.

Detailed 020B status report: `docs/reports/FORGE-020B-TOOL-USING-LOCAL-AGENT-report.md`

## What 020B now proves in code/CI

The production branch now contains a Tool-Using Local Agent path rather than a disconnected demo. The implementation sequence includes:

- production local agent runner;
- production agent test coverage;
- production generation wiring;
- agent evidence-integrity hardening;
- provenance and production-entry-path hardening;
- `ForgeTask.AGENT_STEP` registered in the Learning Contract so Agent-step Learning Events do not silently disappear.

The normal repository CI passes after the Learning Contract correction. Therefore the repository-level implementation and regression surface are currently green at SHA `6dab22f...`.

## What is still not proven

020B is **not yet a full real-model closeout**. The following remains environment-dependent and must stay `UNVERIFIED` until executed against a real Ollama runtime:

1. Real `qwen2.5:7b-instruct` selects/uses the intended tools through the production Agent path.
2. Tool request/result/error provenance is captured from a genuine model episode.
3. Build/test/runtime observations from that episode are preserved as objective evidence.
4. Repair-attempt lineage is preserved if a repair is required.
5. No deterministic/test-double substitute is incorrectly counted as model capability.
6. Durable evidence/reporting is saved for the real episode.

Do not mark those facts PASS based only on unit/integration CI.

## Prior real Local Level 0 remains proven

FORGE-020A5 already proved a genuine Local model structural-generation episode through Forge's production path:

- runtime: Ollama `0.33.2`
- model: `qwen2.5:7b-instruct`
- model digest: `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e7047ca97d631a0b697e`
- quantization: `Q4_K_M`
- normal CI run `33219195713`: SUCCESS
- genuine Local Level 0 run `33219195627`: SUCCESS / PASS
- durable evidence: `docs/evidence/level0/level0-20260828-230922.json`

That proves the Local model/provider baseline, but it does **not** substitute for a genuine 020B Tool-Using Agent run.

## Next execution — real 020B episode

On a machine with Ollama and `qwen2.5:7b-instruct`, execute one genuine production-path Tool-Using Agent episode and preserve evidence. The target loop remains:

`Need -> plan -> retrieve/tool -> generate -> build/test -> inspect -> repair`

Fail closed if model/tool/provider/source/provenance facts are missing or if a deterministic/test substitute is used.

After the real episode:

1. save durable evidence;
2. update this handoff and the 020B report with exact runtime/model/provenance/result facts;
3. record remaining technical debt without rewriting `UNVERIFIED` as PASS;
4. remove any one-off execution machinery if one was temporarily introduced;
5. require final normal CI GREEN before declaring 020B closed.

## Source of Truth to read first

1. `docs/PRODUCT-DIRECTION.md`
2. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
3. `docs/LEARNABLE-LOCAL-AI-VISION.md`
4. `docs/MACHINE-INDEPENDENT-POLICY.md`
5. `docs/reports/FORGE-020B-TOOL-USING-LOCAL-AGENT-report.md`
6. `docs/reports/FORGE-020A5-REAL-LOCAL-LEVEL0-CLOSEOUT-report.md`
7. latest GitHub HEAD / diff / CI

Chat-only status is never the Source of Truth when GitHub has newer evidence.

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
