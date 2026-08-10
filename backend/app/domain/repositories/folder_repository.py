"""FolderRepositoryインターフェース(FORGE V2 Phase 2 Step 1)。

`FORGE-V2-TYPE-DESIGN-REVIEW.md` 9章の`FolderRepository`をそのまま
実装したもの。Architecture Principles AP-016に従い、**循環判定を
含むビジネスルールは一切持たない**、純粋なデータアクセスのみを
提供する(循環検出は`app/services/folder_service.py`の責務)。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.entities.folder import Folder


@runtime_checkable
class FolderRepository(Protocol):
    def get(self, folder_id: str) -> Folder | None:
        """IDでFolderを取得する。存在しなければ`None`。"""
        ...

    def list_by_workspace(self, workspace_id: str) -> tuple[Folder, ...]:
        """指定Workspace配下の全Folderを返す(親子関係を問わず、
        フラットな一覧)。"""
        ...

    def save(self, folder: Folder) -> None:
        """Folderを保存する(新規作成・更新のいずれも)。"""
        ...

    def delete(self, folder_id: str) -> None:
        """Folderを削除する。子Folderの扱い(cascade)は、この
        メソッドの責務ではない(`FolderService.delete()`が、
        削除対象を確定してから、対象1件ずつについてこのメソッドを
        呼ぶ、という設計)。"""
        ...
