"""**Need の中で、どの語が何の役をしているか**
（GENERATED-UI-QG-V2-R4、2026-08-26）。

---

## 直そうとしている壊れ方

実描画・目視で2つの事実が出た（`docs/reports/GENERATED-UI-QUALITY-GATE-V2-report.md`）。

```
「子どもが朝の支度をひとつずつチェックできるようにしたい」
  → child_growth → 「こどもの成長」＋ 体重測定・身長測定

「旅行の写真を日付ごとに残してメモを付けたい」
  → travel → 「旅行」＋ 充電器・着替え・歯ブラシ
```

どちらも**1つの単語がアプリ全体を決めている**。「子ども」が出た
だけで、記録するものまで体重・身長になる。「旅行」が出ただけで
持ち物リストになる。

本番経路がこう圧縮されていたからである。

```
Need → keyword → Domain → Template/Compiler → checklist
```

## この層が変えること

**語に役を与える。** 役が違えば、その語が影響してよい範囲も違う。

* `ACTOR`（子ども）は**誰が使うか**を言う。**記録対象を決めない。**
* `CONTEXT`（旅行）は**どういう場面か**を言う。**作るものを決めない。**
* `RECORDED_DATA`（写真・日付・メモ）が**記録対象を決める。**
* `DESIRED_VIEW`（推移・比較）が**見せ方を決める。**

キーワード表を使うこと自体は変えていない（形態素解析は入れない、
このリポジトリ全体の方針）。変えたのは**キーワードが持つ権限**である。
以前は1語が Domain を選び、Domain がアプリ全体を選んでいた。
これからは、1語は**1つの役を埋めるだけ**であり、構造は
役の**組み合わせ**から決まる。

## この層が保証しないこと

* 日本語の完全な理解。これは決定的な辞書であり、未知語は役が付かない
* 役が付かなかった語を**推測で埋めない**。空欄は空欄のまま残す
  （`CLAUDE.md` §3「分からないものを楽観側へ倒さない」）

役が1つも取れなければ、後段は「分からなかった」として扱う。
それは失敗であって、既定値で埋めてよい合図ではない。
"""

from __future__ import annotations

import re

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "RoleAssignment",
    "SemanticRole",
    "SemanticRoleExtraction",
    "extract_semantic_roles",
]


class SemanticRole(str, Enum):
    """Need の中で語が果たす役。"""

    ACTOR = "actor"
    """**誰が使うか / 誰のためか。** 子ども・家族・チーム。

    **記録対象を決めてはならない。** 「子ども」から体重・身長を
    導くのがまさに TD89 である。
    """

    SUBJECT = "subject"
    """その道具が扱う中心の主題。`MANAGED_OBJECT` が取れないときの受け皿。"""

    MANAGED_OBJECT = "managed_object"
    """**繰り返し増減する対象。** 買うもの・タスク・在庫。"""

    RECORDED_DATA = "recorded_data"
    """**1件ごとに残す値。** 写真・日付・メモ・金額・正解率。

    Entity の Field はここから作る。**ここだけが作る。**
    """

    ACTIVITY = "activity"
    """**繰り返す行い。** 朝の支度・練習・出題・育てる。"""

    CONTEXT = "context"
    """**場面・状況。** 旅行・学校・部署・会議。

    **作るものを決めてはならない。** 「旅行」から持ち物リストを
    導くのが TD89 のもう半分である。
    """

    DESIRED_VIEW = "desired_view"
    """**利用者が見たい形。** 推移・比較・集計・一覧・残高。"""

    EFFECT = "effect"
    """**起きてほしいこと。** 通知・リマインド。"""


@dataclass(frozen=True)
class RoleAssignment:
    """1つの語に1つの役。"""

    role: SemanticRole
    value: str
    """正規化した値（`photo` 等）。**利用者の生の語ではない。**"""

    surface: str
    """実際に Need に現れた語。**根拠として残す。**"""


