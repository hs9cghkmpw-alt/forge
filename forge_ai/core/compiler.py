"""Compiler。

Planner結果(ApplicationPlan)から Forge IR を生成する。
Forge IRは、Forge Runtimeの実際のJSON形式(shared/schemas/ui_schema.v1*.json)と
互換な形へ`to_json_dict()`でシリアライズできる、forge_ai/自身が定義する
中間表現である。forge_ai/はBackend/Runtimeの実装(schema_validator.py・
Dart Runtime)を一切importしない(Provider Independence / Runtime非依存の方針。
禁止事項参照)。あくまで「同じ語彙・同じ形」を独自に(手動同期で)守っている。

現時点でのCompilerは、Application Planを「チェックリスト形式の1画面」へ
決定的に変換する(Forge Language側で最も実績のあるTemplateと同じ形)。
これはCompilerの最終形ではなく、Runtime接続後の拡張ポイントとして
IMPLEMENTATION_REPORT.mdに明記する。

**FORGE v0.6対応(FORGE IR v1 Phase2導入に伴う変更)**: Template-aware
Compiler Stage1(FORGE v0.3)で、このクラスへ一時的に追加した
`DomainField`・`DomainDataModel`・`_DOMAIN_DATA_MODELS`・
`_compile_record_template()`は、`FORGE-IR-V1-PROPOSAL.md`の設計に基づき、
`forge_ai/core/ir/`パッケージ(`ir_generator.py`・
`forge_language_compiler.py`)へ責務ごと移設した。このクラス
(`Compiler`)自体は、以前(Stage1導入前)と同じ「ApplicationPlanを
Checklist単一画面へ変換する」という単一の責務へ戻している。

対象3 Domain(fishing_log/household_budget/habit_tracking)は、
`pipeline_orchestrator.py`側で`forge_ai.core.ir.IRGenerator`→
`forge_ai.core.ir.ForgeLanguageCompiler`という別経路へ振り分けられる
ため、この`Compiler`クラスへは到達しない(呼ばれても`domain_category`
は無視され、常にChecklist単一画面を返す。既存呼び出し元との後方互換の
ためにパラメータ自体は残している)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge_ai.core.planner import ApplicationPlan
from forge_ai.prompt.prompt_builder import PromptBuilder
from forge_ai.provider.provider_interface import AIProvider

# FORGE_v0.2_修正指示.md P3(可能なら)対応:
# 「item / price / quantity のような内部の概念識別子ではなく、ユーザーが
# 完成品と感じられる初期データ(牛乳・卵・パン等)にしてほしい」という
# 指摘への対応。
#
# **設計上の制約(正直な申告)**: `ApplicationPlan`はDomainへの参照を
# 持たない(「CompilerはRuntime/Domainを知らない」という既存の設計原則、
# ファイル冒頭の説明を参照)。そのため、Domainを正式に注入する形には
# せず、`primary_screen.key_elements`の**先頭要素**(Planner・World
# Model構築の過程で、実質的にその画面の「主役となる概念」が先頭に来る
# ことが多い、既存の並び順の性質を利用)が、既知の概念識別子と一致する
# 場合にのみ、複数件の現実的な例値へ置き換える。
#
# **既知の制限**: これは`item`のような単一概念が複数件(牛乳・卵・パン)
# 存在するChecklist的なDomain(Shopping・Task management等)には自然に
# 合うが、「item/price/quantity/store」のように、本来は1件のデータが
# 複数の属性(価格・数量・店舗)を持つ構造(Formに近い)を、Checklistの
# 複数行として扱ってしまっている、より根本的な設計上の制約自体は
# 解決していない(FORGE IR v1導入対象の3 Domainについては、
# `forge_ai/core/ir/`側で解消している)。
_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT: dict[str, tuple[str, ...]] = {
    "item": ("牛乳", "卵", "パン"),
    "task": ("買い物に行く", "部屋を掃除する", "メールを返信する"),
    "entry": ("今日は良い一日でした",),
    "stock": ("在庫アイテムA", "在庫アイテムB"),
    "transaction": ("食費", "交通費", "娯楽"),
    "event": ("定例ミーティング",),
    "question": ("最初の質問",),
    "child": ("体重測定", "身長測定"),
    "measurement": ("体重測定", "身長測定"),
    "catch": ("アジ", "サバ", "カレイ"),
    "habit": ("水を飲む", "運動", "読書"),
    "subject": ("英語", "資格試験の勉強", "読書"),
    "destination": ("京都旅行", "沖縄旅行", "温泉旅行"),
    # FORGE-AI-CONNECT-001 TD24対応(2026-08-11)。「旅行の持ち物
    # チェックリストを作って」がprimary_conceptとして"belongings"を
    # 選ぶようになった(application_planner.pyの
    # `_prioritize_explicitly_mentioned_concepts`参照)ことで、この
    # テーブルに無い場合のraw fallback(内部識別子がそのまま漏れる、
    # `test_success_cases_do_not_leak_raw_concept_identifiers_as_initial_items`
    # が実際に検出した)が発生することが分かったため追加した。
    "belongings": ("パスポート", "着替え", "歯ブラシ", "充電器"),
    # FORGE-AI-QUALITY-001(2026-08-11)対応。`application_planner.py`の
    # `_prioritize_primary_candidate_concepts()`一般化により、travel
    # domainで"destination"以外の概念("accommodation"・"itinerary")も
    # 明示的な言及があれば主役として選ばれうるようになった(例:
    # 「ホテルと観光地を管理したい」)。上記"belongings"と同じ理由
    # (テーブルに無い場合のraw識別子漏れ、Golden Testが実際に検出した)
    # で追加した。"expense"は現時点のGolden Testでは主役に選ばれる
    # ケースが無いが、将来同様の言及パターンで選ばれた場合に備え、
    # 念のため合わせて登録しておく。
    "accommodation": ("京都グランドホテル", "民宿さくら"),
    "itinerary": ("1日目: 清水寺観光", "2日目: 嵐山散策"),
    "expense": ("宿泊費", "交通費", "食費"),
}


# FORGE v1.0新規(Product Quality Sprint1)。色・角丸・余白のプリセット表。
# 元々`forge_ai/core/ir/forge_language_compiler.py`だけが持っていたが、
# FORGE-PRODUCT-VISION-002(2026-08-12、CEO「アプリストアレベルの品質に
# するにはどうすればいいか」対応)で、このモジュール(`Compiler`、
# legacy Checklist経路)にも同じテーマ適用を広げるにあたり、単一の定義元
# としてこちらへ移動した(`forge_language_compiler.py`は既にこの
# モジュールをimportしているため、逆方向のimportは循環importになる。
# 詳細はTECH_DEBT.md TD44)。
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

# FORGE-PRODUCT-VISION-002(2026-08-12)新規。legacy Checklist経路
# (`Compiler.compile()`)は`forge_ai/core/ir/ir_generator.py`の
# `_ENTITY_DEFINITIONS`のようなDomainごとの手作りEntity定義を持たない
# ため、`Entity.visual_style`を経由できない。代わりに`domain_category`
# (文字列)から直接visual_styleを選ぶ、同種の少数プリセット方式にする。
#
# 7 Curated Domain(fishing_log/household_budget/habit_tracking/todo/
# reading_log/inventory/diary)分の値は、`ir_generator.py`の
# `_ENTITY_DEFINITIONS[...].visual_style`と意図的に一致させている
# (todo/reading_logはTD39の分類バグにより現状この経路へ実際には到達
# しないが、TD39が解消された場合に見た目が変わらないようにするため)。
# 残り10 DomainはCurated Domain Libraryの対象外(引き続きこの
# `Compiler`のChecklist/Form経路を使う)であり、今回新たに割り当てた。
_VISUAL_STYLE_BY_DOMAIN_CATEGORY: dict[str, str] = {
    "fishing_log": "neutral",
    "household_budget": "calm",
    "habit_tracking": "vibrant",
    "todo": "vibrant",
    "reading_log": "warm",
    "inventory": "neutral",
    "diary": "warm",
    "shopping": "warm",
    "hospital": "calm",
    "attendance": "neutral",
    "task_management": "vibrant",
    "survey": "neutral",
    "schedule": "calm",
    "child_growth": "warm",
    "study": "vibrant",
    "travel": "warm",
    "generic": "calm",
}


# Forge Language の `app.title`・`screen.title` の文字数上限
# (`backend/app/ai/validators/schema_validator.py`の`string_length`
# ルールと一致させている)。forge_ai/はbackend/をimportしないため、
# 既存の他の語彙・上限と同じく**手動同期**である(モジュール冒頭の
# 説明を参照)。
MAX_TITLE_LENGTH = 80

_FALLBACK_TITLE = "新しいアプリ"


def clamp_title(raw: str | None) -> str:
    """タイトルをForge Languageの制約(1〜80文字)へ必ず収める。

    **FORGE-CONVERSATION-READY-001(2026-08-12)で追加した実バグの修正**:
    `/converse`が導入されて以降、Cognitive Pipelineへ渡るのは
    ユーザーの短い一言ではなく、**会話全体を要約した自己完結型の
    `build_brief`(数十〜百数十文字の説明文)**になった。`ApplicationPlan.
    title`はこの入力から導出されるため、80文字を超えるタイトルが
    現実に生成されるようになり、Validatorが`string_length`違反として
    blockingエラーを出す。しかもこれはRepairでは直らない種類の
    エラーであるため、「Repair(2回)後もValidatorに合格しませんでした」
    という失敗として利用者に見えていた(実機Geminiで再現・確認済み)。

    切り詰め方は、単なる先頭80文字ではなく、**最初の句点まで**を
    優先する(「〜アプリ。入力および管理機能として、〜」のような
    説明文から、意味の通る短いタイトルを取り出すため)。
    """
    text = (raw or "").strip()
    if not text:
        return _FALLBACK_TITLE

    # 最初の句点までが妥当な長さなら、それをタイトルとする。
    head = text.split("。", 1)[0].strip()
    if head and len(head) <= MAX_TITLE_LENGTH:
        return head

    if len(text) <= MAX_TITLE_LENGTH:
        return text
    # 末尾を「…」にして、切り詰めたことが分かるようにする
    # (「…」も1文字として上限に数える)。
    return text[: MAX_TITLE_LENGTH - 1].rstrip() + "…"


def design_tokens_for_style(visual_style: str) -> dict[str, Any]:
    """visual_style名(calm/warm/vibrant/neutral)から、Forge Language
    design_tokens(色コード・角丸・余白)を組み立てる。未知のvisual_style
    が来た場合は"calm"へ安全にフォールバックする(未知Widgetは安全に
    Fallbackするという既存の設計原則を、Design Tokenの選択にも
    適用したもの)。
    """
    preset = _DESIGN_TOKEN_PRESETS.get(visual_style, _DESIGN_TOKEN_PRESETS["calm"])
    return {
        "color_scheme": dict(preset["color_scheme"]),
        "corner_radius": dict(preset["corner_radius"]),
        "spacing_scale": dict(preset["spacing_scale"]),
    }


def design_tokens_for_domain(domain_category: str | None) -> dict[str, Any]:
    """domain_category(文字列、`DomainCategory.value`相当)から、Forge
    Language design_tokensを選ぶ。未知/Noneの場合は"calm"へ
    フォールバックする(`design_tokens_for_style()`と同じ設計原則)。
    """
    style = _VISUAL_STYLE_BY_DOMAIN_CATEGORY.get(domain_category or "", "calm")
    return design_tokens_for_style(style)


@dataclass(frozen=True)
class ForgeIRWidget:
    """Forge Widgetノード1件のIR表現。"""

    type: str
    id: str
    properties: dict[str, Any] = field(default_factory=dict)
    children: tuple["ForgeIRWidget", ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        """Forge Language JSON互換のdictへ変換する(childrenは再帰的に変換)。"""
        result: dict[str, Any] = {"type": self.type, "id": self.id, **self.properties}
        if self.children:
            result["children"] = [c.to_json_dict() for c in self.children]
        return result


@dataclass(frozen=True)
class ForgeIRStateValue:
    """Forge State値1件のIR表現。"""

    type: str
    value: Any
    # FORGE v0.9新規(Typed Record Runtime Phase1)。type="record_list"の
    # 場合のみ使う。`ForgeIRDocument.record_schemas`のキーを指す
    # (このState内の各Recordが、どのSchemaに従うかを示す)。
    schema_ref: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        """Forge Language JSON互換のdictへ変換する。"""
        result: dict[str, Any] = {"type": self.type, "value": self.value}
        if self.schema_ref is not None:
            result["schema_ref"] = self.schema_ref
        return result


@dataclass(frozen=True)
class ForgeIRSchemaField:
    """FORGE v0.9新規(Typed Record Runtime Phase1)。`record_schema`
    1件が持つField 1つのIR表現。`forge_ai.core.ir.ir_types.Field`
    (IRレベルの型定義)を、Forge Language JSON向けの形へそのまま
    落とし込んだもの(意味は変えない、表現形式だけJSON向けにする)。
    """

    name: str
    type: str  # "string" | "number" | "boolean" | "date" | "choice"
    label: str
    required: bool = True
    options: tuple[str, ...] = ()  # type="choice"の場合のみ使用

    def to_json_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name, "type": self.type, "label": self.label, "required": self.required,
        }
        if self.type == "choice":
            result["options"] = list(self.options)
        return result


@dataclass(frozen=True)
class ForgeIRRecordSchema:
    """FORGE v0.9新規(Typed Record Runtime Phase1)。`record_schema`
    1件のIR表現(Fieldの並び)。"""

    fields: tuple[ForgeIRSchemaField, ...]

    def to_json_dict(self) -> dict[str, Any]:
        return {"fields": [f.to_json_dict() for f in self.fields]}


@dataclass(frozen=True)
class ForgeIRScreen:
    """Forge Screen1件のIR表現。"""

    id: str
    title: str
    state: dict[str, ForgeIRStateValue]
    body: ForgeIRWidget

    def to_json_dict(self) -> dict[str, Any]:
        """Forge Language JSON互換のdictへ変換する(state/bodyは再帰的に変換)。"""
        return {
            "id": self.id,
            "title": self.title,
            "state": {k: v.to_json_dict() for k, v in self.state.items()},
            "body": self.body.to_json_dict(),
        }


@dataclass(frozen=True)
class ForgeIRDocument:
    """Forge文書全体のIR表現。"""

    version: str
    initial_screen_id: str
    screens: tuple[ForgeIRScreen, ...]
    app_title: str | None = None
    # FORGE v0.9新規(Typed Record Runtime Phase1)。Schema名(identifier)
    # → ForgeIRRecordSchema。`record_list`型のStateとは独立した定義として
    # 文書のトップレベルに保持する(指示書「Record Listとは独立した
    # 定義として保持します」への対応)。空の場合はJSON上に一切出力しない
    # (record_schemaを使わない既存Domain(Checklist系)の出力を1バイトも
    # 変えないため)。
    record_schemas: dict[str, ForgeIRRecordSchema] = field(default_factory=dict)
    # FORGE v1.0新規(Product Quality Sprint1)。色・角丸・余白の
    # トークン(Widget/Runtime固有の描画情報、IRへは持ち込まない
    # ADR-012の方針。生のdictとして保持する——record_schemasのように
    # 専用データクラスへ分解するほどの構造の複雑さが無いため)。
    # 空dictの場合はJSON上に一切出力しない(design_tokensを使わない
    # 既存Domain・Legacy文書の出力を1バイトも変えないため)。
    design_tokens: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        """Forge Language v1.0互換のJSON dictへ変換する(実際の
        Runtime/Validatorとの互換性はforge_ai/外部で一度だけ確認済み。
        IMPLEMENTATION_REPORT.md参照)。"""
        result: dict[str, Any] = {
            "version": self.version,
            "initial_screen_id": self.initial_screen_id,
            "screens": [s.to_json_dict() for s in self.screens],
        }
        if self.app_title:
            result["app"] = {"title": self.app_title}
        if self.record_schemas:
            result["record_schemas"] = {name: schema.to_json_dict() for name, schema in self.record_schemas.items()}
        if self.design_tokens:
            result["design_tokens"] = self.design_tokens
        return result


class Compiler:
    """`AIProvider`を注入して使う(タイトル等の命名判断、および
    FORGE-AI-QUALITY-001以降は初期データ例`example_items`の提案にも使う)。
    画面構造(Widget/Action/State)の組み立て自体は決定的なPython実装であり、
    Provider任せにしていない(再現性・テスト容易性を優先した設計判断。
    IMPLEMENTATION_REPORT.mdの設計判断章に記録する)。
    """

    def __init__(self, provider: AIProvider, prompt_builder: PromptBuilder | None = None) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()

    def compile(
        self, plan: ApplicationPlan, *, domain_category: str | None = None, template: str = "checklist"
    ) -> ForgeIRDocument:
        """ApplicationPlanから、ForgeIRDocumentを決定的に組み立てる
        (タイトル・初期データ例のみProviderの判断を反映する)。

        FORGE v0.6対応: `domain_category`は後方互換のため引数として残して
        いるが、このメソッド自体はもう使わない(対象5 Domainは
        `pipeline_orchestrator.py`が`forge_ai.core.ir`経由へ振り分ける
        ため、このメソッドへは到達しない)。

        FORGE-AI-QUALITY-001(2026-08-11)対応: `template`引数を新設した。
        `TemplateSelector.select_final()`は"checklist"の他に10種類の
        Template名(form/tracker/calendar/memo/crud/dashboard/catalog/
        detail_list/wizard/generic)を選定していたが、以前はこの選定結果が
        `pipeline_orchestrator.py`から`Compiler.compile()`へ一度も渡され
        ておらず、選定内容に関わらず常にChecklist単一画面が作られていた
        (「満足度アンケート」のようなsurvey Domainが"form"を選んでも、
        実際にはChecklistとして出力されていた、実機Gemini確認で発見した
        不具合)。今回、`template=="form"`の場合のみ、`_compile_form_
        template()`(既存のバックエンドMock Generator`form_template.py`・
        Flutter `templates.dart`の`buildFormTemplate`と同一形状、
        Widget Registry v1.1で既に実装・テスト済みのform/heading/
        card/checkbox Widgetを再利用)へ分岐するようにした。それ以外の
        template名(tracker/calendar/memo等)は、今回は対応を見送り、
        既存のChecklist単一画面のままとする(`TECH_DEBT.md`参照)。
        """
        prompt = self._prompt_builder.build_compile_prompt(
            plan_summary={
                "title": plan.title,
                "screens": [
                    {"name": s.name, "purpose": s.purpose, "key_elements": list(s.key_elements)}
                    for s in plan.screens
                ],
                "data_entities": list(plan.data_entities),
            }
        )
        response = self._provider.complete(prompt)
        # `clamp_title()`でForge Languageの1〜80文字制約へ必ず収める
        # (会話由来の長いbuild_briefでタイトルが上限超過する実バグの修正)。
        title = clamp_title(str(response.structured.get("title") or plan.title or ""))

        primary_screen = plan.screens[0] if plan.screens else None
        elements = list(primary_screen.key_elements) if primary_screen else list(plan.data_entities)
        if not elements:
            elements = ["item"]

        # FORGE_v0.2_修正指示.md P3対応: 先頭要素(主要概念)が既知の
        # 識別子と一致する場合、生の識別子ではなく複数件の現実的な
        # 例値へ置き換える(上記`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`参照)。
        primary_concept = elements[0]

        # FORGE-AI-QUALITY-001(2026-08-11)対応: Providerが依頼内容に即した
        # `example_items`を返してきた場合、それを静的テーブルより優先する
        # (静的テーブルは`primary_concept`単位の画一的な値しか持てず、
        # 「満足度アンケート」も「習い事の満足度アンケート」も常に同じ
        # '最初の質問'になってしまう問題があった)。MockProvider・既存の
        # 実LLM未接続テストは`example_items`を返さないため、その場合は
        # 従来どおり静的テーブル→生の識別子の順にfallbackし、既存の
        # 出力を1バイトも変えない。
        provider_example_items = response.structured.get("example_items")
        provider_items = (
            [str(v).strip() for v in provider_example_items if isinstance(v, str) and str(v).strip()]
            if isinstance(provider_example_items, list)
            else []
        )
        if provider_items:
            elements = provider_items
        else:
            example_items = _EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT.get(primary_concept)
            if example_items:
                elements = list(example_items)

        if template == "form":
            return self._compile_form_template(title, elements, domain_category=domain_category)

        items_state_id = "items"
        new_item_state_id = "new_item_text"

        checklist_items = [
            {"id": f"item_{i + 1}", "text": element, "done": False} for i, element in enumerate(elements)
        ]

        body = ForgeIRWidget(
            type="column",
            id="root_column",
            children=(
                ForgeIRWidget(
                    type="checklist",
                    id="list_view",
                    properties={"state_ref": items_state_id, "empty_state_text": "まだ何もありません"},
                ),
                ForgeIRWidget(
                    type="row",
                    id="add_row",
                    children=(
                        ForgeIRWidget(
                            type="text_field",
                            id="add_field",
                            properties={"state_ref": new_item_state_id, "placeholder": "追加する"},
                        ),
                        ForgeIRWidget(
                            type="button",
                            id="add_button",
                            properties={
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
            id="generated_screen",
            title=title,
            state={
                items_state_id: ForgeIRStateValue(type="checklist", value=checklist_items),
                new_item_state_id: ForgeIRStateValue(type="string", value=""),
            },
            body=body,
        )

        return ForgeIRDocument(
            # FORGE-PRODUCT-VISION-002(2026-08-12)対応: design_tokensは
            # v1.5以降の文書でのみ許可される(`schema_validator.py`の
            # `field_not_allowed_in_version`)。以前のversion="1.0"は
            # design_tokensを一切使わない前提の値だったため、
            # design_tokensを常に出力するようになった今回、あわせて
            # 引き上げる(使うWidget/Action/State型自体はv1.0の範囲内
            # のまま、実際に変わるのはこのversion番号とdesign_tokensの
            # 有無だけ)。
            version="1.5",
            initial_screen_id=screen.id,
            screens=(screen,),
            app_title=title,
            # FORGE-PRODUCT-VISION-002(2026-08-12)対応: 以前はこの経路
            # (Checklist、legacy Compiler)だけがdesign_tokensを一切
            # 出力せず、Curated Domain Library外の全Domain(shopping・
            # survey・travel等、CEO実物監査で「アプリストアレベルの
            # 品質にするには」と問われた対象の大半)がFlutter既定の
            # Material配色のまま描画されていた。`design_tokens_for_
            # domain()`(このモジュール冒頭で定義)を使い、Curated
            # Domain Libraryと同じテーマ適用をこの経路にも広げる。
            design_tokens=design_tokens_for_domain(domain_category),
        )

    def _compile_form_template(
        self, title: str, questions: list[str], *, domain_category: str | None = None
    ) -> ForgeIRDocument:
        """FORGE-AI-QUALITY-001(2026-08-11)新設。`elements`(質問文の
        リスト)から、2画面(入力画面+送礼画面)のForm形状のForgeIR
        Documentを組み立てる。

        `backend/app/ai/generators/templates/form_template.py`
        (`build_form_template`)・`frontend/lib/features/app_generation/
        data/datasources/templates.dart`(`buildFormTemplate`)と**同一の
        Widget構成**(heading→card→form→text_field*N、送信でthanks_screen
        へnavigate)を採用している。これらは既にMock Generator経由で
        Widget Registry v1.1〜1.2(form/heading/card Widget)に対して
        実績があるため、新しいWidget構成パターンを発明せず、既存の
        実績あるShapeへ意図的に合わせた(Widget Registry自体は今回
        一切変更していない)。

        **既知の制限**: 質問の種類(text/checkbox)を判別する情報源が
        現状無いため、全問をtext_field(自由記述)として扱う(`checkbox`
        Widgetの利用は将来の拡張点として見送った)。
        """
        state: dict[str, ForgeIRStateValue] = {}
        question_widgets: list[ForgeIRWidget] = []
        for i, question in enumerate(questions):
            key = f"q{i + 1}"
            state[key] = ForgeIRStateValue(type="string", value="")
            question_widgets.append(ForgeIRWidget(
                type="text_field",
                id=f"{key}_input",
                properties={
                    "state_ref": key,
                    "placeholder": question,
                    "validation": {"rules": [
                        {"type": "max_length", "value": 200, "message": "200文字以内でお願いします"},
                    ]},
                },
            ))

        main_screen = ForgeIRScreen(
            id="generated_screen",
            title=title,
            state=state,
            body=ForgeIRWidget(
                type="column",
                id="root_column",
                children=(
                    ForgeIRWidget(type="heading", id="heading1", properties={"value": title, "level": 1}),
                    ForgeIRWidget(
                        type="card",
                        id="form_card",
                        children=(
                            ForgeIRWidget(
                                type="form",
                                id="main_form",
                                properties={
                                    "submit_label": "送信する",
                                    "submit_action": {"type": "navigate", "target_screen_id": "thanks_screen"},
                                },
                                children=tuple(question_widgets),
                            ),
                        ),
                    ),
                ),
            ),
        )

        thanks_screen = ForgeIRScreen(
            id="thanks_screen",
            title="送信完了",
            state={},
            body=ForgeIRWidget(
                type="column",
                id="thanks_root",
                children=(
                    ForgeIRWidget(type="heading", id="thanks_heading", properties={"value": "送信完了", "level": 1}),
                    ForgeIRWidget(type="text", id="thanks_text", properties={"value": "ご協力ありがとうございました。"}),
                    ForgeIRWidget(
                        type="button", id="back_button",
                        properties={"label": "戻る", "action": {"type": "go_back"}},
                    ),
                ),
            ),
        )

        return ForgeIRDocument(
            # 元々はform_template.py・templates.dartと同じ理由(v1.1専用
            # Widget(form/checkbox/card/heading)+v1.2専用のvalidation
            # プロパティを使うため)でversion="1.2"だった。
            # FORGE-PRODUCT-VISION-002(2026-08-12)対応: design_tokensを
            # 常に出力するようになったため、checklist経路と同じ理由で
            # v1.5へ引き上げる(v1.2で使っていたWidget/Action/State型は
            # すべてv1.5でも引き続き許可される、上位互換の範囲内)。
            version="1.5",
            initial_screen_id=main_screen.id,
            screens=(main_screen, thanks_screen),
            app_title=title,
            design_tokens=design_tokens_for_domain(domain_category),
        )
