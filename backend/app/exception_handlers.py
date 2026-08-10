"""FastAPI例外ハンドラ(FORGE-MILESTONE-005、指示書12章「共通Error Envelope」)。

FastAPI標準の`{"detail": [...]}`形式をそのまま返さず、400/422/AI Error
すべてを`ErrorEnvelope`(`app/schemas/ai.py`)へ統一する。

**注記(重要、未検証)**: このファイルはfastapiに依存し、Claudeの
サンドボックスには無い(ネットワーク不可のため導入不可、実際に
`pip install`を試行して確認済み)。一度もimport・実行できていない。

**JSON構文不正(400) vs スキーマ/型不正(422)の判定について**:
Pydantic v2 + FastAPIでは、リクエストボディがJSONとしてすら解析できない
場合、`RequestValidationError.errors()`の中に`type == "json_invalid"`
というエラーが含まれる(Pydantic v2の一般的な既知の挙動に基づく判断)。
この判定ロジックは**Claude環境で実際に動作確認できていない**。CEO環境で、
意図的に壊れたJSON(例: `{`のような不完全な入力)を送って実際に400が
返ることを確認する必要がある。判定ロジックは`_is_json_syntax_error()`
1箇所に切り出してあるので、外れていた場合はここだけ修正すればよい。

**"request_error"というcategory値について**: `docs/spec/
ADAPTER_CONTRACT_V1.md` 3.1節の5分類(validation_error/planning_error/
provider_error/runtime_error/unexpected_error)は、いずれもAI処理段階の
エラーを想定しており、HTTPリクエスト自体の形式不正はADR自身が
「本Error Contractの対象外とする」と明記している。無理に5分類の
いずれかへ当てはめず、`ErrorDetailDTO.category`が自由な文字列を
許容する設計を活かし、`"request_error"`という6番目の値を使う。
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.ai.runtime.pipeline_errors import ForgeAIPipelineError, ProviderError
from app.schemas.ai import ErrorDetailDTO, ErrorEnvelope


def _is_json_syntax_error(exc: RequestValidationError) -> bool:
    """リクエストボディがJSONとして解析すらできなかった場合に`True`を返す。
    未検証(このファイルのdocstring参照)。"""
    for error in exc.errors():
        if error.get("type") == "json_invalid":
            return True
    return False


async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """`docs/spec/ADAPTER_CONTRACT_V1.md` 3.1節の基準に従う:
    - JSON構文自体が壊れている → 400
    - スキーマ・型が不正(natural_languageの空文字を含む) → 422
    """
    if _is_json_syntax_error(exc):
        envelope = ErrorEnvelope(
            error=ErrorDetailDTO(
                category="request_error",
                sub_reason="json_syntax_invalid",
                message="リクエストボディがJSONとして解析できません。",
                retryable=False,
            )
        )
        return JSONResponse(status_code=400, content=envelope.model_dump())

    first_error = exc.errors()[0] if exc.errors() else {}
    envelope = ErrorEnvelope(
        error=ErrorDetailDTO(
            category="request_error",
            sub_reason="schema_invalid",
            message=f"リクエストの形式が不正です: {first_error.get('msg', str(exc))}",
            retryable=False,
        )
    )
    return JSONResponse(status_code=422, content=envelope.model_dump())


async def forge_ai_pipeline_error_handler(request: Request, exc: ForgeAIPipelineError) -> JSONResponse:
    """`ForgeAIPipelineError`系の例外を捕捉する、アプリ全体で唯一の
    変換場所(`app/routers/ai.py`はこれを局所的に握りつぶさず、そのまま
    伝播させる。FORGE v0.2 P1 6章「response_model=None禁止」対応で、
    ルーター側の重複した`_error_envelope_response`を削除し、ここへ
    一本化した)。"""
    status_code = exc.http_status if isinstance(exc, ProviderError) else 422
    if exc.category == "runtime_error":
        status_code = 500
    envelope = ErrorEnvelope(
        error=ErrorDetailDTO(
            category=exc.category,
            sub_reason=exc.sub_reason,
            message=exc.message,
            retryable=exc.retryable,
            reached_stage=getattr(exc, "stage", None),
        )
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """分類不能な例外(`unexpected_error`)の最終防波堤。本番レスポンスに
    スタックトレース・内部クラス名等を含めない(指示書12章)。"""
    envelope = ErrorEnvelope(
        error=ErrorDetailDTO(
            category="unexpected_error",
            sub_reason=None,
            message="予期しないエラーが発生しました。",
            retryable=False,
        )
    )
    return JSONResponse(status_code=500, content=envelope.model_dump())


def register_exception_handlers(app: Any) -> None:
    """`app/main.py`から呼び出す、まとめ登録用のヘルパー。"""
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(ForgeAIPipelineError, forge_ai_pipeline_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
