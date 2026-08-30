from __future__ import annotations

from dataclasses import replace
import json

import pytest

from forge_ai.core.orchestration.declarative_extension import (
    DeclarativeCapabilityArtifact,
    DeclarativePrimitiveRef,
)
from forge_ai.core.orchestration.extension_manifest import (
    ExtensionEvidence,
    create_extension_manifest,
)
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.orchestration.extension_store import (
    ExtensionStoreError,
    load_promoted_declarative_extension,
    save_promoted_declarative_extension,
)
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel


def _artifact() -> DeclarativeCapabilityArtifact:
    return DeclarativeCapabilityArtifact(
        capability_id="interact.filter",
        primitives=(
            DeclarativePrimitiveRef(
                kind="view", primitive_id="section_header", config={"role": "filter"}
            ),
        ),
        reusable_contract="Reusable filter affordance composed from loaded Forge primitives.",
        language_fragment={
            "op": "append_widget",
            "widget": {
                "type": "section_header",
                "id": "promoted_filter_affordance",
                "properties": {"title": "絞り込み"},
            },
        },
    )


def _manifest():
    candidate = ExtensionCandidate(
        capability_id="interact.filter",
        label_ja="絞り込む",
        support=SupportLevel.MISSING,
        safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.DECLARATIVE,),
        reason="test",
        requires_confirmation=False,
    )
    evidence = ExtensionEvidence(
        semantic_decomposition=True,
        reusable_primitive=True,
        language_binding=True,
        validator_binding=True,
        runtime_binding=True,
        compiler_binding=True,
        tests_pass=True,
        build_pass=True,
        runtime_evidence=True,
    )
    return replace(
        create_extension_manifest(candidate, ExtensionRoute.DECLARATIVE),
        evidence=evidence,
    ).verified().promoted()


def test_promoted_declarative_extension_survives_process_registry_reset(tmp_path) -> None:
    PROMOTED_CAPABILITIES.clear()
    target = tmp_path / "interact.filter.json"
    save_promoted_declarative_extension(target, _manifest(), _artifact())

    PROMOTED_CAPABILITIES.clear()
    assert not PROMOTED_CAPABILITIES.is_promoted("interact.filter")

    installed = load_promoted_declarative_extension(target)
    assert installed.capability_id == "interact.filter"
    assert PROMOTED_CAPABILITIES.is_promoted("interact.filter")
    assert callable(getattr(installed.activation, "apply", None))


def test_store_rejects_integrity_tampering(tmp_path) -> None:
    target = tmp_path / "interact.filter.json"
    save_promoted_declarative_extension(target, _manifest(), _artifact())
    envelope = json.loads(target.read_text(encoding="utf-8"))
    envelope["payload"]["artifact"]["language_fragment"]["widget"]["properties"]["title"] = "tampered"
    target.write_text(json.dumps(envelope), encoding="utf-8")

    PROMOTED_CAPABILITIES.clear()
    with pytest.raises(ExtensionStoreError, match="integrity digest mismatch"):
        load_promoted_declarative_extension(target)
    assert not PROMOTED_CAPABILITIES.is_promoted("interact.filter")


def test_draft_manifest_cannot_be_persisted(tmp_path) -> None:
    candidate = ExtensionCandidate(
        capability_id="interact.filter",
        label_ja="絞り込む",
        support=SupportLevel.MISSING,
        safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.DECLARATIVE,),
        reason="test",
        requires_confirmation=False,
    )
    draft = create_extension_manifest(candidate, ExtensionRoute.DECLARATIVE)
    with pytest.raises(ExtensionStoreError, match="PROMOTED"):
        save_promoted_declarative_extension(tmp_path / "draft.json", draft, _artifact())
