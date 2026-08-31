"""**持っている能力なら作り直さない**（方式B の本線）。

---

固定文は使わない。**ランダムな自由文**を seed から作って投げる。
seed はテストが表示するので、落ちたら同じ試験を再実行できる
（`FORGE_E2E_SEED` で固定する）。

数えているもの:

* `generation_count` — 実装を作った回数
* `provider_calls`   — AI を呼んだ回数

既存能力だけで作れる要求で、このどちらかが 0 でなければ**本線が
壊れている**。
"""

from __future__ import annotations

import os
import pathlib
import random
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from forge_ai.core.ir.capability_ir import entity_spec_from_plan  # noqa: E402
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler  # noqa: E402
from forge_ai.core.ir.ir_generator import IRGenerator  # noqa: E402
from forge_ai.core.orchestration.build_time_extension import (  # noqa: E402
    LoadedBuildActivation,
)
from forge_ai.core.orchestration.capability_artifact_synthesis import (  # noqa: E402
    CapabilityArtifactSynthesizer,
    CapabilityImplementationContract,
)
from forge_ai.core.orchestration.extension_manifest import (  # noqa: E402
    ExtensionEvidence,
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute  # noqa: E402
from forge_ai.core.orchestration.extension_registry import (  # noqa: E402
    PROMOTED_CAPABILITIES,
)
from forge_ai.core.orchestration.flutter_capability_installer import (  # noqa: E402
    INSTALL_ROOT,
    FlutterCapabilityInstaller,
)
from forge_ai.core.orchestration.reuse_first_pipeline import (  # noqa: E402
    ReuseFirstPipeline,
)
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (  # noqa: E402
    SynthesizingBuildTimeImplementer,
)
from forge_ai.core.semantics.capability_plan import plan_capabilities  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402
from forge_ai.testing.free_text_requests import (  # noqa: E402
    RequestShape,
    assert_no_internal_vocabulary,
    generate_request,
)

CAPABILITY = "view.calendar"


def _seed() -> int:
    """CI が落ちたら `FORGE_E2E_SEED` で同じ試験を再実行できる。"""
    raw = os.environ.get("FORGE_E2E_SEED", "").strip()
    return int(raw) if raw else random.SystemRandom().randrange(1, 10**9)


class _Provider:
    """**呼ばれたら数える。** 呼ばれないことを証明するために要る。"""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt):  # noqa: ANN001, ANN202
        self.calls += 1
        return ProviderResponse(text="", structured={})


def _build_document(need, plan, promoted):  # noqa: ANN001, ANN202
    spec = entity_spec_from_plan(plan)
    if spec is None:
        return None
    return ForgeLanguageCompiler().compile(
        IRGenerator().build_from_spec(spec),
        domain_category="generic", title=str(need)[:24],
        promoted_capabilities=tuple(promoted),
    )


def _promoted_manifest() -> ExtensionManifest:
    return ExtensionManifest(
        capability_id=CAPABILITY, label_ja="カレンダーで見る",
        route=ExtensionRoute.BUILD_TIME, requires_confirmation=False,
        status=ExtensionStatus.PROMOTED,
        evidence=ExtensionEvidence(
            semantic_decomposition=True, reusable_primitive=True,
            language_binding=True, validator_binding=True,
            runtime_binding=True, compiler_binding=True,
            tests_pass=True, build_pass=True, runtime_evidence=True,
            safety_review=True,
        ),
    )


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.seed = _seed()
        self.frontend = pathlib.Path(tempfile.mkdtemp(prefix="forge-frontend-"))
        (self.frontend / INSTALL_ROOT).mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.frontend, ignore_errors=True)
        PROMOTED_CAPABILITIES.clear()
        self.addCleanup(PROMOTED_CAPABILITIES.clear)

        self.provider = _Provider()
        self.implementer = SynthesizingBuildTimeImplementer(
            synthesizer=CapabilityArtifactSynthesizer(provider=self.provider),
            contract_for=lambda cid: CapabilityImplementationContract(
                capability_id=cid, intent="月ごとに見る", data_contract=("date",),
                host_language="dart",
                binding_targets=("language", "validator", "runtime", "compiler"),
            ),
            known_source_digests=frozenset(),
        )
        self.pipeline = ReuseFirstPipeline(
            implementer=self.implementer,
            installer=FlutterCapabilityInstaller(
                frontend_root=self.frontend,
                harness_files=frozenset({"capability_test.dart", "probe.dart"}),
                host_prefix="flutter/",
            ),
            build_document=_build_document,
            provider_call_count=lambda: self.provider.calls,
        )

    def _request(self, shape: str, offset: int = 0):  # noqa: ANN202
        """読み取れる自由文を、seed から**決定的に**探す。"""
        for attempt in range(16):
            request = generate_request(self.seed + offset + attempt * 1009, shape)
            plan = plan_capabilities(request.text)
            if entity_spec_from_plan(plan) is None:
                continue
            if shape == RequestShape.NEEDS_MONTHLY_VIEW:
                if CAPABILITY in plan.requested:
                    return request
            elif not plan.missing:
                return request
        self.fail(f"seed={self.seed}: 読み取れる自由文が16回で見つからなかった")
        return None


