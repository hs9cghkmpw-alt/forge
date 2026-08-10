"""Memo Template(新規)。

チェックリストではなく、自由記述の1つのテキスト欄だけを持つ、
最も単純な構造。heading(v1.1新規Widget)を使うため version="1.1"。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import build_document, build_screen_shell


@dataclass(frozen=True)
class MemoTemplateParams:
    title: str
    placeholder: str = "ここに書く"


def build_memo_template(params: MemoTemplateParams) -> dict[str, Any]:
    screen = build_screen_shell(
        screen_id="generated_screen",
        title=params.title,
        state={"note": {"type": "string", "value": ""}},
        body={
            "type": "column",
            "id": "root_column",
            "children": [
                {"type": "heading", "id": "heading1", "value": params.title, "level": 1},
                {
                    "type": "text_field",
                    "id": "note_field",
                    "state_ref": "note",
                    "placeholder": params.placeholder,
                },
            ],
        },
    )
    return build_document(
        app_title=params.title, initial_screen_id="generated_screen", screens=[screen], version="1.1"
    )
