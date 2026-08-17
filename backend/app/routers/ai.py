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
from app.ai.gateway.ai_router import NoProviderAvailableError, default_router
from app.ai.gateway.tasks import ForgeTask
from app.ai.runtime.conversation_engine import ConversationEngine
from app.ai.runtime.conversation_metrics import record_conversation_event
from app.ai.runtime.conversation_policy import classify_build_failure
from app.ai.runtime.conversation_store import ConversationNotFoundError, default_conversation_store
from app.ai.runtime.conversation_types import (
    ConversationAction,
    ConversationReadiness,
    ConversationTurn,
)
from app.ai.runtime.forge_operation import ForgeOperationEngine
from app.ai.runtime.injection_scan import scan_for_injection
from app.ai.runtime.pipeline_errors import (
    ConfirmationSessionError,
    ConversationSessionError,
    ForgeAIPipelineError,
    ProviderError,
    UpdateOperationError,
)
from app.ai.runtime.prompt_pipeline import PipelineNeedsConfirmationResult, PromptPipeline
from app.ai.runtime.provider_router import ProviderRouter
from app.schemas.ai import (
    ConfirmationAnswerRequest,
    ConfirmationDTO,
    ConverseAskResponse,
    ConverseBuildResponse,
    ConverseConfirmResponse,
    ConverseRequest,
    ConverseUpdateResponse,
    CriticResultDTO,
    DiagnosticsDTO,
    ErrorEnvelope,
    GenerateNeedsConfirmationResponse,
    GenerateRequest,
    GenerateResultDTO,
    GenerateSuccessResponse,
    NeedModelDTO,
    UpdateRequest,
    UpdateResultDTO,
    UpdateSuccessResponse,
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


def _no_provider_message(exc: NoProviderAvailableError) -> str:
    """利用者へ見せる文言(FORGE-ROADMAP R0.1、2026-08-17)。

    **枠切れと障害を同じ文言にしない。** 以前はどちらも
    「しばらく待ってからもう一度お試しください」だったが、実測した
    Gemini無料枠は**1日20回/Model**であり(429本文の`quotaValue`)、
    枠を使い切った利用者が5分後に再試行しても同じ結果になる。
    直し方も違う——待つのではなく、翌日にするか、別のProviderを
    足す必要がある。**打つ手が違うものを同じ文言で案内しない。**
    """
    if exc.is_quota_exhaustion:
        return (
            "今日のAI利用枠を使い切りました。日付が変わるまで待つか、"
            "別のAI Providerを設定してください。"
            f"(内訳: {exc})"
        )
    return (
        "今どのAIも利用できませんでした。しばらく待ってからもう一度お試しください。"
        f"(内訳: {exc})"
    )


def _note_update_outcome(bound, result) -> None:  # noqa: ANN001 — _BoundAdapter / UpdateResult
    """`/update`の結果をExperienceへ書き足す(FORGE-ROADMAP R0、2026-08-17)。

    UPDATEはCognitive Pipelineを通らない独立経路なので、
    `prompt_pipeline._note_generation_outcome()`は通らない。**通らない
    経路は記録されない**——それが「ExperienceStoreはあるがProductionから
    記録されない」(Product Direction §7)の作られ方である。

    `attempts`はRepairの往復回数(`forge_operation.py`)であり、
    生成側の`repair_attempts`と同じ意味なので同じ欄へ入れる。
    """
    store = getattr(bound.router, "experience", None)
    if store is None or not bound.experience_refs:
        return
    store.note_generation_outcome(
        bound.experience_refs,
        # Validatorに通らなかった更新は`success=False`で返る
        # (`forge_operation.py`の契約)。成功=Validator合格である。
        validator_passed=bool(result.success),
        repair_attempts=max(0, int(getattr(result, "attempts", 0) or 0) - 1),
    )


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
        injection_report=diagnostics.injection_report,
        safety_report=diagnostics.safety_report,
    )


