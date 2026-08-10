"""Folder関連のRequest/Response DTO(FORGE V2 Phase 2 Step 1)。

`FORGE-V2-API-DESIGN-SPECIFICATION.md` 4.3節・5章、`FORGE-V2-TYPE-
DESIGN-REVIEW.md` 8章の`FolderSummaryDTO`をそのまま実装したもの。

**注記(重要)**: `app/schemas/workspace.py`と同じ制限。pydantic不在の
ためimport・実行検証はできていない。

**`application_count`について(重要な注記)**: API Design仕様は
`FolderSummaryDTO.application_count`を定義しているが、Application
実装(Phase 3)前のため、**このPhaseでは常に`0`を返す**
(`folder_to_summary_dto()`参照)。DTOの形状自体は仕様通りに維持し
(AP-018 Additive-Only、後からフィールドを追加するのではなく、
既に定義されている仕様を先取りしてそのまま実装する)、値の意味だけが
Phase 3まで暫定的である。
"""

from __future__ import annotations

from pydantic import BaseModel


class FolderSummaryDTO(BaseModel):
    id: str
    name: str
    application_count: int
    child_folder_ids: tuple[str, ...]


class CreateFolderRequestDTO(BaseModel):
    name: str
    parent_folder_id: str | None = None


class RenameFolderRequestDTO(BaseModel):
    name: str


class MoveFolderRequestDTO(BaseModel):
    new_parent_folder_id: str | None = None


def folder_to_summary_dto(folder, all_workspace_folders) -> FolderSummaryDTO:  # type: ignore[no-untyped-def]
    """`Folder`(Domain Entity)を`FolderSummaryDTO`(API境界用)へ変換
    する(AP-015)。`all_workspace_folders`から子Folder一覧を導出する
    (Router層が`FolderRepository.list_by_workspace()`の結果を渡す
    想定)。
    """
    child_ids = tuple(f.id for f in all_workspace_folders if f.parent_folder_id == folder.id)
    return FolderSummaryDTO(
        id=folder.id,
        name=folder.name,
        application_count=0,  # 上記docstring参照、Phase 3まで常に0
        child_folder_ids=child_ids,
    )
