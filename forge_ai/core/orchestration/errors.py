"""Cognitive Error階層(FORGE-MILESTONE-007第一段階)。

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3の Error Model
(旧Task6)に対応する。M005側`backend/app/ai/runtime/pipeline_errors.py`
の`PlanningError`とは**別クラス**である(名前が同じでも階層が異なる:
forge_ai/側=段階レベルの詳細、M005側=HTTPカテゴリレベルの集約。
Blueprint 6.3節)。
"""

from __future__ import annotations


class CognitiveError(Exception):
    """Cognitive Pipelineで発生する全エラーの基底クラス。"""

    stage: str = "unknown"

    def __init__(self, message: str, *, stage: str = "unknown") -> None:
        super().__init__(message)
        self.message = message
        self.stage = stage


class AmbiguityError(CognitiveError):
    """Ambiguity Detection自体が回復不能な形で失敗した場合。
    `CognitivePipelineNeedsConfirmation`へ変換する対象。"""


class ConfirmationRequired(CognitiveError):
    """明示的にHuman Confirmation/Escalationが必要と判断された場合の
    予備的な例外経路(3.4節の疑似コードが想定していない箇所で発生した
    場合の安全弁。通常は例外を使わず直接returnする、Blueprint 3.4節)。
    `CognitivePipelineNeedsConfirmation`へ変換する対象。"""


class PlanningError(CognitiveError):
    """Application Planning・Requirement Extraction等が失敗した場合。
    `CognitivePipelineFailed`へ変換する対象。

    ⚠️ `backend/app/ai/runtime/pipeline_errors.PlanningError`とは別クラス。
    """


class CriticFailure(CognitiveError):
    """Design Critic自体が実行時エラーで失敗した場合(評価対象の設計に
    問題があるという意味の`release_ready=false`とは異なる、Critic
    機構自体の障害)。`CognitivePipelineFailed`へ変換する対象。"""


# NotImplementedError(Provider未実装)は、このモジュールでは定義しない。
# `CognitiveOrchestrator`は`NotImplementedError`を一切捕捉せず、Facadeの
# 外側(将来のM005呼び出し元)まで伝播させる(Blueprint 6.2節)。