#: 語 → (役, 正規化値)。**長い語を先に置く**（部分一致なので）。
#:
#: 表を持つこと自体は以前と同じである。違うのは**表の出力が役だ**という点。
#: 以前は語 → Domain であり、Domain がアプリ全体を決めていた。
_ROLE_LEXICON: tuple[tuple[str, SemanticRole, str], ...] = (
    # -- ACTOR: 誰が使うか -------------------------------------------
    ("子ども", SemanticRole.ACTOR, "child"),
    ("こども", SemanticRole.ACTOR, "child"),
    ("子供", SemanticRole.ACTOR, "child"),
    ("赤ちゃん", SemanticRole.ACTOR, "baby"),
    ("生徒", SemanticRole.ACTOR, "student"),
    ("学生", SemanticRole.ACTOR, "student"),
    ("家族", SemanticRole.ACTOR, "family"),
    ("チーム", SemanticRole.ACTOR, "team"),
    ("同僚", SemanticRole.ACTOR, "colleague"),
    ("担当者", SemanticRole.ACTOR, "assignee"),
    ("参加者", SemanticRole.ACTOR, "participant"),
    ("回答者", SemanticRole.ACTOR, "respondent"),
    ("患者", SemanticRole.ACTOR, "patient"),

    # -- CONTEXT: どういう場面か -------------------------------------
    ("旅行", SemanticRole.CONTEXT, "travel"),
    ("出張", SemanticRole.CONTEXT, "business_trip"),
    ("部署", SemanticRole.CONTEXT, "department"),
    ("会議", SemanticRole.CONTEXT, "meeting"),
    ("打ち合わせ", SemanticRole.CONTEXT, "meeting"),
    ("学校", SemanticRole.CONTEXT, "school"),
    ("職場", SemanticRole.CONTEXT, "workplace"),
    ("朝", SemanticRole.CONTEXT, "morning"),
    ("夜", SemanticRole.CONTEXT, "night"),
    ("今日", SemanticRole.CONTEXT, "today"),
    ("毎日", SemanticRole.CONTEXT, "daily"),
    ("月別", SemanticRole.CONTEXT, "monthly"),
    ("スーパー", SemanticRole.CONTEXT, "store"),

    # -- ACTIVITY: 繰り返す行い --------------------------------------
    ("支度", SemanticRole.ACTIVITY, "getting_ready"),
    ("したく", SemanticRole.ACTIVITY, "getting_ready"),
    ("準備", SemanticRole.ACTIVITY, "preparation"),
    ("練習", SemanticRole.ACTIVITY, "practice"),
    ("出題", SemanticRole.ACTIVITY, "quiz"),
    ("勉強", SemanticRole.ACTIVITY, "study"),
    ("学習", SemanticRole.ACTIVITY, "study"),
    ("運動", SemanticRole.ACTIVITY, "exercise"),
    ("育て", SemanticRole.ACTIVITY, "grow"),
    ("栽培", SemanticRole.ACTIVITY, "grow"),
    ("組み合わせ", SemanticRole.ACTIVITY, "combine"),
    ("合成", SemanticRole.ACTIVITY, "combine"),
    ("実験", SemanticRole.ACTIVITY, "experiment"),
    ("釣", SemanticRole.ACTIVITY, "fishing"),
    ("通院", SemanticRole.ACTIVITY, "clinic_visit"),
    ("買い物", SemanticRole.ACTIVITY, "shopping"),

    # -- MANAGED_OBJECT: 増減する対象 --------------------------------
    ("やること", SemanticRole.MANAGED_OBJECT, "task"),
    ("タスク", SemanticRole.MANAGED_OBJECT, "task"),
    ("作業", SemanticRole.MANAGED_OBJECT, "task"),
    ("業務", SemanticRole.MANAGED_OBJECT, "task"),
    ("持ち物", SemanticRole.MANAGED_OBJECT, "belonging"),
    ("在庫", SemanticRole.MANAGED_OBJECT, "stock"),
    ("ストック", SemanticRole.MANAGED_OBJECT, "stock"),
    ("買うもの", SemanticRole.MANAGED_OBJECT, "item"),
    ("品物", SemanticRole.MANAGED_OBJECT, "item"),
    ("英単語", SemanticRole.MANAGED_OBJECT, "word"),
    ("単語", SemanticRole.MANAGED_OBJECT, "word"),
    ("植物", SemanticRole.MANAGED_OBJECT, "plant"),
    ("曲", SemanticRole.MANAGED_OBJECT, "song"),
    ("本", SemanticRole.MANAGED_OBJECT, "book"),
    ("魚", SemanticRole.MANAGED_OBJECT, "fish"),

    # -- RECORDED_DATA: 1件ごとに残す値 ------------------------------
    ("写真", SemanticRole.RECORDED_DATA, "photo"),
    ("画像", SemanticRole.RECORDED_DATA, "photo"),
    ("メモ", SemanticRole.RECORDED_DATA, "note"),
    ("日付", SemanticRole.RECORDED_DATA, "date"),
    ("日時", SemanticRole.RECORDED_DATA, "date"),
    ("金額", SemanticRole.RECORDED_DATA, "amount"),
    ("値段", SemanticRole.RECORDED_DATA, "amount"),
    ("売上", SemanticRole.RECORDED_DATA, "amount"),
    ("収入", SemanticRole.RECORDED_DATA, "amount"),
    ("支出", SemanticRole.RECORDED_DATA, "amount"),
    ("出費", SemanticRole.RECORDED_DATA, "amount"),
    ("正解率", SemanticRole.RECORDED_DATA, "accuracy"),
    ("成功率", SemanticRole.RECORDED_DATA, "accuracy"),
    ("難易度", SemanticRole.RECORDED_DATA, "difficulty"),
    ("手応え", SemanticRole.RECORDED_DATA, "impression"),
    ("感想", SemanticRole.RECORDED_DATA, "impression"),
    ("気分", SemanticRole.RECORDED_DATA, "mood"),
    ("体重", SemanticRole.RECORDED_DATA, "weight"),
    ("身長", SemanticRole.RECORDED_DATA, "height"),
    ("場所", SemanticRole.RECORDED_DATA, "place"),
    ("緯度", SemanticRole.RECORDED_DATA, "latitude"),
    ("経度", SemanticRole.RECORDED_DATA, "longitude"),
    ("種類", SemanticRole.RECORDED_DATA, "kind"),
    ("条件", SemanticRole.RECORDED_DATA, "condition"),
    ("結果", SemanticRole.RECORDED_DATA, "result"),
    ("期限", SemanticRole.RECORDED_DATA, "deadline"),
    ("音", SemanticRole.RECORDED_DATA, "sound"),

    # -- DESIRED_VIEW: 見たい形 --------------------------------------
    ("推移", SemanticRole.DESIRED_VIEW, "trend"),
    ("グラフ", SemanticRole.DESIRED_VIEW, "chart"),
    ("集計", SemanticRole.DESIRED_VIEW, "aggregate"),
    ("比べ", SemanticRole.DESIRED_VIEW, "compare"),
    ("比較", SemanticRole.DESIRED_VIEW, "compare"),
    ("合計", SemanticRole.DESIRED_VIEW, "total"),
    ("残高", SemanticRole.DESIRED_VIEW, "balance"),
    ("一覧", SemanticRole.DESIRED_VIEW, "list"),
    ("絞り込", SemanticRole.DESIRED_VIEW, "filter"),
    ("ごと", SemanticRole.DESIRED_VIEW, "group_by"),
    ("伸び", SemanticRole.DESIRED_VIEW, "trend"),
    ("チェック", SemanticRole.DESIRED_VIEW, "check_off"),
    ("消して", SemanticRole.DESIRED_VIEW, "check_off"),
    ("ひとつずつ", SemanticRole.DESIRED_VIEW, "check_off"),

    # -- EFFECT ------------------------------------------------------
    ("通知", SemanticRole.EFFECT, "notify"),
    ("知らせ", SemanticRole.EFFECT, "notify"),
    ("リマインド", SemanticRole.EFFECT, "notify"),
)


