"""Forge Native AI v0 — Rule Based Planner(`_02_planner`)。

IntentIRから、PlanIR(`app.ai.foundation.interfaces.PlanIR`)を構築する、
**実際に動作する**ルールベースの実装。推論は行わない。

Screen/State/Action/Widgetの具体的な構造そのものは、この段階では
まだ決めない(それはTemplate/Generatorの責務)。Plannerが決めるのは
「何画面必要か」「各画面の目的・必要データ・必要操作」という、
Forge Widget非依存な設計レベルの決定である
(`docs/spec/AI_RUNTIME.md`の「PlannerはRuntimeを知らない」原則、
forge_ai/core/planner.pyと同じ設計原則を踏襲する)。
"""

from __future__ import annotations

from app.ai.foundation.interfaces import IntentIR, PlanIR, ScreenPlan


class RuleBasedPlanner:
    """IntentIR.output_typeから、必要な画面数・画面ごとの目的を
    決定的に導出する。"""

    def plan(self, intent: IntentIR) -> PlanIR:
        if intent.output_type == "form":
            return self._plan_form(intent)
        # checklist・memoはいずれも単一画面。
        return self._plan_single_screen(intent)

    def _plan_single_screen(self, intent: IntentIR) -> PlanIR:
        screen = ScreenPlan(
            screen_id="generated_screen",
            purpose=intent.purpose,
            data_needed=intent.entities,
            actions_needed=("add_item",) if intent.output_type == "checklist" else (),
            empty_state_needed=(intent.output_type == "checklist"),
            error_state_needed=False,
        )
        return PlanIR(screens=(screen,), navigation_edges=(), template_hint=intent.output_type)

    def _plan_form(self, intent: IntentIR) -> PlanIR:
        main_screen = ScreenPlan(
            screen_id="generated_screen",
            purpose=intent.purpose,
            data_needed=intent.entities,
            actions_needed=("submit_form",),
            empty_state_needed=False,
            error_state_needed=True,
        )
        thanks_screen = ScreenPlan(
            screen_id="thanks_screen",
            purpose="送信完了を伝える",
            data_needed=(),
            actions_needed=("go_back",),
            empty_state_needed=False,
            error_state_needed=False,
        )
        return PlanIR(
            screens=(main_screen, thanks_screen),
            navigation_edges=(("generated_screen", "thanks_screen"),),
            template_hint="form",
        )
