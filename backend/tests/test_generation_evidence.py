"""生成物のEvidenceが、**AIを呼ばない経路からも**残ること
(FORGE-PRE-R1-INTEGRITY-GATE-013 §4、2026-08-17)。

---

## 何を直したテストか

TD65として記録した実測:

    /generate（Curated Domain）  生成stageのAI呼び出し 0回
                                 → 生成物についての記録が1件も残らない

R0で入れた`ExperienceRecord`は「1回のAI呼び出しについての事実」なので、
**AIを呼ばなければ書く先が無い**。Curated経路は0.01秒・Quota消費0で
Validator合格のアプリを作るのに、その成功が学習素材にならなかった。

学習データを作るためだけにCuratedへ無理やりAIを通すのは本末転倒で
ある（速くて安定して無料な経路を、記録の都合で遅く不安定に有料に
することになる）。したがって**記録の側を分けた**。

## このファイルが守る不変条件

* Curated生成でも`GenerationRecord`が残る（`ai_calls=0`で）
* Validator不合格でも残る（成功だけ貯めない）
* 由来が`source`で区別される（Curatedの成功をAIの成功として数えない）
* **利用者の発話も生成物本文も入らない**（006 §22）
* Validator合格**だけ**では正例にしない
"""

from __future__ import annotations

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.gateway.generation_evidence import (  # noqa: E402
    GenerationEvidenceStore,
    GenerationRecord,
    GenerationSource,
    RuntimeOutcome,
    default_generation_store,
)
from app.ai.gateway.learning_foundation import AcceptanceSignal  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover — 環境依存
    _FASTAPI_AVAILABLE = False


def _record(**overrides) -> GenerationRecord:
    defaults = {
        "source": GenerationSource.CURATED,
        "domain": "household_budget",
        "validator_passed": True,
    }
    return GenerationRecord(**{**defaults, **overrides})


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestCuratedGenerationsLeaveEvidence(unittest.TestCase):
    """**HTTP APIを叩くだけ**で、AIを呼ばない生成物の記録が残ること。

    `GenerationEvidenceStore`に一切触れずに測る
    (`test_experience_wiring.py`と同じ姿勢)。
    """

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.store = default_generation_store()
        self.store.reset()

    def _generate(self, text: str):
        return self.client.post(
            "/api/v1/ai/generate",
            json={
                "input": {
                    "natural_language": text,
                    "generation_options": {"provider": "mock"},
                }
            },
        )

    def test_a_curated_domain_leaves_a_record_with_zero_ai_calls(self) -> None:
        """**TD65そのものの回帰。**

        `ai_calls=0`が異常値ではないことが、この型を作った理由である。
        """
        response = self._generate("家計の支出をカテゴリ別に管理したい")
        self.assertEqual(response.status_code, 200, response.text)
        curated = [r for r in self.store.all_records() if r.source is GenerationSource.CURATED]
        self.assertTrue(
            curated,
            "Curated Domainの生成がEvidenceを1件も残していない。"
            "AIを呼ばない成功例は、記録する場所が無いと学習素材にならない。",
        )
        self.assertEqual(curated[0].ai_calls, 0)
        self.assertTrue(curated[0].validator_passed)
        self.assertEqual(curated[0].domain, "household_budget")

    def test_a_generated_domain_is_recorded_with_a_different_source(self) -> None:
        """由来が混ざらないこと。混ぜると、Curatedの成績でLocal AIの
        昇格判断が押し上げられる。"""
        self._generate("盆栽の水やりの記録をつけたい")
        sources = {r.source for r in self.store.all_records()}
        self.assertIn(GenerationSource.CLOUD_AI, sources)

    def test_the_source_is_never_guessed_from_the_call_count(self) -> None:
        """**AI呼び出し0回だからCuratedとは推測しない。**

        決定の記録(`domain_resolution`)から読む。読めなければ
        `UNKNOWN`であり、`UNKNOWN`は学習に使えない。
        """
        from app.ai.runtime.prompt_pipeline import _generation_source  # noqa: PLC0415

        self.assertIs(_generation_source([], ai_calls=0), GenerationSource.UNKNOWN)
        self.assertIs(
            _generation_source([{"stage": "domain_resolution", "decision": "curated"}], 0),
            GenerationSource.CURATED,
        )

    def test_the_decision_trace_still_carries_the_stage_we_read(self) -> None:
        """**唯一の接点が消えていないこと。**

        `pipeline_orchestrator`が`domain_resolution`という名前を変えたら、
        由来は黙って`UNKNOWN`へ落ちる——記録は残るが全部「由来不明」に
        なり、学習に使えなくなる。静かに壊れる形なので、名前ごと固定する。
        """
        response = self._generate("家計の支出をカテゴリ別に管理したい")
        stages = {
            entry.get("stage")
            for entry in response.json()["result"]["diagnostics"]["decision_trace"]
        }
        self.assertIn("domain_resolution", stages)

    def test_nothing_recorded_can_carry_what_the_user_said(self) -> None:
        self._generate("むにゃむにゃ特有の言い回しXYZZYを記録したい")
        dumped = repr([r.to_dict() for r in self.store.all_records()])
        self.assertNotIn("XYZZY", dumped)
        self.assertNotIn("むにゃむにゃ", dumped)


