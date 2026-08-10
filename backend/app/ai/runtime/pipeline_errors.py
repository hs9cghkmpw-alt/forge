"""AI Runtime — Pipeline Errors(FORGE-MILESTONE-005 Task9)。

`docs/spec/ADAPTER_CONTRACT_V1.md` 3章(Error Contract)の5分類を、
実際にPythonで捕捉・判定できる例外階層として実装したもの。

HTTP層(`app/routers/ai_generate.py`)は、これらの例外を捕捉して
Error Envelope(3.3節)へ変換する。
"""

from __future__ import annotations


class ForgeAIPipelineError(Exception):
    """全Pipelineエラーの基底クラス。`category`(3.1節の5分類のいずれか)を
    サブクラスごとに固定値として持つ。

    `stage`はFORGE v0.2 P1 5章で追加した構造化フィールド。以前は
    「どの段階で失敗したか」をメッセージ文字列へ埋め込むだけだった
    (例: `f"Cognitive Pipelineが段階'{stage}'で失敗しました: ..."`)。
    HTTPレスポンス(`ErrorDetailDTO.reached_stage`)まで正式なフィールド
    として伝播させ、Frontendが文字列パースに頼らず分岐できるようにする。
    """

    category: str = "unexpected_error"
    retryable: bool = False
    sub_reason: str | None = None

    def __init__(self, message: str, *, sub_reason: str | None = None, stage: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.stage = stage
        if sub_reason is not None:
            self.sub_reason = sub_reason


class UnsupportedEngineError(ForgeAIPipelineError):
    """`engine`が既知の値(現状"forge_ai"のみ)でない場合。

    ADR 3.1節の5分類には明示的な項目が無いが、リクエストの意味的な
    不正として`planning_error`相当(422)で扱う(呼び出し前の段階で
    弾けなかった場合の多重防御。HTTP層のPydanticバリデーションが
    通常はこれより先に弾く想定)。
    """

    category = "planning_error"


class PlanningError(ForgeAIPipelineError):
    """自然言語からIntent/Planを構築できない(ADR 3.1節)。
    `forge_ai.core.pipeline.run_pipeline()`が予期しない例外を送出した
    場合、このエラーへ包んで再送出する。
    """

    category = "planning_error"


class ForgeValidationError(ForgeAIPipelineError):
    """生成されたForge DocumentがValidatorに合格しない、Repair試行後も
    (ADR 3.1節)。命名は標準ライブラリの`ValidationError`との衝突を
    避けるため`Forge`を前置している。
    """

    category = "validation_error"

    def __init__(self, message: str, *, validation_errors: tuple[dict, ...] = (), stage: str | None = None) -> None:
        super().__init__(message, stage=stage)
        self.validation_errors = validation_errors


class ProviderError(ForgeAIPipelineError):
    """LLM Provider呼び出し自体が失敗(ADR 3.1節・3.2節)。

    `sub_reason`は"timeout" | "rate_limited" | "invalid_response" |
    "auth_failed" | "unavailable"のいずれか(ADR 3.2節)。
    """

    category = "provider_error"

    _SUB_REASON_TO_HTTP_STATUS = {
        "timeout": 504,
        "rate_limited": 503,
        "invalid_response": 502,
        "auth_failed": 502,
        "unavailable": 503,
    }

    def __init__(self, message: str, *, sub_reason: str, stage: str | None = None) -> None:
        super().__init__(message, sub_reason=sub_reason, stage=stage)
        self.retryable = sub_reason in ("timeout", "rate_limited", "unavailable")

    @property
    def http_status(self) -> int:
        return self._SUB_REASON_TO_HTTP_STATUS.get(self.sub_reason or "", 502)


class PipelineRuntimeError(ForgeAIPipelineError):
    """Adapter/M005内部の予期しない実行時エラー(ADR 3.1節)。"""

    category = "runtime_error"


class ConfirmationSessionError(ForgeAIPipelineError):
    """FORGE v0.2 P0.2・P1.7節: `/api/v1/ai/generate/confirm`で、
    `request_id`に対応する確認セッションが見つからない
    (`sub_reason="confirmation_session_not_found"`)、または確認往復が
    上限に達した(`sub_reason="confirmation_rounds_exceeded"`)場合。

    いずれもクライアントが送ってきた状態(古い/存在しないrequest_id、
    繰り返しすぎた確認)に起因するため、ADR 3.1節の5分類には無いが
    `exception_handlers.py`の`request_error`と同じ「クライアント側の
    問題」という性質を持つ。`ForgeAIPipelineError`のcategoryは自由な
    文字列を許容する設計を活かし、ここでは`"request_error"`を使う
    (既存のHTTP入力層バリデーション由来のrequest_errorと同じ分類)。
    """

    category = "request_error"
