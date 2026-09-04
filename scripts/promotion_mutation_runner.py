#!/usr/bin/env python3
"""Critical Gate の**全数** mutation 検査（QA-05 / 実装要求 E）。

## なぜ要るか

「テストを書いた」と「Gate が効いている」は別である。テストは、
守っているつもりの条件を外しても落ちないことがある——実際このリポジトリで
2 件の置物を作った（2026-09-04、CPU 上限と memory 上限）。

したがって **Guard を 1 つずつ壊して、対応するテストが落ちることを確認する**。
落ちなければその Guard は存在しないものとして扱う。

## 「今回壊した分だけ分かる」からの脱却

以前は手で 1 つずつ壊していたので、**壊し忘れた Guard は永久に未検証**
だった。ここでは Critical Gate を一覧として持ち、全数を機械で回す。
Gate を足したらこの一覧へ足す——足し忘れると
`test_every_critical_gate_is_mutation_covered` が落ちる。

使い方:

    python3 scripts/promotion_mutation_runner.py
    python3 scripts/promotion_mutation_runner.py --only sandbox_backend_check
"""

from __future__ import annotations

import argparse
import dataclasses
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclasses.dataclass(frozen=True)
class Mutation:
    """1 つの Critical Guard を壊す指示。"""

    name: str
    description: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    covers: tuple[str, ...] = ()
    """この mutation が守っている `PromotionRejection` の値。

    **これを書かないと coverage 試験が落ちる。** Gate を足して mutation を
    足し忘れる、を機械で止めるための紐付けである。
    """

    @property
    def file(self) -> Path:
        return REPO / self.path


GATE = "forge_ai/core/promotion/gate.py"
EFFECTS = "forge_ai/core/promotion/effects.py"
MANIFEST = "forge_ai/core/orchestration/extension_manifest.py"
REGISTRY = "forge_ai/core/orchestration/extension_registry.py"
DEPS = "forge_ai/core/promotion/dependencies.py"
VERIFY = "forge_ai/core/orchestration/promotion_verification.py"
STORE = "forge_ai/core/orchestration/extension_store.py"

GATE_TESTS = ("forge_ai/tests/test_promotion_gate.py",)
CORPUS_TESTS = ("forge_ai/tests/test_generated_source_effect_corpus.py",)
WIRING_TESTS = (
    "forge_ai/tests/test_promotion_gate_wiring.py",
    "forge_ai/tests/test_extension_registry.py",
)
FORGERY_TESTS = ("forge_ai/tests/test_promotion_forgery.py",)
STORE_TESTS = (
    "forge_ai/tests/test_promotion_forgery.py",
    "forge_ai/tests/test_extension_store.py",
)

#: mutation を持たない理由が説明できる rejection。**「面倒だから」は理由でない。**
#: Gate の拒否理由ではないが、**壊れたら偽造が通る**不変条件。
#:
#: Registry / Store 側の再検証は「拒否理由 enum」を持たない。しかし
#: これが壊れると `PromotionRejection` を 1 つも変えずに偽造が通るので、
#: 破壊試験の対象としては同格である。
VERIFICATION_INVARIANTS = {
    "attestation_missing",
    "attestation_digest_mismatch",
    "attestation_capability_mismatch",
    "attestation_manifest_unbound",
    "attestation_manifest_mismatch",
    "attestation_not_reevaluated",
    "attestation_permission_tampered",
    "store_not_reverified",
    "registry_not_reverified",
    "unknown_security_default_relaxed",
}

UNMUTATED_REJECTIONS = {
    # capability_id 不一致は Manifest 検査と同じ if 連鎖の中にあり、
    # `permission_manifest_check` を壊すと同時に落ちる。
    "identity_mismatch",
    # 現在この理由を出す経路がない（将来 Evidence 集約を足したら mutation も足す）。
    "evidence_incomplete",
}

MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        name="permission_manifest_check",
        description="Permission Manifest が無くても通す",
        path=GATE,
        old="""    manifest = request.permission_manifest
    if manifest is None:""",
        new="""    manifest = request.permission_manifest
    if False:""",
        tests=GATE_TESTS,
        covers=('permission_manifest_missing', 'permission_manifest_invalid'),
    ),
    Mutation(
        name="unknown_permission_check",
        description="知らない Permission 値を通す",
        path=GATE,
        old="        if not isinstance(permission, Permission):",
        new="        if False:",
        tests=GATE_TESTS,
        covers=("unknown_permission",),
    ),
    Mutation(
        name="tier_declaration_check",
        description="申告 Tier を信じる（計算 Tier と突き合わせない）",
        path=GATE,
        old="    if not manifest.tier_matches_declaration:",
        new="    if False:",
        tests=GATE_TESTS,
        covers=('tier_declaration_mismatch',),
    ),
    Mutation(
        name="human_approval_check",
        description="Tier C を人の承認なしで通す",
        path=GATE,
        old="        if not manifest.human_approval:",
        new="        if False:",
        tests=GATE_TESTS,
        covers=('tier_c_without_approval',),
    ),
    Mutation(
        name="approval_provenance_check",
        description="承認の出所を問わない",
        path=GATE,
        old="        elif not manifest.approval_reference.strip():",
        new="        elif False:",
        tests=GATE_TESTS,
        covers=('tier_c_approval_without_provenance',),
    ),
    Mutation(
        name="sandbox_attestation_check",
        description="どの Sandbox で走ったか不明でも通す",
        path=GATE,
        old="""    if not backend:
        out.append(""",
        new="""    if False:
        out.append(""",
        tests=GATE_TESTS,
        covers=('sandbox_attestation_missing',),
    ),
    Mutation(
        name="policy_only_treated_as_os_isolated",
        description="policy-only を OS 隔離として数える（非交渉条件 1 違反）",
        path=GATE,
        old='OS_ISOLATED_BACKENDS = frozenset(\n    {"linux-namespace+pid", "linux-namespace", "windows-appcontainer+job"}\n)',
        new='OS_ISOLATED_BACKENDS = frozenset(\n    {"linux-namespace+pid", "linux-namespace", "windows-appcontainer+job", "policy-only"}\n)',
        tests=GATE_TESTS,
        covers=('sandbox_backend_not_acceptable',),
    ),
    Mutation(
        name="generated_test_check",
        description="生成 test が落ちていても通す",
        path=GATE,
        old="    if not request.tests_pass:",
        new="    if False:",
        tests=GATE_TESTS,
        covers=('generated_tests_failed',),
    ),
    Mutation(
        name="build_check",
        description="build が落ちていても通す",
        path=GATE,
        old="    if not request.build_pass:",
        new="    if False:",
        tests=GATE_TESTS,
        covers=('build_failed',),
    ),
    Mutation(
        name="runtime_probe_check",
        description="runtime probe が落ちていても通す",
        path=GATE,
        old="    if not request.runtime_probe_pass:",
        new="    if False:",
        tests=GATE_TESTS,
        covers=('runtime_probe_failed',),
    ),
    Mutation(
        name="digest_equality_check",
        description="検証した物と載せる物が違っても通す（TOCTOU）",
        path=GATE,
        old="        if verified != promoted:",
        new="        if False:",
        tests=GATE_TESTS,
        covers=('verified_artifact_mismatch', 'manifest_digest_mismatch'),
    ),
    Mutation(
        name="digest_presence_check",
        description="digest が無くても通す",
        path=GATE,
        old="        if not verified or not promoted:",
        new="        if False:",
        tests=GATE_TESTS,
        covers=('artifact_digest_missing',),
    ),
    Mutation(
        name="prohibited_effect_check",
        description="禁止 Effect を見逃す",
        path=GATE,
        old="    if prohibited:",
        new="    if False:",
        tests=GATE_TESTS + CORPUS_TESTS,
        covers=('prohibited_effect',),
    ),
    Mutation(
        name="undeclared_effect_check",
        description="宣言されていない Effect を許す",
        path=GATE,
        old="    if undeclared:",
        new="    if False:",
        tests=GATE_TESTS,
        covers=('undeclared_effect',),
    ),
    Mutation(
        name="secret_policy_check",
        description="秘密探索を見逃す",
        path=GATE,
        old="    if EffectKind.CREDENTIAL_ACCESS in inspection.effects:",
        new="    if False:",
        tests=GATE_TESTS,
        covers=('secret_policy_violation',),
    ),
    Mutation(
        name="effect_exceeds_permission_check",
        description="宣言 Permission より強い Effect を許す（権限昇格）",
        path=GATE,
        old="        if escalations:",
        new="        if False:",
        tests=GATE_TESTS,
        covers=('effect_exceeds_permission',),
    ),
    Mutation(
        name="unknown_effect_treated_as_safe",
        description="読めなかった生成物を安全扱いする",
        path=GATE,
        old="    if EffectKind.UNKNOWN in inspection.effects:",
        new="    if False:",
        tests=GATE_TESTS + CORPUS_TESTS,
        covers=('effect_unknown',),
    ),
    Mutation(
        name="unparseable_source_treated_as_safe",
        description="構文が壊れた生成 Source を UNKNOWN にしない",
        path=EFFECTS,
        old="                    effect=EffectKind.UNKNOWN,\n                    detail=f\"python source did not parse: {error.msg}\",",
        new="                    effect=EffectKind.FILESYSTEM_READ,\n                    detail=f\"python source did not parse: {error.msg}\",",
        tests=CORPUS_TESTS,
    ),
    Mutation(
        name="unknown_suffix_treated_as_inert",
        description="知らない拡張子を無害扱いする",
        path=EFFECTS,
        old='        if suffix in _INERT_SUFFIXES:\n            continue',
        new='        if True:\n            continue',
        tests=CORPUS_TESTS,
    ),
    Mutation(
        name="static_inspection_required_check",
        description="静的検査が無くても生成 Source を通す",
        path=GATE,
        old="        if request.requires_generated_source:\n            out.append(\n                RejectionDetail(\n                    PromotionRejection.STATIC_INSPECTION_MISSING,",
        new="        if False:\n            out.append(\n                RejectionDetail(\n                    PromotionRejection.STATIC_INSPECTION_MISSING,",
        tests=GATE_TESTS,
        covers=('static_inspection_missing',),
    ),
    Mutation(
        name="dependency_allowlist_check",
        description="allowlist に無い依存を通す",
        path=GATE,
        old="        if verdict.unknown:",
        new="        if False:",
        tests=GATE_TESTS,
        covers=('dependency_not_allowlisted',),
    ),
    Mutation(
        name="dependency_unknown_security_check",
        description="security_status が不明な依存を安全扱いする",
        path=GATE,
        old="        if verdict.rejected_for_unknown_security:",
        new="        if False:",
        tests=GATE_TESTS,
        covers=('dependency_security_unknown',),
    ),
    Mutation(
        name="dependency_acquisition_check",
        description="その場で依存を取りに行く行為を許す",
        path=GATE,
        old="        except DependencyPolicyViolation as error:",
        new="        except (DependencyPolicyViolation,) as error:  # mutated below\n            error = None  # noqa: F841\n        if False:",
        tests=GATE_TESTS,
        covers=('dependency_acquisition_attempt',),
    ),
    Mutation(
        name="unknown_dependency_policy_reject",
        description="UNKNOWN を拒否する Policy を無効化する",
        path=DEPS,
        old="                if unknown_security_policy is UnknownSecurityPolicy.REJECT:",
        new="                if False:",
        tests=GATE_TESTS,
    ),
    Mutation(
        name="decision_required_for_promotion",
        description="Gate の決定なしに PROMOTED にできるようにする",
        path=MANIFEST,
        old="        decision.require_allowed()",
        new="        pass",
        tests=WIRING_TESTS,
    ),
    Mutation(
        name="attestation_required_at_install",
        description="Attestation が無い PROMOTED を受け入れる（fake digest bypass）",
        path=VERIFY,
        old="    if attestation is None:",
        new="    if False:",
        tests=FORGERY_TESTS,
        covers=("attestation_missing",),
    ),
    Mutation(
        name="attestation_digest_binding",
        description="digest と Attestation の不一致を見逃す（Attestation すり替え）",
        path=VERIFY,
        old="    if recomputed != manifest.promotion_decision_digest:",
        new="    if False:",
        tests=FORGERY_TESTS,
        covers=("attestation_digest_mismatch",),
    ),
    Mutation(
        name="attestation_capability_binding",
        description="他 Capability の決定の流用を許す",
        path=VERIFY,
        old="    if attestation.capability_id != manifest.capability_id:",
        new="    if False:",
        tests=FORGERY_TESTS,
        covers=("attestation_capability_mismatch",),
    ),
    Mutation(
        name="manifest_digest_presence_at_install",
        description="Manifest へ束縛されていない Attestation を許す",
        path=VERIFY,
        old="    if not attestation.extension_manifest_digest:",
        new="    if False:",
        tests=FORGERY_TESTS,
        covers=("attestation_manifest_unbound",),
    ),
    Mutation(
        name="manifest_digest_binding_at_install",
        description="検証後の Manifest 書き換えを見逃す（TOCTOU）",
        path=VERIFY,
        old="    if attestation.extension_manifest_digest != expected_manifest_digest:",
        new="    if False:",
        tests=FORGERY_TESTS,
        covers=("attestation_manifest_mismatch",),
    ),
    Mutation(
        name="attestation_reevaluation",
        description="Attestation を再評価せずに信じる（「通ったよ」を信用する）",
        path=VERIFY,
        old="    if not decision.allowed:",
        new="    if False:",
        tests=FORGERY_TESTS,
        covers=("attestation_not_reevaluated",),
    ),
    Mutation(
        name="permission_manifest_reconstruction_check",
        description="Attestation 内の Permission 改変を見逃す（権限昇格）",
        path=GATE,
        old="        if canonical_permission_manifest_digest(manifest) != (\n            attestation.permission_manifest_digest\n        ):",
        new="        if False:",
        tests=FORGERY_TESTS,
        covers=("attestation_permission_tampered",),
    ),
    Mutation(
        name="manifest_digest_presence_in_gate",
        description="manifest digest 欠落のまま Promotion を通す",
        path=GATE,
        old="    if not verified_manifest or not promoted_manifest:",
        new="    if False:",
        tests=GATE_TESTS,
        covers=("artifact_digest_missing",),
    ),
    Mutation(
        name="store_reverifies_on_load",
        description="Store が load 時に再検証しない（SHA を通過証明として信じる）",
        path=STORE,
        old="        verify_promotion_attestation(manifest)",
        new="        pass",
        tests=STORE_TESTS,
        covers=("store_not_reverified",),
    ),
    Mutation(
        name="unknown_security_default_is_reject",
        description="UNKNOWN 依存の既定を緩い側へ戻す",
        path=GATE,
        old="    unknown_security_policy: UnknownSecurityPolicy = UnknownSecurityPolicy.REJECT",
        new="    unknown_security_policy: UnknownSecurityPolicy = UnknownSecurityPolicy.ALLOW_IF_BUNDLED",
        tests=GATE_TESTS,
        covers=("unknown_security_default_relaxed",),
    ),
    Mutation(
        name="registry_calls_the_verifier",
        description="Registry が再検証を呼ばない（Gate 未通過を素通し）",
        path=REGISTRY,
        old="        verify_promotion_attestation(manifest, activation=activation)",
        new="        pass",
        tests=WIRING_TESTS + FORGERY_TESTS,
        covers=("registry_not_reverified",),
    ),
)


