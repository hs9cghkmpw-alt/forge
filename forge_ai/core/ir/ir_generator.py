"""IRGenerator(FORGE IR v1、Phase2、最小実装。
FORGE v0.8でCRUD(Update/Delete)分を拡張、
FORGE v1.0でField型付けを本格化(Workstream A/G))。

`ApplicationPlan`と`domain_category`を入力として、対象3 Domain
(fishing_log/household_budget/habit_tracking)分の`ForgeIR`を決定的に
生成する。`FORGE-IR-V1-PROPOSAL.md`6章のPhase2に対応する。

**Template-aware Compiler Stage1からの移設**: `forge_ai/core/
compiler.py`にあった`DomainField`・`DomainDataModel`・
`_DOMAIN_DATA_MODELS`は、責務を整理した上でこのモジュールへ移した
(それぞれ IR層の`Field`・Entity定義・Domain登録表に相当する概念
だったため)。`compiler.py`側の該当コードは削除済み。

**対象外Domainについて**: `generate_ir()`は、登録されていない
`domain_category`に対しては`None`を返す(例外にしない)。呼び出し側
(`pipeline_orchestrator.py`)は、`None`が返った場合、既存の
`Compiler`(Checklist単一画面)へフォールバックする。

**FORGE v0.8(Record Runtime Phase2)での拡張**: `update_<entity>`・
`delete_<entity>` Actionと、編集用View(`mode="edit"`のForm View)を
追加した。**「選択(select)」はIRのActionKindへ追加していない**
(意図的な設計判断、下記参照)。

`ActionKind`(既存、`ir_types.py`)に`SELECT_ENTITY`を追加しなかった
理由: 「選択中の1件をどう保持するか」は、Forge Language/Flutter
Runtimeが採用する状態管理方式(フラットなstate store)に起因する、
**このターゲット固有の実装詳細**である。IRは「Recordを更新できる」
「Recordを削除できる」という、どのプラットフォームでも共通に成立する
意味だけを表現し(ADR-010・ADR-012の方針)、「更新・削除のために
まず選択状態をどう表現するか」は`ForgeLanguageCompiler`側の裁量に
委ねる。React等の将来のCompiler Backendは、選択状態を持たず
ルーティング(詳細ページへの遷移)で同じ意味を実現するかもしれない
——IRはどちらの実現方法も等しく許容できる抽象度に留める。

**FORGE v1.0(Workstream A: IR Architecture Audit)で発見・修正した
問題**:

1. `_FieldSpec`が`is_numeric: bool`という「型のあるような無いような」
   影の型情報を持っていた。`FieldType`という正式な列挙型が既に
   `ir_types.py`に存在するにもかかわらず、それを経由せず`bool`から
   `NUMBER`/`STRING`の2値だけを導出しており、`FieldType`という
   Source of Truthと、この`bool`という**もう1つの実質的な
   Source of Truth**が並存していた(監査で発見した重複)。今回、
   `_FieldSpec`が`FieldType`を直接持つように修正し、`bool`による
   影の型判定を廃止した。
2. `primary_field_for()`・`_EntitySpec.primary_field`が、実際には
   どこからも呼ばれていない**死んだコード**だった(Template-aware
   Compiler Stage1時代、`record_list_view`が主要Fieldしか表示できな
   かった頃の名残。FORGE v0.7で全Field表示に切り替わって以降、
   `forge_language_compiler.py`は一度もこれを参照していない)。
   「参照されなくなった意味情報が、あたかも現役のSource of Truthで
   あるかのように残り続ける」のは監査で最も見つけたかった種類の
   問題そのものだったため、削除した(該当テストも削除)。

**発見したが変更しなかった点**: `FieldValidationRule`(IR層)が
Forge Language v1.2の`validation.rules`と同じ語彙
(required/min/max/pattern等)を再利用している点は、`ir_types.py`の
docstringで既に意図的な設計として明記されており、Forge Language
固有の情報がIRへ侵入した結果ではなく、「検証ルールの語彙をIR/Forge
Language間で共有する」という文書化済みの判断だったため、変更して
いない。
"""

from __future__ import annotations

