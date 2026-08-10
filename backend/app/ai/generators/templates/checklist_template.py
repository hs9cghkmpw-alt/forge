"""Checklist Template。

FORGE-MERGE-001以来のMock Generatorが生成していた構造(checklist +
追加用のtext_field/button)を、再利用可能なTemplateとして切り出したもの。
出力するJSONの形はv1.0時代から一切変更していない(既存テストとの互換性)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import build_document, build_screen_shell


@dataclass(frozen=True)
class ChecklistTemplateParams:
    title: str
    items: tuple[str, ...]


def build_checklist_template(params: ChecklistTemplateParams) -> dict[str, Any]:
    checklist_items = [
        {"id": f"item_{i + 1}", "text": item_text, "done": False}
        for i, item_text in enumerate(params.items)
    ]
    screen = build_screen_shell(
        screen_id="generated_screen",
        title=params.title,
        state={
            "new_item_text": {"type": "string", "value": ""},
            "items": {"type": "checklist", "value": checklist_items},
        },
        body={
            "type": "column",
            "id": "root_column",
            "children": [
                {
                    "type": "checklist",
                    "id": "list_view",
                    "state_ref": "items",
                    "empty_state_text": "アイテムはまだないよ",
                },
                {
                    "type": "row",
                    "id": "add_row",
                    "children": [
                        {
                            "type": "text_field",
                            "id": "add_field",
                            "state_ref": "new_item_text",
                            "placeholder": "アイテムを追加",
                        },
                        {
                            "type": "button",
                            "id": "add_button",
                            "label": "追加",
                            "action": {
                                "type": "add_item",
                                "target_state_ref": "items",
                                "source_state_ref": "new_item_text",
                            },
                        },
                    ],
                },
            ],
        },
    )
    return build_document(app_title=params.title, initial_screen_id="generated_screen", screens=[screen])