def _result_dto(result) -> GenerateResultDTO:  # noqa: ANN001 — PipelineRunResult
    return GenerateResultDTO(
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


def _success_response(result) -> GenerateSuccessResponse:  # noqa: ANN001 — PipelineRunResult
    return GenerateSuccessResponse(result=_result_dto(result))


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
    # FORGE-AI-CONNECT-001 TD21対応(2026-08-11): 検出のみ、ブロックはしない
    # (`app/ai/runtime/injection_scan.py`参照)。
    injection_report = scan_for_injection(natural_language)
    result = pipeline.run(
        natural_language,
        engine=engine,
        provider=provider,
        clarification_answers=all_answers,
        injection_report=injection_report,
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
        # Phase B: 保存するのは**利用者の指定**(通常None)であって、
        # 観測された`provider_used`ではない。`provider_used`を保存すると、
        # 再開時にその名前で固定されてしまい(何も呼ばれていなければ
        # `"none"`という存在しない名前になり)Routingが働かなくなる。
        provider=result.requested_provider,
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
            injection_report=result.injection_report,
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


# ---------------------------------------------------------------------------
# POST /api/v1/ai/converse(FORGE-PRODUCT-VISION-002、2026-08-11)
#
# `docs/spec/FORGE_PRODUCT_VISION_002_CONVERSATIONAL_ARCHITECTURE.md`・
# ADR-014参照。既存の`/generate`・`/generate/confirm`は無変更のまま
# 併存する(このエンドポイントは追加のみ、後方互換)。
# ---------------------------------------------------------------------------

_CONVERSE_RESPONSE_MODEL = (
    ConverseAskResponse | ConverseConfirmResponse | ConverseBuildResponse
    | ConverseUpdateResponse | GenerateNeedsConfirmationResponse
)

# 指示書8章: BUILD判定後にPipelineが失敗した場合、原因が追加質問で
# 解消しうるなら、「作れませんでした」で終わらせず会話へ戻す。
_BUILD_FAILURE_ASK_PREFIX = "少しだけ確認させて。"


@router.post("/converse", response_model=_CONVERSE_RESPONSE_MODEL, responses=_GENERATE_ERROR_RESPONSES)
def converse(request: ConverseRequest):
    """1ターン進める。`session_id`が無ければ新規セッションを作る
    (`ConfirmationAnswerRequest.request_id`と同じ往復パターン)。

    ConversationEngineが`ask`と判定すればそのまま質問を返す。`build`と
    判定すれば、会話全体を要約した`build_brief`を既存の
    `PromptPipeline.run()`へそのまま渡し、Forge Documentを生成する
    (ADR-014: Conversation EngineはForge Language・Validator・Domain
    知識を一切持たず、既存資産を完全に再利用する)。既存Cognitive
    Pipeline側がさらに`needs_confirmation`を返した場合は、既存の
    `/generate/confirm`の契約へそのまま委ねる。

    `current_document`が渡された場合(Held画面からの再開)のみ、`update`
    (既存ツールへの変更要求、TD40)を選びうる——`ForgeOperationEngine.
    apply_update()`へそのまま委ねる(`/api/v1/ai/update`と同じ実装)。
    """
    if request.session_id is None:
        session = default_conversation_store.create()
    else:
        try:
            session = default_conversation_store.get(request.session_id)
        except ConversationNotFoundError as exc:
            raise ConversationSessionError(
                f"session_id '{request.session_id}' に対応する会話セッションが見つかりません(存在しないか、期限切れです)。",
                sub_reason="conversation_session_not_found",
                stage="conversation",
            ) from exc

    session = default_conversation_store.add_turn(
        session.session_id, ConversationTurn(role="user", text=request.message)
    )

    # FORGE-AI-FOUNDATION-010 Phase B(2026-08-13)で修正した実バグ。
    #
    # 以前はここで`ProviderRouter.default_provider_name()`が返す名前を
    # `provider_name`として確定させ、それをそのままレスポンスの
    # `provider`/`simulated`として返していた。これは「既定として選ばれる
    # **はず**の名前」であって、実際に応答を生成したProviderではない。
    #
    # 実機で確認した結果(Router state: `gemini available successes=1`):
    # `FORGE_DEFAULT_PROVIDER=mock`を設定していても、Routerはそれを読まず
    # 実Geminiを呼び、レスポンスは`provider: "mock", simulated: true`と
    # 返していた。**利用者の入力が外部Cloudへ出ているのにMockだと
    # 表示していた**。Catalog側を環境依存へ直し(`default_catalog()`)、
    # ここでは**実際に使われた名前を実行後に読む**。
    router = ProviderRouter()

    # FORGE-QUOTA-AWARE-AI-ROUTER-008(2026-08-13): Provider解決を
    # `AIRouter`経由にする。**これが「配線」である** ——前回作った
    # `ModelGateway`は本番から一度も呼ばれておらず、Task別Routingも
    # fallbackも実際には起きていなかった(レビュー §3.1)。基盤を
    # 作って繋がないと、テストは通るのに製品は何も変わらない。
    #
    # `bind()`が返すのは`LLMAdapter`と同じ形なので、
    # `ConversationEngine`は1行も変わらない——Provider名を知らないまま
    # でよい(§1・§46)。
    #
    # `request.provider`が明示されている場合はRoutingを迂回する
    # (利用者の選択をRouterが上書きしない。Mockが使えるのもこの経路だけ)。
    provider = default_router().bind(
        ForgeTask.CONVERSATION_STEP,
        provider=request.provider,
    )
    try:
        step_result = ConversationEngine(provider).step(
            session, has_existing_tool=request.current_document is not None
        )
    except Exception as exc:  # noqa: BLE001 — Provider呼び出し失敗を、既存の/generate系と同じ
        # ForgeAIPipelineError系(友好的な日本語メッセージ・友好的な
        # HTTPステータス)へ変換する。実機確認(2026-08-11)で発見した
        # 実バグの修正: 以前はここで例外を捕捉しておらず、Gemini APIの
        # レート制限(429)発生時に、汎用の`unhandled_exception_handler`
        # (「予期しないエラーが発生しました」という素っ気ない文言)まで
        # 素通りしてしまい、`GeminiProvider`自身が用意した親切な日本語
        # メッセージ(TD31対応)が失われていた。
        message = str(exc)
        # Routerが「使えるProviderが無い」と言った場合、**理由込みで**
        # 伝える(§33 graceful degradation)。ここで偽のToolを作らない。
        if isinstance(exc, NoProviderAvailableError):
            raise ProviderError(
                _no_provider_message(exc),
                sub_reason="unavailable", stage="conversation",
            ) from exc
        sub_reason = "rate_limited" if ("429" in message or "利用上限" in message) else "unavailable"
        raise ProviderError(message, sub_reason=sub_reason, stage="conversation") from exc

    # **実行後**に確定する。Routerがfallbackした場合も正しい名前になる。
    provider_name = provider.last_provider_used or request.provider or "unknown"
    simulated = router.is_simulated(provider_name)

    need_model_dto = NeedModelDTO(**step_result.need_model.to_dict())

    # Stateful User Correction の状態を永続化する
    # (FORGE-USER-GUIDED-SELF-EXTENSION-006 §13、2026-08-13)。
    # Engineは純粋関数なので、状態を書くのはここ1箇所だけ。これが無いと
    # 「違う」を正しく解釈しても次のターンで忘れる(§11の問題そのもの)。
    default_conversation_store.record_hypothesis_event(
        session.session_id,
        event=step_result.hypothesis_event,
        hypothesis=step_result.hypothesis,
        correction_target=step_result.correction_target,
        # FORGE-ROADMAP R0(2026-08-17): 今ターンのAI呼び出しの記録番号を
        # 渡す。Storeはこれを次ターンまで持ち、利用者の「それでいい」/
        # 「違う」を**前ターンの応答へ**書き足す。
        #
        # ここでStoreを`default_experience_store()`から取らず
        # **Routerから取る**のは、記録した先と書き足す先を必ず一致
        # させるためである(`prompt_pipeline._note_generation_outcome()`
        # と同じ理由)。
        experience_refs=provider.experience_refs,
        experience_store=default_router().experience,
    )

    if step_result.action == ConversationAction.ASK:
        default_conversation_store.add_turn(
            session.session_id, ConversationTurn(role="forge", text=step_result.question or "")
        )
        # 同じUnknownを繰り返し質問しないため、今聞いたkeyを記録する
        # (指示書5章)。次ターンの`select_question()`がこれを見て除外する。
        if step_result.question_key:
            default_conversation_store.mark_question_asked(session.session_id, step_result.question_key)
        record_conversation_event(
            session.session_id, "ask", readiness=step_result.readiness.value,
            question_key=step_result.question_key,
            strategy=step_result.strategy.value,
        )
        return ConverseAskResponse(
            session_id=session.session_id, question=step_result.question or "", need_model=need_model_dto,
            readiness=step_result.readiness.value,
            provider=provider_name, simulated=simulated,
        )

    if step_result.action == ConversationAction.CONFIRM:
        # 指示書4章: 専用のConfirm Screenへ倒すのではなく、会話の中で
        # 確認する。ユーザーの次の返事は通常どおり`/converse`へ戻る
        # (セッションは破棄しない)。
        confirm_text = step_result.question or (
            "この操作は元に戻せない可能性があります。進めてよいですか？"
        )
        default_conversation_store.add_turn(
            session.session_id, ConversationTurn(role="forge", text=confirm_text)
        )
        record_conversation_event(
            session.session_id, "confirm", readiness=step_result.readiness.value,
        )
        return ConverseConfirmResponse(
            session_id=session.session_id, question=confirm_text,
            reason=step_result.confirm_reason or "確認が必要な操作を含むため",
            need_model=need_model_dto, readiness=step_result.readiness.value,
            provider=provider_name, simulated=simulated,
        )

    if step_result.action == ConversationAction.UPDATE:
        assert request.current_document is not None  # noqa: S101 — has_existing_tool=Trueの場合のみConversationEngineがUPDATEを選ぶ(conversation_engine.py参照)
        change_request = step_result.build_brief or ""
        # Phase B: UPDATEは会話ステップとは**別のTask**である
        # (Forge Language JSONの書き換え。要求する能力も失敗の意味も違う)。
        # 以前は会話ステップ用に束ねたAdapterを再利用しており、Task別の
        # profile(構造化出力要求・時間予算・試行上限)が効いていなかった。
        update_provider = default_router().bind(
            ForgeTask.FORGE_LANGUAGE_UPDATE, provider=request.provider
        )
        try:
            update_result = ForgeOperationEngine(update_provider).apply_update(
                request.current_document, change_request
            )
        except NoProviderAvailableError as exc:
            raise ProviderError(
                _no_provider_message(exc),
                sub_reason="unavailable", stage="forming_operation",
            ) from exc
        provider_name = update_provider.last_provider_used or provider_name
        simulated = router.is_simulated(provider_name)
        _note_update_outcome(update_provider, update_result)
        default_conversation_store.discard(session.session_id)
        if not update_result.success:
            raise UpdateOperationError(
                update_result.error_message or "更新に失敗しました。",
                validation_errors=(
                    tuple(e.to_dict() for e in update_result.validation.errors)
                    if update_result.validation is not None else ()
                ),
                stage="forming_operation",
            )
        assert update_result.forge_document is not None and update_result.validation is not None  # noqa: S101 — successなら両方Non-None(forge_operation.pyの契約)
        return ConverseUpdateResponse(
            session_id=session.session_id, need_model=need_model_dto, change_request=change_request,
            provider=provider_name, simulated=simulated,
            result=UpdateResultDTO(
                forge_document=update_result.forge_document,
                validation=ValidationResultDTO(
                    valid=update_result.validation.valid,
                    errors=[ValidationIssueDTO(**e.to_dict()) for e in update_result.validation.errors],
                    warnings=[ValidationIssueDTO(**w.to_dict()) for w in update_result.validation.warnings],
                ),
                attempts=update_result.attempts,
            ),
        )

    assert step_result.action == ConversationAction.BUILD  # noqa: S101 — CONFIRM/ASK/UPDATEは上で処理済み
    build_brief = step_result.build_brief or ""
    injection_report = scan_for_injection(build_brief)
    try:
        # Phase B: `provider_name`(既定解決の結果)ではなく
        # **`request.provider`(利用者の明示指定、通常はNone)**を渡す。
        # 以前は解決済みの名前を渡していたため、`PromptPipeline`側では
        # 常に「明示指定あり」となり、Routingが一度も働かなかった。
        result = PromptPipeline().run(
            build_brief, engine="forge_ai", provider=request.provider, injection_report=injection_report,
            # FORGE-HANDOFF-LOCAL-AI-UX-004(2026-08-13): アプリのタイトルは
            # `build_brief`(Forgeが書いた説明文)ではなく、**ユーザー自身の
            # 言葉**から作る。実機で「買い物で何買うかを記録・管理する
            # ための道具」という説明文がそのままアプリ名になっていた。
            title_seed=step_result.need_model.problem or None,
        )
    except ForgeAIPipelineError as exc:
        # 指示書8章: BUILD判定後にPipelineが失敗した場合、「作れません
        # でした」だけで終わらせない。原因が追加質問で解消しうるもの
        # (入力の曖昧さなど、理解段階の失敗)なら会話へ戻す。
        # Validator/Repair/生成段階の失敗は**Forge側の不具合**であり、
        # ユーザーに聞いても直らないため、そのまま安全なエラーとして
        # 送出する(AIの失敗とユーザーの情報不足を混同しない)。
        recoverable = classify_build_failure(
            stage=getattr(exc, "stage", None), sub_reason=getattr(exc, "sub_reason", None)
        )
        record_conversation_event(
            session.session_id, "build_failed", readiness=step_result.readiness.value,
        )
        if not recoverable:
            default_conversation_store.discard(session.session_id)
            raise
        record_conversation_event(session.session_id, "build_to_ask_fallback")
        question = f"{_BUILD_FAILURE_ASK_PREFIX}どんな場面で使いたいか、もう少しだけ教えてもらえますか？"
        default_conversation_store.add_turn(
            session.session_id, ConversationTurn(role="forge", text=question)
        )
        return ConverseAskResponse(
            session_id=session.session_id, question=question, need_model=need_model_dto,
            readiness=ConversationReadiness.INSUFFICIENT_INFORMATION.value,
            provider=provider_name, simulated=simulated,
        )

    if isinstance(result, PipelineNeedsConfirmationResult):
        # Cognitive Pipeline側が確認を求めた場合は、既存の
        # `/generate/confirm`契約へそのまま委ねる(無変更)。
        record_conversation_event(session.session_id, "pipeline_needs_confirmation")
        return _needs_confirmation_response_with_input(result, build_brief, round_count=1)

    record_conversation_event(
        session.session_id, "build", readiness=step_result.readiness.value,
        blocking_unknowns=len(step_result.need_model.blocking_unknowns()),
        safe_assumptions=len(step_result.need_model.assumptions),
    )
    default_conversation_store.discard(session.session_id)

    # 生成本体を実行したProviderを報告する(会話ステップとは別のProviderに
    # なりうる——Routerは各Taskで独立にfallbackする)。
    build_provider_name = result.diagnostics.provider_used or provider_name
    return ConverseBuildResponse(
        session_id=session.session_id, need_model=need_model_dto, build_brief=build_brief,
        result=_result_dto(result), readiness=step_result.readiness.value,
        provider=build_provider_name, simulated=router.is_simulated(build_provider_name),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/ai/update — Forming Operation(FORGE-PRODUCT-VISION-002
# TD40対応、2026-08-11)。Held状態のアプリを、会話で「育てる」。
# ---------------------------------------------------------------------------


@router.post("/update", response_model=UpdateSuccessResponse, responses=_GENERATE_ERROR_RESPONSES)
def update(request: UpdateRequest):
    """既存の`forge_document`を、`change_request`に従って更新する
    (`forge_operation.py`参照)。Cognitive Pipelineを一切通らない
    (Forge Language知識はValidatorだけに委ね、生成しない=既存の
    `/generate`とは独立した経路)。Repair往復後もValidatorに合格
    しなければ、`UpdateOperationError`(422相当)として失敗を返す
    ——不正なJSONを「成功」として返すことは絶対にしない。
    """
    # FORGE-AI-FOUNDATION-010 Phase B(2026-08-13): この経路も
    # **AIRouterを通す**。以前は`ProviderRouter.resolve()`を直接呼んで
    # おり、`/update`だけQuota切れのfallbackもCircuit Breakerも
    # 効いていなかった(Routerを作った後も繋いでいなかった箇所)。
    provider = default_router().bind(ForgeTask.FORGE_LANGUAGE_UPDATE, provider=request.provider)
    try:
        result = ForgeOperationEngine(provider).apply_update(
            request.forge_document, request.change_request
        )
    except NoProviderAvailableError as exc:
        raise ProviderError(
            _no_provider_message(exc),
            sub_reason="unavailable", stage="forming_operation",
        ) from exc

    _note_update_outcome(provider, result)

    if not result.success:
        raise UpdateOperationError(
            result.error_message or "更新に失敗しました。",
            validation_errors=(
                tuple(e.to_dict() for e in result.validation.errors) if result.validation is not None else ()
            ),
            stage="forming_operation",
        )

    assert result.forge_document is not None and result.validation is not None  # noqa: S101 — successならforge_operation.pyの契約上必ず両方Non-None
    return UpdateSuccessResponse(
        result=UpdateResultDTO(
            forge_document=result.forge_document,
            validation=ValidationResultDTO(
                valid=result.validation.valid,
                errors=[ValidationIssueDTO(**e.to_dict()) for e in result.validation.errors],
                warnings=[ValidationIssueDTO(**w.to_dict()) for w in result.validation.warnings],
            ),
            attempts=result.attempts,
        )
    )
