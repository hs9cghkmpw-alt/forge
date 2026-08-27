"""Capability ID の正しさを**機械が見る**（020A3B §4）。

---

## 未知の semantic ID は「作れないこと」ではない

以前 `_classify()` は、Catalog に無い ID を **MISSING** にしていた。
一見安全に見えるが、起きているのは大抵**綴り間違い**か
**Catalog への足し忘れ**である。

MISSING へ倒すと3つ壊れる。

1. 利用者へ「それは作れません」と**嘘**を言う
2. `capability_gap` の説明文に内部 ID が出る
3. Catalog への追加漏れが**永久に気付かれない**

だから落とす（`UnknownCapabilityError`）。

## 責務ごとに namespace を分ける

| 成分 | namespace |
|---|---|
| `fields` / `structure_capabilities` | `data.*` |
| `views` | `view.*` |
| `interactions` | `interact.*` |
| `effects` | `effect.*` |
| 実行時のふるまい | `simulate.*` |

> **注（020A3B）**: 指示書は fields を `record.*`、合成を `media.*` と
> 書いていた。それは 020A3 branch の綴りであり、merge 済みの正典
> （`forge_ai/core/semantics/capabilities.py`）は `data.*` /
> `effect.media_compose` である。**綴りではなく「責務ごとに分ける」
> という要件をここで固定する。** 綴りを揃え直す判断は CEO のもの。

## 置物にしない

`effects` は今のところ必ず空である（`effect.*` は8件とも未実装）。
**空だから Evidence から落としてよい、ではない。** 1つ実装された日に
「ここへ足す」のを忘れないよう、**成分を落としたら落ちる**形にする。
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from forge_ai.core.semantics.capabilities import (  # noqa: E402
    SEMANTIC_CAPABILITIES,
    CapabilityLayer,
)
from forge_ai.core.semantics.capability_plan import (  # noqa: E402
    UnknownCapabilityError,
    _classify,
    plan_capabilities,
)

#: Quality Gate v2 の8つ + 効果や実行時のふるまいを求める Need。
NEEDS: tuple[str, ...] = (
    "毎日の収入と支出を記録して残高を見たい",
    "今日やる作業を登録して、終わったものを消していきたい",
    "子どもが朝の支度をひとつずつチェックできるようにしたい",
    "旅行の写真を日付ごとに残してメモを付けたい",
    "釣った場所を地図に残して魚の種類を記録したい",
    "植物を育てながら音を組み合わせるゲームを作りたい",
    "部署ごとの売上を月別に集計してグラフで比べたい",
    "英単語を出題して、正解率の推移を見たい",
    "部署ごとの売上を比較して、合計と月別推移も見たい",
    "買った物を家族に共有したい",
    "薬を飲む時間に通知してほしい",
    "血圧を記録して、値の推移をカレンダーで見たい",
)


def _plan_components(plan) -> dict[str, tuple[str, ...]]:  # noqa: ANN001
    """Plan が持つ **Capability ID の成分**すべて。

    新しい成分を足したらここへ足す——足さなければ下のテストが
    「Evidence へ届いていない」で落ちる。
    """
    return {
        "fields": tuple(f.capability for f in plan.fields),
        "structure_capabilities": tuple(plan.structure_capabilities),
        "views": tuple(plan.views),
        "interactions": tuple(plan.interactions),
        "effects": tuple(plan.effects),
        "partial": tuple(plan.partial),
        "missing": tuple(plan.missing),
        "requested": tuple(plan.requested),
    }


class TestEveryPlannedIdExistsInTheCatalog(unittest.TestCase):
    """**Plan が出せる ID は、必ず正典にある。**"""

    def test_no_need_produces_an_id_outside_the_catalog(self) -> None:
        for need in NEEDS:
            plan = plan_capabilities(need)
            for component, ids in _plan_components(plan).items():
                for capability_id in ids:
                    with self.subTest(need=need, component=component, id=capability_id):
                        self.assertIn(
                            capability_id, SEMANTIC_CAPABILITIES,
                            "Catalog に無い ID を Plan が作っている",
                        )

    def test_an_unknown_id_is_an_error_not_a_missing_capability(self) -> None:
        """**黙って MISSING にしない。**"""
        with self.assertRaises(UnknownCapabilityError) as caught:
            _classify({"interact.notify"})
        self.assertEqual(caught.exception.capability_id, "interact.notify")

    def test_the_error_names_the_catalog_so_it_can_be_fixed(self) -> None:
        with self.assertRaises(UnknownCapabilityError) as caught:
            _classify({"view.sparkline"})
        self.assertIn("capabilities.py", str(caught.exception))

    def test_a_known_id_still_classifies_normally(self) -> None:
        """弾きすぎて正常な ID まで落とさないこと。"""
        ok, partial, missing = _classify({"view.list", "data.photo", "simulate.loop"})
        self.assertIn("view.list", ok)
        self.assertIn("data.photo", partial)
        self.assertIn("simulate.loop", missing)


class TestNamespacesFollowResponsibility(unittest.TestCase):
    """成分と namespace が対応していること。"""

    _EXPECTED_PREFIX = {
        "fields": "data.",
        "structure_capabilities": "data.",
        "views": "view.",
        "interactions": "interact.",
        "effects": "effect.",
    }

    def test_each_component_only_holds_its_own_namespace(self) -> None:
        for need in NEEDS:
            plan = plan_capabilities(need)
            components = _plan_components(plan)
            for component, prefix in self._EXPECTED_PREFIX.items():
                for capability_id in components[component]:
                    with self.subTest(need=need, component=component, id=capability_id):
                        self.assertTrue(
                            capability_id.startswith(prefix),
                            f"{component} に {prefix} 以外が入っている",
                        )

    def test_the_catalog_layer_matches_the_namespace(self) -> None:
        """**正典の中でも**、層と namespace がずれていないこと。"""
        expected = {
            CapabilityLayer.DATA: "data.",
            CapabilityLayer.VIEW: "view.",
            CapabilityLayer.INTERACT: "interact.",
            CapabilityLayer.EFFECT: "effect.",
            CapabilityLayer.SIMULATE: "simulate.",
        }
        for capability_id, definition in SEMANTIC_CAPABILITIES.items():
            with self.subTest(capability=capability_id):
                self.assertTrue(
                    capability_id.startswith(expected[definition.layer]),
                    f"{capability_id} の層は {definition.layer.value} なのに"
                    f" namespace が違う",
                )

    def test_runtime_behaviour_lives_in_its_own_namespace(self) -> None:
        """実行時のふるまいを `effect.*` へ紛れ込ませない。"""
        simulate = [
            c for c, d in SEMANTIC_CAPABILITIES.items()
            if d.layer is CapabilityLayer.SIMULATE
        ]
        self.assertTrue(simulate, "SIMULATE 層が空になっている")
        for capability_id in simulate:
            self.assertTrue(capability_id.startswith("simulate."))


class TestNoPlanComponentIsAnOrnament(unittest.TestCase):
    """**Plan にあって Evidence に無い成分を作らない。**

    `effects` は今のところ必ず空だが、`_capabilities_used()` が
    読んでいなければ、実装された日に黙って落ちる。
    """

    def setUp(self) -> None:
        from app.ai.runtime.prompt_pipeline import _capabilities_used

        self._used = _capabilities_used

    class _Context:
        def __init__(self, plan) -> None:  # noqa: ANN001
            self.capability_plan = plan

    def test_every_component_reaches_the_evidence(self) -> None:
        for need in NEEDS:
            plan = plan_capabilities(need)
            recorded = set(self._used(self._Context(plan)))
            bare = {
                name.removeprefix("partial:").removeprefix("unsupported:")
                for name in recorded
            }
            for component in ("fields", "structure_capabilities", "views",
                             "interactions", "effects"):
                for capability_id in _plan_components(plan)[component]:
                    with self.subTest(need=need, component=component, id=capability_id):
                        self.assertIn(
                            capability_id, bare,
                            f"{component} が Evidence へ届いていない",
                        )

    def test_the_effects_component_is_read_at_all(self) -> None:
        """**空でも読んでいることを確かめる。**

        実データでは常に空なので、`effects` を持つ Plan を作って
        「読んでいるか」だけを見る。読んでいなければ、`effect.*` が
        1つ実装された日に黙って落ちる。
        """
        plan = plan_capabilities("毎日の収入と支出を記録して残高を見たい")
        with_effect = plan.__class__(
            **{**plan.__dict__, "effects": ("effect.share",)},
        )
        self.assertIn("effect.share", set(self._used(self._Context(with_effect))))


if __name__ == "__main__":
    unittest.main()
