"""**足りない能力の実装を、Forge が実際に書けること**（020E）。

そして同じくらい大事なこと——**書けなかったときに「書けた」と言わない**、
**既存コードの丸写しを「生成した」と数えない**。
"""

from __future__ import annotations

import pathlib
import unittest

from forge_ai.core.orchestration.build_time_extension import BuildTimeExtensionError
from forge_ai.core.orchestration.capability_artifact_synthesis import (
    CapabilityArtifactSynthesizer,
    CapabilityImplementationContract,
    PreexistingSourceError,
    digest_of_source,
)
from forge_ai.prompt.prompt_builder import Prompt
from forge_ai.provider.provider_interface import ProviderResponse

_MODULE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "core" / "orchestration" / "capability_artifact_synthesis.py"
)

CONTRACT = CapabilityImplementationContract(
    capability_id="view.calendar",
    intent="予定を月ごとの表で見る",
    data_contract=("date: number",),
    host_language="dart",
    binding_targets=("language", "validator", "runtime", "compiler"),
)


class _Provider:
    """返す中身を差し替えられる Test Double。"""

    def __init__(self, structured: dict) -> None:
        self.structured = structured
        self.prompts: list[Prompt] = []

    def complete(self, prompt: Prompt) -> ProviderResponse:
        self.prompts.append(prompt)
        return ProviderResponse(text="", structured=self.structured)


def _good_payload() -> dict:
    return {
        "files": [
            {"path": "lib/calendar_view.dart", "content": "class CalendarView {}\n"},
            {"path": "test/calendar_view_test.dart", "content": "void main() {}\n"},
        ],
        "reusable_contract": "月表示の再利用可能な View",
    }


def _synth(structured: dict) -> tuple[CapabilityArtifactSynthesizer, _Provider]:
    provider = _Provider(structured)
    return CapabilityArtifactSynthesizer(provider=provider), provider


class TestItActuallyProducesAnArtifact(unittest.TestCase):
    def test_a_valid_response_becomes_a_build_time_artifact(self) -> None:
        synth, _ = _synth(_good_payload())
        artifact = synth.synthesize(CONTRACT, known_source_digests=frozenset())
        self.assertIsNotNone(artifact)
        assert artifact is not None
        self.assertEqual(artifact.capability_id, "view.calendar")
        self.assertEqual(len(artifact.files), 2)
        artifact.validate()
        self.assertTrue(artifact.source_digest)

    def test_the_contract_reaches_the_prompt(self) -> None:
        synth, provider = _synth(_good_payload())
        synth.synthesize(CONTRACT, known_source_digests=frozenset())
        prompt = provider.prompts[-1]
        self.assertEqual(prompt.stage, "capability_implementation")
        self.assertIn("view.calendar", prompt.instruction)
        self.assertIn("date: number", prompt.instruction)


class TestIdentityCannotBeSwitched(unittest.TestCase):
    """**途中で別の能力へすり替わらない。**"""

    def test_the_model_cannot_rename_the_capability(self) -> None:
        payload = _good_payload()
        payload["capability_id"] = "effect.payment"
        synth, _ = _synth(payload)
        artifact = synth.synthesize(CONTRACT, known_source_digests=frozenset())
        assert artifact is not None
        self.assertEqual(
            artifact.capability_id, "view.calendar",
            "AI の自己申告で capability identity が変わっている",
        )


class TestExistingSourceIsNotCalledGeneration(unittest.TestCase):
    """**既存コードの activation を「自律生成」と数えない。**"""

    def test_regurgitated_shipped_source_is_rejected(self) -> None:
        payload = _good_payload()
        shipped = payload["files"][0]["content"]
        synth, _ = _synth(payload)
        with self.assertRaises(PreexistingSourceError):
            synth.synthesize(
                CONTRACT,
                known_source_digests=frozenset({digest_of_source(shipped)}),
            )

    def test_whitespace_only_edits_do_not_disguise_a_copy(self) -> None:
        """末尾空白や改行コードを変えただけで「新しい実装」にしない。"""
        payload = _good_payload()
        original = payload["files"][0]["content"]
        payload["files"][0]["content"] = original.replace("\n", "\r\n") + "   \n"
        synth, _ = _synth(payload)
        with self.assertRaises(PreexistingSourceError):
            synth.synthesize(
                CONTRACT,
                known_source_digests=frozenset({digest_of_source(original)}),
            )

    def test_genuinely_new_source_passes(self) -> None:
        """弾きすぎない。**違う実装は通る。**"""
        synth, _ = _synth(_good_payload())
        artifact = synth.synthesize(
            CONTRACT,
            known_source_digests=frozenset({digest_of_source("class Other {}")}),
        )
        self.assertIsNotNone(artifact)

    def test_the_digest_check_cannot_be_skipped_by_forgetting_it(self) -> None:
        """**渡し忘れられる形にしない。** 既定値を持たせていない。"""
        synth, _ = _synth(_good_payload())
        with self.assertRaises(TypeError):
            synth.synthesize(CONTRACT)  # type: ignore[call-arg]


