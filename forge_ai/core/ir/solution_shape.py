"""Solution Shape(2026-08-12、CEO「常にニーズに合わせた最適解を出せる
ようにして」対応)。

**解いている問題**: これまで、Forgeが生成するアプリの**形**は1種類しか
無かった。「追加タブ / 一覧タブ / 編集タブ + 入力フォーム +
record_list_view」という構成が、ニーズが何であれ常に出力されていた。

    「腕立ての回数を数えたい」    → 3タブCRUD
    「買うものを並べて消したい」  → 3タブCRUD
    「釣果を細かく記録したい」    → 3タブCRUD  ← これだけが妥当

つまり「いつ作るか」(Conversation Readiness)は判断できるようになった
一方で、「**何を作るか**」は固定だった。買い物メモが欲しい人に、
釣果記録と同じ重さの道具を渡していた。

このモジュールは、Entityの構造から**解の形**を決定的に選ぶ。

**判定材料をEntityのFieldに限っている理由**: ユーザーの言葉
(「数えたい」「チェックしたい」)から直接形を選ぶこともできるが、
それは表現の揺れに弱く、同じニーズでも言い方次第で形が変わってしまう。
一方Entityは、既に会話とEntitySynthesizerを通って「このアプリが
繰り返し記録する1件分のデータ」へ煮詰まった結果であり、
「属性が1つしかない」=「並べてチェックするだけで足りる」という
対応が構造的に安定している。

**現在2形しかない理由(正直な申告)**: 「回数を数える」カウンタ形は、
意図的に**実装していない**。Forge Languageの`ACTION_TYPES`には
`set_value`(固定値の代入)しか無く、`count + 1`のような**動的な
加算を表現する手段が存在しない**(`increment`アクションが無い)。
カウンタ形を作ると「押しても増えないボタン」になるため、Runtimeに
increment相当が入るまでは`RECORD_CRUD`のまま扱う。
"""

from __future__ import annotations

from enum import Enum

from forge_ai.core.ir.ir_types import Entity, FieldType

__all__ = ["SolutionShape", "select_solution_shape"]


class SolutionShape(str, Enum):
    """生成するアプリの構造。Widget名ではなく「道具としての形」を表す。"""

    CHECKLIST = "checklist"
    """並べて、消す。属性を持たない項目の集まり(買い物メモ、持ち物、
    やることリスト)。1画面・タブ無し・入力欄1つ。"""

    RECORD_CRUD = "record_crud"
    """1件が複数の属性を持つ記録(釣果、家計簿、議事録)。
    追加/一覧/編集のタブ構成、型付きフォーム、一覧、グラフ。"""


# CHECKLIST形が吸収できるField型。`checklist`Stateの1項目は
# `{id, text, done}`という形であり、「表示する文字列」1つと
# 「済んだか」1つをちょうど表現できる(それ以上の属性は持てない)。
_CHECKLIST_TEXT_TYPES = frozenset({FieldType.STRING})
_CHECKLIST_DONE_TYPES = frozenset({FieldType.BOOLEAN})


def select_solution_shape(entity: Entity) -> SolutionShape:
    """Entityの構造から、解の形を決定的に選ぶ。

    `CHECKLIST`になるのは、`checklist`Stateの1項目(`{id, text, done}`)
    で**情報を落とさずに表現しきれる**場合だけである:

    * 文字列1つだけ(例: 「買うもの」)
    * 文字列1つ + 真偽値1つ(例: 「やること」+「済んだか」)

    これ以外は、属性を捨てずに保持できる`RECORD_CRUD`にする。
    「軽い形の方が親切だから」といって、日付や金額を持つEntityを
    checklistへ押し込むと、**ユーザーが記録したかった情報が消える**
    ——形を軽くすることと、情報を捨てることは別である。

    Curated Domain(fishing_log等、いずれも4〜5 Field)は、この条件に
    一つも該当しないため、従来どおり`RECORD_CRUD`になる(既存の
    生成結果は1バイトも変わらない)。
    """
    fields = entity.fields
    if not fields:
        # Fieldが1つも無いEntityは`IRGenerator`が作らない想定だが、
        # 防御的に、より情報を落としにくい方(RECORD_CRUD)へ倒す。
        return SolutionShape.RECORD_CRUD

    if len(fields) == 1 and fields[0].type in _CHECKLIST_TEXT_TYPES:
        return SolutionShape.CHECKLIST

    if len(fields) == 2:
        types = {f.type for f in fields}
        if types == _CHECKLIST_TEXT_TYPES | _CHECKLIST_DONE_TYPES:
            return SolutionShape.CHECKLIST

    return SolutionShape.RECORD_CRUD
