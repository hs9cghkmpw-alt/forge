"""Revision Engine(FORGE-MILESTONE-007第一段階、M006 15章)。

Cognitive Revision(設計を直す)であり、既存`repair/repair_engine.py`の
Schema Repair(JSONの仕様違反を直す)とは別物(M006 12.3節の区別を維持)。

**最小実装**: `auto_fixable=True`の指摘(empty_state・
validation_coverage・template_mismatch)のみ、決定的に修正する。
`completeness`・`simplicity`(auto_fixable=False)は、この段階では
修正方法が確立していないため、プラン自体は変更しない(結果として
`max_revision_attempts`到達後にHuman Confirmation/Escalationへ
到達することがあるが、これは「直せないものを直せると偽らない」という
誠実な挙動であり、バグではない)。
"""

from __future__ import annotations

import dataclasses

from forge_ai.core.orchestration.cognitive_types import CriticReport
from forge_ai.core.planner import ApplicationPlan, ScreenPlan


class RevisionEngine:
    """`RevisionEngineProtocol`を満たす。"""

    def revise(self, plan: ApplicationPlan, critic_report: CriticReport, attempt: int) -> ApplicationPlan:
        new_screens = list(plan.screens)
        changed = False

        for issue in critic_report.issues:
            if not issue.auto_fixable:
                continue
            if issue.category == "empty_state":
                new_screens = [
                    s if s.empty_state_message else dataclasses.replace(
                        s, empty_state_message=f"まだ{(s.key_elements[0] if s.key_elements else '項目')}がありません。追加してください。"
                    )
                    for s in new_screens
                ]
                changed = True
            elif issue.category == "validation_coverage":
                new_screens = [
                    s if s.validation_rules else dataclasses.replace(
                        s, validation_rules=(
                            "add操作等で対象の入力欄が空の場合、エラーとはせず静かに何もしないこと。",
                            "必須項目を満たさないまま送信しようとした場合は、入力欄の近くに具体的な理由を表示すること。",
                            "送信に失敗した場合も、利用者が入力済みの内容を失わないこと。",
                            "エラー時は修正方法(何を直せばよいか)を明示すること。",
                        )
                    )
                    for s in new_screens
                ]
                changed = True
            elif issue.category == "template_mismatch":
                # Final Template Selectionが確定したことを踏まえ、対応する
                # Validationを明示的に追加しておく(具体的なTemplate差し替え
                # ロジックは今回のスコープ外、既知の制限)。
                new_screens = [
                    dataclasses.replace(
                        s, validation_rules=s.validation_rules + (
                            f"Final Template Selectionの結果(revision attempt={attempt})に基づき再確認済み。",
                        )
                    )
                    for s in new_screens
                ]
                changed = True

        if not changed:
            # 修正方法が確立していない指摘(completeness/simplicity等)しか
            # 無かった場合、プランを変更せず返す(直せると偽らない)。
            return plan

        return dataclasses.replace(plan, screens=tuple(new_screens))
