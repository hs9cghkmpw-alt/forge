# FORGE-020B — Tool-Using Local Agent production wiring report

Status: **GITHUB REAL-AGENT PASS; PHYSICAL-PC LEG UNVERIFIED**

## Objective

Wire the existing Local provider into a production Tool-Using Agent path rather than creating a disconnected demonstration, preserve fail-closed provenance, and validate the bounded Agent step against a genuine Local model.

The long-term product loop remains:

`Need -> plan -> retrieve/tool -> generate -> build/test -> inspect -> repair`

020B does not claim every stage of that future loop is already implemented or measured.

## Implemented commit sequence

- `f2a39be6326267ab53daf5efef5e95ebf9c8e7e8` — production local agent runner
- `5e982eba0fe47016901ed994bbf44376bb5bb6f3` — production agent coverage
- `763fa326ad8b497db5d0fdb9a56bd57ed7d49710` — Local Tool Agent wired into production generation
- `1780adcebcbde34bfbb145d924826b9c603520c3` — agent evidence-integrity hardening
- `4a09d71a850b322e9ba0f77a6ee01486c734d413` — provenance and production-entry-path hardening
- `6dab22f27a1007b67438cf9ce91f207ae129d274` — register `ForgeTask.AGENT_STEP` in the Learning Contract
- `7660dfabeafbb411c1b16c39addcb70c73f061e9` — add shared real Local Agent verifier
- `eeb48e0c4b28c27a8b37f526ec37c163b7e5b4a7` — trigger one-off genuine GitHub-hosted real-agent execution

## Normal CI evidence

GitHub Actions run `33222716256` completed with conclusion **SUCCESS**. Python 3.11, Python 3.12, backend smoke, and Flutter analyze/test/web build all passed.

The earlier run `33222193528` correctly exposed a contract mismatch: `ForgeTask.AGENT_STEP` existed but was missing from `_FORGE_TASK_MAPPING`. The explicit `forge.agent_step` mapping fixed that defect without weakening the fail-closed contract.

## Genuine real-agent evidence — GitHub-hosted runner

Workflow run `33227448429` completed **SUCCESS**. Its focused 020B regression test, genuine model execution, durable evidence display, artifact upload, and verifier enforcement steps all succeeded.

Artifact:

- id: `9707382693`
- name: `forge-020b-real-local-agent-evidence`
- digest: `sha256:b76d0184c3eac34a3c801a8382c716e8fc530622c731d7d406eef35a2b6cd469`

Durable repository evidence copied from the artifact:

`docs/evidence/agent020b/agent020b-20260829-015345.json`

Exact measured facts:

- runtime reachable: true
- backend: Ollama
- Ollama version: `0.33.2`
- model: `qwen2.5:7b-instruct`
- model digest: `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`
- quantization: `Q4_K_M`
- generation provider requested: `local`
- Agent mode: `verify`
- HTTP: 200 / Forge status `success`
- Agent requested/executed: true / true
- Agent outcome: `succeeded`
- Agent provider/model: `local` / `qwen2.5:7b-instruct`
- tool calls: 2
- tools: `inspect_forge_document`, `validate_forge_document`
- Validator: `passed`
- Episode task: `forge.local_agent.verify`
- Episode deployment: `local`
- Episode provenance: `local_ai_output`
- Generation Evidence UID: `70bd148d54744e47a63f13743b5968fb`
- final episode outcome: `succeeded`
- verifier: `passed=true`, no failures

This proves a genuine qwen Local model produced a structured Agent tool plan and Forge executed the selected bounded read-only tools through the production Agent path. Model self-confidence was not used as success truth; the fresh deterministic Validator supplied the validation result.

## Deliberate non-claims

The Episode records `build`, `test`, `runtime`, and `visual` as `unknown`. Those stages were not executed by the bounded 020B verification episode and therefore are not PASS. `repair_rounds` is empty because no repair was needed; this run cannot prove genuine repair-lineage behavior.

The Ollama log records `bind: address already in use` for the explicit background `ollama serve` command. The install step had already left a reachable runtime on port 11434. The verifier independently identified a reachable Ollama `0.33.2`, the exact qwen model digest, and completed genuine inference successfully. The duplicate start attempt should be removed from future temporary workflows to make startup evidence cleaner.

## Physical-PC leg

The user chose dual-environment verification. The clean GitHub-hosted runner leg is PASS. The physical/user-PC leg remains **UNVERIFIED** until the same verifier is run there and its evidence is committed.

Required command from repository root:

```powershell
$env:FORGE_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"
$env:FORGE_LOCAL_MODEL="qwen2.5:7b-instruct"
python scripts/verify_local_agent_020b.py
```

Acceptance requires a generated `docs/evidence/agent020b/*.json` showing a genuine Local runtime/model, `agent.executed=true`, provider `local`, at least one tool call, Validator passed, Episode provenance `local_ai_output`, and `passed=true` with no failures.

## Remaining separate product evidence

- Generated App Quality Golden Gate remains **FAIL** from the prior visual review.
- Full build/test/runtime/visual Agent observations remain future capability work.
- Genuine repair-attempt lineage remains unmeasured in the successful episode because repair was not required.
- Training use remains `unknown`; this episode is not automatically eligible for SFT/QLoRA/preference training.

## Closeout sequence

1. Preserve this GitHub-runner evidence in the repository. **Done.**
2. Remove the one-off GitHub real-agent workflow. **Done in the evidence closeout commit.**
3. Require normal CI GREEN after cleanup. **Pending at the time this report is written.**
4. Run the shared verifier on the physical/user PC. **UNVERIFIED.**
5. Commit physical-host evidence and update HANDOFF/report with exact facts.

Do not declare dual-environment 020B closeout complete before steps 3–5 are satisfied.
