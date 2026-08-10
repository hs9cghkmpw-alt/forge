"""Workspace Entity(FORGE V2 Phase 1、Workspace Foundation)。

`FORGE-V2-TYPE-DESIGN-REVIEW.md` 3.2節の`Workspace`定義をそのまま
実装したもの。**fastapi/pydantic/supabaseのいずれにも依存しない、
純粋なPythonのみで構成する**(`domain/README.md`の方針、および
`app/ai/runtime/confirmation_store.py`が既に確立している「pure
Pythonロジックはこのサンドボックスでも実際に実行・検証できる」
という規約に従う)。

Architecture Principles適合:
- AP-004(Workspace Is Long-Lived): 終了状態を持たない設計とする
  (`WorkspaceStatus`のようなEnumをこのEntityには持たせない。
  Type Design Review 5章`WorkspaceStatus`は`INITIALIZED`/`ACTIVE`
  の2値のみで、`ACTIVE`が事実上の恒常状態であるため、今回は
  フィールドとして持たせず、「存在すれば常にActive」という不変条件
  で表現する——AP-004の「終了状態を持たない」という原則を、
  最小のフィールドで満たすための判断)。
- AP-022(Explicit Versioning for Persistent Meaning):
  `structure_version`により、Folder/Collection構成の変更を
  追跡できるようにする。
"""

from __future__ import annotations

import dataclasses

_VALID_VIEW_TYPES = ("icon", "list", "dashboard", "category", "timeline")


@dataclasses.dataclass(frozen=True)
class Workspace:
    """Workspace本体(Aggregate Root)。

    更新は`dataclasses.replace()`による新インスタンス生成で行う
    (`forge_ai.core.orchestration.cognitive_context.CognitiveContext`
    が確立している、既存の不変更新パターンをそのまま踏襲する)。
    """

    id: str
    owner_user_id: str
    created_at: str  # ISO8601文字列
    structure_version: int = 1
    display_default_view: str = "icon"

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Workspace.id must not be empty")
        if not self.owner_user_id:
            raise ValueError("Workspace.owner_user_id must not be empty")
        if self.structure_version < 1:
            raise ValueError(f"Workspace.structure_version must be >= 1, got {self.structure_version}")
        if self.display_default_view not in _VALID_VIEW_TYPES:
            raise ValueError(
                f"Workspace.display_default_view must be one of {_VALID_VIEW_TYPES}, "
                f"got {self.display_default_view!r}"
            )

    def with_display_default_view(self, view: str) -> "Workspace":
        """`display_default_view`だけを変更した、新しいWorkspaceを返す。

        不正な`view`が渡された場合、`__post_init__`のValidationにより
        `ValueError`を送出する(呼び出し側=UseCase層が、これを
        `ValidationError`(Type Design15章)へ変換する責務を持つ)。
        """
        return dataclasses.replace(self, display_default_view=view)

    def with_structure_version_incremented(self) -> "Workspace":
        """Folder/Collection構成の変更に伴い、Versionを1つ進めた
        新しいWorkspaceを返す(AP-022)。Phase 1ではこのメソッドの
        呼び出し元は存在しない(Folder/CollectionはPhase 2以降)が、
        Entity自体は既に用意しておく(Type Design3.2節の
        `structure_version`フィールドが要求する振る舞いのため)。
        """
        return dataclasses.replace(self, structure_version=self.structure_version + 1)


def is_valid_view_type(view: str) -> bool:
    """`ViewType`(Type Design5章のEnum)の許可値かどうかを判定する。

    Router層(pydanticに依存する`app/schemas/workspace.py`)からも、
    UseCase層(pydanticに依存しない)からも、同じ判定ロジックを
    参照できるよう、独立した関数として公開する。
    """
    return view in _VALID_VIEW_TYPES


VALID_VIEW_TYPES: tuple[str, ...] = _VALID_VIEW_TYPES
