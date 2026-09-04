"""Evidence-gated lifecycle for reusable Forge capability extensions.

This module is the bridge between *planning an extension* and *claiming that the
capability was acquired*.  A semantic gap must never become IMPLEMENTED merely
because code or a manifest was generated.

Promotion requires evidence across the full binding chain:

semantic decomposition -> Forge Language/validator -> runtime/compiler -> tests
-> build/runtime evidence -> sandbox preflight for BUILD_TIME -> safety review
where applicable.

The manifest is deliberately capability-oriented, not app-oriented.  A Golden
request may motivate an extension, but the produced capability must be reusable
for unseen requests before it can be promoted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256

from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.promotion.attestation import (
    PromotionAttestation,
    canonical_extension_manifest_digest,
)
from forge_ai.core.promotion.gate import PromotionDecision


class ExtensionStatus(str, Enum):
    DRAFT = "draft"
    IMPLEMENTING = "implementing"
    VERIFIED = "verified"
    PROMOTED = "promoted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ExtensionEvidence:
    """Evidence required before a generated capability can enter the catalog."""

    semantic_decomposition: bool = False
    reusable_primitive: bool = False
    language_binding: bool = False
    validator_binding: bool = False
    runtime_binding: bool = False
    compiler_binding: bool = False
    tests_pass: bool = False
    build_pass: bool = False
    runtime_evidence: bool = False
    sandbox_preflight: bool = False
    safety_review: bool = False


@dataclass(frozen=True, slots=True)
class ExtensionManifest:
    capability_id: str
    label_ja: str
    route: ExtensionRoute
    requires_confirmation: bool
    status: ExtensionStatus = ExtensionStatus.DRAFT
    evidence: ExtensionEvidence = ExtensionEvidence()
    source_reason: str = ""
    promotion_attestation: PromotionAttestation | None = None
    """**Gate が判定に使った入力一式**（001A / Major 1）。

    以前はここが digest 文字列だけで、Registry は「非空か」しか見ていな
    かった。したがって `replace(manifest, status=PROMOTED,
    promotion_decision_digest="fake")` で通せた——**実際に再現した。**

    「`promoted()` だけが埋める」というコメントは、`dataclasses.replace`
    に対する Security Boundary にならない。

    いまは結論ではなく**入力**を持つ。Registry と Store はこれで
    `reevaluate_attestation()` を走らせ、**もう一度 Gate を通す。**
    """

    promotion_decision_digest: str = ""
    """`promotion_attestation` の指紋。**単独では信用されない。**

    Registry は「非空か」ではなく「Attestation から計算し直した値と
    一致するか」を見る。すり替えを検出するための値であって、
    通過の証明ではない。
    """

    def promotion_blockers(self) -> tuple[str, ...]:
        """Return exact missing proof; empty means promotion is permitted."""
        required = {
            "semantic_decomposition": self.evidence.semantic_decomposition,
            "reusable_primitive": self.evidence.reusable_primitive,
            "language_binding": self.evidence.language_binding,
            "validator_binding": self.evidence.validator_binding,
            "runtime_binding": self.evidence.runtime_binding,
            "compiler_binding": self.evidence.compiler_binding,
            "tests_pass": self.evidence.tests_pass,
            "build_pass": self.evidence.build_pass,
            "runtime_evidence": self.evidence.runtime_evidence,
        }
        # Generated BUILD_TIME source must never become a reusable capability just
        # because a custom builder returned tests/build/runtime=True.  The sandbox
        # gate is a lifecycle invariant, not merely an implementation detail of one
        # runner.  Other routes do not claim generated host-code execution and are
        # therefore not forced through this specific proof.
        if self.route is ExtensionRoute.BUILD_TIME:
            required["sandbox_preflight"] = self.evidence.sandbox_preflight
        if self.requires_confirmation:
            required["safety_review"] = self.evidence.safety_review
        return tuple(name for name, ok in required.items() if not ok)

    @property
    def can_promote(self) -> bool:
        return not self.promotion_blockers()

    def verified(self) -> "ExtensionManifest":
        blockers = self.promotion_blockers()
        if blockers:
            raise ValueError(
                "Extension cannot be VERIFIED without complete evidence: "
                + ", ".join(blockers)
            )
        return replace(self, status=ExtensionStatus.VERIFIED)

    def promoted(self, decision: PromotionDecision) -> "ExtensionManifest":
        """**Promotion Gate の決定なしに PROMOTED にはできない。**

        `decision` を必須引数にしてあるのは、「呼ぶ側が忘れずに Gate を
        通す」設計が忘れられるからである（このリポジトリで 10 回以上起きた）。
        引数を省いた呼び出しは実行前に TypeError で止まる。
        """
        if self.status is not ExtensionStatus.VERIFIED:
            raise ValueError("Only a VERIFIED extension may be promoted to a reusable capability.")
        if decision.capability_id != self.capability_id:
            raise ValueError(
                "Promotion decision is for a different capability: "
                f"{decision.capability_id!r} != {self.capability_id!r}"
            )
        decision.require_allowed()
        if decision.attestation is None:
            raise ValueError(
                "Promotion decision carries no attestation; refusing to promote. "
                "A decision without its inputs cannot be re-verified at install."
            )
        # **昇格する Manifest そのものへ束縛する**（001A / Major 2）。
        # status と promotion 系 field を除いた正準 digest なので、
        # verified→promoted で値は変わらない。install 時に計算し直して
        # 突き合わせるため、**検証後に Manifest を書き換えると落ちる。**
        attestation = decision.attestation.bound_to_manifest(
            canonical_extension_manifest_digest(self)
        )
        return replace(
            self,
            status=ExtensionStatus.PROMOTED,
            promotion_attestation=attestation,
            promotion_decision_digest=attestation.digest(),
        )


def create_extension_manifest(
    candidate: ExtensionCandidate,
    route: ExtensionRoute,
) -> ExtensionManifest:
    """Create a draft only after decomposition selected a permitted managed route.

    NEEDS_DECOMPOSITION is intentionally not executable.  Unknown semantic gaps
    must first be decomposed into an exact reusable capability.
    """
    if route is ExtensionRoute.NEEDS_DECOMPOSITION:
        raise ValueError("Unresolved semantic structure must be decomposed before creating an extension manifest.")
    if route not in candidate.routes:
        raise ValueError(
            f"Route {route.value!r} is not permitted for capability {candidate.capability_id!r}."
        )
    return ExtensionManifest(
        capability_id=candidate.capability_id,
        label_ja=candidate.label_ja,
        route=route,
        requires_confirmation=candidate.requires_confirmation,
        source_reason=candidate.reason,
    )


def promotion_decision_digest(decision: PromotionDecision) -> str:
    """決定そのものの指紋。後から「何を根拠に通したか」を照合できる。"""
    payload = json.dumps(decision.to_dict(), sort_keys=True, default=str)
    return sha256(payload.encode("utf-8")).hexdigest()