class TestTheRecordCannotHoldContent(unittest.TestCase):
    """`ExperienceRecord`と同じPrivacy境界(006 §22)を型で塞ぐ。"""

    def test_the_only_string_fields_are_identifiers(self) -> None:
        text_fields = {
            f.name for f in dataclasses.fields(GenerationRecord)
            if f.type in ("str", "str | None")
        }
        self.assertEqual(
            text_fields, {"domain", "forge_language_version"},
            f"内容を入れられるフィールドが増えている: {text_fields}",
        )

    def test_it_cannot_hold_an_utterance_or_the_document(self) -> None:
        for forbidden in ("prompt", "utterance", "forge_document", "build_brief",
                          "user_id", "session_id", "response"):
            with self.subTest(field=forbidden):
                with self.assertRaises(TypeError):
                    _record(**{forbidden: "何か"})


class TestWhatCountsAsATrainingCandidate(unittest.TestCase):
    def test_passing_the_validator_is_not_enough(self) -> None:
        """**Validator合格だけでは正例にしない。**

        Validatorは「壊れていない」ことしか言わない。良いかどうかは
        利用者が決める(Product Direction §5)。
        """
        self.assertFalse(_record(validator_passed=True).is_positive_example)

    def test_an_explicit_acceptance_makes_it_a_candidate(self) -> None:
        self.assertTrue(
            _record(user_acceptance=AcceptanceSignal.ACCEPTED).is_positive_example
        )

    def test_a_failed_runtime_disqualifies_it(self) -> None:
        self.assertFalse(
            _record(
                user_acceptance=AcceptanceSignal.ACCEPTED,
                runtime_outcome=RuntimeOutcome.FAILED,
            ).is_positive_example
        )

    def test_an_unknown_source_is_never_a_candidate(self) -> None:
        """由来不明のものを学習へ流さない
        (`TrainingProvenance.UNKNOWN`と同じ姿勢)。"""
        self.assertFalse(
            _record(
                source=GenerationSource.UNKNOWN,
                user_acceptance=AcceptanceSignal.ACCEPTED,
            ).is_positive_example
        )

    def test_silence_is_not_acceptance(self) -> None:
        self.assertIs(_record().user_acceptance, AcceptanceSignal.UNKNOWN)
        self.assertFalse(_record().is_positive_example)


class TestTheStore(unittest.TestCase):
    def test_the_summary_splits_by_source(self) -> None:
        """**Curatedの成功をAIの成功として数えない。**"""
        store = GenerationEvidenceStore()
        store.record(_record(source=GenerationSource.CURATED, ai_calls=0))
        store.record(_record(source=GenerationSource.CLOUD_AI, ai_calls=3))
        store.record(_record(source=GenerationSource.CLOUD_AI, validator_passed=False))
        summary = store.summary_by_source()
        self.assertEqual(summary["curated"]["samples"], 1)
        self.assertEqual(summary["curated"]["mean_ai_calls"], 0.0)
        self.assertEqual(summary["cloud_ai"]["samples"], 2)
        self.assertEqual(summary["cloud_ai"]["validator_pass_rate"], 0.5)

    def test_acceptance_is_written_once_and_the_first_wins(self) -> None:
        store = GenerationEvidenceStore()
        stored = store.record(_record())
        store.note_user_acceptance([stored.ref], AcceptanceSignal.CORRECTED)
        store.note_user_acceptance([stored.ref], AcceptanceSignal.ABANDONED)
        self.assertIs(store.all_records()[0].user_acceptance, AcceptanceSignal.CORRECTED)

    def test_unknown_never_overwrites(self) -> None:
        store = GenerationEvidenceStore()
        stored = store.record(_record())
        store.note_user_acceptance([stored.ref], AcceptanceSignal.ACCEPTED)
        store.note_user_acceptance([stored.ref], AcceptanceSignal.UNKNOWN)
        self.assertIs(store.all_records()[0].user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_old_records_are_dropped_instead_of_growing_without_bound(self) -> None:
        store = GenerationEvidenceStore()
        for _ in range(GenerationEvidenceStore._MAX_RECORDS + 20):  # noqa: SLF001
            store.record(_record())
        self.assertEqual(
            len(store.all_records()), GenerationEvidenceStore._MAX_RECORDS  # noqa: SLF001
        )


if __name__ == "__main__":
    unittest.main()
