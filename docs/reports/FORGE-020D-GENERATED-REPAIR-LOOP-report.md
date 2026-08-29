# FORGE-020D — Generated App Objective Repair Loop

## Status

**GITHUB REAL GENERATED-APP REPAIR PASS; VISUAL UNVERIFIED; PHYSICAL-PC LEG SEPARATE**

The GitHub-hosted clean-runner probe successfully exercised the generated-artifact repair path against a real isolated Flutter workspace. The result is durable evidence that Forge can observe an objective generated-app test failure, apply a bounded Forge-side repair, re-run objective verification, then obtain passing generated-app test/build/runtime outcomes.

This does **not** make the Golden Generated App Quality Gate pass. Visual quality remains `unknown` in this episode and the latest Golden Gate remains FAIL until it is genuinely re-run and passes.

## Evidence

- Workflow: `FORGE-020D real generated Flutter repair`
- Run ID: `33236863659`
- Job ID: `99059255267`
- Result: `success`
- Head SHA that produced the evidence: `ad4cea4579c788fb573d72cb21645973eb7f39c7`
- GitHub artifact ID: `9710186190`
- Artifact name: `forge-020d-real-generated-repair-evidence`
- Artifact digest: `sha256:bb66c4b1fb38dec4f70783b813b15f16fd7d82f20adee98687d80cded89f6bd9`
- Durable repository evidence: `docs/evidence/agent020d/forge-020d-real-evidence-20260829.json`

## Objective trajectory

The durable evidence records:

- schema: `forge.generated_flutter_repair.020e.v1`
- generated artifact fingerprint: `bbbb683514b53261eebe2ff9af3837a1ab3b12d16f926ce80dd3f08c9ec93db5`
- verification count: `2`
- first verification: test `failed`, build `unknown`, runtime `unknown`
- failure classification: `test_failed`
- repair rounds: `1`
- repair round 1: `resolved=true`
- second verification: test `passed`, build `passed`, runtime `passed`
- visual: `unknown`
- episode outcome: `succeeded`
- `repair_succeeded=true`

The repair callback could not self-assert success. It only mutated the isolated generated workspace. Success was accepted only after fresh `CommandRunner` observations from the same generated workspace returned passing outcomes.

## What was actually executed

The probe materialized a generated Flutter runtime shell around a Forge Document in a fresh isolated workspace, injected a deterministic failing Flutter test, ran objective verification, repaired only the generated workspace, then re-ran verification. The final verification required real Flutter test, Web build, and Flutter widget/runtime execution to pass.

The generated workspace boundary prevents Forge's own repository build from being counted as generated-app evidence. Model text and log interpretation are not verification truth; exit code / timeout observations are.

## Initial probe failure and correction

The first real-run attempt failed before the repair loop because the clean GitHub runner could not import `forge_ai` (`ModuleNotFoundError`). This was an environment/provisioning defect in the standalone probe, not evidence that the generated repair loop failed. The probe and workflow were corrected to provide the repository Python path and install backend dependencies before the real run.

The successful run above is the evidence-bearing run.

## Deliberate non-claims

This evidence does not prove:

- visual quality or Golden Gate success (`visual=unknown`);
- physical/user-PC execution;
- arbitrary application semantics beyond the tested generated Flutter shell;
- autonomous model-selected repair quality—the repair mutation in this probe is Forge-side and bounded;
- production API exposure of every build/test/runtime/repair detail.

## Closeout rule

The one-off real-repair workflow should be removed after preserving this evidence, then the normal persistent CI should be green after cleanup. Golden Gate remains FAIL until a genuine visual/behavioral rerun says otherwise.
