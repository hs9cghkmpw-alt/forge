"""Forge Knowledge と Intelligence Context（016A commit D / 017A §8・§15）。

---

## このファイルが守っているもの

`design_language.knowledge_entries()` は014から存在したが、**本番から
1度も呼ばれていなかった**（TD69）。「作ったが本番から呼ばれない」の
5例目である。

したがってこのファイルは、型が正しいことだけでなく、
**本番のHTTP経路を通ったときに実際に知識が使われ、Evidenceへ残ること**
を確かめる。

## 境界（017 §17・§18）

* **AppはGlobalを見られる。GlobalはAppを見られない**
* **Personalは誰にも見えない**
* Evidenceへ残るのは**識別子と版だけ**（本文は残さない）
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.gateway.generation_evidence import default_generation_store  # noqa: E402
from app.ai.gateway.intelligence_context import IntelligenceContextResolver  # noqa: E402
from app.ai.gateway.knowledge import (  # noqa: E402
    KnowledgeEntry,
    KnowledgeStatus,
    KnowledgeStore,
    default_knowledge_store,
)
from app.ai.gateway.learning_contract import DataResidency, IntelligenceScope  # noqa: E402
from app.ai.gateway.learning_foundation import TrainingProvenance  # noqa: E402
from app.ai.gateway.tasks import ForgeTask  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


def _entry(entry_id: str, **overrides) -> KnowledgeEntry:
    defaults = {
        "entry_id": entry_id,
        "content": f"{entry_id}の説明",
        "status": KnowledgeStatus.ACTIVE,
        "provenance": TrainingProvenance.FORGE_SYNTHETIC,
    }
    return KnowledgeEntry(**{**defaults, **overrides})


class TestScopeIsAStructuralBoundary(unittest.TestCase):
    """**「返さない運用」ではなく、Storeが構造として分かれている。**"""

    def setUp(self) -> None:
        self.store = KnowledgeStore()
        self.store.add(_entry("g.1"))
        self.store.add(_entry("a.1", scope=IntelligenceScope.APP, app_id="app-A"))
        self.store.add(_entry("a.2", scope=IntelligenceScope.APP, app_id="app-B"))
        self.store.add(_entry("p.1", scope=IntelligenceScope.PERSONAL))

    def _ids(self, **kwargs) -> set[str]:
        return {e.entry_id for e in self.store.retrieve(**kwargs)}

    def test_global_cannot_see_app_knowledge(self) -> None:
        """**逆向きを許すと、あるAppの知識が全利用者の生成へ効く**
        （017 §18）。"""
        self.assertEqual(self._ids(scope=IntelligenceScope.GLOBAL), {"g.1"})

    def test_global_cannot_see_personal_knowledge(self) -> None:
        self.assertNotIn("p.1", self._ids(scope=IntelligenceScope.GLOBAL))

    def test_an_app_sees_its_own_and_global(self) -> None:
        self.assertEqual(
            self._ids(scope=IntelligenceScope.APP, app_id="app-A"), {"g.1", "a.1"}
        )

    def test_an_app_cannot_see_another_app(self) -> None:
        self.assertNotIn("a.2", self._ids(scope=IntelligenceScope.APP, app_id="app-A"))

    def test_an_app_cannot_see_personal(self) -> None:
        self.assertNotIn("p.1", self._ids(scope=IntelligenceScope.APP, app_id="app-A"))

    def test_personal_sees_personal_and_global_only(self) -> None:
        self.assertEqual(
            self._ids(scope=IntelligenceScope.PERSONAL), {"g.1", "p.1"}
        )

    def test_app_knowledge_requires_an_app_id(self) -> None:
        """**app_idの無いApp Knowledgeを作らせない。**

        作れると、どのAppのものか分からないEntryがGlobalへ紛れ込む。
        """
        with self.assertRaises(ValueError):
            _entry("bad", scope=IntelligenceScope.APP)

    def test_global_knowledge_cannot_carry_an_app_id(self) -> None:
        with self.assertRaises(ValueError):
            _entry("bad", scope=IntelligenceScope.GLOBAL, app_id="app-A")


class TestDefaultsAreNotOptimistic(unittest.TestCase):
    def test_a_new_entry_is_a_draft(self) -> None:
        """**分からないものを「使ってよい」へ倒さない。**"""
        entry = KnowledgeEntry(entry_id="x", content="y")
        self.assertIs(entry.status, KnowledgeStatus.DRAFT)
        self.assertFalse(entry.status.is_retrievable)

    def test_a_draft_is_not_retrieved(self) -> None:
        store = KnowledgeStore()
        store.add(KnowledgeEntry(entry_id="x", content="y"))
        self.assertEqual(store.retrieve(), ())

    def test_residency_defaults_to_local_only(self) -> None:
        self.assertIs(KnowledgeEntry(entry_id="x", content="y").residency,
                      DataResidency.LOCAL_ONLY)

    def test_provenance_defaults_to_unknown(self) -> None:
        self.assertIs(KnowledgeEntry(entry_id="x", content="y").provenance,
                      TrainingProvenance.UNKNOWN)

    def test_deprecated_entries_are_kept_but_not_retrieved(self) -> None:
        """**消さずに残す。** 過去の生成物がこれを参照している。"""
        store = KnowledgeStore()
        store.add(_entry("old", status=KnowledgeStatus.DEPRECATED))
        self.assertEqual(store.retrieve(), ())
        self.assertIsNotNone(store.get("old"))


class TestEvidenceKeepsIdentifiersNotText(unittest.TestCase):
    """**raw retrieved text ではなく識別子だけ**（016 §12.1）。"""

    def test_a_reference_carries_the_id_and_version(self) -> None:
        entry = _entry("design_role.metric.primary", version=3)
        self.assertEqual(entry.reference, "design_role.metric.primary@v3")

    def test_the_context_dict_has_no_content(self) -> None:
        resolver = IntelligenceContextResolver(_store_with_secret())
        context = resolver.resolve(ForgeTask.COGNITIVE_STAGE)
        self.assertNotIn("この本文は外へ出てはいけない", repr(context.to_dict()))

    def test_the_context_exposes_references_only(self) -> None:
        resolver = IntelligenceContextResolver(_store_with_secret())
        context = resolver.resolve(ForgeTask.COGNITIVE_STAGE)
        self.assertEqual(set(context.to_dict()), {"scope", "app_id", "entry_count", "references"})


def _store_with_secret() -> KnowledgeStore:
    store = KnowledgeStore()
    store.add(_entry("design_role.metric.primary", content="この本文は外へ出てはいけない"))
    return store


class TestTheResolverDoesNotRankProviders(unittest.TestCase):
    """**責務を混ぜない**（017A §8）。AIRouterを神クラスにしない。"""

    def test_the_resolver_has_no_routing_methods(self) -> None:
        for forbidden in ("rank", "ranking_for", "order", "select_provider",
                          "generate", "bind", "candidates_for"):
            self.assertFalse(
                hasattr(IntelligenceContextResolver, forbidden),
                f"IntelligenceContextResolver に {forbidden} が生えている"
                "（Provider選択はAIRouterの仕事）",
            )

    def test_a_conversation_step_needs_no_design_vocabulary(self) -> None:
        """何を作るかを聞いている段階で、どう見せるかは決めていない。"""
        context = IntelligenceContextResolver(default_knowledge_store()).resolve(
            ForgeTask.CONVERSATION_STEP
        )
        self.assertTrue(context.is_empty)

    def test_not_every_entry_is_handed_over(self) -> None:
        """**全部渡さない。** 選択肢が多いとAIは外すし、Local Modelの
        文脈長を無駄に使う（014 §7と同じ理由）。"""
        store = default_knowledge_store()
        context = IntelligenceContextResolver(store).resolve(ForgeTask.ENTITY_SYNTHESIS)
        self.assertLess(len(context.entries), store.size())
        self.assertTrue(context.entries)


class TestForgeGlobalKnowledgeIsDerivedNotDuplicated(unittest.TestCase):
    def test_every_design_role_becomes_an_entry(self) -> None:
        from app.ai.runtime.design_language import knowledge_entries

        self.assertEqual(default_knowledge_store().size(), len(knowledge_entries()))

    def test_forge_written_knowledge_is_marked_synthetic(self) -> None:
        """**利用者データ由来ではない**ことを記録で言えること。"""
        for entry in default_knowledge_store().retrieve():
            with self.subTest(entry=entry.entry_id):
                self.assertIs(entry.provenance, TrainingProvenance.FORGE_SYNTHETIC)
                self.assertNotEqual(entry.provenance, TrainingProvenance.FORGE_USER_DATA)

    def test_no_entry_leaves_the_device_by_default(self) -> None:
        for entry in default_knowledge_store().retrieve():
            with self.subTest(entry=entry.entry_id):
                self.assertIs(entry.residency, DataResidency.LOCAL_ONLY)


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestKnowledgeReachesProduction(unittest.TestCase):
    """**本番から呼ばれること**（TD69の再発防止）。

    `knowledge_entries()`は014から存在したが、本番から1度も呼ばれて
    いなかった。型を作っただけで終わらせない。
    """

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.store = default_generation_store()
        self.store.reset()

    def _generate(self) -> None:
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": "家計の収入と支出を記録したい",
                            "generation_options": {"provider": "mock"}}},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_a_generation_records_which_knowledge_it_used(self) -> None:
        self._generate()
        record = self.store.all_records()[0]
        self.assertTrue(
            record.knowledge_references,
            "生成物のEvidenceに知識の参照が1件も無い（Knowledgeが本番から呼ばれていない）",
        )

    def test_the_references_carry_a_version(self) -> None:
        """知識を直した後で「どの版で作られたか」を辿れること。"""
        self._generate()
        for reference in self.store.all_records()[0].knowledge_references:
            with self.subTest(reference=reference):
                self.assertRegex(reference, r"@v\d+$")

    def test_the_evidence_never_carries_the_knowledge_text(self) -> None:
        """**識別子だけ**（016 §12.1）。"""
        self._generate()
        dumped = repr([r.to_dict() for r in self.store.all_records()])
        for phrase in ("使うとき:", "避けるとき:", "その画面で一番大事"):
            self.assertNotIn(phrase, dumped)


if __name__ == "__main__":
    unittest.main()
