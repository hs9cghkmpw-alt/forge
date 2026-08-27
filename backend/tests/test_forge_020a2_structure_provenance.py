"""**構造を誰が作ったかを、正しく測る**（FORGE-020A2 §3、2026-08-26）。

---

## 直そうとしている誤認

R4 以降、文書はこの順で出来る。

```
Capability Plan → 決定的な EntitySpec → IR → Design Intent（AI）
```

**構造は決定的に組まれ、AI は Design Intent だけ答える**ことがある。
その状態で `last_provider_used == "local"` になると、

    domain_resolution != curated  +  provider == local  →  LOCAL_AI

という判定で **`GenerationSource.LOCAL_AI`**——「Local Model が構造を
決めた」——になってしまう。

**それは嘘である。** Local Model は見た目の役だけ答えた。

Level 0 がこれを Real Local Model run として数えると、
「Local Model がソフトウェアの構造を作れた」という**存在しない実績**が
記録される。

## 直し方

`GenerationStructureSource` を分け、**構造を作った段をその場で記録する**。
Provider 名から後で推定しない。Decision Trace の文字列も parse しない
（`CognitiveContext` に typed value として持たせる）。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.ai.gateway.capability_evidence import (  # noqa: E402
    GenerationStructureSource,
    structure_source_is_ai,
)
from app.ai.gateway.generation_evidence import (  # noqa: E402
    GenerationSource,
    default_generation_store,
)
from app.main import app  # noqa: E402
from forge_ai.core.semantics.structure_provenance import StructureSource  # noqa: E402

DETERMINISTIC_NEED = "旅行の写真を日付ごとに残してメモを付けたい"
CURATED_NEED = "毎日の収入と支出を記録して残高を見たい"


class TestTheTwoEnumsAgree(unittest.TestCase):
    """`forge_ai` は `backend` を import できないので値で照合する。"""

    def test_every_forge_ai_value_exists_in_the_backend_enum(self) -> None:
        for member in StructureSource:
            with self.subTest(member=member):
                self.assertEqual(
                    GenerationStructureSource(member.value).value, member.value,
                )

    def test_both_enums_have_the_same_members(self) -> None:
        self.assertEqual(
            {m.value for m in StructureSource},
            {m.value for m in GenerationStructureSource},
        )


class TestDeterministicStructureIsNotAnAiAchievement(unittest.TestCase):
    def test_a_deterministic_plan_is_not_ai_structure(self) -> None:
        self.assertFalse(
            structure_source_is_ai(
                GenerationStructureSource.DETERMINISTIC_CAPABILITY_PLAN,
            ),
        )

    def test_curated_is_not_ai_structure(self) -> None:
        self.assertFalse(structure_source_is_ai(GenerationStructureSource.CURATED))

    def test_entity_synthesis_is_ai_structure(self) -> None:
        self.assertTrue(
            structure_source_is_ai(GenerationStructureSource.AI_ENTITY_SYNTHESIS),
        )

    def test_unknown_is_never_ai(self) -> None:
        """**記録し損ねたものを AI 側へ倒さない。**"""
        self.assertFalse(structure_source_is_ai(GenerationStructureSource.UNKNOWN))


class TestADesignIntentOnlyLocalCallIsNotLocalAi(unittest.TestCase):
    """**再現: 構造は決定的、AI は Design Intent だけ。**

    `_generation_source()` を直接呼ぶ。「local が答えた」という事実だけを
    渡して、それでも `LOCAL_AI` にならないことを確かめる。
    """

    def setUp(self) -> None:
        from app.ai.runtime.prompt_pipeline import _generation_source

        self._source = _generation_source
        self._trace = [{"stage": "domain_resolution", "decision": "generated"}]

    class _Context:
        def __init__(self, structure: StructureSource) -> None:
            self.structure_source = structure

    def test_deterministic_plan_with_a_local_provider_is_not_local_ai(self) -> None:
        source = self._source(
            self._trace, "local",
            self._Context(StructureSource.DETERMINISTIC_CAPABILITY_PLAN),
        )
        self.assertIsNot(
            source, GenerationSource.LOCAL_AI,
            "構造は Forge が決定的に組んだのに、Local Model の手柄になっている",
        )
        self.assertIs(source, GenerationSource.COMPOSITION)

    def test_deterministic_plan_with_a_cloud_provider_is_not_cloud_ai(self) -> None:
        source = self._source(
            self._trace, "gemini",
            self._Context(StructureSource.DETERMINISTIC_CAPABILITY_PLAN),
        )
        self.assertIsNot(source, GenerationSource.CLOUD_AI)

    def test_ai_entity_synthesis_with_a_local_provider_is_local_ai(self) -> None:
        """**本物のときは、ちゃんと LOCAL_AI と言う。**

        弾きすぎて Local AI が永久に実績を持てない、では意味がない。
        """
        source = self._source(
            self._trace, "local", self._Context(StructureSource.AI_ENTITY_SYNTHESIS),
        )
        self.assertIs(source, GenerationSource.LOCAL_AI)

    def test_a_mock_provider_stays_a_test_double(self) -> None:
        """`TEST_DOUBLE` を `COMPOSITION` へ洗い流さない（014 §2）。"""
        source = self._source(
            self._trace, "mock",
            self._Context(StructureSource.DETERMINISTIC_CAPABILITY_PLAN),
        )
        self.assertIs(source, GenerationSource.TEST_DOUBLE)


class TestProductionAlwaysRecordsWhoBuiltTheStructure(unittest.TestCase):
    """**本番が `UNKNOWN` を残さないこと。**

    provenance の配線を外すとここが落ちる。`_generation_source()` は
    `UNKNOWN` では格下げしない（推測しない）ので、**この検査が
    その穴を塞いでいる**。
    """

    def setUp(self) -> None:
        self.client = TestClient(app)

    def _record_for(self, need: str):  # noqa: ANN202
        store = default_generation_store()
        before = len(store.all_records())
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": need,
                            "generation_options": {"provider": "mock"}}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        records = store.all_records()
        self.assertGreater(len(records), before)
        return records[-1]

    def test_a_deterministic_generation_records_its_structure_source(self) -> None:
        record = self._record_for(DETERMINISTIC_NEED)
        self.assertIs(
            record.structure_source,
            GenerationStructureSource.DETERMINISTIC_CAPABILITY_PLAN,
        )

    def test_a_curated_generation_records_curated(self) -> None:
        record = self._record_for(CURATED_NEED)
        self.assertIs(record.structure_source, GenerationStructureSource.CURATED)

    def test_no_production_generation_leaves_the_structure_unknown(self) -> None:
        for need in (DETERMINISTIC_NEED, CURATED_NEED,
                     "植物を育てながら音を組み合わせるゲームを作りたい",
                     "子どもが朝の支度をひとつずつチェックできるようにしたい"):
            with self.subTest(need=need):
                self.assertIsNot(
                    self._record_for(need).structure_source,
                    GenerationStructureSource.UNKNOWN,
                    "構造を誰が作ったか記録されていない",
                )

    def test_a_deterministic_structure_names_no_provider(self) -> None:
        """**呼んでもいない Provider の手柄にしない**（019B §4 / 020A）。"""
        self.assertEqual(self._record_for(DETERMINISTIC_NEED).structure_provider, "")

    def test_the_structure_task_is_observed_not_asserted(self) -> None:
        """本番が通す Task は `cognitive_stage` である。"""
        self.assertEqual(
            self._record_for(DETERMINISTIC_NEED).structure_task, "cognitive_stage",
        )


if __name__ == "__main__":
    unittest.main()
