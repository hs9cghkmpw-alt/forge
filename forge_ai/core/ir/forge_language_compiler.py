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
"""

from __future__ import annotations

from typing import Any

from forge_ai.core.compiler import (
    ForgeIRDocument,
    ForgeIRRecordSchema,
    ForgeIRSchemaField,
    ForgeIRScreen,
    ForgeIRStateValue,
    ForgeIRWidget,
)
from forge_ai.core.ir.ir_types import Entity, FieldType, ForgeIR, ViewKind

# FORGE v1.0新規(Product Quality Sprint1)。Entityの`visual_style`
# (IR層、プラットフォーム非依存の「雰囲気」ヒント)から、実際の
# Forge Language `design_tokens`(色コード・角丸・余白という、Flutter
# Runtime固有の描画情報)への変換表。**具体的な色コードを選ぶという
# 判断はここ、Compiler層に閉じる**(IRはこの変換表の存在を知らない、
# ADR-012の方針)。
#
# 4種類という少数のプリセットに絞ったのは、`FORGE-PRODUCT-DESIGN-
# LAYER-PROPOSAL.md`3.4節の判断(「無限に多様な配色をAIが自由に生成
# するのではなく、品質が保証された少数の選択肢から選ぶ」)に基づく。
_DESIGN_TOKEN_PRESETS: dict[str, dict[str, Any]] = {
    "calm": {
        "color_scheme": {"primary": "#5B7C99", "secondary": "#8FA8BD", "success": "#6B9080", "error": "#C1666B"},
        "corner_radius": {"small": 8, "medium": 12, "large": 16},
        "spacing_scale": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
    },
    "warm": {
        "color_scheme": {"primary": "#D68C45", "secondary": "#E8B37A", "success": "#7A9D6F", "error": "#C1666B"},
        "corner_radius": {"small": 10, "medium": 16, "large": 24},
        "spacing_scale": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
    },
    "vibrant": {
        "color_scheme": {"primary": "#6366F1", "secondary": "#EC4899", "success": "#10B981", "error": "#EF4444"},
        "corner_radius": {"small": 12, "medium": 18, "large": 28},
        "spacing_scale": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
    },
    "neutral": {
        "color_scheme": {"primary": "#5C6470", "secondary": "#8A94A6", "success": "#4C9A6A", "error": "#B5493A"},
        "corner_radius": {"small": 6, "medium": 10, "large": 14},
        "spacing_scale": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
    },
}

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


class ForgeLanguageCompiler:
    """`ForgeIR` → `ForgeIRDocument`(Forge Language v1.3)。

    対象3 Domain(fishing_log/household_budget/habit_tracking)専用。
    現在の実装は、IRのList View 1件・Form View(create)1件・
    Form View(edit)1件・Entity 1件という構成(`IRGenerator`が今回
    生成する形)のみを想定する。IRがこれ以外の構成(複数Entity・
    Relationship等)を持つ場合は、今回のスコープ外として
    `ForgeLanguageCompilationError`を送出する。
    """

    def compile(self, ir: ForgeIR, *, domain_category: str, title: str) -> ForgeIRDocument:
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

        return self._compile_single_screen(
            entity, title, include_crud=edit_form_view is not None, domain_category=domain_category
        )

    def _compile_single_screen(
        self, entity: Entity, title: str, *, include_crud: bool, domain_category: str
    ) -> ForgeIRDocument:
        """FORGE v0.6でList View + Form Viewを単一画面へ変換する設計を
        導入し(モジュールdocstring参照)、FORGE v0.7で出力の中身を
        `record_list`/`record_list_view`/`add_record`ベースへ更新、
        FORGE v0.8で選択・更新・削除を追加、FORGE v1.0で視覚的階層
        (`section_header`)・Design Token・grid layoutを追加した。
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

        # FORGE v1.0対応: 単一画面を「意味のある情報のまとまり」へ区切る
        # (指示書「単純なColumnではなく、意味のある情報のまとまりとして
        # 構成する」)。`section_header`はいずれも状態を持たない表示専用
        # Widgetであり、CRUD挙動には一切影響しない。
        body_children: list[ForgeIRWidget] = [
            ForgeIRWidget(
                type="section_header", id="create_section_header",
                properties={"title": f"{entity.label}を追加", "subtitle": "必要な情報を入力してください"},
            ),
            ForgeIRWidget(
                type="form",
                id="record_form",
                properties={"submit_label": "保存", "submit_action": create_submit_action},
                children=tuple(create_form_children),
            ),
            ForgeIRWidget(type="divider", id="form_list_divider"),
        ]

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

        body_children.extend([
            ForgeIRWidget(
                type="section_header", id="list_section_header",
                properties={"title": f"{entity.label}一覧"},
            ),
            ForgeIRWidget(type="record_list_view", id="records_list_view", properties=record_list_view_properties),
        ])

        # v1.6新規: 数値Fieldを持つEntityは、一覧の直後にbar_chartを
        # 追加する(household_budgetの「収支をグラフで見たい」という
        # 既存の例文——`example_picker_sheet.dart`——を実現するための
        # 追加。数値Fieldを持たないEntityには何も追加しない)。
        bar_chart_widget = self._build_bar_chart_widget(entity, records_state_id)
        if bar_chart_widget is not None:
            body_children.append(bar_chart_widget)

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

            body_children.extend([
                ForgeIRWidget(type="divider", id="list_edit_divider"),
                ForgeIRWidget(
                    type="section_header", id="edit_section_header",
                    properties={"title": f"{entity.label}を編集", "subtitle": "一覧からカードを選ぶと入力欄が埋まります"},
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
                    properties={"label": "削除", "action": delete_action},
                ),
            ])

        body = ForgeIRWidget(type="column", id="root_column", children=tuple(body_children))
        screen = ForgeIRScreen(id="generated_screen", title=title, state=state, body=body)

        return ForgeIRDocument(
            # v1.6(2026-08-11、Widget Vocabulary Expansion): choice_field/
            # bar_chartはv1.6専用のため(design_tokens/section_header/
            # layout:"grid"は既にv1.5で追加済み、record_schemas/
            # schema_refはv1.4で追加済み。v1.6はいずれの上位互換、
            # 無変更)。
            version="1.6",
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
        preset = _DESIGN_TOKEN_PRESETS.get(entity.visual_style, _DESIGN_TOKEN_PRESETS["calm"])
        return {
            "color_scheme": dict(preset["color_scheme"]),
            "corner_radius": dict(preset["corner_radius"]),
            "spacing_scale": dict(preset["spacing_scale"]),
        }

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
        `bool`型のまま扱われる(パース不要)。それ以外の型
        (string/number/date/choice)は、既存Widget構成(`text_field`+
        `string`型state)を維持する——Forge Languageへ新しいWidget型を
        追加しないという指示書の制約により、これらの型は文字列として
        入力を受け、Runtime側(`ForgeFieldValueParser`)が型付き値へ
        変換する設計にした(4.2節`FORGE-IR-V1-PROPOSAL.md`と同じ、
        「新しい式言語は導入せず、既存の仕組みの範囲で実現する」という
        方針の踏襲)。
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

            placeholder = f.label
            if f.type == FieldType.DATE:
                # TD33参照: `ForgeFieldValueParser._parseDate()`はISO 8601
                # (YYYY-MM-DD)の厳密一致を要求するため、送信前に形式を
                # 示す(dateはchoice_fieldのような専用Widgetをまだ持たない
                # ため、この応急処置は維持する)。
                placeholder = f"{f.label}(YYYY-MM-DD)"

            field_properties = {"state_ref": state_id, "placeholder": placeholder}
            if validation_rules:
                field_properties["validation"] = {"rules": validation_rules}

            children.append(ForgeIRWidget(type="text_field", id=f"{state_id}{id_suffix}", properties=field_properties))
        return children, field_states

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
                "state_ref": records_state_id,
                "value_field": value_field.name,
                "label_field": label_field.name,
                "title": f"{entity.label}の{value_field.label}",
            },
        )
