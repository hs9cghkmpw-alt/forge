# Forge Handoff — current Source of Truth

## Current state

- Branch: `claude/forge-master-handoff-k46jns`
- Current task: **FORGE-020D/020E — objective generated-app verification + bounded repair + runtime evidence closeout**
- 020B production wiring commit: `763fa326ad8b497db5d0fdb9a56bd57ed7d49710`
- Shared 020B real-agent verifier: `scripts/verify_local_agent_020b.py`
- Genuine GitHub-hosted real Tool-Using Local Agent run `33227448429` = **SUCCESS / PASS**.
- Durable 020B evidence: `docs/evidence/agent020b/agent020b-20260829-015345.json`.
- 020B artifact id `9707382693`, digest `sha256:b76d0184c3eac34a3c801a8382c716e8fc530622c731d7d406eef35a2b6cd469`.
- Physical/user-PC 020B real-agent leg: **UNVERIFIED / NOT YET EXECUTED**.
- Generated-artifact workspace isolation/materialization is implemented.
- Objective `CommandObservation` exit-code/timeout mapping into GenerationEpisode is implemented.
- Bounded generated-app repair loop is implemented; repair cannot self-assert PASS and must reverify.
- Real GitHub-hosted generated Flutter repair/runtime run `33236863659` = **SUCCESS / PASS**.
- Durable 020D/020E evidence: `docs/evidence/agent020d/forge-020d-real-evidence-20260829.json`.
- 020D/020E artifact id `9710186190`, digest `sha256:bb66c4b1fb38dec4f70783b813b15f16fd7d82f20adee98687d80cded89f6bd9`.
- Evidence-bearing head SHA: `ad4cea4579c788fb573d72cb21645973eb7f39c7`.
- Golden Generated App Quality Gate remains **FAIL**. Visual outcome in the real repair episode is `unknown` and must not be rewritten as PASS.

Detailed reports:

- `docs/reports/FORGE-020B-TOOL-USING-LOCAL-AGENT-report.md`
- `docs/reports/FORGE-020D-GENERATED-REPAIR-LOOP-report.md`

## What the genuine 020D/020E GitHub-runner episode proved

A clean GitHub-hosted runner materialized an isolated generated Flutter app around a Forge Document, injected a deterministic failing Flutter test, observed the failure objectively, applied one bounded Forge-side repair, and re-ran the same generated-workspace verifier.

Exact durable evidence:

- schema `forge.generated_flutter_repair.020e.v1`
- generated artifact fingerprint `bbbb683514b53261eebe2ff9af3837a1ab3b12d16f926ce80dd3f08c9ec93db5`
- verification count `2`
- initial failure code `test_failed`
- initial test `failed`
- initial build `unknown`
- initial runtime `unknown`
- repair rounds `1`
- repair round 1 `resolved=true`
- final test `passed`
- final build `passed`
- final runtime `passed`
- final visual `unknown`
- final outcome `succeeded`
- `repair_succeeded=true`

This proves the objective generated-artifact trajectory `test fail -> repair -> test pass -> build pass -> runtime pass` on a real Flutter runner. Success comes from Forge-observed command exit codes/timeouts, not model claims or log interpretation.

## Important boundary — what is still not proved

- Visual quality remains unmeasured in this episode (`visual=unknown`).
- The latest Golden Generated App Quality Gate remains **FAIL** until a genuine visual/behavioral rerun passes.
- The 020D real-run repair mutation is trusted Forge-side and bounded; it is not evidence that a local model autonomously chose a good repair.
- Physical/user-PC execution of the shared 020B local-agent verifier remains unverified.
- Production API DTO exposure of all build/test/runtime/repair details is not yet the same as internal Episode evidence.
- Capability gaps such as real simulation/media semantics must not be papered over by registry names without renderer/runtime support.

## Initial real-repair probe failure

An earlier GitHub real-repair attempt failed before entering the repair loop with `ModuleNotFoundError: forge_ai`. The standalone probe did not have the repository root on Python's import path and the workflow had not provisioned backend dependencies. Those environment defects were corrected. Only successful run `33236863659` is the evidence-bearing repair/runtime run.

## Physical-PC 020B leg still pending

From the repository root on the physical PC:

```powershell
$env:FORGE_LOCAL_BASE_URL="http://127.0.0.1:11434/v1"
$env:FORGE_LOCAL_MODEL="qwen2.5:7b-instruct"
python scripts/verify_local_agent_020b.py
```

Do not label the physical leg PASS until its evidence JSON exists and is preserved.

## Next work

1. Remove the one-off `FORGE-020D real generated Flutter repair` workflow after durable evidence preservation.
2. Require normal persistent CI to pass after that cleanup.
3. Move to the actual Golden Generated App Quality Gate blockers: semantic/runtime support first, then genuine runtime/visual rerun.
4. Keep `visual=unknown` and Golden Gate FAIL until directly measured.
5. After objective generated-app verification is stable, wire model/agent diagnosis and controlled repair selection without weakening the same verifier boundary.

## Source of Truth to read first

1. `docs/PRODUCT-DIRECTION.md`
2. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
3. `docs/LEARNABLE-LOCAL-AI-VISION.md`
4. `docs/MACHINE-INDEPENDENT-POLICY.md`
5. `docs/reports/FORGE-020B-TOOL-USING-LOCAL-AGENT-report.md`
6. `docs/reports/FORGE-020D-GENERATED-REPAIR-LOOP-report.md`
7. `docs/evidence/agent020b/agent020b-20260829-015345.json`
8. `docs/evidence/agent020d/forge-020d-real-evidence-20260829.json`
9. latest GitHub HEAD / diff / CI

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
