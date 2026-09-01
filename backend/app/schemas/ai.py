"""`/api/v1/ai/generate` のリクエスト/レスポンスモデル
(FORGE-MILESTONE-005、`docs/spec/ADAPTER_CONTRACT_V1.md` 5章に対応)。

**注記(重要)**: このファイルはpydanticに依存する。Claudeのサンドボックスには
pydantic・fastapiがインストールされておらず、ネットワークも無いため
導入できなかった(`pip install`を実際に試行し、失敗を確認済み)。
したがってこのファイル自体は一度もimport・実行できていない
(構文は目視で確認したが、Pydantic v2の実際の挙動での検証はできていない)。
CEO環境で`pip install -r requirements.txt`実行後、`pytest`または
`uvicorn app.main:app --reload`で初めて動作確認できる。

**2026-08-11追記**: 上記は執筆当時の制約であり、現在は解消している。
このセッション以降、`.venv`にpydantic/fastapi/httpx等が実際にインストール
された状態で`uvicorn app.main:app`を起動し、`POST /api/v1/ai/generate`
経由の実Gemini呼び出しを含め、このファイルは実際にimport・実行・検証
済みである(TECH_DEBT.md TD37前後の記録参照)。
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
    provider: Literal["mock", "openai", "claude", "gemini", "oss", "local"] | None = Field(
        default=None,
        description=(
            "Engineが内部で使うLLM実装。既定は'mock'。"
            "'native'/'forge_ai'はEngine名なのでHTTP経由では指定不可。"
        ),
    )
    """**`local`はProvider名なので受理する**（FORGE-020A、2026-08-26）。

    ---

    ## ここが塞がっていた

    `local`（`LocalModelProvider`。Registry上 `IMPLEMENTED` /
    `Deployment.LOCAL` / 構造化出力対応）は、`_SPECIFIC_FACTORIES` にも
    Provider Registry にも在るのに、**HTTPからは1つも選べなかった**。
    代わりに受理していた `oss` は `NotImplementedError` を投げるスタブで、
    Registry自身が「`local`が実質的な後継」と書いている。

    つまり**動く方を隠して、動かない方を公開していた。**
    Forgeが繰り返している「作ったが本番から呼ばれない」の7例目である。

    以前の説明文は「'native'/'local'/'forge_ai' は Engine名との混同を
    防ぐため受理しない」と書いていたが、`local` は Engine名ではない
    ——Provider Registry の `provider_id` である。除外の理由が
    当てはまっていなかった。

    Vision §39 Level 0（Local Model が動く）は

        Runtime → LocalModelProvider → AIRouter → Forge pipeline
          → Validator → Evidence

    を通ることの証明なので、**ここが開いていないと実機でも測れない。**
    """
    # CEO実物監査対応: M005契約「Repair最大2回・Validator最大3回」と
    # 矛盾しないよう、HTTP入力層でも上限を2に制限する(以前はle=10だった)。
    max_repair_attempts: int | None = Field(default=None, ge=0, le=2)
    agent_mode: Literal["off", "verify"] = Field(
        default="off",
        description=(
            "FORGE-020B Local Tool Agent。off=従来経路、verify=生成後にLocal Agentが"
            "read-only Tool Broker経由で客観検証する。現段階では品質/遅延の実測前なので"
            "既定では有効化しない。"
        ),
    )


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
    # FORGE-AI-CONNECT-001 TD21対応(2026-08-11)。検出のみ、ブロックはしない
    # (`app/ai/runtime/injection_scan.py`参照)。
    injection_report: dict[str, Any] | None = None
    # FORGE-AI-CONNECT-001 TD20対応(2026-08-11)。検出のみ、ブロックはしない
    # (`app/ai/runtime/output_safety.py`参照)。needs_confirmation時は
    # 最終Documentがまだ存在しないため常にNone。
    safety_report: dict[str, Any] | None = None


class ArtifactRefDTO(BaseModel):
    """利用者が**いま見ている生成物**を後から指すためのID
    (FORGE-016A §3、2026-08-24)。

    「これでいい」「そこは違う」が来たとき、Forgeは**どの生成物への
    評価なのか**を知らなければ記録できない。013で`generation_ref`を
    Pipelineから返すようにしたが、HTTPまで届いていなかったので、
    結局`note_user_acceptance()`を呼ぶ経路が1本も無かった(TD65)。

    **内部のrefは出さない。** 出すと、Clientが任意のrefへ「受け入れた」
    を書けてしまう——それは学習素材の捏造である。不透明なIDを発行し、
    Forge自身が解決する。

    ---

    ## `artifact_id`は認可ではない（FORGE-017A §13）

    推測できないだけの**Bearer Capability**である。持っている人が
    評価を書ける。「不透明なIDだから権限を確認済み」とは扱わない。
    Cloud / 複数利用者へ広げるときは、所有者・App・Subjectの境界と
    必ず結びつける必要がある。

    ## Dataset Lineageのidではない（FORGE-017A §3）

    これは**失効する**（プロセス内・上限あり）。系譜には
    `ArtifactEvidenceId`（Evidence側の永続ID）を使う。
    **`artifact_id`をCloudのLearning Eventへ載せない。**
    """

    artifact_id: str = Field(..., description="この生成物へ評価を送るための一時的なハンドル。/api/v1/ai/feedback へそのまま返す。プロセス内でのみ有効で失効する")
    version_token: str = Field(..., description="この世代を表すランダムなtoken。古い世代へ評価を書かないための照合用。**内容から作らない**ので、同じDocumentでも毎回違う値になる(FORGE-017A §4)")




class AgentRunDTO(BaseModel):
    """FORGE-020B Local Tool Agent の外部向け要約。

    Tool本文、Prompt、ユーザー発話、Generation Evidence UIDは返さない。
    """

    requested: bool = True
    executed: bool = False
    outcome: Literal["succeeded", "partial", "failed", "abandoned", "unknown"] = "unknown"
    episode_id: str = ""
    provider: str = ""
    model: str = ""
    tool_calls: int = 0
    tools_used: list[str] = Field(default_factory=list)
    validator_outcome: Literal["passed", "failed", "skipped", "unsupported", "unknown"] = "unknown"
    stopped_because: str = ""

class GenerateResultDTO(BaseModel):
    forge_document: dict[str, Any] = Field(..., description="Forge Language準拠のJSON。Validator合格済みのもののみ(ADR 2.3節)")
    validation: ValidationResultDTO
    quality: CriticResultDTO | None = None
    capability_gap: dict[str, Any] | None = None
    """**作れないと分かっていることを利用者へ返す**（TD90 / 020A2 §5）。

    Plan は `simulate.loop` を MISSING と正しく名指しできていたのに、
    返っていたのは CRUD だけだった。**知っていて黙っていた**のを
    やめるための欄である。

    `blocks_completion=True` のときは `quality.release_ready` も
    `False` になる——求められたことの本質が出来ていないなら、
    「仕上がった」と言わない。
    """
    diagnostics: DiagnosticsDTO
    agent: AgentRunDTO | None = None
    artifact: ArtifactRefDTO | None = Field(
        default=None,
        description="この生成物のID(FORGE-016A §3)。Evidenceを記録していない場合はnull",
    )


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

    timings: StageTimingsDTO | None = None
    """段ごとの実測時間（計測できたときだけ載る）。UI は使わない。

    実機で本当に曖昧な要求はここへ落ちうる。**そこで内訳が消えると、
    どの段が遅いのか分からなくなる。**
    """



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


# ---------------------------------------------------------------------------
# POST /api/v1/ai/converse(FORGE-PRODUCT-VISION-002、2026-08-11)
#
# `docs/spec/FORGE_PRODUCT_VISION_002_CONVERSATIONAL_ARCHITECTURE.md`・
# ADR-014参照。既存の`/generate`系とは独立した、追加のみのエンドポイント
# (既存Frontendの動作に影響しない)。
# ---------------------------------------------------------------------------


class ConverseRequest(BaseModel):
    """会話の最新のユーザー発話を送る。1ターン目は`session_id`を省略する
    (新しいConversationSessionが作られ、レスポンスの`session_id`を
    次ターン以降で送り返す——`ConfirmationAnswerRequest.request_id`と
    同じ往復パターン)。"""

    version: Literal["1.0"] = "1.0"
    session_id: str | None = Field(default=None, description="2ターン目以降、直前のレスポンスのsession_idをそのまま送る")
    message: str = Field(..., min_length=1, max_length=2000)
    provider: Literal["mock", "gemini", "local"] | None = Field(
        default=None,
        description="ConversationEngineが使うLLM Provider。既定は'mock'。",
    )
    agent_mode: Literal["off", "verify"] = Field(
        default="off",
        description="BUILD後にFORGE-020B Local Tool Agent検証を行うか。",
    )
    """`local` は FORGE-020A で開けた。**会話がForgeの本線である**ので、
    ここが塞がったままだと Local Model は本線を1度も通れない。"""
    current_document: dict[str, Any] | None = Field(
        default=None,
        description=(
            "FORGE-PRODUCT-VISION-002続き(2026-08-11新設)。Held画面(既に"
            "生成済みのツールを表示中)から会話を再開する場合、そのForge "
            "Documentをそのまま渡す。渡された場合のみConversationEngineは"
            "'update'(既存ツールへの変更要求)を選びうる(TD40)。"
        ),
    )
    artifact_id: str | None = Field(
        default=None, min_length=1,
        description=(
            "FORGE-019A §2: 会話からの変更も`/update`と同じRevisionServiceを"
            "通る。`current_document`を渡すなら、それを受け取ったときの"
            "artifact capabilityも一緒に渡す。無いと変更は受け付けられない"
        ),
    )
    seen_version_token: str | None = Field(
        default=None, min_length=1,
        description="利用者が見ていた版。古ければstale_versionとして拒否する",
    )
    idempotency_key: str | None = Field(default=None, max_length=200)


class UnknownItemDTO(BaseModel):
    """FORGE-CONVERSATION-READY-001(2026-08-12)新設(指示書6章)。
    未知情報に「なぜ重要なのか」を持たせる。"""

    key: str
    impact: Literal["blocking", "high", "low", "cosmetic"]
    reason: str
    status: Literal["unknown", "resolved"] = "unknown"


class SafeAssumptionDTO(BaseModel):
    """FORGE-CONVERSATION-READY-001(2026-08-12)新設(指示書6章)。
    Forgeが聞かずに決めたことと、その理由。"""

    key: str
    value: str
    reason: str


class NeedModelDTO(BaseModel):
    """FORGE-CONVERSATION-READY-001(2026-08-12)で`unknowns`/`assumptions`
    を**追加**した。既存の`unknown_important`/`safe_assumptions`
    (文字列リスト)は、Flutter側の`NeedModelSummary`が既にパースして
    いるため、型・キー名ともに一切変更していない(後方互換)。"""

    problem: str
    known: list[str] = Field(default_factory=list)
    unknown_important: list[str] = Field(default_factory=list)
    safe_assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    unknowns: list[UnknownItemDTO] = Field(default_factory=list)
    assumptions: list[SafeAssumptionDTO] = Field(default_factory=list)


class SimulatedOutputMixin(BaseModel):
    """FORGE-HANDOFF-LOCAL-AI-UX-004 §9(2026-08-13)新設。

    指示書:「Silent Mock fallbackは禁止」「Mockだから内部JSONっぽい画面が
    出てもいい、という考えは禁止」。**どのProviderが答えたのか**と、
    **その出力が模擬かどうか**を、レスポンスが必ず自己申告する。

    Flutter側はこれを見て、模擬出力であることを画面上に明示する
    (黙って本物のように見せない)。既定値を持つ追加フィールドなので、
    このフィールドを知らない既存クライアントは影響を受けない(後方互換)。
    """

    provider: str = "mock"
    """実際に使われたProvider名。"""

    simulated: bool = False
    """`True`なら、この結果は実際の推論ではなくMockが組み立てた模擬出力。"""


class StageTimingsDTO(BaseModel):
    """**どの段に何ミリ秒かかったか。**

    実機で `/converse` が 73.54 秒かかったとき、内訳が分からなかった。
    合計だけでは「1つ速くしたから全部速い」と丸めてしまう。段ごとに
    分けて返すので、**次に何を速くすべきかが実測で決まる。**

    * `stages_ms` … 段の名前 → 合計ミリ秒（同じ段を複数回通ったら足す）
    * `stage_calls` … 段ごとの通過回数
    * `counters` … LLM 呼び出し回数など
    * `notes` … 速い道を通ったか、などの短い事実
    """

    stages_ms: dict[str, float] = {}
    stage_calls: dict[str, int] = {}
    counters: dict[str, int] = {}
    notes: dict[str, str] = {}


class ConverseAskResponse(SimulatedOutputMixin):
    version: Literal["1.0"] = "1.0"
    status: Literal["ask"] = "ask"
    session_id: str
    question: str
    need_model: NeedModelDTO
    readiness: str = "needs_question"
    """FORGE-CONVERSATION-READY-001(2026-08-12)新設。この質問に至った
    Readiness(`needs_question` / `insufficient_information`)。Metrics・
    Golden Test・Debugのために返す(指示書2章)。"""

    timings: StageTimingsDTO | None = None
    """段ごとの実測時間（計測できたときだけ載る）。UI は使わない。"""



class ConverseConfirmResponse(SimulatedOutputMixin):
    """FORGE-CONVERSATION-READY-001(2026-08-12)新設(指示書4章)。

    外部作用・不可逆操作を含む依頼に対し、**実行する前に**会話の中で
    確認する。専用のConfirm Screenを復活させるのではなく、ASKと同じ
    「会話の1ターン」として返す(指示書4章)——Flutter側も、質問と
    同じ吹き出しとして自然に表示できる。
    """

    version: Literal["1.0"] = "1.0"
    status: Literal["confirm"] = "confirm"
    session_id: str
    question: str
    """ユーザーへ見せる確認文。"""

    reason: str
    """なぜ確認が必要なのか(外部送信・不可逆操作など)。"""

    need_model: NeedModelDTO
    readiness: str = "needs_confirmation"

    timings: StageTimingsDTO | None = None
    """段ごとの実測時間（計測できたときだけ載る）。UI は使わない。"""



class ConverseBuildResponse(SimulatedOutputMixin):
    """BUILDと判定された場合、既存の`PromptPipeline.run()`をそのまま
    通した結果(`GenerateResultDTO`)を、会話の文脈と一緒に返す
    (ADR-014: Conversation EngineはForge Language知識を持たず、既存の
    `/generate`と全く同じ生成結果をそのまま横流しする)。"""

    version: Literal["1.0"] = "1.0"
    status: Literal["build"] = "build"
    session_id: str
    need_model: NeedModelDTO
    build_brief: str
    result: GenerateResultDTO
    readiness: str = "build_ready"
    """FORGE-CONVERSATION-READY-001(2026-08-12)新設。どのReadinessで
    作ることにしたか(`build_ready` / `safe_to_assume`)。Metrics・
    Golden Test・Debugのために返す(指示書2章)。"""


# ---------------------------------------------------------------------------
# POST /api/v1/ai/update — Forming Operation(FORGE-PRODUCT-VISION-002
# TD40対応、2026-08-11)。Held状態のアプリを、会話で「育てる」。
# ---------------------------------------------------------------------------

    timings: StageTimingsDTO | None = None
    """段ごとの実測時間（計測できたときだけ載る）。UI は使わない。"""



class UpdateRequest(BaseModel):
    version: Literal["1.0"] = "1.0"
    forge_document: dict[str, Any] = Field(..., description="更新対象の既存Forge Document(現在の状態そのまま)")
    change_request: str = Field(..., min_length=1, max_length=2000, description="ユーザーの変更要求(自然言語)")
    provider: Literal["mock", "gemini", "local"] | None = None
    """`local` は FORGE-020A で開けた（上の `ConverseRequest` と同じ理由）。"""

    artifact_id: str | None = Field(None, min_length=1)
    seen_version_token: str | None = Field(None, min_length=1)
    idempotency_key: str | None = Field(None, max_length=200)


class UpdateResultDTO(BaseModel):
    forge_document: dict[str, Any]
    validation: ValidationResultDTO
    attempts: int
    artifact: ArtifactRefDTO | None = None
    revision_mode: Literal["local_semantic_patch", "full_regen_fallback"] = "full_regen_fallback"
    semantic_operation: str | None = None
    semantic_target: dict[str, str] | None = None
    critic_passed: bool = False
    revision_provider: str = Field(
        default="forge_deterministic",
        description=(
            "**実際にこの文書を変えたのは誰か**(FORGE-019B §4)。"
            "局所patchはLLMを1回も呼ばないので`forge_deterministic`。"
            "全体再生成へ落ちた場合は実際に生成したProvider名。"
            "会話のProvider(`provider`)とは別物であり、混ぜない"
        ),
    )
    replayed: bool = Field(
        default=False,
        description="再送に対して以前の結果をそのまま返したか(FORGE-019B §2)",
    )


class UpdateSuccessResponse(BaseModel):
    version: Literal["1.0"] = "1.0"
    status: Literal["success"] = "success"
    result: UpdateResultDTO


class ConverseUpdateResponse(SimulatedOutputMixin):
    """`/converse`がConversationSessionから`update`と判定した場合の
    レスポンス(FORGE-PRODUCT-VISION-002続き、2026-08-11新設)。中身は
    `UpdateSuccessResponse`と同じ`ForgeOperationEngine`の結果だが、会話
    セッションの文脈(`session_id`・`need_model`・変更要求の要約)も
    一緒に返す(`ConverseBuildResponse`と対称的な設計)。"""

    version: Literal["1.0"] = "1.0"
    status: Literal["update"] = "update"
    session_id: str
    need_model: NeedModelDTO
    change_request: str
    result: UpdateResultDTO


# ---------------------------------------------------------------------------
# POST /api/v1/ai/feedback — 「これでいい / そこは違う」(FORGE-016A §3、
# 2026-08-24)。
#
# **入口はここ1つだけである。** Evidence Storeを直接叩く近道を作らない
# (`app/ai/gateway/artifact_feedback.py`の冒頭を参照)。入口が増えるたび
# に記録の意味が経路ごとにずれ、集計が静かに嘘になる。
# ---------------------------------------------------------------------------

    timings: StageTimingsDTO | None = None
    """段ごとの実測時間（計測できたときだけ載る）。UI は使わない。"""



class FeedbackRequest(BaseModel):
    """利用者がその生成物をどう扱ったか。

    **内部refは受け取らない。** `artifact_id`(Forgeが発行した不透明な
    ID)か`session_id`のどちらかで指す。任意のrefを信用すると、見ても
    いない生成物へ「受け入れた」を書けてしまう。

    **発話は受け取らない。** 何と言って評価したかは記録しない
    (006 §22 / 016A §10のPrivacy境界)。ここにあるのは「どう扱われたか」
    という閉じた語彙だけである。
    """

    signal: Literal["accepted", "corrected", "abandoned"] = Field(
        ..., description="accepted=明示的に承認 / corrected=訂正された / abandoned=そこで終わった。unknownは受け付けない(沈黙は情報ではない)"
    )
    artifact_id: str | None = Field(default=None, description="generate/converseのresult.artifact.artifact_id")
    session_id: str | None = Field(default=None, description="artifact_idが無い場合の代替。そのセッションの最新の生成物へ書く")
    seen_version_token: str | None = Field(
        default=None,
        description="利用者が見ていた世代のtoken。いまの世代と違えばstale_artifactとして拒否する",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "同じ送信の繰り返しを見分けるためのキー(FORGE-017A §2)。"
            "一致すると duplicate_request として追記しない。"
            "**省略した場合は再送とみなさず、別の評価として追記する**"
            "——分からないものを『たぶん再送』へ倒すと、本物の再評価が静かに消える"
        ),
    )


class FeedbackResponse(BaseModel):
    """記録できたか、できなかったならなぜか。

    **黙って捨てない。** 拒否した理由を返さないと、Client側は
    「記録された」と思い込んだまま動き続ける。
    """

    version: Literal["1.0"] = "1.0"
    status: Literal["success"] = "success"
    recorded: bool = Field(..., description="評価をEventとして追記できたか")
    signal: str
    summary_updated: bool = Field(
        default=False,
        description=(
            "要約(user_acceptance)を更新したか。2回目以降はfalseになる"
            "——要約は最初の信号が勝つ。**recorded=true かつ summary_updated=false は正常**であり、"
            "「事実は残したが要約は変えなかった」という意味(FORGE-017A §2)"
        ),
    )
    rejected: str | None = Field(
        default=None,
        description="unknown_artifact / stale_artifact / duplicate_request / unusable_signal のいずれか。recordedがtrueならnull",
    )
