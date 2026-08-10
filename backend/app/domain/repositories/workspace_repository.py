"""WorkspaceRepositoryインターフェース(FORGE V2 Phase 1)。

`domain/README.md`の方針(`repositories/`はインターフェースのみ、
実装は`app/repositories/`が持つ)・`FORGE-V2-TYPE-DESIGN-REVIEW.md`
9章の`WorkspaceRepository`をそのまま実装したもの。

Architecture Principles AP-016(Repositories Perform Persistence,
Not Business Decisions)に従い、このインターフェースは`get`/`save`
という、データアクセスの意味そのままのメソッドのみを持つ。
「1 User = 1 Workspace」という制約の**検証**はUseCase層の責務であり、
Repository自体は「重複していたら拒否する」といった判断を行わない
(単純にデータを読み書きするだけ)。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.entities.workspace import Workspace


@runtime_checkable
class WorkspaceRepository(Protocol):
    """Workspaceの永続化を担うインターフェース。

    実装は`app/repositories/`配下に置く(infrastructure層)。
    `Protocol`を使うことで、実装クラスがこのクラスを明示的に
    継承しなくても、必要なメソッドを実装していれば構造的に
    適合する(Structural Subtyping、既存コードの型ヒント文化
    ——`forge_ai`各所の`Protocol`利用——と一貫性を保つ)。
    """

    def get(self, workspace_id: str) -> Workspace | None:
        """IDでWorkspaceを取得する。存在しなければ`None`。"""
        ...

    def get_by_owner(self, owner_user_id: str) -> Workspace | None:
        """Owner(User ID)でWorkspaceを取得する。存在しなければ`None`。"""
        ...

    def save(self, workspace: Workspace) -> None:
        """Workspaceを保存する(新規作成・更新のいずれも)。"""
        ...
