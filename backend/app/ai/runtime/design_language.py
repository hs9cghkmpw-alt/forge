"""Design Language V1 — **AIが選ぶ語彙**
(FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、2026-08-17)。

---

## これは「見た目の設定」ではない

Product Direction §3 が決めている分担がこのモジュールの理由である。

> **AIは意味を決める。Forgeは品質を保証する。**

```
❌ AIが決める:  font_size: 36 / color: "#23D18B" / padding: 16
✅ AIが決める:  metric.primary / finance.income / surface.elevated
   Forgeが保証: それが実際に何pxで何色になるか
```

この分担には3つの効果がある。

1. **生成品質が上がる** — 値のブレが構造的に消える。AIが毎回
   `#12FF88`と`#00FF88`のどちらを選ぶかで揺れることが無くなる
2. **Local AIが小さくて済む** — 語彙から1つ選ぶのは、色コードと
   フォントサイズを整合的に生成するよりはるかに易しい
3. **Evidenceが意味単位で残る** — 「`#23D18B`が選ばれた」ではなく
   「`finance.income`が選ばれ、利用者がACCEPTEDした」が残る

3番目が閉ループの入口である。**見た目の作業が、そのままLocal AIの
学習素材になる。**

## 語彙を無制限に増やさない

Golden Apps（Finance / Wellness / Tasks）を表現するのに必要な
**最小の語彙**から始める。増やすときは、

* 既存の役割の組み合わせで表現できないか
* Golden App以外にも一般化するか

を先に確かめる。語彙が増えるほど、AIが選び間違える余地と、
Runtimeが保証すべき組み合わせが増える。

## 「識別子であって自然言語ではない」を型で示す

`SemanticRole`は`[a-z0-9._-]`だけを許す。これは見た目の制約では
なく、**利用者の発話がEvidenceへ混入する経路を塞ぐ**ためである
(006 §22)。`GenerationRecord.design_language_roles`は自由文字列の
tupleなので、型だけでは「発話全文を入れる」を防げなかった
(014 §6)。

## Local AIへ渡すための情報を、語彙と同じ場所に持つ

各roleは`meaning` / `use_when` / `avoid_when`を持つ。将来RAGで
Local AIへ渡すためであり、**語彙の定義とその説明が別ファイルに
分かれると必ずずれる**ので同居させている(§12)。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    "DESIGN_LANGUAGE_VERSION",
    "InvalidSemanticIdentifier",
    "RoleCategory",
    "SEMANTIC_ROLES",
    "SemanticRole",
    "design_roles_in",
    "is_known_role",
    "role_definition",
    "validate_identifier",
]

DESIGN_LANGUAGE_VERSION = "1.0"

# Forge内部Vocabularyの形。**自然言語を入れない**ための境界である。
#
#   metric.primary      OK
#   finance.income      OK
#   "残高を目立たせて"    NG（空白・非ASCII）
#   "Metric.Primary"     NG（大文字）
#
# 大文字を許さないのは、`metric.primary`と`Metric.Primary`が別の
# 識別子として両方記録されると、Evidenceの集計が割れるためである。
# 「同じものは同じ文字列」を機械的に保証する方が、後から正規化する
# より確実である。
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9]*([._-][a-z0-9]+)*$")
_MAX_IDENTIFIER_LENGTH = 64


class InvalidSemanticIdentifier(ValueError):
    """Forge内部Vocabularyとして受け付けられない文字列。"""

    def __init__(self, raw: object, reason: str) -> None:
        # **値そのものは短く切って出す。** 利用者の発話が誤って渡された
        # ときに、それを丸ごとログへ流さないため(006 §22)。
        shown = repr(raw)[:40]
        super().__init__(f"Semantic identifierとして不正です({reason}): {shown}")


def validate_identifier(raw: object) -> str:
    """Forge内部Vocabularyの識別子として検証する(014 §6)。

    **自由文を弾くことが目的**であって、綺麗さのためではない。
    """
    if not isinstance(raw, str):
        raise InvalidSemanticIdentifier(raw, "文字列ではない")
    if not raw:
        raise InvalidSemanticIdentifier(raw, "空")
    if len(raw) > _MAX_IDENTIFIER_LENGTH:
        raise InvalidSemanticIdentifier(raw, f"{_MAX_IDENTIFIER_LENGTH}文字を超える")
    if not _IDENTIFIER_PATTERN.match(raw):
        raise InvalidSemanticIdentifier(raw, "使えるのは小文字英数と . _ - のみ")
    return raw


class RoleCategory(str, Enum):
    """役割の種類。Runtimeがどの軸へ変換するかを決める。"""

    TYPOGRAPHY = "typography"
    COLOR = "color"
    SURFACE = "surface"
    SHAPE = "shape"
    DENSITY = "density"
    COMPONENT = "component"


@dataclass(frozen=True)
class SemanticRole:
    """1つの意味的役割。

    `meaning` / `use_when` / `avoid_when` は**Local AIへ渡すための
    説明**である(§12)。語彙の定義と説明を同じ場所に持つのは、
    別ファイルに分けると必ずずれるためである。
    """

    id: str
    category: RoleCategory
    meaning: str
    use_when: str
    avoid_when: str

    def __post_init__(self) -> None:
        validate_identifier(self.id)

    def to_knowledge_entry(self) -> dict[str, str]:
        """将来RAGでLocal AIへ渡す形。**まだRAG本体は無い**が、
        渡せる形にしておかないと後から作り直しになる。"""
        return {
            "id": self.id,
            "category": self.category.value,
            "meaning": self.meaning,
            "use_when": self.use_when,
            "avoid_when": self.avoid_when,
        }


def _role(id_: str, category: RoleCategory, meaning: str, use_when: str, avoid_when: str) -> SemanticRole:
    return SemanticRole(
        id=id_, category=category, meaning=meaning, use_when=use_when, avoid_when=avoid_when
    )


_T = RoleCategory.TYPOGRAPHY
_C = RoleCategory.COLOR
_S = RoleCategory.SURFACE
_SH = RoleCategory.SHAPE
_D = RoleCategory.DENSITY
_CO = RoleCategory.COMPONENT

#: Design Language V1の全語彙。**Golden Apps 3系統を表現できる最小集合。**
#:
#: 増やすときは「既存の組み合わせで表現できないか」「Golden App以外へ
#: 一般化するか」を先に確かめること。
SEMANTIC_ROLES: tuple[SemanticRole, ...] = (
    # --- Typography ----------------------------------------------------
    _role("text.display", _T, "画面で最も大きい表示文字。",
          "アプリ名やオンボーディングの見出し。",
          "本文。1画面に2つ以上。"),
    _role("text.headline", _T, "セクションの主見出し。",
          "画面内の大きな区切り。",
          "リスト項目のタイトル(それはtext.title)。"),
    _role("text.title", _T, "カードやリスト項目のタイトル。",
          "個々の項目の名前。",
          "画面全体の見出し。"),
    _role("text.body", _T, "本文。既定の可読サイズ。",
          "説明文・メモ・自由記述の表示。",
          "数値の強調(それはmetric.*)。"),
    _role("text.label", _T, "入力欄やボタンに付く短い語。",
          "フィールド名・タブ名・凡例。",
          "文章。"),
    _role("text.secondary", _T, "補助情報。本文より弱い。",
          "日付・単位・注記・前月比の説明。",
          "主要な内容。読めなくてよい情報ではないので、極端に小さくしない。"),
    _role("metric.primary", _T, "画面で**最も重要な単一のKPI**。",
          "残高・合計・今日の達成率など、利用者が最初に見る1つの数値。",
          "リスト内の全数値。**同一画面で2つ以上使わない。**"),
    _role("metric.secondary", _T, "主KPIを補足する数値。",
          "前月比・内訳の小計・サブ指標。",
          "主KPIと同じ大きさにしたい数値(それはmetric.primary)。"),

    # --- Color semantics ------------------------------------------------
    _role("color.primary", _C, "アプリの主色。操作の中心。",
          "主要CTA・選択状態・アクセント。",
          "本文の色。警告の色。"),
    _role("color.secondary", _C, "副次的なアクセント。",
          "補助的な操作・タグ。",
          "主要CTA。"),
    _role("state.success", _C, "成功・達成・正常。",
          "完了・目標達成・正常稼働。",
          "収入(それはfinance.income)。意味が違うものを色で兼用しない。"),
    _role("state.warning", _C, "注意。まだ失敗ではない。",
          "残量が少ない・期限が近い。",
          "エラー。"),
    _role("state.danger", _C, "エラー・危険・不可逆操作。",
          "削除・失敗・上限超過。",
          "支出(それはfinance.expense)。"),
    _role("finance.income", _C, "**金銭の増加**という意味。",
          "収入・入金・プラスの残高変化。",
          "一般的な成功(それはstate.success)。"),
    _role("finance.expense", _C, "**金銭の減少**という意味。",
          "支出・出金・マイナスの残高変化。",
          "エラー(それはstate.danger)。"),
    _role("text.primary", _C, "主要な文字色。",
          "本文・見出しの色。",
          "補助情報。"),

    # --- Surface --------------------------------------------------------
    _role("surface.background", _S, "画面全体の地の面。",
          "Scaffoldの背景。",
          "カード。"),
    _role("surface.card", _S, "情報のまとまりを載せる面。",
          "KPIカード・リスト項目の箱。",
          "画面全体。"),
    _role("surface.elevated", _S, "背景より手前にある面。",
          "強調したいカード・重ねて見せる領域。",
          "全カード。**全部を持ち上げると階層が消える。**"),
    _role("surface.selected", _S, "選択中であることを示す面。",
          "選択されたタブ・行。",
          "常時強調。"),

    # --- Shape ----------------------------------------------------------
    _role("shape.small", _SH, "小さい角丸。", "チップ・小ボタン。", "大きなカード。"),
    _role("shape.medium", _SH, "標準の角丸。", "カード・入力欄。", "円形にしたいもの。"),
    _role("shape.large", _SH, "大きい角丸。", "ヒーローカード・シート。", "小さな要素。"),
    _role("shape.pill", _SH, "完全な丸み。", "タグ・フィルタチップ。", "文章を含む広い面。"),

    # --- Density --------------------------------------------------------
    _role("density.compact", _D, "情報を詰める。", "一覧・タスクリスト。", "読ませたい本文。"),
    _role("density.normal", _D, "標準の余白。", "多くの画面の既定。", ""),
    _role("density.relaxed", _D, "ゆったり見せる。", "日記・ウェルネスなど落ち着かせたい画面。", "密度が要る一覧。"),

    # --- Component intent ------------------------------------------------
    _role("button.primary", _CO, "その画面の主要操作。",
          "保存・追加・実行。**画面に1つ。**",
          "取り消し・戻る。"),
    _role("button.secondary", _CO, "副次的な操作。",
          "キャンセル・絞り込み。",
          "主要操作。"),
    _role("card.metric", _CO, "KPIを見せるカード。",
          "残高・達成率のヒーロー領域。",
          "自由記述の表示。"),
    _role("card.summary", _CO, "内訳・要約を見せるカード。",
          "カテゴリ別集計・週次まとめ。",
          "単一KPI(それはcard.metric)。"),
    _role("card.list", _CO, "繰り返し項目を並べるカード。",
          "記録一覧・タスク一覧。",
          "単発の情報。"),
    _role("navigation.primary", _CO, "画面間の主要な行き来。",
          "下部ナビ・主要タブ。",
          "画面内の絞り込み。"),
)

_ROLE_BY_ID: dict[str, SemanticRole] = {r.id: r for r in SEMANTIC_ROLES}


def is_known_role(role: object) -> bool:
    """Design Language V1の語彙に含まれるか。

    **未知のroleは通さない。** 自由に増やせると、Runtimeが保証できない
    値が入り込み、「意味を選ばせる」という分担が崩れる。
    """
    return isinstance(role, str) and role in _ROLE_BY_ID


def role_definition(role: str) -> SemanticRole | None:
    return _ROLE_BY_ID.get(role)


def knowledge_entries() -> tuple[dict[str, str], ...]:
    """将来RAGでLocal AIへ渡すための全語彙(§12)。"""
    return tuple(r.to_knowledge_entry() for r in SEMANTIC_ROLES)


def design_roles_in(forge_document: Any) -> tuple[str, ...]:
    """**最終Forge Documentの事実から**、使われたroleを抽出する(§11)。

    要件はすべて「後からEvidenceとして信用できること」から来ている。

    * **AIの自己申告から取らない** — 「使ったつもり」ではなく、
      実際にDocumentへ入った値だけを見る
    * **Repair後の確定Documentから取る** — 直す前の値を記録すると、
      実際に描画されたものと食い違う
    * **決定的** — 同じDocumentからは必ず同じ結果。ソートする
    * **重複を潰す** — 同じroleを10回使ったことは、ここでは数えない
      (使ったか否かの集合として持つ)
    * **未知の値は入れない** — 語彙に無い文字列は捨てる。自由文が
      Evidenceへ入る経路を残さない(006 §22 / 014 §6)
    """
    found: set[str] = set()
    _collect_roles(forge_document, found)
    return tuple(sorted(found))


def _collect_roles(node: Any, found: set[str]) -> None:
    """`style_role`という**キー名**だけを見る。

    値の形で判定しない——たまたま`metric.primary`という文字列が
    本文に入っていたものを拾わないため。
    """
    if isinstance(node, dict):
        role = node.get("style_role")
        if is_known_role(role):
            found.add(role)
        for value in node.values():
            _collect_roles(value, found)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _collect_roles(value, found)
