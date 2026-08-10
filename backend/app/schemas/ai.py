"""`/api/v1/ai/generate` のリクエスト/レスポンスモデル
(FORGE-MILESTONE-005、`docs/spec/ADAPTER_CONTRACT_V1.md` 5章に対応)。

**注記(重要)**: このファイルはpydanticに依存する。Claudeのサンドボックスには
pydantic・fastapiがインストールされておらず、ネットワークも無いため
導入できなかった(`pip install`を実際に試行し、失敗を確認済み)。
したがってこのファイル自体は一度もimport・実行できていない
(構文は目視で確認したが、Pydantic v2の実際の挙動での検証はできていない)。
CEO環境で`pip install -r requirements.txt`実行後、`pytest`または
`uvicorn app.main:app --reload`で初めて動作確認できる。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request(ADAPTER_CONTRACT_V1.md 5.2節)
# ---------------------------------------------------------------------------


class GenerationOptionsDTO(BaseModel):
    """`generation_options`。ADR 4.0節(Engine/Provider分離)に対応。

    CEO実物監査対応: `engine`/`provider`をHTTP公開APIレベルで許可リスト化
    した(`Literal`)。Router内部の`ProviderRouter`は後方互換のため
    `native`/`local`/Provider名としての`forge_ai`を引き続き解決できるが、
    **HTTP経由ではこれらを受理しない**(Engine名とProvider名の混同を、
    外部公開APIの型で構造的に防ぐ。ADAPTER_CONTRACT_V1.md 4.0節)。
    Pydanticが不正な値を422で弾く(HTTP入力層でのバリデーション)。
    """

    platform: Literal["mobile", "web", "desktop", "cross_platform"] | None = None
    engine: Literal["forge_ai"] | None = Field(
        default=None, description="どの認知パイプライン実装を使うか。現状は'forge_ai'のみ有効。"
    )
    provider: Literal["mock", "openai", "claude", "gemini", "oss"] | None = Field(
        default=None, description="Engineが内部で使うLLM実装。既定は'mock'。'native'/'local'/'forge_ai'はHTTP経由では指定不可。"
    )
    # CEO実物監査対応: M005契約「Repair最大2回・Validator最大3回」と
    # 矛盾しないよう、HTTP入力層でも上限を2に制限する(以前はle=10だった)。
    max_repair_attempts: int | None = Field(default=None, ge=0, le=2)


class GenerateInputDTO(BaseModel):
    natural_language: str = Field(
        ..., min_length=1, max_length=2000, description="ユーザーが入力した自然言語"
    )
    session_context: dict[str, Any] | None = None
    user_metadata: dict[str, Any] | None = None
    generation_options: GenerationOptionsDTO | None = None


class GenerateRequest(BaseModel):
    """FORGE v0.2 Final Gate P0.2対応: `version`を`Literal["1.0"]`へ
    固定した(以前は任意の`str`を受理していた)。未知のversion文字列は
    Pydanticがこのフィールドの入力バリデーションで拒否し、既存の
    `request_validation_exception_handler`(`app/exception_handlers.py`)
    経由で`status: "error"`・`category: "request_error"`・
    HTTP 422として返る(この経路は既に実装済みで、型を変えるだけで
    自動的に有効になる)。"""

    version: Literal["1.0"] = "1.0"
    input: GenerateInputDTO


# ---------------------------------------------------------------------------
# Response — 成功(ADAPTER_CONTRACT_V1.md 5.3節)
# ---------------------------------------------------------------------------


class ValidationIssueDTO(BaseModel):
    path: str
    category: str
    severity: str
    rule: str
    message: str


class ValidationResultDTO(BaseModel):
    valid: bool
    errors: list[ValidationIssueDTO] = Field(default_factory=list)
    warnings: list[ValidationIssueDTO] = Field(default_factory=list)


class CriticResultDTO(BaseModel):
    score: int
    release_ready: bool
    issues: list[dict[str, str]] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)


class DiagnosticsDTO(BaseModel):
    engine_used: str
    provider_used: str
    repair_attempts: int
    intent_ir: dict[str, Any] | None = None
    plan_ir: dict[str, Any] | None = None
    conversion_warnings: list[str] = Field(default_factory=list)
    # FORGE v0.2 PART A 4.2節で追加。cognitive_revision_attemptsは
    # Cognitive Revision Loopの試行回数(repair_attemptsとは独立した
    # 別カウンタ、ADR 2.4節・M005 D59の教訓)。
    cognitive_revision_attempts: int = 0
    ambiguity_report: dict[str, Any] | None = None
    domain_classification: dict[str, Any] | None = None
    decision_trace: list[dict[str, Any]] = Field(default_factory=list)


class GenerateResultDTO(BaseModel):
    forge_document: dict[str, Any] = Field(..., description="Forge Language準拠のJSON。Validator合格済みのもののみ(ADR 2.3節)")
    validation: ValidationResultDTO
    quality: CriticResultDTO | None = None
    diagnostics: DiagnosticsDTO


class GenerateSuccessResponse(BaseModel):
    version: Literal["1.0"] = "1.0"
    status: Literal["success"] = "success"
    result: GenerateResultDTO


# ---------------------------------------------------------------------------
# Response — 確認要求(FORGE_v0.2_COMPLETE_IMPLEMENTATION_DIRECTIVE.md
# PART A 5.2節に対応。CognitivePipelineNeedsConfirmationを例外として
# 潰さず、正式なレスポンス型として表現する)。
#
# **既知の制限**: `open_questions`は自由記述の疑問文であり、選択式の
# `choices`(ボタン/Chip用の定型選択肢)ではない。Cognitive層
# (`ConfirmationRequest`)は現時点で選択肢データを持たないため、ここで
# 架空の選択肢を作らない(共通指示書「不明な内容を推測で断定すること」
# の禁止、および本Directiveの禁止事項「押せるが動かないUI」を避けるため)。
# Flutter側は`open_questions`を自由入力欄として表示することを想定する。
# ---------------------------------------------------------------------------


class ConfirmationDTO(BaseModel):
    request_id: str = Field(..., description="このリクエストの追跡ID(diagnostics.decision_traceと対応付け可能)")
    question: str
    reason: str
    reached_stage: str
    open_questions: list[str] = Field(default_factory=list)
    # FORGE v0.2 P1 7章対応: 確認往復の残り回数をFrontendへ伝える
    # (`confirmation_store.MAX_CONFIRMATION_ROUNDS`と対応)。UIが
    # 「あと何回まで確認できるか」を表示できるようにするための情報であり、
    # 上限自体はBackend側(`/generate/confirm`)で強制する。
    rounds_remaining: int = 0


class GenerateNeedsConfirmationResponse(BaseModel):
    version: Literal["1.0"] = "1.0"
    status: Literal["needs_confirmation"] = "needs_confirmation"
    confirmation: ConfirmationDTO
    diagnostics: DiagnosticsDTO | None = None


class ConfirmationAnswerRequest(BaseModel):
    """`POST /api/v1/ai/generate/confirm`のリクエストボディ
    (FORGE v0.2 P0.2・P1.7節)。

    `request_id`は直前の`needs_confirmation`レスポンス
    (`confirmation.request_id`)から取得したものをそのまま送る。

    FORGE v0.2 Final Gate P0.2対応: `version`を`GenerateRequest`と同様
    `Literal["1.0"]`へ固定した。
    """

    version: Literal["1.0"] = "1.0"
    request_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Response — エラー(共通Error Envelope、指示書12章・ADR 3.3節)
# ---------------------------------------------------------------------------


class ErrorDetailDTO(BaseModel):
    category: str
    sub_reason: str | None = None
    message: str
    retryable: bool = False
    # FORGE v0.2 P1 5章対応: 以前はメッセージ文字列へ埋め込むだけだった
    # 「どの段階で失敗したか」を、正式なフィールドとして追加した。
    # リクエスト形式不正(request_error、Pydantic入力層)にはPipeline段階の
    # 概念自体が無いため`None`のまま(捏造しない)。
    reached_stage: str | None = None


class ErrorEnvelope(BaseModel):
    """全エラー(400/422/5xx)がこの形式で統一される。FastAPI標準の
    `{"detail": [...]}`をそのまま返さない(指示書12章)。"""

    version: Literal["1.0"] = "1.0"
    status: Literal["error"] = "error"
    error: ErrorDetailDTO
