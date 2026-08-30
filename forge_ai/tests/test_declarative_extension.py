from __future__ import annotations

from forge_ai.core.orchestration.declarative_extension import (
    DeclarativeCapabilityArtifact,
    DeclarativeExtensionProbes,
    DeclarativePrimitiveRef,
    implement_declarative_extension,
)
from forge_ai.core.orchestration.extension_manifest import create_extension_manifest
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel


def _candidate() -> ExtensionCandidate:
    return ExtensionCandidate(
        capability_id="interact.filter",
        label_ja="絞り込む",
        support=SupportLevel.MISSING,
        safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.DECLARATIVE, ExtensionRoute.BUILD_TIME),
        reason="missing",
        requires_confirmation=False,
    )


def _artifact(capability_id: str = "interact.filter") -> DeclarativeCapabilityArtifact:
    return DeclarativeCapabilityArtifact(
        capability_id=capability_id,
        primitives=(
            DeclarativePrimitiveRef(
                kind="transform",
                primitive_id="transform.filter",
                config={"predicate": "expression"},
            ),
            DeclarativePrimitiveRef(
                kind="view",
                primitive_id="view.list",
                config={},
            ),
        ),
        reusable_contract="Filter any record collection with a boolean Forge expression.",
        language_fragment={"kind": "filter", "source": "records", "where": {"kind": "expression"}},
    )


def _probes(value: bool = True) -> DeclarativeExtensionProbes:
    probe = lambda artifact: value
    return DeclarativeExtensionProbes(
        language_binding=probe,
        validator_binding=probe,
        runtime_binding=probe,
        compiler_binding=probe,
        tests_pass=probe,
        build_pass=probe,
        runtime_evidence=probe,
    )


def test_complete_declarative_evidence_promotes_capability() -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.DECLARATIVE)
    result = implement_declarative_extension(manifest, _artifact(), _probes(True))
    assert result.status.value == "promoted"
    assert result.promotion_blockers() == ()


def test_failed_probe_keeps_manifest_unpromoted() -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.DECLARATIVE)
    probes = _probes(True)
    probes = DeclarativeExtensionProbes(
        language_binding=probes.language_binding,
        validator_binding=probes.validator_binding,
        runtime_binding=lambda artifact: False,
        compiler_binding=probes.compiler_binding,
        tests_pass=probes.tests_pass,
        build_pass=probes.build_pass,
        runtime_evidence=probes.runtime_evidence,
    )
    result = implement_declarative_extension(manifest, _artifact(), probes)
    assert result.status.value == "implementing"
    assert "runtime_binding" in result.promotion_blockers()


def test_artifact_cannot_swap_capability_identity() -> None:
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.DECLARATIVE)
    try:
        implement_declarative_extension(manifest, _artifact("view.map"), _probes(True))
    except ValueError as exc:
        assert "changed capability identity" in str(exc)
    else:
        raise AssertionError("capability identity substitution was accepted")


def test_unknown_primitive_kind_is_rejected() -> None:
    artifact = DeclarativeCapabilityArtifact(
        capability_id="interact.filter",
        primitives=(DeclarativePrimitiveRef(kind="arbitrary_code", primitive_id="x", config={}),),
        reusable_contract="bad",
        language_fragment={"kind": "x"},
    )
    manifest = create_extension_manifest(_candidate(), ExtensionRoute.DECLARATIVE)
    try:
        implement_declarative_extension(manifest, artifact, _probes(True))
    except ValueError as exc:
        assert "Unsupported primitive kind" in str(exc)
    else:
        raise AssertionError("unsupported primitive kind was accepted")
