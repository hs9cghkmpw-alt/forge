"""**人が普通に書きそうな自由文**を、毎回違う形で作る。

---

## 固定文で試験しない理由

固定文を使うと、Forge はその文に最適化される。「その1文なら通る」は
製品の実力ではない。文面・分野・言い回しを毎回変えて、
**答えを教えない文**を投げる。

## 入れてはいけないもの

* `view.calendar` のような capability の名前
* `calendar_view` のような widget の名前
* Forge の内部用語（Capability / Widget / Registry / Document …）

利用者はそんな言葉を知らない。**テストが答えを直接教える文にしない。**

## 再現できること

`seed` を渡せば同じ文が出る。CI が落ちたら、その seed を指定して
**完全に同じ試験**を再実行できる。
"""

from __future__ import annotations

from dataclasses import dataclass
import random
import re

__all__ = [
    "FORBIDDEN_SUBSTRINGS",
    "FreeTextRequest",
    "RequestShape",
    "generate_request",
    "assert_no_internal_vocabulary",
]

#: 入力文へ入っていてはいけない語。**Forge の内部語彙である。**
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "capability", "Capability", "ケイパビリティ",
    "widget", "Widget", "ウィジェット",
    "registry", "Registry", "レジストリ",
    "view.", "data.", "interact.", "transform.",
    "_view", "forge", "Forge",
    "PROMOTED", "promoted",
)


@dataclass(frozen=True, slots=True)
class Subject:
    """題材。**分野ごとに、利用者が使う言葉だけ**を持つ。"""

    domain: str
    thing: str
    """記録する対象（「食べたもの」など）。"""

    detail: str
    """一緒に残したい細かいこと（「お店の名前」など）。"""

    when_word: str
    """日付を指す、利用者側の言い方（「食べた日」など）。"""


_SUBJECTS: tuple[Subject, ...] = (
    Subject("家計", "使ったお金", "何に使ったか", "使った日"),
    Subject("予定", "打ち合わせ", "相手の名前", "会う日"),
    Subject("在庫", "残っている材料", "残りの数", "仕入れた日"),
    Subject("釣果", "釣れた魚", "釣れた場所", "釣りに行った日"),
    Subject("勤怠", "働いた時間", "担当した仕事", "出勤した日"),
    Subject("タスク", "やること", "締め切りの理由", "片づけた日"),
    Subject("申請", "出した書類", "提出先", "出した日"),
    Subject("健康", "その日の体調", "気になったこと", "測った日"),
    Subject("売上", "売れた商品", "いくらで売れたか", "売れた日"),
    Subject("学習", "勉強したこと", "使った教材", "勉強した日"),
    Subject("予約", "受けた予約", "お客さんの名前", "来店する日"),
    Subject("持ち物", "持っていくもの", "誰のものか", "使う日"),
    Subject("読書", "読んだ本", "感想", "読み終えた日"),
    Subject("練習", "練習した内容", "うまくいったか", "練習した日"),
    Subject("修理", "直した箇所", "使った部品", "直した日"),
)

#: 「記録して一覧で見たい」を、利用者の言い方で。
_LIST_PHRASINGS: tuple[str, ...] = (
    "{thing}を記録して、あとから{list_word}で見返したい",
    "{thing}を残しておいて、{detail}も一緒に{list_word}にしたい",
    "毎回{thing}をメモして、{list_word}で振り返れるようにしたい",
    "{thing}をためていって、{detail}つきの{list_word}を作りたい",
    "{thing}を書きとめておきたい。{list_word}で並べて見たい",
    "{thing}をひとつずつ入れて、{list_word}で確認できるといい",
)

_LIST_WORDS: tuple[str, ...] = ("一覧", "リスト", "並び", "表")

#: 「日付を月ごとに見たい」を、**月表示の名前を出さずに**言う。
#:
#: 「カレンダー」という語そのものは利用者が普通に使う言葉なので入れてよい。
#: 入れてはいけないのは `view.calendar` のような**内部の名前**である。
_MONTH_PHRASINGS: tuple[str, ...] = (
    "{thing}を記録して、{when_word}を月ごとにまとめて見たい",
    "{thing}を残しておいて、どの月に何回あったか分かるようにしたい",
    "{thing}をメモして、{when_word}を月単位で振り返れるようにしたい",
    "{thing}を入れておいて、月ごとの回数がひと目で分かるといい",
    "{thing}を記録したい。{when_word}が月でまとまって見えると助かる",
)

_SOFTENERS: tuple[str, ...] = (
    "", "", "",
    "うまく言えないけど、",
    "ざっくりでいいので、",
    "できれば、",
    "自分用でいいんだけど、",
)

_TAILS: tuple[str, ...] = (
    "。", "。", "。",
    "。あとで見返すことが多いので。",
    "。続けられる形がいい。",
    "。細かい機能はいらない。",
)


class RequestShape:
    """何が要る要求なのか。**入力文には現れない。**"""

    EXISTING_ONLY = "existing_only"
    """いま持っている能力だけで作れるはずの要求。"""

    NEEDS_MONTHLY_VIEW = "needs_monthly_view"
    """月ごとにまとめて見る能力が要る要求。"""


@dataclass(frozen=True, slots=True)
class FreeTextRequest:
    text: str
    shape: str
    domain: str
    seed: int

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "shape": self.shape,
            "domain": self.domain,
            "seed": self.seed,
        }


def assert_no_internal_vocabulary(text: str) -> None:
    """**答えを教える文になっていないか。**"""
    lowered = text.lower()
    for token in FORBIDDEN_SUBSTRINGS:
        if token.lower() in lowered:
            raise AssertionError(
                f"free-text request leaks Forge's internal vocabulary {token!r}: {text!r}",
            )
    if re.search(r"[A-Za-z]{4,}", text):
        raise AssertionError(
            f"free-text request contains an English identifier-like word: {text!r}",
        )


def generate_request(
    seed: int,
    shape: str = RequestShape.EXISTING_ONLY,
    *,
    avoid_domain: str | None = None,
) -> FreeTextRequest:
    """seed から自由文を1つ作る。**同じ seed なら同じ文。**"""
    rng = random.Random(seed)
    candidates = [s for s in _SUBJECTS if s.domain != avoid_domain]
    subject = rng.choice(candidates)

    if shape == RequestShape.NEEDS_MONTHLY_VIEW:
        template = rng.choice(_MONTH_PHRASINGS)
    else:
        template = rng.choice(_LIST_PHRASINGS)

    body = template.format(
        thing=subject.thing,
        detail=subject.detail,
        when_word=subject.when_word,
        list_word=rng.choice(_LIST_WORDS),
    )
    text = f"{rng.choice(_SOFTENERS)}{body}{rng.choice(_TAILS)}"
    assert_no_internal_vocabulary(text)
    return FreeTextRequest(
        text=text, shape=shape, domain=subject.domain, seed=seed,
    )
