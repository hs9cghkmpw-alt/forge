"""Scripted Conversation Set(FORGE-QUALITY-AI-INDEPENDENCE-003 §26、
2026-08-12)。

実ユーザーデータがまだ無くても会話品質の測定を止めないための、
**手で設計した50セッション**のデータセット。

指示書§26が要求する会話の種類を全て含む:

    明確な要求 / 曖昧 / 分からない / 任せる / どっちでもいい /
    無関係回答 / 途中変更 / UPDATE / 共有 / 削除 / 高リスク

**LLMをここでは呼ばない理由**: 測りたいのは「Forge側のPolicyが
正しく振る舞うか」であって、LLMの機嫌ではない。各セッションは
「LLMがこう報告したとき」を`_SimulatedLLM`で決定的に再現し、
その上でPolicyの出力(ASK/BUILD/UPDATE/CONFIRM、質問回数、縮退、
仮定)を測る。LLMが誤った提案をしてもPolicyが正すこと自体が
指示書3章の要求であるため、この分離は本質的である。

**Provider比較への再利用**(指示書§26末尾): `user_messages`と
`expect`(期待される最終Action等)はProvider非依存なので、
`_SimulatedLLM`を実Providerへ差し替えれば、そのままGemini vs Local
の会話品質比較に使える。差し替え口は`run_session(llm=...)`である。
**ただし実Providerでの実行は本セッションでは行っていない**
(Gemini無料枠上限・Localモデル取得不可、TD51)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.ai.runtime.conversation_engine import ConversationEngine
from app.ai.runtime.conversation_policy import detect_risk_signals
from app.ai.runtime.conversation_types import (
    ConversationAction,
    ConversationSession,
    ConversationTurn,
    QuestionStrategy,
)

__all__ = [
    "SCRIPTED_SESSIONS",
    "ConversationDatasetMetrics",
    "ScriptedSession",
    "SessionOutcome",
    "run_all_sessions",
    "run_session",
]


class _LLMLike(Protocol):
    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ScriptedSession:
    """1セッション分の台本と期待値。

    `unknowns`はLLMが報告する未知(key, impact)。`resolved_after_turn`
    に達すると報告しなくなる(=ユーザーの回答で解消した状況の再現)。
    `None`なら**最後まで解消しない**——「分からない」「任せる」系の
    セッションがこれにあたる。
    """

    name: str
    category: str
    user_messages: tuple[str, ...]
    unknowns: tuple[tuple[str, str], ...] = ()
    resolved_after_turn: int | None = 1
    has_existing_tool: bool = False
    expect_action: ConversationAction | None = None
    expect_max_questions: int | None = None
    expect_shrink: bool = False


@dataclass
class SessionOutcome:
    """1セッションを最後まで進めた結果(指示書§26の測定項目)。"""

    name: str
    category: str
    actions: list[ConversationAction] = field(default_factory=list)
    asked: list[tuple[str, str]] = field(default_factory=list)
    strategies: list[str] = field(default_factory=list)
    blocking_unknowns_at_build: int = 0
    safe_assumptions: int = 0
    build_failed: bool = False

    @property
    def questions_before_build(self) -> int:
        return sum(1 for a in self.actions if a is ConversationAction.ASK)

    @property
    def repeated_question_count(self) -> int:
        """同じUnknownを**同じ段で**繰り返した回数(TD50で定義を修正)。"""
        return len(self.asked) - len(set(self.asked))

    @property
    def confirm_count(self) -> int:
        return sum(1 for a in self.actions if a is ConversationAction.CONFIRM)

    @property
    def solution_shrink_count(self) -> int:
        return sum(1 for s in self.strategies if s == QuestionStrategy.SHRINK_SOLUTION.value)

    @property
    def final_action(self) -> ConversationAction:
        return self.actions[-1]


class _SimulatedLLM:
    """「まともなLLM」の決定的な再現。

    Policyを測るための土台であり、LLMの賢さを測るものではない。
    わざと素直に振る舞わせる(未知をそのまま報告し、素直にaskを提案し、
    外部作用を正しく申告する)ことで、**Policyが何を上書きしたのかが
    そのまま観測できる**。
    """

    def __init__(self, session: ScriptedSession) -> None:
        self._session = session
        self._turn = 0

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        self._turn += 1
        spec = self._session
        resolved = (
            spec.resolved_after_turn is not None and self._turn > spec.resolved_after_turn
        )
        unknowns = (
            []
            if resolved
            else [
                {"key": key, "impact": impact, "reason": f"{key}によって作るものが変わるため"}
                for key, impact in spec.unknowns
            ]
        )
        latest = prompt.rsplit("ユーザー: ", 1)[-1].strip() if "ユーザー: " in prompt else ""
        external, destructive = detect_risk_signals(latest)

        if unknowns:
            action = "ask"
        elif spec.has_existing_tool:
            action = "update"
        else:
            action = "build"

        return {
            "problem": spec.name,
            "known": [],
            "unknowns": unknowns,
            "assumptions": [],
            "confidence": 0.4 if unknowns else 0.9,
            "next_action": action,
            "question": f"{unknowns[0]['key']}について教えてください" if unknowns else "",
            "question_key": unknowns[0]["key"] if unknowns else "",
            "build_brief": "" if unknowns else f"{spec.name}のための道具を作る",
            "external_effect": external,
            "destructive": destructive,
        }


def run_session(spec: ScriptedSession, *, llm: _LLMLike | None = None) -> SessionOutcome:
    """1セッションを最後まで進める。

    `llm`を差し替えれば、同じ台本で実Provider(Gemini/Local)を評価できる
    (指示書§26末尾のDataset再利用)。
    """
    engine = ConversationEngine(llm or _SimulatedLLM(spec))
    session = ConversationSession(session_id=spec.name)
    outcome = SessionOutcome(name=spec.name, category=spec.category)

    for message in spec.user_messages:
        session = session.with_turn(ConversationTurn(role="user", text=message))
        try:
            result = engine.step(session, has_existing_tool=spec.has_existing_tool)
        except Exception:  # noqa: BLE001 — build_failureも測定対象
            outcome.build_failed = True
            break

        outcome.actions.append(result.action)
        outcome.strategies.append(result.strategy.value)

        if result.action is ConversationAction.ASK:
            if result.question_key:
                outcome.asked.append((result.question_key, result.strategy.value))
                session = session.with_asked_key(result.question_key)
            session = session.with_turn(
                ConversationTurn(role="forge", text=result.question or "")
            )
            continue

        if result.action is ConversationAction.CONFIRM:
            session = session.with_turn(
                ConversationTurn(role="forge", text=result.question or "確認")
            )
            continue

        outcome.blocking_unknowns_at_build = len(result.need_model.blocking_unknowns())
        outcome.safe_assumptions = len(result.need_model.assumptions)
        break

    return outcome


@dataclass
class ConversationDatasetMetrics:
    """データセット全体の集計(指示書§26の測定項目)。"""

    sessions: int = 0
    total_questions: int = 0
    repeated_questions: int = 0
    confirms: int = 0
    shrinks: int = 0
    builds: int = 0
    updates: int = 0
    unresolved: int = 0
    build_failures: int = 0
    blocking_at_build: int = 0
    safe_assumptions: int = 0

    @property
    def avg_questions_per_session(self) -> float:
        return self.total_questions / self.sessions if self.sessions else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessions": self.sessions,
            "avg_questions_before_build": round(self.avg_questions_per_session, 2),
            "repeated_question_count": self.repeated_questions,
            "blocking_unknowns_at_build": self.blocking_at_build,
            "safe_assumptions": self.safe_assumptions,
            "solution_shrink_count": self.shrinks,
            "confirm_count": self.confirms,
            "build_count": self.builds,
            "update_count": self.updates,
            "unresolved_sessions": self.unresolved,
            "build_failure_count": self.build_failures,
        }


def run_all_sessions(
    sessions: tuple[ScriptedSession, ...] | None = None,
) -> tuple[list[SessionOutcome], ConversationDatasetMetrics]:
    outcomes = [run_session(s) for s in (sessions or SCRIPTED_SESSIONS)]
    metrics = ConversationDatasetMetrics(sessions=len(outcomes))
    for o in outcomes:
        metrics.total_questions += o.questions_before_build
        metrics.repeated_questions += o.repeated_question_count
        metrics.confirms += o.confirm_count
        metrics.shrinks += o.solution_shrink_count
        metrics.blocking_at_build += o.blocking_unknowns_at_build
        metrics.safe_assumptions += o.safe_assumptions
        if o.build_failed:
            metrics.build_failures += 1
        elif o.final_action is ConversationAction.BUILD:
            metrics.builds += 1
        elif o.final_action is ConversationAction.UPDATE:
            metrics.updates += 1
        else:
            metrics.unresolved += 1
    return outcomes, metrics


def _clear(name: str, message: str) -> ScriptedSession:
    """明確な要求: 未知なし、1ターンでBUILD。"""
    return ScriptedSession(
        name=name, category="clear", user_messages=(message,),
        unknowns=(), resolved_after_turn=0,
        expect_action=ConversationAction.BUILD, expect_max_questions=0,
    )


def _one_question(name: str, first: str, answer: str, key: str) -> ScriptedSession:
    """曖昧だが1問で解消する: ASK 1回 → BUILD。"""
    return ScriptedSession(
        name=name, category="ambiguous", user_messages=(first, answer),
        unknowns=((key, "high"),), resolved_after_turn=1,
        expect_action=ConversationAction.BUILD, expect_max_questions=1,
    )


def _stuck(name: str, category: str, messages: tuple[str, ...], key: str) -> ScriptedSession:
    """解消しない未知: 無限ASKせず縮退してBUILDへ。"""
    return ScriptedSession(
        name=name, category=category, user_messages=messages,
        unknowns=((key, "blocking"),), resolved_after_turn=None,
        expect_action=ConversationAction.BUILD, expect_shrink=True,
    )


def _risky(name: str, messages: tuple[str, ...], *, has_tool: bool = False) -> ScriptedSession:
    """高リスク: CONFIRMで止まる。"""
    return ScriptedSession(
        name=name, category="high_risk", user_messages=messages,
        unknowns=(), resolved_after_turn=0, has_existing_tool=has_tool,
        expect_action=ConversationAction.CONFIRM,
    )


def _update(name: str, message: str) -> ScriptedSession:
    return ScriptedSession(
        name=name, category="update", user_messages=(message,),
        unknowns=(), resolved_after_turn=0, has_existing_tool=True,
        expect_action=ConversationAction.UPDATE,
    )


# --- 50セッション ------------------------------------------------------
# 指示書§26が列挙する種類を全て含む。件数は実際に数えて50。
SCRIPTED_SESSIONS: tuple[ScriptedSession, ...] = (
    # 明確な要求(10)
    _clear("shopping_clear", "買い物で何買うか忘れるからメモしたい"),
    _clear("todo_clear", "仕事のTodoを管理したい"),
    _clear("reading_clear", "読んだ本を記録したい"),
    _clear("fishing_clear", "釣った魚のサイズと場所を記録したい"),
    _clear("budget_clear", "家計簿をつけたい"),
    _clear("habit_clear", "毎日の習慣を記録したい"),
    _clear("inventory_clear", "在庫を管理したい"),
    _clear("diary_clear", "日記を書きたい"),
    _clear("meeting_clear", "会議の議事録を残したい"),
    _clear("bp_clear", "毎日の血圧を記録したい"),
    # 曖昧 → 1問で解消(10)
    _one_question("shopping_shared", "買い物で忘れる", "自分だけで使う", "shared_usage"),
    _one_question("schedule_shared", "予定を管理したい", "家族と共有したい", "shared_usage"),
    _one_question("study_target", "勉強を記録したい", "資格の勉強", "what_to_track"),
    _one_question("expense_scope", "お金の管理をしたい", "毎日の出費", "what_to_track"),
    _one_question("health_scope", "健康管理をしたい", "体重を測る", "what_to_track"),
    _one_question("kids_scope", "子供のことを記録したい", "身長と体重", "what_to_track"),
    _one_question("travel_scope", "旅行の準備をしたい", "持ち物リスト", "what_to_track"),
    _one_question("work_scope", "仕事を整理したい", "やることリスト", "what_to_track"),
    _one_question("pet_scope", "ペットのことを記録したい", "ごはんの回数", "what_to_track"),
    _one_question("car_scope", "車のことを管理したい", "給油の記録", "what_to_track"),
    # 「分からない」(5)
    _stuck("dontknow_1", "dont_know",
           ("何か便利なもの作って", "分からない", "分からない", "分からない"), "what_to_track"),
    _stuck("dontknow_2", "dont_know",
           ("記録をつけたい", "わからない", "わかんない", "うーん"), "what_to_track"),
    _stuck("dontknow_3", "dont_know",
           ("何か管理したい", "特にない", "とくにない", "うーん"), "what_to_track"),
    _stuck("dontknow_4", "dont_know",
           ("便利にしたい", "わからないな", "うーん", "難しい"), "what_to_track"),
    _stuck("dontknow_5", "dont_know",
           ("整理したい", "分からない", "うーん", "ええと"), "what_to_track"),
    # 「任せる」(5)
    _stuck("delegate_1", "delegated",
           ("何か作って", "任せる", "任せる", "任せる"), "what_to_track"),
    _stuck("delegate_2", "delegated",
           ("記録したい", "おまかせ", "お任せします", "はい"), "what_to_track"),
    _stuck("delegate_3", "delegated",
           ("管理したい", "決めて", "きめて", "はい"), "what_to_track"),
    _stuck("delegate_4", "delegated",
           ("道具が欲しい", "任せるよ", "うん", "はい"), "what_to_track"),
    _stuck("delegate_5", "delegated",
           ("何か欲しい", "そっちで決めて", "はい", "うん"), "what_to_track"),
    # 「どっちでもいい」(5)
    _stuck("whatever_1", "whatever",
           ("リストを作りたい", "どっちでもいい", "どちらでも", "はい"), "shared_usage"),
    _stuck("whatever_2", "whatever",
           ("記録をつけたい", "なんでもいい", "何でもいい", "うん"), "shared_usage"),
    _stuck("whatever_3", "whatever",
           ("メモしたい", "どっちでもいいよ", "はい", "うん"), "shared_usage"),
    _stuck("whatever_4", "whatever",
           ("管理したい", "どちらでもいい", "うん", "はい"), "shared_usage"),
    _stuck("whatever_5", "whatever",
           ("作りたい", "なんでもいいです", "はい", "はい"), "shared_usage"),
    # 無関係回答(5)
    _stuck("irrelevant_1", "irrelevant",
           ("買い物リストが欲しい", "今日は天気がいいね", "そうだね", "うん"), "shared_usage"),
    _stuck("irrelevant_2", "irrelevant",
           ("記録したい", "お腹すいた", "ところで", "うん"), "what_to_track"),
    _stuck("irrelevant_3", "irrelevant",
           ("管理したい", "昨日の映画が面白かった", "そう", "うん"), "what_to_track"),
    _stuck("irrelevant_4", "irrelevant",
           ("メモが欲しい", "ねえ", "あのさ", "うん"), "what_to_track"),
    _stuck("irrelevant_5", "irrelevant",
           ("作って", "こんにちは", "元気?", "うん"), "what_to_track"),
    # 途中変更(3)
    ScriptedSession(
        name="changed_mind_1", category="changed_mind",
        user_messages=("買い物リストが欲しい", "やっぱり family で使いたい", "うん"),
        unknowns=(("shared_usage", "high"),), resolved_after_turn=2,
        expect_action=ConversationAction.BUILD,
    ),
    ScriptedSession(
        name="changed_mind_2", category="changed_mind",
        user_messages=("Todoを作りたい", "やっぱり読書記録にしたい", "はい"),
        unknowns=(("what_to_track", "blocking"),), resolved_after_turn=2,
        expect_action=ConversationAction.BUILD,
    ),
    ScriptedSession(
        name="changed_mind_3", category="changed_mind",
        user_messages=("記録したい", "いや、やっぱりリストがいい", "うん"),
        unknowns=(("what_to_track", "blocking"),), resolved_after_turn=2,
        expect_action=ConversationAction.BUILD,
    ),
    # UPDATE(4)
    _update("update_1", "期限も追加して"),
    _update("update_2", "よく買うものを上に置きたい"),
    _update("update_3", "カテゴリ分けもしたい"),
    _update("update_4", "金額も記録できるようにして"),
    # 共有(1) — 外部作用
    _risky("share_1", ("作ったリストを家族にも共有したい",)),
    # 削除(1) — 不可逆
    _risky("delete_1", ("古い記録を全部削除したい",), has_tool=True),
    # 高リスク(1)
    _risky("risky_1", ("このリストをみんなに公開したい",)),
)


def session_count_by_category() -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in SCRIPTED_SESSIONS:
        counts[s.category] = counts.get(s.category, 0) + 1
    return counts
