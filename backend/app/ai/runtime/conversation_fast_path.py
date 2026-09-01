"""**簡単な要求に、毎回 LLM を待たせない**（実機 2026-08-31 の速度 FAIL）。

---

## 何が起きていたか

実機（Ollama + `qwen2.5:1.5b-instruct`）で `/api/v1/ai/converse` を叩いた実測:

```text
HTTP 200 / simulated=false / **73.54 秒**
```

Flutter 側の `receiveTimeout` は 10 秒なので、Chrome では先に
「サーバーに接続できませんでした」になる。**画面まで到達しない。**

同じモデルで単純な structured 生成は warm 状態で約 4.02 秒である。
つまり 73 秒の主因はモデルの遅さではなく、**Conversation Engine の
大きな prompt と schema を小型 CPU モデルへ丸投げしている構造**である。

そして中身も誤っていた。

> 「事務所の鍵を誰が持ち出していて、いつ返す予定か記録したい」

に対して「誰が持っているか」「返却予定はいつか」を**利用開始前に
確認すべき未知**と判定して聞き返した。これらは未知ではない
——**作る管理ツールの入力項目**である。値は利用者が後から入れる。

## この層がすること

要求を読んで、**いま持っている能力の組み合わせだけで成立する**と
決定的に言い切れるなら、大きな LLM 判定を通さずに BUILD へ進める。

判断には**既存の資産だけ**を使う。新しい分類器を作らない。

| 使うもの | 何のために |
|---|---|
| `plan_capabilities()`（forge_ai） | 足りない能力があるかどうか |
| `detect_risk_signals()`（既存 policy） | 外部作用・不可逆操作 |
| 記録の意図（この層） | 「作って」ではなく「記録・管理したい」か |

## 速い道へ入れない条件（**迷ったら LLM へ渡す**）

* 足りない能力がある → 自己拡張の判断が要る
* 外部作用・不可逆操作の気配 → 安全側。確認が要る
* 記録・管理の意図が読み取れない（「困ってる」「いい感じのやつ作って」）
  → **本当に曖昧**なので聞くべきである
* 2 ターン目以降 / 既に質問している → 文脈を読む必要がある

**fail-closed である。** 分からないものを速い道へ倒さない。
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.ai.runtime.conversation_policy import detect_risk_signals
from app.ai.runtime.conversation_types import (
    ConversationAction,
    ConversationReadiness,
    ConversationSession,
    ConversationStepResult,
    NeedModel,
    SafeAssumption,
)

__all__ = [
    "FastPathOutcome",
    "deterministic_step",
    "recording_intent_of",
]

#: **記録・管理したい**という意図。動詞の側で受ける。
#:
#: 分野ごとの名詞（鍵・食事・在庫…）を並べる方向では埋まらない
#: （分野の数だけ増える。TD96 と同じ轍）。「何を」ではなく
#: **「どうしたいか」**で見る。
_RECORDING_INTENT = re.compile(
    r"(記録|記入|入力|登録|管理|保存|控え|メモ|残し|残す|付け|つけ|"
    r"一覧|リスト|台帳|見返|振り返|把握|確認)"
)

#: 「作って」「なんとかして」だけの、中身の無い依頼。
_NO_SUBJECT = re.compile(r"^[\s、。]*(なんとか|どうにか|いい感じ|よしなに)")

#: **何を**管理するのかが名指しされていない。
#:
#: 「家族で何か管理したい」——記録の意図はあるが、対象が無い。
#: これは本当に聞くべき未知である（Golden Case 02）。
_UNNAMED_SUBJECT = re.compile(r"(何か|なにか|いろいろ|色々|諸々|もろもろ)")

#: **既にある物への変更**を頼む言い方。
#:
#: 「期限も追加して」——何に足すのかは、既存の道具があって初めて決まる。
#: 道具がまだ無いのにこれを新規作成として通すと、**何の期限なのか
#: 分からないまま**作ってしまう（Golden Case 06）。
#:
#: この層が受け持つのは**新しく作る**要求だけである。変更の解釈は
#: 既存の UPDATE/ASK 補正へ渡す。
_MODIFICATION_FRAGMENT = re.compile(
    r"(も追加|も入れ|も付け|も欲し|に変え|へ変え|を消し|を削っ|やめたい|"
    r"変更して|直して)"
)

#: **複数人で使う前提。**
#:
#: 「家族で予定を管理したい」「チームで共有したい」。
#: 誰が追加できるかで**保存場所と権限の設計が変わる**ので、
#: 聞かずに済ませてはならない（Golden Case 02）。
#:
#: 「事務所の鍵を**誰が**持ち出しているか記録したい」の「誰が」とは
#: 別物である。あちらは**記録する項目**であって、道具を誰と使うかの
#: 話ではない。だから「誰が」単体では倒さない。
_SHARED_USAGE = re.compile(
    r"(家族で|みんなで|皆で|全員で|チームで|社内で|部署で|共有|"
    r"一緒に使|複数人|他の人も|メンバーで)"
)


@dataclass(frozen=True, slots=True)
class FastPathOutcome:
    """速い道を通ったか、通らなかったならなぜか。"""

    result: ConversationStepResult | None
    reason: str
    """**通らなかった理由も残す。** 黙って落ちない。"""

    plan: object | None = None

    @property
    def taken(self) -> bool:
        return self.result is not None


def recording_intent_of(text: str) -> str | None:
    """「記録・管理したい」意図を表す語。無ければ `None`。"""
    if _NO_SUBJECT.match(text or ""):
        return None
    match = _RECORDING_INTENT.search(text or "")
    return match.group(0) if match is not None else None


def deterministic_step(
    session: ConversationSession, *, has_existing_tool: bool = False,
) -> FastPathOutcome:
    """LLM を呼ばずに決められるなら決める。決められないなら `None`。"""
    user_turns = [t for t in session.turns if t.role == "user"]
    if not user_turns:
        return FastPathOutcome(None, "利用者の発話がまだ無い")
    if has_existing_tool:
        # 既存ツールへの変更要求は、何をどう変えるかの解釈が要る。
        return FastPathOutcome(None, "既存ツールへの変更要求は解釈が要る")
    if len(user_turns) > 1 or session.asked_question_keys:
        # すでに会話が始まっている。文脈を読む必要がある。
        return FastPathOutcome(None, "2ターン目以降は文脈を読む必要がある")

    text = user_turns[-1].text or ""
    if len(text.strip()) < 6:
        return FastPathOutcome(None, "短すぎて要求を特定できない")

    external, destructive = detect_risk_signals(text)
    if external or destructive:
        # 安全側へ倒す。確認は既存の CONFIRM Policy に任せる。
        return FastPathOutcome(None, "外部作用または不可逆操作の気配がある")

    if _MODIFICATION_FRAGMENT.search(text):
        # 既にある物への変更要求。新規作成として通さない。
        return FastPathOutcome(None, "既にある物への変更を頼む言い方である")

    if _UNNAMED_SUBJECT.search(text):
        # **何を**管理するのかが決まっていない。聞くべき未知である。
        return FastPathOutcome(None, "何を扱うのかが名指しされていない")

    if _SHARED_USAGE.search(text):
        # 誰が追加できるかで保存場所と権限が変わる。聞くべき未知である。
        return FastPathOutcome(None, "複数人で使う前提は、権限と保存場所の設計が変わる")

    # **既存の decomposition を再利用する。** ここで新しい分類器を作らない。
    from forge_ai.core.semantics.capability_plan import (  # noqa: PLC0415
        plan_capabilities,
    )

    plan = plan_capabilities(text)
    if plan.missing:
        # 足りない能力がある。自己拡張するかどうかの判断が要る。
        return FastPathOutcome(
            None, f"足りない能力がある: {', '.join(plan.missing)}", plan=plan,
        )

    # 通してよい根拠は2つある。**どちらか一方で足りる。**
    #
    # 1. decomposition が「IR を組めるだけの材料が揃っている」と言っている
    #    （`is_actionable`）。これが一番強い根拠である
    # 2. 記録・管理したいという意図が読み取れる。項目まで分解できなくても、
    #    **作る物の形は決まっている**（項目は生成時に決める）
    #
    # 2 が要るのは、分野の語彙が表に無いと項目が立たないからである。
    # 「事務所の鍵を誰が持ち出しているか記録したい」がこれに当たる
    # ——鍵も持ち出しも表に無いが、**やりたいことは明確**である。
    intent = recording_intent_of(text)
    if not plan.is_actionable and intent is None:
        return FastPathOutcome(
            None, "記録・管理の意図を読み取れない（本当に曖昧）", plan=plan,
        )
    ground = (
        f"要求から作る物の形が決まっている（{', '.join(plan.requested)}）"
        if plan.is_actionable
        else f"記録・管理の要求である（{intent}）"
    )

    need_model = NeedModel(
        problem=text,
        known=(text,),
        unknowns=(),
        assumptions=(
            SafeAssumption(
                key="fast_path",
                value="いま持っている能力の組み合わせで作る",
                reason=(
                    f"{ground}。足りない能力も、外部への作用も"
                    "見つからなかったため、確認せずに作った"
                ),
            ),
            SafeAssumption(
                key="tool_fields_are_not_unknowns",
                value="記録する項目は、作るツールの入力欄として用意する",
                reason=(
                    "「誰が」「いつ」のような項目は、利用開始前に確定させる"
                    "未知ではなく、利用者が後から入れる値である"
                ),
            ),
        ),
        confidence=1.0,
    )
    return FastPathOutcome(
        ConversationStepResult(
            action=ConversationAction.BUILD,
            need_model=need_model,
            build_brief=text,
            readiness=ConversationReadiness.BUILD_READY,
        ),
        f"既存の能力だけで作れる: {ground}",
        plan=plan,
    )
