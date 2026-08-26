"""アプリの**名前**を決める（Generated UI Quality Gate v2 修正1、2026-08-26）。

---

## 何が起きていたか

実描画で 8 アプリを撮ったところ、AppBar にこう出ていた。

    毎日の収入と支出を記録して残高を見たい
    子どもが朝の支度をひとつずつチェックできるようにしたい
    部署ごとの売上を月別に集計してグラフで比べたい

これは**名前ではなく、利用者が言った願望文そのもの**である。

原因は `Intent.goal` を**そのままアプリ名として使っていた**こと
（`understanding/intent_recognizer.py` の古いコメントにも
「`Intent.goal`は`ApplicationPlan.title`にそのまま使われる」と書いてある）。

**目的（goal）と名前（name）は別物である。**

* 目的は「何のために作るか」——文である
* 名前は「それを何と呼ぶか」——短い名詞句である

`_derive_title_like_goal()` は末尾の依頼表現を落とすが、
どれにも当たらなければ**文をそのまま返す**（安全側のフォールバック）。
その「安全側」が、名前としては一番悪い結果を出していた。

## なぜ形態素解析で切り出さないのか

「残高を見たい」から「たい」だけ落とすと**「残高を見」**になる。
**半端に壊れた名前は、元の文より悪い。** 形態素解析は新規依存であり、
入れても願望文からの名詞句抽出が安全になるわけではない。

## 代わりにやること — 名付けを「生成の一部」にする

名前を付けるのは**理解の結果**である。だから

1. **AI が名付けたなら、それを検査して採用する**
   （`design_intent` の軸ごと検証と同じ形。外れたら既定値へ落として
   由来を記録する）
2. 通らなければ、**取り出せた概念のラベル**から名付ける
   （「家計簿記録」——Forge が実際に理解したものの名前）
3. それも無ければ、**Domain の日本語名**（`Domain.user_facing_name`）
4. どれも無ければ、**分からなかったと認める**

**候補は全部 `is_name_like()` を通す。例外は無い。** 要求文は
この検査を通らない（実測: 8 件すべて落ちる）。逆に、語尾を落とした結果が
たまたま短い名詞句になっていれば（「買い物リストを作りたい」→
「買い物リスト」）、それは**名前として正しい**ので通す。
判定するのは出所ではなく、**名前の形をしているかどうか**である。

4 まで落ちたということは Forge がその要求を理解できていないという
ことであり、それを名前で取り繕わない（`CLAUDE.md` §3「分からないものを
楽観側へ倒さない」）。

## 由来を返す

`NameSource` を戻り値に含める。「AI が名付けた」と
「Forge が既定で埋めた」を後から区別できないと、
**名付けができているかどうかを測れない**。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

#: 名前として許す長さ。これを超えるものは「名前」ではなく「説明文」である。
#:
#: 実測（Quality Gate v2）: 落とすべき文はいずれも 17 文字以上、
#: 通すべき名前（買い物リスト / 家計簿記録 / 釣果記録 / やること）は
#: いずれも 6 文字以下だった。境界は広めに取る——長さで落とすのは
#: 最後の網であり、主な判定は下の語尾・句読点で行う。
MAX_APP_NAME_LENGTH = 14

#: 名前に**あってはならない**印。
#:
#: * 句読点・疑問符 → 1つの名詞句ではない
#: * 願望・依頼の語尾 → 名前ではなく要求文である
#: * 接続の「して」 → 複数の動作をつないだ文である
#:
#: 「〜ます」「〜です」を丸ごと禁止語にはしない。名詞に含まれうる
#: （「ますく」等）ので、**語尾**としてだけ見る。
_FORBIDDEN_ANYWHERE: tuple[str, ...] = (
    "、", "。", "，", "．", ",", ".", "！", "？", "!", "?",
    "したい", "たいです", "ほしい", "欲しい", "ください",
    "できるように", "したら", "しないと", "しなきゃ",
    "して", "せて",
)

_FORBIDDEN_SUFFIXES: tuple[str, ...] = (
    "たい", "ます", "です", "ました", "ません", "だろう", "しよう",
    "する", "やる", "見る", "作る",
)

#: **内部識別子**の形。`item` / `fish_record` / `task` 等。
#:
#: これを弾かないと、Entity のラベルが取れなかったときに
#: `entity.name`（英小文字の識別子）がそのままアプリ名になる。
#: 実際に踏んだ——`decide_app_name()` を入れた直後、
#: 「日常の 買い物リストです」を正しく落とした結果、次の候補の
#: **`item` が名前として通ってしまった**（`test_pipeline.py` が検出）。
#:
#: #29「mockの品質: 内部識別子を出さない」と同じ穴である。**3度目**。
#:
#: 大文字を含むもの（`Todo`）は弾かない——人が付けた名前でありうる。
#: 全部が英小文字・数字・下線なら、それは人へ見せる名前ではない。
_INTERNAL_IDENTIFIER = re.compile(r"^[a-z0-9_]+$")

#: 何も分からなかったときの名前。
#:
#: **利用者の文を入れない。** ここへ落ちたということは Forge が
#: その要求を理解できていないということであり、名前で取り繕わない。
GENERIC_APP_NAME = "新しいアプリ"


class NameSource(str, Enum):
    """名前が**どこから来たか**。"""

    AI = "ai"
    """AI が名付け、`is_name_like()` を通った。**これが本来の姿である。**"""

    ENTITY = "entity"
    """取り出せた概念のラベルから名付けた（例: 「家計簿記録」）。"""

    DOMAIN = "domain"
    """Domain の日本語名から名付けた（例: 「やること」）。"""

    GENERIC = "generic"
    """**何も分からなかった。** 名前を付けられていない、という事実。"""


@dataclass(frozen=True)
class AppName:
    """決まった名前と、その由来。"""

    text: str
    source: NameSource

    @property
    def named_by_understanding(self) -> bool:
        """**理解の結果として名付けられたか。**

        `GENERIC` は「名前が付いた」ではなく「付けられなかった」である。
        測るときにここを混ぜない。
        """
        return self.source is not NameSource.GENERIC


def is_name_like(text: str | None) -> bool:
    """それは**名前**か（短い名詞句か）。文なら `False`。

    完全な日本語判定ではない。**要求文を名前として通さない**ための
    決定的な検査であり、通したものが必ず良い名前だとは主張しない。
    """
    candidate = (text or "").strip()
    if not candidate:
        return False
    if len(candidate) > MAX_APP_NAME_LENGTH:
        return False
    if _INTERNAL_IDENTIFIER.match(candidate):
        return False
    if any(mark in candidate for mark in _FORBIDDEN_ANYWHERE):
        return False
    return all(not candidate.endswith(suffix) for suffix in _FORBIDDEN_SUFFIXES)


def decide_app_name(
    *,
    ai_title: str | None = None,
    entity_label: str | None = None,
    domain_label: str | None = None,
) -> AppName:
    """アプリ名を決める。**候補は全部 `is_name_like()` を通す。**

    上から順に見て、検査を通った最初のものを採用する。どれも通らなければ
    `GENERIC_APP_NAME`——「分からなかった」をそう書く。

    要求文をここへ渡しても構わない。**検査が落とす。** 出所で弾くと
    「買い物リスト」のような正しい名前まで落ちる。
    """
    for candidate, source in (
        (ai_title, NameSource.AI),
        (entity_label, NameSource.ENTITY),
        (domain_label, NameSource.DOMAIN),
    ):
        text = (candidate or "").strip()
        if is_name_like(text):
            return AppName(text=text, source=source)
    return AppName(text=GENERIC_APP_NAME, source=NameSource.GENERIC)


def domain_label_for(domain_category: str | None) -> str | None:
    """Domain カテゴリ名（`"household_budget"` 等）から利用者向けの
    日本語名を引く。

    表を新しく作らない。`Domain.user_facing_name`（`label_ja` 優先）が
    既に「ユーザーへ提示してよい名前」として存在する。
    """
    from forge_ai.core.domain_model import DomainCategory, DomainRegistry

    if not domain_category:
        return None
    try:
        category = DomainCategory(domain_category)
    except ValueError:
        return None
    if category is DomainCategory.GENERIC:
        # **generic は「分からなかった」である。** その日本語名を
        # アプリ名にすると、分からなかったことが名前で隠れる。
        return None
    return DomainRegistry().get(category).user_facing_name or None
