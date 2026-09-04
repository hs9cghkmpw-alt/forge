"""テストが Promotion Gate を**実際に通す**ための helper。

**偽の決定を作らない。** ここが返すのは `evaluate_promotion` を本当に
呼んで得た決定である。Gate を迂回する近道をテスト側に用意すると、
Gate が壊れてもテストが緑のままになる——それは置物である。
"""

from __future__ import annotations

from forge_ai.core.promotion.attestation import (
    canonical_permission_manifest_digest,
)
from forge_ai.core.promotion.effects import SourceInspectionResult
from forge_ai.core.promotion.gate import (
    PromotionDecision,
    PromotionRequest,
    evaluate_promotion,
)
from forge_ai.core.sandbox.policy import CapabilityTier, Permission, PermissionManifest


def tier_a_manifest(capability_id: str) -> PermissionManifest:
    return PermissionManifest(
        capability_id=capability_id,
        permissions=frozenset({Permission.LOCAL_COMPUTE}),
        declared_tier=CapabilityTier.A,
    )


def allowed_decision(capability_id: str) -> PromotionDecision:
    """宣言経路と同等の、**本物の Gate を通った**許可決定。"""
    decision = evaluate_promotion(
        PromotionRequest(
            capability_id=capability_id,
            requires_generated_source=False,
            permission_manifest=tier_a_manifest(capability_id),
            inspection=SourceInspectionResult(
                effects=frozenset(), findings=(), files_inspected=0
            ),
            verified_manifest_digest=canonical_permission_manifest_digest(
                tier_a_manifest(capability_id)
            ),
            promoted_manifest_digest=canonical_permission_manifest_digest(
                tier_a_manifest(capability_id)
            ),
        )
    )
    # helper 自身が壊れて「拒否された決定」を配らないようにする。
    assert decision.allowed, decision.to_dict()
    return decision
