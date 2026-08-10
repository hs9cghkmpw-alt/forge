"""SupabaseWorkspaceRepository(FORGE V2 Phase 1、本番用実装)。

**注記(重要、未検証)**: このファイルは`supabase`パッケージ
(`requirements.txt`に`supabase==2.5.1`として記載済みだが、Claudeの
サンドボックスにはインストールされておらず、ネットワークも無いため
導入できなかった)に依存する。したがってこのファイル自体は一度も
import・実行できていない(`app/schemas/ai.py`・`app/routers/ai.py`が
既に開示している、同種の制限)。**CEO環境で`pip install -r
requirements.txt`実行後、実際のSupabaseプロジェクトに対して動作
確認する必要がある。**

`FORGE-V2-DATABASE-DESIGN-SPECIFICATION.md` 4.1節の`workspaces`
テーブル定義、12章のRLS Policyと対応する
(`backend/migrations/0001_create_workspaces.sql`参照)。RLSが
有効化されているため、このRepositoryが発行するクエリ自体は
`owner_user_id`でのフィルタを明示的に書かなくても、Supabase側の
RLSによってUser本人の行以外は返らない(ただし、コード上の意図を
明確にするため、`get_by_owner`では`owner_user_id`を明示的に
WHERE句へ含めている)。
"""

from __future__ import annotations

from typing import Any

from app.domain.entities.workspace import Workspace

_TABLE_NAME = "workspaces"


class SupabaseWorkspaceRepository:
    """`WorkspaceRepository`Protocolを構造的に満たす、Supabase実装。"""

    def __init__(self, client: Any) -> None:
        """`client`は`supabase.Client`(`supabase.create_client(...)`の
        戻り値)を想定する。型ヒントを`Any`にしているのは、`supabase`
        パッケージがこのサンドボックスに無く、`from supabase import
        Client`が実行できないため(型情報だけのimportも失敗する)。
        CEO環境でこのファイルを検証する際、`Client`型を正しく
        importして型ヒントを厳密化することを推奨する。
        """
        self._client = client

    def get(self, workspace_id: str) -> Workspace | None:
        response = (
            self._client.table(_TABLE_NAME)
            .select("*")
            .eq("id", workspace_id)
            .limit(1)
            .execute()
        )
        rows = response.data
        if not rows:
            return None
        return _row_to_workspace(rows[0])

    def get_by_owner(self, owner_user_id: str) -> Workspace | None:
        response = (
            self._client.table(_TABLE_NAME)
            .select("*")
            .eq("owner_user_id", owner_user_id)
            .limit(1)
            .execute()
        )
        rows = response.data
        if not rows:
            return None
        return _row_to_workspace(rows[0])

    def save(self, workspace: Workspace) -> None:
        # upsert: 既存行が無ければINSERT、あればUPDATE(`id`が競合キー)。
        # 「新規作成」と「更新」を1つのメソッドで扱うという、
        # WorkspaceRepositoryインターフェース自体の設計(Type Design
        # Review9章)に合わせた実装。
        self._client.table(_TABLE_NAME).upsert(_workspace_to_row(workspace)).execute()


def _row_to_workspace(row: dict[str, Any]) -> Workspace:
    return Workspace(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        created_at=row["created_at"],
        structure_version=row["structure_version"],
        display_default_view=row["display_default_view"],
    )


def _workspace_to_row(workspace: Workspace) -> dict[str, Any]:
    return {
        "id": workspace.id,
        "owner_user_id": workspace.owner_user_id,
        "created_at": workspace.created_at,
        "structure_version": workspace.structure_version,
        "display_default_view": workspace.display_default_view,
    }
