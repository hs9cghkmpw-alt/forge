"""Conversation Engine(FORGE-PRODUCT-VISION-002、2026-08-11)。

「聞くか、作るか、既存ツールを変更するか」を判断する薄い意思決定層。
design doc(`docs/spec/FORGE_PRODUCT_VISION_002_CONVERSATIONAL_
ARCHITECTURE.md` Phase B)・ADR-014の実装。`has_existing_tool=True`
(Held画面から会話を再開した場合)が渡されたときのみ`update`を選びうる
(TD40、2026-08-11続き)。

1ターンにつき`AIProvider.complete_structured()`を1回だけ呼ぶ(指示書
21章「毎回5回LLMを呼ぶ必要はない」)。forge_ai/を一切importしない
(Cognitive Pipelineの外に立つ、ADR-014)。
"""

from __future__ import annotations

from app.ai.runtime.conversation_store import MAX_CONVERSATION_TURNS
from app.ai.runtime.conversation_types import (
    ConversationAction,
    ConversationSession,
    ConversationStepResult,
    NeedModel,
)
from app.ai.runtime.provider_router import AIProvider

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "problem": {"type": "string"},
        "known": {"type": "array", "items": {"type": "string"}},
        "unknown_important": {"type": "array", "items": {"type": "string"}},
        "safe_assumptions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "next_action": {"type": "string", "enum": ["ask", "build", "update"]},
        "question": {"type": "string"},
        "build_brief": {"type": "string"},
    },
    "required": [
        "problem", "known", "unknown_important", "safe_assumptions",
        "confidence", "next_action", "question", "build_brief",
    ],
}

# design doc B.3「Forgeが決めてよい領域」(指示書13章)を、プロンプトの
# 中で具体的に例示する。ここに列挙する項目についてunknown_importantへ
# 入れないよう明示的に指示することで、「質問攻めにしない」という
# 指示書5章の原則を、LLMの気まぐれではなく指示として固定する。
_SYSTEM_PROMPT = """あなたはForgeという製品の会話エンジンです。
ユーザーは「アプリを作りたい」とは思っていません。日常のちょっとした
困りごとを話しているだけです。あなたの仕事は、その会話から問題を理解し、
本当に必要な場合だけ1つだけ質問し、十分理解したら道具(アプリ)を
作る判断をすることです。

厳守事項:
1. 質問は、回答によって作るものの構造が大きく変わる場合だけにする。
   対象ユーザー・画面数・色・レイアウト・入力検証の細かさ等、Forge側で
   合理的なデフォルトを決めてよいものについては絶対に質問しない
   (safe_assumptionsへ記録するだけにする)。
2. 質問は一度に1つだけ。
3. 十分理解できたら(unknown_importantが空になったら)、next_actionを
   "build"にする。
4. next_action="build"の場合、build_briefには、この会話全体を踏まえた
   完全で自己完結した日本語の説明文を書くこと(このbuild_brief単体が、
   会話の文脈を一切知らない別のシステムへそのまま渡され、そこから
   アプリが生成される。会話で分かった情報を漏らさず含めること)。
5. next_action="ask"の場合、questionには自然な会話文で1問だけ書く。
   build_briefは空文字列にする。
6. next_action="build"または"update"の場合、questionは空文字列にする。
7. 既に使用中のツールがある場合のみ、"update"を選べる(無い場合は
   選ばないこと)。ユーザーの発話が、今使っているツールへの変更・
   追加要求(例:「よく買うものを上に置きたい」「予算も管理したい」)
   であれば next_action="update" とし、build_briefにはその変更要求を
   完全で自己完結した日本語で書くこと(会話の文脈を知らない別の
   システムが、今のツールのJSONとこの文だけを見て更新する)。
   ユーザーの発話が今のツールと無関係な、全く新しい困りごとであれば、
   "update"ではなく通常どおり"ask"/"build"で判断すること。
"""


def _build_prompt(session: ConversationSession, *, has_existing_tool: bool) -> str:
    lines = [_SYSTEM_PROMPT]
    if has_existing_tool:
        lines.append("\n[状態] ユーザーは現在、既に生成済みのツールを使っています。")
    else:
        lines.append("\n[状態] まだツールは生成されていません(これは新しい会話です)。")
    lines.append("\n[会話]")
    for turn in session.turns:
        speaker = "ユーザー" if turn.role == "user" else "Forge"
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines)


class ConversationEngine:
    """`ConversationSession`を受け取り、1ステップ進める。"""

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def step(self, session: ConversationSession, *, has_existing_tool: bool = False) -> ConversationStepResult:
        """`has_existing_tool`(FORGE-PRODUCT-VISION-002続き、2026-08-11
        新設): 呼び出し側(Held画面)が既存のツールを持っている状態から
        会話を再開した場合に`True`を渡す。この場合のみ、`update`が
        選ばれうる(design doc B.4、TD40)。"""
        if not session.turns or session.turns[-1].role != "user":
            raise ValueError("step()はユーザーの発話が末尾にある状態でのみ呼べます。")

        prompt = _build_prompt(session, has_existing_tool=has_existing_tool)
        raw = self._provider.complete_structured(prompt, _RESPONSE_SCHEMA)

        need_model = NeedModel(
            problem=str(raw.get("problem", "")),
            known=tuple(raw.get("known", []) or []),
            unknown_important=tuple(raw.get("unknown_important", []) or []),
            safe_assumptions=tuple(raw.get("safe_assumptions", []) or []),
            confidence=float(raw.get("confidence", 0.0) or 0.0),
        )

        user_turn_count = sum(1 for t in session.turns if t.role == "user")
        llm_action = raw.get("next_action")
        # `has_existing_tool=False`ならupdateを鵜呑みにしない(更新対象が
        # 無いのにupdateへ倒すと、後段でクラッシュする——決定的な上書き
        # ルール、design doc B.3と同じ思想)。
        wants_update = llm_action == "update" and has_existing_tool

        # design doc B.3: 決定的な上書きルール。LLMの自己申告
        # (next_action)を鵜呑みにしない(指示書11章)。
        # (1) unknown_importantが実質的に空ならBUILD/UPDATEへ倒す。
        # (2) ユーザーターン数が上限に達したらBUILD/UPDATEへ倒す(無限に
        #     聞き続けない、指示書18章のSmallest Useful Tool精神)。
        force_ready = (not need_model.unknown_important) or (user_turn_count >= MAX_CONVERSATION_TURNS)

        if force_ready or llm_action in ("build", "update"):
            brief = str(raw.get("build_brief") or "").strip()
            if not brief:
                # LLMがbuild_briefを空で返した場合(force_readyだが
                # LLM自身はask寄りに判定していた等)の安全網。会話全体を
                # 素朴に連結したものへフォールバックする(クラッシュより、
                # 質の落ちるbriefの方がまだ良い)。
                brief = "。".join(t.text for t in session.turns if t.role == "user")
            action = ConversationAction.UPDATE if wants_update else ConversationAction.BUILD
            return ConversationStepResult(action=action, need_model=need_model, build_brief=brief)

        question = str(raw.get("question") or "").strip()
        if not question:
            # 同じ理由の安全網: askなのに質問文が空なら、素朴なBUILDへ
            # 倒す(空文字の質問をユーザーへ見せるのは、無反応より悪い)。
            build_brief = "。".join(t.text for t in session.turns if t.role == "user")
            return ConversationStepResult(
                action=ConversationAction.BUILD, need_model=need_model, build_brief=build_brief,
            )
        return ConversationStepResult(action=ConversationAction.ASK, need_model=need_model, question=question)
