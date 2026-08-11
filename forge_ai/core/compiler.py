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
}


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
    """`AIProvider`を注入して使う(主にタイトル等の命名判断に使う想定)。
    画面構造(Widget/Action/State)の組み立て自体は決定的なPython実装であり、
    Provider任せにしていない(再現性・テスト容易性を優先した設計判断。
    IMPLEMENTATION_REPORT.mdの設計判断章に記録する)。
    """

    def __init__(self, provider: AIProvider, prompt_builder: PromptBuilder | None = None) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()

    def compile(self, plan: ApplicationPlan, *, domain_category: str | None = None) -> ForgeIRDocument:
        """ApplicationPlanから、Checklistテンプレート形状のForgeIRDocumentを
        決定的に組み立てる(タイトルのみProviderの判断を反映する)。

        FORGE v0.6対応: `domain_category`は後方互換のため引数として残して
        いるが、このメソッド自体はもう使わない(対象3 Domainは
        `pipeline_orchestrator.py`が`forge_ai.core.ir`経由へ振り分ける
        ため、このメソッドへは到達しない)。
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
        title = str(response.structured.get("title") or plan.title or "新しいアプリ")

        primary_screen = plan.screens[0] if plan.screens else None
        elements = list(primary_screen.key_elements) if primary_screen else list(plan.data_entities)
        if not elements:
            elements = ["item"]

        # FORGE_v0.2_修正指示.md P3対応: 先頭要素(主要概念)が既知の
        # 識別子と一致する場合、生の識別子ではなく複数件の現実的な
        # 例値へ置き換える(上記`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`参照)。
        primary_concept = elements[0]
        example_items = _EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT.get(primary_concept)
        if example_items:
            elements = list(example_items)

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
            version="1.0",
            initial_screen_id=screen.id,
            screens=(screen,),
            app_title=title,
        )
