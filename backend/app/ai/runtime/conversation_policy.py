"""Conversation Policy(FORGE-CONVERSATION-READY-001、2026-08-12)。

「どこまで聞いたら作るのか」を**決定的に**judgeする層。

指示書3章の原則をこのモジュールが体現する:

    LLM Proposal  <  Deterministic System Facts / Safety Rules

`ConversationEngine`はLLMを1回呼び、その結果(NeedModel + 提案action)を
このモジュールへ渡すだけである。実際にASK/BUILD/UPDATE/CONFIRMの
どれにするかは、ここに書かれた決定的なルールが決める。LLMの
`next_action`も`confidence`も、**単独では決して**BUILDの理由にならない。

**なぜ3つのPolicyを1モジュールに置いたか**: 指示書12章は
`readiness_policy`/`question_policy`/`confirmation_policy`への分離を
許可しているが、同時に「空の抽象化は作らない」とも指示している。
3つはいずれも「事実 → どうするか」という同じ入力(NeedModel +
DecisionContext)を共有し、互いに参照し合う(Readinessの判定に
Confirm判定が要る)。ファイルを3つに割ると、共有する型と定数を
行き来するだけの薄いモジュールが2つ増える。責務はモジュール内の
セクション見出しで明確に分けたうえで、1ファイルに保っている。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.runtime.conversation_types import (
    ConversationAction,
    ConversationReadiness,
    DecisionContext,
    NeedModel,
    QuestionStrategy,
    SafeAssumption,
    UnknownImpact,
    UnknownItem,
)

__all__ = [
    "ConfirmationDecision",
    "escalate_question_strategy",
    "shrink_assumption_for",
    "user_delegated_decision",
    "ReadinessDecision",
    "classify_build_failure",
    "detect_risk_signals",
    "evaluate_readiness",
    "requires_confirmation",
    "resolve_action",
    "select_question",
]


# ---------------------------------------------------------------------------
# Confirmation Policy(指示書4章)
# ---------------------------------------------------------------------------

# 外部作用(Forgeの外・他人へ影響が及ぶ)を示す語。ユーザーの発話に
# 現れた場合、LLMの判断に関わらずCONFIRMを必須にする(指示書4章)。
#
# **単なるUI生成・安全なローカルTool作成では毎回CONFIRMしないこと**
# (指示書4章)という制約があるため、ここに列挙するのは「実際に外部へ
# 出て行く/他人に届く/元へ戻せない」操作に限る。「記録したい」
# 「管理したい」のような、ローカルに閉じた語は決して入れない。
_EXTERNAL_EFFECT_KEYWORDS: tuple[str, ...] = (
    "送って", "送信", "送りたい", "共有", "シェア", "公開", "招待",
    "通知して", "メール", "LINEで", "投稿",
)

_DESTRUCTIVE_KEYWORDS: tuple[str, ...] = (
    "削除", "消して", "消したい", "全部消", "初期化", "リセットして",
    "支払", "購入", "課金", "決済", "送金",
    "権限", "パスワード", "アカウントを",
)


@dataclass(frozen=True)
class ConfirmationDecision:
    required: bool
    reason: str | None = None

    def __bool__(self) -> bool:  # `if decision:` と書けるように
        return self.required


def detect_risk_signals(text: str) -> tuple[bool, bool]:
    """ユーザー発話から(external_effect, destructive)を決定的に検出する。

    LLMにも同じ判断を申告させる(`conversation_engine.py`のschema)が、
    **LLMが「外部作用は無い」と言っても、ここで検出されれば
    CONFIRMになる**(指示書3章: System Facts優先)。逆は成り立つ
    ——LLMが検出した外部作用は、キーワードに無くても尊重する
    (安全側に倒す)。
    """
    lowered = text or ""
    external = any(k in lowered for k in _EXTERNAL_EFFECT_KEYWORDS)
    destructive = any(k in lowered for k in _DESTRUCTIVE_KEYWORDS)
    return external, destructive


def requires_confirmation(context: DecisionContext) -> ConfirmationDecision:
    """外部作用・不可逆操作を含むならCONFIRMを要求する(指示書4章)。

    Confirm Screen(専用画面)を復活させるのではなく、**会話の中で
    確認する**ための判定である(指示書4章)——戻り値は
    `ConversationAction.CONFIRM`となり、`/converse`は質問と同じ形で
    確認文を返す。
    """
    if context.external_effect and context.destructive:
        return ConfirmationDecision(
            True, "外部への送信・共有と、元に戻せない操作の両方を含むため"
        )
    if context.external_effect:
        return ConfirmationDecision(True, "Forgeの外(他の人・外部サービス)へ影響が及ぶため")
    if context.destructive:
        return ConfirmationDecision(True, "削除・金銭・権限など、元に戻せない操作を含むため")
    return ConfirmationDecision(False)


# ---------------------------------------------------------------------------
# Question Policy(指示書5章)
# ---------------------------------------------------------------------------


def _askable_impacts(context: DecisionContext) -> frozenset[UnknownImpact]:
    """今このターンで「質問してよい」重要度の集合。

    **`MAX_CONVERSATION_TURNS`の新しい意味**(指示書1章): ターン上限は
    BUILD条件ではなく、**質問戦略を変更する閾値**である。上限に達した
    ら、HIGH(解の構造は変わるが、答えなくても作れる)は質問をやめて
    Safe Assumptionへ回す。一方`BLOCKING`は上限に達しても質問し続ける
    ——「質問しすぎない」と「分からなくても作る」は別だからである
    (指示書1章)。
    """
    if context.at_or_over_turn_threshold:
        return frozenset({UnknownImpact.BLOCKING})
    return frozenset({UnknownImpact.BLOCKING, UnknownImpact.HIGH})


def select_question(need_model: NeedModel, context: DecisionContext) -> UnknownItem | None:
    """次に聞くべき未知を1件選ぶ。聞くべきものが無ければ`None`。

    規則(指示書5章):
    * 質問するのは`BLOCKING`・`HIGH`のみ。`LOW`はSafe Assumption候補、
      `COSMETIC`はDesign Systemが決めるため決して聞かない。
    * 同じUnknownを言い換えて繰り返し質問しない
      (`context.asked_question_keys`に載っているkeyは選ばない)。
    * `BLOCKING`を`HIGH`より優先する。
    """
    allowed = _askable_impacts(context)
    candidates = [
        u for u in need_model.unknowns
        if u.status == "unknown" and u.impact in allowed and u.key not in context.asked_question_keys
    ]
    if not candidates:
        return None
    blocking = [u for u in candidates if u.impact == UnknownImpact.BLOCKING]
    return (blocking or candidates)[0]


def assumptions_for_unasked(need_model: NeedModel, context: DecisionContext) -> tuple[SafeAssumption, ...]:
    """質問せずに済ませる未知を、理由付きのSafe Assumptionへ変換する
    (指示書6章: 仮定にも「なぜ」を残す)。

    対象は「質問対象になりえたが、聞かないと決めたもの」:
    * `LOW`・`COSMETIC`(そもそも質問しない重要度)
    * 既に質問済みの`HIGH`(繰り返し聞かない)
    * ターン閾値に達した後の`HIGH`(質問戦略の変更、指示書1章)
    """
    allowed = _askable_impacts(context)
    result: list[SafeAssumption] = []
    for u in need_model.unknowns:
        if u.status != "unknown":
            continue
        if u.impact == UnknownImpact.BLOCKING:
            continue  # BLOCKINGは決して仮定で済ませない
        already_asked = u.key in context.asked_question_keys
        not_askable_now = u.impact not in allowed
        if u.impact in (UnknownImpact.LOW, UnknownImpact.COSMETIC):
            reason = f"解の構造を変えないため({u.impact.value})。Forge側の既定で進める"
        elif already_asked:
            reason = "一度確認済みのため、繰り返し質問せず既定で進める"
        elif not_askable_now:
            reason = "会話が長くなったため、質問せず既定で進める(後から変更できる)"
        else:
            continue
        result.append(SafeAssumption(key=u.key, value="forge_default", reason=reason))
    return tuple(result)


# ---------------------------------------------------------------------------
# Readiness Policy(指示書2章)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadinessDecision:
    readiness: ConversationReadiness
    question: UnknownItem | None = None
    confirm_reason: str | None = None
    strategy: QuestionStrategy = QuestionStrategy.ASK
    """FORGE-QUALITY-AI-INDEPENDENCE-003 §15。`NEEDS_QUESTION`/
    `INSUFFICIENT_INFORMATION`のとき、どう聞くか(段)。"""

    shrink_assumption: SafeAssumption | None = None
    """`SHRINK_SOLUTION`のとき、そのUnknownを必要としない最小の解へ
    落とすために採用する既定(指示書14章)。"""


def evaluate_readiness(need_model: NeedModel, context: DecisionContext) -> ReadinessDecision:
    """NeedModelとSystem Factsから、決定的にReadinessを導出する。

    **LLMの`confidence`も`next_action`も、ここでは一切参照しない**
    (指示書2章「LLMの自己申告confidenceだけでBUILD判断をしない」)。
    参照するのは、未知の件数とimpact、既に質問したkey、ターン数、
    外部作用・不可逆操作の有無、既存Toolの有無——すべてForge側が
    事実として知っていることだけである。

    判定順序(上から順に、最初に該当したもの):

    1. 外部作用・不可逆操作あり → `NEEDS_CONFIRMATION`
       (安全性が最優先。情報が揃っていても確認を挟む)
    2. 聞くべき未知(BLOCKING/HIGHかつ未質問)あり → `NEEDS_QUESTION`
    3. BLOCKINGが質問済みなのに未解消 → `INSUFFICIENT_INFORMATION`
       (**決してBUILDしない**。ターン数を理由にBUILDへ倒すことは無い)
    4. 残る未知がLOW以下 → `SAFE_TO_ASSUME`
    5. 未知なし → `BUILD_READY`
    """
    confirmation = requires_confirmation(context)
    if confirmation.required:
        return ReadinessDecision(
            ConversationReadiness.NEEDS_CONFIRMATION, confirm_reason=confirmation.reason
        )

    question = select_question(need_model, context)
    if question is not None:
        return ReadinessDecision(ConversationReadiness.NEEDS_QUESTION, question=question)

    # ここへ来た時点で「今このターンで**通常の質問として**聞くべきもの
    # は無い」。ただしBLOCKINGが残っているなら、それは「質問済みなのに
    # 解消していない」ということであり、勝手に作ってはならない
    # (指示書16章の完了条件)。
    #
    # **FORGE-QUALITY-AI-INDEPENDENCE-003 §15**: ここで従来は無条件に
    # `INSUFFICIENT_INFORMATION`(=同じことをまた聞く)へ倒しており、
    # ユーザーが「分からない」「任せる」と答え続けた場合に**無限ASK**へ
    # 陥る経路が残っていた。Strategy Escalationで段を上げる。
    unresolved_blocking = need_model.blocking_unknowns()
    if unresolved_blocking:
        target = unresolved_blocking[0]
        strategy = escalate_question_strategy(
            target,
            ask_count=context.ask_count_for(target.key),
            delegated=context.user_delegated,
            context=context,
        )
        if strategy is QuestionStrategy.SHRINK_SOLUTION:
            # そのUnknownを必要としない最小の解へ落として作る
            # (指示書14章 Smallest Useful Tool)。
            return ReadinessDecision(
                ConversationReadiness.SAFE_TO_ASSUME,
                strategy=strategy,
                shrink_assumption=shrink_assumption_for(target),
            )
        if strategy is QuestionStrategy.STOP:
            # 高リスクなUnknownは、縮退も既定採用もしない。
            # 勝手に仮定せず、確認として返す(指示書31章 最低条件C)。
            return ReadinessDecision(
                ConversationReadiness.NEEDS_CONFIRMATION,
                question=target, strategy=strategy,
                confirm_reason=(
                    f"{target.key}が決まらないまま進めると、取り返しのつかない"
                    "操作になる可能性があるため"
                ),
            )
        return ReadinessDecision(
            ConversationReadiness.INSUFFICIENT_INFORMATION,
            question=target, strategy=strategy,
        )

    if any(u.status == "unknown" for u in need_model.unknowns):
        return ReadinessDecision(ConversationReadiness.SAFE_TO_ASSUME)
    return ReadinessDecision(ConversationReadiness.BUILD_READY)


# ---------------------------------------------------------------------------
# Strategy Escalation / Unresolvable Unknown(指示書12〜15章)
# ---------------------------------------------------------------------------

# 同じUnknownについて、通常の質問(ASK)→聞き直し(REPHRASE)→既定の
# 提示(OFFER_DEFAULT)→縮退(SHRINK_SOLUTION)と段を上げる境界。
# **MAX_CONVERSATION_TURNSとは別物**である: あちらは会話全体の長さ、
# こちらは「この1つのUnknownに何回向き合ったか」。
_REPHRASE_AFTER_ASKS = 1
_OFFER_DEFAULT_AFTER_ASKS = 2
_SHRINK_AFTER_ASKS = 3

# ユーザーが「決めてくれ」と委ねたことを示す表現(指示書12章の
# `user_delegated_decision`)。これが出たら、同じことを聞き続けるのは
# 会話として失礼であり、既定を提示する段へ即座に進む。
_DELEGATION_PHRASES: tuple[str, ...] = (
    "わからない", "分からない", "わかんない", "任せる", "まかせる",
    "おまかせ", "お任せ", "どっちでもいい", "どちらでも", "なんでもいい",
    "何でもいい", "決めて", "きめて", "特にない", "とくにない",
)


def user_delegated_decision(text: str) -> bool:
    """ユーザーが判断をForgeへ委ねたか(指示書12章)。

    「分からない」「任せる」「どっちでもいい」に対して同じ質問を
    繰り返すのは、`repeated_question`以前に会話として成立していない。
    """
    lowered = (text or "").strip()
    return any(phrase in lowered for phrase in _DELEGATION_PHRASES)


def escalate_question_strategy(
    unknown: UnknownItem,
    *,
    ask_count: int,
    delegated: bool,
    context: DecisionContext,
) -> QuestionStrategy:
    """同じUnknownに対して、次にどう振る舞うかを決める(指示書15章)。

    **`MAX_CONVERSATION_TURNS`による強制BUILDへは戻さない**。ここで
    上がるのは「聞き方の段」であって、「作ってしまう」判断ではない。

    高リスク(外部作用・不可逆操作)の場合だけ、`OFFER_DEFAULT`や
    `SHRINK_SOLUTION`を**飛ばして`STOP`**にする。「共有範囲が分からない
    から、とりあえず全体公開にしておきますね」のような既定は、
    取り返しがつかないためである(指示書13章 HARD_BLOCKING)。
    """
    high_risk = context.external_effect or context.destructive

    if delegated:
        # 委ねられた以上、聞き直しは飛ばす。ただし高リスクなら
        # 「任せる」と言われても勝手に決めない(指示書31章 最低条件C)。
        return QuestionStrategy.STOP if high_risk else QuestionStrategy.OFFER_DEFAULT

    if ask_count <= _REPHRASE_AFTER_ASKS:
        return QuestionStrategy.ASK if ask_count == 0 else QuestionStrategy.REPHRASE
    if ask_count <= _OFFER_DEFAULT_AFTER_ASKS:
        return QuestionStrategy.STOP if high_risk else QuestionStrategy.OFFER_DEFAULT
    if ask_count <= _SHRINK_AFTER_ASKS:
        return QuestionStrategy.STOP if high_risk else QuestionStrategy.SHRINK_SOLUTION
    return QuestionStrategy.STOP if high_risk else QuestionStrategy.SHRINK_SOLUTION


def shrink_assumption_for(unknown: UnknownItem) -> SafeAssumption:
    """縮退時に採用する既定を、理由付きで組み立てる(指示書14章)。

    「作れない」と言う代わりに、**そのUnknownを必要としない最小の解**
    へ落とす。Forgeの製品思想「まず小さく作る → 会話で育てる」を
    ここで守る——後から`UPDATE`で広げられるため、この既定は
    取り返しがつく。
    """
    return SafeAssumption(
        key=unknown.key,
        value="minimal",
        reason=(
            f"{unknown.key}が決まらなかったため、これを必要としない"
            "最小の形でまず作る(後から会話で広げられる)"
        ),
    )


# ---------------------------------------------------------------------------
# Action 決定(指示書3章: System Facts / Safety Rulesで一貫して決める)
# ---------------------------------------------------------------------------

_BUILDABLE = frozenset({ConversationReadiness.BUILD_READY, ConversationReadiness.SAFE_TO_ASSUME})


def resolve_action(
    readiness: ConversationReadiness, context: DecisionContext
) -> ConversationAction:
    """ReadinessとSystem Factsから、最終的なActionを決める。

    LLMの提案(`context.llm_proposed_action`)が効くのは
    **「BUILDとUPDATEのどちらか」という一点だけ**であり、しかも
    `has_existing_tool`が事実として`True`のときに限る(指示書3章:
    existing_toolがない → UPDATE不可)。「作ってよいか」自体は
    Readinessが決めるのであって、LLMの申告では決まらない。
    """
    if readiness == ConversationReadiness.NEEDS_CONFIRMATION:
        return ConversationAction.CONFIRM
    if readiness in (
        ConversationReadiness.NEEDS_QUESTION,
        ConversationReadiness.INSUFFICIENT_INFORMATION,
    ):
        return ConversationAction.ASK
    assert readiness in _BUILDABLE  # noqa: S101 — ConversationReadinessは5値であり、上で3値を処理済み
    if context.llm_proposed_action == "update" and context.has_existing_tool:
        return ConversationAction.UPDATE
    return ConversationAction.BUILD


# ---------------------------------------------------------------------------
# Build Failure 分類(指示書8章)
# ---------------------------------------------------------------------------

# 生成失敗のうち、「ユーザーへ追加で聞けば解消しうる」段階。
# Cognitive Pipelineのどの段階で落ちたかで判断する——理解(入力の
# 曖昧さ)の段階で落ちたなら追加質問で解消しうるが、Forge Language
# 生成・Validator・Repairで落ちたのは**Forge側の不具合**であり、
# ユーザーに聞いても直らない(指示書8章「AIの失敗とユーザー情報不足を
# 混同しないこと」)。
_QUESTION_RECOVERABLE_STAGES: frozenset[str] = frozenset({
    "normalization", "ambiguity_detection", "domain_classification",
    "intent_recognition", "meaning_extraction", "conversation",
})


def classify_build_failure(*, stage: str | None, sub_reason: str | None) -> bool:
    """BUILD失敗が「追加質問で解消しうる」ものかを判定する(指示書8章)。

    `True`なら`/converse`はASKへ戻し(「少しだけ確認させて。」)、
    `False`なら安全なエラー表示へ倒す。**内部不具合をユーザーの
    情報不足のように見せない**ため、既定は`False`(内部不具合扱い)と
    し、明示的に該当する段階だけ`True`にしている。
    """
    if sub_reason in ("rate_limited", "unavailable"):
        # Provider側の一時障害。ユーザーに聞いても直らない。
        return False
    return bool(stage) and stage in _QUESTION_RECOVERABLE_STAGES
