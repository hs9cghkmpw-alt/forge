"""`POST/PATCH/DELETE /v1/folders`・`POST /v1/folders/{id}/move`
(FORGE V2 Phase 2 Step 1)。

`FORGE-V2-API-DESIGN-SPECIFICATION.md` 4.3節をそのまま実装する。

**注記(重要、未検証)**: `app/routers/workspace.py`と同じ制限
(fastapi不在、JWT検証未実装)。一度もimport・実行できていない。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from app.core.exceptions import ConflictError, NotFoundError, PermissionError_, ValidationError
from app.core.security import get_current_user_id
from app.domain.usecases.get_or_create_workspace_usecase import GetOrCreateWorkspaceUseCase
from app.repositories.in_memory_folder_repository import InMemoryFolderRepository
from app.schemas.folder import (
    CreateFolderRequestDTO,
    FolderSummaryDTO,
    MoveFolderRequestDTO,
    RenameFolderRequestDTO,
    folder_to_summary_dto,
)
from app.services.folder_service import FolderService

router = APIRouter(prefix="/v1/folders", tags=["folder"])

# Phase 1の`di.get_workspace_repository()`と同じ考え方で、Folder用の
# シングルトンRepositoryをプロセス内で使い回す。Phase 2 Step 1では
# `core/di.py`へ正式に統合せず、このモジュール内に留める(Small PR
# 相当に収めるための判断、Remaining Risksへ記録)。
_folder_repository = InMemoryFolderRepository()


def _authenticate(authorization: str | None) -> str:
    try:
        return get_current_user_id(authorization)
    except PermissionError_ as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _get_workspace_id_for_user(user_id: str) -> str:
    """このRouterが扱うFolderは、常にUser本人のWorkspace配下に限定
    される(AP-002)。Workspace自体の取得/自動作成はPhase 1の
    UseCaseを再利用する。"""
    # NOTE: Phase 1と同じRepositoryインスタンスを共有していないため
    # (上記コメント参照)、ここではPhase 1のdi経由のRepositoryを使う。
    from app.core.di import get_workspace_repository

    workspace = GetOrCreateWorkspaceUseCase(get_workspace_repository()).execute(user_id)
    return workspace.id


@router.post("", response_model=FolderSummaryDTO, status_code=201)
def create_folder(
    body: CreateFolderRequestDTO, authorization: str | None = Header(default=None)
) -> FolderSummaryDTO:
    user_id = _authenticate(authorization)
    workspace_id = _get_workspace_id_for_user(user_id)
    service = FolderService(_folder_repository)
    try:
        folder = service.create(workspace_id, body.name, body.parent_folder_id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    all_folders = _folder_repository.list_by_workspace(workspace_id)
    return folder_to_summary_dto(folder, all_folders)


@router.patch("/{folder_id}", response_model=FolderSummaryDTO)
def rename_folder(
    folder_id: str, body: RenameFolderRequestDTO, authorization: str | None = Header(default=None)
) -> FolderSummaryDTO:
    user_id = _authenticate(authorization)
    workspace_id = _get_workspace_id_for_user(user_id)
    service = FolderService(_folder_repository)
    try:
        folder = service.rename(workspace_id, folder_id, body.name)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    all_folders = _folder_repository.list_by_workspace(workspace_id)
    return folder_to_summary_dto(folder, all_folders)


@router.delete("/{folder_id}", status_code=200)
def delete_folder(
    folder_id: str, cascade: bool = Query(default=False), authorization: str | None = Header(default=None)
) -> dict:
    user_id = _authenticate(authorization)
    workspace_id = _get_workspace_id_for_user(user_id)
    service = FolderService(_folder_repository)
    try:
        service.delete(workspace_id, folder_id, cascade=cascade)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted", "id": folder_id}


@router.post("/{folder_id}/move", response_model=FolderSummaryDTO)
def move_folder(
    folder_id: str, body: MoveFolderRequestDTO, authorization: str | None = Header(default=None)
) -> FolderSummaryDTO:
    user_id = _authenticate(authorization)
    workspace_id = _get_workspace_id_for_user(user_id)
    service = FolderService(_folder_repository)
    try:
        folder = service.move(workspace_id, folder_id, body.new_parent_folder_id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    all_folders = _folder_repository.list_by_workspace(workspace_id)
    return folder_to_summary_dto(folder, all_folders)
