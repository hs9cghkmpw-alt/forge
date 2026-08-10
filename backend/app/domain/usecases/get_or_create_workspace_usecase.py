"""GetOrCreateWorkspaceUseCase(FORGE V2 Phase 1)。

`domain/README.md`の規約(「1ユースケース=1クラス」「entitiesと
repositoriesのインターフェースのみに依存する」)に従う。
`FORGE-V2-TYPE-DESIGN-REVIEW.md` 7章`GetWorkspaceQuery`+
Freeze Report13章「初回アクセス時の自動作成」の判断を実装する。

fastapi/pydanticに一切依存しない、純粋なPythonのみで構成する
(このサンドボックスでも実際に実行・検証できる)。
"""

from __future__ import annotations

from app.domain.entities.workspace import Workspace
from app.domain.entities.workspace_factory import create_initial_workspace
from app.domain.repositories.workspace_repository import WorkspaceRepository


class GetOrCreateWorkspaceUseCase:
    """認証されたUser本人のWorkspaceを返す。存在しなければ
    `WorkspaceFactory`経由で自動作成し、`Repository.save()`する。

    **1 User = 1 Workspaceの保証**: `get_by_owner()`が`None`を返した
    場合のみ新規作成するため、同じ`owner_user_id`に対して複数回
    呼び出しても、2件目以降は既存のWorkspaceがそのまま返る
    (Repository実装がスレッドセーフである限り、この保証は成り立つ。
    `InMemoryWorkspaceRepository`は`threading.Lock`で保護済み)。
    """

    def __init__(self, workspace_repository: WorkspaceRepository) -> None:
        self._workspace_repository = workspace_repository

    def execute(self, owner_user_id: str) -> Workspace:
        existing = self._workspace_repository.get_by_owner(owner_user_id)
        if existing is not None:
            return existing

        new_workspace = create_initial_workspace(owner_user_id)
        self._workspace_repository.save(new_workspace)
        return new_workspace
