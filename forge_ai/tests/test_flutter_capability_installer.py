"""**獲得能力を Forge の Flutter アプリへ載せる**ところの不変条件（TD94）。

実際に描けるかどうかは Flutter が要るので `frontend/test_acquired/` が見る。
ここが見るのは installer 側——**どこへ書くか / 何を書かないか / 表を
作り直すか**である。
"""

from __future__ import annotations

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
    FlutterCapabilityInstaller,
    InstallationError,
    capability_slug,
)

HARNESS = frozenset({"capability_test.dart", "probe.dart"})


def _artifact(
    capability_id: str = "view.calendar",
    files: tuple[tuple[str, str], ...] | None = None,
) -> BuildTimeCapabilityArtifact:
    default = (
        ("capability_impl.dart", "int one() => 1;\n"),
        ("capability_test.dart", "void main() {}\n"),
        ("probe.dart", "void main() {}\n"),
        ("flutter/forge_binding.dart", "const capability = 0;\n"),
    )
    return BuildTimeCapabilityArtifact(
        capability_id=capability_id,
        files=tuple(
            BuildTimeSourceFile(path=path, content=content)
            for path, content in (files or default)
        ),
        reusable_contract="再利用可能な実装",
        changed_bindings=("language", "validator", "runtime", "compiler"),
    )


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.frontend = pathlib.Path(tempfile.mkdtemp(prefix="forge-frontend-"))
        (self.frontend / INSTALL_ROOT).mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.frontend, ignore_errors=True)
        self.installer = FlutterCapabilityInstaller(
            frontend_root=self.frontend, harness_files=HARNESS,
        )


class TestWhatLandsInTheApp(_Base):
    def test_the_binding_and_the_implementation_are_installed(self) -> None:
        installed = self.installer.install(_artifact())
        self.assertEqual(
            installed.installed_files,
            (
                "lib/json_ui/acquired/view_calendar/capability_impl.dart",
                "lib/json_ui/acquired/view_calendar/forge_binding.dart",
            ),
        )

    def test_the_isolated_harness_is_not_shipped(self) -> None:
        """**検証の道具は製品ではない。** テストと probe は載せない。"""
        self.installer.install(_artifact())
        directory = self.frontend / INSTALL_ROOT / "view_calendar"
        names = sorted(p.name for p in directory.iterdir())
        self.assertNotIn("capability_test.dart", names)
        self.assertNotIn("probe.dart", names)

    def test_the_slug_is_deterministic(self) -> None:
        self.assertEqual(capability_slug("view.calendar"), "view_calendar")
        self.assertEqual(capability_slug("view.calendar"), capability_slug("view.calendar"))


class TestWhatIsRefused(_Base):
    """**描けないものを載せない。**"""

    def test_an_artifact_without_a_binding_is_refused(self) -> None:
        artifact = _artifact(files=(
            ("capability_impl.dart", "int one() => 1;\n"),
            ("capability_test.dart", "void main() {}\n"),
        ))
        with self.assertRaises(InstallationError):
            self.installer.install(artifact)

    def test_a_path_escaping_the_acquired_root_is_refused(self) -> None:
        """外へ出るパスは載らない。

        実際にはより手前の `artifact.validate()` が落とす。installer 側の
        同じ検査は**多重防御**として残す（`InstallationError` はその親を
        継承しているので、ここでは親で受ける）。
        """
        artifact = _artifact(files=(
            ("capability_impl.dart", "int one() => 1;\n"),
            ("capability_test.dart", "void main() {}\n"),
            ("flutter/../../../forge_binding.dart", "const capability = 0;\n"),
        ))
        with self.assertRaises(BuildTimeExtensionError):
            self.installer.install(artifact)

    def test_writing_never_touches_shipped_source(self) -> None:
        """書き込み先は獲得用の1ディレクトリだけ。"""
        shipped = self.frontend / "lib" / "json_ui" / "schema"
        shipped.mkdir(parents=True)
        guarded = shipped / "forge_document.dart"
        guarded.write_text("// shipped\n", encoding="utf-8")
        self.installer.install(_artifact())
        self.assertEqual(guarded.read_text(encoding="utf-8"), "// shipped\n")


class TestTheRegistrationTableIsRebuilt(_Base):
    """**追記ではなく、丸ごと作り直す。**"""

    def test_an_empty_root_produces_an_empty_table(self) -> None:
        body = self.installer.rewrite_registrations().read_text(encoding="utf-8")
        self.assertIn("void registerAcquiredCapabilities() {", body)
        self.assertNotIn("registerAcquiredCapability(", body)

    def test_an_installed_capability_is_registered(self) -> None:
        self.installer.install(_artifact())
        body = self.installer.rewrite_registrations().read_text(encoding="utf-8")
        self.assertIn("import 'view_calendar/forge_binding.dart' as capability_0;", body)
        self.assertIn("registerAcquiredCapability(capability_0.capability);", body)

    def test_a_removed_capability_disappears_from_the_table(self) -> None:
        """installer を通っていない能力が表に残り続けない。"""
        self.installer.install(_artifact())
        self.installer.rewrite_registrations()
        shutil.rmtree(self.frontend / INSTALL_ROOT / "view_calendar")
        body = self.installer.rewrite_registrations().read_text(encoding="utf-8")
        self.assertNotIn("view_calendar", body)

    def test_two_capabilities_are_ordered_deterministically(self) -> None:
        self.installer.install(_artifact("view.calendar"))
        self.installer.install(_artifact("view.timeline"))
        first = self.installer.rewrite_registrations().read_text(encoding="utf-8")
        second = self.installer.rewrite_registrations().read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertLess(first.index("view_calendar"), first.index("view_timeline"))


if __name__ == "__main__":
    unittest.main()
