"""Forge Language Validator(v1.0 + v1.1 + v1.2 + v1.3 + v1.4対応)。

FORGE-MILESTONE-003。v1.0・v1.1は凍結のまま、v1.2でRuntime契約を拡張した:
  - State型に `number` を追加。
  - Action型に `set_state`/`toggle_state`/`reset_state`/`submit_form`/`composite`
    の5種を追加(navigate/go_back/set_value/add_itemは維持。set_valueは
    v1.0/v1.1互換のため廃止しない)。
  - text_field/checkboxへ任意の `validation` プロパティを追加。

FORGE v0.7(Record Runtime Phase1)でv1.3を追加した:
  - State型に `record_list` を追加(複数Fieldを持つRecordの配列)。
  - Widget型に `record_list_view` を追加(`record_list` state専用、
    Phase1では`layout: "card"`のみ)。
  - Action型に `add_record` を追加(`field_bindings`で複数の
    source stateを1つのRecordへ束ねる、`FORGE-IR-V1-PROPOSAL.md`
    4.3節で設計した「宣言的なField束ね」方式)。
  - **Phase1では`update_record`/`delete_record`・`record_schemas`
    (Field型の宣言・Entity単位Validation)は未実装(指示書の制約)。
    `record_list`のFieldは、現時点では緩い型(string/number/boolean)
    のみで検査し、宣言されたSchemaとの突き合わせは行わない。**

FORGE v0.8(Record Runtime Phase2)で、v1.3を維持したまま(指示書の
制約「Versionは1.3のまま維持」)、CRUD基盤を追加した:
  - State型に `selected_record` を追加(選択中の1件、無選択時は
    `value: null`)。単体の`record`型そのもの(v1.3提案時のPhase2以降
    構想)ではなく、「選択」というPhase2固有のユースケースに限定した
    命名にしている。
  - Action型に `select_record`/`update_record`/`delete_record` を追加。
  - `record_list_view` Widgetへ、選択・編集・削除を有効化する
    `selectable`/`selected_state_ref`/`select_field_bindings`
    プロパティを追加(既存の`state_ref`/`layout`/`display_fields`/
    `empty_state_text`は無変更)。

FORGE v0.9(Typed Record Runtime Phase1)でv1.4を追加した:
  - 文書トップレベルへ `record_schemas` を追加した(`record_list`とは
    独立した、Field型定義)。1件のSchemaは、`name`(識別子)・
    `type`(string/number/boolean/date/choiceのいずれか)・`label`・
    `required`・(type="choice"の場合のみ)`options`を持つFieldの配列
    (`fields`)を持つ。
  - `record_list`型のStateへ、任意の`schema_ref`プロパティを追加した
    (`record_schemas`内のいずれかのSchema名を指す)。
  - **今回は型情報の追加のみであり、Widget生成・CRUD挙動・Runtime
    動作は一切変更していない**(指示書の制約)。既存の`record_list`
    (`schema_ref`無し)は引き続き合格し続ける(後方互換)。

`version`フィールドの値によって、その文書で使用できるWidget/Action種別を
制限する(v1.0/v1.1/v1.2文書がv1.3専用Action/State/Widget型を使ったら
不合格にする)。

設計上の注記(FORGE-MERGE-001 D9から継続): `jsonschema`パッケージは
引き続きサンドボックスに無いため、標準ライブラリのみで実装している。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.ai.runtime.design_language import is_known_role


# ---------------------------------------------------------------------------
# 定数(shared/schemas/ui_schema.v1*.json と同期させること)
# ---------------------------------------------------------------------------

MAX_NESTING_DEPTH = 12
MAX_WIDGETS_PER_SCREEN = 200
MAX_SCREENS = 20
MAX_CHECKLIST_ITEMS = 500
MAX_STRING_LIST_ITEMS = 500
MAX_COMPOSITE_ACTIONS = 10
MAX_COMPOSITE_DEPTH = 3  # composite内にcomposite…と何段ネストしてよいか
MAX_RECORD_LIST_ITEMS = 500  # checklist/string_listと同じ上限に揃える
MAX_RECORD_FIELDS = 20  # 1Recordが持てるFieldの上限(既存state.maxProperties: 30より保守的)
MAX_FIELD_BINDINGS = 20  # add_record.field_bindingsの上限(MAX_RECORD_FIELDSと揃える)

SUPPORTED_VERSIONS = {"1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12"}

# バージョン文字列同士を数値として比較するための順序付きタプル。
# **設計上の注記(このセッションで実際に発見・修正した再発バグへの
# 対策)**: `version in {"1.2", "1.3"}`のような、特定バージョンの
# 集合を直接書き下す形は、新しいVersionを追加するたびに、その
# プロパティを許可すべき箇所を1つずつ探して追記する必要があり、
# 実際にFORGE v0.7→v0.8→v0.9で3回とも該当箇所を見落として、
# 生成したドキュメントが不合格になるバグを起こした(このセッション
# 自身で発見・修正した)。今回、`_version_at_least()`という「以上」
# 比較のヘルパーへ置き換え、将来のVersion追加(v1.5等)で
# 同種の見落としが起きないようにした。
# **文字列の大小比較ではなく、この並びの位置で比較する**(`_at_least()`)。
# "1.10" < "1.9" になる文字列比較を避けるためであり、ここへ追記する
# 順序がそのままバージョンの前後関係になる。
_VERSION_ORDER = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12")


def _version_at_least(version: str, minimum: str) -> bool:
    """`version`が`minimum`以上かどうかを判定する。未知のversion文字列
    が渡された場合は安全側(False)に倒す。"""
    if version not in _VERSION_ORDER or minimum not in _VERSION_ORDER:
        return False
    return _VERSION_ORDER.index(version) >= _VERSION_ORDER.index(minimum)

# v1.0で凍結された6種
WIDGET_TYPES_V1_0 = {"text", "text_field", "button", "column", "row", "checklist"}
# v1.1で追加された6種
WIDGET_TYPES_V1_1_ADDITIONS = {"heading", "checkbox", "card", "list", "divider", "form"}
# v1.2はWidget種別を追加していない(既存12種のtext_field/checkboxへ
# validationプロパティを追加しただけ)
# v1.3で追加された1種(FORGE v0.7 Record Runtime Phase1)。
# FORGE v0.8(Phase2)では新しいWidget**型**は追加せず、この
# `record_list_view`自体のプロパティを拡張した(下記`_check_widget_schema`
# 参照)。
WIDGET_TYPES_V1_3_ADDITIONS = {"record_list_view"}
# v1.5で追加された1種(FORGE v1.0 Product Quality Sprint1)。
# `record_list_view`自体は新しいWidget型を追加せず、`layout`プロパティへ
# "grid"を追加しただけ(下記`_check_widget_schema`参照、v1.3提案時から
# 予定されていた拡張)。
WIDGET_TYPES_V1_5_ADDITIONS = {"section_header"}
# v1.6で追加された2種(FORGE-AI-QUALITY-001、2026-08-11、CEO承認によりForge
# Language Freeze運用を解除して追加)。
#
# `docs/spec/LANGUAGE_FREEZE.md`は「今後数年変更しない土台」を目指す運用
# 方針だったが、2章のFreeze条件(実Runtimeでの`flutter analyze`確認等)を
# そもそも一度も満たしておらず、正式に凍結宣言されたことは無かった
# (同ドキュメント1章に明記済み)。CEOへ「今のWidget語彙(14種)では
# テキスト入力とチェックボックス相当の表現力しか無く、'家計簿の収支を
# グラフで見たい'という既存の例文(`example_picker_sheet.dart`)自体が
# 実現不可能な約束になっている」ことを報告し、Widget追加の凍結解除の
# 承認を得た上で着手した。
#
# * `choice_field`: 決まった選択肢から1つ選ぶ入力(例: 家計簿の
#   カテゴリ)。TD33で「text_fieldのplaceholderに選択肢を埋め込む」
#   という応急処置をしたが、根本的にはドロップダウンで選ばせるべき
#   だった(誤入力自体を構造的に防げる)。
# * `bar_chart`: record_listの数値Fieldを棒グラフで可視化する(例:
#   家計簿の支出内訳)。集計(月ごとの合計等)は行わない、Phase1の
#   最小実装(1 Record = 1本の棒)。
WIDGET_TYPES_V1_6_ADDITIONS = {"choice_field", "bar_chart"}

# v1.7で追加された2種(FORGE-AI-QUALITY-001、2026-08-11、CEO「全て実装
# してくれ。確認もしなくて良い、ゴールは示している。つくってくれ。」に
# 対応する、Widget Vocabulary Expansionの第2弾)。
#
# * `date_field`: 日付を選ばせる入力(Flutterの`showDatePicker()`で
#   実装、新規パッケージ依存なし)。TD33で「text_fieldのplaceholderに
#   YYYY-MM-DD形式を書くだけ」という応急処置をしていたが、choice_field
#   (TD34)と同じ理由で、自由入力を構造的に禁止するカレンダーUIへ置き換える。
# * `tab_view`: 複数の子Widget群を、タブ切り替えで表示する(Flutterの
#   `DefaultTabController`/`TabBar`/`TabBarView`で実装、新規パッケージ
#   依存なし)。単一画面に「追加」「一覧」「編集」を縦に積み上げる
#   今までの構成(FORGE v1.0 Sprint1、section_headerで区切っただけ)を、
#   タブで切り替える構成へ発展させる。
#
#   **画面遷移(Navigator.push)ではなくタブを選んだ理由(重要な設計判断)**:
#   Flutter Runtime側を調査した結果、`ForgeScreenView`は画面遷移の
#   たびに**独立した新しい`ForgeRuntimeState`**を生成する設計になって
#   いる(`forge_renderer.dart`の`_ForgeScreenViewState.initState()`)。
#   つまり「一覧画面」の`records`と「追加画面」の`records`は、同じ
#   `state_ref`名を使っていても実行時には別々のインスタンスであり、
#   追加画面で`add_record`しても一覧画面には反映されない
#   (画面をまたいだState共有・戻り値の受け渡し機構が存在しないため)。
#   複数`screens`によるCRUD分割は、この制約を無視すると「追加した
#   はずのデータが一覧に出てこない」という壊れたアプリを生成して
#   しまう。この根本的なRuntime側の制約を安全に回避しつつ、
#   「単一画面に全部詰め込まれている」という見た目の問題だけを
#   解決する手段として、State共有が一切不要な`tab_view`
#   (同一画面・同一Stateのまま、表示を切り替えるだけ)を選んだ。
WIDGET_TYPES_V1_7_ADDITIONS = {"date_field", "tab_view"}

# v1.8で追加された1種(FORGE-AI-QUALITY-001、2026-08-11、CEO「壊れてる?
# って機能でもどんどん追加してくれ。あとでなおす。」)。
#
# * `slider`: 上限・下限が決まっている数値Field(例: reading_logの
#   「評価(5段階)」)向けの入力(Flutter標準の`Slider`で実装、新規
#   パッケージ依存なし)。`state_ref`は既存の"number"型state
#   (v1.2で追加済み)を直接使う——choice_field/date_fieldと違って
#   新しいstate型は不要。範囲外の値を構造的に入力できない。
WIDGET_TYPES_V1_8_ADDITIONS = {"slider"}

# v1.11で追加された1種(FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、TD69、
# 2026-08-17)。**v1.10でWidgetを1つも増やさなかったのに、ここで増やす
# 理由**を残しておく。
#
# v1.10でDesign Language(意味的役割)を入れたとき、`metric.primary`
# ——「画面で最も重要な単一のKPI」——という役割を語彙へ入れた。しかし
# **その役割を持てるWidgetが1つも無かった**。既存19種で数値を出せるのは
#
#   * `text`      : Stateの文字列を出すだけ。集計できない
#   * `bar_chart` : **複数**の値を並べる。単一の主数値には使えない
#
# の2つで、どちらも「今月の残高を、画面で一番大きく1つだけ見せる」を
# 表現できない。つまり語彙に**出力先の無い言葉**が入っていた
# (`docs/reports/FORGE-R1-DESIGN-LANGUAGE-014-report.md`の未達2)。
#
# * `metric_view`: record_listを**1つの数値へ畳んで**大きく見せる。
#   `bar_chart`との違いは、グループ化しない(=常に1つの値になる)こと
#   である。集計そのものは既存のTRANSFORM層
#   (`frontend/lib/json_ui/runtime/forge_aggregate.dart`)を使い、
#   このWidgetは所有しない——v1.9で`bar_chart`が最初の利用者になった
#   のと同じ形で、2番目の利用者になる。
WIDGET_TYPES_V1_11_ADDITIONS = {"metric_view"}

WIDGET_TYPES_BY_VERSION: dict[str, set[str]] = {
    "1.0": WIDGET_TYPES_V1_0,
    "1.1": WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS,
    "1.2": WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS,
    "1.3": WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS,
    # FORGE v0.9(Typed Record Runtime Phase1)。record_schema導入は
    # 型情報の追加のみで、新しいWidget型は追加しない(指示書の制約)。
    "1.4": WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS,
    "1.5": WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS | WIDGET_TYPES_V1_5_ADDITIONS,
    "1.6": (
        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS
        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS
    ),
    "1.7": (
        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS
        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS
    ),
    "1.8": (
        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS
        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS
        | WIDGET_TYPES_V1_8_ADDITIONS
    ),
    # v1.9(FORGE-USER-GUIDED-SELF-EXTENSION-006 Phase 4、2026-08-13)は
    # **新しいWidget型を追加しない**。`bar_chart`へ`group_by`/`aggregate`を
    # 足しただけである(v1.2がvalidationプロパティを、v1.5が
    # record_list_viewへlayout="grid"を足したのと同じ、property-onlyの追加)。
    #
    # Widgetを増やさずに表現の幅を増やせたのは、足したものが**表示ではなく
    # データ変換**だからである(`TRANSFORM`層、v2レビュー §4)。
    "1.9": (
        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS
        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS
        | WIDGET_TYPES_V1_8_ADDITIONS
    ),
    # v1.10(FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、2026-08-17)。
    # **Widgetを1つも増やさない。** 足したのは全Widget共通の
    # `style_role`(Design Languageの意味的役割)であり、表示できるものの
    # 種類ではなく「どういう意味で見せるか」が増えた。
    #
    # v1.9で「Widgetを増やさずに表現の幅を増やせた」のと同じ形である
    # ——あちらはデータ変換、こちらは意味付け。
    "1.10": (
        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS
        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS
        | WIDGET_TYPES_V1_8_ADDITIONS
    ),
    # v1.11。`metric_view`(Hero KPI)を追加。上の
    # WIDGET_TYPES_V1_11_ADDITIONS のコメントに理由を書いてある。
    "1.11": (
        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS
        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS
        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS
    ),
    # v1.12(FORGE-R1-CLOSURE-015、2026-08-17)は**Widget型を増やさない**。
    # `metric_view`へ絞り込み(filter_*)と符号付け(sign_*)を足しただけの
    # property-onlyな追加である(v1.2/v1.5/v1.9と同じ形)。
    #
    # 足したのは表示できるものの種類ではなく、**お金の出入りという意味**
    # を表せるかどうかである。それまで「金額の合計」までしか言えず、
    # 家計簿の利用者が一番知りたい「今いくら残っているか」に答えられて
    # いなかった。
    "1.12": (
        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS
        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS
        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS
    ),
}
WIDGET_TYPES_ALL = (
    WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS
    | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS
    | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS
)  # 未知Widget判定用

# `tab_view`はchildren[i]が「1タブ分の中身」に対応する、column/row/card/
# formと同じ「フラットなchildren配列を持つコンテナ」として設計した
# (`_walk_widgets`・`_widget_depth`等の既存の再帰処理をそのまま再利用
# できるようにするため。詳細はWIDGET_TYPES_V1_7_ADDITIONSのコメント参照)。
CONTAINER_WIDGET_TYPES = {"column", "row", "card", "form", "tab_view"}

# v1.0/v1.1で確定していた4種
ACTION_TYPES_V1_0 = {"navigate", "go_back", "set_value", "add_item"}
# v1.2で追加された5種
ACTION_TYPES_V1_2_ADDITIONS = {"set_state", "toggle_state", "reset_state", "submit_form", "composite"}
# v1.3で追加された4種。`add_record`はFORGE v0.7(Phase1)、
# `select_record`/`update_record`/`delete_record`はFORGE v0.8(Phase2)で追加
# (指示書「Versionは1.3のまま維持」に従い、新しいVersion階層は作らない)。
ACTION_TYPES_V1_3_ADDITIONS = {"add_record", "select_record", "update_record", "delete_record"}

ACTION_TYPES_BY_VERSION: dict[str, set[str]] = {
    "1.0": ACTION_TYPES_V1_0,
    "1.1": ACTION_TYPES_V1_0,
    "1.2": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS,
    "1.3": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    # FORGE v0.9。record_schema導入は新しいAction型を追加しない。
    "1.4": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    # FORGE v1.0 Product Quality Sprint1。design_tokens/section_header
    # 導入は新しいAction型を追加しない。
    "1.5": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    # v1.6。choice_field/bar_chart追加は新しいAction型を追加しない
    # (choice_fieldはtext_fieldと同様set_value等の既存Actionで操作する)。
    "1.6": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    # v1.7。date_field/tab_view追加は新しいAction型を追加しない
    # (date_fieldは既存の"string"型state、tab_viewはAction自体を持たない
    # 表示専用コンテナ)。
    "1.7": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    # v1.8。slider追加は新しいAction型を追加しない。
    "1.8": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    # v1.9はActionを追加しない(足したのはデータ変換であり操作ではない)。
    "1.9": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    # v1.10もActionを追加しない(足したのは意味付けであり操作ではない)。
    "1.10": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    # v1.11。metric_viewは表示専用なので新しいAction型を追加しない。
    "1.11": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
    "1.12": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,
}
ACTION_TYPES = ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS  # 全バージョン合計(未知typeの判定用)

# v1.0/v1.1で確定していた4型
STATE_TYPES_V1_0 = {"string", "boolean", "string_list", "checklist"}
# v1.2で追加
STATE_TYPES_V1_2_ADDITIONS = {"number"}
# v1.3で追加。`record_list`はFORGE v0.7(Phase1)、`selected_record`は
# FORGE v0.8(Phase2)で追加。
STATE_TYPES_V1_3_ADDITIONS = {"record_list", "selected_record"}

STATE_TYPES_BY_VERSION: dict[str, set[str]] = {
    "1.0": STATE_TYPES_V1_0,
    "1.1": STATE_TYPES_V1_0,
    "1.2": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS,
    "1.3": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    # FORGE v0.9。record_schema導入は新しいState型を追加しない
    # (`record_list`へ`schema_ref`プロパティが増えるだけ)。
    "1.4": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    # FORGE v1.0 Product Quality Sprint1。design_tokens/section_header
    # 導入は新しいState型を追加しない。
    "1.5": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    # v1.6。choice_field/bar_chart追加は新しいState型を追加しない
    # (choice_fieldは既存の"string"、bar_chartは既存の"record_list"を参照する)。
    "1.6": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    # v1.7。date_field/tab_view追加は新しいState型を追加しない。
    "1.7": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    # v1.8。sliderは既存の"number"型state(v1.2で追加済み)をそのまま
    # 使うため、新しいState型を追加しない。
    "1.8": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    # v1.9はState型を追加しない。集計結果は**保存しない**——表示のたびに
    # 導出する純粋関数であり、保存されるデータは1バイトも増えない。
    "1.9": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    # v1.10もState型を追加しない。意味的役割は**表示の解釈**であって、
    # 保存されるデータではない。
    "1.10": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    # v1.11。metric_viewは既存の"record_list"を参照するだけで、
    # 新しいState型を追加しない(bar_chartと同じ)。
    "1.11": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
    "1.12": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,
}
STATE_TYPES = STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS

# FORGE v0.9新規(Typed Record Runtime Phase1)。record_schemaの
# Fieldが取りうる型(指示書「Supported Types」)。
RECORD_SCHEMA_FIELD_TYPES = {"string", "number", "boolean", "date", "choice"}
MAX_RECORD_SCHEMA_FIELDS = 30  # 既存state.maxProperties: 30と揃える
MAX_RECORD_SCHEMAS = 20  # 1文書内で定義できるrecord_schemaの数の上限
MAX_CHOICE_OPTIONS = 30

# Record Fieldの値として許容する型(Phase1、record_schemas未実装のため
# 緩い型検査のみ: 文字列・数値・真偽値。ネストしたobject/arrayは禁止する)。
RECORD_FIELD_VALUE_TYPES = (str, int, float, bool)

VALIDATION_RULE_TYPES = {"required", "min_length", "max_length", "min", "max", "pattern"}

# v1.9新規(2026-08-13)。`bar_chart.aggregate`が取りうる値。
# Runtime側(`frontend/lib/json_ui/runtime/forge_aggregate.dart`の
# `ForgeAggregateOp`)と**1:1で一致させること**——ここが食い違うと、
# Validatorは通るのにRuntimeが解釈できない文書が生まれる(TD37と同じ形の事故)。
BAR_CHART_AGGREGATES = {"count", "sum", "average"}

# `metric_view`(v1.11、Hero KPI)が受け付ける集計。**bar_chartより広い。**
#
# 単一の数値だからこそ意味を持つ集計がある——「一番大きかったのは」
# (max)、「今いくつか」(latest)は、1つの値だから答えになる。棒グラフの
# ように複数並べる文脈では、これらは別の問いになるので広げない。
#
# 広げた理由(FORGE-R1-CLOSURE-015 §2): `MeasureSemantics`が
# `extremum`(サイズ・自己ベスト)と`level`(体温・残高)を区別できるように
# なったのに、出す先がsum/average/countしか無ければ、**語彙にあるのに
# 表現できない**状態を作ることになる(014で`metric.primary`に出力先が
# 無かったのと同じ失敗)。
METRIC_VIEW_AGGREGATES = BAR_CHART_AGGREGATES | {"max", "min", "latest"}

IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class Severity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"


class Category(str, Enum):
    SYNTAX = "syntax"
    SCHEMA = "schema"
    SEMANTIC = "semantic"
    RUNTIME_SAFETY = "runtime_safety"


@dataclass
class ValidationIssue:
    path: str
    category: Category
    severity: Severity
    rule: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category.value,
            "severity": self.severity.value,
            "rule": self.rule,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


def validate_forge_document_from_text(raw_text: str) -> ValidationResult:
    try:
        doc = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return ValidationResult(
            valid=False,
            errors=[
                ValidationIssue(
                    path="$", category=Category.SYNTAX, severity=Severity.BLOCKING,
                    rule="valid_json",
                    message=f"JSONとして解析できません: {exc.msg} (line {exc.lineno}, col {exc.colno})",
                )
            ],
        )
    return validate_forge_document(doc)


def validate_forge_document(doc: Any) -> ValidationResult:
    schema_errors = _check_schema(doc, "$")
    if schema_errors:
        return ValidationResult(valid=False, errors=schema_errors)

    version = doc["version"]
    allowed_widgets = WIDGET_TYPES_BY_VERSION[version]

    semantic_errors, semantic_warnings = _check_semantics(doc, allowed_widgets)
    safety_errors, safety_warnings = _check_runtime_safety(doc)

    errors = semantic_errors + safety_errors
    warnings = semantic_warnings + safety_warnings
    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


# ---------------------------------------------------------------------------
# レイヤー2: Schema
# ---------------------------------------------------------------------------

def _err(path: str, category: Category, rule: str, message: str, severity: Severity = Severity.BLOCKING) -> ValidationIssue:
    return ValidationIssue(path=path, category=category, severity=severity, rule=rule, message=message)


def _check_schema(doc: Any, path: str) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []

    if not isinstance(doc, dict):
        return [_err(path, Category.SCHEMA, "root_is_object", "ルートはobjectである必要があります。")]

    allowed_keys = {"version", "app", "initial_screen_id", "screens", "record_schemas", "design_tokens"}
    errors.extend(_check_additional_properties(doc, allowed_keys, path))

    version = doc.get("version")
    if version not in SUPPORTED_VERSIONS:
        errors.append(_err(f"{path}/version", Category.SCHEMA, "version_const",
                            f"version は {sorted(SUPPORTED_VERSIONS)} のいずれかである必要があります(実際: {version!r})。"))
        return errors

    if "record_schemas" in doc:
        # FORGE v0.9新規(Typed Record Runtime Phase1)。
        if not _version_at_least(version, "1.4"):
            errors.append(_err(f"{path}/record_schemas", Category.SCHEMA, "field_not_allowed_in_version",
                                "record_schemasはv1.4以降の文書でのみ使用できます。"))
        else:
            errors.extend(_check_record_schemas(doc["record_schemas"], f"{path}/record_schemas"))

    if "design_tokens" in doc:
        # FORGE v1.0 Product Quality Sprint1新規。Widget/Runtime固有の
        # 描画情報(色・角丸・余白)であり、IRへは持ち込まない
        # (ADR-012の方針を維持、Forge Language Compiler固有の情報)。
        if not _version_at_least(version, "1.5"):
            errors.append(_err(f"{path}/design_tokens", Category.SCHEMA, "field_not_allowed_in_version",
                                "design_tokensはv1.5以降の文書でのみ使用できます。"))
        else:
            errors.extend(_check_design_tokens(doc["design_tokens"], f"{path}/design_tokens"))

    if "app" in doc:
        app = doc["app"]
        if not isinstance(app, dict):
            errors.append(_err(f"{path}/app", Category.SCHEMA, "type", "app はobjectである必要があります。"))
        else:
            errors.extend(_check_additional_properties(app, {"title"}, f"{path}/app"))
            if "title" in app and not _is_nonempty_str(app["title"], 80):
                errors.append(_err(f"{path}/app/title", Category.SCHEMA, "string_length",
                                    "app.title は1〜80文字の文字列である必要があります。"))

    if not isinstance(doc.get("initial_screen_id"), str) or not doc.get("initial_screen_id"):
        errors.append(_err(f"{path}/initial_screen_id", Category.SCHEMA, "required",
                            "initial_screen_id は必須の非空文字列です。"))

    screens = doc.get("screens")
    if not isinstance(screens, list) or not (1 <= len(screens) <= MAX_SCREENS):
        errors.append(_err(f"{path}/screens", Category.SCHEMA, "array_bounds",
                            f"screens は要素数1〜{MAX_SCREENS}の配列である必要があります。"))
    else:
        allowed_widgets = WIDGET_TYPES_BY_VERSION[version]
        for i, screen in enumerate(screens):
            errors.extend(_check_screen_schema(screen, f"{path}/screens/{i}", allowed_widgets, version))

    return errors


def _check_screen_schema(screen: Any, path: str, allowed_widgets: set[str], version: str) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    if not isinstance(screen, dict):
        return [_err(path, Category.SCHEMA, "type", "screen はobjectである必要があります。")]

    errors.extend(_check_additional_properties(screen, {"id", "title", "state", "body"}, path))

    if not _is_identifier(screen.get("id")):
        errors.append(_err(f"{path}/id", Category.SCHEMA, "identifier_format", "screen.idが不正です。"))
    if not _is_nonempty_str(screen.get("title"), 80):
        errors.append(_err(f"{path}/title", Category.SCHEMA, "string_length", "screen.titleは1〜80文字です。"))

    if "state" in screen:
        state = screen["state"]
        if not isinstance(state, dict) or len(state) > 30:
            errors.append(_err(f"{path}/state", Category.SCHEMA, "type", "stateは最大30項目のobjectです。"))
        else:
            for key, value in state.items():
                errors.extend(_check_state_value_schema(value, f"{path}/state/{key}", version))

    if "body" not in screen:
        errors.append(_err(f"{path}/body", Category.SCHEMA, "required", "screen.bodyは必須です。"))
    else:
        errors.extend(_check_widget_schema(screen["body"], f"{path}/body", allowed_widgets, version))

    return errors


def _check_state_value_schema(value: Any, path: str, version: str) -> list[ValidationIssue]:
    allowed_state_types = STATE_TYPES_BY_VERSION[version]
    if not isinstance(value, dict) or "type" not in value or value.get("type") not in STATE_TYPES:
        return [_err(path, Category.SCHEMA, "state_value_type",
                      f"stateの値は type が {sorted(STATE_TYPES)} のいずれかであるobjectである必要があります。")]

    t = value["type"]
    if t not in allowed_state_types:
        return [_err(f"{path}/type", Category.SCHEMA, "state_type_not_allowed_in_version",
                      f"State type '{t}' はこの文書のversionでは使用できません。")]

    errors: list[ValidationIssue] = []
    # FORGE v0.9新規: record_list型のみ、任意の`schema_ref`プロパティを
    # 許可する(v1.4未満の文書では使えない、下記で別途検査する)。
    allowed_value_keys = {"type", "value", "schema_ref"} if t == "record_list" else {"type", "value"}
    errors.extend(_check_additional_properties(value, allowed_value_keys, path))
    if "schema_ref" in value:
        if not _version_at_least(version, "1.4"):
            errors.append(_err(f"{path}/schema_ref", Category.SCHEMA, "field_not_allowed_in_version",
                                "schema_refはv1.4以降の文書でのみ使用できます。"))
        elif not _is_identifier(value["schema_ref"]):
            errors.append(_err(f"{path}/schema_ref", Category.SCHEMA, "identifier_format", "schema_refが不正です。"))
    if "value" not in value:
        return errors + [_err(path, Category.SCHEMA, "required", "state値には value が必須です。")]
    v = value["value"]

    if t == "string":
        if not isinstance(v, str) or len(v) > 2000:
            errors.append(_err(path, Category.SCHEMA, "type", "type=stringのvalueは2000文字以内の文字列です。"))
    elif t == "boolean":
        if not isinstance(v, bool):
            errors.append(_err(path, Category.SCHEMA, "type", "type=booleanのvalueは真偽値です。"))
    elif t == "number":
        # Python: bool は int のサブクラスなので明示的に除外する。
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            errors.append(_err(path, Category.SCHEMA, "type", "type=numberのvalueは数値です。"))
    elif t == "string_list":
        if not isinstance(v, list) or len(v) > MAX_STRING_LIST_ITEMS or not all(
            isinstance(item, str) and len(item) <= 500 for item in v
        ):
            errors.append(_err(path, Category.SCHEMA, "type",
                                f"type=string_listのvalueは各要素500文字以内・最大{MAX_STRING_LIST_ITEMS}件の配列です。"))
    elif t == "checklist":
        if not isinstance(v, list) or len(v) > MAX_CHECKLIST_ITEMS:
            errors.append(_err(path, Category.SCHEMA, "array_bounds",
                                f"type=checklistのvalueは最大{MAX_CHECKLIST_ITEMS}件の配列です。"))
        else:
            for i, item in enumerate(v):
                errors.extend(_check_checklist_item_schema(item, f"{path}/value/{i}"))
    elif t == "record_list":
        if not isinstance(v, list) or len(v) > MAX_RECORD_LIST_ITEMS:
            errors.append(_err(path, Category.SCHEMA, "array_bounds",
                                f"type=record_listのvalueは最大{MAX_RECORD_LIST_ITEMS}件の配列です。"))
        else:
            for i, item in enumerate(v):
                errors.extend(_check_record_item_schema(item, f"{path}/value/{i}"))
    elif t == "selected_record":
        # FORGE v0.8(Record Runtime Phase2)。無選択時は`null`、選択中は
        # record_list項目と同じ形({id, fields})を許容する。
        if v is not None:
            errors.extend(_check_record_item_schema(v, f"{path}/value"))
    return errors


_DESIGN_TOKEN_COLOR_ROLES = {"primary", "secondary", "success", "error", "background", "surface"}
_DESIGN_TOKEN_RADIUS_SIZES = {"small", "medium", "large"}
_DESIGN_TOKEN_SPACING_SIZES = {"xs", "sm", "md", "lg", "xl"}
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _check_design_tokens(design_tokens: Any, path: str) -> list[ValidationIssue]:
    """FORGE v1.0 Product Quality Sprint1新規。`design_tokens`
    (色・角丸・余白)の構造を検証する。record_schemasと同様、
    record_list等とは独立したトップレベルの任意ブロックであり、
    Widget/Runtime側の描画情報である(IRへは持ち込まない、ADR-012)。
    """
    if not isinstance(design_tokens, dict):
        return [_err(path, Category.SCHEMA, "type", "design_tokensはobjectである必要があります。")]

    errors = _check_additional_properties(
        design_tokens, {"color_scheme", "corner_radius", "spacing_scale"}, path
    )

    if "color_scheme" in design_tokens:
        color_scheme = design_tokens["color_scheme"]
        if not isinstance(color_scheme, dict) or "primary" not in color_scheme:
            errors.append(_err(f"{path}/color_scheme", Category.SCHEMA, "required",
                                "color_schemeはobjectであり、'primary'を含む必要があります。"))
        else:
            errors.extend(_check_additional_properties(
                color_scheme, _DESIGN_TOKEN_COLOR_ROLES, f"{path}/color_scheme"
            ))
            for role, value in color_scheme.items():
                if role in _DESIGN_TOKEN_COLOR_ROLES and (
                    not isinstance(value, str) or not _HEX_COLOR_PATTERN.match(value)
                ):
                    errors.append(_err(f"{path}/color_scheme/{role}", Category.SCHEMA, "color_format",
                                        f"色は'#RRGGBB'形式である必要があります(実際: {value!r})。"))

    if "corner_radius" in design_tokens:
        corner_radius = design_tokens["corner_radius"]
        if not isinstance(corner_radius, dict) or not corner_radius:
            errors.append(_err(f"{path}/corner_radius", Category.SCHEMA, "type",
                                "corner_radiusは1件以上を持つobjectである必要があります。"))
        else:
            errors.extend(_check_additional_properties(
                corner_radius, _DESIGN_TOKEN_RADIUS_SIZES, f"{path}/corner_radius"
            ))
            for size, value in corner_radius.items():
                if size in _DESIGN_TOKEN_RADIUS_SIZES and (not isinstance(value, (int, float)) or value < 0):
                    errors.append(_err(f"{path}/corner_radius/{size}", Category.SCHEMA, "type",
                                        "corner_radiusの値は0以上の数値である必要があります。"))

    if "spacing_scale" in design_tokens:
        spacing_scale = design_tokens["spacing_scale"]
        if not isinstance(spacing_scale, dict) or not spacing_scale:
            errors.append(_err(f"{path}/spacing_scale", Category.SCHEMA, "type",
                                "spacing_scaleは1件以上を持つobjectである必要があります。"))
        else:
            errors.extend(_check_additional_properties(
                spacing_scale, _DESIGN_TOKEN_SPACING_SIZES, f"{path}/spacing_scale"
            ))
            for size, value in spacing_scale.items():
                if size in _DESIGN_TOKEN_SPACING_SIZES and (not isinstance(value, (int, float)) or value < 0):
                    errors.append(_err(f"{path}/spacing_scale/{size}", Category.SCHEMA, "type",
                                        "spacing_scaleの値は0以上の数値である必要があります。"))

    return errors


def _check_record_schemas(record_schemas: Any, path: str) -> list[ValidationIssue]:
    """FORGE v0.9新規(Typed Record Runtime Phase1)。文書トップレベルの
    `record_schemas`(Schema名 → {fields: [...]})を検査する。
    `record_list`とは独立した定義であり(指示書の要求)、ここでの検証は
    `record_list`側の実際のデータとは突き合わせない(record_listの
    schema_refが指す先が存在するかは、別途セマンティック層で検査する、
    `_check_semantics`参照)。
    """
    if not isinstance(record_schemas, dict) or len(record_schemas) > MAX_RECORD_SCHEMAS:
        return [_err(path, Category.SCHEMA, "type",
                      f"record_schemasは最大{MAX_RECORD_SCHEMAS}件のobjectである必要があります。")]
    errors: list[ValidationIssue] = []
    for schema_name, schema_def in record_schemas.items():
        schema_path = f"{path}/{schema_name}"
        if not _is_identifier(schema_name):
            errors.append(_err(schema_path, Category.SCHEMA, "identifier_format",
                                f"record_schema名 '{schema_name}' が不正です。"))
        if not isinstance(schema_def, dict):
            errors.append(_err(schema_path, Category.SCHEMA, "type", "record_schemaはobjectである必要があります。"))
            continue
        errors.extend(_check_additional_properties(schema_def, {"fields"}, schema_path))
        fields = schema_def.get("fields")
        if not isinstance(fields, list) or not (1 <= len(fields) <= MAX_RECORD_SCHEMA_FIELDS):
            errors.append(_err(f"{schema_path}/fields", Category.SCHEMA, "array_bounds",
                                f"fieldsは要素数1〜{MAX_RECORD_SCHEMA_FIELDS}の配列である必要があります。"))
            continue
        field_names: set[str] = set()
        for i, field_def in enumerate(fields):
            field_path = f"{schema_path}/fields/{i}"
            errors.extend(_check_record_schema_field(field_def, field_path))
            if isinstance(field_def, dict) and _is_identifier(field_def.get("name")):
                name = field_def["name"]
                if name in field_names:
                    errors.append(_err(field_path, Category.SCHEMA, "duplicate_field_name",
                                        f"Field名 '{name}' がこのSchema内で重複しています。"))
                field_names.add(name)
    return errors


def _check_record_schema_field(field_def: Any, path: str) -> list[ValidationIssue]:
    """`record_schemas.<name>.fields`の1要素を検査する(指示書
    「Supported Types」: string/number/boolean/date/choiceのみ)。"""
    if not isinstance(field_def, dict):
        return [_err(path, Category.SCHEMA, "type", "Field定義はobjectである必要があります。")]

    allowed_keys = {"name", "type", "label", "required", "options"}
    errors = _check_additional_properties(field_def, allowed_keys, path)

    if not _is_identifier(field_def.get("name")):
        errors.append(_err(f"{path}/name", Category.SCHEMA, "identifier_format", "Field名が不正です。"))

    field_type = field_def.get("type")
    if field_type not in RECORD_SCHEMA_FIELD_TYPES:
        errors.append(_err(f"{path}/type", Category.SCHEMA, "enum",
                            f"typeは{sorted(RECORD_SCHEMA_FIELD_TYPES)}のいずれかである必要があります(実際: {field_type!r})。"))

    if not _is_nonempty_str(field_def.get("label"), 80):
        errors.append(_err(f"{path}/label", Category.SCHEMA, "string_length", "labelは1〜80文字の文字列です。"))

    if "required" in field_def and not isinstance(field_def["required"], bool):
        errors.append(_err(f"{path}/required", Category.SCHEMA, "type", "requiredは真偽値である必要があります。"))

    if field_type == "choice":
        options = field_def.get("options")
        if not isinstance(options, list) or not (1 <= len(options) <= MAX_CHOICE_OPTIONS) or not all(
            isinstance(o, str) and o for o in options
        ):
            errors.append(_err(f"{path}/options", Category.SCHEMA, "array_bounds",
                                f"type=choiceの場合、optionsは要素数1〜{MAX_CHOICE_OPTIONS}の非空文字列配列が必須です。"))
    elif "options" in field_def:
        errors.append(_err(f"{path}/options", Category.SCHEMA, "field_not_applicable",
                            "optionsはtype=choiceの場合のみ使用できます。"))

    return errors


def _check_checklist_item_schema(item: Any, path: str) -> list[ValidationIssue]:
    if not isinstance(item, dict):
        return [_err(path, Category.SCHEMA, "type", "checklist項目はobjectである必要があります。")]
    errors = _check_additional_properties(item, {"id", "text", "done"}, path)
    if not _is_identifier(item.get("id")):
        errors.append(_err(f"{path}/id", Category.SCHEMA, "identifier_format", "checklist項目のidが不正です。"))
    if not _is_nonempty_str(item.get("text"), 500):
        errors.append(_err(f"{path}/text", Category.SCHEMA, "string_length", "checklist項目のtextが不正です。"))
    if not isinstance(item.get("done"), bool):
        errors.append(_err(f"{path}/done", Category.SCHEMA, "type", "checklist項目のdoneは真偽値です。"))
    return errors


def _check_record_item_schema(item: Any, path: str) -> list[ValidationIssue]:
    """FORGE v0.7(Record Runtime Phase1)。`record_list`の1件を検査する。

    **既知の制限(Phase1、指示書の制約により意図的)**: `record_schemas`
    (Field名・型の宣言)はまだ導入していないため、`fields`の各値は
    「文字列・数値・真偽値のいずれか」という緩い型検査のみを行う
    (宣言されたSchemaとの突き合わせ、必須Field欠落検査は行わない)。
    """
    if not isinstance(item, dict):
        return [_err(path, Category.SCHEMA, "type", "record項目はobjectである必要があります。")]
    errors = _check_additional_properties(item, {"id", "fields"}, path)
    if not _is_identifier(item.get("id")):
        errors.append(_err(f"{path}/id", Category.SCHEMA, "identifier_format", "record項目のidが不正です。"))

    fields_value = item.get("fields")
    if not isinstance(fields_value, dict) or len(fields_value) > MAX_RECORD_FIELDS:
        errors.append(_err(f"{path}/fields", Category.SCHEMA, "type",
                            f"record項目のfieldsは最大{MAX_RECORD_FIELDS}件のobjectである必要があります。"))
        return errors

    for field_name, field_value in fields_value.items():
        if not _is_identifier(field_name):
            errors.append(_err(f"{path}/fields/{field_name}", Category.SCHEMA, "identifier_format",
                                f"Field名 '{field_name}' が不正です。"))
        # bool は int のサブクラスなので、isinstance(v, RECORD_FIELD_VALUE_TYPES)は
        # bool/int/float/strの全てを正しく受理する(意図した挙動)。
        if not isinstance(field_value, RECORD_FIELD_VALUE_TYPES):
            errors.append(_err(f"{path}/fields/{field_name}", Category.SCHEMA, "type",
                                f"Field '{field_name}' の値は文字列・数値・真偽値のいずれかである必要があります。"))
        elif isinstance(field_value, str) and len(field_value) > 2000:
            errors.append(_err(f"{path}/fields/{field_name}", Category.SCHEMA, "string_length",
                                f"Field '{field_name}' の文字列値が長すぎます(2000文字以内)。"))
    return errors


def _check_validation_schema(validation: Any, path: str) -> list[ValidationIssue]:
    if not isinstance(validation, dict):
        return [_err(path, Category.SCHEMA, "type", "validationはobjectである必要があります。")]
    errors = _check_additional_properties(validation, {"rules"}, path)
    rules = validation.get("rules")
    if not isinstance(rules, list) or not (1 <= len(rules) <= 10):
        errors.append(_err(f"{path}/rules", Category.SCHEMA, "array_bounds", "rulesは要素数1〜10の配列です。"))
        return errors
    for i, rule in enumerate(rules):
        errors.extend(_check_validation_rule_schema(rule, f"{path}/rules/{i}"))
    return errors


def _check_validation_rule_schema(rule: Any, path: str) -> list[ValidationIssue]:
    if not isinstance(rule, dict) or "type" not in rule:
        return [_err(path, Category.SCHEMA, "validation_rule_type_missing", "validation ruleにはtypeが必須です。")]
    t = rule.get("type")
    if t not in VALIDATION_RULE_TYPES:
        return [_err(f"{path}/type", Category.SCHEMA, "unknown_validation_rule",
                      f"未知のvalidation rule type '{t}' です。許可: {sorted(VALIDATION_RULE_TYPES)}")]
    errors = _check_additional_properties(rule, {"type", "value", "message"}, path)
    if not _is_nonempty_str(rule.get("message"), 200):
        errors.append(_err(f"{path}/message", Category.SCHEMA, "required", "validation ruleのmessageは必須です。"))
    if t in {"min_length", "max_length", "min", "max"}:
        if "value" not in rule or isinstance(rule["value"], bool) or not isinstance(rule["value"], (int, float)):
            errors.append(_err(f"{path}/value", Category.SCHEMA, "required", f"{t}にはnumeric valueが必須です。"))
    elif t == "pattern":
        if not isinstance(rule.get("value"), str):
            errors.append(_err(f"{path}/value", Category.SCHEMA, "required", "patternには文字列valueが必須です。"))
        else:
            try:
                re.compile(rule["value"])
            except re.error as exc:
                errors.append(_err(f"{path}/value", Category.SCHEMA, "invalid_regex", f"不正な正規表現です: {exc}"))
    elif t == "required" and "value" in rule:
        errors.append(_err(f"{path}/value", Category.SCHEMA, "additional_properties",
                            "requiredはvalueを取りません。"))
    return errors


def _check_widget_schema(widget: Any, path: str, allowed_widgets: set[str], version: str) -> list[ValidationIssue]:
    if not isinstance(widget, dict) or "type" not in widget:
        return [_err(path, Category.SCHEMA, "widget_type_missing", "widgetにはtypeが必須です。")]

    t = widget.get("type")
    if t not in WIDGET_TYPES_ALL:
        return [_err(f"{path}/type", Category.SCHEMA, "unknown_widget", f"未知のWidget type '{t}' です。")]
    if t not in allowed_widgets:
        return [_err(f"{path}/type", Category.SCHEMA, "widget_not_allowed_in_version",
                      f"Widget type '{t}' はこの文書のversionでは使用できません。")]

    errors: list[ValidationIssue] = []
    if not _is_identifier(widget.get("id")):
        errors.append(_err(f"{path}/id", Category.SCHEMA, "identifier_format", "widget.idが不正です。"))

    # --- style_role(v1.10、Design Language)-------------------------------
    #
    # **全Widget共通の任意キー**である。ここ1箇所で検査し、以降の
    # type別チェックへは`style_role`を除いたdictを渡す。
    #
    # なぜ1箇所か: type別の`allowed_keys`へ個別に足すと、**Widgetを
    # 1つ追加するたびに足し忘れる**。20種すべてに同じキーを配るのは、
    # Forgeが4回繰り返した「呼び出し側が忘れずにやる」設計そのもの
    # である(`CLAUDE.md` §3)。
    if "style_role" in widget:
        if not _version_at_least(version, "1.10"):
            errors.append(_err(f"{path}/style_role", Category.SCHEMA, "field_not_allowed_in_version",
                                "style_roleはv1.10以降の文書でのみ使用できます。"))
        elif not is_known_role(widget["style_role"]):
            # **未知のroleは通さない。** 自由に増やせると、Runtimeが
            # 保証できない値が入り、「AIは意味を選ぶ / Forgeが品質を
            # 保証する」という分担が崩れる。
            errors.append(_err(f"{path}/style_role", Category.SCHEMA, "unknown_style_role",
                                "style_roleはDesign Languageの語彙である必要があります"
                                f"(実際: {str(widget['style_role'])[:40]!r})。"))
        widget = {k: v for k, v in widget.items() if k != "style_role"}

    if t == "text":
        errors.extend(_check_additional_properties(widget, {"type", "id", "value", "state_ref", "style"}, path))
        if not isinstance(widget.get("value"), str) or len(widget["value"]) > 500:
            errors.append(_err(f"{path}/value", Category.SCHEMA, "string_length", "text.valueが不正です。"))
        if "state_ref" in widget and not _is_identifier(widget["state_ref"]):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "identifier_format", "state_refが不正です。"))
        if "style" in widget and widget["style"] not in {"title", "body", "caption"}:
            errors.append(_err(f"{path}/style", Category.SCHEMA, "enum", "styleが不正です。"))

    elif t == "text_field":
        allowed_keys = {"type", "id", "placeholder", "state_ref"}
        if _version_at_least(version, "1.2"):
            allowed_keys = allowed_keys | {"validation"}
        errors.extend(_check_additional_properties(widget, allowed_keys, path))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "text_field.state_refは必須です。"))
        if "placeholder" in widget and (not isinstance(widget["placeholder"], str) or len(widget["placeholder"]) > 80):
            errors.append(_err(f"{path}/placeholder", Category.SCHEMA, "string_length", "placeholderが不正です。"))
        if "validation" in widget:
            errors.extend(_check_validation_schema(widget["validation"], f"{path}/validation"))

    elif t == "button":
        errors.extend(_check_additional_properties(widget, {"type", "id", "label", "action"}, path))
        if not _is_nonempty_str(widget.get("label"), 40):
            errors.append(_err(f"{path}/label", Category.SCHEMA, "string_length", "button.labelが不正です。"))
        if "action" not in widget:
            errors.append(_err(f"{path}/action", Category.SCHEMA, "required", "button.actionは必須です。"))
        else:
            errors.extend(_check_action_schema(widget["action"], f"{path}/action", version, depth=0))

    elif t in {"column", "row"}:
        errors.extend(_check_additional_properties(widget, {"type", "id", "children"}, path))
        children = widget.get("children")
        max_children = 60 if t == "column" else 20
        if not isinstance(children, list) or len(children) > max_children:
            errors.append(_err(f"{path}/children", Category.SCHEMA, "array_bounds", f"{t}.childrenが不正です。"))
        else:
            for i, child in enumerate(children):
                errors.extend(_check_widget_schema(child, f"{path}/children/{i}", allowed_widgets, version))

    elif t == "checklist":
        errors.extend(_check_additional_properties(widget, {"type", "id", "state_ref", "empty_state_text"}, path))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "checklist.state_refは必須です。"))
        if "empty_state_text" in widget and (
            not isinstance(widget["empty_state_text"], str) or len(widget["empty_state_text"]) > 80
        ):
            errors.append(_err(f"{path}/empty_state_text", Category.SCHEMA, "string_length", "empty_state_textが不正です。"))

    elif t == "heading":
        errors.extend(_check_additional_properties(widget, {"type", "id", "value", "level"}, path))
        if not _is_nonempty_str(widget.get("value"), 80):
            errors.append(_err(f"{path}/value", Category.SCHEMA, "string_length", "heading.valueが不正です。"))
        if "level" in widget and widget["level"] not in (1, 2):
            errors.append(_err(f"{path}/level", Category.SCHEMA, "enum", "levelは1または2です。"))

    elif t == "checkbox":
        allowed_keys = {"type", "id", "label", "state_ref"}
        if _version_at_least(version, "1.2"):
            allowed_keys = allowed_keys | {"validation"}
        errors.extend(_check_additional_properties(widget, allowed_keys, path))
        if not _is_nonempty_str(widget.get("label"), 120):
            errors.append(_err(f"{path}/label", Category.SCHEMA, "string_length", "checkbox.labelが不正です。"))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "checkbox.state_refは必須です。"))
        if "validation" in widget:
            errors.extend(_check_validation_schema(widget["validation"], f"{path}/validation"))

    elif t == "card":
        errors.extend(_check_additional_properties(widget, {"type", "id", "children"}, path))
        children = widget.get("children")
        if not isinstance(children, list) or not (1 <= len(children) <= 20):
            errors.append(_err(f"{path}/children", Category.SCHEMA, "array_bounds",
                                "card.childrenは要素数1〜20の配列です。"))
        else:
            for i, child in enumerate(children):
                errors.extend(_check_widget_schema(child, f"{path}/children/{i}", allowed_widgets, version))

    elif t == "list":
        errors.extend(_check_additional_properties(widget, {"type", "id", "state_ref", "empty_state_text"}, path))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "list.state_refは必須です。"))
        if "empty_state_text" in widget and (
            not isinstance(widget["empty_state_text"], str) or len(widget["empty_state_text"]) > 80
        ):
            errors.append(_err(f"{path}/empty_state_text", Category.SCHEMA, "string_length", "empty_state_textが不正です。"))

    elif t == "record_list_view":
        # FORGE v0.7(Record Runtime Phase1)。`layout`は将来`"table"`を
        # 追加する前提でプロパティ自体は用意するが、Phase1では"card"のみ
        # 許可する(指示書の制約: tableは実装しない)。
        #
        # FORGE v0.8(Record Runtime Phase2)対応: `selectable`/
        # `selected_state_ref`/`select_field_bindings`を追加した。
        # `record_list_view`自体はWidget型としては据え置き(新しい
        # Widget型は追加しない)、プロパティ拡張のみで選択・編集・削除の
        # 有効化を表現する(責務分離: 「一覧表示」というWidgetの役割は
        # 変えず、選択可能かどうかは任意プロパティとして重ねる)。
        errors.extend(_check_additional_properties(
            widget,
            {
                "type", "id", "state_ref", "empty_state_text", "layout", "display_fields",
                "selectable", "selected_state_ref", "select_field_bindings",
            },
            path,
        ))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "record_list_view.state_refは必須です。"))
        if "empty_state_text" in widget and (
            not isinstance(widget["empty_state_text"], str) or len(widget["empty_state_text"]) > 80
        ):
            errors.append(_err(f"{path}/empty_state_text", Category.SCHEMA, "string_length", "empty_state_textが不正です。"))
        if "layout" in widget:
            allowed_layouts = {"card", "grid"} if _version_at_least(version, "1.5") else {"card"}
            if widget["layout"] not in allowed_layouts:
                errors.append(_err(f"{path}/layout", Category.SCHEMA, "enum",
                                    f"layoutは{sorted(allowed_layouts)}のいずれかである必要があります"
                                    "(tableは未実装)。"))
        if "display_fields" in widget:
            display_fields = widget["display_fields"]
            if not isinstance(display_fields, list) or not (1 <= len(display_fields) <= MAX_RECORD_FIELDS) or not all(
                _is_identifier(f) for f in display_fields
            ):
                errors.append(_err(f"{path}/display_fields", Category.SCHEMA, "array_bounds",
                                    f"display_fieldsは要素数1〜{MAX_RECORD_FIELDS}のFieldName配列です。"))
        if "selectable" in widget and not isinstance(widget["selectable"], bool):
            errors.append(_err(f"{path}/selectable", Category.SCHEMA, "type", "selectableは真偽値である必要があります。"))
        if widget.get("selectable") is True and not _is_identifier(widget.get("selected_state_ref")):
            errors.append(_err(f"{path}/selected_state_ref", Category.SCHEMA, "required",
                                "selectable=trueの場合、selected_state_refが必須です。"))
        if "selected_state_ref" in widget and not _is_identifier(widget["selected_state_ref"]):
            errors.append(_err(f"{path}/selected_state_ref", Category.SCHEMA, "identifier_format",
                                "selected_state_refが不正です。"))
        if "select_field_bindings" in widget:
            bindings = widget["select_field_bindings"]
            if not isinstance(bindings, dict) or not (1 <= len(bindings) <= MAX_FIELD_BINDINGS):
                errors.append(_err(f"{path}/select_field_bindings", Category.SCHEMA, "array_bounds",
                                    f"select_field_bindingsは要素数1〜{MAX_FIELD_BINDINGS}のobjectである必要があります。"))
            else:
                for field_name, source_ref in bindings.items():
                    if not _is_identifier(field_name) or not _is_identifier(source_ref):
                        errors.append(_err(f"{path}/select_field_bindings/{field_name}", Category.SCHEMA,
                                            "identifier_format", f"select_field_bindingsの'{field_name}'が不正です。"))

    elif t == "divider":
        errors.extend(_check_additional_properties(widget, {"type", "id"}, path))

    elif t == "section_header":
        # FORGE v1.0 Product Quality Sprint1新規。単一画面内に視覚的な
        # 階層(「入力」「一覧」「編集」等のセクション区切り)を持たせる
        # ための、状態を持たない表示専用Widget(指示書「Rich Card /
        # Section / Grid表現」への対応)。
        errors.extend(_check_additional_properties(widget, {"type", "id", "title", "subtitle"}, path))
        if not _is_nonempty_str(widget.get("title"), 80):
            errors.append(_err(f"{path}/title", Category.SCHEMA, "string_length",
                                "section_header.titleは1〜80文字の文字列である必要があります。"))
        if "subtitle" in widget and (
            not isinstance(widget["subtitle"], str) or len(widget["subtitle"]) > 120
        ):
            errors.append(_err(f"{path}/subtitle", Category.SCHEMA, "string_length",
                                "subtitleは120文字以内の文字列である必要があります。"))

    elif t == "form":
        errors.extend(_check_additional_properties(
            widget, {"type", "id", "children", "submit_label", "submit_action"}, path
        ))
        children = widget.get("children")
        if not isinstance(children, list) or not (1 <= len(children) <= 30):
            errors.append(_err(f"{path}/children", Category.SCHEMA, "array_bounds",
                                "form.childrenは要素数1〜30の配列です。"))
        else:
            for i, child in enumerate(children):
                errors.extend(_check_widget_schema(child, f"{path}/children/{i}", allowed_widgets, version))
        if not _is_nonempty_str(widget.get("submit_label"), 40):
            errors.append(_err(f"{path}/submit_label", Category.SCHEMA, "string_length", "submit_labelが不正です。"))
        if "submit_action" not in widget:
            errors.append(_err(f"{path}/submit_action", Category.SCHEMA, "required", "form.submit_actionは必須です。"))
        else:
            errors.extend(_check_action_schema(widget["submit_action"], f"{path}/submit_action", version, depth=0))

    elif t == "choice_field":
        # v1.6新規(CEO承認によりForge Language Freeze運用解除、詳細は
        # WIDGET_TYPES_V1_6_ADDITIONSのコメント参照)。決まった選択肢から
        # 1つを選ばせる入力。TD33で`text_field`のplaceholderへ選択肢を
        # 埋め込む応急処置をしていたが、本来必要なのはユーザーが自由文字列を
        # 打鍵できない(=誤入力自体が構造的に起こらない)入力手段であり、
        # `text_field`の亜種ではなく独立したWidget型として追加する。
        errors.extend(_check_additional_properties(
            widget, {"type", "id", "label", "state_ref", "options", "placeholder"}, path
        ))
        if not _is_nonempty_str(widget.get("label"), 80):
            errors.append(_err(f"{path}/label", Category.SCHEMA, "string_length", "choice_field.labelが不正です。"))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "choice_field.state_refは必須です。"))
        options = widget.get("options")
        if not isinstance(options, list) or not (1 <= len(options) <= 20) or not all(
            _is_nonempty_str(o, 40) for o in options
        ):
            errors.append(_err(f"{path}/options", Category.SCHEMA, "array_bounds",
                                "choice_field.optionsは要素数1〜20の、各要素が1〜40文字の文字列である配列です。"))
        elif len(set(options)) != len(options):
            errors.append(_err(f"{path}/options", Category.SCHEMA, "array_uniqueness",
                                "choice_field.optionsに重複した選択肢があります。"))
        if "placeholder" in widget and (not isinstance(widget["placeholder"], str) or len(widget["placeholder"]) > 80):
            errors.append(_err(f"{path}/placeholder", Category.SCHEMA, "string_length", "placeholderが不正です。"))

    elif t == "bar_chart":
        # v1.6新規。record_listの数値Fieldを棒グラフで可視化する
        # (指示書の制約により、月ごとの合計等の集計は行わないPhase1の
        # 最小実装: 1 Record = 1本の棒)。household_budget等の「収支を
        # グラフで見たい」という既存の例文を実現するための追加。
        # v1.9(2026-08-13)で`group_by`/`aggregate`を追加。指定すると
        # 1 Record = 1本ではなく**グループごとに1本**になる。
        errors.extend(_check_additional_properties(
            widget,
            {"type", "id", "state_ref", "value_field", "label_field", "title",
             "group_by", "aggregate"},
            path,
        ))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "bar_chart.state_refは必須です。"))

        grouping = widget.get("group_by")
        if grouping is not None and not _is_identifier(grouping):
            errors.append(_err(
                f"{path}/group_by", Category.SCHEMA, "identifier",
                "bar_chart.group_byはField名でなければなりません。",
            ))
        aggregate = widget.get("aggregate")
        if aggregate is not None and aggregate not in BAR_CHART_AGGREGATES:
            errors.append(_err(
                f"{path}/aggregate", Category.SCHEMA, "enum",
                f"bar_chart.aggregateは{sorted(BAR_CHART_AGGREGATES)}のいずれかです。",
            ))
        if aggregate is not None and grouping is None:
            # 集計方法だけ指定してグループ化キーが無いのは、ほぼ確実に
            # 書き間違いである。黙って「集計しない」に倒すと、利用者は
            # 指定が効いていないことに気づけない。
            errors.append(_err(
                f"{path}/aggregate", Category.SCHEMA, "required",
                "bar_chart.aggregateを指定する場合、group_byも必要です。",
            ))

        # **要求を緩める範囲を正確に限定する**。集計する場合:
        #   * `value_field`は sum/average のときだけ必要(countは数えるだけ)
        #   * `label_field`は不要(グループ化キーがラベルになる)
        aggregating = grouping is not None
        needs_value_field = (not aggregating) or (aggregate or "count") != "count"
        if needs_value_field and not _is_identifier(widget.get("value_field")):
            errors.append(_err(f"{path}/value_field", Category.SCHEMA, "required", "bar_chart.value_fieldは必須です。"))
        if not aggregating and not _is_identifier(widget.get("label_field")):
            errors.append(_err(f"{path}/label_field", Category.SCHEMA, "required", "bar_chart.label_fieldは必須です。"))
        if "title" in widget and (not isinstance(widget["title"], str) or len(widget["title"]) > 80):
            errors.append(_err(f"{path}/title", Category.SCHEMA, "string_length", "titleが不正です。"))

    elif t == "metric_view":
        # v1.11新規(FORGE-R1、TD69)。record_listを**1つの数値へ畳んで**
        # 大きく見せる。`bar_chart`との違いは**グループ化しない**こと
        # ——常に値が1つになる。それが「画面で最も重要な単一のKPI」
        # (`metric.primary`)という意味に対応する。
        #
        # `group_by`を敢えて受け付けない。受け付ければ「グループが複数
        # あるのに数値は1つ」という表示できない文書が作れてしまう。
        # 複数の値を並べたいなら`bar_chart`が既にある。
        errors.extend(_check_additional_properties(
            widget,
            {"type", "id", "state_ref", "value_field", "aggregate", "label", "unit", "empty_text",
             # v1.12(FORGE-R1-CLOSURE-015 §2.3)。お金の出入りを表すため
             # の2つの仕組み。**どちらもRecordの絞り込み/符号付けであって、
             # 新しい集計方法ではない**。
             #
             #   filter_field/filter_value : 収入だけ・支出だけを合計する
             #   sign_field/negative_when  : 支出を負として合計する(=残高)
             #
             # これが無いと「金額の合計」までしか言えず、家計簿の利用者が
             # 一番知りたい「今いくら残っているか」に答えられない。
             "filter_field", "filter_value", "sign_field", "negative_when"},
            path,
        ))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "metric_view.state_refは必須です。"))

        aggregate = widget.get("aggregate")
        if aggregate is not None and aggregate not in METRIC_VIEW_AGGREGATES:
            errors.append(_err(
                f"{path}/aggregate", Category.SCHEMA, "enum",
                f"metric_view.aggregateは{sorted(METRIC_VIEW_AGGREGATES)}のいずれかです。",
            ))
        # `count`は数えるだけなので値Fieldが要らない。sum/averageは要る。
        # 既定を`count`にしてあるのは、**Fieldが無くても必ず成立する側**
        # だからである(`CLAUDE.md` §3「分からないものを楽観側へ倒さない」)。
        if (aggregate or "count") != "count" and not _is_identifier(widget.get("value_field")):
            errors.append(_err(
                f"{path}/value_field", Category.SCHEMA, "required",
                "metric_view.value_fieldは、aggregateがsum/averageのとき必須です。",
            ))
        for key, limit in (("label", 40), ("unit", 8), ("empty_text", 40),
                           ("filter_value", 40), ("negative_when", 40)):
            if key in widget and (not isinstance(widget[key], str) or len(widget[key]) > limit):
                errors.append(_err(f"{path}/{key}", Category.SCHEMA, "string_length",
                                    f"metric_view.{key}は{limit}文字以内の文字列です。"))
        for field_key, value_key in (("filter_field", "filter_value"),
                                     ("sign_field", "negative_when")):
            if (field_key in widget or value_key in widget) and not _version_at_least(version, "1.12"):
                errors.append(_err(
                    f"{path}/{field_key}", Category.SCHEMA, "field_not_allowed_in_version",
                    f"metric_view.{field_key}はv1.12以降の文書でのみ使用できます。",
                ))
            if field_key in widget and not _is_identifier(widget.get(field_key)):
                errors.append(_err(f"{path}/{field_key}", Category.SCHEMA, "identifier",
                                    f"metric_view.{field_key}はField名でなければなりません。"))
            # **片方だけの指定を通さない。** 「どのFieldで」だけ書いて
            # 「どの値のとき」が無いと、絞り込みも符号付けも成立しない。
            # 黙って無視すると、指定したつもりの絞り込みが効かないまま
            # 「収入の合計」という見出しの下に全額が出る。
            if (field_key in widget) != (value_key in widget):
                errors.append(_err(f"{path}/{field_key}", Category.SCHEMA, "required",
                                    f"metric_view.{field_key}と{value_key}は両方必要です。"))
        if "sign_field" in widget and (widget.get("aggregate") or "count") != "sum":
            # 符号付けは合計にしか意味が無い。平均や最大に負の記録を
            # 混ぜても、答えになる数値にならない。
            errors.append(_err(f"{path}/sign_field", Category.SCHEMA, "field_not_allowed",
                                "metric_view.sign_fieldはaggregate=sumのときだけ使えます。"))

    elif t == "date_field":
        # v1.7新規(CEO「全て実装してくれ」対応、Widget Vocabulary
        # Expansion第2弾)。choice_field(TD34)と同じ理由: TD33で
        # `text_field`のplaceholderへ「日付(YYYY-MM-DD)」という書式の
        # ヒントを埋め込む応急処置をしていたが、それでも利用者は自由な
        # 文字列を打ててしまい、`ForgeFieldValueParser._parseDate()`が
        # 要求する厳密なISO 8601完全一致を満たさない入力は依然として
        # 送信後に拒否されうる。`showDatePicker()`(Flutter標準)による
        # カレンダーUIへ置き換えることで、誤入力自体を構造的に防ぐ。
        errors.extend(_check_additional_properties(
            widget, {"type", "id", "label", "state_ref", "placeholder"}, path
        ))
        if not _is_nonempty_str(widget.get("label"), 80):
            errors.append(_err(f"{path}/label", Category.SCHEMA, "string_length", "date_field.labelが不正です。"))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "date_field.state_refは必須です。"))
        if "placeholder" in widget and (not isinstance(widget["placeholder"], str) or len(widget["placeholder"]) > 80):
            errors.append(_err(f"{path}/placeholder", Category.SCHEMA, "string_length", "placeholderが不正です。"))

    elif t == "tab_view":
        # v1.7新規。column/row/card/formと同じ「フラットなchildren配列を
        # 持つコンテナ」として設計している(CONTAINER_WIDGET_TYPESの
        # コメント参照)。`children[i]`が`tab_titles[i]`というタブの中身
        # (通常は`column`)に対応する。
        errors.extend(_check_additional_properties(widget, {"type", "id", "tab_titles", "children"}, path))
        tab_titles = widget.get("tab_titles")
        valid_titles = (
            isinstance(tab_titles, list) and (1 <= len(tab_titles) <= 6)
            and all(_is_nonempty_str(t, 20) for t in tab_titles)
        )
        if not valid_titles:
            errors.append(_err(f"{path}/tab_titles", Category.SCHEMA, "array_bounds",
                                "tab_titlesは要素数1〜6の、各要素が1〜20文字の文字列である配列です。"))
        children = widget.get("children")
        if not isinstance(children, list) or not (1 <= len(children) <= 6):
            errors.append(_err(f"{path}/children", Category.SCHEMA, "array_bounds",
                                "tab_view.childrenは要素数1〜6の配列です。"))
        else:
            for i, child in enumerate(children):
                errors.extend(_check_widget_schema(child, f"{path}/children/{i}", allowed_widgets, version))
        if valid_titles and isinstance(children, list) and len(tab_titles) != len(children):
            errors.append(_err(f"{path}/children", Category.SCHEMA, "array_length_mismatch",
                                "tab_titlesとchildrenは同じ要素数である必要があります。"))

    elif t == "slider":
        # v1.8新規。上限・下限が決まっている数値Field専用の入力
        # (例: reading_logの「評価(5段階)」)。既存の"number"型state
        # (v1.2で追加済み)を直接使い、新しいstate型は追加しない。
        errors.extend(_check_additional_properties(widget, {"type", "id", "label", "state_ref", "min", "max"}, path))
        if not _is_nonempty_str(widget.get("label"), 80):
            errors.append(_err(f"{path}/label", Category.SCHEMA, "string_length", "slider.labelが不正です。"))
        if not _is_identifier(widget.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "slider.state_refは必須です。"))
        min_v = widget.get("min")
        max_v = widget.get("max")
        min_valid = isinstance(min_v, (int, float)) and not isinstance(min_v, bool)
        max_valid = isinstance(max_v, (int, float)) and not isinstance(max_v, bool)
        if not min_valid:
            errors.append(_err(f"{path}/min", Category.SCHEMA, "required", "slider.minは数値である必要があります。"))
        if not max_valid:
            errors.append(_err(f"{path}/max", Category.SCHEMA, "required", "slider.maxは数値である必要があります。"))
        if min_valid and max_valid and min_v >= max_v:
            errors.append(_err(f"{path}/max", Category.SCHEMA, "range",
                                "slider.maxはslider.minより大きい必要があります。"))

    return errors


def _check_action_schema(action: Any, path: str, version: str, depth: int) -> list[ValidationIssue]:
    if not isinstance(action, dict) or "type" not in action:
        return [_err(path, Category.SCHEMA, "action_type_missing", "actionにはtypeが必須です。")]

    t = action.get("type")
    if t not in ACTION_TYPES:
        return [_err(f"{path}/type", Category.SCHEMA, "unknown_action",
                      f"未知のAction type '{t}' です。許可されているのは {sorted(ACTION_TYPES)} のみです。")]
    allowed_actions = ACTION_TYPES_BY_VERSION[version]
    if t not in allowed_actions:
        return [_err(f"{path}/type", Category.SCHEMA, "action_not_allowed_in_version",
                      f"Action type '{t}' はこの文書のversionでは使用できません。")]

    errors: list[ValidationIssue] = []
    if t == "navigate":
        errors.extend(_check_additional_properties(action, {"type", "target_screen_id"}, path))
        if not isinstance(action.get("target_screen_id"), str) or not action["target_screen_id"]:
            errors.append(_err(f"{path}/target_screen_id", Category.SCHEMA, "required", "navigate.target_screen_idが不正です。"))
    elif t == "go_back":
        errors.extend(_check_additional_properties(action, {"type"}, path))
    elif t in {"set_value", "set_state"}:
        errors.extend(_check_additional_properties(action, {"type", "state_ref", "value"}, path))
        if not _is_identifier(action.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", f"{t}.state_refが不正です。"))
        if "value" not in action:
            errors.append(_err(f"{path}/value", Category.SCHEMA, "required", f"{t}.valueは必須です。"))
    elif t == "add_item":
        errors.extend(_check_additional_properties(action, {"type", "target_state_ref", "source_state_ref"}, path))
        if not _is_identifier(action.get("target_state_ref")):
            errors.append(_err(f"{path}/target_state_ref", Category.SCHEMA, "required", "add_item.target_state_refが不正です。"))
        if not _is_identifier(action.get("source_state_ref")):
            errors.append(_err(f"{path}/source_state_ref", Category.SCHEMA, "required", "add_item.source_state_refが不正です。"))
    elif t == "add_record":
        # FORGE v0.7(Record Runtime Phase1)。`FORGE-IR-V1-PROPOSAL.md`
        # 4.3節で設計した「宣言的なField束ね」方式: `field_bindings`が
        # Record Field名(識別子)→source state_ref(識別子)の対応表を
        # 持ち、Runtimeが実行時に各source stateの現在値を読んで1つの
        # Recordへ束ねる(動的な式評価は行わない、静的な対応表のみ)。
        errors.extend(_check_additional_properties(action, {"type", "target_state_ref", "field_bindings"}, path))
        if not _is_identifier(action.get("target_state_ref")):
            errors.append(_err(f"{path}/target_state_ref", Category.SCHEMA, "required", "add_record.target_state_refが不正です。"))
        errors.extend(_check_field_bindings_schema(action.get("field_bindings"), path))
    elif t == "select_record":
        # FORGE v0.8(Record Runtime Phase2)。**このActionは通常、
        # 文書のJSON上には現れない**(`record_id`は特定の1件を指す値で
        # あり、Compilerが静的なJSONへ埋め込める情報ではないため)。
        # 実際には`record_list_view`Widgetの`selectable`/
        # `selected_state_ref`/`select_field_bindings`プロパティを
        # Runtimeが読み取り、タップされたRecordのidを実行時に補って
        # このAction型のインスタンスをDart側で直接組み立てて発行する
        # (`forge_action_dispatcher.dart`参照)。Schema/Validatorとしては、
        # 将来的な直接記述(例: 特殊なbuttonからの発行)や、テスト用に
        # 手で組み立てたJSONも受理できるよう、型定義自体は用意しておく。
        errors.extend(_check_additional_properties(
            action, {"type", "source_state_ref", "target_state_ref", "field_bindings"}, path
        ))
        if not _is_identifier(action.get("source_state_ref")):
            errors.append(_err(f"{path}/source_state_ref", Category.SCHEMA, "required", "select_record.source_state_refが不正です。"))
        if not _is_identifier(action.get("target_state_ref")):
            errors.append(_err(f"{path}/target_state_ref", Category.SCHEMA, "required", "select_record.target_state_refが不正です。"))
        if "field_bindings" in action:
            errors.extend(_check_field_bindings_schema(action.get("field_bindings"), path))
    elif t == "update_record":
        # FORGE v0.8(Record Runtime Phase2)。`record_id_ref`は、更新対象の
        # idが入っているstate(通常`selected_record`)を指す。`select_record`
        # と異なり、こちらは「選択中のRecordを更新する」という静的に
        # 表現できる操作のため、通常のbutton/form.submit_actionとして
        # 文書内に直接現れる(Compilerが生成する)。
        errors.extend(_check_additional_properties(
            action, {"type", "target_state_ref", "record_id_ref", "field_bindings"}, path
        ))
        if not _is_identifier(action.get("target_state_ref")):
            errors.append(_err(f"{path}/target_state_ref", Category.SCHEMA, "required", "update_record.target_state_refが不正です。"))
        if not _is_identifier(action.get("record_id_ref")):
            errors.append(_err(f"{path}/record_id_ref", Category.SCHEMA, "required", "update_record.record_id_refが不正です。"))
        errors.extend(_check_field_bindings_schema(action.get("field_bindings"), path))
    elif t == "delete_record":
        # FORGE v0.8(Record Runtime Phase2)。`record_id_ref`が
        # `selected_record`を指す場合は「選択中を削除」(update_recordと
        # 対称的、静的に表現できる)。`record_list_view`のカード単位の
        # 削除ボタンは、update_recordと違いRuntimeがタップされたRecordの
        # idを直接補ってこのAction型を組み立てて発行する(select_record
        # と同じ理由、`forge_action_dispatcher.dart`参照)ため、
        # `record_id_ref`はこちらも静的なJSON上は「selected_record等、
        # 何らかのstateを指す」という契約のみを検査する。
        errors.extend(_check_additional_properties(action, {"type", "target_state_ref", "record_id_ref"}, path))
        if not _is_identifier(action.get("target_state_ref")):
            errors.append(_err(f"{path}/target_state_ref", Category.SCHEMA, "required", "delete_record.target_state_refが不正です。"))
        if not _is_identifier(action.get("record_id_ref")):
            errors.append(_err(f"{path}/record_id_ref", Category.SCHEMA, "required", "delete_record.record_id_refが不正です。"))
    elif t == "toggle_state":
        errors.extend(_check_additional_properties(action, {"type", "state_ref"}, path))
        if not _is_identifier(action.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "toggle_state.state_refが不正です。"))
    elif t == "reset_state":
        errors.extend(_check_additional_properties(action, {"type", "state_ref"}, path))
        if not _is_identifier(action.get("state_ref")):
            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "reset_state.state_refが不正です。"))
    elif t == "submit_form":
        errors.extend(_check_additional_properties(action, {"type", "form_ref", "success_action"}, path))
        if not _is_identifier(action.get("form_ref")):
            errors.append(_err(f"{path}/form_ref", Category.SCHEMA, "required", "submit_form.form_refが不正です。"))
        if "success_action" not in action:
            errors.append(_err(f"{path}/success_action", Category.SCHEMA, "required", "submit_form.success_actionは必須です。"))
        else:
            errors.extend(_check_action_schema(action["success_action"], f"{path}/success_action", version, depth))
    elif t == "composite":
        errors.extend(_check_additional_properties(action, {"type", "actions"}, path))
        actions = action.get("actions")
        if not isinstance(actions, list) or not (1 <= len(actions) <= MAX_COMPOSITE_ACTIONS):
            errors.append(_err(f"{path}/actions", Category.SCHEMA, "array_bounds",
                                f"composite.actionsは要素数1〜{MAX_COMPOSITE_ACTIONS}の配列です。"))
        elif depth >= MAX_COMPOSITE_DEPTH:
            errors.append(_err(path, Category.RUNTIME_SAFETY, "max_composite_depth",
                                f"compositeのネストが上限({MAX_COMPOSITE_DEPTH}段)を超えています。"))
        else:
            for i, sub_action in enumerate(actions):
                errors.extend(_check_action_schema(sub_action, f"{path}/actions/{i}", version, depth + 1))
    return errors


def _check_field_bindings_schema(field_bindings: Any, path: str) -> list[ValidationIssue]:
    """`add_record`/`select_record`/`update_record`で共有する、
    `field_bindings`(Record Field名→source state_refの対応表)の検査。"""
    if not isinstance(field_bindings, dict) or not (1 <= len(field_bindings) <= MAX_FIELD_BINDINGS):
        return [_err(f"{path}/field_bindings", Category.SCHEMA, "array_bounds",
                      f"field_bindingsは要素数1〜{MAX_FIELD_BINDINGS}のobjectである必要があります。")]
    errors: list[ValidationIssue] = []
    for field_name, source_ref in field_bindings.items():
        if not _is_identifier(field_name):
            errors.append(_err(f"{path}/field_bindings/{field_name}", Category.SCHEMA, "identifier_format",
                                f"Field名 '{field_name}' が不正です。"))
        if not _is_identifier(source_ref):
            errors.append(_err(f"{path}/field_bindings/{field_name}", Category.SCHEMA, "identifier_format",
                                f"'{field_name}' のsource state_refが不正です。"))
    return errors


def _check_additional_properties(obj: dict, allowed: set[str], path: str) -> list[ValidationIssue]:
    extra = set(obj.keys()) - allowed
    if not extra:
        return []
    return [_err(path, Category.SCHEMA, "additional_properties", f"許可されていない項目: {sorted(extra)}")]


def _is_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(IDENTIFIER_RE.match(value))


def _is_nonempty_str(value: Any, max_len: int) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= max_len


# ---------------------------------------------------------------------------
# レイヤー3: 意味検査(Semantic)
# ---------------------------------------------------------------------------

def _check_semantics(doc: dict, allowed_widgets: set[str]) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    screens = doc["screens"]
    screen_ids = [s["id"] for s in screens]

    seen: set[str] = set()
    for i, sid in enumerate(screen_ids):
        if sid in seen:
            errors.append(_err(f"$/screens/{i}/id", Category.SEMANTIC, "duplicate_screen_id",
                                f"screen id '{sid}' が重複しています。"))
        seen.add(sid)

    if doc["initial_screen_id"] not in screen_ids:
        errors.append(_err("$/initial_screen_id", Category.SEMANTIC, "initial_screen_exists",
                            f"initial_screen_id '{doc['initial_screen_id']}' に一致するscreenがありません。"))

    all_widget_ids: dict[str, str] = {}

    for i, screen in enumerate(screens):
        screen_path = f"$/screens/{i}"
        state = screen.get("state", {})

        # FORGE v0.9新規: record_list型stateのschema_refが、実際に
        # doc["record_schemas"]内に存在することを確認する
        # (record_schemas自体はrecord_listとは独立した定義のため、
        # スキーマ層(_check_record_schemas)ではなく、参照整合性の
        # 検査であるこの意味検査層で確認する)。
        record_schema_names = set(doc.get("record_schemas", {}).keys())
        for state_key, state_value in state.items():
            if isinstance(state_value, dict) and state_value.get("type") == "record_list" and "schema_ref" in state_value:
                schema_ref = state_value["schema_ref"]
                if schema_ref not in record_schema_names:
                    errors.append(_err(
                        f"{screen_path}/state/{state_key}/schema_ref", Category.SEMANTIC, "schema_reference_exists",
                        f"schema_ref '{schema_ref}' に一致するrecord_schemasの定義がありません。",
                    ))

        # form_ref解決用: このscreen内のform widget id集合を先に集めておく。
        form_ids_in_screen = {
            w["id"] for _, w in _walk_widgets(screen["body"], f"{screen_path}/body") if w["type"] == "form"
        }

        for w_path, widget in _walk_widgets(screen["body"], f"{screen_path}/body"):
            wid = widget["id"]
            if wid in all_widget_ids:
                errors.append(_err(f"{w_path}/id", Category.SEMANTIC, "duplicate_widget_id",
                                    f"widget id '{wid}' は '{all_widget_ids[wid]}' と重複しています。"))
            else:
                all_widget_ids[wid] = w_path

            wtype = widget["type"]

            if wtype in {
                "text", "text_field", "checklist", "list", "record_list_view",
                "choice_field", "bar_chart", "date_field", "slider", "metric_view",
            } and (
                wtype != "text" or "state_ref" in widget
            ):
                ref = widget.get("state_ref")
                if ref is not None:
                    errors.extend(_check_state_ref(ref, wtype, state, w_path))

            if wtype == "record_list_view":
                # FORGE v0.8(Record Runtime Phase2)。selected_state_ref・
                # select_field_bindingsの参照整合性を検査する。
                selected_ref = widget.get("selected_state_ref")
                if selected_ref is not None:
                    errors.extend(_check_state_ref(selected_ref, "selected_record", state, w_path,
                                                    ref_field="selected_state_ref"))
                if "select_field_bindings" in widget:
                    errors.extend(_check_field_bindings_refs(
                        widget["select_field_bindings"], state, w_path, property_name="select_field_bindings"
                    ))

            if wtype == "checkbox":
                errors.extend(_check_state_ref(widget["state_ref"], "checkbox", state, w_path))

            if wtype == "bar_chart":
                # v1.6新規。value_field/label_fieldが、state_refが指す
                # record_listのschema_ref先(record_schemas)に実在するFieldを
                # 指しているか検査する(record_list_view.display_fieldsは
                # identifier形式のみ検査して実在確認まではしていないが、
                # bar_chartは「存在しないFieldでグラフが描けたつもりになる」
                # 実害が大きいため、record_list_viewより踏み込んだ検査を行う)。
                ref = widget.get("state_ref")
                state_value = state.get(ref) if isinstance(ref, str) else None
                schema_ref = state_value.get("schema_ref") if isinstance(state_value, dict) else None
                schema_def = doc.get("record_schemas", {}).get(schema_ref) if schema_ref else None
                if isinstance(schema_def, dict):
                    fields_by_name = {
                        f.get("name"): f for f in schema_def.get("fields", []) if isinstance(f, dict)
                    }
                    value_field = widget.get("value_field")
                    label_field = widget.get("label_field")

                    # v1.9(2026-08-13)。集計する場合、value_field/label_fieldは
                    # 省略できる(`_check_widget_schema`参照)。省略されたものを
                    # 「存在しないFieldを指している」と誤検出しないようにする。
                    grouping = widget.get("group_by")
                    aggregating = grouping is not None
                    if aggregating:
                        # グループ化キー自体は実在するFieldでなければならない。
                        # ここを検査しないと、存在しないFieldで「集計できた
                        # つもり」になり、実行時は静かに空のグラフが出る。
                        if grouping not in fields_by_name:
                            errors.append(_err(
                                f"{w_path}/group_by", Category.SEMANTIC, "field_reference_exists",
                                f"group_by '{grouping}' に一致するFieldが"
                                f"record_schemas['{schema_ref}']にありません。",
                            ))
                    if aggregating and value_field is None:
                        pass  # countではvalue_field不要
                    elif value_field not in fields_by_name:
                        errors.append(_err(
                            f"{w_path}/value_field", Category.SEMANTIC, "field_reference_exists",
                            f"value_field '{value_field}' に一致するFieldがrecord_schemas['{schema_ref}']にありません。",
                        ))
                    elif fields_by_name[value_field].get("type") != "number":
                        errors.append(_err(
                            f"{w_path}/value_field", Category.SEMANTIC, "field_type_mismatch",
                            f"value_field '{value_field}' はtype=numberのFieldである必要があります"
                            f"(実際: {fields_by_name[value_field].get('type')!r})。",
                        ))
                    if aggregating and label_field is None:
                        pass  # 集計時はグループ化キーがラベルになる
                    elif label_field not in fields_by_name:
                        errors.append(_err(
                            f"{w_path}/label_field", Category.SEMANTIC, "field_reference_exists",
                            f"label_field '{label_field}' に一致するFieldがrecord_schemas['{schema_ref}']にありません。",
                        ))

            if wtype == "metric_view":
                # v1.11新規。`bar_chart`と同じ理由で、value_fieldが実在の
                # 数値Fieldを指しているかまで検査する。**画面で一番大きく
                # 出る数値**なので、「存在しないFieldで0が出る」は
                # bar_chartより実害が大きい。
                ref = widget.get("state_ref")
                state_value = state.get(ref) if isinstance(ref, str) else None
                schema_ref = state_value.get("schema_ref") if isinstance(state_value, dict) else None
                schema_def = doc.get("record_schemas", {}).get(schema_ref) if schema_ref else None
                if isinstance(schema_def, dict):
                    fields_by_name = {
                        f.get("name"): f for f in schema_def.get("fields", []) if isinstance(f, dict)
                    }
                    value_field = widget.get("value_field")
                    if (widget.get("aggregate") or "count") == "count" and value_field is None:
                        pass  # 件数を数えるだけなので値Fieldは要らない
                    elif value_field not in fields_by_name:
                        errors.append(_err(
                            f"{w_path}/value_field", Category.SEMANTIC, "field_reference_exists",
                            f"value_field '{value_field}' に一致するFieldが"
                            f"record_schemas['{schema_ref}']にありません。",
                        ))
                    elif fields_by_name[value_field].get("type") != "number":
                        errors.append(_err(
                            f"{w_path}/value_field", Category.SEMANTIC, "field_type_mismatch",
                            f"value_field '{value_field}' はtype=numberのFieldである必要があります"
                            f"(実際: {fields_by_name[value_field].get('type')!r})。",
                        ))

            if wtype in {"text_field", "checkbox"} and "validation" in widget:
                warnings.extend(_check_validation_applicability(widget, state, w_path))

            if wtype == "button":
                errors.extend(_check_action_refs(widget["action"], screen_ids, state, form_ids_in_screen, w_path))

            if wtype == "form":
                errors.extend(_check_action_refs(
                    widget["submit_action"], screen_ids, state, form_ids_in_screen, f"{w_path}/submit_action"
                ))
                input_types = {"text_field", "checkbox", "choice_field", "date_field", "slider"}
                has_input = any(
                    c["type"] in input_types for _, c in _walk_widgets(widget, w_path)
                    if c["id"] != widget["id"]
                )
                if not has_input:
                    warnings.append(_err(
                        w_path, Category.SEMANTIC, "form_without_input",
                        "formにtext_field/checkbox等の入力Widgetが1つも含まれていません。",
                        severity=Severity.WARNING,
                    ))

        if screen["id"] != doc["initial_screen_id"]:
            has_exit = any(
                (w["type"] == "button" and _action_eventually_navigates_or_backs(w["action"])) or
                (w["type"] == "form" and _action_eventually_navigates_or_backs(w["submit_action"]))
                for _, w in _walk_widgets(screen["body"], screen_path)
            )
            if not has_exit:
                warnings.append(_err(
                    screen_path, Category.SEMANTIC, "no_back_navigation",
                    f"screen '{screen['id']}' はinitial screenではないのに、go_back/navigateが無く行き止まりの可能性があります。",
                    severity=Severity.WARNING,
                ))

    return errors, warnings


def _action_eventually_navigates_or_backs(action: dict) -> bool:
    """composite/submit_formの中に潜んでいるnavigate/go_backも見つける
    (FORGE-MILESTONE-003で導入した合成Actionに合わせ、no_back_navigation警告の
    誤検知を防ぐ)。"""
    t = action.get("type")
    if t in {"navigate", "go_back"}:
        return True
    if t == "submit_form":
        return _action_eventually_navigates_or_backs(action.get("success_action", {}))
    if t == "composite":
        return any(_action_eventually_navigates_or_backs(a) for a in action.get("actions", []))
    return False


def _check_validation_applicability(widget: dict, state: dict, path: str) -> list[ValidationIssue]:
    """min/maxは数値stateにのみ、min_length/max_length/patternは文字列stateにのみ
    意味を持つ。State型に適用できないValidationは安全に失敗させる(ブロッキング
    エラーにはせず、警告として開発ログに理由を残す。指示書5章の方針)。"""
    warnings: list[ValidationIssue] = []
    state_ref = widget.get("state_ref")
    state_value = state.get(state_ref) if state_ref else None
    state_type = state_value.get("type") if isinstance(state_value, dict) else None

    rules = widget.get("validation", {}).get("rules", [])
    for i, rule in enumerate(rules):
        rule_type = rule.get("type")
        if rule_type in {"min_length", "max_length", "pattern"} and state_type not in {"string"}:
            warnings.append(_err(
                f"{path}/validation/rules/{i}", Category.SEMANTIC, "validation_rule_not_applicable",
                f"'{rule_type}' はstring型のstateにのみ意味を持ちますが、'{state_ref}'はtype={state_type}です。",
                severity=Severity.WARNING,
            ))
        elif rule_type in {"min", "max"} and state_type not in {"number"}:
            warnings.append(_err(
                f"{path}/validation/rules/{i}", Category.SEMANTIC, "validation_rule_not_applicable",
                f"'{rule_type}' はnumber型のstateにのみ意味を持ちますが、'{state_ref}'はtype={state_type}です。",
                severity=Severity.WARNING,
            ))
    return warnings


def _check_field_bindings_refs(
    field_bindings: dict, state: dict, path: str, *, property_name: str = "field_bindings"
) -> list[ValidationIssue]:
    """`add_record`/`select_record`/`update_record`/`record_list_view.
    select_field_bindings`で共有する、`field_bindings`の各source_refが
    実在し、string/number/boolean型であることの検査(意味検査レイヤー)。"""
    errors: list[ValidationIssue] = []
    for field_name, source_ref in field_bindings.items():
        if source_ref not in state:
            errors.append(_err(f"{path}/{property_name}/{field_name}", Category.SEMANTIC,
                                "state_reference_exists", f"State reference '{source_ref}' does not exist."))
        elif state[source_ref].get("type") not in {"string", "number", "boolean"}:
            errors.append(_err(
                f"{path}/{property_name}/{field_name}", Category.SEMANTIC, "state_reference_type_mismatch",
                f"{property_name}['{field_name}']が参照する '{source_ref}' はstring/number/boolean型である必要が"
                f"ありますが、実際は type={state[source_ref].get('type')} です。",
            ))
    return errors


def _check_action_refs(
    action: dict, screen_ids: list[str], state: dict, form_ids_in_screen: set[str], path: str
) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    t = action.get("type")
    if t == "navigate" and action["target_screen_id"] not in screen_ids:
        errors.append(_err(f"{path}/action/target_screen_id", Category.SEMANTIC, "navigation_target_exists",
                            f"navigate先 '{action['target_screen_id']}' に一致するscreenがありません。"))
    if t in {"set_value", "set_state"}:
        errors.extend(_check_state_ref(action["state_ref"], "set_value", state, f"{path}/action"))
    if t == "add_item":
        errors.extend(_check_state_ref(action["target_state_ref"], "checklist", state, f"{path}/action", ref_field="target_state_ref"))
        errors.extend(_check_state_ref(action["source_state_ref"], "string", state, f"{path}/action", ref_field="source_state_ref"))
    if t == "add_record":
        errors.extend(_check_state_ref(
            action["target_state_ref"], "record_list", state, f"{path}/action", ref_field="target_state_ref"
        ))
        errors.extend(_check_field_bindings_refs(action.get("field_bindings", {}), state, f"{path}/action"))
    if t == "select_record":
        errors.extend(_check_state_ref(
            action["source_state_ref"], "record_list", state, f"{path}/action", ref_field="source_state_ref"
        ))
        errors.extend(_check_state_ref(
            action["target_state_ref"], "selected_record", state, f"{path}/action", ref_field="target_state_ref"
        ))
        errors.extend(_check_field_bindings_refs(action.get("field_bindings", {}), state, f"{path}/action"))
    if t == "update_record":
        errors.extend(_check_state_ref(
            action["target_state_ref"], "record_list", state, f"{path}/action", ref_field="target_state_ref"
        ))
        errors.extend(_check_state_ref(
            action["record_id_ref"], "selected_record", state, f"{path}/action", ref_field="record_id_ref"
        ))
        errors.extend(_check_field_bindings_refs(action.get("field_bindings", {}), state, f"{path}/action"))
    if t == "delete_record":
        errors.extend(_check_state_ref(
            action["target_state_ref"], "record_list", state, f"{path}/action", ref_field="target_state_ref"
        ))
        errors.extend(_check_state_ref(
            action["record_id_ref"], "selected_record", state, f"{path}/action", ref_field="record_id_ref"
        ))
    if t == "toggle_state":
        errors.extend(_check_state_ref(action["state_ref"], "checkbox", state, f"{path}/action"))
    if t == "reset_state":
        if action["state_ref"] not in state:
            errors.append(_err(f"{path}/action/state_ref", Category.SEMANTIC, "state_reference_exists",
                                f"State reference '{action['state_ref']}' does not exist."))
    if t == "submit_form":
        if action["form_ref"] not in form_ids_in_screen:
            errors.append(_err(f"{path}/action/form_ref", Category.SEMANTIC, "form_reference_exists",
                                f"form_ref '{action['form_ref']}' に一致するform widgetがこのscreen内にありません。"))
        errors.extend(_check_action_refs(action["success_action"], screen_ids, state, form_ids_in_screen, f"{path}/action/success_action"))
    if t == "composite":
        for sub_action in action.get("actions", []):
            errors.extend(_check_action_refs(sub_action, screen_ids, state, form_ids_in_screen, path))
    return errors


def _check_state_ref(ref: str, expected_kind: str, state: dict, path: str, ref_field: str = "state_ref") -> list[ValidationIssue]:
    if ref not in state:
        return [_err(f"{path}/{ref_field}", Category.SEMANTIC, "state_reference_exists",
                      f"State reference '{ref}' does not exist.")]

    actual_type = state[ref].get("type")
    expected_type_map = {
        "text": "string", "text_field": "string", "checklist": "checklist",
        "string": "string", "checkbox": "boolean", "list": "string_list",
        "record_list_view": "record_list", "record_list": "record_list",
        "selected_record": "selected_record",
        "choice_field": "string", "bar_chart": "record_list", "date_field": "string", "slider": "number",
        # v1.11。bar_chartと同じくrecord_listを畳んで見せる。
        "metric_view": "record_list",
    }
    expected_type = expected_type_map.get(expected_kind)
    if expected_type and actual_type != expected_type:
        return [_err(f"{path}/{ref_field}", Category.SEMANTIC, "state_reference_type_mismatch",
                      f"State reference '{ref}' は type={expected_type} を期待していますが、実際は type={actual_type} です。")]
    return []


def _walk_widgets(widget: dict, path: str):
    yield path, widget
    if widget["type"] in CONTAINER_WIDGET_TYPES:
        for i, child in enumerate(widget.get("children", [])):
            yield from _walk_widgets(child, f"{path}/children/{i}")


# ---------------------------------------------------------------------------
# レイヤー4: Runtime Safety
# ---------------------------------------------------------------------------

def _check_runtime_safety(doc: dict) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for i, screen in enumerate(doc["screens"]):
        screen_path = f"$/screens/{i}"
        depth = _widget_depth(screen["body"])
        if depth > MAX_NESTING_DEPTH:
            errors.append(_err(f"{screen_path}/body", Category.RUNTIME_SAFETY, "max_nesting_depth",
                                f"ネスト深度 {depth} が上限 {MAX_NESTING_DEPTH} を超えています。"))

        widget_count = sum(1 for _ in _walk_widgets(screen["body"], f"{screen_path}/body"))
        if widget_count > MAX_WIDGETS_PER_SCREEN:
            errors.append(_err(screen_path, Category.RUNTIME_SAFETY, "max_widgets_per_screen",
                                f"screen内のWidget数 {widget_count} が上限 {MAX_WIDGETS_PER_SCREEN} を超えています。"))

    # 注記: Widgetはツリー、Stateはキー参照のみで他Widgetを指さないため、
    # 構造上の循環参照は発生し得ない。Action側(composite)の循環・過剰ネストは
    # _check_action_schema の depth 引数(MAX_COMPOSITE_DEPTH)で別途防いでいる。

    return errors, warnings


def _widget_depth(widget: dict) -> int:
    if widget["type"] not in CONTAINER_WIDGET_TYPES or not widget.get("children"):
        return 1
    return 1 + max((_widget_depth(c) for c in widget["children"]), default=0)
