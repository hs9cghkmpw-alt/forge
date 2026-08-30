"""自然言語の未知要求 → 実 build で獲得 → 原要求 retry → 別要求で再利用（020E-4）。

fake builder / fake loader を使わない。`ManagedBuildWorkspaceRunner` が
**実 subprocess** を起動し、生成された Python を本当に試験・ビルド・実行する。
Capability Plan も retry も**本番の関数**である。

---

## 何を証明し、何を証明しないか

| | |
|---|---|
| 証明する | 獲得前は MISSING であること |
| 証明する | 実 test / 実 build / 実 runtime_probe を通ったものだけが PROMOTED になること |
| 証明する | PROMOTED 後、**原要求を retry すると gap が消える**こと（`capability_plan` が Registry を見る本番経路） |
| 証明する | **別の**自然言語要求で再利用され、**2度目の生成も build も起きない**こと |
| **証明しない** | **その Source を実 Model が書いたこと。** ここでは Provider は Test Double である |
| **証明しない** | 生成 Document の Validator / Flutter runtime 描画 |

4つ目までが本物なので、残る1点（実 Model）が次のボトルネックである。

## なぜ view.map で証明しないのか

`view.map` の実装は既に repo にある。既存コードを PROMOTED にしても
「Forge が能力を作った」ことにならない
（`docs/reports/FORGE-020E-CAPABILITY-ARTIFACT-SYNTHESIS-report.md` §0）。

静的実装が無い `view.calendar` を使う。専用テンプレートは作っていない
——capability 専用分岐は静的テストで禁止済みである。
"""

from __future__ import annotations

import unittest

from forge_ai.core.orchestration.capability_artifact_synthesis import (
    CapabilityArtifactSynthesizer,
    CapabilityImplementationContract,
)
from forge_ai.core.orchestration.extension_plan import (
    ExtensionRoute,
    plan_extension_candidates,
)
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (
    SynthesizingBuildTimeImplementer,
)
from forge_ai.core.semantics.capability_plan import plan_capabilities
from forge_ai.prompt.prompt_builder import Prompt
from forge_ai.provider.provider_interface import ProviderResponse

TARGET = "view.calendar"

#: 最初の未知要求。
FIRST_REQUEST = "通院した日をカレンダーで確認したい"
#: **別の**自然言語要求。同じ能力を要るが、文も題材も違う。
SECOND_REQUEST = "会議の予定を登録してカレンダーで見たい"

_IMPL = '''"""Generated reusable capability implementation."""


def month_cells(days):
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
    def test_rows_of_seven(self):
        self.assertEqual(month_cells(range(1, 10)), [[1, 2, 3, 4, 5, 6, 7], [8, 9]])


if __name__ == "__main__":
    unittest.main()
'''

_PROBE = '''from capability_impl import month_cells

assert month_cells([1, 2, 3]) == [[1, 2, 3]]
print("runtime probe ok")
'''


class _Provider:
    """**Test Double。** 実 Model ではない——ここが未証明点である。"""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt: Prompt) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(text="", structured={
            "files": [
                {"path": "capability_impl.py", "content": _IMPL},
                {"path": "capability_impl_test.py", "content": _TEST},
                {"path": "probe.py", "content": _PROBE},
            ],
            "reusable_contract": "月ごとの並びを作る再利用可能な実装",
        })


def _contract(capability_id: str) -> CapabilityImplementationContract:
    """**Catalog から機械的に引く。** 能力ごとの表を持たない。"""
    from forge_ai.core.semantics.capabilities import SEMANTIC_CAPABILITIES

    definition = SEMANTIC_CAPABILITIES[capability_id]
    return CapabilityImplementationContract(
        capability_id=capability_id,
        intent=definition.intent,
        data_contract=tuple(definition.required_fields),
        host_language="python",
        binding_targets=("language", "validator", "runtime", "compiler"),
    )


