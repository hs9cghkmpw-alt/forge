"""Form Template。

複数の質問(checkbox / text_field)を1つのformにまとめ、送信すると
別画面(お礼画面)へnavigateする、2画面構成のTemplate。
ChecklistやMemoと異なり、初めてnavigate Actionを実際に使うTemplateであり、
card Widgetでの視覚的なグルーピングも実演する。FORGE-MILESTONE-003で、
コメント欄にvalidation(max_length)を追加したため、v1.1専用Widget
(form/checkbox/card/heading)に加えv1.2専用のvalidationプロパティも使う。
よって version="1.2"。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .base import build_document, build_screen_shell

QuestionKind = Literal["text", "checkbox"]


@dataclass(frozen=True)
class FormQuestion:
    key: str  # state参照キー。安定ID規則(^[a-z][a-z0-9_]*$)に従うこと
    label: str
    kind: QuestionKind


@dataclass(frozen=True)
class FormTemplateParams:
    title: str
    questions: tuple[FormQuestion, ...]
    thanks_message: str = "ご協力ありがとうございました。"


def build_form_template(params: FormTemplateParams) -> dict[str, Any]:
    state: dict[str, Any] = {}
    question_widgets: list[dict[str, Any]] = []

    for q in params.questions:
        if q.kind == "checkbox":
            state[q.key] = {"type": "boolean", "value": False}
            question_widgets.append(
                {"type": "checkbox", "id": f"{q.key}_input", "label": q.label, "state_ref": q.key}
            )
        else:
            state[q.key] = {"type": "string", "value": ""}
            question_widgets.append(
                {
                    "type": "text_field", "id": f"{q.key}_input", "state_ref": q.key, "placeholder": q.label,
                    "validation": {"rules": [
                        {"type": "max_length", "value": 200, "message": "200文字以内でお願いします"},
                    ]},
                }
            )

    main_screen = build_screen_shell(
        screen_id="generated_screen",
        title=params.title,
        state=state,
        body={
            "type": "column",
            "id": "root_column",
            "children": [
                {"type": "heading", "id": "heading1", "value": params.title, "level": 1},
                {
                    "type": "card",
                    "id": "form_card",
                    "children": [
                        {
                            "type": "form",
                            "id": "main_form",
                            "children": question_widgets,
                            "submit_label": "送信する",
                            "submit_action": {"type": "navigate", "target_screen_id": "thanks_screen"},
                        },
                    ],
                },
            ],
        },
    )

    thanks_screen = build_screen_shell(
        screen_id="thanks_screen",
        title="送信完了",
        state={},
        body={
            "type": "column",
            "id": "thanks_root",
            "children": [
                {"type": "heading", "id": "thanks_heading", "value": "送信完了", "level": 1},
                {"type": "text", "id": "thanks_text", "value": params.thanks_message},
                {
                    "type": "button", "id": "back_button", "label": "戻る",
                    "action": {"type": "go_back"},
                },
            ],
        },
    )

    return build_document(
        app_title=params.title,
        initial_screen_id="generated_screen",
        screens=[main_screen, thanks_screen],
        version="1.2",
    )
