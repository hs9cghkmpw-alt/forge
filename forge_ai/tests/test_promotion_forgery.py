"""**偽造 PROMOTED Manifest** の拒否（001A / Major 1・2 の追加破壊試験）。

独立レビューの指摘:

> `replace(manifest, status=PROMOTED, promotion_decision_digest="fake")`
> のような Manifest を作れば、Promotion Gate を通らず Registry へ入れられる。
> 「`promoted()` だけが digest を埋める」というコメントは
> Python の dataclass/replace に対する Security Boundary にはならない。

**指摘は正しく、実際に再現した。** ここはその再発防止である。

## 正直な限界

同一プロセス内の任意コードに対する暗号的境界ではない。
`evaluate_promotion` を差し替えられれば何でも通る。Python のプロセス内で
これ以上は作れない。**ここで止まるのは「Gate を通さずに PROMOTED を
名乗る」であり、偽造しようとすると本当に Gate を満たす入力を作る羽目になる。**
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from forge_ai.core.orchestration.extension_manifest import (
    ExtensionEvidence,
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PromotedCapabilityRegistry
from forge_ai.core.orchestration.promotion_verification import (
    PromotionVerificationError,
    verify_promotion_attestation,
)
from forge_ai.tests.promotion_helpers import allowed_decision

CAP = "view.calendar"
OTHER = "view.other"


def _full_evidence() -> ExtensionEvidence:
    return ExtensionEvidence(
        **{name: True for name in ExtensionEvidence.__dataclass_fields__}
    )


def _verified(capability_id: str = CAP) -> ExtensionManifest:
    return ExtensionManifest(
        capability_id=capability_id,
        label_ja="カレンダーで見る",
        route=ExtensionRoute.DECLARATIVE,
        requires_confirmation=False,
        evidence=_full_evidence(),
    ).verified()


def _genuinely_promoted(capability_id: str = CAP) -> ExtensionManifest:
    manifest = _verified(capability_id)
    return manifest.promoted(allowed_decision(capability_id))


class _Activation:
    widget_types = ("calendar_view",)

    def __init__(self, capability_id: str = CAP) -> None:
        self.capability_id = capability_id

    def resolve(self, *args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("a refused promotion must never be activated")


def _install(manifest: ExtensionManifest) -> None:
    PromotedCapabilityRegistry().install(manifest, _Activation(manifest.capability_id))


class TestTheGenuinePathStillWorks(unittest.TestCase):
    """**通る道が残っていること。** 何も通らない Gate は Gate ではない。"""

    def test_a_genuinely_promoted_manifest_installs(self) -> None:
        _install(_genuinely_promoted())

    def test_a_genuine_manifest_passes_standalone_verification(self) -> None:
        verify_promotion_attestation(_genuinely_promoted())


class TestForgedDigestsAreRefused(unittest.TestCase):
    def test_a_literal_fake_digest_is_refused(self) -> None:
        """レビューが指摘した、そのままの攻撃。"""
        forged = replace(
            _verified(),
            status=ExtensionStatus.PROMOTED,
            promotion_decision_digest="fake",
        )
        with self.assertRaises(ValueError) as caught:
            _install(forged)
        self.assertIn("attestation", str(caught.exception))

    def test_a_random_looking_64_hex_digest_is_refused(self) -> None:
        """**それらしい形**なら通る、にしない。"""
        forged = replace(
            _verified(),
            status=ExtensionStatus.PROMOTED,
            promotion_decision_digest=sha256(b"not a real decision").hexdigest(),
        )
        with self.assertRaises(ValueError):
            _install(forged)

    def test_a_digest_that_does_not_match_its_attestation_is_refused(self) -> None:
        """Attestation は本物だが digest だけ差し替えた場合。"""
        genuine = _genuinely_promoted()
        tampered = replace(genuine, promotion_decision_digest="0" * 64)
        with self.assertRaises(ValueError) as caught:
            _install(tampered)
        self.assertIn("does not match its attestation", str(caught.exception))


class TestStolenAndStaleDecisionsAreRefused(unittest.TestCase):
    def test_another_capabilitys_decision_is_refused(self) -> None:
        """他 Capability の決定を流用する。"""
        stolen = _genuinely_promoted(OTHER).promotion_attestation
        forged = replace(
            _verified(CAP),
            status=ExtensionStatus.PROMOTED,
            promotion_attestation=stolen,
            promotion_decision_digest=stolen.digest(),
        )
        with self.assertRaises(ValueError) as caught:
            _install(forged)
        self.assertIn("different capability", str(caught.exception))

    def test_a_denied_decision_cannot_be_smuggled_in(self) -> None:
        """拒否された決定の入力で Attestation を作っても、再評価で落ちる。"""
        genuine = _genuinely_promoted()
        denied = replace(
            genuine.promotion_attestation,
            tests_pass=False,
            requires_generated_source=True,
        )
        forged = replace(
            genuine,
            promotion_attestation=denied,
            promotion_decision_digest=denied.digest(),
        )
        with self.assertRaises(ValueError) as caught:
            _install(forged)
        self.assertIn("re-evaluation", str(caught.exception))

    def test_a_stale_decision_from_an_older_manifest_is_refused(self) -> None:
        """**検証したあとで Manifest を書き換える**（TOCTOU）。"""
        genuine = _genuinely_promoted()
        # 昇格後に確認要否を書き換える（＝別の Manifest になる）
        stale = replace(genuine, requires_confirmation=True)
        with self.assertRaises(ValueError) as caught:
            _install(stale)
        self.assertIn("manifest changed after it was verified", str(caught.exception))

    def test_changing_the_route_after_promotion_is_refused(self) -> None:
        genuine = _genuinely_promoted()
        swapped = replace(genuine, route=ExtensionRoute.BUILD_TIME)
        with self.assertRaises(ValueError):
            _install(swapped)

    def test_downgrading_the_evidence_after_promotion_is_refused(self) -> None:
        genuine = _genuinely_promoted()
        weakened = replace(
            genuine, evidence=replace(genuine.evidence, sandbox_preflight=False)
        )
        with self.assertRaises(ValueError):
            _install(weakened)


class TestTamperedPermissionsAreRefused(unittest.TestCase):
    def test_adding_permissions_after_promotion_is_refused(self) -> None:
        """**権限昇格。** 承認済みの決定に権限を足す。"""
        genuine = _genuinely_promoted()
        escalated = replace(
            genuine.promotion_attestation,
            permissions=("local.compute", "network.outbound"),
        )
        forged = replace(
            genuine,
            promotion_attestation=escalated,
            promotion_decision_digest=escalated.digest(),
        )
        with self.assertRaises(ValueError) as caught:
            _install(forged)
        # 再構成した Permission Manifest の digest が合わなくなるので、
        # 再評価が `permission_manifest_invalid` で落ちる。
        self.assertIn("permission_manifest_invalid", str(caught.exception))

    def test_forging_human_approval_is_refused(self) -> None:
        genuine = _genuinely_promoted()
        approved = replace(
            genuine.promotion_attestation,
            human_approval=True,
            approval_reference="なりすまし承認",
        )
        forged = replace(
            genuine,
            promotion_attestation=approved,
            promotion_decision_digest=approved.digest(),
        )
        with self.assertRaises(ValueError):
            _install(forged)

    def test_changing_approval_provenance_is_refused(self) -> None:
        """承認の**出所**だけ書き換える。"""
        genuine = _genuinely_promoted()
        rewritten = replace(
            genuine.promotion_attestation, approval_reference="別の承認番号"
        )
        forged = replace(
            genuine,
            promotion_attestation=rewritten,
            promotion_decision_digest=rewritten.digest(),
        )
        with self.assertRaises(ValueError):
            _install(forged)


class TestTamperedDependencyIdentityIsRefused(unittest.TestCase):
    def test_swapping_in_an_unlisted_dependency_is_refused(self) -> None:
        genuine = _genuinely_promoted()
        swapped = replace(
            genuine.promotion_attestation,
            observed_imports=("package:evil/evil.dart",),
        )
        forged = replace(
            genuine,
            promotion_attestation=swapped,
            promotion_decision_digest=swapped.digest(),
        )
        with self.assertRaises(ValueError) as caught:
            _install(forged)
        self.assertIn("re-evaluation", str(caught.exception))

    def test_hiding_a_dangerous_effect_does_not_help(self) -> None:
        """観測 Effect を消しても、消したこと自体は通過理由にならない。

        （消せば通るのは事実である——だから**静的検査の結果を後から
        書き換えられる状況を作らない**ことが本質であり、ここでは
        「Effect を足したら落ちる」向きを固定する。）
        """
        genuine = _genuinely_promoted()
        dangerous = replace(
            genuine.promotion_attestation, observed_effects=("shell",)
        )
        forged = replace(
            genuine,
            promotion_attestation=dangerous,
            promotion_decision_digest=dangerous.digest(),
        )
        with self.assertRaises(ValueError):
            _install(forged)


class TestTheStoreKeepsTheSameGuarantee(unittest.TestCase):
    """**Store の SHA256 は改ざん検知であって、Gate 通過の証明ではない。**

    したがって「SHA を正しく計算し直した改ざん」は SHA では捕まらない。
    捕まえるのは load 時の**再検証**である。
    """

    def _round_trip(self, mutate) -> None:
        from forge_ai.core.orchestration.declarative_extension import (
            DeclarativeCapabilityArtifact,
            DeclarativePrimitiveRef,
        )
        from forge_ai.core.orchestration.extension_store import (
            ExtensionStoreError,
            _digest,
            load_promoted_declarative_extension,
            save_promoted_declarative_extension,
        )

        artifact = DeclarativeCapabilityArtifact(
            capability_id=CAP,
            primitives=(
                DeclarativePrimitiveRef(
                    kind="view",
                    primitive_id="section_header",
                    config={"role": "calendar"},
                ),
            ),
            reusable_contract="Reusable calendar affordance from loaded primitives.",
            language_fragment={
                "op": "append_widget",
                "widget": {
                    "type": "section_header",
                    "id": "promoted_calendar",
                    "properties": {"title": "カレンダー"},
                },
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.json"
            save_promoted_declarative_extension(
                path, _genuinely_promoted(), artifact
            )
            # 素直に読めることをまず確かめる（通る道が残っていること）。
            load_promoted_declarative_extension(path)

            envelope = json.loads(path.read_text(encoding="utf-8"))
            mutate(envelope["payload"])
            # **改ざん検知 digest は正しく計算し直す。**
            envelope["sha256"] = _digest(envelope["payload"])
            path.write_text(json.dumps(envelope), encoding="utf-8")

            with self.assertRaises(ExtensionStoreError) as caught:
                load_promoted_declarative_extension(path)
            self.assertIn("re-verification", str(caught.exception))

    def test_a_forged_digest_with_a_recomputed_envelope_sha_is_refused(self) -> None:
        def mutate(payload):
            payload["manifest"]["promotion_decision_digest"] = sha256(
                b"forged"
            ).hexdigest()

        self._round_trip(mutate)

    def test_a_stripped_attestation_is_refused_on_load(self) -> None:
        def mutate(payload):
            payload["manifest"]["promotion_attestation"] = None

        self._round_trip(mutate)

    def test_permissions_escalated_inside_the_stored_attestation_are_refused(
        self,
    ) -> None:
        def mutate(payload):
            attestation = payload["manifest"]["promotion_attestation"]
            attestation["permissions"] = ["local.compute", "network.outbound"]

        self._round_trip(mutate)

    def test_a_stored_manifest_edited_after_saving_is_refused(self) -> None:
        """保存後に Manifest を書き換える（TOCTOU の永続版）。"""

        def mutate(payload):
            payload["manifest"]["requires_confirmation"] = True

        self._round_trip(mutate)


class TestTheAttestationMustBeBoundToAManifest(unittest.TestCase):
    def test_an_unbound_attestation_is_refused(self) -> None:
        """`extension_manifest_digest` が空の Attestation を受け入れない。"""
        genuine = _genuinely_promoted()
        unbound = replace(genuine.promotion_attestation, extension_manifest_digest="")
        forged = replace(
            genuine,
            promotion_attestation=unbound,
            promotion_decision_digest=unbound.digest(),
        )
        with self.assertRaises(PromotionVerificationError) as caught:
            verify_promotion_attestation(forged)
        self.assertIn("not bound to any manifest digest", str(caught.exception))

    def test_binding_to_an_empty_digest_is_refused_at_the_source(self) -> None:
        """`bound_to_manifest("")` そのものを拒否する。"""
        genuine = _genuinely_promoted()
        with self.assertRaises(ValueError):
            genuine.promotion_attestation.bound_to_manifest("")


class TestVerificationIsUsedByBothCallers(unittest.TestCase):
    """**同じ検査を 2 箇所に書かない。** ずれるからである。"""

    def test_registry_and_store_share_one_verifier(self) -> None:
        import inspect

        from forge_ai.core.orchestration import extension_registry, extension_store

        for module in (extension_registry, extension_store):
            source = inspect.getsource(module)
            self.assertIn(
                "verify_promotion_attestation",
                source,
                f"{module.__name__} が共通の再検証を呼んでいない",
            )


if __name__ == "__main__":
    unittest.main()