class SelfExtensionEndToEndTest(unittest.TestCase):
    def setUp(self) -> None:
        PROMOTED_CAPABILITIES.clear()
        self.addCleanup(PROMOTED_CAPABILITIES.clear)
        self.provider = _Provider()
        self.implementer = SynthesizingBuildTimeImplementer(
            synthesizer=CapabilityArtifactSynthesizer(provider=self.provider),
            contract_for=_contract,
            known_source_digests=frozenset(),
        )

    # ---- 1. BEFORE ACQUISITION ----------------------------------------

    def test_the_capability_is_missing_before_acquisition(self) -> None:
        plan = plan_capabilities(FIRST_REQUEST)
        self.assertIn(TARGET, plan.missing)
        self.assertNotIn(TARGET, plan.views)
        self.assertFalse(PROMOTED_CAPABILITIES.is_promoted(TARGET))

    # ---- 2/3. ACQUISITION and PROMOTION -------------------------------

    def _acquire(self):  # noqa: ANN202
        candidate = plan_extension_candidates((TARGET,))[0]
        self.assertIn(ExtensionRoute.BUILD_TIME, candidate.routes)
        from forge_ai.core.orchestration.extension_manifest import (
            create_extension_manifest,
        )

        manifest = create_extension_manifest(candidate, route=ExtensionRoute.BUILD_TIME)
        implementation = self.implementer(manifest)
        PROMOTED_CAPABILITIES.install(
            implementation.manifest, implementation.activation,
        )
        return implementation

    def test_acquisition_uses_real_build_evidence(self) -> None:
        implementation = self._acquire()
        execution = self.implementer.last_execution
        assert execution is not None

        for kind in ("test", "build", "runtime_probe"):
            with self.subTest(kind=kind):
                self.assertTrue(execution.evidence.passed(kind))
        probe = next(
            c for c in execution.evidence.commands if c.kind == "runtime_probe"
        )
        self.assertIn("runtime probe ok", probe.stdout)

        self.assertEqual(implementation.manifest.promotion_blockers(), ())
        assert implementation.activation is not None
        self.assertTrue(implementation.activation.loaded)
        self.assertEqual(
            implementation.activation.source_digest, execution.result.source_digest,
        )
        self.assertEqual(
            implementation.activation.runtime_fingerprint,
            execution.result.runtime_fingerprint,
        )

    # ---- 4. RETRY THE ORIGINAL REQUEST --------------------------------

    def test_retrying_the_original_request_no_longer_reports_the_gap(self) -> None:
        """**本番の Capability Plan が Registry を見る。** ここは偽装ではない。"""
        self.assertIn(TARGET, plan_capabilities(FIRST_REQUEST).missing)
        self._acquire()
        retried = plan_capabilities(FIRST_REQUEST)
        self.assertNotIn(
            TARGET, retried.missing,
            "獲得したのに、同じ gap が retry 後も残っている",
        )
        self.assertIn(TARGET, retried.views, "獲得した能力が使われていない")

    # ---- 6. REUSE ON A DIFFERENT REQUEST ------------------------------

    def test_a_second_different_request_reuses_without_rebuilding(self) -> None:
        self._acquire()
        synthesis_after_first = self.implementer.synthesis_count
        build_after_first = self.implementer.build_count
        provider_calls_after_first = self.provider.calls
        self.assertEqual((synthesis_after_first, build_after_first), (1, 1))

        second = plan_capabilities(SECOND_REQUEST)
        self.assertNotIn(TARGET, second.missing)
        self.assertIn(TARGET, second.views)

        # **2度目の生成も build も起きていないこと。**
        self.assertEqual(self.implementer.synthesis_count, synthesis_after_first)
        self.assertEqual(self.implementer.build_count, build_after_first)
        self.assertEqual(self.provider.calls, provider_calls_after_first)

    def test_the_two_requests_are_actually_different(self) -> None:
        """同じ文を2回入れて「再利用した」と言わないための確認。"""
        self.assertNotEqual(FIRST_REQUEST, SECOND_REQUEST)
        self.assertIn(TARGET, plan_capabilities(SECOND_REQUEST).missing)


class SelfExtensionNegativeProofTest(unittest.TestCase):
    """**落ちるべきものが落ちること。**"""

    def setUp(self) -> None:
        PROMOTED_CAPABILITIES.clear()
        self.addCleanup(PROMOTED_CAPABILITIES.clear)

    def _implementer_with(self, probe: str) -> SynthesizingBuildTimeImplementer:
        class _Broken(_Provider):
            def complete(self, prompt: Prompt) -> ProviderResponse:
                self.calls += 1
                return ProviderResponse(text="", structured={
                    "files": [
                        {"path": "capability_impl.py", "content": _IMPL},
                        {"path": "capability_impl_test.py", "content": _TEST},
                        {"path": "probe.py", "content": probe},
                    ],
                    "reusable_contract": "x",
                })

        return SynthesizingBuildTimeImplementer(
            synthesizer=CapabilityArtifactSynthesizer(provider=_Broken()),
            contract_for=_contract,
            known_source_digests=frozenset(),
        )

    def test_a_failing_runtime_probe_leaves_the_gap_open(self) -> None:
        from forge_ai.core.orchestration.extension_manifest import (
            create_extension_manifest,
        )

        implementer = self._implementer_with("raise SystemExit(1)\n")
        candidate = plan_extension_candidates((TARGET,))[0]
        manifest = create_extension_manifest(candidate, route=ExtensionRoute.BUILD_TIME)
        implementation = implementer(manifest)

        self.assertIsNone(implementation.activation)
        with self.assertRaises(ValueError):
            PROMOTED_CAPABILITIES.install(
                implementation.manifest, implementation.activation,
            )
        # **獲得できていないので、gap はそのまま残る。**
        self.assertIn(TARGET, plan_capabilities(FIRST_REQUEST).missing)

    def test_requested_alone_never_counts_as_promoted(self) -> None:
        """requested と PROMOTED を混同しない（`6da20fc` の境界）。"""
        plan = plan_capabilities(FIRST_REQUEST)
        self.assertIn(TARGET, plan.requested)
        self.assertFalse(PROMOTED_CAPABILITIES.is_promoted(TARGET))
        self.assertIn(TARGET, plan.missing)


if __name__ == "__main__":
    unittest.main()
