"""POST /api/v1/ai/generate・POST /api/v1/ai/generate/confirm
(FORGE_v0.2_COMPLETE_IMPLEMENTATION_DIRECTIVE.md / FORGE_v0.2_修正指示.md
P0〜P1章に基づき全面改訂)。

**注記(重要)**: このファイルはfastapiに依存する。Claudeのサンドボックスには
fastapiがインストールされておらず、ネットワークも無いため導入できなかった
(`pip install`を実際に試行し、失敗を確認済み)。したがってこのファイル自体は
一度もimport・実行できていない。`app/ai/runtime/prompt_pipeline.py`・
`app/ai/runtime/confirmation_store.py`という「呼び出される側」の純粋な
Pythonロジックは、Claudeの環境で実際にunittest実行して検証済みだが、
この薄いルーター層(HTTPの皮)はCEO環境で`uvicorn app.main:app --reload`
を実行した上での動作確認が必要。

**P1 6章対応(response_model=None禁止)**: 以前はエラー時に`JSONResponse`を
route関数が直接returnしていたため、`response_model`を`None`にせざるを
得なかった。今回、`ForgeAIPipelineError`系の例外を局所的に握りつぶさず、
`app/exception_handlers.py`に一本化されたグローバルハンドラへ伝播させる
設計へ変更した(FastAPIの例外ハンドラは、route自体の`response_model`
バリデーションの対象外であるため、これにより`response_model`を成功系の
型だけで正しく宣言できる)。

呼び出し順序(ADAPTER_CONTRACT_V1.md 7.2節 Runtime Call Sequenceに対応):
    PromptPipeline.run(natural_language, engine=..., provider=...)
        -> 成功: GenerateSuccessResponse
        -> 確認要求: GenerateNeedsConfirmationResponse(ConfirmationStoreへ記録)
        -> ForgeAIPipelineError系の例外: そのままraiseし、グローバル
           ハンドラ(`app/exception_handlers.py`)がError Envelopeへ変換する
"""

from __future__ import annotations

from fastapi import APIRouter

from app.ai.runtime.confirmation_store import (
    MAX_CONFIRMATION_ROUNDS,
    ConfirmationNotFoundError,
    ConfirmationRoundExceededError,
    default_confirmation_store,
)
from app.ai.runtime.pipeline_errors import ConfirmationSessionError
from app.ai.runtime.prompt_pipeline import PipelineNeedsConfirmationResult, PromptPipeline
from app.schemas.ai import (
    ConfirmationAnswerRequest,
    ConfirmationDTO,
    CriticResultDTO,
    DiagnosticsDTO,
    ErrorEnvelope,
    GenerateNeedsConfirmationResponse,
    GenerateRequest,
    GenerateResultDTO,
    GenerateSuccessResponse,
    ValidationIssueDTO,
    ValidationResultDTO,
)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

# FORGE v0.2 P1 6章対応: response_model=Noneを使わず、実際に返しうる型を
# 正式に宣言する(OpenAPIスキーマが実装と一致するようにする)。
_GENERATE_RESPONSE_MODEL = GenerateSuccessResponse | GenerateNeedsConfirmationResponse
_GENERATE_ERROR_RESPONSES = {
    400: {"model": ErrorEnvelope, "description": "リクエストボディがJSONとして解析できない(request_error/json_syntax_invalid)"},
    422: {"model": ErrorEnvelope, "description": "リクエスト形式不正、またはPlanning/Validation失敗(request_error・planning_error・validation_error)"},
    500: {"model": ErrorEnvelope, "description": "予期しない内部エラー(runtime_error・unexpected_error)"},
    502: {"model": ErrorEnvelope, "description": "Provider応答不正・認証失敗(provider_error)"},
    503: {"model": ErrorEnvelope, "description": "Provider利用不可・レート制限(provider_error)"},
    504: {"model": ErrorEnvelope, "description": "Providerタイムアウト(provider_error)"},
}