class TestUnusableResponsesBecomeNoneNotAFakeArtifact(unittest.TestCase):
    """**作れなかったものを「作れた」と言わない。**"""

    def test_an_empty_response_is_none(self) -> None:
        synth, _ = _synth({})
        self.assertIsNone(synth.synthesize(CONTRACT, known_source_digests=frozenset()))

    def test_implementation_without_tests_is_rejected(self) -> None:
        """検証できない実装は受け取らない。"""
        synth, _ = _synth({"files": [
            {"path": "lib/calendar_view.dart", "content": "class CalendarView {}"},
        ]})
        self.assertIsNone(synth.synthesize(CONTRACT, known_source_digests=frozenset()))

    def test_tests_without_implementation_is_rejected(self) -> None:
        synth, _ = _synth({"files": [
            {"path": "test/calendar_view_test.dart", "content": "void main() {}"},
        ]})
        self.assertIsNone(synth.synthesize(CONTRACT, known_source_digests=frozenset()))

    def test_unsafe_paths_are_dropped(self) -> None:
        synth, _ = _synth({"files": [
            {"path": "../../etc/passwd", "content": "x"},
            {"path": "/abs/path.dart", "content": "y"},
            {"path": "test/ok_test.dart", "content": "void main() {}"},
        ]})
        # 実装ファイルが1つも残らないので None。
        self.assertIsNone(synth.synthesize(CONTRACT, known_source_digests=frozenset()))

    def test_an_incomplete_contract_is_refused(self) -> None:
        synth, _ = _synth(_good_payload())
        broken = CapabilityImplementationContract(
            capability_id="", intent="x", data_contract=(),
            host_language="dart", binding_targets=("language",),
        )
        with self.assertRaises(BuildTimeExtensionError):
            synth.synthesize(broken, known_source_digests=frozenset())


class TestNoCapabilitySpecificBranchExists(unittest.TestCase):
    """**map 専用 generator を一般機構として作らない。**

    「足りない能力を作る」の中に `if capability_id == "view.map"` を
    書いた瞬間、それは Template を1つ増やしたのと同じである。
    """

    def test_the_module_holds_no_capability_id_literals(self) -> None:
        source = _MODULE.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.split("\n")
            if not line.lstrip().startswith("#")
        )
        # docstring 内の説明（禁止例として書いてある）は除く。
        body = code.split('"""')
        executable = "".join(body[i] for i in range(0, len(body), 2))
        for namespace in ("view.", "data.", "effect.", "interact.", "simulate."):
            with self.subTest(namespace=namespace):
                self.assertNotIn(
                    namespace, executable,
                    f"{namespace} を実行コードが名指ししている"
                    "（能力ごとの分岐は Template と同じ）",
                )

    def test_two_different_capabilities_take_the_same_path(self) -> None:
        """能力を変えても、通る道が変わらないこと。"""
        other = CapabilityImplementationContract(
            capability_id="effect.share",
            intent="作ったものを人に渡す",
            data_contract=(),
            host_language="dart",
            binding_targets=("language", "validator", "runtime", "compiler"),
        )
        synth, provider = _synth(_good_payload())
        first = synth.synthesize(CONTRACT, known_source_digests=frozenset())
        second = synth.synthesize(other, known_source_digests=frozenset())
        assert first is not None and second is not None
        self.assertEqual(first.capability_id, "view.calendar")
        self.assertEqual(second.capability_id, "effect.share")
        self.assertEqual(len(provider.prompts), 2)
        self.assertEqual(provider.prompts[0].stage, provider.prompts[1].stage)


if __name__ == "__main__":
    unittest.main()
