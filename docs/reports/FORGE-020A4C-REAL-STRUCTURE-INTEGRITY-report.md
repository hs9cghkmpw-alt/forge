# FORGE-020A4C — Real Structure Integrity Gate

Status: **CLOSED — implementation and skeptical full-suite closeout green**

## Final implementation evidence

- Final implementation SHA: `b29d7504b184edaac4944eb42fffec4ab8587c7b`
- Skeptical closeout workflow run: `33217747922` = **SUCCESS**
- Focused verification:
  - Entity contract evidence tests: **7 passed**
  - Real structure integrity tests: **6 passed**
  - Local model production-path tests: **51 passed**
  - Level 0 preflight tests: **13 passed**
  - 020A3B provider-integrity tests: **14 passed**
  - Generation Evidence tests: **25 passed**
- Full `forge_ai`: **592 passed**
- Full backend: **1906 passed, 17 skipped, 1 warning**
- Syntax / `git diff --check`: PASS
- Temporary one-shot workflow and helper scripts were deleted before the final implementation commit.
- Real Local Model runs remain **0**. This task closes the integrity gate; it does not fabricate a real-model run.

## Why

020A4B proved that `ENTITY_SYNTHESIS` can traverse the production AIRouter path, but a second false-PASS path remained: real Local/Cloud Entity output is sanitized before IR/Validator. A repaired artifact could therefore be valid even when the model itself did not satisfy the Entity contract.

That distinction is critical for Forge's Growing AI path. Product robustness may repair a bad model answer, but model capability measurement and future training data must still know that the model answer was bad.

## What changed

- Added privacy-safe `EntitySynthesisContractEvidence` and closed `EntitySynthesisRepair` vocabulary.
- Product sanitization remains enabled; model contract ability and Forge repair ability are separate facts.
- `EntitySynthesizer` observes raw structural violations before sanitization and propagates evidence through `EntitySynthesisAttempt -> CognitiveContext -> GenerationRecord`.
- `GenerationRecord.to_dict()` serializes attempt diagnosis plus 020A4C contract fields without prompt/raw model output/user text.
- OpenAI-compatible providers record the **actual accepted structured-output mode**. AIRouter and ForgeAIProviderBridge carry that observation to Entity Synthesis.
- Real Local Level 0 fails closed unless the Entity output passed the raw model contract without Forge repair and was accepted under `strict_json_schema` or `json_schema` mode.
- `JSON_OBJECT` / prompt fallback remains valid product behavior but is insufficient evidence of strict Local model contract ability.

## Exact truth boundary

A Real Local structural run may count only when the evidence shows all of the following:

1. `structure_source == AI_ENTITY_SYNTHESIS`;
2. `structure_provider == LOCAL`;
3. `structure_task == entity_synthesis` and the task was actually observed;
4. `generation_source == LOCAL_AI` and deployment is Local;
5. raw Entity Synthesis satisfied the model contract before Forge repair;
6. no Entity sanitizer repair was required;
7. the accepted structured-output mode is schema-constrained (`strict_json_schema` or `json_schema`);
8. production Generation Evidence exists;
9. Validator passed;
10. verification is REAL.

The following do **not** count: Test Double, curated output, deterministic Capability Plan structure, Cloud structure, Design-Intent-only Local calls, repaired structural output, unknown structured-output mode, JSON_OBJECT fallback, prompt-only JSON, or Validator PASS by itself.

## Mutation / adversarial cases covered

- unknown field type -> STRING repair cannot count;
- missing required flag that Forge injects cannot count;
- invalid choice metadata / choice downgrade cannot count;
- invalid visual style or label fallback is observable repair;
- Validator PASS cannot rescue a repaired model output;
- unknown contract evidence fails closed;
- JSON_OBJECT / weaker fallback cannot prove strict contract compliance;
- model output with 7 or 8 fields cannot masquerade as strict success when the Prompt contract caps fields at 6;
- a legitimate optional field omission is not falsely classified as repair when another field already satisfies the required-field rule;
- structured-output mode is treated as a closed identifier in the privacy guard, not as arbitrary content.

## Skeptical review chronology

The first implementation commit (`4bb9702d2df495bdda06892704b174ed061388ef`) passed dedicated 020A4C focused tests but was **not** accepted as complete. Review found:

1. optional `required` omission could be incorrectly classified as repaired;
2. Prompt max-6-fields vs sanitizer max-8-fields allowed 7/8 fields to look like strict model success;
3. legacy RealLocal passing fixtures lacked the new fail-closed evidence fields;
4. Privacy guard had not yet classified structured-output mode as a closed identifier;
5. mechanical Markdown quoting damage existed in `CHANGELOG.md` / `TECH_DEBT.md`.

The first skeptical closeout then exposed two full-backend regressions despite focused green. Those were fixed by updating the success fixture to satisfy the new real contract and explicitly classifying the mode identifier in the privacy test. The gate itself was not weakened. The final closeout then reached **1906 backend passes** and **592 forge_ai passes**.

## Dataset / training handoff

Future Generation Episodes / JSONL datasets must preserve at least these distinct layers:

`model_output_contract -> forge_repairs -> final_artifact`

They must also retain provider/model/tool provenance, objective Validator/build/test/runtime/visual evidence, user outcome where applicable, consent/training-rights and lineage. Forge-repaired outputs must not be mislabeled as positive SFT/preference/QLoRA examples for the model behavior that required repair. QLoRA itself is not implemented by this task.

## Base evidence

- Base SHA: `e659181427224242458561a06a32af01b8295023`
- Base CI run: `33175691427` = SUCCESS / 4 jobs green.

## Next gate

The next gate is **not more 020A4C code**. It is a genuine Real Local Level 0 execution on a machine/runtime that can run the open-weight model.

Required sequence:

1. update the branch safely and preserve unknown local work;
2. run `python scripts/forge_doctor.py`;
3. run `python scripts/preflight_local_model_level0.py` and require `eligible_for_real_run`;
4. configure the real Local runtime/model for that session;
5. run `python scripts/verify_local_model_level0.py`;
6. accept `Real Local Model runs: 0 -> 1` only if the production evidence proves an unrepaired schema-contract Local structural PASS.

If real Qwen fails, retain the failure evidence and fix the observed model/prompt/retrieval issue. Do not add a Local-output repair or relax the Level 0 predicate merely to obtain PASS.
