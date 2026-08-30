"""**生成した Source が、実際に試験・ビルド・起動確認を通ること**（020E-2）。

このテストは fake builder / fake loader を使わない。
`ManagedBuildWorkspaceRunner` が**実 subprocess** を起動し、生成された
Python を本当に実行する。

---

## このテストが証明すること / しないこと

| | |
|---|---|
| 証明する | 生成された Artifact が実 workspace へ materialize され、実 `unittest` / `compileall` / probe を通り、exact build のみが activation になること |
| 証明する | 試験・ビルド・起動確認のどれか1つでも落ちれば PROMOTED されないこと |
| **証明しない** | **その Source を「Forge（実 Model）が書いた」こと。** ここでは Provider は Test Double であり、実装文字列はテストが与えている |

3つ目は Real Model を動かすまで **UNPROVEN のまま**である。
`docs/evidence/` にもそう書く。
"""

from __future__ import annotations

import pathlib
import sys
import unittest

from forge_ai.core.orchestration.build_time_extension import BuildTimeExtensionError
from forge_ai.core.orchestration.capability_artifact_synthesis import (
    CapabilityArtifactSynthesizer,
    CapabilityImplementationContract,
)
from forge_ai.core.orchestration.extension_manifest import (
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (
    CapabilityImplementationUnavailable,
    SynthesizingBuildTimeImplementer,
    command_plan_for_language,
)
from forge_ai.prompt.prompt_builder import Prompt
from forge_ai.provider.provider_interface import ProviderResponse

_MODULE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "core" / "orchestration" / "synthesizing_build_time_implementer.py"
)

CAPABILITY = "view.calendar"

CONTRACT = CapabilityImplementationContract(
    capability_id=CAPABILITY,
    intent="予定を月ごとの表で見る",
    data_contract=("day: number",),
    host_language="python",
    binding_targets=("language", "validator", "runtime", "compiler"),
)

#: 生成物として扱う実 Python。**実際に実行される。**
_IMPL = '''"""Generated reusable capability implementation."""


def month_cells(days):
    """Group day numbers into week rows without inventing missing days."""
    if not days:
        return []
    rows = []
    current = []
    for day in sorted(int(d) for d in days):
        current.append(day)
        if len(current) == 7:
            rows.append(current)
            current = []
    if current:
        rows.append(current)
    return rows
'''

_TEST = '''import unittest

from capability_impl import month_cells


class MonthCellsTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(month_cells([]), [])

    def test_rows_of_seven(self):
        self.assertEqual(month_cells(range(1, 10)), [[1, 2, 3, 4, 5, 6, 7], [8, 9]])


if __name__ == "__main__":
    unittest.main()
'''

_PROBE = '''from capability_impl import month_cells

rows = month_cells([1, 2, 3])
assert rows == [[1, 2, 3]], rows
print("runtime probe ok")
'''


def _payload(impl: str = _IMPL, test: str = _TEST, probe: str = _PROBE) -> dict:
    return {
        "files": [
            {"path": "capability_impl.py", "content": impl},
            {"path": "capability_impl_test.py", "content": test},
            {"path": "probe.py", "content": probe},
        ],
        "reusable_contract": "月ごとの並びを作る再利用可能な実装",
    }


class _Provider:
    def __init__(self, structured: dict) -> None:
        self.structured = structured

    def complete(self, prompt: Prompt) -> ProviderResponse:
        return ProviderResponse(text="", structured=self.structured)


def _implementer(structured: dict, **kwargs) -> SynthesizingBuildTimeImplementer:  # noqa: ANN003
    return SynthesizingBuildTimeImplementer(
        synthesizer=CapabilityArtifactSynthesizer(provider=_Provider(structured)),
        contract_for=lambda _capability_id: CONTRACT,
        known_source_digests=frozenset(),
        **kwargs,
    )


def _manifest() -> ExtensionManifest:
    return ExtensionManifest(
        capability_id=CAPABILITY,
        label_ja="予定を月で見る",
        route=ExtensionRoute.BUILD_TIME,
        requires_confirmation=False,
    )


@unittest.skipUnless(sys.executable, "python interpreter required for managed build")
class TestGeneratedSourceSurvivesARealBuild(unittest.TestCase):
    """**実 subprocess。** fake builder も fake loader も使わない。"""

    def test_generation_build_probe_and_activation(self) -> None:
        implementer = _implementer(_payload())
        implementation = implementer(_manifest())

        self.assertIs(implementation.manifest.status, ExtensionStatus.PROMOTED)
        self.assertIsNotNone(implementation.activation)
        assert implementation.activation is not None
        self.assertEqual(implementation.activation.capability_id, CAPABILITY)

        execution = implementer.last_execution
        assert execution is not None
        # **3つとも実際に走って通っていること。**
        for kind in ("test", "build", "runtime_probe"):
            with self.subTest(kind=kind):
                self.assertTrue(execution.evidence.passed(kind), kind)
        self.assertTrue(execution.result.build_id)
        self.assertTrue(execution.result.runtime_fingerprint)
        self.assertEqual(execution.result.source_digest, execution.evidence.source_digest)

    def test_the_probe_output_is_real_process_output(self) -> None:
        """**本当にそのコードが動いたことを、出力で確かめる。**"""
        implementer = _implementer(_payload())
        implementer(_manifest())
        execution = implementer.last_execution
        assert execution is not None
        probe = next(c for c in execution.evidence.commands if c.kind == "runtime_probe")
        self.assertIn("runtime probe ok", probe.stdout)


