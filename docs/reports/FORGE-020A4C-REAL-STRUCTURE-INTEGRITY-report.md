# FORGE-020A4C — Real Structure Integrity Gate

Status: **IMPLEMENTED — CI verification pending at creation time**

## Why
020A4B proved that `ENTITY_SYNTHESIS` can traverse the production AIRouter path, but a second false-PASS path remained: real Local/Cloud Entity output is sanitized before IR/Validator. A repaired artifact could therefore be valid even when the model itself did not satisfy the Entity contract.

## What changed
- Added privacy-safe `EntitySynthesisContractEvidence` and closed `EntitySynthesisRepair` vocabulary.
- Product sanitization remains enabled; model contract ability and Forge repair ability are now separate facts.
- `EntitySynthesizer` observes raw structural violations before sanitization and propagates evidence through the existing `EntitySynthesisAttempt -> CognitiveContext -> GenerationRecord` path.
- `GenerationRecord.to_dict()` now serializes the existing attempt diagnosis plus 020A4C contract fields; no prompt/raw model output/user text is stored.
- OpenAI-compatible providers record the **actual accepted structured-output mode**. AIRouter and ForgeAIProviderBridge carry that observation to Entity Synthesis.
- Real Local Level 0 now fails closed unless the Entity output passed without Forge repair and was accepted under strict/json-schema mode.
- `JSON_OBJECT`/prompt fallback remains valid product behavior but is not sufficient evidence of strict Local model contract ability.

## Mutation intent covered
- unknown type -> STRING cannot count as Real Local
- required injection cannot count
- choice downgrade cannot count
- invalid visual style / label fallback are observable repairs
- Validator PASS alone cannot count a repaired run
- unknown contract evidence fails closed
- JSON_OBJECT fallback cannot prove strict contract compliance
- serializer exposes only closed structural diagnosis

## Truth boundaries
- Mock preflight is a **wiring proof**, not model semantic-quality proof.
- A usable repaired app may still be returned to the user; that does not become a Local AI positive.
- Real Local Model runs remain **0** until a genuine `qwen2.5:7b-instruct` production structural run satisfies the new gate.
- Do not run the real Qwen Level 0 until exact-SHA CI for this task is green.

## Dataset / training handoff
Future Generation Episodes / JSONL must keep `model_output_contract`, `forge_repairs`, and `final_artifact` separate. Forge-repaired output must not be mislabeled as an AI positive for SFT/preference/QLoRA candidates. QLoRA itself is not part of this task.

## Base evidence
- Base SHA: `e659181427224242458561a06a32af01b8295023`
- Base CI: run `33175691427` = success (4 jobs green, independently checked before implementation).

## Next
1. Confirm exact final implementation SHA CI is all green.
2. Record the final SHA/run in HANDOFF and this report.
3. Only then, on a machine with real Ollama + `qwen2.5:7b-instruct`, run preflight followed by `scripts/verify_local_model_level0.py`.
4. A repaired run must remain rejected; only unrepaired strict-contract Local structure generation may change Real Local Model runs from 0 to 1.
