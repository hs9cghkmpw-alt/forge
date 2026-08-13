"""Conversation Engine — 型定義(FORGE-PRODUCT-VISION-002、2026-08-11)。

CEO指示書「『アプリを作るAI』から『困りごとを話すと道具が生まれる
AI』への製品思想更新」への対応。設計の背景・判断根拠は
`docs/spec/FORGE_PRODUCT_VISION_002_CONVERSATIONAL_ARCHITECTURE.md`
(Phase B)・`docs/adr/ADR-014-conversation-engine-wraps-not-replaces-
pipeline.md`を参照。

このファイルはforge_ai/を一切importしない(ADR-014: Conversation
Engineは既存Cognitive Pipelineの「外」に立つ、薄い意思決定層)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ConversationAction(str, Enum):
    """指示書22章のASK/BUILD/UPDATE/CONFIRM契約。

    FORGE-CONVERSATION-READY-001(2026-08-12)で`CONFIRM`が実際に発火する
    ようになった(それまでは型としてのみ存在した)。発火条件は
    `conversation_policy.requires_confirmation()`が決定的に判定する。
    """

    ASK = "ask"
    BUILD = "build"
    UPDATE = "update"
    CONFIRM = "confirm"


class QuestionStrategy(str, Enum):
    """未解消のUnknownに対して、次に取る手
    (FORGE-QUALITY-AI-INDEPENDENCE-003 §15 Strategy Escalation)。

    **MAX_TURNSによる強制BUILDへは決して戻さない**。代わりに、同じ
    Unknownについて情報量が増えていないとき、聞き方そのものを
    段階的に変える:

        ASK → REPHRASE → OFFER_DEFAULT → SHRINK_SOLUTION → BUILD/CONFIRM/STOP
    """

    ASK = "ask"
    """通常の質問(初回)。"""

    REPHRASE = "rephrase"
    """同じUnknownを、別の角度・短い二択で聞き直す。"""

    OFFER_DEFAULT = "offer_default"
    """「こう決めておきますね」と既定を提示して合意を取る。"""

    SHRINK_SOLUTION = "shrink_solution"
    """そのUnknownを**必要としない**、より小さい解へ縮退する
    (指示書14章 Smallest Useful Tool)。"""

    STOP = "stop"
    """縮退もできず、勝手に仮定してもいけない(高リスク)。
    正直に「作れない」と伝える。"""


class UnknownImpact(str, Enum):
    """未知情報が「解(作られる道具)」をどれだけ変えるか
    (FORGE-CONVERSATION-READY-001 指示書5章のQuestion Policy)。

    質問してよいのは原則`BLOCKING`・`HIGH`のみ。`LOW`はSafe Assumption
    の候補、`COSMETIC`はDesign Systemが決めるため決して質問しない。
    """

    BLOCKING = "blocking"
    """これが分からないと、そもそも何を作るか決まらない。"""

    HIGH = "high"
    """解の構造が大きく変わる(例: 家族と共有するか=永続化と権限が変わる)。"""

    LOW = "low"
    """解の構造は変わらない。Safe Assumptionで進めてよい。"""

    COSMETIC = "cosmetic"
    """見た目・配置。Design Systemの領分であり、質問してはならない。"""

    @property
    def is_hard_blocking(self) -> bool:
        """FORGE-QUALITY-AI-INDEPENDENCE-003 §13。**推測してはならない**
        種類のBLOCKINGか。

        指示書は`HARD_BLOCKING`/`SOFT_BLOCKING`という別の列挙も許容して
        いるが、Forgeでは既に「外部作用・不可逆操作」を
        `DecisionContext.external_effect`/`destructive`という**System
        Factsとして別途持っている**(指示書3章)。同じ意味の分類を
        Unknown側にも二重に持つと、両者が食い違ったときにどちらが
        正なのか決められなくなる。したがってHARD/SOFTの区別は、
        Unknownのimpact値ではなく`DecisionContext`側の事実で判定する
        (`conversation_policy.escalate_question_strategy()`参照)。
        このプロパティは、その判断が「Unknown単体では決まらない」ことを
        明示するために置いている。
        """
        return False


_ASKABLE_IMPACTS: frozenset[UnknownImpact] = frozenset({UnknownImpact.BLOCKING, UnknownImpact.HIGH})


class ConversationReadiness(str, Enum):
    """「どこまで聞いたら作るのか」の判定結果
    (指示書2章 Conversation Readiness)。

    **LLMの自己申告confidenceだけでBUILD判断をしない**という原則
    (指示書2章・3章)のため、この値は`conversation_policy.
    evaluate_readiness()`が、System Facts(既存Toolの有無・ターン数・
    既に質問した項目・外部作用の有無)とNeedModelから**決定的に**導出する。
    """

    BUILD_READY = "build_ready"
    """重要な未知が無い。そのまま作れる。"""

    SAFE_TO_ASSUME = "safe_to_assume"
    """残る未知はLOW以下(または質問済みのHIGH)。Safe Assumptionを
    明示して作る。"""

    NEEDS_QUESTION = "needs_question"
    """まだ聞くべき(BLOCKING/HIGHかつ未質問の)未知がある。"""

    NEEDS_CONFIRMATION = "needs_confirmation"
    """外部作用・不可逆操作を含む。実行前に確認が要る。"""

    INSUFFICIENT_INFORMATION = "insufficient_information"
    """BLOCKINGな未知が、質問済みにもかかわらず解消していない。
    **決してBUILDしない**(指示書16章の完了条件)。ターン数を理由に
    BUILDへ倒すことは無い——質問の仕方を変えて聞き直す。"""


@dataclass(frozen=True)
class ConversationTurn:
    role: Literal["user", "forge"]
    text: str


@dataclass(frozen=True)
class UnknownItem:
    """未知情報1件(指示書6章: 「なぜ重要なのか」を追跡できるようにする)。

    `reason`を必ず持たせるのは、Debug・Golden Test・Product Analytics・
    将来のAI学習で判断根拠を追えるようにするため(指示書6章)。
    """

    key: str
    impact: UnknownImpact
    reason: str
    status: Literal["unknown", "resolved"] = "unknown"

    @property
    def askable(self) -> bool:
        """質問してよい重要度か(COSMETIC/LOWは質問しない)。"""
        return self.impact in _ASKABLE_IMPACTS

    def to_dict(self) -> dict:
        return {
            "key": self.key, "impact": self.impact.value,
            "reason": self.reason, "status": self.status,
        }


@dataclass(frozen=True)
class SafeAssumption:
    """Forge側が「聞かずに決めた」こと1件(指示書6章)。

    `reason`を必ず持たせるのはUnknownItemと同じ理由。加えて、
    ユーザーへ「こう仮定しました」と説明できる材料にもなる。
    """

    key: str
    value: str
    reason: str

    def to_dict(self) -> dict:
        return {"key": self.key, "value": self.value, "reason": self.reason}


@dataclass(frozen=True)
class NeedModel:
    """指示書9章の概念例を、Gemini structured outputで安定して返せる形
    (非再帰的なフラット構造)へ具体化したもの(design doc B.2)。

    `known`は指示書の概念例(`dict[str, bool]`)ではなく`list[str]`に
    した。Gemini `responseSchema`はOpenAPI Schemaのサブセットであり、
    任意のkeyを持つdict(`additionalProperties`)よりも、固定shapeの
    array/objectの方が安定して返る。

    **FORGE-CONVERSATION-READY-001(2026-08-12)での拡張(指示書6章)**:
    未知・仮定を、単なる文字列から`UnknownItem`/`SafeAssumption`
    (impact・reason付き)へ格上げした。旧来の文字列リストとしての
    見え方は`unknown_important`/`safe_assumptions`プロパティが提供する
    ため、既存の呼び出し側(`to_dict()`経由のHTTP DTO、Flutter側の
    `NeedModelSummary`)は一切変更せずに済む。
    """

    problem: str
    known: tuple[str, ...] = ()
    unknowns: tuple[UnknownItem, ...] = ()
    assumptions: tuple[SafeAssumption, ...] = ()
    confidence: float = 0.0

    @property
    def unknown_important(self) -> tuple[str, ...]:
        """後方互換の見え方: 質問対象になりうる(BLOCKING/HIGH)未知のkey。

        **`confidence`と同様、これ単独でBUILD判断に使ってはならない**
        (指示書2章)。判断は`conversation_policy.evaluate_readiness()`
        が行う。
        """
        return tuple(u.key for u in self.unknowns if u.askable and u.status == "unknown")

    @property
    def safe_assumptions(self) -> tuple[str, ...]:
        """後方互換の見え方: 仮定を「key=value」の文字列で返す。"""
        return tuple(f"{a.key}={a.value}" for a in self.assumptions)

    def blocking_unknowns(self) -> tuple[UnknownItem, ...]:
        return tuple(
            u for u in self.unknowns
            if u.impact == UnknownImpact.BLOCKING and u.status == "unknown"
        )

    def to_dict(self) -> dict:
        """HTTP DTO(`NeedModelDTO`)へそのまま渡せる形。

        `unknown_important`/`safe_assumptions`という既存のキー名・型
        (文字列リスト)は維持したまま、`unknowns`/`assumptions`という
        リッチな表現を**追加**する(既存のFlutter側パースを壊さない)。
        """
        return {
            "problem": self.problem,
            "known": list(self.known),
            "unknown_important": list(self.unknown_important),
            "safe_assumptions": list(self.safe_assumptions),
            "confidence": self.confidence,
            "unknowns": [u.to_dict() for u in self.unknowns],
            "assumptions": [a.to_dict() for a in self.assumptions],
        }


@dataclass(frozen=True)
class DecisionContext:
    """ASK/BUILD/UPDATE/CONFIRMの判断に使う**System Facts**
    (指示書3章: LLM Proposal < Deterministic System Facts)。

    ここに入るのは、LLMの申告ではなく**Forge側が事実として知っている
    こと**だけである。`llm_proposed_action`だけは例外的にLLMの提案を
    そのまま持つが、これは「提案として参照する」ためであり、
    Policyはこれを鵜呑みにしない。
    """

    has_existing_tool: bool = False
    user_turn_count: int = 0
    asked_question_keys: tuple[str, ...] = ()
    """このセッションで既に質問した未知のkey(同じUnknownを言い換えて
    繰り返し質問しないため。指示書5章)。"""

    llm_proposed_action: str | None = None
    external_effect: bool = False
    """外部送信・他人への通知・公開・共有範囲変更など、Forgeの外へ
    影響が及ぶか(指示書4章)。"""

    destructive: bool = False
    """削除・不可逆操作・金銭操作・権限変更を含むか(指示書4章)。"""

    ask_counts: dict[str, int] = field(default_factory=dict)
    """FORGE-QUALITY-AI-INDEPENDENCE-003 §12。Unknownのkeyごとの質問回数。
    Strategy Escalationの段を決める(`asked_question_keys`が
    「聞いたか」の有無であるのに対し、こちらは回数)。"""

    user_delegated: bool = False
    """ユーザーが「分からない」「任せる」と判断を委ねたか(§12の
    `user_delegated_decision`)。同じことを聞き続けないための事実。"""

    def ask_count_for(self, key: str) -> int:
        return self.ask_counts.get(key, 0)

    @property
    def at_or_over_turn_threshold(self) -> bool:
        """`MAX_CONVERSATION_TURNS`に達したか。

        **これはBUILD条件ではない**(指示書1章)。質問戦略を変える
        閾値としてのみ使う(より短い二択にする、HIGHをSafe Assumption
        へ回す、「まず小さく作る」と伝える)。
        """
        from app.ai.runtime.conversation_store import MAX_CONVERSATION_TURNS

        return self.user_turn_count >= MAX_CONVERSATION_TURNS


@dataclass(frozen=True)
class ConversationStepResult:
    """`ConversationEngine.step()`の戻り値。"""

    action: ConversationAction
    need_model: NeedModel
    question: str | None = None
    """action == ASKの場合のみ、意味のある値を持つ(1問だけ)。"""

    build_brief: str | None = None
    """action == BUILD/UPDATEの場合のみ、意味のある値を持つ。既存の
    `PromptPipeline.run()`へそのまま渡せる、会話全体を要約した1つの
    自然文(ADR-014、design doc B.1)。"""

    readiness: ConversationReadiness = ConversationReadiness.BUILD_READY
    """この判断の根拠となったReadiness(指示書2章)。Metrics・Golden
    Test・Debugのために必ず載せる。"""

    confirm_reason: str | None = None
    """action == CONFIRMの場合のみ。何を確認したいのか(指示書4章)。"""

    question_key: str | None = None
    """action == ASKの場合のみ。今聞いている未知のkey(繰り返し質問の
    抑止に使う。指示書5章)。"""

    strategy: QuestionStrategy = QuestionStrategy.ASK
    """FORGE-QUALITY-AI-INDEPENDENCE-003 §15。この質問がEscalationの
    どの段か(ASK/REPHRASE/OFFER_DEFAULT)。Metricsと Golden Testで
    「同じことを繰り返していないか」を測るために載せる。"""


@dataclass(frozen=True)
class ConversationSession:
    """会話1件分の状態。`ConversationStore`(`confirmation_store.py`と
    同じ設計、プロセス内メモリ)が保持する。"""

    session_id: str
    turns: tuple[ConversationTurn, ...] = field(default_factory=tuple)
    created_at: float = 0.0
    asked_question_keys: tuple[str, ...] = field(default_factory=tuple)
    """FORGE-CONVERSATION-READY-001(2026-08-12)新設。既に質問した未知の
    key。同じUnknownを言い換えて繰り返し質問しないため(指示書5章)。"""

    ask_counts: dict[str, int] = field(default_factory=dict)
    """FORGE-QUALITY-AI-INDEPENDENCE-003 §12新設。Unknownのkeyごとに、
    何回聞いたか。`asked_question_keys`が「聞いたかどうか」の集合で
    あるのに対し、こちらは**Strategy Escalationの段数**を決めるための
    回数である(1回目=ASK、2回目=REPHRASE、…)。"""

    def with_turn(self, turn: ConversationTurn) -> ConversationSession:
        return ConversationSession(
            session_id=self.session_id, turns=self.turns + (turn,),
            created_at=self.created_at, asked_question_keys=self.asked_question_keys,
            ask_counts=dict(self.ask_counts),
        )

    def with_asked_key(self, key: str) -> ConversationSession:
        """そのUnknownを1回聞いたことを記録する。

        `asked_question_keys`は重複しない集合として保つ一方、
        `ask_counts`は**呼ばれるたびに増える**(同じUnknownへ聞き直した
        回数がEscalationの段数になるため)。
        """
        if not key:
            return self
        counts = dict(self.ask_counts)
        counts[key] = counts.get(key, 0) + 1
        keys = self.asked_question_keys
        if key not in keys:
            keys = keys + (key,)
        return ConversationSession(
            session_id=self.session_id, turns=self.turns, created_at=self.created_at,
            asked_question_keys=keys, ask_counts=counts,
        )

    def ask_count_for(self, key: str) -> int:
        return self.ask_counts.get(key, 0)
