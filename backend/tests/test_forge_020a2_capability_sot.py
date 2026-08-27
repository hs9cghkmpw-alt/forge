"""**Capability の Source of Truth が1つであること**（FORGE-020A2 §1）。

---

## 何を防いでいるか

R4 の時点で、同じ「Forge Capability」に表が2つあった。

| | 場所 | 例 |
|---|---|---|
| A | `backend/app/ai/runtime/capability.py` | `data.photo` / `effect.notify` |
| B | `forge_ai/core/semantics/capability_plan.py` | `record.photo` / `interact.notify` |

**会話が「写真は作れない」と言い、生成が別 ID で「partial」と言う。**
どちらが正なのか誰も答えられない状態だった。片方だけ直せば静かに食い違う。

このテストは、**2つ目の表が生えてこないこと**を機械的に固定する。
人が2箇所を見比べて揃える運用は、二重表そのものである。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# `forge_ai` は repository 直下にある（backend からの相対で2つ上）。
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.runtime.capability import (  # noqa: E402
    CAPABILITY_REGISTRY,
    _RUNTIME_BINDINGS,
)
from app.ai.validators.schema_validator import WIDGET_TYPES_ALL  # noqa: E402
from forge_ai.core.semantics.capabilities import (  # noqa: E402
    SEMANTIC_CAPABILITIES,
    SafetyClass,
    SupportLevel,
)
from forge_ai.core.semantics.capability_plan import plan_capabilities  # noqa: E402

#: Quality Gate v2 の8 Need（絵とテストが同じ入力を見る）。
NEEDS = (
    "毎日の収入と支出を記録して残高を見たい",
    "今日やる作業を登録して、終わったものを消していきたい",
    "子どもが朝の支度をひとつずつチェックできるようにしたい",
    "旅行の写真を日付ごとに残してメモを付けたい",
    "釣った場所を地図に残して魚の種類を記録したい",
    "植物を育てながら音を組み合わせるゲームを作りたい",
    "部署ごとの売上を月別に集計してグラフで比べたい",
    "英単語を出題して、正解率の推移を見たい",
)


class TestThereIsOnlyOneCatalog(unittest.TestCase):
    def test_the_runtime_adapter_declares_no_capability_of_its_own(self) -> None:
        """**Adapter に Catalog に無い ID があってはならない。**"""
        unknown = set(_RUNTIME_BINDINGS) - set(SEMANTIC_CAPABILITIES)
        self.assertEqual(
            unknown, set(),
            f"Runtime だけが知っている Capability がある（2つ目の表）: {sorted(unknown)}",
        )

    def test_every_registry_entry_comes_from_the_catalog(self) -> None:
        self.assertEqual(set(CAPABILITY_REGISTRY), set(SEMANTIC_CAPABILITIES))

    def test_the_generation_plan_uses_only_catalog_ids(self) -> None:
        """**生成側も同じ ID を読む。**"""
        for need in NEEDS:
            plan = plan_capabilities(need)
            everything = (
                set(plan.requested) | set(plan.views) | set(plan.interactions)
                | set(plan.effects) | set(plan.missing) | set(plan.partial)
                | set(plan.structure_capabilities)
                | {f.capability for f in plan.fields}
            )
            for capability_id in sorted(everything):
                with self.subTest(need=need, capability=capability_id):
                    self.assertIn(capability_id, SEMANTIC_CAPABILITIES)

    def test_no_alias_pair_survives(self) -> None:
        """**同じ意味の ID を2つ持たない。**

        R4 が持っていた別名（`record.photo` / `interact.notify` /
        `view.total` / `media.compose`）が復活していないこと。
        """
        for alias in ("record.photo", "record.text", "record.sound", "record.entity",
                      "interact.notify", "view.total", "media.compose"):
            with self.subTest(alias=alias):
                self.assertNotIn(alias, SEMANTIC_CAPABILITIES)


class TestConversationAndGenerationSeeTheSameId(unittest.TestCase):
    """**photo / notify / trend で会話と生成が同じ ID を見る**（§1 の要求）。"""

    def test_photo(self) -> None:
        plan = plan_capabilities("旅行の写真を日付ごとに残してメモを付けたい")
        self.assertIn("data.photo", plan.partial)
        self.assertIn("data.photo", CAPABILITY_REGISTRY)
        self.assertFalse(CAPABILITY_REGISTRY["data.photo"].supported)

    def test_notify(self) -> None:
        plan = plan_capabilities("期限が近づいたら通知してほしい")
        self.assertIn("effect.notify", plan.missing)
        self.assertIn("effect.notify", CAPABILITY_REGISTRY)
        self.assertTrue(CAPABILITY_REGISTRY["effect.notify"].requires_confirmation)

    def test_trend(self) -> None:
        plan = plan_capabilities("英単語を出題して、正解率の推移を見たい")
        self.assertIn("view.trend", plan.views)
        self.assertIn("view.trend", plan.partial)
        self.assertIn("view.trend", CAPABILITY_REGISTRY)


class TestSupportAndBindingCannotDisagree(unittest.TestCase):
    """**支援の度合いと Widget の結び付きを、人が見比べて揃えない。**"""

    def test_implemented_capabilities_have_a_real_widget(self) -> None:
        for definition in SEMANTIC_CAPABILITIES.values():
            if definition.support is not SupportLevel.IMPLEMENTED:
                continue
            with self.subTest(capability=definition.id):
                widgets = _RUNTIME_BINDINGS.get(definition.id, ())
                self.assertTrue(
                    widgets, "IMPLEMENTED と宣言したのに Widget が無い",
                )
                for widget in widgets:
                    self.assertIn(widget, WIDGET_TYPES_ALL, f"{definition.id} -> {widget}")

    def test_missing_capabilities_have_no_widget(self) -> None:
        for definition in SEMANTIC_CAPABILITIES.values():
            if definition.support is not SupportLevel.MISSING:
                continue
            with self.subTest(capability=definition.id):
                self.assertEqual(
                    _RUNTIME_BINDINGS.get(definition.id, ()), (),
                    "MISSING と宣言したのに Widget と結び付いている",
                )

    def test_confirmation_is_derived_from_the_safety_class(self) -> None:
        """**確認 Policy を2箇所で手管理しない。**"""
        for definition in SEMANTIC_CAPABILITIES.values():
            with self.subTest(capability=definition.id):
                self.assertEqual(
                    CAPABILITY_REGISTRY[definition.id].requires_confirmation,
                    definition.safety is SafetyClass.SENSITIVE,
                )

    def test_supported_is_derived_from_the_support_level(self) -> None:
        for definition in SEMANTIC_CAPABILITIES.values():
            with self.subTest(capability=definition.id):
                self.assertEqual(
                    CAPABILITY_REGISTRY[definition.id].supported,
                    definition.support is SupportLevel.IMPLEMENTED,
                )


class TestTheAdapterHoldsNoSemantics(unittest.TestCase):
    """**Adapter に意味を書き戻せないこと。**"""

    def test_the_adapter_module_declares_no_labels_or_keywords(self) -> None:
        """静的検査。`label_ja=` / `detection_keywords=` の**定義**が
        Adapter に無いこと（Catalog から引くだけであること）。"""
        import pathlib

        source = (
            pathlib.Path(__file__).resolve().parents[1]
            / "app" / "ai" / "runtime" / "capability.py"
        ).read_text(encoding="utf-8")
        # `_binding()` が Catalog から写す1箇所だけが許される。
        self.assertEqual(
            source.count("label_ja="), 1,
            "Adapter が独自のラベルを持っている（2つ目の表）",
        )
        self.assertEqual(
            source.count("detection_keywords="), 1,
            "Adapter が独自の検出語を持っている（2つ目の表）",
        )


if __name__ == "__main__":
    unittest.main()
