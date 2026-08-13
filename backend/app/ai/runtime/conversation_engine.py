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

from app.ai.runtime.conversation_policy import (
    assumptions_for_unasked,
    detect_risk_signals,
    evaluate_readiness,
    resolve_action,
    user_delegated_decision,
)
from app.ai.runtime.conversation_types import (
    ConversationAction,
    ConversationReadiness,
    ConversationSession,
    ConversationStepResult,
    DecisionContext,
    NeedModel,
    QuestionStrategy,
    SafeAssumption,
    UnknownImpact,
    UnknownItem,
)
from app.ai.runtime.provider_router import AIProvider

# FORGE-CONVERSATION-READY-001(2026-08-12)で拡張したschema。
#
# * `unknown_important`(文字列配列)→ `unknowns`(key/impact/reasonを
#   持つobject配列)。指示書6章「なぜ重要なのかを追跡できるように」。
# * `safe_assumptions`(文字列配列)→ `assumptions`(key/value/reason)。
# * `external_effect`/`destructive`を追加。指示書4章のCONFIRM判定へ、
#   LLM側の観測を**材料として**渡す(決定はPolicyが行う)。
#
# **Gemini responseSchemaの制約に配慮している点**: object配列は使うが、
# 再帰・`additionalProperties`・`$ref`は使わない(TD40で、
# `properties`の無い`"type": "object"`をGeminiが黙って`{}`にする挙動を
# 確認済み。ここでは全objectに`properties`を明示している)。
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "problem": {"type": "string"},
        "known": {"type": "array", "items": {"type": "string"}},
        "unknowns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "impact": {"type": "string", "enum": ["blocking", "high", "low", "cosmetic"]},
                    "reason": {"type": "string"},
                },
                "required": ["key", "impact", "reason"],
            },
        },
        "assumptions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["key", "value", "reason"],
            },
        },
        "confidence": {"type": "number"},
        "next_action": {"type": "string", "enum": ["ask", "build", "update"]},
        "question": {"type": "string"},
        "question_key": {"type": "string"},
        "build_brief": {"type": "string"},
        "external_effect": {"type": "boolean"},
        "destructive": {"type": "boolean"},
    },
    "required": [
        "problem", "known", "unknowns", "assumptions",
        "confidence", "next_action", "question", "question_key", "build_brief",
        "external_effect", "destructive",
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
1. 分かっていないことは`unknowns`へ、必ず次の4段階のimpactを付けて
   列挙する。この分類が、質問するかどうかを決める:
   - "blocking": これが分からないと、そもそも何を作るか決まらない。
   - "high": 答えによって道具の構造が大きく変わる
     (例: 家族と共有するか=保存場所と権限が変わる)。
   - "low": 構造は変わらない。Forge側の既定で進めてよい。
   - "cosmetic": 色・配置・ボタンの位置など見た目のこと。
   **色・レイアウト・ボタンの位置・画面数・入力検証の細かさは、
   必ず"cosmetic"か"low"にすること**(Forgeが決める領分であり、
   ユーザーに聞いてはならない)。
2. `unknowns`の各項目には、なぜその重要度なのかを`reason`へ短く書く。
3. 聞かずに決めたことは`assumptions`へ、key・value・reasonを書く。
4. 質問は一度に1つだけ。質問する場合は`question_key`に、その質問が
   対応する`unknowns`のkeyを必ず入れること。
5. 一度聞いたことを、言い換えて再び聞かないこと(下の[既に質問済み]
   に載っているkeyは`question_key`にしてはならない)。
6. next_action="build"の場合、build_briefには、この会話全体を踏まえた
   完全で自己完結した日本語の説明文を書くこと(このbuild_brief単体が、
   会話の文脈を一切知らない別のシステムへそのまま渡され、そこから
   アプリが生成される。会話で分かった情報を漏らさず含めること)。
7. next_action="ask"の場合、questionには自然な会話文で1問だけ書く。
   build_briefは空文字列にする。
8. next_action="build"または"update"の場合、questionは空文字列にする。
9. 既に使用中のツールがある場合のみ、"update"を選べる(無い場合は
   選ばないこと)。ユーザーの発話が、今使っているツールへの変更・
   追加要求(例:「よく買うものを上に置きたい」「予算も管理したい」)
   であれば next_action="update" とし、build_briefにはその変更要求を
   完全で自己完結した日本語で書くこと(会話の文脈を知らない別の
   システムが、今のツールのJSONとこの文だけを見て更新する)。
   ユーザーの発話が今のツールと無関係な、全く新しい困りごとであれば、
   "update"ではなく通常どおり"ask"/"build"で判断すること。
10. ユーザーの依頼が、Forgeの外へ影響する操作(誰かへ送る・共有する・
    公開する・通知する)を含むなら`external_effect`をtrueにする。
    削除・金銭・権限変更など元に戻せない操作を含むなら`destructive`を
    trueにする。単にローカルで記録・管理するだけの道具を作る場合は
    どちらもfalseにすること。
"""

# 「まず小さく作る」ことを伝える戦略へ切り替える閾値に達した際、
# プロンプトへ足す指示(指示書1章: ターン上限は強制BUILDではなく、
# 質問戦略を変更する閾値である)。
_NARROWED_QUESTION_GUIDANCE = """
[質問の仕方] 会話が長くなっています。もしまだ聞く必要があるなら、
自由回答ではなく「AとBのどちらですか」のような短い二択にしてください。
それ以外のことは聞かず、assumptionsへ記録して先へ進めてください。
"""


def _build_prompt(
    session: ConversationSession, *, has_existing_tool: bool, narrowed: bool
) -> str:
    lines = [_SYSTEM_PROMPT]
    if narrowed:
        lines.append(_NARROWED_QUESTION_GUIDANCE)
    if has_existing_tool:
        lines.append("\n[状態] ユーザーは現在、既に生成済みのツールを使っています。")
    else:
        lines.append("\n[状態] まだツールは生成されていません(これは新しい会話です)。")
    if session.asked_question_keys:
        # 繰り返し質問の抑止(指示書5章)を、Policy側の決定的な
        # フィルタ(`select_question()`)だけでなく、プロンプトでも
        # 明示する。Policyだけでも同じUnknownを再び「聞く」ことは
        # 防げるが、LLMに毎回同じ質問文を生成させるのは無駄であり、
        # 会話履歴を見て別の観点へ移ってもらう方が結果が良い。
        lines.append("\n[既に質問済み] " + ", ".join(session.asked_question_keys))
    lines.append("\n[会話]")
    for turn in session.turns:
        speaker = "ユーザー" if turn.role == "user" else "Forge"
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines)


def _parse_impact(raw: object) -> UnknownImpact:
    """未知のimpact。不正値は最も安全な`COSMETIC`ではなく`LOW`へ倒す。

    `COSMETIC`へ倒すと「Design Systemが決める」扱いになり、本当は
    重要かもしれない未知が完全に無視される。`LOW`ならSafe Assumption
    として理由付きで記録が残るため、後から追える(指示書6章)。
    """
    if isinstance(raw, str):
        try:
            return UnknownImpact(raw)
        except ValueError:
            return UnknownImpact.LOW
    return UnknownImpact.LOW


def _parse_unknowns(raw: object) -> tuple[UnknownItem, ...]:
    if not isinstance(raw, list):
        return ()
    items: list[UnknownItem] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(UnknownItem(
            key=key,
            impact=_parse_impact(entry.get("impact")),
            reason=str(entry.get("reason") or "").strip() or "(理由の記載なし)",
        ))
    return tuple(items)


def _parse_assumptions(raw: object) -> tuple[SafeAssumption, ...]:
    if not isinstance(raw, list):
        return ()
    items: list[SafeAssumption] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(SafeAssumption(
            key=key,
            value=str(entry.get("value") or "").strip() or "forge_default",
            reason=str(entry.get("reason") or "").strip() or "(理由の記載なし)",
        ))
    return tuple(items)


def _fallback_brief(session: ConversationSession) -> str:
    """LLMが`build_brief`を空で返した場合の安全網。会話全体を素朴に
    連結する(クラッシュより、質の落ちるbriefの方がまだ良い)。"""
    return "。".join(t.text for t in session.turns if t.role == "user")


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

        user_turn_count = sum(1 for t in session.turns if t.role == "user")
        latest_user_text = session.turns[-1].text

        # 質問戦略の切り替え(指示書1章)。**これはBUILD条件ではない**。
        narrowed = DecisionContext(user_turn_count=user_turn_count).at_or_over_turn_threshold
        prompt = _build_prompt(session, has_existing_tool=has_existing_tool, narrowed=narrowed)
        raw = self._provider.complete_structured(prompt, _RESPONSE_SCHEMA)

        need_model = NeedModel(
            problem=str(raw.get("problem", "")),
            known=tuple(raw.get("known", []) or []),
            unknowns=_parse_unknowns(raw.get("unknowns")),
            assumptions=_parse_assumptions(raw.get("assumptions")),
            confidence=float(raw.get("confidence", 0.0) or 0.0),
        )

        # 外部作用・不可逆操作は、LLMの申告とForge側の決定的な検出の
        # **OR**を取る(指示書3章: System Facts優先。LLMが「無い」と
        # 言っても、こちらが検出したなら安全側=CONFIRMへ倒す)。
        detected_external, detected_destructive = detect_risk_signals(latest_user_text)
        context = DecisionContext(
            has_existing_tool=has_existing_tool,
            user_turn_count=user_turn_count,
            asked_question_keys=session.asked_question_keys,
            llm_proposed_action=raw.get("next_action") if isinstance(raw.get("next_action"), str) else None,
            external_effect=bool(raw.get("external_effect")) or detected_external,
            destructive=bool(raw.get("destructive")) or detected_destructive,
            ask_counts=dict(session.ask_counts),
            # 「分からない」「任せる」と委ねられたら、同じことを
            # 聞き続けない(§12)。
            #
            # **会話全体のユーザー発話を見る**(最新の1件だけではない)。
            # Scripted Conversation Setで見つけた実バグ: 最新発話だけを
            # 見ていたため、「任せる」→「うん」と続くと**委任が忘れられ**、
            # 段が上がらず同じ既定提示を繰り返していた。一度「決めて」と
            # 言われた事実は、その後の相槌で取り消されない。
            user_delegated=any(
                user_delegated_decision(t.text) for t in session.turns if t.role == "user"
            ),
        )

        # ---- ここから先が意思決定。LLMのnext_action/confidenceは、
        # ---- 単独ではBUILDの理由にならない(指示書2章・3章)。
        decision = evaluate_readiness(need_model, context)
        action = resolve_action(decision.readiness, context)

        # 聞かずに済ませた未知を、理由付きのSafe Assumptionとして
        # NeedModelへ足す(指示書6章: 判断根拠を追えるようにする)。
        if action in (ConversationAction.BUILD, ConversationAction.UPDATE):
            extra = assumptions_for_unasked(need_model, context)
            if decision.shrink_assumption is not None:
                # SHRINK_SOLUTION: そのUnknownを必要としない最小の解へ
                # 落として作ったことを、理由付きで記録する(§14)。
                extra = extra + (decision.shrink_assumption,)
            if extra:
                existing = {a.key for a in need_model.assumptions}
                need_model = NeedModel(
                    problem=need_model.problem, known=need_model.known,
                    unknowns=need_model.unknowns,
                    assumptions=need_model.assumptions + tuple(
                        a for a in extra if a.key not in existing
                    ),
                    confidence=need_model.confidence,
                )

        if action == ConversationAction.CONFIRM:
            return ConversationStepResult(
                action=action, need_model=need_model, readiness=decision.readiness,
                confirm_reason=decision.confirm_reason,
                question=str(raw.get("question") or "").strip() or None,
                build_brief=str(raw.get("build_brief") or "").strip() or _fallback_brief(session),
            )

        if action == ConversationAction.ASK:
            question = str(raw.get("question") or "").strip()
            target = decision.question
            if decision.strategy is QuestionStrategy.OFFER_DEFAULT and target is not None:
                # §15: 聞き直しても情報が増えないなら、質問をやめて
                # 「こう決めておきますね」と既定を提示する。ユーザーが
                # 「任せる」と言った場合はここへ直行する。
                question = (
                    f"{target.key}について決めかねているようなので、"
                    "こちらで一般的な形にしておきますね。それで進めて大丈夫ですか？"
                )
            elif decision.strategy is QuestionStrategy.REPHRASE and target is not None and not question:
                question = f"{target.key}について、どちらが近いですか？"
            if not question:
                # **以前はここでBUILDへ倒していた**(空の質問文を出すより
                # 作ってしまえ、という判断)。しかしそれは「分からなくても
                # 作る」ことに他ならず、指示書1章・16章に反する。
                # 未知の内容そのものを使った質問文を組み立てて、必ず聞く。
                question = (
                    f"{target.key}について、もう少しだけ教えてもらえますか？"
                    if target is not None
                    else "もう少しだけ詳しく教えてもらえますか？"
                )
            return ConversationStepResult(
                action=action, need_model=need_model, readiness=decision.readiness,
                question=question,
                question_key=(target.key if target is not None else None),
                strategy=decision.strategy,
            )

        brief = str(raw.get("build_brief") or "").strip() or _fallback_brief(session)
        return ConversationStepResult(
            action=action, need_model=need_model, readiness=decision.readiness, build_brief=brief,
            # 縮退して作った場合、その事実(SHRINK_SOLUTION)を必ず載せる。
            # Scripted Conversation Setを流して見つけた実バグ: ここで
            # strategyを渡し忘れていたため既定のASKになり、
            # `solution_shrink_count`が常に0になっていた(縮退が
            # 実際には起きているのに、測定上まったく見えなかった)。
            strategy=decision.strategy,
        )