def _diagnostics_dto(diagnostics) -> DiagnosticsDTO:  # noqa: ANN001 — app.ai.runtime.prompt_pipeline.Diagnostics
    return DiagnosticsDTO(
        engine_used=diagnostics.engine_used,
        provider_used=diagnostics.provider_used,
        repair_attempts=diagnostics.repair_attempts,
        intent_ir=diagnostics.intent_ir,
        plan_ir=diagnostics.plan_ir,
        conversion_warnings=list(diagnostics.conversion_warnings),
        cognitive_revision_attempts=diagnostics.cognitive_revision_attempts,
        ambiguity_report=diagnostics.ambiguity_report,
        domain_classification=diagnostics.domain_classification,
        decision_trace=list(diagnostics.decision_trace),
    )


def _success_response(result) -> GenerateSuccessResponse:  # noqa: ANN001 — PipelineRunResult
    return GenerateSuccessResponse(
        result=GenerateResultDTO(
            forge_document=result.forge_document,
            validation=ValidationResultDTO(
                valid=result.validation.valid,
                errors=[ValidationIssueDTO(**e.to_dict()) for e in result.validation.errors],
                warnings=[ValidationIssueDTO(**w.to_dict()) for w in result.validation.warnings],
            ),
            quality=(
                CriticResultDTO(
                    score=result.quality.score,
                    release_ready=result.quality.release_ready,
                    issues=[dict(i) for i in result.quality.issues],
                    required_fixes=list(result.quality.required_fixes),
                )
                if result.quality is not None
                else None
            ),
            diagnostics=_diagnostics_dto(result.diagnostics),
        )
    )


def _run_pipeline_and_build_response(
    natural_language: str,
    *,
    engine: str,
    provider: str | None,
    max_repair_attempts: int | None,
    round_count: int,
    clarification_answer: str | None = None,
    previous_answers: tuple[str, ...] = (),
):
    pipeline_kwargs: dict = {}
    if max_repair_attempts is not None:
        pipeline_kwargs["max_repair_attempts"] = max_repair_attempts
    pipeline = PromptPipeline(**pipeline_kwargs)

    # FORGE v0.2 Final Gate 最終調整 P1対応(重要なバグ修正):
    # 以前はここで`clarification_answer=clarification_answer`
    # (今回1件のみ)しか`PromptPipeline.run()`へ渡していなかったため、
    # 2回以上確認往復があった場合、1回目の回答が失われていた
    # (例: 1回目「家族向け」、2回目「買い物リスト」の場合、Pipelineには
    # 「x 買い物リスト」しか渡らず、「家族向け」という情報が消えていた)。
    # `previous_answers`(過去の回答履歴)と今回の回答を結合した
    # **全件**を`clarification_answers`として渡すよう修正した。
    all_answers = previous_answers + ((clarification_answer,) if clarification_answer else ())
    result = pipeline.run(
        natural_language, engine=engine, provider=provider, clarification_answers=all_answers
    )

    if isinstance(result, PipelineNeedsConfirmationResult):
        # 次回`/generate/confirm`が呼ばれた際も、`natural_language`
        # (元入力、回答を含まない)を`original_natural_language`として
        # 保存し続ける。今回までの全回答(`all_answers`)を`previous_
        # answers`として引き継ぎ、次回はこれに次の回答を加えた全件が
        # 渡るようにする(上記のバグ修正と対になる設計)。
        return _needs_confirmation_response_with_input(
            result, natural_language, round_count=round_count, previous_answers=all_answers
        )
    return _success_response(result)


