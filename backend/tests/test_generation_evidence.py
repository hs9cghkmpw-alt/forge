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
    StructureProvenance,
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

    def test_a_curated_domain_leaves_a_record(self) -> None:
        """**TD65そのものの回帰。**

        Curated経路は**構造をAIに決めさせない**。その成功例を記録する
        場所が無かったのがTD65である。

        ---

        ## `ai_calls == 0` を主張しなくなった理由（R1で変わった事実）

        013時点では、Curated生成のAI呼び出しは**0回**だった。
        R1でDesign Intent段（`design_intent.py`）を入れたことで、
        **Curatedでも1回はAIを呼ぶ**ようになった。

        呼ぶのは「この画面はどの密度で見せるか」という**意味**だけで
        あり、構造は今もCuratedの決定的な定義から作られる。だから
        `source`は`CURATED`のままで正しい——`source`が答えるのは
        「**構造**を誰が決めたか」である。

        **これは無料ではない**。Curatedの長所だった「0.01秒・Quota
        消費0」が失われる。Gemini無料枠は実測で1日20回/Modelなので
        （TD66）、この1回は軽くない。`ai_calls`に実数が入るので、
        **コストがEvidence上で見える**ようにしてある。
        """
        response = self._generate("家計の支出をカテゴリ別に管理したい")
        self.assertEqual(response.status_code, 200, response.text)
        curated = [r for r in self.store.all_records() if r.source is GenerationSource.CURATED]
        self.assertTrue(
            curated,
            "Curated Domainの生成がEvidenceを1件も残していない。"
            "構造をAIに決めさせない成功例も、記録する場所が無いと"
            "学習素材にならない。",
        )
        self.assertTrue(curated[0].validator_passed)
        self.assertEqual(curated[0].domain, "household_budget")

    def test_the_curated_path_still_does_not_let_ai_decide_the_structure(self) -> None:
        """**Design Intentを入れてもCuratedはCuratedのままであること。**

        AIが選ぶのは密度・面といった意味だけで、Entityの構造・Field・
        画面構成はCuratedの決定的な定義から作られる。ここが崩れると
        「Curatedの安定性」という長所そのものが消える。
        """
        self._generate("家計の支出をカテゴリ別に管理したい")
        curated = [r for r in self.store.all_records() if r.source is GenerationSource.CURATED]
        self.assertTrue(curated)
        self.assertLessEqual(
            curated[0].ai_calls, 2,
            "Curated経路のAI呼び出しが増えすぎている。構造までAIに"
            "決めさせていないか確認すること（Curatedの長所が消える）。",
        )

    def test_a_mock_generation_is_never_recorded_as_cloud_ai(self) -> None:
        """**014 §2で直した実バグの回帰テスト。**

        013では`domain_resolution == "generated"`を無条件に`CLOUD_AI`へ
        写していた。そのため、Mock Providerで作ったものまで
        「Cloud AIの実績」として記録されていた——このテスト自身が、
        013では`assertIn(CLOUD_AI, sources)`と書いて**その誤りを固定
        していた**。

        Mockの成功をCloudの実績に混ぜると、Cloudの品質を過大評価する。
        Localへ混ぜれば、Local AIの昇格判断が壊れる。**どちらでもない**
        ので`TEST_DOUBLE`である。
        """
        self._generate("盆栽の水やりの記録をつけたい")
        generated = [r for r in self.store.all_records() if r.source is not GenerationSource.CURATED]
        self.assertTrue(generated, "生成されたDomainの記録が無い。")
        for record in generated:
            with self.subTest(ref=record.ref):
                self.assertIs(
                    record.source, GenerationSource.TEST_DOUBLE,
                    "Mock Providerの生成がTEST_DOUBLE以外で記録されている。",
                )
                self.assertNotIn(
                    record.source, {GenerationSource.CLOUD_AI, GenerationSource.LOCAL_AI},
                )

    def test_capability_plan_structure_is_not_attributed_to_provider(self) -> None:
        """後段でProviderが呼ばれても、構造は決定的Planの成果。"""
        self._generate("実験の条件と結果を残して、条件ごとに成功率を比べたい")
        record = self.store.all_records()[-1]
        self.assertIs(
            record.structure_provenance,
            StructureProvenance.DETERMINISTIC_CAPABILITY_PLAN,
        )
        self.assertIsNot(record.structure_provenance, StructureProvenance.LOCAL_AI)

    def test_a_test_double_is_not_a_training_candidate(self) -> None:
        """Mockの出力を教師にすると、Mockの癖を学ぶことになる。"""
        self.assertFalse(GenerationSource.TEST_DOUBLE.is_usable_for_training)

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