def _clear_pycache() -> None:
    """**`.pyc` が残ると壊したはずのコードが効かない**（2026-09-04 に踏んだ）。"""
    for cache in REPO.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run(tests: tuple[str, ...]) -> bool:
    """テストが通れば True。**mutation 後に True なら Guard は置物。**"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def run_mutation(mutation: Mutation) -> tuple[bool, str]:
    path = mutation.file
    original = path.read_text(encoding="utf-8")
    if mutation.old not in original:
        return False, "対象コードが見つからない（Gate の書き換えで陳腐化した）"
    if original.count(mutation.old) != 1:
        return False, f"対象コードが {original.count(mutation.old)} 箇所ある（一意でない）"
    try:
        path.write_text(original.replace(mutation.old, mutation.new, 1), encoding="utf-8")
        _clear_pycache()
        still_green = _run(mutation.tests)
        if still_green:
            return False, "Guard を外してもテストが通った（置物）"
        return True, "検出"
    finally:
        path.write_text(original, encoding="utf-8")
        _clear_pycache()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    selected = [m for m in MUTATIONS if not args.only or m.name == args.only]
    if not selected:
        print(f"no mutation named {args.only!r}", file=sys.stderr)
        return 2

    print(f"Critical Gate mutation: {len(selected)} 件\n")
    failures: list[str] = []
    for mutation in selected:
        detected, note = run_mutation(mutation)
        mark = "PASS" if detected else "FAIL"
        print(f"  [{mark}] {mutation.name:42s} {mutation.description} — {note}")
        if not detected:
            failures.append(f"{mutation.name}: {note}")

    print()
    if failures:
        print(f"検出できなかった Guard が {len(failures)} 件ある:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"全 {len(selected)} 件の Guard が、壊すとテストで落ちる。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