@dataclass(frozen=True)
class SemanticRoleExtraction:
    """Need から取れた役の全部。"""

    assignments: tuple[RoleAssignment, ...] = ()

    def of(self, role: SemanticRole) -> tuple[str, ...]:
        """その役の正規化値を、**出現順のまま**返す。"""
        return tuple(dict.fromkeys(a.value for a in self.assignments if a.role is role))

    def surfaces_of(self, role: SemanticRole) -> tuple[str, ...]:
        """その役を埋めた**生の語**。根拠として使う。"""
        return tuple(dict.fromkeys(a.surface for a in self.assignments if a.role is role))

    def has(self, role: SemanticRole) -> bool:
        return bool(self.of(role))

    @property
    def is_empty(self) -> bool:
        """**何も分からなかった。** 既定値で埋めてよい合図ではない。"""
        return not self.assignments

    def structural_values(self) -> tuple[str, ...]:
        """**構造を決めてよい役**の値だけ。

        `ACTOR` と `CONTEXT` は入らない——それがこの層の要点である。
        """
        structural = (
            SemanticRole.MANAGED_OBJECT, SemanticRole.RECORDED_DATA,
            SemanticRole.ACTIVITY, SemanticRole.DESIRED_VIEW, SemanticRole.EFFECT,
            SemanticRole.SUBJECT,
        )
        return tuple(dict.fromkeys(
            a.value for a in self.assignments if a.role in structural
        ))

    def to_dict(self) -> dict[str, list[str]]:
        """Decision Trace へそのまま載せられる形。"""
        return {
            role.value: list(self.of(role))
            for role in SemanticRole
            if self.of(role)
        }


