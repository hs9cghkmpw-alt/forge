"""AI Runtime — Template Engine(FORGE-MILESTONE-004 PHASE4)。

これまでTemplate(`app/ai/generators/templates/`)は、Python関数
(`build_checklist_template`等)としてのみ存在し、「AIがどのTemplateを
選べるか」を判断するための構造化されたメタデータを持っていなかった。

このモジュールは、**既存の3つのTemplate実装(checklist/memo/form、
`app/ai/generators/templates/`に実装済み・テスト済み)を対象に**、
AIが選択可能な構造化メタデータ(`Template`)としてカタログ化する。
Template自体の実装(JSON生成ロジック)はここでは変更しない
(既存の`build_checklist_template`等をそのまま利用する)。

新しいTemplate実装を追加するものではない。既存3種の「説明」を
構造化しただけであり、生成される文書の中身は一切変わらない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Template:
    """AIが選択可能な、1つのTemplateの構造化メタデータ。

    実際のJSON生成関数(`builder`)への参照を持つが、Template Engine自体は
    その関数を呼び出さない(呼び出すのはTemplate Selector以降の責務)。
    """

    id: str
    category: str
    priority: int
    capabilities: tuple[str, ...]
    required_widgets: tuple[str, ...]
    optional_widgets: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    description: str = ""
    builder: Callable[..., dict] | None = field(default=None, repr=False, compare=False)

    schema_version: str = "1.0"
    """FORGE-AI-CONNECT-001 TD22対応(2026-08-11)。このTemplateメタデータ
    構造自体のバージョン(`IntentIR.schema_version`・`PlanIR.
    schema_version`と同じ考え方)。既存3種のTemplate(checklist/memo/
    form)は全てこの既定値のまま。"""


class TemplateRegistry:
    """既知のTemplate一覧を保持する。新しいTemplateを追加する際は、
    このクラスへ登録するだけでよい(Selector・Plannerを変更する必要はない、
    という拡張性を意図している)。
    """

    def __init__(self) -> None:
        self._templates: dict[str, Template] = {t.id: t for t in _BUILTIN_TEMPLATES}

    def get(self, template_id: str) -> Template | None:
        return self._templates.get(template_id)

    def all_templates(self) -> tuple[Template, ...]:
        return tuple(self._templates.values())

    def by_category(self, category: str) -> tuple[Template, ...]:
        return tuple(t for t in self._templates.values() if t.category == category)

    def by_tag(self, tag: str) -> tuple[Template, ...]:
        return tuple(t for t in self._templates.values() if tag in t.tags)

    def by_capability(self, capability: str) -> tuple[Template, ...]:
        return tuple(t for t in self._templates.values() if capability in t.capabilities)


def _checklist_builder(**kwargs: object) -> dict:
    """既存の`build_checklist_template`への薄い委譲。importをこの関数内に
    留めているのは、Template Engineモジュール自体が(未使用時に)
    generators/への依存を強制しないようにするため
    (テスト容易性・依存方向の明確化)。"""
    from app.ai.generators.templates.checklist_template import (
        ChecklistTemplateParams,
        build_checklist_template,
    )

    return build_checklist_template(ChecklistTemplateParams(**kwargs))  # type: ignore[arg-type]


def _memo_builder(**kwargs: object) -> dict:
    from app.ai.generators.templates.memo_template import MemoTemplateParams, build_memo_template

    return build_memo_template(MemoTemplateParams(**kwargs))  # type: ignore[arg-type]


def _form_builder(**kwargs: object) -> dict:
    from app.ai.generators.templates.form_template import FormTemplateParams, build_form_template

    return build_form_template(FormTemplateParams(**kwargs))  # type: ignore[arg-type]


_BUILTIN_TEMPLATES: tuple[Template, ...] = (
    Template(
        id="checklist",
        category="checklist",
        priority=10,
        capabilities=("list_management", "item_tracking", "quick_capture"),
        required_widgets=("column", "checklist", "row", "text_field", "button"),
        optional_widgets=(),
        tags=(
            "list", "todo", "tracking", "shopping", "travel", "household",
            "schedule", "child", "pet", "gift", "budget", "food",
        ),
        description="項目の追加・チェック・削除を行う単一画面のチェックリスト。"
        "Mock Generatorの9カテゴリ(買い物/旅行/家事/予定/子ども/ペット/"
        "プレゼント/家計簿/ご飯)が全てこのTemplateを使う。",
        builder=_checklist_builder,
    ),
    Template(
        id="memo",
        category="memo",
        priority=5,
        capabilities=("free_text_capture",),
        required_widgets=("column", "heading", "text_field"),
        optional_widgets=(),
        tags=("notes", "memo", "freeform", "journal"),
        description="見出し+自由記述の1つのテキスト欄だけを持つ、最も単純な構造。",
        builder=_memo_builder,
    ),
    Template(
        id="form",
        category="form",
        priority=8,
        capabilities=("structured_data_collection", "multi_screen_flow", "validation"),
        required_widgets=("column", "heading", "card", "form", "button", "text"),
        optional_widgets=("checkbox", "text_field"),
        tags=("survey", "questionnaire", "form", "feedback", "signup"),
        description="複数の質問(checkbox/text_field)を1つのformにまとめ、"
        "送信すると別画面(お礼画面)へnavigateする、2画面構成のTemplate。",
        builder=_form_builder,
    ),
)
