"""Promotion Gate — **正式採用を許す唯一の判定点**（EXT-10 / EXT-03 / EXT-09）。

## なぜ 1 箇所へ集めるのか

判定が散ると、片方だけ直して片方が残る。このリポジトリは
「作ったが本番から呼ばれない」を 10 回以上繰り返している。
したがって Gate は **1 つの関数**にし、`ExtensionManifest.promoted()` が
**この決定を引数として要求する**形にした。決定を作らずに Promotion する
経路は、書こうとすると型で止まる。

## 拒否理由は typed で残す

`ValueError("something failed")` では、後から集計も分類もできない。
`PromotionRejection` enum を返し、Evidence へそのまま載せる。

## fail closed

分からないものは通さない。特に:

  Permission Manifest が無い    → 拒否（「無いなら安全」は禁止）
  Effect が読めない（UNKNOWN）  → 拒否
  依存の素性が不明              → 拒否
  Sandbox backend が空          → 拒否

## policy-only について

CI の runner は namespace を作れないため `policy-only` で走る。これは
**OS 隔離の証拠ではない**。Gate は既定で OS 隔離を要求し、policy-only を
通すには明示 opt-in が要る。通した場合も Evidence に
`os_isolated: false` と残るので、後から本番証拠と読み違えられない。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from forge_ai.core.promotion.dependencies import (
    DependencyAllowlist,
    DependencyVerdict,
    UnknownSecurityPolicy,
)
from forge_ai.core.promotion.effects import (
    EffectKind,
    SourceInspectionResult,
)
from forge_ai.core.sandbox.policy import (
    CapabilityTier,
    Permission,
    PermissionManifest,
)

ALLOW_POLICY_ONLY_ENV = "FORGE_SANDBOX_ALLOW_POLICY_ONLY"

#: OS 層の強制隔離を通った backend。**`policy-only` と空文字は入らない。**
OS_ISOLATED_BACKENDS = frozenset(
    {"linux-namespace+pid", "linux-namespace", "windows-appcontainer+job"}
)


class PromotionRejection(str, Enum):
    """なぜ通さなかったか。**生の例外文字列で管理しない。**"""

    STATIC_INSPECTION_MISSING = "static_inspection_missing"
    PROHIBITED_EFFECT = "prohibited_effect"
    UNDECLARED_EFFECT = "undeclared_effect"
    SECRET_POLICY_VIOLATION = "secret_policy_violation"
    EFFECT_UNKNOWN = "effect_unknown"

    SANDBOX_ATTESTATION_MISSING = "sandbox_attestation_missing"
    SANDBOX_BACKEND_NOT_ACCEPTABLE = "sandbox_backend_not_acceptable"

    GENERATED_TESTS_FAILED = "generated_tests_failed"
    BUILD_FAILED = "build_failed"
    RUNTIME_PROBE_FAILED = "runtime_probe_failed"
    EVIDENCE_INCOMPLETE = "evidence_incomplete"

    ARTIFACT_DIGEST_MISSING = "artifact_digest_missing"
    VERIFIED_ARTIFACT_MISMATCH = "verified_artifact_mismatch"
    MANIFEST_DIGEST_MISMATCH = "manifest_digest_mismatch"

    PERMISSION_MANIFEST_MISSING = "permission_manifest_missing"
    PERMISSION_MANIFEST_INVALID = "permission_manifest_invalid"
    UNKNOWN_PERMISSION = "unknown_permission"
    TIER_DECLARATION_MISMATCH = "tier_declaration_mismatch"
    TIER_C_WITHOUT_APPROVAL = "tier_c_without_approval"
    TIER_C_APPROVAL_WITHOUT_PROVENANCE = "tier_c_approval_without_provenance"
    EFFECT_EXCEEDS_PERMISSION = "effect_exceeds_permission"

    DEPENDENCY_NOT_ALLOWLISTED = "dependency_not_allowlisted"
    DEPENDENCY_SECURITY_UNKNOWN = "dependency_security_unknown"
    DEPENDENCY_ACQUISITION_ATTEMPT = "dependency_acquisition_attempt"

    IDENTITY_MISMATCH = "identity_mismatch"


class PromotionDenied(RuntimeError):
    """Gate が拒否した。`decision` に typed reason が入っている。"""

    def __init__(self, decision: "PromotionDecision") -> None:
        self.decision = decision
        reasons = ", ".join(item.reason.value for item in decision.rejections)
        super().__init__(f"{decision.capability_id}: promotion refused ({reasons})")


@dataclass(frozen=True, slots=True)
class RejectionDetail:
    reason: PromotionRejection
    detail: str

    def to_dict(self) -> dict:
        return {"reason": self.reason.value, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    capability_id: str
    allowed: bool
    rejections: tuple[RejectionDetail, ...]
    evidence: Mapping[str, object]

    @property
    def reasons(self) -> tuple[PromotionRejection, ...]:
        return tuple(item.reason for item in self.rejections)

    def require_allowed(self) -> None:
        if not self.allowed:
            raise PromotionDenied(self)

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "allowed": self.allowed,
            "rejections": [item.to_dict() for item in self.rejections],
            "evidence": dict(self.evidence),
        }


#: Effect → その Effect を持つために宣言が要る Permission。
#: 宣言より強い Effect を持っていたら Permission escalation である。
_EFFECT_REQUIRES_PERMISSION = {
    EffectKind.NETWORK: Permission.NETWORK_OUTBOUND,
    EffectKind.FILESYSTEM_READ: Permission.FILESYSTEM_WORKSPACE,
    EffectKind.FILESYSTEM_WRITE: Permission.FILESYSTEM_WORKSPACE,
    EffectKind.DESTRUCTIVE_FILESYSTEM: Permission.FILESYSTEM_USER_FILES,
    EffectKind.PROCESS_SPAWN: Permission.PROCESS_SPAWN,
    EffectKind.SHELL: Permission.PROCESS_SPAWN,
    EffectKind.CREDENTIAL_ACCESS: Permission.CREDENTIALS,
    EffectKind.ENVIRONMENT_READ: Permission.CREDENTIALS,
    EffectKind.NATIVE_LIBRARY: Permission.OS_INTEGRATION,
    EffectKind.PERSISTENCE: Permission.LOCAL_STORAGE_WRITE,
    EffectKind.PACKAGE_INSTALL: Permission.NETWORK_OUTBOUND,
    EffectKind.CODE_DOWNLOAD: Permission.NETWORK_OUTBOUND,
}


def policy_only_opt_in() -> bool:
    """policy-only を許す明示 opt-in があるか。**既定は False。**"""
    return os.environ.get(ALLOW_POLICY_ONLY_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True, slots=True)
class PromotionRequest:
    """Gate が判定するのに要るもの全部。**足りなければ拒否される。**"""

    capability_id: str
    requires_generated_source: bool
    """BUILD_TIME のように、生成 Source をホストで実行する経路か。"""

    permission_manifest: PermissionManifest | None = None
    inspection: SourceInspectionResult | None = None
    declared_effects: frozenset[EffectKind] = frozenset()

    sandbox_backend: str = ""
    sandbox_policy_version: str = ""
    sandbox_policy_digest: str = ""

    tests_pass: bool = False
    build_pass: bool = False
    runtime_probe_pass: bool = False

    verified_source_digest: str = ""
    promoted_source_digest: str = ""
    verified_artifact_digest: str = ""
    promoted_artifact_digest: str = ""
    verified_manifest_digest: str = ""
    promoted_manifest_digest: str = ""

    command_sources: tuple[str, ...] = ()
    """build/test で実際に走らせた command 文字列。取得行為の走査対象。"""

    allowlist: DependencyAllowlist | None = None
    unknown_security_policy: UnknownSecurityPolicy = (
        UnknownSecurityPolicy.ALLOW_IF_BUNDLED
    )
    extra_evidence: Mapping[str, object] = field(default_factory=dict)


def _check_permission_manifest(
    request: PromotionRequest, out: list[RejectionDetail]
) -> PermissionManifest | None:
    manifest = request.permission_manifest
    if manifest is None:
        out.append(
            RejectionDetail(
                PromotionRejection.PERMISSION_MANIFEST_MISSING,
                "Permission Manifest が無い。"
                "**無いことを安全とみなさない**（非交渉条件 3）",
            )
        )
        return None
    if not manifest.capability_id:
        out.append(
            RejectionDetail(
                PromotionRejection.PERMISSION_MANIFEST_INVALID,
                "Permission Manifest に capability_id が無い",
            )
        )
        return manifest
    if manifest.capability_id != request.capability_id:
        out.append(
            RejectionDetail(
                PromotionRejection.IDENTITY_MISMATCH,
                f"Manifest の capability_id {manifest.capability_id!r} が "
                f"Promotion 対象 {request.capability_id!r} と違う",
            )
        )
    for permission in manifest.permissions:
        if not isinstance(permission, Permission):
            out.append(
                RejectionDetail(
                    PromotionRejection.UNKNOWN_PERMISSION,
                    f"未知の Permission: {permission!r}",
                )
            )
    if not manifest.tier_matches_declaration:
        out.append(
            RejectionDetail(
                PromotionRejection.TIER_DECLARATION_MISMATCH,
                f"申告 Tier と計算 Tier {manifest.tier.value} が食い違う。"
                "申告を信じない",
            )
        )
    if manifest.tier is CapabilityTier.C:
        if not manifest.human_approval:
            out.append(
                RejectionDetail(
                    PromotionRejection.TIER_C_WITHOUT_APPROVAL,
                    "Tier C は人の承認なしに Promotion しない",
                )
            )
        elif not manifest.approval_reference.strip():
            out.append(
                RejectionDetail(
                    PromotionRejection.TIER_C_APPROVAL_WITHOUT_PROVENANCE,
                    "Tier C の承認に出所が無い（後から検証できない承認は承認ではない）",
                )
            )
    return manifest


def _check_effects(
    request: PromotionRequest,
    manifest: PermissionManifest | None,
    out: list[RejectionDetail],
) -> SourceInspectionResult | None:
    inspection = request.inspection
    if inspection is None:
        if request.requires_generated_source:
            out.append(
                RejectionDetail(
                    PromotionRejection.STATIC_INSPECTION_MISSING,
                    "生成 Source を実行する経路なのに静的検査の結果が無い",
                )
            )
        return None

    if EffectKind.UNKNOWN in inspection.effects:
        out.append(
            RejectionDetail(
                PromotionRejection.EFFECT_UNKNOWN,
                "読めなかった生成物がある。**UNKNOWN を安全側へ倒さない**",
            )
        )

    prohibited = inspection.prohibited - {EffectKind.UNKNOWN}
    if prohibited:
        out.append(
            RejectionDetail(
                PromotionRejection.PROHIBITED_EFFECT,
                "生成 Capability に許されない Effect: "
                + ", ".join(sorted(e.value for e in prohibited)),
            )
        )

    if EffectKind.CREDENTIAL_ACCESS in inspection.effects:
        out.append(
            RejectionDetail(
                PromotionRejection.SECRET_POLICY_VIOLATION,
                "秘密を探す書き方が入っている（値は記録しない）",
            )
        )

    undeclared = inspection.effects - request.declared_effects - {EffectKind.UNKNOWN}
    if undeclared:
        out.append(
            RejectionDetail(
                PromotionRejection.UNDECLARED_EFFECT,
                "宣言されていない Effect: "
                + ", ".join(sorted(e.value for e in undeclared)),
            )
        )

    if manifest is not None:
        escalations = sorted(
            {
                _EFFECT_REQUIRES_PERMISSION[effect].value
                for effect in inspection.effects
                if effect in _EFFECT_REQUIRES_PERMISSION
                and _EFFECT_REQUIRES_PERMISSION[effect] not in manifest.permissions
            }
        )
        if escalations:
            out.append(
                RejectionDetail(
                    PromotionRejection.EFFECT_EXCEEDS_PERMISSION,
                    "宣言 Permission より実 Effect が強い。不足: "
                    + ", ".join(escalations),
                )
            )
    return inspection


def _check_sandbox(request: PromotionRequest, out: list[RejectionDetail]) -> bool:
    if not request.requires_generated_source:
        return False
    backend = request.sandbox_backend
    if not backend:
        out.append(
            RejectionDetail(
                PromotionRejection.SANDBOX_ATTESTATION_MISSING,
                "どの Sandbox backend で走ったかの記録が無い（空 = 隔離を通っていない）",
            )
        )
        return False
    if not request.sandbox_policy_version or not request.sandbox_policy_digest:
        out.append(
            RejectionDetail(
                PromotionRejection.SANDBOX_ATTESTATION_MISSING,
                "Sandbox policy の version / digest が無い",
            )
        )
    os_isolated = backend in OS_ISOLATED_BACKENDS
    if not os_isolated:
        if backend == "policy-only" and policy_only_opt_in():
            # 通すが、**OS 隔離の証拠にはしない。** Evidence に残す。
            return False
        out.append(
            RejectionDetail(
                PromotionRejection.SANDBOX_BACKEND_NOT_ACCEPTABLE,
                f"backend {backend!r} は OS 隔離ではない。"
                "policy-only を本番の安全証明にしない（非交渉条件 1）",
            )
        )
    return os_isolated


def _check_execution_evidence(
    request: PromotionRequest, out: list[RejectionDetail]
) -> None:
    if not request.requires_generated_source:
        return
    if not request.tests_pass:
        out.append(
            RejectionDetail(
                PromotionRejection.GENERATED_TESTS_FAILED,
                "生成 test が通っていない",
            )
        )
    if not request.build_pass:
        out.append(RejectionDetail(PromotionRejection.BUILD_FAILED, "build が通っていない"))
    if not request.runtime_probe_pass:
        out.append(
            RejectionDetail(
                PromotionRejection.RUNTIME_PROBE_FAILED,
                "runtime probe が通っていない",
            )
        )


def _check_identity(request: PromotionRequest, out: list[RejectionDetail]) -> None:
    """検証した物と載せる物が同じか（TOCTOU 対策）。"""
    if not request.requires_generated_source:
        return
    pairs = (
        ("source", request.verified_source_digest, request.promoted_source_digest),
        ("artifact", request.verified_artifact_digest, request.promoted_artifact_digest),
    )
    for label, verified, promoted in pairs:
        if not verified or not promoted:
            out.append(
                RejectionDetail(
                    PromotionRejection.ARTIFACT_DIGEST_MISSING,
                    f"{label} digest が固定されていない",
                )
            )
            continue
        if verified != promoted:
            out.append(
                RejectionDetail(
                    PromotionRejection.VERIFIED_ARTIFACT_MISMATCH,
                    f"検証した {label} と載せる {label} が違う（検証後すり替え）",
                )
            )
    verified_manifest = request.verified_manifest_digest
    promoted_manifest = request.promoted_manifest_digest
    if verified_manifest or promoted_manifest:
        if verified_manifest != promoted_manifest:
            out.append(
                RejectionDetail(
                    PromotionRejection.MANIFEST_DIGEST_MISMATCH,
                    "検証した Manifest と載せる Manifest が違う",
                )
            )


def _check_dependencies(
    request: PromotionRequest,
    inspection: SourceInspectionResult | None,
    out: list[RejectionDetail],
) -> DependencyVerdict | None:
    from forge_ai.core.sandbox.policy import (
        DependencyPolicyViolation,
        assert_dependencies_allowed,
    )

    verdict: DependencyVerdict | None = None
    if inspection is not None:
        allowlist = request.allowlist or DependencyAllowlist.load()
        verdict = allowlist.evaluate(
            inspection.imports,
            unknown_security_policy=request.unknown_security_policy,
        )
        if verdict.unknown:
            out.append(
                RejectionDetail(
                    PromotionRejection.DEPENDENCY_NOT_ALLOWLISTED,
                    "Forge が検証していない依存: " + ", ".join(verdict.unknown),
                )
            )
        if verdict.rejected_for_unknown_security:
            out.append(
                RejectionDetail(
                    PromotionRejection.DEPENDENCY_SECURITY_UNKNOWN,
                    "security_status が不明な依存を安全扱いしない: "
                    + ", ".join(verdict.rejected_for_unknown_security),
                )
            )

    sources = request.command_sources
    if inspection is not None:
        sources = sources + tuple(
            f"{finding.path} {finding.detail}" for finding in inspection.findings
        )
    if sources:
        try:
            assert_dependencies_allowed(
                requested=frozenset(),
                allowlist=frozenset(),
                sources=sources,
            )
        except DependencyPolicyViolation as error:
            out.append(
                RejectionDetail(
                    PromotionRejection.DEPENDENCY_ACQUISITION_ATTEMPT,
                    f"依存をその場で取りに行こうとしている: {error}",
                )
            )
    return verdict


def evaluate_promotion(request: PromotionRequest) -> PromotionDecision:
    """**Promotion を許してよいかを決める唯一の関数。**"""
    rejections: list[RejectionDetail] = []

    manifest = _check_permission_manifest(request, rejections)
    inspection = _check_effects(request, manifest, rejections)
    os_isolated = _check_sandbox(request, rejections)
    _check_execution_evidence(request, rejections)
    _check_identity(request, rejections)
    verdict = _check_dependencies(request, inspection, rejections)

    evidence: dict[str, object] = {
        "capability_id": request.capability_id,
        "requires_generated_source": request.requires_generated_source,
        "sandbox_backend": request.sandbox_backend,
        "os_isolated": os_isolated,
        "sandbox_policy_version": request.sandbox_policy_version,
        "sandbox_policy_digest": request.sandbox_policy_digest,
        "tests_pass": request.tests_pass,
        "build_pass": request.build_pass,
        "runtime_probe_pass": request.runtime_probe_pass,
        "verified_source_digest": request.verified_source_digest,
        "promoted_source_digest": request.promoted_source_digest,
        "verified_artifact_digest": request.verified_artifact_digest,
        "promoted_artifact_digest": request.promoted_artifact_digest,
        "verified_manifest_digest": request.verified_manifest_digest,
        "promoted_manifest_digest": request.promoted_manifest_digest,
        "permission_manifest": manifest.to_dict() if manifest else None,
        "risk_tier": manifest.tier.value if manifest else None,
        "approval_provenance": manifest.approval_reference if manifest else "",
        "static_inspection": inspection.to_dict() if inspection else None,
        "declared_effects": sorted(e.value for e in request.declared_effects),
        "dependencies": verdict.to_dict() if verdict else None,
    }
    evidence.update(dict(request.extra_evidence))

    return PromotionDecision(
        capability_id=request.capability_id,
        allowed=not rejections,
        rejections=tuple(rejections),
        evidence=MappingProxyType(evidence),
    )
