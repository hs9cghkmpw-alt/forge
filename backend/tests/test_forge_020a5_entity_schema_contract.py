"""FORGE-020A5 — provider schema must enforce canonical Entity contract."""

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
