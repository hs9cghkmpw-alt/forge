"""UpdateWorkspaceSettingsUseCase(FORGE V2 Phase 1)。

`FORGE-V2-TYPE-DESIGN-REVIEW.md` 6章`UpdateWorkspaceSettingsCommand`
を実装する。fastapi/pydanticに一切依存しない。
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.workspace import Workspace, is_valid_view_type
from app.domain.repositories.workspace_repository import WorkspaceRepository


class UpdateWorkspaceSettingsUseCase:
    """`display_default_view`のみを更新する(Type Design6章の
    Command定義通り、それ以外のフィールドはこのUseCase経由では
    変更できない)。
    """

    def __init__(self, workspace_repository: WorkspaceRepository) -> None:
        self._workspace_repository = workspace_repository

    def execute(self, owner_user_id: str, display_default_view: str | None) -> Workspace:
        workspace = self._workspace_repository.get_by_owner(owner_user_id)
        if workspace is None:
            raise NotFoundError(entity_type="Workspace", entity_id=owner_user_id)

        if display_default_view is None:
            # 何も指定されていない場合は無変更のまま返す(部分更新、
            # Type Design6章のCommandは全フィールドOptionalのため)。
            return workspace

        if not is_valid_view_type(display_default_view):
            raise ValidationError(
                field="display_default_view",
                reason=f"must be one of the known ViewType values, got {display_default_view!r}",
            )

        updated = workspace.with_display_default_view(display_default_view)
        self._workspace_repository.save(updated)
        return updated