def _needs_confirmation_response_with_input(
    result: PipelineNeedsConfirmationResult,
    natural_language: str,
    *,
    round_count: int,
    previous_answers: tuple[str, ...] = (),
) -> GenerateNeedsConfirmationResponse:
    # FORGE v0.2 Final Gate P0.7対応: 前回到達時点のdiagnosticsを
    # ConfirmationStoreへ保持し、再確認時に前回状態を追跡できるようにする。
    session = default_confirmation_store.create(
        original_natural_language=natural_language,
        engine=result.engine_used,
        provider=result.provider_used,
        reached_stage=result.reached_stage,
        reason=result.reason,
        round_count=round_count,
        ambiguity_report=result.ambiguity_report,
        domain_classification=result.domain_classification,
        decision_trace=result.decision_trace,
        previous_answers=previous_answers,
    )
    return GenerateNeedsConfirmationResponse(
        confirmation=ConfirmationDTO(
            request_id=session.request_id,
            question=result.message,
            reason=result.reason,
            reached_stage=result.reached_stage,
            open_questions=list(result.open_questions),
            rounds_remaining=max(0, MAX_CONFIRMATION_ROUNDS - round_count),
        ),
        diagnostics=DiagnosticsDTO(
            engine_used=result.engine_used,
            provider_used=result.provider_used,
            repair_attempts=0,
            ambiguity_report=result.ambiguity_report,
            domain_classification=result.domain_classification,
            decision_trace=list(result.decision_trace),
        ),
    )


@router.post(
    "/generate",
    response_model=_GENERATE_RESPONSE_MODEL,
    responses=_GENERATE_ERROR_RESPONSES,
)
def generate(request: GenerateRequest):
    options = request.input.generation_options
    engine = (options.engine if options else None) or "forge_ai"
    provider = options.provider if options else None
    max_repair_attempts = options.max_repair_attempts if options else None

    return _run_pipeline_and_build_response(
        request.input.natural_language,
        engine=engine,
        provider=provider,
        max_repair_attempts=max_repair_attempts,
        round_count=1,
    )


@router.post(
    "/generate/confirm",
    response_model=_GENERATE_RESPONSE_MODEL,
    responses=_GENERATE_ERROR_RESPONSES,
)
def confirm(request: ConfirmationAnswerRequest):
    """FORGE v0.2 P0.2章「needs_confirmationフローを最後まで完成させる」。

    `request_id`からセッションを取得し、ユーザーの回答を元の入力とは
    **別引数として**Cognitive Pipelineへ渡し、再実行する
    (`confirmation_store.py`冒頭のdocstring参照: forge_ai側は途中段階
    からの再開をサポートしないため、これは「全体再実行」という現実的な
    代替設計である)。

    **契約の変更点(Final Gate P0.1対応)**: `ConfirmationStore.
    consume_and_advance()`の戻り値を、以前の2値タプル(`record,
    augmented_input`)から3値タプル(`record, original_natural_language,
    answer`)へ変更した(このモジュール自体はfastapi依存のためClaude
    環境では実行できないが、`ConfirmationStore.consume_and_advance()`
    自体はfastapiに依存しない純粋なPythonクラスであり、実際に
    `backend/tests/test_confirmation_store.py`で実行し、3値タプルが
    返ることを確認済み)。このRouterのアンパック文もこの新しい契約に
    合わせて更新した。`_run_pipeline_and_build_response()`へは
    `original_natural_language`(回答を含まない)と`answer`
    (`clarification_answer`として)を別々に渡し、`record.
    previous_answers`(過去の回答履歴)も引き継ぐ。**このRouter自体の
    実行確認はCEO環境の`uvicorn`/`pytest`が必要(冒頭の注記参照)。**
    """
    try:
        record, original_natural_language, answer = default_confirmation_store.consume_and_advance(
            request.request_id, answer=request.answer
        )
    except ConfirmationNotFoundError as exc:
        raise ConfirmationSessionError(
            f"request_id '{request.request_id}' に対応する確認セッションが見つかりません(存在しないか、期限切れ、または既に使用済みです)。",
            sub_reason="confirmation_session_not_found",
            stage="confirmation",
        ) from exc
    except ConfirmationRoundExceededError as exc:
        raise ConfirmationSessionError(
            str(exc), sub_reason="confirmation_rounds_exceeded", stage="confirmation"
        ) from exc

    return _run_pipeline_and_build_response(
        original_natural_language,
        engine=record.engine,
        provider=record.provider,
        max_repair_attempts=None,
        round_count=record.round_count + 1,
        clarification_answer=answer,
        previous_answers=record.previous_answers,
    )
