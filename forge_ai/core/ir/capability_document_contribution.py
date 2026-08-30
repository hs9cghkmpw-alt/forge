"""**獲得した能力が、生成物へ届くための宣言**（020E-5）。

---

## なぜ要るのか

`forge_language_compiler.py` は widget をこう出していた。

```python
if "view.map" in promoted_capabilities:
    document = self._attach_map_view(document, entity)
```

**能力名で分岐している。** `view.map` にだけ人が書いた枝があり、
Self-Extension で獲得した能力には枝が無い。つまり——

> 能力を獲得しても、**生成されるソフトウェアには一生現れない。**

獲得の目的そのものが果たせない。Planner 側の同じ形は
`CapabilityDefinition.required_fields` の宣言へ移した（`83683e1`）。
これは Compiler 側の同じ手当てである。

## 枝ではなく表にする

表であることが本質である。**枝は人が書き足すものだが、表は獲得した
能力が自分で登録できる。**

```python
register_document_contribution(contribution)   # 獲得時に登録
```

Compiler は promoted な能力を順に見て、**登録されている宣言を適用する
だけ**になる。`view.map` という文字列は Compiler から消える。

## これは「Dart が描ける」という意味ではない

宣言は「この能力はこの widget を出す」と言っているだけである。
その widget を Runtime が描けるかどうかは**別の事実**であり、
BUILD_TIME で新しい Runtime を実際にビルドして初めて成立する。
宣言を足しただけで描けるようになるわけではない。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRWidget
from forge_ai.core.ir.ir_types import Entity, FieldType

__all__ = [
    "CapabilityDocumentContribution",
    "ContributionRequirementError",
    "FieldNameRef",
    "apply_capability_contributions",
    "document_contribution_for",
    "register_document_contribution",
    "registered_contribution_ids",
]


class ContributionRequirementError(ValueError):
    """**宣言した前提が満たされていない。**

    黙って widget を落とさない。前提が要るのに無いなら、それは
    生成物の欠陥であって「なんとなく出さない」で済ませてよいものではない。
    """


@dataclass(frozen=True, slots=True)
class FieldNameRef:
    """「必須項目 `name` の**実際の欄名**」を指す差し込み。

    宣言の中に生の欄名を書かないための小さな型である。
    """

    name: str


@dataclass(frozen=True, slots=True)
class CapabilityDocumentContribution:
    """1つの能力が生成 Document へ足すもの。**データであって、コードではない。**"""

    capability_id: str
    widget_type: str
    widget_id: str
    document_version: str
    required_numeric_fields: tuple[str, ...] = field(default=())
    """**明示的な数値**として要る欄。

    例えば地図は緯度・経度を要る。**自由入力の地名から導いてよいという
    意味ではない**（それは geocoding という別の能力である）。
    """

    properties: tuple[tuple[str, object], ...] = field(default=())
    """widget の属性。順序を保つため tuple で持つ。

    値が `FieldNameRef` なら、その必須項目の実際の欄名へ置き換える。
    """

    label_property: str | None = None
    """必須項目以外の最初の文字列欄を入れる属性（無ければ入れない）。"""

    fallback_container_id: str = "contribution_root"
    """本文が `column` でないときに包む器の id。"""

    def validate(self) -> None:
        if not self.capability_id.strip():
            raise ContributionRequirementError("contribution requires capability_id")
        if not self.widget_type.strip() or not self.widget_id.strip():
            raise ContributionRequirementError("contribution requires widget type and id")
        if not self.document_version.strip():
            raise ContributionRequirementError("contribution requires document version")

    def build_widget(self, entity: Entity) -> ForgeIRWidget:
        """宣言から widget を1つ作る。**前提を満たさなければ落とす。**"""
        self.validate()
        resolved: dict[str, object] = {}
        for required in self.required_numeric_fields:
            found = next((f for f in entity.fields if f.name == required), None)
            if found is None:
                raise ContributionRequirementError(
                    f"{self.capability_id} requires an explicit numeric "
                    f"{required!r} field; free-form text requires a separate capability"
                )
            if found.type is not FieldType.NUMBER:
                raise ContributionRequirementError(
                    f"{self.capability_id} {required!r} field must be numeric"
                )
            resolved[required] = found

        properties: dict[str, object] = {}
        for key, value in self.properties:
            properties[key] = (
                resolved[value.name].name if isinstance(value, FieldNameRef) else value
            )

        if self.label_property is not None:
            label = next(
                (
                    f.name for f in entity.fields
                    if f.name not in set(self.required_numeric_fields)
                    and f.type is FieldType.STRING
                ),
                None,
            )
            if label is not None:
                properties[self.label_property] = label

        return ForgeIRWidget(
            type=self.widget_type, id=self.widget_id, properties=properties,
        )

    def apply(self, document: ForgeIRDocument, entity: Entity) -> ForgeIRDocument:
        widget = self.build_widget(entity)
        screens: list[ForgeIRScreen] = []
        for screen in document.screens:
            if screen.body.type == "column":
                body = ForgeIRWidget(
                    type=screen.body.type, id=screen.body.id,
                    properties=dict(screen.body.properties),
                    children=(*screen.body.children, widget),
                )
            else:
                body = ForgeIRWidget(
                    type="column", id=self.fallback_container_id,
                    children=(screen.body, widget),
                )
            screens.append(ForgeIRScreen(
                id=screen.id, title=screen.title, state=dict(screen.state), body=body,
            ))
        return ForgeIRDocument(
            version=self.document_version,
            initial_screen_id=document.initial_screen_id,
            screens=tuple(screens),
            app_title=document.app_title,
            record_schemas=dict(document.record_schemas),
            design_tokens=dict(document.design_tokens),
        )


#: **登録表。** 枝ではないので、獲得した能力が自分で足せる。
_CONTRIBUTIONS: dict[str, CapabilityDocumentContribution] = {}


def register_document_contribution(
    contribution: CapabilityDocumentContribution,
) -> CapabilityDocumentContribution:
    """能力の出力宣言を登録する。

    出荷済みの能力は起動時に、獲得した能力は promotion 後に登録する。
    **同じ id を別の宣言で上書きしない**——静かなすり替えを防ぐ。
    """
    contribution.validate()
    existing = _CONTRIBUTIONS.get(contribution.capability_id)
    if existing is not None and existing != contribution:
        raise ContributionRequirementError(
            f"document contribution for {contribution.capability_id!r} already registered"
            " with a different declaration",
        )
    _CONTRIBUTIONS[contribution.capability_id] = contribution
    return contribution


def document_contribution_for(capability_id: str) -> CapabilityDocumentContribution | None:
    return _CONTRIBUTIONS.get(capability_id)


def registered_contribution_ids() -> tuple[str, ...]:
    return tuple(sorted(_CONTRIBUTIONS))


def apply_capability_contributions(
    document: ForgeIRDocument,
    capability_ids: tuple[str, ...],
    entity: Entity,
) -> ForgeIRDocument:
    """**PROMOTED な能力の宣言だけ**を順に適用する。

    Compiler はこれを呼ぶだけで、どの能力かを知らない。
    """
    current = document
    seen: set[str] = set()
    for capability_id in capability_ids:
        if capability_id in seen:
            continue
        seen.add(capability_id)
        contribution = _CONTRIBUTIONS.get(capability_id)
        if contribution is None:
            continue
        current = contribution.apply(current, entity)
    return current
