"""Repair Engine。

Validator結果(既存Backendの`schema_validator.py`ではなく、forge_ai/自身が
定義する軽量な`RepairIssue`)を受け取り、Forge IRを自己修正する。
複数回実行可能(呼び出し側が`max_iterations`まで繰り返し呼べる)。

forge_ai/はBackendのValidatorを一切importしない(Runtime非依存の方針)。
将来Runtime接続する際は、Backendの`ValidationIssue`を`RepairIssue`へ
変換するアダプタを別途用意する想定(IMPLEMENTATION_REPORT.mdに記録)。
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRStateValue
from forge_ai.prompt.prompt_builder import PromptBuilder
from forge_ai.provider.provider_interface import AIProvider


@dataclass(frozen=True)
class RepairIssue:
    """forge_ai/自身が定義する、Validatorに依存しない軽量な問題表現。"""

    path: str
    category: str
    message: str


@dataclass(frozen=True)
class RepairResult:
    """1回(または複数回)のrepair呼び出しの結果。"""

    ir: ForgeIRDocument
    fixed_issues: tuple[RepairIssue, ...]
    remaining_issues: tuple[RepairIssue, ...]
    iterations: int


class RepairEngine:
    """既知パターンは決定的に修正し、それ以外はProviderへ修正方針を尋ねる
    (ただし今回のMockProviderは修正内容そのものを生成しない。
    「どの問題に対応したか」という数量情報のみ返す簡易実装。
    実際のLLM接続後、Provider側が修正案そのものを返す拡張を想定)。
    """

    def __init__(self, provider: AIProvider, prompt_builder: PromptBuilder | None = None, max_iterations: int = 2) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._max_iterations = max_iterations

    def repair(self, ir: ForgeIRDocument, issues: tuple[RepairIssue, ...]) -> RepairResult:
        """Forge IRとissuesから、最大max_iterations回まで修正を試みる。
        1回のイテレーションで1件も直せなかった場合は、それ以上繰り返さず
        打ち切る(無限リトライ防止。禁止事項11章)。"""
        if not issues:
            # 直すべき問題が無ければ、ループへ入る前に0イテレーションで確定させる。
            # (forループの反復変数はbodyの実行前に代入されるため、breakだけに
            # 頼るとiterations=1と誤って報告されるバグがあった。テストで発見・修正)
            return RepairResult(ir=ir, fixed_issues=(), remaining_issues=(), iterations=0)

        current_ir = ir
        remaining = list(issues)
        fixed: list[RepairIssue] = []
        iteration = 0

        for iteration in range(1, self._max_iterations + 1):
            if not remaining:
                break

            prompt = self._prompt_builder.build_repair_prompt(
                ir_summary={"version": current_ir.version, "screen_count": len(current_ir.screens)},
                issues=tuple({"path": i.path, "category": i.category, "message": i.message} for i in remaining),
            )
            self._provider.complete(prompt)  # Mock実装では戻り値は使わず、決定的修正のみ行う

            before_count = len(remaining)
            still_remaining: list[RepairIssue] = []
            for issue in remaining:
                fixed_ir = self._try_fix(current_ir, issue)
                if fixed_ir is not None:
                    current_ir = fixed_ir
                    fixed.append(issue)
                else:
                    still_remaining.append(issue)
            remaining = still_remaining

            if len(remaining) == before_count:
                # 今回のイテレーションで1件も直せなかった = これ以上繰り返しても
                # 無駄なので打ち切る(無限リトライ防止)。
                break

        return RepairResult(
            ir=current_ir,
            fixed_issues=tuple(fixed),
            remaining_issues=tuple(remaining),
            iterations=iteration,
        )

    def _try_fix(self, ir: ForgeIRDocument, issue: RepairIssue) -> ForgeIRDocument | None:
        """既知の問題カテゴリだけを決定的に修正する。未知のカテゴリはNoneを返し
        (修正できなかったことを示す)、クラッシュさせない。"""
        if issue.category == "missing_app_title":
            fallback_title = ir.screens[0].title if ir.screens else "新しいアプリ"
            return replace(ir, app_title=fallback_title)

        if issue.category == "empty_checklist_state" and ir.screens:
            screen = ir.screens[0]
            new_state = dict(screen.state)
            for key, value in new_state.items():
                if value.type == "checklist" and not value.value:
                    new_state[key] = ForgeIRStateValue(
                        type="checklist",
                        value=[{"id": "item_1", "text": "最初のアイテム", "done": False}],
                    )
            new_screen = replace(screen, state=new_state)
            new_screens = (new_screen,) + ir.screens[1:]
            return replace(ir, screens=new_screens)

        return None
