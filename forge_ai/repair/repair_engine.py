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

from forge_ai.core.compiler import ForgeIRDocument
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
        (修正できなかったことを示す)、クラッシュさせない。

        FORGE-AI-QUALITY-001(2026-08-11)で発見・修正した実バグ:
        `backend/app/ai/runtime/forge_ai_adapter.py`の`to_repair_issues()`
        が、以前は`issue.category`へ`ValidationIssue.category`(Category
        enum、`"schema"`等4値のみ)を渡していたため、ここで判定していた
        `"missing_app_title"`・`"empty_checklist_state"`のどちらとも
        一度も一致せず、**Repair Loopは本番経路で呼ばれてはいたが、実際の
        Validator不合格を一度も修正できていなかった**(TD17・TD31参照)。
        アダプター側を`e.rule`(具体的なルール名)を渡すよう修正した上で、
        ここも実際に`schema_validator.py`が生成する具体的なrule名
        (`"string_length"`)+path(`/app/title`)で判定するよう修正した。

        `"empty_checklist_state"`という以前のパターンは削除した。実際に
        `schema_validator.py`を確認したところ、checklistが空(0件)である
        こと自体を不合格にするルールは存在しない(買い物リストが未入力の
        状態で始まるのは正常な状態のため)。存在しないルールを「既知の
        修正パターン」として持ち続けるのは、事実に基づかない安心感を
        与えるだけだったため、正直に削除した。
        """
        if issue.category == "missing_app_title":
            # forge_ai自身のテスト(`test_repair_engine.py`)が直接
            # `RepairIssue(category="missing_app_title", ...)`を構築する
            # ケースとの後方互換のために残している(Adapterを経由しない
            # 直接呼び出し)。実際のBackend Validator経由では、下記の
            # `string_length` + `/app/title`パスの分岐が該当する。
            fallback_title = ir.screens[0].title if ir.screens else "新しいアプリ"
            return replace(ir, app_title=fallback_title)

        if issue.category == "string_length" and issue.path.endswith("/app/title"):
            # 実際のBackend Validator(`_check_schema`)が生成しうる、
            # app.titleが1〜80文字の文字列でない場合のrule名。
            fallback_title = ir.screens[0].title if ir.screens else "新しいアプリ"
            return replace(ir, app_title=fallback_title)

        return None
