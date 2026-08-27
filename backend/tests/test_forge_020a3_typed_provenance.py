"""**構造の出所は、診断の書式が変わっても生き残る**（020A3）。

`CognitiveContext` が型で持っているので、`decision_trace` の文言を
変えても Evidence は壊れない。
"""

import unittest

from forge_ai.core.orchestration.cognitive_context import (
    CognitiveContext,
    StructureProvenance,
    StructureProvider,
    StructureSource,
)


class TypedProvenanceTests(unittest.TestCase):
    def test_typed_provenance_survives_diagnostic_changes(self) -> None:
        context = CognitiveContext(
            raw_input="private input", started_at="now",
            structure_provenance=StructureProvenance(
                StructureSource.DETERMINISTIC_CAPABILITY_PLAN,
                StructureProvider.NONE, "entity_structure",
            ), decision_trace=(),
        )
        provenance = context.structure_provenance
        self.assertIs(provenance.source, StructureSource.DETERMINISTIC_CAPABILITY_PLAN)
        self.assertIs(provenance.provider, StructureProvider.NONE)
        self.assertFalse(provenance.is_ai)

    def test_the_type_is_shared_with_the_backend_not_copied(self) -> None:
        """**同じ値の enum を2つ置かない**（merge、TD85 と同じ形）。"""
        from app.ai.gateway.capability_evidence import GenerationStructureSource

        self.assertIs(GenerationStructureSource, StructureSource)


if __name__ == "__main__":
    unittest.main()
