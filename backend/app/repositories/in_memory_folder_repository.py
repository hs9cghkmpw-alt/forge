"""InMemoryFolderRepository(FORGE V2 Phase 2 Step 1)。

`FolderRepository`Protocolの、プロセス内メモリのみで完結する実装。
Phase 1の`InMemoryWorkspaceRepository`と同じ設計判断(fastapi/
pydantic/supabaseのいずれにも依存しないため、このサンドボックスでも
実際に実行・検証できる)。**循環判定は行わない**(Repository層の
責務ではない、`folder_repository.py`のdocstring参照)。
"""

from __future__ import annotations

import threading

from app.domain.entities.folder import Folder


class InMemoryFolderRepository:
    """`FolderRepository`Protocolを構造的に満たす、メモリ内実装。"""

    def __init__(self) -> None:
        self._by_id: dict[str, Folder] = {}
        self._lock = threading.Lock()

    def get(self, folder_id: str) -> Folder | None:
        with self._lock:
            return self._by_id.get(folder_id)

    def list_by_workspace(self, workspace_id: str) -> tuple[Folder, ...]:
        with self._lock:
            return tuple(f for f in self._by_id.values() if f.workspace_id == workspace_id)

    def save(self, folder: Folder) -> None:
        with self._lock:
            self._by_id[folder.id] = folder

    def delete(self, folder_id: str) -> None:
        with self._lock:
            self._by_id.pop(folder_id, None)
