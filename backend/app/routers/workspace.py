"""`GET`/`PATCH /v1/workspace`(FORGE V2 Phase 1)。

`FORGE-V2-API-DESIGN-SPECIFICATION.md` 4.1節をそのまま実装する。

**注記(2026-08-17更新)**: このファイルは**import・実行済み**である。
`backend/tests/test_workspace_router.py`が`TestClient`経由で叩いており、
GitHub Actionsがpushごとに実行している(013 §8で訂正)。

**ただし下記の認証の制限は今も有効である。** 「実行できている」ことと
「本番で使える」ことは別なので、混同しないこと。

**認証について**: `app/core/security.py`の`get_current_user_id()`が
未実装(`_verify_and_decode()`がNotImplementedError、同ファイルの
docstring参照)であるため、**このRouter自体も、実際のJWT検証が
CEO環境で実装されるまでは動作しない**。Router自体のロジック
(UseCase呼び出し・DTO変換・例外→HTTPステータス変換)は、CEO環境で
`security.py`が完成した時点で、そのまま動作する設計にしてある。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.core.di import get_workspace_repository
from app.core.exceptions import NotFoundError, PermissionError_, ValidationError
from app.core.security import get_current_user_id
from app.domain.usecases.get_or_create_workspace_usecase import GetOrCreateWorkspaceUseCase
from app.domain.usecases.update_workspace_settings_usecase import UpdateWorkspaceSettingsUseCase
from app.schemas.workspace import (
    UpdateWorkspaceSettingsRequestDTO,
    WorkspaceDetailDTO,
    workspace_to_detail_dto,
)

router = APIRouter(prefix="/v1/workspace", tags=["workspace"])


def _authenticate(authorization: str | None) -> str:
    """`get_current_user_id()`の`PermissionError_`を、HTTP 401へ
    変換する共通ヘルパー(API Design Specification7章)。"""
    try:
        return get_current_user_id(authorization)
    except PermissionError_ as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("", response_model=WorkspaceDetailDTO)
def get_workspace(authorization: str | None = Header(default=None)) -> WorkspaceDetailDTO:
    """認証されたUser本人のWorkspaceを返す。存在しなければ自動作成
    する(API Design Specification4.1節 #1)。"""
    user_id = _authenticate(authorization)
    use_case = GetOrCreateWorkspaceUseCase(get_workspace_repository())
    workspace = use_case.execute(user_id)
    return workspace_to_detail_dto(workspace)


@router.patch("", response_model=WorkspaceDetailDTO)
def update_workspace_settings(
    body: UpdateWorkspaceSettingsRequestDTO,
    authorization: str | None = Header(default=None),
) -> WorkspaceDetailDTO:
    """`display_default_view`のみ更新する(API Design Specification
    4.1節 #2)。"""
    user_id = _authenticate(authorization)
    use_case = UpdateWorkspaceSettingsUseCase(get_workspace_repository())
    try:
        workspace = use_case.execute(user_id, body.display_default_view)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotFoundError as exc:
        # Phase 1では、GET未実行のままPATCHだけ呼ぶケースは
        # 「未作成」を意味する。Freeze Report13章の判断により、
        # PATCH経由では自動作成しない(GET経由のみ自動作成する、
        # API Design4.1節 #1のDone Definitionとの整合)。
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return workspace_to_detail_dto(workspace)