class TestTheSourceComesFromTheProviderFacts(unittest.TestCase):
    """**由来は実際に答えたProviderの事実から決める**(014 §2)。

    Registryの`deployment`/`test_only`がSingle Source of Truthである。
    """

    def test_curated_resolution_wins(self) -> None:
        """Curated経路は生成stageでAIを呼ばないので、会話ステップの
        Providerが`last_provider_used`に残っていても**Curatedである**。"""
        from app.ai.runtime.prompt_pipeline import _generation_source  # noqa: PLC0415

        trace = [{"stage": "domain_resolution", "decision": "curated"}]
        self.assertIs(_generation_source(trace, "gemini"), GenerationSource.CURATED)

    def test_a_cloud_provider_is_recorded_as_cloud_ai(self) -> None:
        from app.ai.runtime.prompt_pipeline import _generation_source  # noqa: PLC0415

        trace = [{"stage": "domain_resolution", "decision": "generated"}]
        self.assertIs(_generation_source(trace, "gemini"), GenerationSource.CLOUD_AI)

    def test_a_local_provider_is_recorded_as_local_ai(self) -> None:
        """**Local AIが将来動いたときの契約を、今のうちに固定する。**

        実モデルを呼ぶ必要はない——Registryが`deployment=local`と
        宣言していることが根拠であり、そこが判定の唯一の入口である。
        """
        from app.ai.runtime.prompt_pipeline import _generation_source  # noqa: PLC0415

        trace = [{"stage": "domain_resolution", "decision": "generated"}]
        self.assertIs(_generation_source(trace, "local"), GenerationSource.LOCAL_AI)

    def test_a_test_only_provider_is_neither_cloud_nor_local(self) -> None:
        """`mock`はRegistry上`deployment=local`だが、**`test_only`を先に
        見る**。順序を逆にするとMockがLocal AIの実績を水増しする。"""
        from app.ai.runtime.prompt_pipeline import _generation_source  # noqa: PLC0415

        trace = [{"stage": "domain_resolution", "decision": "generated"}]
        self.assertIs(_generation_source(trace, "mock"), GenerationSource.TEST_DOUBLE)

    def test_an_unknown_provider_is_unknown(self) -> None:
        """**推測しない。** 未登録の名前から由来を当てにいかない。"""
        from app.ai.runtime.prompt_pipeline import _generation_source  # noqa: PLC0415

        trace = [{"stage": "domain_resolution", "decision": "generated"}]
        for provider in (None, "", "登録されていないProvider"):
            with self.subTest(provider=provider):
                self.assertIs(_generation_source(trace, provider), GenerationSource.UNKNOWN)

    def test_no_decision_trace_still_reads_the_provider(self) -> None:
        """決定の記録が無くても、**誰が答えたか**は分かる。"""
        from app.ai.runtime.prompt_pipeline import _generation_source  # noqa: PLC0415

        self.assertIs(_generation_source([], "gemini"), GenerationSource.CLOUD_AI)
        self.assertIs(_generation_source([], None), GenerationSource.UNKNOWN)

    def test_the_registry_is_the_single_source_of_truth(self) -> None:
        """Providerを1つ増やすたびに判定表へ書き足す形にしない。

        Registryの宣言だけで決まるので、**Provider追加時に由来判定を
        書き忘れることができない**。
        """
        from app.ai.gateway.generation_evidence import source_for_generated  # noqa: PLC0415
        from app.ai.gateway.provider_registry import Deployment, provider_registry  # noqa: PLC0415

        for definition in provider_registry():
            with self.subTest(provider=definition.provider_id):
                actual = source_for_generated(definition.provider_id)
                if definition.test_only:
                    expected = GenerationSource.TEST_DOUBLE
                elif definition.deployment is Deployment.LOCAL:
                    expected = GenerationSource.LOCAL_AI
                else:
                    expected = GenerationSource.CLOUD_AI
                self.assertIs(actual, expected)

class TestTheRecordCannotHoldContent(unittest.TestCase):
    """`ExperienceRecord`と同じPrivacy境界(006 §22)を型で塞ぐ。"""

    def test_the_only_string_fields_are_identifiers(self) -> None:
        text_fields = {
            f.name for f in dataclasses.fields(GenerationRecord)
            if f.type in ("str", "str | None")
        }
        self.assertEqual(
            # `uid`は**この記録自身の身元**であり、内容ではない
            # (FORGE-017A §3、Dataset Lineage用の永続ID)。
            # 追加するときは「識別子か、内容か」を必ず判断すること
            # ——このテストは判断を強制するために在る。
            text_fields, {"domain", "forge_language_version", "uid", "structure_task",
                          "entity_synthesis_rejection_reason"},
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
