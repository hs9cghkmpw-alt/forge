"""ForgeLanguageCompiler(FORGE IR v1、Phase2で新設、
FORGE v0.7 Record Runtime Phase1・FORGE v0.8 Phase2で更新)。

`ForgeIR`を入力として、Forge Language(`ForgeIRDocument`)を生成する。
既存の`forge_ai.core.compiler.Compiler`(ApplicationPlanを直接入力に
取る、Checklist単一画面専用)とは**別のクラス**であり、`Compiler`
自体は変更していない(「既存Compilerを全面的に壊さない」という指示書
の制約、Phase2から継続)。

役割分担は`FORGE-IR-V1-PROPOSAL.md`3章の通り: IRは「何が起きるべきか」
(Entity/View/Action/Event)を表現し、このクラスは「Flutter Runtime上で
それをどう実現するか」(Widget種別・state_ref・具体的なAction JSON)を
決める。

**FORGE v0.7(Record Runtime Phase1)での変更**: Phase2では、Forge
Language v1.2の制約(`add_item`はchecklist型state専用・複数値の動的
合成機能なし)により、一覧に反映されるのは**主要Fieldのみ**という
妥協を受け入れていた。今回、v1.3の`record_list` State・
`record_list_view` Widget(layout="card")・`add_record` Action
(`field_bindings`による宣言的なField束ね、`FORGE-IR-V1-PROPOSAL.md`
4.3節)が実装されたことで、**Entityの全Fieldを一覧へ反映できる**ように
なった(Phase2の既知の制限を解消)。

**FORGE v0.8(Record Runtime Phase2)での変更**: 選択・編集・削除を
追加した。

* `selected_record`型のstate(`selected`)を新設する。
* `record_list_view`へ`selectable`/`selected_state_ref`/
  `select_field_bindings`を追加し、各Cardをタップすると選択でき、
  選択時に編集用フィールド(`edit_field_<name>`)へ値が自動反映される
  ようにする。
* **編集用の入力欄(`edit_field_<name>`)は、作成用の入力欄
  (`field_<name>`)とは意図的に別のstateとして分離した**(指示書の
  Design Policy「コード重複よりも責務分離を優先」に基づく判断: 同じ
  stateを作成/編集で使い回すと、「今どちらの操作をしているか」が
  Forge Languageの静的なJSONだけでは区別できなくなるため)。
* 「更新」ボタン(`update_record`、`record_id_ref="selected"`)と
  「削除」ボタン(`delete_record`、同じく`record_id_ref="selected"`)
  は、いずれも「選択中の1件に対する操作」という共通の形にした。これに
  より、両方とも**Compilerが静的に生成できる、通常のbutton.action**
  として表現できる(動的な値の補完が要らない)。「選択」自体
  (`select_record`)だけがCardタップ時にRuntimeが動的に組み立てる
  特殊な経路であり、これはForge Language側の実装詳細である
  (`ir_generator.py`のモジュールdocstring、ADR-012参照)。

**FORGE v0.9(Typed Record Runtime Phase1)での変更**: `record_schema`
(Entity定義のField型情報)を、Forge Language文書の`record_schemas`
(トップレベル、`record_list`とは独立した定義)として出力するように
なった。`records`(record_list型state)は`schema_ref`でこの定義を
指す。**この変更はWidget生成・CRUD挙動には一切影響しない**
(指示書「Runtime動作も変更しません」): Widget構成(`form`/
`record_list_view`/`button`)・Action(`add_record`/`update_record`/
`delete_record`)は無変更のまま、`record_schemas`という新しい情報が
文書へ追加されるだけである。Versionを`"1.3"`から`"1.4"`へ上げた
(`record_schemas`・`schema_ref`はv1.4専用のため)。

**FORGE v1.0(Product Quality Sprint1)での変更**: 「単一画面でも、
単純なWidget縦並びではなく、視覚的階層とドメインらしい情報設計を
持つアプリを生成できること」という目標に対応する。

* `design_tokens`(色・角丸・余白)を、Entityの`visual_style`
  (calm/warm/vibrant/neutral)に応じた**少数のプリセット**から選んで
  出力する(`FORGE-PRODUCT-DESIGN-LAYER-PROPOSAL.md`3.4節「無限に
  多様な配色をAIが自由に生成するのではなく、品質が保証された少数の
  選択肢から選ぶ」という設計判断の実装)。
* `section_header`Widgetで、単一画面を「Entityの見出し」「入力」
  「一覧」「編集」という意味のあるセクションへ区切る(指示書
  「単純なColumnではなく、意味のある情報のまとまりとして構成する」
  への対応)。
* 一覧(`record_list_view`)のレイアウトを、Domain名に基づき`card`/
  `grid`から選ぶ(Field数が少なく一覧性を優先したいDomain——TODO・
  習慣トラッカー——は`grid`、Field数が多く1件の情報量を優先したい
  Domainは`card`のまま)。
* Versionを`"1.4"`から`"1.5"`へ上げた(`design_tokens`・
  `section_header`・`layout: "grid"`はv1.5専用のため)。

**今回変更しなかったもの(指示書の制約通り)**: 複数画面・
Navigation・集計/グラフ・LLM-assisted Design Reasoningは、いずれも
今回のスコープ外(`FORGE-PRODUCT-DESIGN-LAYER-PROPOSAL.md`のロード
マップにおけるPhase 3・4・7に相当し、別途のマイルストーンで扱う)。

**v1.6(2026-08-11、Widget Vocabulary Expansion)での変更**: CEO承認に
より`docs/spec/LANGUAGE_FREEZE.md`のWidget追加凍結を解除して着手
(同ドキュメント自体は、実際には一度も正式に凍結宣言されていな
かったことを確認済み、詳細はTD34参照)。

* CHOICE型Fieldは、TD33のplaceholderへ選択肢を埋め込む応急処置を
  やめ、専用の`choice_field`Widget(ドロップダウン)を使うように
  なった。
* 数値Fieldを持つEntity(fishing_log/household_budget/reading_log/
  inventoryの4 Domain)は、一覧の直後に`bar_chart`が追加される
  (1 Record = 1本の棒、月ごとの合計等の集計は行わないPhase1の
  最小実装)。数値Fieldを持たないEntity(habit_tracking/todo/diary)
  には追加しない。
* これにより、household_budgetの「収入や支出を記録して、月ごとの
  収支をグラフで見たい」という既存の例文(`example_picker_sheet.
  dart`)が、ようやく字義通りに実現可能になった(以前は棒グラフに
  相当するWidgetが存在せず、実現不可能な約束だった)。
* 「月ごとの」集計自体(この例文が本来求めている水準)は、なお
  今回のスコープ外(1 Record = 1本の棒というPhase1の制約)。

**v1.7(2026-08-11、Widget Vocabulary Expansion第2弾)での変更**: CEO
「全て実装してくれ。確認もしなくて良い、ゴールは示している。
つくってくれ。」という明示的な指示を受けて着手。

* DATE型Fieldは、TD33のplaceholderへ「YYYY-MM-DD」という書式ヒントを
  埋め込む応急処置をやめ、専用の`date_field`Widget(カレンダー選択)を
  使うようになった。
* 単一画面内の「追加」「一覧」「編集」を、`divider`で区切って縦に
  積み上げる構成から、`tab_view`によるタブ切り替え構成へ変更した。
* **複数`screens`によるNavigator画面遷移は、今回も選択しなかった**
  (意図的な判断であり、単なる先送りではない): Flutter Runtime側
  (`forge_renderer.dart`)を調査した結果、`ForgeScreenView`は画面
  遷移のたびに独立した新しい`ForgeRuntimeState`を生成する設計に
  なっており、「一覧画面」の`records`Stateと「追加画面」の`records`
  Stateは、同じ`state_ref`名でも実行時には別インスタンスになる
  (画面をまたいだState共有・戻り値の受け渡し機構が存在しない)。
  この制約を無視して複数画面へ分割すると、「追加したはずのデータが
  一覧に出てこない」という壊れたアプリを生成してしまう。この
  根本的なRuntime側の制約を安全に回避しつつ、「単一画面に全部
  詰め込まれている」という見た目の問題だけを解決する手段として、
  State共有が一切不要な`tab_view`(同一画面・同一Stateのまま、
  表示だけを切り替える)を選んだ。真の意味での複数画面CRUD(一覧
  画面と追加/編集画面を独立したScreenとして行き来する)を実現するには、
  Runtime側に画面をまたいだState共有、または画面遷移の戻り値受け渡し
  機構を新設する必要があり、これは今回のスコープ外(別途の
  マイルストームで扱う、TECH_DEBT.md参照)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — 型注釈のみ
    from forge_ai.core.ir.design_intent import DesignIntent

from typing import Any

from forge_ai.core.compiler import (
    ForgeIRDocument,
    ForgeIRRecordSchema,
    ForgeIRSchemaField,
    ForgeIRScreen,
    ForgeIRStateValue,
    ForgeIRWidget,
    clamp_title,
    design_tokens_for_style,
)
from forge_ai.core.ir.ir_types import Entity, FieldType, ForgeIR, ViewKind
from forge_ai.core.ir.solution_shape import SolutionShape, select_solution_shape

# FORGE v1.0新規(Product Quality Sprint1)。Entityの`visual_style`
# (IR層、プラットフォーム非依存の「雰囲気」ヒント)から、実際の
# Forge Language `design_tokens`(色コード・角丸・余白という、Flutter
# Runtime固有の描画情報)への変換は、`design_tokens_for_style()`
# (`forge_ai/core/compiler.py`)へ委譲する。**具体的な色コードを選ぶ
# という判断はCompiler層に閉じる**(IRはこの変換表の存在を知らない、
# ADR-012の方針)。
#
# FORGE-PRODUCT-VISION-002(2026-08-12)対応: プリセット表自体は、
# legacy Checklist経路(`Compiler`)にも同じテーマ適用を広げるため、
# `forge_ai/core/compiler.py`側へ移動した(このモジュールは元々
# `forge_ai.core.compiler`をimportしているため、単一の定義元は
# そちらに置くのが自然。TECH_DEBT.md TD44参照)。

# FORGE v1.0新規(Product Quality Sprint1)。一覧をgrid表示にする
# Domain(Field数が少なく、一覧性を優先したいもの)。それ以外は
# 引き続きcard表示のまま(既存Domainの見た目を不必要に変えない、
# `household_budget`・`fishing_log`はcardのまま)。domain_category
# (Compilerの`compile()`が受け取る、文字列としてのDomain識別子)に
# 基づく判断であり、IRへは持ち込まない(あくまでForge Language
# Compilerの表示選択)。
_GRID_PREFERRED_DOMAINS = {"todo", "habit_tracking"}


class ForgeLanguageCompilationError(Exception):
    """`ForgeIR`がForge Languageへコンパイルできない形の場合(例:
    対象Domainに必要なView/Entityが欠けている)。IRGeneratorが正しく
    動作していれば通常発生しない、防御的な例外。"""



# ---------------------------------------------------------------------------
# Design Language V1（FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、2026-08-17）
# ---------------------------------------------------------------------------
#
# Compilerが`style_role`を出すのは、**構造から意味が決まる箇所だけ**である。
#
# 「このカードは目立たせたい」のような判断はここではしない——それは
# 利用者のNeedから来る意味であり、Cognitive Pipeline/AIが決めるべきもの
# である。Compilerが知っているのは「これはセクションの見出しである」
# 「これは繰り返し項目の一覧である」といった**構造上の事実**だけなので、
# そこから決まるroleに限って付ける。
#
# 値を書かないのが要点である。`text.headline`が何pxで何色になるかは
# Runtime（`design_language.dart`）が保証する。Compilerは意味だけを言う。
#
# roleの綴りはbackend側の語彙（`app/ai/runtime/design_language.py`）と
# 一致していなければならない。ずれると**Validatorが落とす**ので、
# 黙って壊れることはない（`unknown_style_role`）。
_ROLE_SECTION_HEADER = "text.headline"
_ROLE_RECORD_LIST = "card.list"
_ROLE_SUMMARY_CHART = "card.summary"
_ROLE_PRIMARY_BUTTON = "button.primary"
_ROLE_SECONDARY_BUTTON = "button.secondary"
_ROLE_FIELD_LABEL = "text.label"
# v1.11。**画面で最も重要な単一のKPI**。この綴りは v1.10 で語彙へ入れた
# のに、出力先のWidgetが無いまま置かれていた（TD69）。`metric_view` を
# 足したことで、初めて実際の画面へ出るようになった。
_ROLE_HERO_METRIC = "metric.primary"


def _intent_role(design_intent: "DesignIntent | None", axis: str, fallback: str) -> str:
    """AIが選んだroleを取り出す。**選んでいなければ既定値**。

    `design_intent`が`None`なのは「AIへ聞かなかった」場合であり、
    それ自体は異常ではない（Providerが無い経路・テスト）。
    """
    if design_intent is None:
        return fallback
    return design_intent.role_for(axis) or fallback

class ForgeLanguageCompiler:
    """`ForgeIR` → `ForgeIRDocument`(Forge Language v1.3)。

    対象3 Domain(fishing_log/household_budget/habit_tracking)専用。
    現在の実装は、IRのList View 1件・Form View(create)1件・
    Form View(edit)1件・Entity 1件という構成(`IRGenerator`が今回
    生成する形)のみを想定する。IRがこれ以外の構成(複数Entity・
    Relationship等)を持つ場合は、今回のスコープ外として
    `ForgeLanguageCompilationError`を送出する。
    """

    def compile(
        self, ir: ForgeIR, *, domain_category: str, title: str,
        design_intent: "DesignIntent | None" = None,
    ) -> ForgeIRDocument:
        errors = ir.referential_integrity_errors()
        if errors:
            raise ForgeLanguageCompilationError(f"ForgeIR has referential integrity errors: {errors}")
        if len(ir.entities) != 1:
            raise ForgeLanguageCompilationError(
                f"ForgeLanguageCompiler(Phase2)は単一Entityのみ対応。実際: {len(ir.entities)}件"
            )
        entity = ir.entities[0]

        list_view = next((v for v in ir.views if v.kind == ViewKind.LIST and v.entity == entity.name), None)
        create_form_view = next(
            (v for v in ir.views if v.kind == ViewKind.FORM and v.entity == entity.name and v.mode == "create"), None
        )
        if list_view is None or create_form_view is None:
            raise ForgeLanguageCompilationError(
                f"Entity '{entity.name}' に対応するList ViewまたはForm View(create)が見つかりません"
            )
        # FORGE v0.8対応: 編集用View(mode="edit")。無ければCRUD無しの
        # 旧Phase1相当の出力(作成+一覧のみ)へ安全にフォールバックする
        # (`IRGenerator`は必ず生成するため通常発生しないが、防御的に
        # 「無ければ付けない」という後方互換な挙動にしている)。
        edit_form_view = next(
            (v for v in ir.views if v.kind == ViewKind.FORM and v.entity == entity.name and v.mode == "edit"), None
        )

        # `clamp_title()`でForge Languageの1〜80文字制約へ必ず収める
        # (`compiler.py`参照。会話由来の長いbuild_briefで、app.title・
        # screen.titleが上限超過してValidatorに落ちる実バグの修正)。
        safe_title = clamp_title(title)

        # 2026-08-12(CEO「常にニーズに合わせた最適解を出せるように
        # して」)対応: 以前はニーズが何であれ`_compile_single_screen()`
        # (3タブCRUD)へ直行していた。属性を1つしか持たないEntity
        # (「買うもの」だけ)にまで、釣果記録と同じ重さの道具を
        # 渡していたことになる。`select_solution_shape()`が、Entityの
        # 構造から解の形を決定的に選ぶ(`solution_shape.py`参照)。
        shape = select_solution_shape(entity)
        if shape is SolutionShape.CHECKLIST:
            return self._compile_checklist_screen(entity, safe_title, domain_category=domain_category)

        return self._compile_single_screen(
            entity, safe_title,
            include_crud=edit_form_view is not None, domain_category=domain_category,
            design_intent=design_intent,
        )

    def _compile_checklist_screen(
        self, entity: Entity, title: str, *, domain_category: str
    ) -> ForgeIRDocument:
        """CHECKLIST形(2026-08-12新設)。「並べて、消す」だけの道具。

        属性を1つ(または「文字列 + 済んだか」の2つ)しか持たない
        Entityに対して、タブもフォームも編集画面も作らず、
        **1画面・入力欄1つ・一覧1つ**へ畳み込む。

        Widget構成は`forge_ai/core/compiler.py`のChecklist経路と
        意図的に同じ形(`checklist` + `row[text_field, button]`)に
        している——この形はForge Language v1.0から存在し、Flutter
        Runtime・Validatorの双方で最も実績があるためである
        (新しいWidget構成を発明しない、という既存の方針)。

        `section_header`だけはv1.5の語彙を使い、「何のリストなのか」を
        画面上で示す(3タブ構成では`tab_titles`が担っていた役割)。
        """
        items_state_id = "items"
        new_item_state_id = "new_item_text"

        body = ForgeIRWidget(
            type="column",
            id="root_column",
            children=(
                ForgeIRWidget(
                    type="section_header", id="list_section_header",
                    properties={
                        "style_role": _ROLE_SECTION_HEADER,
                        "title": entity.label,
                        "subtitle": "思いついたら追加して、済んだらチェックしてください",
                    },
                ),
                ForgeIRWidget(
                    type="checklist", id="items_checklist",
                    properties={
                        "state_ref": items_state_id,
                        "empty_state_text": f"まだ{entity.label}がありません",
                    },
                ),
                ForgeIRWidget(
                    type="row", id="add_row",
                    children=(
                        ForgeIRWidget(
                            type="text_field", id="add_field",
                            properties={"state_ref": new_item_state_id, "placeholder": "追加する"},
                        ),
                        ForgeIRWidget(
                            type="button", id="add_button",
                            properties={
                                # その画面の主要操作。画面に1つだけ。
                                "style_role": _ROLE_PRIMARY_BUTTON,
                                "label": "追加",
                                "action": {
                                    "type": "add_item",
                                    "target_state_ref": items_state_id,
                                    "source_state_ref": new_item_state_id,
                                },
                            },
                        ),
                    ),
                ),
            ),
        )

        screen = ForgeIRScreen(
            id="generated_screen", title=title,
            state={
                items_state_id: ForgeIRStateValue(type="checklist", value=[]),
                new_item_state_id: ForgeIRStateValue(type="string", value=""),
            },
            body=body,
        )
        return ForgeIRDocument(
            # section_header(v1.5)・design_tokens(v1.5)を使うため。
            # RECORD_CRUD経路と揃えて"1.8"(上位互換)を宣言する。
            version="1.11",
            initial_screen_id=screen.id,
            screens=(screen,),
            app_title=title,
            # record_listを使わないため`record_schemas`は出力しない
            # (空dictはJSONへ出ない、`ForgeIRDocument.to_json_dict()`参照)。
            design_tokens=self._build_design_tokens(entity),
        )

    def _compile_single_screen(
        self, entity: Entity, title: str, *, include_crud: bool, domain_category: str,
        design_intent: "DesignIntent | None" = None,
    ) -> ForgeIRDocument:
        """FORGE v0.6でList View + Form Viewを単一画面へ変換する設計を
        導入し(モジュールdocstring参照)、FORGE v0.7で出力の中身を
        `record_list`/`record_list_view`/`add_record`ベースへ更新、
        FORGE v0.8で選択・更新・削除を追加、FORGE v1.0で視覚的階層
        (`section_header`)・Design Token・grid layoutを追加した。

        **v1.7での変更(2026-08-11、CEO「全て実装してくれ」対応)**:
        「追加」「一覧」「編集」を`divider`区切りで縦に積み上げる構成
        から、`tab_view`によるタブ切り替え構成へ変更した。複数
        `screens`によるNavigator画面遷移ではなく、あくまで単一画面・
        単一`ForgeRuntimeState`のまま表示だけをタブで切り替える
        (`WIDGET_TYPES_V1_7_ADDITIONS`のコメント参照: Runtime側が
        画面遷移のたびに独立したStateを生成する設計であるため、CRUDに
        必要な`records`の共有を画面をまたいで行うことができない、という
        Runtime側の制約を踏まえた判断)。
        """
        records_state_id = "records"
        selected_state_id = "selected"
        field_state_ids = {f.name: f"field_{f.name}" for f in entity.fields}
        edit_field_state_ids = {f.name: f"edit_field_{f.name}" for f in entity.fields}

        create_form_children, create_field_states = self._build_field_inputs(entity, field_state_ids)

        create_reset_actions = [{"type": "reset_state", "state_ref": sid} for sid in field_state_ids.values()]
        create_submit_action = {
            "type": "composite",
            "actions": [
                {
                    "type": "add_record",
                    "target_state_ref": records_state_id,
                    "field_bindings": dict(field_state_ids.items()),
                },
                *create_reset_actions,
            ],
        }

        create_tab = ForgeIRWidget(
            type="column", id="create_tab",
            children=(
                ForgeIRWidget(
                    type="section_header", id="create_section_header",
                    properties={
                        "style_role": _ROLE_SECTION_HEADER,"title": f"{entity.label}を追加", "subtitle": "必要な情報を入力してください"},
                ),
                ForgeIRWidget(
                    type="form",
                    id="record_form",
                    properties={"submit_label": "保存", "submit_action": create_submit_action},
                    children=tuple(create_form_children),
                ),
            ),
        )

        state: dict[str, ForgeIRStateValue] = {
            records_state_id: ForgeIRStateValue(
                type="record_list", value=[],
                # FORGE v0.9対応: record_listを、対応するrecord_schema
                # (Entity名をそのままSchema名にする)へ結びつける。
                schema_ref=entity.name,
            ),
        }
        state.update(create_field_states)

        # FORGE v1.0対応: Field数が少なくコンパクトなDomainはgrid、
        # それ以外は引き続きcard(モジュールdocstring参照)。
        list_layout = "grid" if domain_category in _GRID_PREFERRED_DOMAINS else "card"

        record_list_view_properties: dict[str, Any] = {
            "state_ref": records_state_id,
            "layout": list_layout,
            # FORGE v0.7対応: 全Field名を渡す(Phase2は主要Field
            # のみだった。IRのList View自体は元々全Fieldを意図
            # していたため、`ForgeLanguageCompiler`側の制約が
            # 解消された今、その意図をそのまま反映できる)。
            "display_fields": list(entity.field_names()),
            "empty_state_text": f"まだ{entity.label}がありません",
        }

        if include_crud:
            # FORGE v0.8対応: 選択を有効化する。選択されると、Runtimeが
            # `select_field_bindings`に従って編集用フィールドへ値を
            # 反映する(`forge_action_dispatcher.dart`参照)。
            record_list_view_properties["selectable"] = True
            record_list_view_properties["selected_state_ref"] = selected_state_id
            record_list_view_properties["select_field_bindings"] = dict(edit_field_state_ids.items())
            state[selected_state_id] = ForgeIRStateValue(type="selected_record", value=None)

        list_tab_children: list[ForgeIRWidget] = [
            ForgeIRWidget(
                type="record_list_view", id="records_list_view",
                # 面の扱いは**AIが選ぶ**（surface.card か surface.elevated か）。
                # 「全部を持ち上げると階層が消える」ので、持ち上げるかどうかは
                # 利用者のNeedから来る意味の判断であり、構造からは決まらない。
                properties={
                    **record_list_view_properties,
                    "style_role": _intent_role(design_intent, "list_surface", _ROLE_RECORD_LIST),
                },
            ),
        ]

        # v1.6新規: 数値Fieldを持つEntityは、一覧の直後にbar_chartを
        # 追加する(household_budgetの「収支をグラフで見たい」という
        # 既存の例文——`example_picker_sheet.dart`——を実現するための
        # 追加。数値Fieldを持たないEntityには何も追加しない)。
        # v1.11新規: 数値Fieldを持つEntityは、**一覧より前に**Hero KPIを
        # 置く（`metric_view`、FORGE-R1 / TD69）。
        #
        # 順序に意味がある。「今月の残高」を知りたい人は、一覧を読みたい
        # わけではない——**開いた瞬間に答えが目に入る**のが、家計簿を
        # 家計簿たらしめている部分である。一覧の下に置くと、それは
        # 「一覧のおまけの合計」になってしまう。
        hero_metric_widget = self._build_hero_metric_widget(entity, records_state_id)
        if hero_metric_widget is not None:
            list_tab_children.insert(0, hero_metric_widget)

        bar_chart_widget = self._build_bar_chart_widget(entity, records_state_id)
        if bar_chart_widget is not None:
            list_tab_children.append(bar_chart_widget)

        tab_titles = [f"{entity.label}を追加", f"{entity.label}一覧"]
        tabs = [create_tab, ForgeIRWidget(type="column", id="list_tab", children=tuple(list_tab_children))]

        if include_crud:
            edit_form_children, edit_field_states = self._build_field_inputs(
                entity, edit_field_state_ids, id_suffix="_edit_input"
            )
            state.update(edit_field_states)

            edit_reset_actions = [{"type": "reset_state", "state_ref": sid} for sid in edit_field_state_ids.values()]
            update_submit_action = {
                "type": "composite",
                "actions": [
                    {
                        "type": "update_record",
                        "target_state_ref": records_state_id,
                        "record_id_ref": selected_state_id,
                        "field_bindings": dict(edit_field_state_ids.items()),
                    },
                    *edit_reset_actions,
                    {"type": "reset_state", "state_ref": selected_state_id},
                ],
            }
            delete_action = {
                "type": "composite",
                "actions": [
                    {"type": "delete_record", "target_state_ref": records_state_id, "record_id_ref": selected_state_id},
                    *edit_reset_actions,
                    {"type": "reset_state", "state_ref": selected_state_id},
                ],
            }

            tab_titles.append(f"{entity.label}を編集")
            tabs.append(ForgeIRWidget(
                type="column", id="edit_tab",
                children=(
                    ForgeIRWidget(
                        type="section_header", id="edit_section_header",
                        properties={
                            "style_role": _ROLE_SECTION_HEADER,"title": f"{entity.label}を編集", "subtitle": "一覧からカードを選ぶと入力欄が埋まります"},
                    ),
                    ForgeIRWidget(
                        type="form",
                        id="record_edit_form",
                        properties={"submit_label": "更新", "submit_action": update_submit_action},
                        children=tuple(edit_form_children),
                    ),
                    ForgeIRWidget(
                        type="button",
                        id="record_delete_button",
                        # 削除は主要操作ではない。**state.dangerではなく
                        # button.secondary**——「危険」はActionの
                        # `destructive`が既に持っている事実であり、
                        # 意味を色で二重に持つと食い違ったときに直せない。
                        properties={
                            "style_role": _ROLE_SECONDARY_BUTTON,
                            "label": "削除", "action": delete_action,
                        },
                    ),
                ),
            ))

        body = ForgeIRWidget(
            type="tab_view", id="root_tabs",
            properties={
                "tab_titles": tab_titles,
                # 情報密度は**AIが選ぶ**。一覧中心か、じっくり読ませたいかは
                # 構造からは決まらない（同じCRUDでも、家計簿とジャーナルでは
                # 適切な密度が違う）。
                "style_role": _intent_role(design_intent, "screen_density", "density.normal"),
            },
            children=tuple(tabs),
        )
        screen = ForgeIRScreen(id="generated_screen", title=title, state=state, body=body)

        return ForgeIRDocument(
            # v1.8(2026-08-11、Widget Vocabulary Expansion第3弾):
            # sliderはv1.8専用のため(それ以前のWidgetは既に追加済み。
            # v1.8はいずれの上位互換、無変更)。
            version="1.11",
            initial_screen_id=screen.id,
            screens=(screen,),
            app_title=title,
            record_schemas={entity.name: self._build_record_schema(entity)},
            design_tokens=self._build_design_tokens(entity),
        )

    def _build_design_tokens(self, entity: Entity) -> dict[str, Any]:
        """FORGE v1.0新規(Product Quality Sprint1)。Entityの
        `visual_style`(IR層、プラットフォーム非依存)から、実際の
        Forge Language `design_tokens`(Flutter Runtime固有の描画
        情報)を選ぶ。未知の`visual_style`が来た場合は"calm"へ安全に
        フォールバックする(既存の「未知Widgetは安全にFallback」と
        同じ設計原則を、Design Tokenの選択にも適用したもの)。
        """
        return design_tokens_for_style(entity.visual_style)

    def _build_record_schema(self, entity: Entity) -> ForgeIRRecordSchema:
        """FORGE v0.9新規(Typed Record Runtime Phase1)。IRの`Entity.
        fields`(`ir_types.Field`、プラットフォーム非依存の型定義)を、
        Forge Language JSON向けの`ForgeIRSchemaField`へそのまま
        変換する(意味は変えない、表現形式だけJSON向けにする)。
        """
        schema_fields = tuple(
            ForgeIRSchemaField(
                name=f.name,
                type=f.type.value,
                label=f.label,
                required=f.required,
                options=f.choices,
            )
            for f in entity.fields
        )
        return ForgeIRRecordSchema(fields=schema_fields)

    def _build_field_inputs(
        self, entity: Entity, field_state_ids: dict[str, str], *, id_suffix: str = "_input"
    ) -> tuple[list[ForgeIRWidget], dict[str, ForgeIRStateValue]]:
        """Entityの各Fieldに対応する入力Widgetと、その初期stateの組を
        作る。作成用フォーム・編集用フォームの両方から呼ばれる、共有
        ロジック(指示書「コード重複よりも責務分離」に基づき、"何の
        Fieldがあるか"というロジック自体は共有しつつ、"作成用か編集用
        か"というstateの持ち方は呼び出し側で分離する)。

        FORGE v1.0(Workstream B.4)対応: `boolean`型のFieldのみ、
        `checkbox` Widget + `boolean`型stateを生成する(指示書「可能
        であれば既存checkbox Widgetを利用してください」)。これにより、
        boolean値は文字列を経由せず、Runtime全体を通して一貫して
        `bool`型のまま扱われる(パース不要)。

        **v1.6/v1.7での更新**: 当初は「Forge Languageへ新しいWidget型を
        追加しない」という制約(Widget Freeze)により、string/number/
        date/choiceはすべて`text_field`+`string`型stateへ落とし込んで
        いたが、CEO承認によりFreeze運用を解除して以降、choice型は
        `choice_field`(v1.6)、date型は`date_field`(v1.7)という専用
        Widgetを使うようになった(いずれも`string`型stateはそのまま
        再利用する、状態の持ち方自体は変えていない)。string/number型は
        引き続き`text_field`+`string`型stateのまま(Runtime側の
        `ForgeFieldValueParser`が型付き値へ変換する設計は無変更)。
        """
        children: list[ForgeIRWidget] = []
        field_states: dict[str, ForgeIRStateValue] = {}
        for f in entity.fields:
            state_id = field_state_ids[f.name]

            if f.type == FieldType.BOOLEAN:
                field_states[state_id] = ForgeIRStateValue(type="boolean", value=False)
                children.append(
                    ForgeIRWidget(
                        type="checkbox", id=f"{state_id}{id_suffix}",
                        properties={"state_ref": state_id, "label": f.label},
                    )
                )
                continue

            if f.type == FieldType.NUMBER and f.min_value is not None and f.max_value is not None:
                # v1.8新規(2026-08-11、CEO「壊れてる?って機能でもどんどん
                # 追加してくれ。あとでなおす。」対応)。上限・下限が
                # 決まっているNUMBER Field(例: reading_logの
                # 「評価(5段階)」)は、`slider`Widget(Flutter標準の
                # `Slider`)を使う。既存の"string"型stateではなく、
                # 既存の"number"型state(v1.2で追加済み)を直接使う——
                # `ForgeStateStore.addRecord()`は既にnumber型stateからの
                # 生の値読み取りに対応済みであることをRuntimeコード
                # (`forge_state_store.dart`)で確認済み。範囲外の値を
                # 構造的に入力できないため、他のNUMBER Fieldと違い
                # patternバリデーションのヒントは不要(`_build_field()`
                # 参照)。
                field_states[state_id] = ForgeIRStateValue(type="number", value=f.min_value)
                children.append(
                    ForgeIRWidget(
                        type="slider", id=f"{state_id}{id_suffix}",
                        properties={"state_ref": state_id, "label": f.label, "min": f.min_value, "max": f.max_value},
                    )
                )
                continue

            field_states[state_id] = ForgeIRStateValue(type="string", value="")

            validation_rules: list[dict[str, Any]] = [
                {"type": rule.type, "message": rule.message, **({"value": rule.value} if rule.value is not None else {})}
                for rule in f.validations
            ]

            if f.type == FieldType.CHOICE and f.choices:
                # FORGE-AI-QUALITY-001(2026-08-11、v1.6): TD33で
                # `text_field`のplaceholderへ選択肢を埋め込む応急処置を
                # していた(当時はForge Language Widget追加が凍結されて
                # いたため)。CEO承認によりFreeze運用を解除し、本来
                # 必要だった「決まった選択肢から選ばせる」ための専用
                # Widget(`choice_field`、Flutterの`DropdownButtonFormField`
                # で実装)を追加した。ユーザーが自由文字列を打鍵できない
                # ため、`ForgeFieldValueParser._parseChoice()`が要求する
                # 完全一致を、UIの構造そのもので保証できる(placeholderの
                # 文言に頼った応急処置より根本的)。
                field_properties: dict[str, Any] = {
                    "state_ref": state_id, "label": f.label, "options": list(f.choices),
                }
                children.append(
                    ForgeIRWidget(type="choice_field", id=f"{state_id}{id_suffix}", properties=field_properties)
                )
                continue

            if f.type == FieldType.DATE:
                # v1.7新規(2026-08-11、CEO「全て実装してくれ」対応):
                # TD33の「text_fieldのplaceholderへ『日付(YYYY-MM-DD)』
                # という書式のヒントを埋め込む」応急処置を、choice_field
                # (TD34)と同じ理由で専用Widgetへ置き換えた。
                # `showDatePicker()`(Flutter標準)によるカレンダーUIは、
                # 選んだ日付を常にISO 8601形式の文字列で返すため、
                # `ForgeFieldValueParser._parseDate()`が拒否する不正な
                # 入力(存在しない日付・区切り文字違い等)がそもそも
                # 発生しなくなる。
                children.append(
                    ForgeIRWidget(
                        type="date_field", id=f"{state_id}{id_suffix}",
                        properties={"state_ref": state_id, "label": f.label},
                    )
                )
                continue

            field_properties = {"state_ref": state_id, "placeholder": f.label}
            if validation_rules:
                field_properties["validation"] = {"rules": validation_rules}

            children.append(ForgeIRWidget(type="text_field", id=f"{state_id}{id_suffix}", properties=field_properties))
        return children, field_states

    def _build_hero_metric_widget(self, entity: Entity, records_state_id: str) -> ForgeIRWidget | None:
        """v1.11新規（FORGE-R1、TD69）。Entityが数値Fieldを持つ場合のみ、
        その合計を**画面で一番大きい単一の数値**として置く。

        ---

        ## なぜ合計なのか（平均でも件数でもなく）

        「今月いくら使ったか」「今月の残高」——数値Fieldを持つ記録型
        アプリで最初に知りたいのは、ほぼ常に**積み上がった量**である。
        平均は「1回あたり」を知りたいときの問いで、それは後から
        利用者が言えばよい（Revisionの仕事）。

        数値Fieldを持たないEntity（habit/todo/diary）には**何も置かない**。
        `bar_chart`と同じ判断で、「根拠のない集計を発明しない」。
        件数を出すことはできるが、「習慣が3件ある」は画面で一番大きく
        出すべき数値ではない。**出せるからといって出さない。**

        ## 値を決めない

        `metric.primary`が何pxで何色になるかはRuntimeが保証する。
        Compilerは「これは主KPIである」という意味だけを言う。
        """
        value_field = next((f for f in entity.fields if f.type == FieldType.NUMBER), None)
        if value_field is None:
            return None

        return ForgeIRWidget(
            type="metric_view", id="records_hero_metric",
            properties={
                "style_role": _ROLE_HERO_METRIC,
                "state_ref": records_state_id,
                "value_field": value_field.name,
                "aggregate": "sum",
                "label": f"{value_field.label}の合計",
                # まだ1件も無いときに 0 とだけ出ると「0円だ」という
                # **事実でない読み取り**を招く。記録が無いことを言う。
                "empty_text": "まだ記録がありません",
            },
        )

    def _build_bar_chart_widget(self, entity: Entity, records_state_id: str) -> ForgeIRWidget | None:
        """v1.6新規。Entityが数値Fieldを持つ場合のみ、一覧の直後に
        `bar_chart`(1 Record = 1本の棒、集計は行わないPhase1最小実装)を
        追加する。数値Fieldを持たないEntity(habit/todo/diary)は対象外
        (指示書「根拠のない集計を発明しない」と同じ精神: 描くものが
        無ければWidgetを増やさない)。

        `label_field`は、CHOICE型Field(例: household_budgetの
        `category`)があればそれを優先する(棒同士を区別する軸として
        最も自然)。無ければSTRING型、それも無ければ数値Field以外の
        最初のFieldを使う。
        """
        value_field = next((f for f in entity.fields if f.type == FieldType.NUMBER), None)
        if value_field is None:
            return None

        candidates = [f for f in entity.fields if f.name != value_field.name]
        label_field = (
            next((f for f in candidates if f.type == FieldType.CHOICE), None)
            or next((f for f in candidates if f.type == FieldType.STRING), None)
            or (candidates[0] if candidates else value_field)
        )

        return ForgeIRWidget(
            type="bar_chart", id="records_bar_chart",
            properties={
                # 集計して見せる面。**単一KPI(card.metric)ではない**
                # ——複数の値の内訳を示すので card.summary である。
                "style_role": _ROLE_SUMMARY_CHART,
                "state_ref": records_state_id,
                "value_field": value_field.name,
                "label_field": label_field.name,
                "title": f"{entity.label}の{value_field.label}",
            },
        )
