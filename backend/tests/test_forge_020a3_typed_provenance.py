import unittest

from forge_ai.core.orchestration.cognitive_context import (
    CognitiveContext, StructureProvider, StructureProvenance, StructureSource,
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
import unittest
