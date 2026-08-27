"""**Capability を落とさない Plan**（FORGE-020A2 §2、2026-08-26）。

---

## 修正前に測った実際の結果

`PlanShape` が排他的な enum だったため、複数の見せ方を求められると
**後ろが黙って捨てられていた**。修正前に本番のコードで実測した:

```
「部署ごとの売上を比較して、合計と月別推移も見たい」
  役 : group_by, compare, total, trend        ← 4つ要求している
  shape: record_log_with_group_compare
  views: ('view.list', 'view.group_compare')  ← total と trend が消えた

「支出の合計と月別推移が見たい」
  役 : total, trend
  views: ('view.list', 'view.trend')          ← total が消えた

「作業を記録して、担当者で絞り込んで、チームごとに比べたい」
  役 : filter, group_by, compare
  shape: unknown
  views: ('view.list',)                       ← compare も filter も消えた
```

**利用者が言ったことの半分が、どこにも記録されずに消えていた。**
「出来ない」とすら言われない——`unsupported` にも入らない。

## 直し方: enum を増やさない

`RECORD_LOG_WITH_TOTAL_AND_TREND` を足すのは禁止である。組み合わせの
数だけ enum が増え、5つ目の view で破綻する。

**直交する成分に分ける。**

* `StructuralMode` — どういうデータ構造か（CHECKLIST / RECORD_ENTITY）
* `views` — 何を見たいか（**集合**。1つ選ばない）
* `interactions` / `effects` / `missing` / `partial`

「どういう構造か」と「何を見たいか」は別の軸である。
"""

from __future__ import annotations

import unittest

from forge_ai.core.semantics.capability_plan import (
    StructuralMode,
    plan_capabilities,
)

COMPARE_TOTAL_TREND = "部署ごとの売上を比較して、合計と月別推移も見たい"
TOTAL_AND_TREND = "支出の合計と月別推移が見たい"
FILTER_AND_COMPARE = "作業を記録して、担当者で絞り込んで、チームごとに比べたい"


class TestNoRequestedViewIsSilentlyDropped(unittest.TestCase):
    """**言われたことを黙って捨てない。**"""

    def test_compare_total_and_trend_all_survive(self) -> None:
        """修正前は `view.list` と `view.group_compare` しか残らなかった。"""
        plan = plan_capabilities(COMPARE_TOTAL_TREND)
        for view in ("view.list", "view.group_compare", "view.metric", "view.trend"):
            with self.subTest(view=view):
                self.assertIn(view, plan.views, plan.views)

    def test_total_and_trend_both_survive(self) -> None:
        """修正前は `view.trend` が `view.metric` を潰していた。"""
        plan = plan_capabilities(TOTAL_AND_TREND)
        self.assertIn("view.metric", plan.views, plan.views)
        self.assertIn("view.trend", plan.views, plan.views)

    def test_an_unknown_combination_does_not_drop_half_of_it(self) -> None:
        """絞り込み + 比較。**片方だけ消えない。**

        `view.group_compare` は作れる。`interact.filter` は作れない——
        だから `missing` に**名指しで**入る。消えるのとは違う。
        """
        plan = plan_capabilities(FILTER_AND_COMPARE)
        self.assertIn("view.group_compare", plan.views, plan.views)
        self.assertIn(
            "interact.filter", plan.missing,
            f"作れないものが missing にも views にも無い: {plan.to_dict()}",
        )

    def test_everything_requested_is_accounted_for(self) -> None:
        """**要求は必ずどこかに現れる。** 出来た / 一部 / 出来ない、のどれか。"""
        for need in (COMPARE_TOTAL_TREND, TOTAL_AND_TREND, FILTER_AND_COMPARE):
            with self.subTest(need=need):
                plan = plan_capabilities(need)
                accounted = set(plan.requested)
                resolved = (
                    set(plan.views) | set(plan.interactions) | set(plan.effects)
                    | set(plan.missing) | set(plan.partial)
                    | set(plan.structure_capabilities)
                    | {f.capability for f in plan.fields}
                )
                self.assertEqual(
                    accounted - resolved, set(),
                    "要求されたのに、出来たとも出来ないとも記録されていない",
                )


class TestStructureAndViewsAreOrthogonal(unittest.TestCase):
    """**「どういう構造か」と「何を見たいか」を混ぜない。**"""

    def test_structural_mode_has_no_view_names(self) -> None:
        """組み合わせ enum を増やしていないこと。"""
        for mode in StructuralMode:
            for word in ("total", "trend", "compare", "chart", "metric", "with"):
                self.assertNotIn(
                    word, mode.value,
                    f"StructuralMode に view が混ざっている: {mode.value}",
                )

    def test_the_structural_vocabulary_stays_small(self) -> None:
        """view を足すたびに構造が増える設計になっていないこと。"""
        self.assertLessEqual(len(StructuralMode), 4, tuple(StructuralMode))

    def test_a_record_need_is_a_record_entity_whatever_the_views(self) -> None:
        for need in (COMPARE_TOTAL_TREND, TOTAL_AND_TREND, FILTER_AND_COMPARE):
            with self.subTest(need=need):
                self.assertIs(
                    plan_capabilities(need).structure, StructuralMode.RECORD_ENTITY,
                )

    def test_a_checklist_is_a_checklist_whatever_the_views(self) -> None:
        plan = plan_capabilities("今日やる作業を登録して、終わったものを消していきたい")
        self.assertIs(plan.structure, StructuralMode.CHECKLIST)

    def test_order_does_not_change_the_plan(self) -> None:
        """同じ意味なら同じ Plan（順序に依存しない）。"""
        first = plan_capabilities("売上を部署ごとに比べて、合計も見たい")
        second = plan_capabilities("売上の合計も見たいし、部署ごとに比べたい")
        self.assertEqual(set(first.views), set(second.views))
        self.assertIs(first.structure, second.structure)


