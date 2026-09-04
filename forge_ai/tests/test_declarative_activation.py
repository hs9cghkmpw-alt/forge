from __future__ import annotations

from forge_ai.tests.promotion_helpers import allowed_decision


def _gate_promote(manifest):
    """本物の Gate を通して PROMOTED にする。"""
    return manifest.promoted(allowed_decision(manifest.capability_id))

from dataclasses import replace

import pytest

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRWidget
from forge_ai.core.orchestration.declarative_activation import (
    DeclarativeActivationError, activation_from_artifact,
    apply_promoted_document_activations,
)
from forge_ai.core.orchestration.declarative_extension import (
    DeclarativeCapabilityArtifact, DeclarativePrimitiveRef,
)
from forge_ai.core.orchestration.extension_manifest import ExtensionEvidence, create_extension_manifest
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel


def _artifact() -> DeclarativeCapabilityArtifact:
    return DeclarativeCapabilityArtifact(
        capability_id="interact.filter",
        primitives=(DeclarativePrimitiveRef(kind="view", primitive_id="section_header", config={}),),
        reusable_contract="Append an existing-language filter affordance to generated screens.",
        language_fragment={
            "op": "append_widget",
            "widget": {
                "type": "section_header",
                "id": "promoted_filter_affordance",
                "properties": {"title": "絞り込み"},
            },
        },
    )


def _document() -> ForgeIRDocument:
    screen = ForgeIRScreen(
        id="screen", title="Test", state={},
        body=ForgeIRWidget(type="column", id="root", children=()),
    )
    return ForgeIRDocument(version="1.15", initial_screen_id="screen", screens=(screen,), app_title="Test")


def _promoted_manifest():
    candidate = ExtensionCandidate(
        capability_id="interact.filter", label_ja="絞り込む",
        support=SupportLevel.MISSING, safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.DECLARATIVE,), reason="test", requires_confirmation=False,
    )
    evidence = ExtensionEvidence(
        semantic_decomposition=True, reusable_primitive=True, language_binding=True,
        validator_binding=True, runtime_binding=True, compiler_binding=True,
        tests_pass=True, build_pass=True, runtime_evidence=True,
    )
    return _gate_promote(replace(
        create_extension_manifest(candidate, ExtensionRoute.DECLARATIVE), evidence=evidence
    ).verified())


def test_promoted_activation_changes_generated_document() -> None:
    PROMOTED_CAPABILITIES.clear()
    activation = activation_from_artifact(_artifact())
    PROMOTED_CAPABILITIES.install(_promoted_manifest(), activation)

    result = apply_promoted_document_activations(_document(), ("interact.filter",))
    assert result.screens[0].body.children[-1].id == "promoted_filter_affordance"
    assert result.screens[0].body.children[-1].properties["title"] == "絞り込み"


def test_unrequested_promoted_capability_does_not_modify_document() -> None:
    PROMOTED_CAPABILITIES.clear()
    activation = activation_from_artifact(_artifact())
    PROMOTED_CAPABILITIES.install(_promoted_manifest(), activation)

    original = _document()
    result = apply_promoted_document_activations(original, ())
    assert result == original


def test_unknown_declarative_operation_fails_closed() -> None:
    bad = replace(_artifact(), language_fragment={"op": "generated_python"})
    activation = activation_from_artifact(bad)
    with pytest.raises(DeclarativeActivationError, match="BUILD_TIME"):
        activation.apply(_document())
