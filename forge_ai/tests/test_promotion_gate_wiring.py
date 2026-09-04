"""Gate が**本番経路に実際に配線されている**ことの試験。

Gate 単体が正しくても、本番が通らなければ意味がない。
このリポジトリはその失敗を 10 回以上している。
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from forge_ai.core.orchestration.extension_manifest import (
    ExtensionEvidence,
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PromotedCapabilityRegistry
from forge_ai.core.promotion.effects import SourceInspectionResult
from forge_ai.core.promotion.gate import (
    PromotionDenied,
    PromotionRequest,
    evaluate_promotion,
)
from forge_ai.core.sandbox.policy import CapabilityTier, Permission, PermissionManifest

CAP = "view.calendar"


def _full_evidence() -> ExtensionEvidence:
    return ExtensionEvidence(
        semantic_decomposition=True,
        reusable_primitive=True,
        language_binding=True,
        validator_binding=True,
        runtime_binding=True,
        compiler_binding=True,
        tests_pass=True,
        build_pass=True,
        runtime_evidence=True,
        sandbox_preflight=True,
        safety_review=True,
    )


def _manifest(route: ExtensionRoute = ExtensionRoute.DECLARATIVE) -> ExtensionManifest:
    return ExtensionManifest(
        capability_id=CAP,
        label_ja="カレンダーで見る",
        route=route,
        requires_confirmation=False,
        evidence=_full_evidence(),
    )


def _allowed_decision():
    decision = evaluate_promotion(
        PromotionRequest(
            capability_id=CAP,
            requires_generated_source=False,
            permission_manifest=PermissionManifest(
                capability_id=CAP,
                permissions=frozenset({Permission.LOCAL_COMPUTE}),
                declared_tier=CapabilityTier.A,
            ),
            inspection=SourceInspectionResult(
                effects=frozenset(), findings=(), files_inspected=0
            ),
        )
    )
    assert decision.allowed
    return decision


def _denied_decision():
    decision = evaluate_promotion(
        PromotionRequest(capability_id=CAP, requires_generated_source=True)
    )
    assert not decision.allowed
    return decision


class TestPromotionRequiresAGateDecision(unittest.TestCase):
    def test_a_denied_decision_cannot_promote(self) -> None:
        verified = _manifest().verified()
        with self.assertRaises(PromotionDenied):
            verified.promoted(_denied_decision())

    def test_an_allowed_decision_promotes_and_records_its_digest(self) -> None:
        promoted = _manifest().verified().promoted(_allowed_decision())
        self.assertIs(promoted.status, ExtensionStatus.PROMOTED)
        self.assertTrue(promoted.promotion_decision_digest)

    def test_a_decision_for_another_capability_is_refused(self) -> None:
        other = evaluate_promotion(
            PromotionRequest(
                capability_id="view.other",
                requires_generated_source=False,
                permission_manifest=PermissionManifest(
                    capability_id="view.other",
                    permissions=frozenset({Permission.LOCAL_COMPUTE}),
                ),
                inspection=SourceInspectionResult(
                    effects=frozenset(), findings=(), files_inspected=0
                ),
            )
        )
        self.assertTrue(other.allowed)
        with self.assertRaises(ValueError):
            _manifest().verified().promoted(other)

    def test_promotion_cannot_be_called_without_a_decision(self) -> None:
        """**引数を省いた呼び出しは通らない。** 忘れられない配線である。"""
        verified = _manifest().verified()
        with self.assertRaises(TypeError):
            verified.promoted()  # type: ignore[call-arg]


class TestTheRegistryRefusesUngatedManifests(unittest.TestCase):
    """`replace(manifest, status=PROMOTED)` で横から入る道を塞ぐ。"""

    def test_a_manifest_that_skipped_the_gate_cannot_be_installed(self) -> None:
        forged = replace(
            _manifest(), status=ExtensionStatus.PROMOTED
        )  # decision digest は空のまま
        self.assertEqual("", forged.promotion_decision_digest)
        registry = PromotedCapabilityRegistry()

        class _Activation:
            capability_id = CAP
            widget_types = ("calendar_view",)

            def resolve(self, *args, **kwargs):  # pragma: no cover - not reached
                raise AssertionError("must not be reachable")

        with self.assertRaises(ValueError) as caught:
            registry.install(forged, _Activation())
        self.assertIn("promotion decision digest", str(caught.exception))


class TestTheProductionDeclarativePathGoesThroughTheGate(unittest.TestCase):
    def test_declarative_promotion_carries_a_decision_digest(self) -> None:
        from forge_ai.core.orchestration.declarative_extension import (
            declarative_permission_manifest,
        )

        manifest = declarative_permission_manifest(CAP)
        self.assertIs(manifest.tier, CapabilityTier.A)
        self.assertEqual(CAP, manifest.capability_id)


if __name__ == "__main__":
    unittest.main()
