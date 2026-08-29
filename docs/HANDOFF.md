# Forge Handoff — current Source of Truth

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current task: **FORGE-020B — Tool-Using Local Agent production wiring / dual-environment closeout**
- 020B production wiring commit: `763fa326ad8b497db5d0fdb9a56bd57ed7d49710`
- 020B evidence-integrity hardening: `1780adcebcbde34bfbb145d924826b9c603520c3`
- 020B provenance / production-entry hardening: `4a09d71a850b322e9ba0f77a6ee01486c734d413`
- Learning-contract fix for `ForgeTask.AGENT_STEP`: `6dab22f27a1007b67438cf9ce91f207ae129d274`
- Shared real-agent verifier: `scripts/verify_local_agent_020b.py`
- Normal CI run `33222716256` = **SUCCESS**, all four jobs green.
- Genuine GitHub-hosted real Tool-Using Local Agent run `33227448429` = **SUCCESS / PASS**.
- Durable GitHub-runner evidence: `docs/evidence/agent020b/agent020b-20260829-015345.json`.
- GitHub Actions artifact: id `9707382693`, digest `sha256:b76d0184c3eac34a3c801a8382c716e8fc530622c731d7d406eef35a2b6cd469`.
- **Physical/user PC real-agent run: UNVERIFIED / NOT YET EXECUTED.**
- Golden Generated App Quality Gate remains **FAIL** from the latest visual review. 020B success does not rewrite that evidence.

Detailed 020B report: `docs/reports/FORGE-020B-TOOL-USING-LOCAL-AGENT-report.md`

## What the genuine GitHub-runner episode proved

The one-off runner installed/used a real Ollama runtime and real `qwen2.5:7b-instruct` weights, then executed the shared verifier through Forge's production HTTP generation path with `provider=local` and `agent_mode=verify`.

Exact evidence:

- Ollama `0.33.2`
- model `qwen2.5:7b-instruct`
- digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`
- quantization `Q4_K_M`
- HTTP status 200 / Forge status `success`
- Agent requested: true
- Agent executed: true
- Agent provider: `local`
- Agent model: `qwen2.5:7b-instruct`
- Agent outcome: `succeeded`
- tool calls: 2
- tools used: `inspect_forge_document`, `validate_forge_document`
- fresh Validator outcome: `passed`
- Episode deployment: `local`
- Episode provenance: `local_ai_output`
- Generation Evidence UID: `70bd148d54744e47a63f13743b5968fb`
- verifier `passed=true`, failures=[]

This is genuine 020B evidence of a real Local model producing an Agent tool plan and Forge executing the selected read-only inspection tools through the production Agent path. It is not a test-double substitute.

## Important boundary — what this episode did NOT prove

The bounded 020B verifier intentionally leaves `build`, `test`, `runtime`, and `visual` outcomes as `unknown`; those stages were not executed in this Agent episode. `repair_rounds` is empty because no repair was required. Therefore do not claim the full future loop `build/test/runtime/visual/repair` has been proven by this run.

The runner log also shows a second `ollama serve` process could not bind because port 11434 was already occupied. The verifier independently confirmed the reachable Ollama runtime and exact model digest before counting the run; the duplicate-start log is not evidence of a failed inference run, but future one-off workflows should avoid launching a redundant server process when the installer already started one.

## Dual-environment closeout still pending

The user elected to validate in both environments:

1. GitHub-hosted clean runner — **PASS**.
2. Physical/user PC with Ollama + the same shared verifier — **UNVERIFIED**.

On the physical PC, run from the repository root:

```powershell
$env:FORGE_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"
$env:FORGE_LOCAL_MODEL="qwen2.5:7b-instruct"
python scripts/verify_local_agent_020b.py
```

Commit the resulting `docs/evidence/agent020b/*.json`, then update this handoff/report with the physical-host facts. Do not label the PC leg PASS until that evidence exists.

## Cleanup / completion rule

The GitHub one-off real-agent workflow is temporary execution machinery and must not remain as permanent architecture after its evidence is preserved. Final closeout requires:

1. durable real-run evidence committed;
2. temporary workflow removed;
3. final normal CI GREEN after cleanup;
4. physical-PC real-agent evidence added;
5. remaining unmeasured build/test/runtime/visual/repair capabilities kept explicitly separate from 020B's bounded verification scope.

## Source of Truth to read first

1. `docs/PRODUCT-DIRECTION.md`
2. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
3. `docs/LEARNABLE-LOCAL-AI-VISION.md`
4. `docs/MACHINE-INDEPENDENT-POLICY.md`
5. `docs/reports/FORGE-020B-TOOL-USING-LOCAL-AGENT-report.md`
6. `docs/evidence/agent020b/agent020b-20260829-015345.json`
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
