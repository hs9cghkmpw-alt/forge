from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement target, found {count}: {old!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Canonical structural contract shared by prompt, raw-model evaluator and provider schema.
contract = ROOT / "forge_ai/core/semantics/entity_contract.py"
contract.write_text(
    '''"""Canonical Entity Synthesis structural contract.

This module contains only provider-independent structural limits. Product-side
sanitizers may be more permissive for robustness, but model capability evidence
must use these stricter limits. Backend adapters import these values rather than
re-declaring a parallel contract.
"""

from __future__ import annotations

ENTITY_IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]*$"
ENTITY_STRICT_MIN_FIELDS = 1
ENTITY_STRICT_MAX_FIELDS = 6
ENTITY_STRICT_MIN_CHOICES = 2
ENTITY_STRICT_MAX_CHOICES = 6

__all__ = [
    "ENTITY_IDENTIFIER_PATTERN",
    "ENTITY_STRICT_MIN_FIELDS",
    "ENTITY_STRICT_MAX_FIELDS",
    "ENTITY_STRICT_MIN_CHOICES",
    "ENTITY_STRICT_MAX_CHOICES",
]
''',
    encoding="utf-8",
)

# entity_synthesizer: consume canonical contract and fail strict evidence when
# prompt-level choice cardinality is exceeded, while retaining the wider product
# sanitizer ceiling for robustness.
replace_once(
    "forge_ai/core/ir/entity_synthesizer.py",
    "from forge_ai.core.semantics.structure_provenance import (\n",
    "from forge_ai.core.semantics.entity_contract import (\n"
    "    ENTITY_IDENTIFIER_PATTERN,\n"
    "    ENTITY_STRICT_MAX_CHOICES,\n"
    "    ENTITY_STRICT_MAX_FIELDS,\n"
    "    ENTITY_STRICT_MIN_CHOICES,\n"
    ")\n"
    "from forge_ai.core.semantics.structure_provenance import (\n",
)
replace_once(
    "forge_ai/core/ir/entity_synthesizer.py",
    '_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")',
    '_IDENTIFIER_PATTERN = re.compile(ENTITY_IDENTIFIER_PATTERN)',
)
replace_once(
    "forge_ai/core/ir/entity_synthesizer.py",
    "# Prompt contract is intentionally stricter than the product sanitizer: the\n"
    "# model is instructed to return no more than 6 fields. Product robustness may\n"
    "# accept 7-8 fields, but that is not strict model-contract success.\n"
    "_STRICT_CONTRACT_MAX_FIELDS = 6\n"
    "# choice型1件が持てる選択肢の上限(Prompt側の指示は2〜6個)。\n"
    "_MAX_CHOICES = 12\n"
    "_MIN_CHOICES = 2",
    "# Product robustness intentionally accepts more than the model contract.\n"
    "# Strict evidence uses the canonical contract imported above.\n"
    "_MAX_CHOICES = 12\n"
    "_MIN_CHOICES = ENTITY_STRICT_MIN_CHOICES",
)
replace_once(
    "forge_ai/core/ir/entity_synthesizer.py",
    "    seen: set[str] = set()\n    valid_field_count = 0\n    any_required = False\n",
    "    seen: set[str] = set()\n"
    "    valid_field_count = 0\n"
    "    any_required = False\n"
    "    within_prompt_choice_limits = True\n",
)
replace_once(
    "forge_ai/core/ir/entity_synthesizer.py",
    "        raw_choices = raw.get(\"choices\")\n        sanitized_choices = _sanitize_choices(raw_choices)\n",
    "        raw_choices = raw.get(\"choices\")\n"
    "        sanitized_choices = _sanitize_choices(raw_choices)\n"
    "        if isinstance(raw_choices, list) and len(raw_choices) > ENTITY_STRICT_MAX_CHOICES:\n"
    "            within_prompt_choice_limits = False\n",
)
replace_once(
    "forge_ai/core/ir/entity_synthesizer.py",
    "    within_prompt_field_limit = fields_received <= _STRICT_CONTRACT_MAX_FIELDS\n",
    "    within_prompt_field_limit = fields_received <= ENTITY_STRICT_MAX_FIELDS\n",
)
replace_once(
    "forge_ai/core/ir/entity_synthesizer.py",
    "        and within_prompt_field_limit\n",
    "        and within_prompt_field_limit\n        and within_prompt_choice_limits\n",
)

# PromptBuilder: derive visible cardinalities from the same contract values.
replace_once(
    "forge_ai/prompt/prompt_builder.py",
    "from typing import Any\n",
    "from typing import Any\n\n"
    "from forge_ai.core.semantics.entity_contract import (\n"
    "    ENTITY_STRICT_MAX_CHOICES,\n"
    "    ENTITY_STRICT_MAX_FIELDS,\n"
    "    ENTITY_STRICT_MIN_CHOICES,\n"
    ")\n",
)
replace_once(
    "forge_ai/prompt/prompt_builder.py",
    '                "   多くても6個まで。そして**1個で足りるなら1個にすること**。\\n"\n',
    '                f"   多くても{ENTITY_STRICT_MAX_FIELDS}個まで。そして**1個で足りるなら1個にすること**。\\n"\n',
)
replace_once(
    "forge_ai/prompt/prompt_builder.py",
    '                "5. choiceを選んだ場合、choicesには実際にありえる選択肢を2〜6個"\n',
    '                f"5. choiceを選んだ場合、choicesには実際にありえる選択肢を{ENTITY_STRICT_MIN_CHOICES}〜{ENTITY_STRICT_MAX_CHOICES}個"\n',
)

# Bridge: make the already-used json_schema mode enforce the structural portions
# of the model contract. No domain-specific values or templates are introduced.
replace_once(
    "backend/app/ai/runtime/forge_ai_provider_bridge.py",
    "from forge_ai.core.semantics.capability_plan import plan_capabilities\n",
    "from forge_ai.core.semantics.capability_plan import plan_capabilities\n"
    "from forge_ai.core.semantics.entity_contract import (\n"
    "    ENTITY_IDENTIFIER_PATTERN,\n"
    "    ENTITY_STRICT_MAX_CHOICES,\n"
    "    ENTITY_STRICT_MAX_FIELDS,\n"
    "    ENTITY_STRICT_MIN_CHOICES,\n"
    "    ENTITY_STRICT_MIN_FIELDS,\n"
    ")\n",
)
replace_once(
    "backend/app/ai/runtime/forge_ai_provider_bridge.py",
    '            "entity_name": {"type": "string"},',
    '            "entity_name": {"type": "string", "pattern": ENTITY_IDENTIFIER_PATTERN},',
)
replace_once(
    "backend/app/ai/runtime/forge_ai_provider_bridge.py",
    '            "fields": {\n                "type": "array",\n                "items": {',
    '            "fields": {\n'
    '                "type": "array",\n'
    '                "minItems": ENTITY_STRICT_MIN_FIELDS,\n'
    '                "maxItems": ENTITY_STRICT_MAX_FIELDS,\n'
    '                "items": {',
)
replace_once(
    "backend/app/ai/runtime/forge_ai_provider_bridge.py",
    '                        "name": {"type": "string"},',
    '                        "name": {"type": "string", "pattern": ENTITY_IDENTIFIER_PATTERN},',
)
replace_once(
    "backend/app/ai/runtime/forge_ai_provider_bridge.py",
    '                        "choices": {"type": "array", "items": {"type": "string"}},',
    '                        "choices": {\n'
    '                            "type": "array",\n'
    '                            "minItems": ENTITY_STRICT_MIN_CHOICES,\n'
    '                            "maxItems": ENTITY_STRICT_MAX_CHOICES,\n'
    '                            "items": {"type": "string"},\n'
    '                        },',
)

# Focused mutation-style contract tests. Any future weakening of a structural
# schema constraint should fail here before a costly real-model run.
test = ROOT / "backend/tests/test_forge_020a5_entity_schema_contract.py"
test.write_text(
    '''"""FORGE-020A5 — provider schema must enforce canonical Entity contract."""

from __future__ import annotations

import re
import unittest

from forge_ai.core.semantics.entity_contract import (
    ENTITY_IDENTIFIER_PATTERN,
    ENTITY_STRICT_MAX_CHOICES,
    ENTITY_STRICT_MAX_FIELDS,
    ENTITY_STRICT_MIN_CHOICES,
    ENTITY_STRICT_MIN_FIELDS,
)
from forge_ai.prompt.prompt_builder import PromptBuilder

from app.ai.runtime.forge_ai_provider_bridge import _RESPONSE_SCHEMAS


class TestEntitySchemaContract(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = _RESPONSE_SCHEMAS["entity_synthesis"]
        self.fields = self.schema["properties"]["fields"]
        self.field = self.fields["items"]

    def test_entity_identifier_is_provider_enforced(self) -> None:
        self.assertEqual(
            self.schema["properties"]["entity_name"]["pattern"],
            ENTITY_IDENTIFIER_PATTERN,
        )

    def test_field_identifier_is_provider_enforced(self) -> None:
        self.assertEqual(
            self.field["properties"]["name"]["pattern"],
            ENTITY_IDENTIFIER_PATTERN,
        )

    def test_identifier_contract_accepts_only_canonical_snake_case(self) -> None:
        pattern = re.compile(ENTITY_IDENTIFIER_PATTERN)
        for value in ("watering_record", "plant2", "a"):
            self.assertIsNotNone(pattern.fullmatch(value), value)
        for value in ("WateringRecord", "water-record", "水やり", "2plant", "has space"):
            self.assertIsNone(pattern.fullmatch(value), value)

    def test_field_count_matches_strict_model_contract(self) -> None:
        self.assertEqual(self.fields["minItems"], ENTITY_STRICT_MIN_FIELDS)
        self.assertEqual(self.fields["maxItems"], ENTITY_STRICT_MAX_FIELDS)

    def test_choice_count_matches_strict_model_contract(self) -> None:
        choices = self.field["properties"]["choices"]
        self.assertEqual(choices["minItems"], ENTITY_STRICT_MIN_CHOICES)
        self.assertEqual(choices["maxItems"], ENTITY_STRICT_MAX_CHOICES)

    def test_schema_does_not_encode_bonsai_or_other_domain_templates(self) -> None:
        rendered = repr(self.schema)
        for domain_word in ("盆栽", "水やり", "買い物", "家計", "釣果"):
            self.assertNotIn(domain_word, rendered)

    def test_prompt_uses_the_same_cardinality_contract(self) -> None:
        prompt = PromptBuilder().build_entity_synthesis_prompt(
            user_text="任意の記録",
            plan_summary={},
            domain_name="generated",
        )
        self.assertIn(f"多くても{ENTITY_STRICT_MAX_FIELDS}個", prompt.system)
        self.assertIn(
            f"{ENTITY_STRICT_MIN_CHOICES}〜{ENTITY_STRICT_MAX_CHOICES}個",
            prompt.system,
        )


if __name__ == "__main__":
    unittest.main()
''',
    encoding="utf-8",
)

# Extend existing 020A4C contract tests with the same-category hole discovered
# by skeptical review: 7 choices is inside the product sanitizer's ceiling but
# outside the model contract and therefore must never count as strict success.
contract_test = ROOT / "forge_ai/tests/test_forge_020a4c_entity_contract_evidence.py"
text = contract_test.read_text(encoding="utf-8")
needle = "\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
if needle not in text:
    raise SystemExit("forge_ai contract test insertion point not found")
extra = '''

class TestStrictChoiceCardinality(unittest.TestCase):
    def test_seven_choices_cannot_masquerade_as_strict_model_success(self) -> None:
        structured = {
            "entity_name": "watering_record",
            "entity_label": "水やり記録",
            "visual_style": "calm",
            "fields": [
                {
                    "name": "condition",
                    "label": "状態",
                    "type": "choice",
                    "required": True,
                    "choices": ["a", "b", "c", "d", "e", "f", "g"],
                }
            ],
        }
        evidence = _entity_contract_evidence(
            structured,
            structured_output_mode="json_schema",
        )
        self.assertFalse(evidence.strict_contract_passed)

'''
contract_test.write_text(text.replace(needle, extra + needle, 1), encoding="utf-8")

print("FORGE-020A5 entity schema contract patch applied")
