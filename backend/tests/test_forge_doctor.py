"""`scripts/forge_doctor.py` が**読むだけ**であること（FORGE-020A1）。

環境変数を触る script なので、秘密の漏れ方を型ではなく**テストで**
固定する（`CLAUDE.md` §4: 値も長さも先頭数文字も出さない）。
"""

from __future__ import annotations

import importlib.util
import io
import contextlib
import os
import pathlib
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: 実在しそうで、絶対に出力へ現れてはならない値。
_FAKE_SECRET = "zzz-not-a-real-key-9f3a7c1e"


def _load():
    import sys

    spec = importlib.util.spec_from_file_location(
        "_forge_doctor", _ROOT / "scripts" / "forge_doctor.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # **`sys.modules` へ入れてから exec する。** `@dataclass` は
    # `sys.modules[cls.__module__]` を引くので、入れないと解決に失敗する。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestForgeDoctorNeverLeaksSecrets(unittest.TestCase):
    def setUp(self) -> None:
        self.doctor = _load()

    def test_no_part_of_a_secret_reaches_the_output(self) -> None:
        import sys

        os.environ["GEMINI_API_KEY"] = _FAKE_SECRET
        argv = sys.argv
        try:
            sys.argv = ["forge_doctor.py"]
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.doctor.main()
            output = buffer.getvalue()
        finally:
            sys.argv = argv
            os.environ.pop("GEMINI_API_KEY", None)

        self.assertNotIn(_FAKE_SECRET, output)
        # **先頭数文字も出さない。**
        self.assertNotIn(_FAKE_SECRET[:6], output)
        # **長さも出さない。**
        self.assertNotIn(str(len(_FAKE_SECRET)), output.split("python")[0])
        # 「設定されている」ことだけは言ってよい。
        self.assertIn("GEMINI_API_KEY", output)
        self.assertIn("設定あり", output)

    def test_the_json_form_also_hides_the_value(self) -> None:
        import json
        import sys

        os.environ["OPENAI_API_KEY"] = _FAKE_SECRET
        argv = sys.argv
        try:
            sys.argv = ["forge_doctor.py", "--json"]
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.doctor.main()
            payload = json.loads(buffer.getvalue())
        finally:
            sys.argv = argv
            os.environ.pop("OPENAI_API_KEY", None)

        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(_FAKE_SECRET, rendered)
        self.assertNotIn(_FAKE_SECRET[:6], rendered)


class TestForgeDoctorChangesNothing(unittest.TestCase):
    """**インストールしない。設定を書き換えない。**"""

    def setUp(self) -> None:
        self.doctor = _load()

    def test_the_environment_is_unchanged(self) -> None:
        import sys

        before = dict(os.environ)
        argv = sys.argv
        try:
            sys.argv = ["forge_doctor.py"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.doctor.main()
        finally:
            sys.argv = argv
        self.assertEqual(dict(os.environ), before)

    def test_the_source_never_installs_anything(self) -> None:
        """静的検査。**実行して確かめられないものは読んで確かめる。**"""
        source = (_ROOT / "scripts" / "forge_doctor.py").read_text(encoding="utf-8")
        for forbidden in ("pip install", "apt-get", "brew install", "os.environ["):
            with self.subTest(forbidden=forbidden):
                if forbidden == "os.environ[":
                    # 読み取り（`.get`）は許すが、代入は許さない。
                    self.assertNotIn("os.environ[", source.replace("os.environ.get", ""))
                else:
                    self.assertNotIn(forbidden, source)


class TestForgeDoctorReportsWhatThisMachineCanDo(unittest.TestCase):
    def setUp(self) -> None:
        self.doctor = _load()

    def test_every_capability_has_a_verdict(self) -> None:
        can = self.doctor.verdict(self.doctor.collect())
        for key in (
            "backend_and_forge_ai_tests", "renderer_tests", "quality_gate_visual",
            "github_sync", "model_download", "level0_local_model", "level0_5_baseline",
        ):
            self.assertIn(key, can)
            self.assertIsInstance(can[key], bool)

    def test_level0_requires_a_running_runtime(self) -> None:
        """**Runtime が無いのに「可」と言わない。**"""
        findings = [
            f for f in self.doctor.collect()
            if not f.name.startswith(("runtime", "gpu"))
        ]
        self.assertFalse(self.doctor.verdict(findings)["level0_local_model"])


if __name__ == "__main__":
    unittest.main()