class TestEveryCapabilityIdIsCanonical(unittest.TestCase):
    """**Plan が使う ID は Catalog に在るものだけ**（020A2 §1）。"""

    def test_no_plan_invents_a_capability_id(self) -> None:
        from forge_ai.core.semantics.capabilities import is_known_capability

        needs = (
            COMPARE_TOTAL_TREND, TOTAL_AND_TREND, FILTER_AND_COMPARE,
            "旅行の写真を日付ごとに残してメモを付けたい",
            "植物を育てながら音を組み合わせるゲームを作りたい",
            "子どもが朝の支度をひとつずつチェックできるようにしたい",
            "英単語を出題して、正解率の推移を見たい",
        )
        for need in needs:
            plan = plan_capabilities(need)
            everything = (
                set(plan.requested) | set(plan.views) | set(plan.interactions)
                | set(plan.effects) | set(plan.missing) | set(plan.partial)
                | set(plan.structure_capabilities)
                | {f.capability for f in plan.fields}
            )
            for capability_id in everything:
                with self.subTest(need=need, capability=capability_id):
                    self.assertTrue(
                        is_known_capability(capability_id),
                        f"Catalog に無い ID: {capability_id}",
                    )


if __name__ == "__main__":
    unittest.main()


class TestLayoutComesFromCapabilityComposition(unittest.TestCase):
    """**同じ record entity でも、Capability の構成で性格が変わる**
    （TD91 / 020A2 §6）。

    R4 では record entity のアプリが**全部「追加」タブで始まって**いた。
    Shape の違いは一覧タブ側にあるので、**開いた瞬間には区別が付かなかった**。

    専用の photo UI / analytics UI は作らない。
    """

    def test_each_composition_gets_its_own_emphasis(self) -> None:
        from forge_ai.core.ir.capability_ir import LayoutEmphasis, compose_layout

        expected = {
            "部署ごとの売上を月別に集計してグラフで比べたい":
                LayoutEmphasis.COMPARISON_FIRST,
            "英単語を出題して、正解率の推移を見たい": LayoutEmphasis.SUMMARY_FIRST,
            "毎日の収入と支出を記録して残高を見たい": LayoutEmphasis.SUMMARY_FIRST,
            "旅行の写真を日付ごとに残してメモを付けたい": LayoutEmphasis.MEDIA_FIRST,
            "釣った場所を地図に残して魚の種類を記録したい": LayoutEmphasis.INPUT_FIRST,
            "今日やる作業を登録して、終わったものを消していきたい":
                LayoutEmphasis.TASK_FIRST,
            "ぷるぷるした何か": LayoutEmphasis.NONE,
        }
        for need, emphasis in expected.items():
            with self.subTest(need=need):
                self.assertIs(compose_layout(plan_capabilities(need)), emphasis)

    def test_group_by_alone_is_not_a_comparison(self) -> None:
        """**「日付ごとに残して」は比較の要求ではない。**

        ここを同じ扱いにしていたので、写真アプリが comparison-first の
        画面になっていた（020A2 §6 の実装中に気付いた）。
        """
        self.assertNotIn(
            "view.group_compare", plan_capabilities("写真を日付ごとに残したい").views,
        )
        self.assertIn(
            "view.group_compare",
            plan_capabilities("売上を部署ごとに比べたい").views,
        )

    def test_no_emphasis_is_named_after_a_need(self) -> None:
        from forge_ai.core.ir.capability_ir import LayoutEmphasis

        for emphasis in LayoutEmphasis:
            for word in ("kids", "photo", "analytics", "game", "study", "finance"):
                self.assertNotIn(word, emphasis.value)

    def test_the_compiler_and_the_emphasis_enum_agree(self) -> None:
        """Compiler は Capability 層を import しない。**値で照合する。**"""
        from forge_ai.core.ir.capability_ir import LayoutEmphasis
        from forge_ai.core.ir.forge_language_compiler import (
            _SUMMARY_LEADING_EMPHASES,
        )

        known = {e.value for e in LayoutEmphasis}
        self.assertTrue(
            _SUMMARY_LEADING_EMPHASES <= known,
            f"Compiler が知らない emphasis を見ている: "
            f"{_SUMMARY_LEADING_EMPHASES - known}",
        )
