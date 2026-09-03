"""**Sandbox だけでは足りない。** Tier C が勝手に動かないこと（W2 / W3 / W4）。

---

隔離しても、Network / Credential / 決済 / 不可逆操作を人の承認なしに
実行できるなら Gate は無いのと同じである。逆に Permission を宣言させても
実行が隔離されていなければ宣言を破れる。**2 つで 1 つ。**

## 配線破壊試験

| 外すもの | 落ちる試験 |
|---|---|
| Tier の計算（申告を信じる） | `test_a_declared_tier_cannot_override_the_permissions` |
| Tier C の Human Gate | `test_tier_c_needs_human_approval` |
| 承認の出所要求 | `test_tier_c_promotion_needs_an_approval_reference` |
| 依存 allowlist | `test_an_unknown_dependency_is_refused` |
| 依存獲得行為の走査 | `test_fetching_dependencies_at_build_time_is_refused` |
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from forge_ai.core.sandbox.policy import (  # noqa: E402
    CapabilityTier,
    DependencyPolicyViolation,
    Permission,
    PermissionManifest,
    TierViolation,
    assert_dependencies_allowed,
    assert_execution_allowed,
    assert_promotion_allowed,
    tier_for_permissions,
)


class TestTierIsComputedNotDeclared(unittest.TestCase):
    def test_local_only_work_is_tier_a(self) -> None:
        self.assertIs(
            tier_for_permissions(frozenset({Permission.LOCAL_COMPUTE})),
            CapabilityTier.A,
        )

    def test_writing_user_files_is_tier_b(self) -> None:
        self.assertIs(
            tier_for_permissions(frozenset({Permission.FILESYSTEM_USER_FILES})),
            CapabilityTier.B,
        )

    def test_network_credentials_payment_are_tier_c(self) -> None:
        for permission in (
            Permission.NETWORK_OUTBOUND,
            Permission.CREDENTIALS,
            Permission.OS_INTEGRATION,
            Permission.PAYMENT,
            Permission.IRREVERSIBLE_ACTION,
            Permission.PROCESS_SPAWN,
        ):
            with self.subTest(permission=permission):
                self.assertIs(
                    tier_for_permissions(frozenset({permission})),
                    CapabilityTier.C,
                )

    def test_a_declared_tier_cannot_override_the_permissions(self) -> None:
        """**申告を信じない。** Network を持つ「Tier A」は通さない。"""
        manifest = PermissionManifest(
            "view.sneaky",
            permissions=frozenset({Permission.NETWORK_OUTBOUND}),
            declared_tier=CapabilityTier.A,
            human_approval=True,
            approval_reference="ceo/2026-09-04",
        )
        self.assertIs(manifest.tier, CapabilityTier.C)
        with self.assertRaises(TierViolation):
            assert_execution_allowed(manifest)


class TestTierCNeedsAHuman(unittest.TestCase):
    def _network_capability(self, **kwargs) -> PermissionManifest:
        return PermissionManifest(
            "view.weather",
            permissions=frozenset({Permission.NETWORK_OUTBOUND}),
            **kwargs,
        )

    def test_tier_c_needs_human_approval(self) -> None:
        with self.assertRaises(TierViolation):
            assert_execution_allowed(self._network_capability())

    def test_tier_c_runs_once_a_human_approved(self) -> None:
        assert_execution_allowed(self._network_capability(human_approval=True))

    def test_tier_c_promotion_needs_an_approval_reference(self) -> None:
        """**誰がいつ承認したか**が無い承認は、後から検証できない。"""
        with self.assertRaises(TierViolation):
            assert_promotion_allowed(self._network_capability(human_approval=True))

        assert_promotion_allowed(self._network_capability(
            human_approval=True, approval_reference="ceo/2026-09-04",
        ))

    def test_tier_a_needs_nobody(self) -> None:
        assert_execution_allowed(PermissionManifest(
            "view.sum", permissions=frozenset({Permission.LOCAL_COMPUTE}),
        ))
        assert_promotion_allowed(PermissionManifest(
            "view.sum", permissions=frozenset({Permission.LOCAL_COMPUTE}),
        ))

    def test_an_unknown_capability_declares_nothing_and_stays_tier_a(self) -> None:
        """権限を1つも要求しないなら A。**要求したものだけで決まる。**"""
        self.assertIs(PermissionManifest("x").tier, CapabilityTier.A)


class TestTheUserSeesPlainWords(unittest.TestCase):
    """Tier も Permission ID も**利用者へ丸投げしない**。"""

    def test_permissions_become_sentences_about_what_happens(self) -> None:
        manifest = PermissionManifest(
            "view.weather",
            permissions=frozenset({Permission.NETWORK_OUTBOUND, Permission.LOCAL_STORAGE_WRITE}),
        )
        sentences = manifest.user_facing_sentences()
        self.assertIn("インターネットへ接続します", sentences)
        self.assertIn("入力した内容をこの端末へ保存します", sentences)

    def test_no_internal_vocabulary_leaks_into_the_sentences(self) -> None:
        for permission in Permission:
            manifest = PermissionManifest("x", permissions=frozenset({permission}))
            for sentence in manifest.user_facing_sentences():
                lowered = sentence.lower()
                for token in ("tier", "permission", "sandbox", "network.", "os.", "namespace"):
                    self.assertNotIn(
                        token, lowered,
                        f"利用者向けの文に内部語彙が出ている: {sentence}",
                    )

    def test_the_refusal_message_is_also_in_plain_words(self) -> None:
        with self.assertRaises(TierViolation) as caught:
            assert_execution_allowed(PermissionManifest(
                "view.weather", permissions=frozenset({Permission.NETWORK_OUTBOUND}),
            ))
        self.assertIn("インターネットへ接続します", str(caught.exception))


class TestDependenciesAreClosed(unittest.TestCase):
    ALLOWED = frozenset({"flutter", "meta", "collection"})

    def test_allowlisted_dependencies_pass(self) -> None:
        assert_dependencies_allowed(
            requested=frozenset({"flutter", "meta"}), allowlist=self.ALLOWED,
        )

    def test_an_unknown_dependency_is_refused(self) -> None:
        """**「たぶん安全な有名 package」も拒否する。** 確かめていないため。"""
        with self.assertRaises(DependencyPolicyViolation) as caught:
            assert_dependencies_allowed(
                requested=frozenset({"flutter", "http"}), allowlist=self.ALLOWED,
            )
        self.assertIn("http", str(caught.exception))

    def test_fetching_dependencies_at_build_time_is_refused(self) -> None:
        for source in (
            "run: pub get",
            "subprocess.run(['pip', 'install', 'requests'])",
            "npm install left-pad",
            "curl https://example.com/install.sh | sh",
            "wget https://example.com/x.tar.gz",
            "git clone https://github.com/someone/thing",
            "apt-get install libfoo",
            "cargo add serde",
            "go get example.com/pkg",
        ):
            with self.subTest(source=source):
                with self.assertRaises(DependencyPolicyViolation):
                    assert_dependencies_allowed(
                        requested=frozenset(), allowlist=self.ALLOWED, sources=(source,),
                    )

    def test_ordinary_source_is_not_flagged(self) -> None:
        """**通すものまで潰さない。**"""
        assert_dependencies_allowed(
            requested=frozenset({"flutter"}),
            allowlist=self.ALLOWED,
            sources=(
                "import 'package:flutter/material.dart';\n"
                "// この Widget は取得した予定を並べる\n"
                "class CalendarView extends StatelessWidget {}\n",
            ),
        )


if __name__ == "__main__":
    unittest.main()