class TestFailedEvidenceBlocksPromotion(unittest.TestCase):
    """**1つでも落ちたら PROMOTED しない。**

    落ちた場合は例外ではなく「昇格していない manifest と activation なし」
    が返る。これは fail-closed として正しい形なので、**返り値の中身**を
    見る（例外の有無ではなく）。
    """

    def _assert_not_promoted(self, implementer) -> None:  # noqa: ANN001
        implementation = implementer(_manifest())
        self.assertIsNot(implementation.manifest.status, ExtensionStatus.PROMOTED)
        self.assertIsNone(
            implementation.activation,
            "証拠が揃っていないのに activation が出ている",
        )
        self.assertTrue(
            implementation.manifest.promotion_blockers(),
            "何が足りないのかが記録されていない",
        )

    def test_a_failing_generated_test_is_not_promoted(self) -> None:
        broken = _TEST.replace("[[1, 2, 3, 4, 5, 6, 7], [8, 9]]", "[[0]]")
        self._assert_not_promoted(_implementer(_payload(test=broken)))

    def test_a_failing_runtime_probe_is_not_promoted(self) -> None:
        self._assert_not_promoted(_implementer(_payload(probe="raise SystemExit(3)\n")))

    def test_source_that_cannot_compile_is_not_promoted(self) -> None:
        self._assert_not_promoted(_implementer(_payload(impl="def broken(:\n")))

    def test_a_failing_phase_stops_later_phases(self) -> None:
        """落ちた後の段を「通った証拠」として数えない。"""
        implementer = _implementer(_payload(impl="def broken(:\n"))
        implementer(_manifest())
        execution = implementer.last_execution
        assert execution is not None
        self.assertFalse(execution.evidence.passed("test"))
        self.assertFalse(
            any(c.kind == "runtime_probe" for c in execution.evidence.commands),
            "試験が落ちた後に runtime_probe まで走っている",
        )


class TestNothingIsClaimedWhenNothingWasGenerated(unittest.TestCase):
    def test_an_unusable_generation_raises_instead_of_promoting(self) -> None:
        implementer = _implementer({})
        with self.assertRaises(CapabilityImplementationUnavailable):
            implementer(_manifest())

    def test_an_unsupported_language_is_refused(self) -> None:
        other = CapabilityImplementationContract(
            capability_id=CAPABILITY, intent="x", data_contract=(),
            host_language="dart",
            binding_targets=("language", "validator", "runtime", "compiler"),
        )
        implementer = SynthesizingBuildTimeImplementer(
            synthesizer=CapabilityArtifactSynthesizer(provider=_Provider(_payload())),
            contract_for=lambda _c: other,
            known_source_digests=frozenset(),
        )
        with self.assertRaises(CapabilityImplementationUnavailable):
            implementer(_manifest())

    def test_the_contract_cannot_change_capability_identity(self) -> None:
        other = CapabilityImplementationContract(
            capability_id="effect.payment", intent="x", data_contract=(),
            host_language="python",
            binding_targets=("language", "validator", "runtime", "compiler"),
        )
        implementer = SynthesizingBuildTimeImplementer(
            synthesizer=CapabilityArtifactSynthesizer(provider=_Provider(_payload())),
            contract_for=lambda _c: other,
            known_source_digests=frozenset(),
        )
        with self.assertRaises(BuildTimeExtensionError):
            implementer(_manifest())


class TestCountsProveNoSecondBuild(unittest.TestCase):
    """2回目の要求で再生成・再 build が**起きていない**ことを数で示すため。"""

    def test_counts_start_at_zero_and_increment_once_per_call(self) -> None:
        implementer = _implementer(_payload())
        self.assertEqual((implementer.synthesis_count, implementer.build_count), (0, 0))
        implementer(_manifest())
        self.assertEqual((implementer.synthesis_count, implementer.build_count), (1, 1))


class TestNoCapabilitySpecificBranch(unittest.TestCase):
    def test_the_module_holds_no_capability_id_literals(self) -> None:
        source = _MODULE.read_text(encoding="utf-8")
        body = source.split('"""')
        executable = "".join(body[i] for i in range(0, len(body), 2))
        for namespace in ("view.", "data.", "effect.", "interact.", "simulate."):
            with self.subTest(namespace=namespace):
                self.assertNotIn(namespace, executable)

    def test_command_plans_are_keyed_by_language_not_capability(self) -> None:
        python_plan = command_plan_for_language("python")
        self.assertEqual({c.kind for c in python_plan}, {"test", "build", "runtime_probe"})
        with self.assertRaises(CapabilityImplementationUnavailable):
            command_plan_for_language("nonexistent-language")


if __name__ == "__main__":
    unittest.main()
