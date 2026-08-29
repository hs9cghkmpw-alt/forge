# FORGE-020B — Tool-Using Local Agent production wiring report

Status: **IMPLEMENTATION / CI GREEN; REAL TOOL-USING LOCAL EPISODE UNVERIFIED**

## Objective

Wire the existing Local provider into a production Tool-Using Agent path rather than creating a disconnected demonstration. The intended product loop is:

`Need -> plan -> retrieve/tool -> generate -> build/test -> inspect -> repair`

The implementation must preserve typed tool contracts, permission/safety boundaries, provider/router production wiring, deterministic objective observations, repair lineage and evidence/provenance integrity.

## Implemented commit sequence

- `f2a39be6326267ab53daf5efef5e95ebf9c8e7e8` — production local agent runner
- `5e982eba0fe47016901ed994bbf44376bb5bb6f3` — production agent coverage
- `763fa326ad8b497db5d0fdb9a56bd57ed7d49710` — Local Tool Agent wired into production generation
- `1780adcebcbde34bfbb145d924826b9c603520c3` — agent evidence-integrity hardening
- `4a09d71a850b322e9ba0f77a6ee01486c734d413` — provenance and production-entry-path hardening
- `6dab22f27a1007b67438cf9ce91f207ae129d274` — register `ForgeTask.AGENT_STEP` in the Learning Contract

## CI evidence

Normal GitHub Actions run `33222716256` for SHA `6dab22f27a1007b67438cf9ce91f207ae129d274` completed with conclusion **SUCCESS**.

All four normal CI jobs passed:

- backend + forge_ai (Python 3.11): SUCCESS
- backend + forge_ai (Python 3.12): SUCCESS
- backend smoke (startup + CORS): SUCCESS
- frontend Flutter: analyze SUCCESS, tests SUCCESS, web build SUCCESS

The preceding failure on run `33222193528` was caused by a contract mismatch: `ForgeTask.AGENT_STEP` existed in `tasks.py` but was missing from `_FORGE_TASK_MAPPING` in `learning_contract.py`. This was corrected by mapping it to `LearningTaskId("forge", "agent_step")`.

The fix is intentionally narrow: the Learning Contract remains fail-closed, and every `ForgeTask` must have an explicit Learning Task mapping.

## Proven by repository evidence

At the repository/CI level, 020B now proves that:

1. a production Agent task exists and participates in the normal routing/task vocabulary;
2. the Agent path is wired into production generation code rather than living only as a demo/test island;
3. regression tests cover the production Agent path;
4. provenance/evidence integrity received dedicated hardening;
5. the Learning Contract includes the Agent task explicitly;
6. the normal backend, smoke, frontend test and build surfaces remain green after the change.

## Not yet proven — fail closed

A real Tool-Using Local model episode has **not yet been executed and preserved as 020B evidence**. Therefore all of the following remain `UNVERIFIED`:

- genuine Ollama runtime invocation for the 020B Agent loop;
- genuine `qwen2.5:7b-instruct` Agent-step outputs;
- real tool selection/request/result/error trajectory;
- objective build/test/runtime observations from the same episode;
- repair-attempt lineage from a genuine model repair, if needed;
- complete durable 020B episode evidence proving provider/model/tool provenance and no deterministic/test-double substitution.

Prior FORGE-020A5 real Local Level 0 evidence proves the Local model/provider baseline, but it cannot be reused as proof of Tool-Using Agent behavior.

## Real-run acceptance gate

A 020B real episode may be counted only if evidence proves, at minimum:

1. a genuine Local Ollama deployment/model was used;
2. Agent execution used the production path;
3. `agent_step` provenance is present where expected;
4. tool requests/results/errors are typed and attributable to the episode;
5. permission/safety checks are applied before side effects;
6. build/test/runtime truth comes from deterministic observations, not model self-confidence;
7. repair attempts link to the originating failure/observation;
8. no test double, curated substitute or deterministic replacement is counted as Local model capability;
9. durable evidence is saved before closeout;
10. a final normal CI run is GREEN after any closeout edits/cleanup.

## Remaining separate product evidence

The latest Generated App Quality Golden Gate remains **FAIL** from the prior visual review. No 020B repository CI result changes that visual/product-quality fact.

## Next action

Run one genuine production-path Tool-Using Agent episode on a machine with Ollama + `qwen2.5:7b-instruct`, save the evidence, update this report/HANDOFF with exact results, clean up any one-off runner machinery if introduced, and require final normal CI GREEN before declaring FORGE-020B complete.