#: 「出勤した日」「釣りに行った日」「休みの日」のような、**日付を指す言い方**。
#: 「毎日」「今日」「誕生日」は形が違うので拾わない。
_DATE_PHRASE = re.compile(r"[^\s、。，．]{1,10}(?:た日|の日)")


def extract_semantic_roles(text: str) -> SemanticRoleExtraction:
    """Need から役を取り出す。**決定的**。

    同じ語が複数の役を持つ表は書いていない。1語1役にしてある——
    曖昧な語をどちらにも入れると、結局「1語がアプリを決める」状態へ
    戻るからである。
    """
    source = (text or "").strip()
    if not source:
        return SemanticRoleExtraction()

    found: list[RoleAssignment] = []
    seen: set[tuple[SemanticRole, str]] = set()
    for surface, role, value in _ROLE_LEXICON:
        if surface in source and (role, value) not in seen:
            seen.add((role, value))
            found.append(RoleAssignment(role=role, value=value, surface=surface))

    # **利用者は「日付」とは書かない。**
    #
    # ランダムな自由文を実際に投げて分かったことである。人は
    # 「出勤した日」「使った日」「釣りに行った日」と書く。表は
    # 「日付」「日時」しか持っていなかったので、そういう文では
    # 日付の欄が1つも立たず、記録の型が組めずに画面が作れなかった。
    #
    # 語を1つずつ足しても追いつかない（分野の数だけ増える）ので、
    # **「〜た日 / 〜の日」という日本語の形**で受ける。表に既に
    # 日付があるときは触らない。
    if (SemanticRole.RECORDED_DATA, "date") not in seen:
        match = _DATE_PHRASE.search(source)
        if match is not None:
            seen.add((SemanticRole.RECORDED_DATA, "date"))
            found.append(RoleAssignment(
                role=SemanticRole.RECORDED_DATA, value="date",
                surface=match.group(0),
            ))

    # **Need に現れた順に並べる。** 表の並び順を意味の順にしない。
    found.sort(key=lambda a: source.index(a.surface))
    return SemanticRoleExtraction(assignments=tuple(found))


def concepts_blocked_by_role(text: str) -> frozenset[str]:
    """**Domain 選択に使ってはならない概念**（TD89、2026-08-26）。

    `lexicon.CONCEPT_KEYWORDS` は語 → 概念名（`子ども` → `child`）を
    引く表であり、`Intent.required_concepts` を経て Domain のスコアに
    なる。そこに `ACTOR` / `CONTEXT` の語が混ざっていると、
    **「誰が使うか」が「何を作るか」を決めてしまう。**

    実測: 「子どもが朝の支度を…」で `child` が概念として数えられ、
    `child_growth` が primary domain になり、体重・身長が並んだ。

    ここでは「この Need の中で ACTOR / CONTEXT として現れた語が、
    たまたま概念表にも載っている」ものだけを返す。**語彙表そのものは
    書き換えない**——概念表は Domain 側の語彙であり、こちらの都合で
    削ると別の Need が壊れる。
    """
    from forge_ai.core.lexicon import CONCEPT_KEYWORDS  # noqa: PLC0415

    extraction = extract_semantic_roles(text)
    blocked_surfaces = set(extraction.surfaces_of(SemanticRole.ACTOR))
    blocked_surfaces |= set(extraction.surfaces_of(SemanticRole.CONTEXT))
    if not blocked_surfaces:
        return frozenset()

    # **他に何も語られていないなら、その語がその Need の主題である。**
    #
    # 実装中に踏んだ（既存の Golden が落ちた）:
    #
    #     「旅行の計画を立てたい」        → travel を外すと generic
    #     「スーパーで買う物を管理したい」 → store を外すと generic
    #
    # 「旅行の写真を日付ごとに残して」の旅行は**場面**である——写真・
    # 日付・メモという記録対象が別にあるから、そう言える。記録対象も
    # 行いも見せ方も1つも語られていない文では、その語こそが主題である。
    #
    # 役を消すのではなく、**役が主題に格上げされる条件**を書いている。
    if not extraction.structural_values():
        return frozenset()

    # 構造を決めてよい役でも同じ概念名が出るなら、**止めない**。
    # 例: 「持ち物リストを作りたい」の「持ち物」は MANAGED_OBJECT。
    allowed: set[str] = set()
    for surface, concept in CONCEPT_KEYWORDS:
        if surface in (text or "") and surface not in blocked_surfaces:
            allowed.add(concept)

    blocked: set[str] = set()
    for surface, concept in CONCEPT_KEYWORDS:
        if surface in blocked_surfaces and concept not in allowed:
            blocked.add(concept)
    return frozenset(blocked)