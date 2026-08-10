"""FolderService(FORGE V2 Phase 2 Step 1)。

`domain/README.md`の規約上、`services/`は「複数usecaseを跨ぐ調整や、
外部API呼び出しを伴うアプリケーション層」と位置づけられている。
`FORGE-V2-TYPE-DESIGN-REVIEW.md` 10章・`FORGE-V2-ARCHITECTURE-
FREEZE-REPORT.md` 5章が`FolderService`を"Application Service"
(Repository等I/Oを伴うオーケストレーション)として分類していることと
一貫させるため、Phase 1のように個別UseCaseへ分割せず、CEO指示
「FolderServiceのみ」の通り**単一クラス**として`app/services/`
配下に実装する。

**Phase 1との実装粒度の違いについて(正直な申告)**: Phase 1では
`GetOrCreateWorkspaceUseCase`・`UpdateWorkspaceSettingsUseCase`という
2つの独立したUseCaseクラスに分割した(`domain/usecases/`配下、
「1 usecase = 1 class」という`domain/README.md`の規約により忠実な
実装)。今回、CEOの指示文が明示的に「FolderServiceのみ」と1クラスを
指定していたため、その通りに実装した。**この2つの粒度が並存する
ことになった点は、意図的な設計変更ではなく、指示文の粒度差をそのまま
反映した結果である**ため、Final Report・Remaining Risksへ記録する
(Phase 2 Step 2以降、あるいはPhase 1への遡及的な統一が必要かどうかは
CEO判断を仰ぐ)。

責務(Architecture Principles AP-016の裏返し、Repositoryには置かない
ビジネスルールをここに集約する):
- 循環検知(`create`の`parent_folder_id`指定時、`move`時の両方)
- Workspace所属確認(親Folderが同じWorkspaceに属するか)
- cascade判定(子Folderが存在する状態での削除可否)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.entities.folder import Folder
from app.domain.repositories.folder_repository import FolderRepository


class FolderService:
    def __init__(self, folder_repository: FolderRepository) -> None:
        self._folder_repository = folder_repository

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    def create(self, workspace_id: str, name: str, parent_folder_id: str | None) -> Folder:
        """新規Folderを作成する(API Design4.3節 #10)。

        `parent_folder_id`が指定された場合、(1)存在すること、
        (2)同じWorkspaceに属すること、を検証する(循環自体は、
        まだ存在しない新規Folderが親になることはあり得ないため、
        `create`では循環検知の対象外——循環が起こりうるのは`move`
        のみ)。
        """
        if not name or not name.strip():
            raise ValidationError(field="name", reason="must not be empty")

        if parent_folder_id is not None:
            parent = self._folder_repository.get(parent_folder_id)
            if parent is None:
                raise NotFoundError(entity_type="Folder", entity_id=parent_folder_id)
            if parent.workspace_id != workspace_id:
                raise ValidationError(
                    field="parent_folder_id",
                    reason="parent folder must belong to the same workspace",
                )

        folder = Folder(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            name=name,
            parent_folder_id=parent_folder_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._folder_repository.save(folder)
        return folder

    # ------------------------------------------------------------------
    # rename
    # ------------------------------------------------------------------

    def rename(self, workspace_id: str, folder_id: str, new_name: str) -> Folder:
        """Folderを改名する(API Design4.3節 #11)。"""
        folder = self._get_owned_folder(workspace_id, folder_id)
        if not new_name or not new_name.strip():
            raise ValidationError(field="name", reason="must not be empty")

        updated = folder.with_name(new_name)
        self._folder_repository.save(updated)
        return updated

    # ------------------------------------------------------------------
    # move
    # ------------------------------------------------------------------

    def move(self, workspace_id: str, folder_id: str, new_parent_folder_id: str | None) -> Folder:
        """Folder自体を階層内で再配置する(API Design4.3節 #13、
        Applicationの所属Folder変更とは別の操作、既存の区別を踏襲)。
        """
        folder = self._get_owned_folder(workspace_id, folder_id)

        if new_parent_folder_id is not None:
            new_parent = self._folder_repository.get(new_parent_folder_id)
            if new_parent is None:
                raise NotFoundError(entity_type="Folder", entity_id=new_parent_folder_id)
            if new_parent.workspace_id != workspace_id:
                raise ValidationError(
                    field="new_parent_folder_id",
                    reason="new parent folder must belong to the same workspace",
                )
            if self._would_create_cycle(folder_id, new_parent_folder_id):
                raise ValidationError(
                    field="new_parent_folder_id",
                    reason="moving here would create a circular folder reference",
                )

        updated = folder.with_parent_folder_id(new_parent_folder_id)
        self._folder_repository.save(updated)
        return updated

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    def delete(self, workspace_id: str, folder_id: str, cascade: bool) -> None:
        """Folderを削除する(API Design4.3節 #12)。

        子Folderが存在する場合、`cascade=True`が明示されない限り
        `ConflictError`を送出する(Type Design Review6章
        `DeleteFolderCommand`)。

        **Phase 3までのScope限定(重要な注記)**: Applicationが
        まだ実装されていないため、「所属Applicationが存在する場合」
        の判定は、このPhaseでは行わない(Folder.pyのdocstring・
        Remaining Risks参照)。子Folderの有無のみを判定する。
        """
        folder = self._get_owned_folder(workspace_id, folder_id)
        children = [f for f in self._folder_repository.list_by_workspace(workspace_id) if f.parent_folder_id == folder_id]

        if children and not cascade:
            raise ConflictError(
                entity_type="Folder", entity_id=folder_id,
                reason=f"has {len(children)} child folder(s); pass cascade=true to delete them as well",
            )

        if cascade:
            for child in children:
                self.delete(workspace_id, child.id, cascade=True)

        self._folder_repository.delete(folder.id)

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------

    def _get_owned_folder(self, workspace_id: str, folder_id: str) -> Folder:
        folder = self._folder_repository.get(folder_id)
        if folder is None:
            raise NotFoundError(entity_type="Folder", entity_id=folder_id)
        if folder.workspace_id != workspace_id:
            # 他Workspaceからの操作は「存在しない」として扱う
            # (AP-002・API Design8章、Workspace Owner以外には
            # 存在の有無すら明かさないという既存の設計方針を踏襲)。
            raise NotFoundError(entity_type="Folder", entity_id=folder_id)
        return folder

    def _would_create_cycle(self, folder_id: str, new_parent_folder_id: str) -> bool:
        """`new_parent_folder_id`を`folder_id`の新しい親にした場合に
        循環が生じるかどうかを判定する。`new_parent_folder_id`から
        祖先を辿り、`folder_id`自身に到達するかを確認する(到達すれば
        循環)。"""
        if new_parent_folder_id == folder_id:
            return True

        visited: set[str] = set()
        current_id: str | None = new_parent_folder_id
        while current_id is not None:
            if current_id == folder_id:
                return True
            if current_id in visited:
                # 既存データが壊れている場合の防御(通常この分岐には
                # 到達しないはずだが、無限ループを避けるため安全側に倒す)。
                break
            visited.add(current_id)
            current = self._folder_repository.get(current_id)
            if current is None:
                break
            current_id = current.parent_folder_id
        return False
