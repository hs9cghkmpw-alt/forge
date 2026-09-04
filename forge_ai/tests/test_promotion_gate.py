"""Promotion Gate の網羅試験（FORGE-PROMOTION-HARD-GATE-001）。

**正常系を増やしただけで完成にしない。** ここで確かめるのは
「条件を満たさないものが本当に止まるか」である。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from forge_ai.core.promotion.dependencies import (
    DependencyAllowlist,
    UnknownSecurityPolicy,
)
from forge_ai.core.promotion.effects import (
    EffectKind,
    SourceInspectionResult,
    inspect_generated_sources,
)
from forge_ai.core.promotion.gate import (
    PromotionDenied,
    PromotionRejection,
    PromotionRequest,
    evaluate_promotion,
)
from forge_ai.core.sandbox.policy import (
    CapabilityTier,
    Permission,
    PermissionManifest,
)

CAP = "view.calendar"


def _clean_inspection() -> SourceInspectionResult:
    return SourceInspectionResult(effects=frozenset(), findings=(), files_inspected=1)


def _tier_a() -> PermissionManifest:
    return PermissionManifest(
        capability_id=CAP,
        permissions=frozenset({Permission.LOCAL_COMPUTE}),
        declared_tier=CapabilityTier.A,
    )


def _good_request(**overrides) -> PromotionRequest:
    """**通るはずの最小構成。** ここから 1 つ壊して落ちることを見る。"""
    base = dict(
        capability_id=CAP,
        requires_generated_source=True,
        permission_manifest=_tier_a(),
        inspection=_clean_inspection(),
        declared_effects=frozenset(),
        sandbox_backend="linux-namespace+pid",
        sandbox_policy_version="v1",
        sandbox_policy_digest="a" * 64,
        tests_pass=True,
        build_pass=True,
        runtime_probe_pass=True,
        verified_source_digest="s" * 64,
        promoted_source_digest="s" * 64,
        verified_artifact_digest="f" * 64,
        promoted_artifact_digest="f" * 64,
    )
    base.update(overrides)
    return PromotionRequest(**base)


class TestTheHappyPathIsActuallyReachable(unittest.TestCase):
    """**まず通ることを確かめる。** 何も通らない Gate は Gate ではなく壁である。"""

    def test_a_clean_tier_a_capability_is_promoted(self) -> None:
        decision = evaluate_promotion(_good_request())
        self.assertTrue(decision.allowed, decision.to_dict())
        self.assertTrue(decision.evidence["os_isolated"])

    def test_a_declarative_capability_needs_no_build_evidence(self) -> None:
        decision = evaluate_promotion(
            PromotionRequest(
                capability_id=CAP,
                requires_generated_source=False,
                permission_manifest=_tier_a(),
                inspection=_clean_inspection(),
            )
        )
        self.assertTrue(decision.allowed, decision.to_dict())

    def test_tier_b_passes_when_permissions_match_effects(self) -> None:
        manifest = PermissionManifest(
            capability_id=CAP,
            permissions=frozenset(
                {Permission.LOCAL_COMPUTE, Permission.LOCAL_STORAGE_WRITE}
            ),
        )
        self.assertIs(manifest.tier, CapabilityTier.B)
        decision = evaluate_promotion(
            _good_request(permission_manifest=manifest)
        )
        self.assertTrue(decision.allowed, decision.to_dict())

    def test_tier_c_passes_only_with_approval_and_provenance(self) -> None:
        manifest = PermissionManifest(
            capability_id=CAP,
            permissions=frozenset(
                {Permission.LOCAL_COMPUTE, Permission.NETWORK_OUTBOUND}
            ),
            human_approval=True,
            approval_reference="CEO 2026-09-04 承認 #42",
        )
        self.assertIs(manifest.tier, CapabilityTier.C)
        decision = evaluate_promotion(_good_request(permission_manifest=manifest))
        self.assertTrue(decision.allowed, decision.to_dict())
        self.assertEqual(decision.evidence["risk_tier"], "C")


class TestPermissionManifestIsMandatory(unittest.TestCase):
    """非交渉条件 3: **「Manifest が無いなら安全」は禁止。**"""

    def test_a_missing_manifest_refuses_promotion(self) -> None:
        decision = evaluate_promotion(_good_request(permission_manifest=None))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.PERMISSION_MANIFEST_MISSING, decision.reasons)

    def test_a_manifest_without_capability_id_is_invalid(self) -> None:
        broken = PermissionManifest(capability_id="", permissions=frozenset())
        decision = evaluate_promotion(_good_request(permission_manifest=broken))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.PERMISSION_MANIFEST_INVALID, decision.reasons)

    def test_a_manifest_for_another_capability_is_refused(self) -> None:
        other = PermissionManifest(
            capability_id="view.somethingelse",
            permissions=frozenset({Permission.LOCAL_COMPUTE}),
        )
        decision = evaluate_promotion(_good_request(permission_manifest=other))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.IDENTITY_MISMATCH, decision.reasons)

    def test_a_faked_tier_is_refused(self) -> None:
        """Tier を低く申告しても、**権限から計算した Tier が勝つ。**"""
        liar = PermissionManifest(
            capability_id=CAP,
            permissions=frozenset({Permission.NETWORK_OUTBOUND}),
            declared_tier=CapabilityTier.A,
            human_approval=True,
            approval_reference="x",
        )
        decision = evaluate_promotion(_good_request(permission_manifest=liar))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.TIER_DECLARATION_MISMATCH, decision.reasons)

    def test_an_unknown_permission_is_refused(self) -> None:
        """未知の Permission 値が混ざったら通さない。

        `frozenset` は実行時に型を検査しないので、生文字列が入りうる。
        **知らない権限を「たぶん無害」にしない。**
        """
        smuggled = PermissionManifest(
            capability_id=CAP,
            permissions=frozenset({Permission.LOCAL_COMPUTE, "root.everything"}),  # type: ignore[arg-type]
        )
        decision = evaluate_promotion(_good_request(permission_manifest=smuggled))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.UNKNOWN_PERMISSION, decision.reasons)

    def test_tier_c_without_human_approval_is_refused(self) -> None:
        manifest = PermissionManifest(
            capability_id=CAP,
            permissions=frozenset({Permission.NETWORK_OUTBOUND}),
        )
        decision = evaluate_promotion(_good_request(permission_manifest=manifest))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.TIER_C_WITHOUT_APPROVAL, decision.reasons)

    def test_tier_c_approval_without_provenance_is_refused(self) -> None:
        manifest = PermissionManifest(
            capability_id=CAP,
            permissions=frozenset({Permission.NETWORK_OUTBOUND}),
            human_approval=True,
            approval_reference="   ",
        )
        decision = evaluate_promotion(_good_request(permission_manifest=manifest))
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.TIER_C_APPROVAL_WITHOUT_PROVENANCE, decision.reasons
        )


class TestEffectsMustNotExceedPermissions(unittest.TestCase):
    def test_an_undeclared_effect_refuses_promotion(self) -> None:
        inspection = SourceInspectionResult(
            effects=frozenset({EffectKind.NETWORK}), findings=(), files_inspected=1
        )
        decision = evaluate_promotion(_good_request(inspection=inspection))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.UNDECLARED_EFFECT, decision.reasons)

    def test_an_effect_stronger_than_the_declared_permission_is_refused(self) -> None:
        inspection = SourceInspectionResult(
            effects=frozenset({EffectKind.NETWORK}), findings=(), files_inspected=1
        )
        decision = evaluate_promotion(
            _good_request(
                inspection=inspection,
                declared_effects=frozenset({EffectKind.NETWORK}),
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.EFFECT_EXCEEDS_PERMISSION, decision.reasons)

    def test_a_prohibited_effect_is_refused_even_if_declared(self) -> None:
        """**宣言すれば通る、にしない。** shell は宣言しても載せない。"""
        inspection = SourceInspectionResult(
            effects=frozenset({EffectKind.SHELL}), findings=(), files_inspected=1
        )
        decision = evaluate_promotion(
            _good_request(
                inspection=inspection,
                declared_effects=frozenset({EffectKind.SHELL}),
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.PROHIBITED_EFFECT, decision.reasons)

    def test_unknown_effects_fail_closed(self) -> None:
        inspection = SourceInspectionResult(
            effects=frozenset({EffectKind.UNKNOWN}), findings=(), files_inspected=1
        )
        decision = evaluate_promotion(_good_request(inspection=inspection))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.EFFECT_UNKNOWN, decision.reasons)

    def test_missing_inspection_refuses_generated_source(self) -> None:
        decision = evaluate_promotion(_good_request(inspection=None))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.STATIC_INSPECTION_MISSING, decision.reasons)

    def test_secret_hunting_is_reported_as_a_secret_violation(self) -> None:
        inspection = SourceInspectionResult(
            effects=frozenset({EffectKind.CREDENTIAL_ACCESS}),
            findings=(),
            files_inspected=1,
        )
        decision = evaluate_promotion(_good_request(inspection=inspection))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.SECRET_POLICY_VIOLATION, decision.reasons)


class TestSandboxEvidenceIsRequired(unittest.TestCase):
    def test_a_missing_backend_refuses_promotion(self) -> None:
        decision = evaluate_promotion(_good_request(sandbox_backend=""))
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.SANDBOX_ATTESTATION_MISSING, decision.reasons
        )

    def test_a_missing_policy_digest_refuses_promotion(self) -> None:
        decision = evaluate_promotion(_good_request(sandbox_policy_digest=""))
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.SANDBOX_ATTESTATION_MISSING, decision.reasons
        )

    def test_windows_appcontainer_counts_as_os_isolation(self) -> None:
        """**Windows を弱めない。** 実機 backend は OS 隔離として通る。"""
        decision = evaluate_promotion(
            _good_request(sandbox_backend="windows-appcontainer+job")
        )
        self.assertTrue(decision.allowed, decision.to_dict())
        self.assertTrue(decision.evidence["os_isolated"])

    def test_policy_only_is_refused_without_explicit_opt_in(self) -> None:
        """非交渉条件 1: **policy-only を本番の安全証明にしない。**"""
        with patch.dict("os.environ", {}, clear=True):
            decision = evaluate_promotion(_good_request(sandbox_backend="policy-only"))
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.SANDBOX_BACKEND_NOT_ACCEPTABLE, decision.reasons
        )

    def test_policy_only_never_counts_as_os_isolation_even_when_allowed(self) -> None:
        """CI の opt-in で通しても、**Evidence は os_isolated=False のまま。**

        ここを混同すると、CI が緑なだけで「実 OS 隔離で検証済み」と
        読めてしまう。読めないようにしておく。
        """
        with patch.dict("os.environ", {"FORGE_SANDBOX_ALLOW_POLICY_ONLY": "1"}):
            decision = evaluate_promotion(_good_request(sandbox_backend="policy-only"))
        self.assertTrue(decision.allowed, decision.to_dict())
        self.assertFalse(decision.evidence["os_isolated"])
        self.assertEqual(decision.evidence["sandbox_backend"], "policy-only")

    def test_an_unknown_backend_name_is_refused(self) -> None:
        decision = evaluate_promotion(_good_request(sandbox_backend="totally-safe"))
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.SANDBOX_BACKEND_NOT_ACCEPTABLE, decision.reasons
        )


class TestExecutionEvidenceIsRequired(unittest.TestCase):
    def test_failing_tests_refuse_promotion(self) -> None:
        decision = evaluate_promotion(_good_request(tests_pass=False))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.GENERATED_TESTS_FAILED, decision.reasons)

    def test_failing_build_refuses_promotion(self) -> None:
        decision = evaluate_promotion(_good_request(build_pass=False))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.BUILD_FAILED, decision.reasons)

    def test_failing_runtime_probe_refuses_promotion(self) -> None:
        decision = evaluate_promotion(_good_request(runtime_probe_pass=False))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.RUNTIME_PROBE_FAILED, decision.reasons)


class TestVerifiedArtifactEqualsPromotedArtifact(unittest.TestCase):
    """検証後すり替え（TOCTOU）を許さない。"""

    def test_source_swapped_after_verification_is_refused(self) -> None:
        decision = evaluate_promotion(_good_request(promoted_source_digest="b" * 64))
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.VERIFIED_ARTIFACT_MISMATCH, decision.reasons
        )

    def test_artifact_swapped_after_verification_is_refused(self) -> None:
        decision = evaluate_promotion(_good_request(promoted_artifact_digest="c" * 64))
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.VERIFIED_ARTIFACT_MISMATCH, decision.reasons
        )

    def test_a_missing_digest_is_refused(self) -> None:
        decision = evaluate_promotion(_good_request(verified_source_digest=""))
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.ARTIFACT_DIGEST_MISSING, decision.reasons)

    def test_a_swapped_manifest_is_refused(self) -> None:
        decision = evaluate_promotion(
            _good_request(
                verified_manifest_digest="m" * 64,
                promoted_manifest_digest="n" * 64,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn(PromotionRejection.MANIFEST_DIGEST_MISMATCH, decision.reasons)


class TestDependencyPolicy(unittest.TestCase):
    def test_an_unlisted_dependency_refuses_promotion(self) -> None:
        inspection = SourceInspectionResult(
            effects=frozenset(),
            findings=(),
            files_inspected=1,
            imports=frozenset({"package:evil/evil.dart"}),
        )
        decision = evaluate_promotion(_good_request(inspection=inspection))
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.DEPENDENCY_NOT_ALLOWLISTED, decision.reasons
        )

    def test_a_listed_dependency_is_accepted(self) -> None:
        inspection = SourceInspectionResult(
            effects=frozenset(),
            findings=(),
            files_inspected=1,
            imports=frozenset({"dart:math", "package:flutter/material.dart"}),
        )
        decision = evaluate_promotion(_good_request(inspection=inspection))
        self.assertTrue(decision.allowed, decision.to_dict())

    def test_unknown_security_status_can_be_refused_by_policy(self) -> None:
        """**UNKNOWN を安全扱いしない Policy が選べること。**"""
        inspection = SourceInspectionResult(
            effects=frozenset(),
            findings=(),
            files_inspected=1,
            imports=frozenset({"dart:math"}),
        )
        decision = evaluate_promotion(
            _good_request(
                inspection=inspection,
                unknown_security_policy=UnknownSecurityPolicy.REJECT,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.DEPENDENCY_SECURITY_UNKNOWN, decision.reasons
        )

    def test_a_dependency_acquisition_command_refuses_promotion(self) -> None:
        decision = evaluate_promotion(
            _good_request(command_sources=("flutter pub get",))
        )
        self.assertFalse(decision.allowed)
        self.assertIn(
            PromotionRejection.DEPENDENCY_ACQUISITION_ATTEMPT, decision.reasons
        )

    def test_adding_a_dependency_without_updating_the_allowlist_fails(self) -> None:
        """コードに足しただけで allowlist 未更新なら落ちる。"""
        allowlist = DependencyAllowlist.load()
        self.assertNotIn("package:dio/dio.dart", allowlist.names)
        verdict = allowlist.evaluate(frozenset({"package:dio/dio.dart"}))
        self.assertFalse(verdict.ok)
        self.assertIn("package:dio/dio.dart", verdict.unknown)


class TestTheDecisionIsTypedAndTraceable(unittest.TestCase):
    """実装要求 G: `passed=True` だけでは足りない。"""

    def test_rejections_are_typed_not_raw_strings(self) -> None:
        decision = evaluate_promotion(_good_request(permission_manifest=None))
        for item in decision.rejections:
            self.assertIsInstance(item.reason, PromotionRejection)

    def test_the_evidence_carries_every_required_field(self) -> None:
        decision = evaluate_promotion(_good_request())
        for key in (
            "sandbox_backend",
            "os_isolated",
            "risk_tier",
            "approval_provenance",
            "static_inspection",
            "dependencies",
            "verified_source_digest",
            "promoted_source_digest",
            "tests_pass",
            "build_pass",
            "runtime_probe_pass",
            "permission_manifest",
        ):
            self.assertIn(key, decision.evidence)

    def test_denial_raises_with_the_decision_attached(self) -> None:
        decision = evaluate_promotion(_good_request(tests_pass=False))
        with self.assertRaises(PromotionDenied) as caught:
            decision.require_allowed()
        self.assertIs(caught.exception.decision, decision)

    def test_no_secret_values_appear_in_the_evidence(self) -> None:
        """秘密の**値**を Evidence へ書かない（CLAUDE.md §4）。"""
        source = 'const key = String.fromEnvironment("API_KEY_VALUE_ABCDEF");'
        inspection = inspect_generated_sources((("lib/a.dart", source),))
        decision = evaluate_promotion(_good_request(inspection=inspection))
        rendered = repr(decision.to_dict())
        self.assertNotIn("ABCDEF", rendered)


if __name__ == "__main__":
    unittest.main()


def _load_mutation_runner():
    """runner を module として読む。

    `dataclass` は定義時に `sys.modules` を引くので、**登録してから**
    exec する必要がある（登録せずに実行して AttributeError を出した）。
    """
    import importlib.util
    import pathlib
    import sys

    runner_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "scripts"
        / "promotion_mutation_runner.py"
    )
    spec = importlib.util.spec_from_file_location("_forge_mutation_runner", runner_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestEveryCriticalGateIsMutationCovered(unittest.TestCase):
    """**Gate を足して mutation を足し忘れる**を機械で止める。

    ここが落ちたら、新しい拒否理由に対応する破壊試験が無いということ。
    「今回壊した分だけ分かる」へ戻らないための歯止めである。
    """

    def test_every_rejection_reason_has_a_mutation(self) -> None:
        module = _load_mutation_runner()
        covered = {value for m in module.MUTATIONS for value in m.covers}
        covered |= set(module.UNMUTATED_REJECTIONS)
        all_reasons = {reason.value for reason in PromotionRejection}
        missing = sorted(all_reasons - covered)
        self.assertEqual(
            [],
            missing,
            "この拒否理由に対応する mutation が無い（置物になりうる）: "
            + ", ".join(missing),
        )

    def test_no_mutation_points_at_a_removed_reason(self) -> None:
        module = _load_mutation_runner()
        all_reasons = {reason.value for reason in PromotionRejection}
        stale = sorted({v for m in module.MUTATIONS for v in m.covers} - all_reasons)
        self.assertEqual(
            [], stale, "存在しない拒否理由を指している mutation: " + ", ".join(stale)
        )
