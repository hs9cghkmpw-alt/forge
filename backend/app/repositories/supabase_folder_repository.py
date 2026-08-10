"""SupabaseFolderRepository(FORGE V2 Phase 2 Step 1、本番用実装)。

**注記(重要、未検証)**: `app/repositories/supabase_workspace_
repository.py`と全く同じ制限(`supabase`パッケージ未導入、
ネットワーク不可)。一度もimport・実行できていない。CEO環境での
検証が必要。

`FORGE-V2-DATABASE-DESIGN-SPECIFICATION.md` 4.2節の`folders`
テーブル定義と対応する(`backend/migrations/0002_create_folders.
sql`参照)。
"""

from __future__ import annotations

from typing import Any

from app.domain.entities.folder import Folder

_TABLE_NAME = "folders"


class SupabaseFolderRepository:
    """`FolderRepository`Protocolを構造的に満たす、Supabase実装。"""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, folder_id: str) -> Folder | None:
        response = self._client.table(_TABLE_NAME).select("*").eq("id", folder_id).limit(1).execute()
        rows = response.data
        if not rows:
            return None
        return _row_to_folder(rows[0])

    def list_by_workspace(self, workspace_id: str) -> tuple[Folder, ...]:
        response = self._client.table(_TABLE_NAME).select("*").eq("workspace_id", workspace_id).execute()
        return tuple(_row_to_folder(row) for row in response.data)

    def save(self, folder: Folder) -> None:
        self._client.table(_TABLE_NAME).upsert(_folder_to_row(folder)).execute()

    def delete(self, folder_id: str) -> None:
        self._client.table(_TABLE_NAME).delete().eq("id", folder_id).execute()


def _row_to_folder(row: dict[str, Any]) -> Folder:
    # `application_ids`はDBカラムとして存在しない(folder.pyのdocstring
    # 参照、Phase 3まで常に空タプル)。
    return Folder(
        id=row["id"],
        workspace_id=row["workspace_id"],
        name=row["name"],
        parent_folder_id=row.get("parent_folder_id"),
        created_at=row["created_at"],
    )


def _folder_to_row(folder: Folder) -> dict[str, Any]:
    return {
        "id": folder.id,
        "workspace_id": folder.workspace_id,
        "name": folder.name,
        "parent_folder_id": folder.parent_folder_id,
        "created_at": folder.created_at,
    }