from forge_ai.core.ir.ir_types import (
    Action,
    ActionKind,
    Entity,
    Event,
    EventTrigger,
    Field,
    FieldType,
    FieldValidationRule,
    ForgeIR,
    NavigationGraph,
    View,
    ViewKind,
)
from forge_ai.core.planner import ApplicationPlan


class _FieldSpec:
    """Entity定義を書く際の内部シンタックスシュガー(モジュール外へは
    公開しない)。`_ENTITY_DEFINITIONS`の記述を簡潔にするためだけの
    もので、IRそのものではない(IRは`ir_types.Field`)。

    FORGE v1.0対応: `is_numeric: bool`(影の型情報、監査で発見)を廃止し、
    `field_type: FieldType`を直接持つように変更した。
    """

    __slots__ = ("name", "label", "field_type", "required", "choices", "min_value", "max_value")

    def __init__(
        self,
        name: str,
        label: str,
        *,
        field_type: FieldType = FieldType.STRING,
        required: bool = True,
        choices: tuple[str, ...] = (),
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> None:
        self.name = name
        self.label = label
        self.field_type = field_type
        self.required = required
        self.choices = choices
        # v1.8新規。両方指定された場合のみForge Language Compilerが
        # `slider`Widgetを選ぶ(`ir_types.Field`のdocコメント参照)。
        self.min_value = min_value
        self.max_value = max_value


class _EntitySpec:
    __slots__ = ("name", "label", "field_specs", "visual_style")

    def __init__(
        self, name: str, label: str, field_specs: tuple[_FieldSpec, ...], *, visual_style: str = "calm"
    ) -> None:
        self.name = name
        self.label = label
        self.field_specs = field_specs
        # FORGE v1.0(Product Quality Sprint1)新規。このDomainの
        # 「雰囲気・トーン」を表す、プラットフォーム非依存な性質
        # (具体的な色コードやWidget名はIRに含めない、ADR-012の方針を
        # 維持しつつ、抽象的な"温かみ"や"落ち着き"はどのプラット
        # フォームでも意味を持つ性質としてIRへ格上げした)。実際に
        # `ir_types.Entity.visual_style`へそのまま渡され、
        # `ForgeLanguageCompiler`がDesign Tokenプリセット・一覧の
        # レイアウト(card/grid)を選ぶ材料として使う。
        self.visual_style = visual_style


# FORGE v0.6対応: Template-aware Compiler Stage1の`_DOMAIN_DATA_MODELS`
# から移設(内容は同一、`entity_name`→小文字snake_caseの`name`+
# 表示用`label`の2つへ分離した点のみ変更)。
#
# FORGE v1.0(Workstream G)対応: 各FieldへFieldTypeを設定した。
#
# 「写真」フィールド(指示書のFishRecord例に含まれる)は、Forge Runtimeに
# 画像アップロード用Widgetが存在しないため、今回も対象外とした
# (`lexicon.py`の"写真"非対応コメントと同じ理由による意図的な省略)。
#
# **choice型の採用方針(指示書「根拠のないchoice optionsをCompilerが
# 勝手に発明しないでください」への対応)**: 今回、`household_budget`の
# `category`のみをchoice型にした。根拠は、`forge_ai/core/compiler.py`
# の`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT["transaction"]`(FORGE_v0.2 P3で
# 導入、既存コードに実在する)が`("食費", "交通費", "娯楽")`という
# 具体的なカテゴリ例を既に持っていたため、これを「Template/
# ApplicationPlanに既に存在する選択肢」とみなした。`species`
# (魚種)には対応する既存の選択肢データが無いため、string型のまま
# 維持した(架空のoptionsを発明していない)。
#
# **新規追加したField(`date`・`completed`)について**: 指示書
# Workstream Gの例に沿い、時間的な性質を持つ`fishing_log`・
# `household_budget`へ`date`(date型、任意)を追加し、`habit_tracking`
# へは「その日達成したか」を表す`completed`(boolean型、任意)を追加
# した。理由: (1)指示書が明示的にこれらのField追加を例示している、
# (2)`boolean`型を実際にどのDomainも使っていなかった状態を解消し、
# Workstream B〜Dの型別実装(number/boolean/date/choice)を3 Domain
# 全体で実際に検証できるようにするため。`habit_tracking`の既存Field
# 名(`name`)を`habit_name`へ改名する等の、指示書の例に見られる
# その他の変更は、既存Field名の変更が既存テスト・既存生成結果との
# 互換性を不必要に壊すため、今回は行っていない(指示書「小さなコード
# 量より、一貫性・後方互換性・検証可能性を優先」に基づく判断)。
_ENTITY_DEFINITIONS: dict[str, _EntitySpec] = {
    "fishing_log": _EntitySpec(
        name="fish_record",
        label="釣果記録",
        visual_style="neutral",
        field_specs=(
            _FieldSpec("species", "魚種", field_type=FieldType.STRING),
            _FieldSpec("size", "サイズ(cm)", field_type=FieldType.NUMBER, required=False),
            _FieldSpec("weight", "重量(g)", field_type=FieldType.NUMBER, required=False),
            _FieldSpec("location", "場所", field_type=FieldType.STRING, required=False),
            _FieldSpec("date", "日付", field_type=FieldType.DATE, required=False),
        ),
    ),
    "household_budget": _EntitySpec(
        name="transaction",
        label="家計簿記録",
        visual_style="calm",
        field_specs=(
            _FieldSpec(
                "category", "カテゴリ", field_type=FieldType.CHOICE,
                choices=("食費", "交通費", "娯楽", "その他"),
            ),
            _FieldSpec("amount", "金額", field_type=FieldType.NUMBER, required=True),
            _FieldSpec("date", "日付", field_type=FieldType.DATE, required=False),
            _FieldSpec("payment_method", "支払方法", field_type=FieldType.STRING, required=False),
        ),
    ),
    "habit_tracking": _EntitySpec(
        name="habit",
        label="習慣記録",
        visual_style="vibrant",
        field_specs=(
            _FieldSpec("name", "名称", field_type=FieldType.STRING),
            _FieldSpec("goal", "目標", field_type=FieldType.STRING, required=False),
            _FieldSpec("completed", "達成済み", field_type=FieldType.BOOLEAN, required=False),
            _FieldSpec("date", "日付", field_type=FieldType.DATE, required=False),
        ),
    ),
    # FORGE v1.0(Product Quality Sprint1)新規: Curated Domain
    # Libraryの初期拡張(`FORGE-PRODUCT-DESIGN-LAYER-PROPOSAL.md`
    # 3.5節「①Curated Domain Library」)。以下4 Domainは、指示書が
    # 明示的に対象として挙げた「TODO/reading_log/inventory/diary」に
    # 対応する。いずれも、指示書の制約「根拠のないchoice optionsを
    # 発明しない」は、**Compilerが実行時に発明すること**を禁じたもので
    # あり、この場でCurated Domain Libraryそのものを人手で設計する
    # (=このモジュール自体を書く)ことは、その制約が想定する行為とは
    # 異なる(既存3 Domainの`household_budget.category`と同じ位置づけ:
    # 人手で丁寧に設計したcurated optionsである)。
    "todo": _EntitySpec(
        name="todo_item",
        label="TODO",
        visual_style="vibrant",
        field_specs=(
            _FieldSpec("title", "やること", field_type=FieldType.STRING),
            _FieldSpec(
                "priority", "優先度", field_type=FieldType.CHOICE,
                choices=("高", "中", "低"), required=False,
            ),
            _FieldSpec("due_date", "期限", field_type=FieldType.DATE, required=False),
            _FieldSpec("completed", "完了", field_type=FieldType.BOOLEAN, required=False),
        ),
    ),
    "reading_log": _EntitySpec(
        name="book_record",
        label="読書記録",
        visual_style="warm",
        field_specs=(
            _FieldSpec("title", "書名", field_type=FieldType.STRING),
            _FieldSpec("author", "著者", field_type=FieldType.STRING, required=False),
            _FieldSpec(
                "status", "状況", field_type=FieldType.CHOICE,
                choices=("読みたい", "読書中", "読了"), required=False,
            ),
            _FieldSpec(
                "rating", "評価(5段階)", field_type=FieldType.NUMBER, required=False,
                # v1.8新規: 「5段階」という既存のlabelそのものが根拠と
                # なる、具体的な範囲(1〜5)。Compilerがこれを見て
                # `slider`Widgetを選ぶ(構造的に範囲外の値を入力できない)。
                min_value=1, max_value=5,
            ),
            _FieldSpec("finished_date", "読了日", field_type=FieldType.DATE, required=False),
        ),
    ),
    "inventory": _EntitySpec(
        name="inventory_item",
        label="在庫記録",
        visual_style="neutral",
        field_specs=(
            _FieldSpec("item_name", "品名", field_type=FieldType.STRING),
            _FieldSpec("quantity", "数量", field_type=FieldType.NUMBER, required=True),
            _FieldSpec(
                "category", "カテゴリ", field_type=FieldType.CHOICE,
                choices=("食品", "日用品", "衣類", "その他"), required=False,
            ),
            _FieldSpec("expiry_date", "期限日", field_type=FieldType.DATE, required=False),
            _FieldSpec("location", "保管場所", field_type=FieldType.STRING, required=False),
        ),
    ),
    "diary": _EntitySpec(
        name="diary_entry",
        label="日記",
        visual_style="warm",
        field_specs=(
            _FieldSpec("title", "タイトル", field_type=FieldType.STRING, required=False),
            _FieldSpec("content", "本文", field_type=FieldType.STRING),
            _FieldSpec(
                "mood", "気分", field_type=FieldType.CHOICE,
                choices=("嬉しい", "普通", "悲しい", "怒り", "疲れた"), required=False,
            ),
            _FieldSpec("date", "日付", field_type=FieldType.DATE, required=False),
        ),
    ),
}

_NUMERIC_PATTERN = r"^-?[0-9]+(\.[0-9]+)?$"
# FORGE v1.0新規: ISO 8601日付(YYYY-MM-DD)の書式チェック(実在する日付かは
# Forge Languageのpatternでは検査できないため、Runtime側のParserが担う。
# ここではあくまで「書式」だけを軽く絞り込む、Form入力時の一次的な補助)。
_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class IRGenerator:
    """`ApplicationPlan`(+`domain_category`)から`ForgeIR`を決定的に
    生成する。副作用・状態を持たない(インスタンスメソッドは全て純粋
    関数)。"""

    def generate(self, plan: ApplicationPlan, *, domain_category: str) -> ForgeIR | None:
        """`domain_category`が対象3 Domainのいずれでもない場合は`None`
        を返す(例外にしない、呼び出し側がフォールバック判断できる
        ようにするため)。

        `plan`は現時点では実質的に未使用(Entity定義は`domain_category`
        だけから決定的に導出できるため)。将来、`plan`の内容(例:
        `unassigned_requirements`)をIR生成へ反映する拡張の余地として、
        引数自体は残している。
        """
        spec = _ENTITY_DEFINITIONS.get(domain_category)
        if spec is None:
            return None
        return self._build_ir(spec)

    def _build_ir(self, spec: _EntitySpec) -> ForgeIR:
        fields = tuple(self._build_field(fs) for fs in spec.field_specs)
        entity = Entity(name=spec.name, label=spec.label, fields=fields, visual_style=spec.visual_style)

        list_view = View(
            id=f"{spec.name}_list",
            kind=ViewKind.LIST,
            entity=spec.name,
            display_fields=entity.field_names(),
        )
        form_view = View(
            id=f"{spec.name}_form",
            kind=ViewKind.FORM,
            entity=spec.name,
            mode="create",
        )
        # FORGE v0.8対応: 編集用View(`mode="edit"`)。Phase2の制約
        # (record_detail・multi screenは対象外)により、これも
        # List View/Form Viewと同じく最終的には単一画面へ畳み込まれる
        # (`ForgeLanguageCompiler`側の判断、モジュールdocstring参照)。
        edit_form_view = View(
            id=f"{spec.name}_edit_form",
            kind=ViewKind.FORM,
            entity=spec.name,
            mode="edit",
        )

        create_action = Action(id=f"create_{spec.name}", kind=ActionKind.CREATE_ENTITY, entity=spec.name)
        update_action = Action(id=f"update_{spec.name}", kind=ActionKind.UPDATE_ENTITY, entity=spec.name)
        delete_action = Action(id=f"delete_{spec.name}", kind=ActionKind.DELETE_ENTITY, entity=spec.name)

        submit_event = Event(
            id=f"on_{spec.name}_form_submit",
            trigger=EventTrigger.SUBMIT,
            source_view=form_view.id,
            action=create_action.id,
        )
        edit_submit_event = Event(
            id=f"on_{spec.name}_edit_form_submit",
            trigger=EventTrigger.SUBMIT,
            source_view=edit_form_view.id,
            action=update_action.id,
        )
        # FORGE v0.8対応: 「一覧の1件をタップして削除する」という意図を、
        # List ViewからDELETE_ENTITY Actionへ直接結びつけるEventとして
        # 表現する(「編集する」は一旦Edit Formを経由するのに対し、
        # 「削除する」は一覧から直接、という非対称性はIntent/UXの自然な
        # 違いを反映したものであり、Forge Language側の実装都合ではない)。
        delete_event = Event(
            id=f"on_{spec.name}_list_delete",
            trigger=EventTrigger.TAP,
            source_view=list_view.id,
            action=delete_action.id,
        )

        # FORGE v0.6対応: 現在のForge Language Compilerは、List View/
        # Form Viewを単一画面へ畳み込むため(Proposal 3.3節)、画面間の
        # 実際の遷移(edges)は不要。`initial_view`は一覧側とする
        # (一覧+フォームが1画面にまとまるため、どちらを起点にしても
        # 実質的な違いは無いが、「まず何が見えるか」という意図を表す
        # ため一覧側を選んだ)。
        navigation = NavigationGraph(initial_view=list_view.id, edges=())

        ir = ForgeIR(
            entities=(entity,),
            views=(list_view, form_view, edit_form_view),
            actions=(create_action, update_action, delete_action),
            events=(submit_event, edit_submit_event, delete_event),
            navigation=navigation,
        )

        # 決定的生成であっても、参照整合性が崩れていれば早期に気づける
        # ようにする(このIRGenerator自身のバグを、呼び出し側より先に
        # 検出するための内部的な安全策)。
        errors = ir.referential_integrity_errors()
        if errors:
            raise AssertionError(f"IRGenerator produced an internally inconsistent ForgeIR: {errors}")

        return ir

    def _build_field(self, spec: _FieldSpec) -> Field:
        has_slider_bounds = spec.field_type == FieldType.NUMBER and spec.min_value is not None and spec.max_value is not None
        validations: list[FieldValidationRule] = []
        if spec.required:
            validations.append(FieldValidationRule(type="required", message=f"{spec.label}を入力してください"))
        if spec.field_type == FieldType.NUMBER and not has_slider_bounds:
            # v1.8新規: min_value/max_valueが両方揃っているFieldは
            # `slider`Widgetになる(構造的に範囲外の値を入力できない
            # ため、choice_field/date_fieldと同じ理由でこのヒントが
            # 不要になる)。それ以外のNUMBER Fieldは従来通り。
            validations.append(
                FieldValidationRule(
                    type="pattern", value=_NUMERIC_PATTERN, message=f"{spec.label}は数字で入力してください"
                )
            )
        elif spec.field_type == FieldType.DATE:
            validations.append(
                FieldValidationRule(
                    type="pattern", value=_DATE_PATTERN,
                    message=f"{spec.label}はYYYY-MM-DD形式で入力してください",
                )
            )
        return Field(
            name=spec.name,
            label=spec.label,
            type=spec.field_type,
            required=spec.required,
            choices=spec.choices,
            validations=tuple(validations),
            min_value=spec.min_value,
            max_value=spec.max_value,
        )


# 対象Domainの一覧(呼び出し側が「この3 Domainが対象である」ことを
# 判定するために使う、`pipeline_orchestrator.py`から参照される)。
SUPPORTED_DOMAIN_CATEGORIES: frozenset[str] = frozenset(_ENTITY_DEFINITIONS.keys())
