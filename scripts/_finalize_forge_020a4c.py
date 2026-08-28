"""One-shot closeout for FORGE-020A4C after skeptical review of 4bb9702d.

The initial integrity gate passed focused tests but full-suite review found two
strict-contract edge cases and stale test fixtures.  This script applies the
reviewed closeout changes mechanically; the temporary workflow deletes this
script after successful verification.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old[:120]!r}")
    write(path, content.replace(old, new, 1))


# 1. Strict Entity contract must follow the actual Prompt contract, not the
#    broader product sanitizer limits.
path = "forge_ai/core/ir/entity_synthesizer.py"
replace_once(
    path,
    "_MAX_FIELDS = 8\n",
    "_MAX_FIELDS = 8\n"
    "# Prompt contract is intentionally stricter than the product sanitizer: the\n"
    "# model is instructed to return no more than 6 fields. Product robustness may\n"
    "# accept 7-8 fields, but that is not strict model-contract success.\n"
    "_STRICT_CONTRACT_MAX_FIELDS = 6\n",
)
replace_once(
    path,
    "        required = raw.get(\"required\")\n"
    "        if required is True:\n"
    "            any_required = True\n"
    "        elif required is not False:\n"
    "            # Non-bool is silently treated as False and can later cause injection.\n"
    "            note(EntitySynthesisRepair.REQUIRED_INJECTED)\n",
    "        required = raw.get(\"required\")\n"
    "        if required is True:\n"
    "            any_required = True\n"
    "        elif required is False or required is None:\n"
    "            # `required` is optional per field. Omission is valid as long as\n"
    "            # at least one accepted field explicitly has required=true.\n"
    "            pass\n"
    "        else:\n"
    "            # A supplied non-bool is repaired to False by the sanitizer.\n"
    "            note(EntitySynthesisRepair.REQUIRED_INJECTED)\n",
)
replace_once(
    path,
    "    raw_schema_valid = (\n"
    "        entity_name is not None\n",
    "    within_prompt_field_limit = fields_received <= _STRICT_CONTRACT_MAX_FIELDS\n"
    "    raw_schema_valid = (\n"
    "        entity_name is not None\n"
    "        and within_prompt_field_limit\n",
)

# 2. Strengthen focused contract tests for those two edge cases.
path = "forge_ai/tests/test_forge_020a4c_entity_contract_evidence.py"
append = '''\n\ndef test_optional_field_may_omit_required_when_another_field_is_required():\n    raw = _valid()\n    raw["fields"].append({\n        "name": "note",\n        "label": "メモ",\n        "type": "string",\n        "choices": [],\n        "measure": "unknown",\n    })\n    ev = _entity_contract_evidence(raw, structured_output_mode="json_schema")\n    assert EntitySynthesisRepair.REQUIRED_INJECTED not in ev.repairs_applied\n    assert ev.strict_contract_passed is True\n\n\ndef test_more_than_six_fields_violates_prompt_contract_even_if_product_accepts_them():\n    raw = _valid()\n    raw["fields"] = [\n        {\n            "name": f"field_{index}",\n            "label": f"項目{index}",\n            "type": "string",\n            "required": index == 0,\n            "choices": [],\n            "measure": "unknown",\n        }\n        for index in range(7)\n    ]\n    ev = _entity_contract_evidence(raw, structured_output_mode="json_schema")\n    assert ev.fields_received == 7\n    assert ev.strict_contract_passed is False\n    # This is a model-contract violation, not a claimed Forge repair: the broader\n    # product sanitizer can still accept the seven fields.\n    assert EntitySynthesisRepair.FIELD_DROPPED not in ev.repairs_applied\n'''
content = read(path)
if "test_more_than_six_fields_violates_prompt_contract" not in content:
    write(path, content.rstrip() + append + "\n")

# 3. Existing Level0 passing fixture must explicitly satisfy the new fail-closed
#    evidence contract. Do not weaken RealLocalModelRun defaults.
path = "backend/tests/test_forge_020a_local_model_path.py"
replace_once(
    path,
    '            "structure_task": ForgeTask.ENTITY_SYNTHESIS.value,\n'
    '            "runtime_backend": LocalRuntimeBackend.OLLAMA,\n',
    '            "structure_task": ForgeTask.ENTITY_SYNTHESIS.value,\n'
    '            "entity_synthesis_strict_contract_passed": True,\n'
    '            "entity_synthesis_repairs": (),\n'
    '            "structured_output_mode": "json_schema",\n'
    '            "runtime_backend": LocalRuntimeBackend.OLLAMA,\n',
)

# 4. Production TestDouble preflight must prove the new evidence actually flows
#    through /generate, while also proving that Mock remains wiring-only evidence.
path = "backend/tests/test_forge_020a4_level0_preflight.py"
replace_once(
    path,
    "        self.assertTrue(record.entity_synthesis_accepted)\n"
    "        self.assertIsNone(record.entity_synthesis_rejection_reason)\n"
    "        self.assertTrue(record.validator_passed)\n",
    "        self.assertTrue(record.entity_synthesis_accepted)\n"
    "        self.assertIsNone(record.entity_synthesis_rejection_reason)\n"
    "        # Mock nested-schema repair makes the production route executable,\n"
    "        # but the resulting Entity still needs Forge's required-field repair.\n"
    "        # Therefore Mock is a wiring proof, never a model-quality proof.\n"
    "        self.assertFalse(record.entity_synthesis_strict_contract_passed)\n"
    "        self.assertIn(\"required_injected\", record.entity_synthesis_repairs)\n"
    "        self.assertTrue(record.validator_passed)\n",
)

# 5. Repair malformed markdown introduced by the first mechanical prefix write.
path = "CHANGELOG.md"
content = read(path)
old_prefix = '''# FORGE-020A4C — Real Structure Integrity Gate\n\n"\n    "- Separate raw Entity model-contract success from Forge sanitizer repairs.\n"\n    "- Propagate actual structured-output mode provenance.\n"\n    "- Real Local Level 0 now rejects repaired/unknown/non-schema-mode structural outputs.\n"\n    "- Serialize privacy-safe Entity Synthesis diagnosis for durable learning evidence.\n\n# CHANGELOG\n'''
new_prefix = '''# FORGE-020A4C — Real Structure Integrity Gate\n\n- Separate raw Entity model-contract success from Forge sanitizer repairs.\n- Propagate actual structured-output mode provenance.\n- Real Local Level 0 now rejects repaired/unknown/non-schema-mode structural outputs.\n- Serialize privacy-safe Entity Synthesis diagnosis for durable learning evidence.\n\n# CHANGELOG\n'''
if old_prefix not in content:
    raise RuntimeError("CHANGELOG.md: malformed 020A4C prefix not found")
write(path, content.replace(old_prefix, new_prefix, 1))

path = "TECH_DEBT.md"
content = read(path)
old_prefix = '''# TD020A4C — Model contract vs Forge repair provenance\n\n"\n    "**Resolved in FORGE-020A4C.** Previously Entity Synthesis could sanitize a real model's invalid structure and then satisfy Validator/Level0 evidence, conflating product robustness with model ability. Contract evidence and repair provenance now fail closed for Real Local Level 0. Structured-output fallback mode is also recorded. Future datasets must preserve model-output / Forge-repair / final-artifact separation.\n\n# TECH_DEBT.md\n'''
new_prefix = '''# TD020A4C — Model contract vs Forge repair provenance\n\n**Resolved in FORGE-020A4C.** Previously Entity Synthesis could sanitize a real model's invalid structure and then satisfy Validator/Level0 evidence, conflating product robustness with model ability. Contract evidence and repair provenance now fail closed for Real Local Level 0. Structured-output fallback mode is also recorded. Future datasets must preserve model-output / Forge-repair / final-artifact separation.\n\n# TECH_DEBT.md\n'''
if old_prefix not in content:
    raise RuntimeError("TECH_DEBT.md: malformed 020A4C prefix not found")
write(path, content.replace(old_prefix, new_prefix, 1))

# 6. Record skeptical-review findings in the durable report before full CI.
path = "docs/reports/FORGE-020A4C-REAL-STRUCTURE-INTEGRITY-report.md"
content = read(path)
content = content.replace(
    "Status: **IMPLEMENTED — CI verification pending at creation time**",
    "Status: **IMPLEMENTED — full exact-SHA CI pending closeout**",
    1,
)
review_block = '''\n## Skeptical review after first implementation commit\nThe first implementation commit (`4bb9702d2df495bdda06892704b174ed061388ef`) passed the dedicated 020A4C focused tests, but was **not** treated as complete. Independent code review found:\n\n1. A valid optional field that omitted `required` was incorrectly classified as repaired, even when another field already had `required=true`. This was a false negative in the strict-contract evaluator.\n2. The Prompt contract says no more than 6 fields, while the product sanitizer intentionally accepts up to 8. Seven/eight fields could therefore have been called strict model success. The strict evaluator now enforces the 6-field Prompt limit without pretending the product repaired an artifact it actually accepted.\n3. Existing full-suite RealLocal passing fixtures did not yet opt into the new fail-closed evidence fields and would fail full CI. Fixtures are updated rather than weakening production defaults.\n4. Production `/generate` Mock preflight now asserts the contract evidence reaches `GenerationRecord` and remains non-model-proof (`required_injected`, strict=false), while still proving routing.\n5. Mechanical Markdown quoting damage in CHANGELOG/TECH_DEBT was repaired.\n\nThese are exactly the kind of failures the project must surface before running real Qwen; focused green alone was insufficient evidence.\n'''
if "## Skeptical review after first implementation commit" not in content:
    content = content.rstrip() + review_block + "\n"
write(path, content)

print("FORGE-020A4C skeptical closeout applied")
