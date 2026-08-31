"""**検査したものと動くものが同じであること**、そして
**持っている能力を作り直さないこと**（方式B）。

---

## 守っているもの

| | |
|---|---|
| 検査 → 組み込みの間で1byteでも変われば拒否 | 証拠の鎖を切らない |
| 別の生成物へ差し替えたら拒否 | 「検査したもの」のすり替えを防ぐ |
| 載せたあとに書き換えられたら検出 | 「Flutter 側だけ直す」抜け道を塞ぐ |
| 保存先名の衝突を検出 | 古いコードが混ざるのを防ぐ |
| 古いファイルを残さない | 同上 |
| 既存能力があるのに再生成したら失敗 | 方式Bの本線 |
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from forge_ai.core.orchestration.build_time_extension import (  # noqa: E402
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
    BuildTimeSourceFile,
)
from forge_ai.core.orchestration.flutter_capability_installer import (  # noqa: E402
    INSTALL_ROOT,
    PROVENANCE_FILE,
    FlutterCapabilityInstaller,
    InstallationError,
    verify_installed_capability,
)
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (  # noqa: E402
    VerifiedCapabilityArtifact,
)

HARNESS = frozenset({"capability_test.dart", "probe.dart"})


def _artifact(
    capability_id: str = "view.calendar",
    impl: str = "int one() => 1;\n",
) -> BuildTimeCapabilityArtifact:
    return BuildTimeCapabilityArtifact(
        capability_id=capability_id,
        files=(
            BuildTimeSourceFile(path="capability_impl.dart", content=impl),
            BuildTimeSourceFile(path="capability_test.dart", content="void main() {}\n"),
            BuildTimeSourceFile(path="probe.dart", content="void main() {}\n"),
            BuildTimeSourceFile(
                path="flutter/forge_binding.dart", content="const capability = 0;\n",
            ),
        ),
        reusable_contract="再利用可能な実装",
        changed_bindings=("language", "validator", "runtime", "compiler"),
    )


def _verified(artifact: BuildTimeCapabilityArtifact) -> VerifiedCapabilityArtifact:
    return VerifiedCapabilityArtifact(
        artifact=artifact,
        source_digest=artifact.source_digest,
        build_id="build-abc",
        runtime_fingerprint="fp-abc",
    )


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.frontend = pathlib.Path(tempfile.mkdtemp(prefix="forge-frontend-"))
        (self.frontend / INSTALL_ROOT).mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.frontend, ignore_errors=True)
        self.installer = FlutterCapabilityInstaller(
            frontend_root=self.frontend, harness_files=HARNESS,
        )


class TestTheInspectedArtifactIsTheInstalledOne(_Base):
    """**検査したものと動くものを同じにする。**"""

    def test_the_verified_artifact_installs(self) -> None:
        installed = self.installer.install(_verified(_artifact()))
        self.assertEqual(
            verify_installed_capability(self.frontend, "view_calendar"),
            installed.source_digest,
        )

    def test_one_changed_character_after_inspection_is_refused(self) -> None:
        """検査のあと 1 文字でも変われば載せない。"""
        verified = _verified(_artifact())
        tampered = VerifiedCapabilityArtifact(
            artifact=_artifact(impl="int one() => 2;\n"),  # ← 1 文字違う
            source_digest=verified.source_digest,
            build_id=verified.build_id,
            runtime_fingerprint=verified.runtime_fingerprint,
        )
        with self.assertRaises(BuildTimeExtensionError):
            self.installer.install(tampered)

    def test_swapping_in_a_different_artifact_is_refused(self) -> None:
        """別の生成物へのすり替えを通さない。"""
        other = _artifact(impl="int two() => 2;\nint three() => 3;\n")
        swapped = VerifiedCapabilityArtifact(
            artifact=other,
            source_digest=_artifact().source_digest,  # ← 検査したのは別物
            build_id="build-abc",
            runtime_fingerprint="fp-abc",
        )
        with self.assertRaises(BuildTimeExtensionError):
            self.installer.install(swapped)

    def test_editing_the_installed_flutter_side_is_detected(self) -> None:
        """**「Flutter 側だけ直す」抜け道を塞ぐ。**"""
        self.installer.install(_verified(_artifact()))
        binding = (
            self.frontend / INSTALL_ROOT / "view_calendar" / "forge_binding.dart"
        )
        binding.write_text("const capability = 1;\n", encoding="utf-8")
        with self.assertRaises(InstallationError):
            verify_installed_capability(self.frontend, "view_calendar")

    def test_adding_a_file_after_install_is_detected(self) -> None:
        self.installer.install(_verified(_artifact()))
        extra = self.frontend / INSTALL_ROOT / "view_calendar" / "extra.dart"
        extra.write_text("// smuggled\n", encoding="utf-8")
        with self.assertRaises(InstallationError):
            verify_installed_capability(self.frontend, "view_calendar")


class TestEvidenceMustDescribeTheArtifact(unittest.TestCase):
    """**証拠が別のものを指していたら渡さない。**

    この不変条件は `implement_build_time_extension()` が持っている。
    `SynthesizingBuildTimeImplementer` 側に同じ検査を重ねてみたが、
    **到達しないコード**だったので置いていない（配線破壊試験で分かった。
    外しても何も落ちないものは、コードでも置物である）。

    ここでは、辻褄の合った嘘をつく runner を注入して、その1枚の検査が
    実際に効いていることを確かめる。
    """

    def test_a_mismatched_evidence_digest_refuses_to_hand_out_the_artifact(self) -> None:
        from forge_ai.core.orchestration.build_time_workspace import (
            BuildTimeBuildResult,
            CommandEvidence,
            ManagedBuildEvidence,
            ManagedBuildExecution,
        )
        from forge_ai.core.orchestration.capability_artifact_synthesis import (
            CapabilityArtifactSynthesizer,
            CapabilityImplementationContract,
        )
        from forge_ai.core.orchestration.extension_manifest import ExtensionManifest
        from forge_ai.core.orchestration.extension_plan import ExtensionRoute
        from forge_ai.core.orchestration.synthesizing_build_time_implementer import (
            SynthesizingBuildTimeImplementer,
        )
        from forge_ai.provider.provider_interface import ProviderResponse

        payload = {
            "files": [
                {"path": "capability_impl.dart", "content": "int one() => 1;\n"},
                {"path": "capability_test.dart", "content": "void main() {}\n"},
                {"path": "probe.dart", "content": "void main() {}\n"},
                {"path": "flutter/forge_binding.dart", "content": "const capability = 0;\n"},
            ],
            "reusable_contract": "再利用可能な実装",
        }

        class _Provider:
            def complete(self, prompt):  # noqa: ANN001, ANN202
                return ProviderResponse(text="", structured=payload)

        def _ok(kind: str) -> CommandEvidence:
            return CommandEvidence(
                kind=kind, argv=("true",), exit_code=0, timed_out=False,
                stdout="", stderr="",
            )

        class _LyingRunner:
            """**辻褄は合っているが、別のものを指す証拠**を返す runner。

            result と evidence が食い違うだけなら下の層が捕まえる。
            ここで試すのは、その2つが**互いに一致したまま artifact とは
            別のものを指している**場合である——下の層は素通しする。
            """

            def run(self, artifact, commands):  # noqa: ANN001, ANN202
                commands = tuple(commands)
                lie = "0" * 64
                evidence = ManagedBuildEvidence(
                    build_id="build-lie",
                    workspace_digest=lie,
                    source_digest=lie,  # ← artifact のものではない
                    runtime_fingerprint="fp-lie",
                    commands=tuple(_ok(c.kind) for c in commands),
                )
                return ManagedBuildExecution(
                    result=BuildTimeBuildResult(
                        build_id="build-lie",
                        source_digest=lie,
                        runtime_fingerprint="fp-lie",
                        tests_pass=True, build_pass=True,
                        runtime_evidence=True, safety_review=True,
                    ),
                    evidence=evidence,
                )

        implementer = SynthesizingBuildTimeImplementer(
            synthesizer=CapabilityArtifactSynthesizer(provider=_Provider()),
            contract_for=lambda cid: CapabilityImplementationContract(
                capability_id=cid, intent="月ごとに見る", data_contract=("date",),
                host_language="dart",
                binding_targets=("language", "validator", "runtime", "compiler"),
            ),
            known_source_digests=frozenset(),
            runner=_LyingRunner(),
        )
        manifest = ExtensionManifest(
            capability_id="view.calendar", label_ja="カレンダーで見る",
            route=ExtensionRoute.BUILD_TIME, requires_confirmation=False,
        )
        with self.assertRaises(BuildTimeExtensionError):
            implementer(manifest)
        self.assertIsNone(implementer.last_verified)


class TestTheInstallLocationIsNotShared(_Base):
    """**保存先名の衝突と、古いファイルの残留。**"""

    def test_a_slug_collision_between_capabilities_is_detected(self) -> None:
        self.installer.install(_verified(_artifact("view.calendar")))
        # 別の能力 id だが同じ slug になる形。
        record = self.frontend / INSTALL_ROOT / "view_calendar" / PROVENANCE_FILE
        provenance = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(provenance["capability_id"], "view.calendar")
        with self.assertRaises(InstallationError):
            self.installer.install(_verified(_artifact("view-calendar")))

    def test_a_directory_with_unknown_files_is_not_mixed_into(self) -> None:
        stray = self.frontend / INSTALL_ROOT / "view_calendar"
        stray.mkdir(parents=True)
        (stray / "leftover.dart").write_text("// old\n", encoding="utf-8")
        with self.assertRaises(InstallationError):
            self.installer.install(_verified(_artifact()))

    def test_reinstalling_removes_files_the_new_artifact_does_not_have(self) -> None:
        """**古い生成物を残さない。**"""
        self.installer.install(_verified(_artifact()))
        directory = self.frontend / INSTALL_ROOT / "view_calendar"
        stale = directory / "capability_impl.dart"
        self.assertTrue(stale.is_file())

        smaller = BuildTimeCapabilityArtifact(
            capability_id="view.calendar",
            files=(
                BuildTimeSourceFile(path="capability_test.dart", content="void main() {}\n"),
                BuildTimeSourceFile(
                    path="flutter/forge_binding.dart", content="const capability = 9;\n",
                ),
            ),
            reusable_contract="再利用可能な実装",
            changed_bindings=("language", "validator", "runtime", "compiler"),
        )
        self.installer.install(_verified(smaller))
        self.assertFalse(
            stale.is_file(), "前回の生成物が残っている（古いコードが混ざる）",
        )
        verify_installed_capability(self.frontend, "view_calendar")


if __name__ == "__main__":
    unittest.main()
