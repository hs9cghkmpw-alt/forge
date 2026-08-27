"""**実行機を固定しない**（020A2 §8）。

020A の書き方は「Claude の container か、別の実機か」だった。これは
**恒久的な実行機がどこかに1台ある**ように読める。実際には、
`docs/MACHINE-INDEPENDENT-POLICY.md` が言うとおり
**その時 Local Model を実行できるPCが、そのセッションの Execution Host**
である。

もう1つ、020A1 は Baseline Benchmark の前提に GPU を入れていた。
CPU で Real Model が動いて実測できるなら Benchmark 自体は有効である。
**GPU を絶対条件にすると、CPU で回せる小型モデルの実測が永久に
取れない。**

文書は人が書き換えるので、型では守れない。**ここで落ちる形にする。**
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_POLICY = _ROOT / "docs" / "MACHINE-INDEPENDENT-POLICY.md"


def _doctor():
    spec = importlib.util.spec_from_file_location(
        "_forge_doctor_policy", _ROOT / "scripts" / "forge_doctor.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestThePolicyDoesNotAssumeAPermanentHost(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _POLICY.read_text(encoding="utf-8")

    def test_the_execution_host_is_decided_per_session(self) -> None:
        self.assertIn(
            "その時 Local Model を実行できるPC",
            self.text,
            "Execution Host が『どのPCか』ではなく『その時動かせるPC』"
            " であることが書かれていない",
        )

    def test_no_machine_is_named_as_the_permanent_host(self) -> None:
        """**特定の1台を常設の実行機として書かない。**"""
        for phrase in ("常設の実機", "専用機を用意", "固定の実行機"):
            self.assertNotIn(
                phrase, self.text, f"『{phrase}』は恒久的な実行機を前提にしている",
            )


class TestBenchmarkDoesNotRequireGpu(unittest.TestCase):
    """**GPU を絶対条件にしない**（020A2 §8）。"""

    def setUp(self) -> None:
        self.doctor = _doctor()

    def _verdict(self, **available: bool) -> dict[str, bool]:
        findings = [
            self.doctor.Finding(name=name, available=value)
            for name, value in available.items()
        ]
        return self.doctor.verdict(findings)

    def test_cpu_only_runtime_can_still_run_the_baseline_benchmark(self) -> None:
        verdict = self._verdict(**{
            "runtime:ollama": True, "runtime:listening": True, "gpu:nvidia": False,
        })
        self.assertTrue(
            verdict["level0_5_baseline"],
            "GPU が無いだけで Baseline Benchmark を不能にしている。"
            " CPU で出た数字も実測である",
        )
        self.assertFalse(verdict["gpu_accelerated"])

    def test_a_gpu_alone_does_not_make_the_benchmark_possible(self) -> None:
        """**逆も倒さない。** Runtime が無ければ GPU があっても測れない。"""
        verdict = self._verdict(**{
            "runtime:ollama": False, "runtime:listening": False, "gpu:nvidia": True,
        })
        self.assertFalse(verdict["level0_5_baseline"])
        self.assertFalse(verdict["level0_local_model"])

    def test_the_policy_says_gpu_is_not_a_precondition(self) -> None:
        text = _POLICY.read_text(encoding="utf-8")
        self.assertIn("GPU は必須ではない", text)

    def test_gpu_is_reported_as_its_own_evidence(self) -> None:
        """GPU を消すのではなく、**別の Evidence** として残すこと。"""
        verdict = self._verdict(**{
            "runtime:ollama": True, "runtime:listening": True, "gpu:nvidia": True,
        })
        self.assertIn("gpu_accelerated", verdict)
        self.assertTrue(verdict["gpu_accelerated"])


if __name__ == "__main__":
    unittest.main()