class TestExistingCapabilitiesNeverRegenerate(_Base):
    """**持っているなら作らない。**"""

    def test_an_existing_only_request_generates_nothing(self) -> None:
        request = self._request(RequestShape.EXISTING_ONLY)
        assert_no_internal_vocabulary(request.text)
        outcome = self.pipeline.handle(request.text)
        self.assertIsNone(outcome.failure, f"seed={self.seed} {request.text!r}")
        self.assertEqual(
            outcome.generation_count, 0,
            f"seed={self.seed} 既存能力だけで作れる要求で生成が走った: {request.text!r}",
        )
        self.assertEqual(outcome.provider_calls, 0, f"seed={self.seed}")
        self.assertIsNotNone(outcome.document, f"seed={self.seed}")

    def test_an_already_acquired_capability_is_reused_not_regenerated(self) -> None:
        """**2回目は作り直さない。**"""
        request = self._request(RequestShape.NEEDS_MONTHLY_VIEW, offset=17)
        # 「既に獲得済み」を、Registry の**本番の門**を通して作る。
        PROMOTED_CAPABILITIES.install(
            _promoted_manifest(),
            LoadedBuildActivation(
                capability_id=CAPABILITY, build_id="build-x",
                runtime_fingerprint="fp-x", source_digest="digest-x", loaded=True,
            ),
        )
        outcome = self.pipeline.handle(request.text)
        self.assertEqual(
            outcome.generation_count, 0,
            f"seed={self.seed} 獲得済みの能力を作り直した: {request.text!r}",
        )
        self.assertEqual(
            self.provider.calls, 0,
            f"seed={self.seed} 獲得済みなのに AI を呼んだ",
        )
        self.assertIn(CAPABILITY, outcome.reused, f"seed={self.seed}")

    def test_an_existing_only_request_is_fast(self) -> None:
        """**遅すぎても不合格。** 生成も検査も走っていないこと。"""
        request = self._request(RequestShape.EXISTING_ONLY, offset=41)
        outcome = self.pipeline.handle(request.text)
        self.assertEqual(outcome.timings.synthesis_ms, 0.0)
        self.assertEqual(outcome.timings.verify_ms, 0.0)
        self.assertEqual(outcome.timings.install_ms, 0.0)
        self.assertLess(
            outcome.timings.total_ms, 500.0,
            f"seed={self.seed} 既存能力だけの要求が遅すぎる: "
            f"{outcome.timings.to_dict()}",
        )


class TestTheGeneratedFreeTextIsHonest(unittest.TestCase):
    """**テストが答えを教える文になっていないこと。**"""

    def test_no_request_leaks_internal_vocabulary(self) -> None:
        for seed in range(300):
            for shape in (RequestShape.EXISTING_ONLY, RequestShape.NEEDS_MONTHLY_VIEW):
                assert_no_internal_vocabulary(generate_request(seed, shape).text)

    def test_the_same_seed_gives_the_same_sentence(self) -> None:
        first = generate_request(4242, RequestShape.NEEDS_MONTHLY_VIEW).text
        second = generate_request(4242, RequestShape.NEEDS_MONTHLY_VIEW).text
        self.assertEqual(first, second)

    def test_different_seeds_give_different_sentences(self) -> None:
        seen = {
            generate_request(seed, RequestShape.EXISTING_ONLY).text
            for seed in range(60)
        }
        self.assertGreater(len(seen), 20, f"文面が固定に近い: {len(seen)} 種")


if __name__ == "__main__":
    unittest.main()
