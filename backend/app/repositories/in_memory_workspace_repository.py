"""InMemoryWorkspaceRepository(FORGE V2 Phase 1)。

`WorkspaceRepository`(`domain/repositories/workspace_repository.py`)
の、プロセス内メモリのみで完結する実装。**fastapi/pydantic/
supabaseのいずれにも依存しないため、このサンドボックスでも実際に
実行・検証できる**(`app/ai/runtime/confirmation_store.py`と同じ、
既存の設計判断——「早すぎるマイクロサービス化禁止」「Database追加
禁止」の方針時と同様、まずメモリ内実装で仕様を固める——を踏襲する)。

**用途**: (1)単体テスト・開発時のRepository代替として使う、
(2)`SupabaseWorkspaceRepository`(本番用、`supabase_workspace_
repository.py`)が実際にネットワーク越しに検証できるようになるまでの
繋ぎとして使う。`core/di.py`が、環境変数に応じてどちらを使うかを
切り替える(`di.py`参照)。

**永続化についての既知の制限**: サーバー再起動や複数ワーカー構成では
保持されない(`ConfirmationStore`と同じ制限、TECH_DEBTとして記録)。
"""

from __future__ import annotations

import threading

from app.domain.entities.workspace import Workspace


class InMemoryWorkspaceRepository:
    """`WorkspaceRepository`Protocolを構造的に満たす、メモリ内実装。"""

    def __init__(self) -> None:
        self._by_id: dict[str, Workspace] = {}
        self._by_owner: dict[str, str] = {}  # owner_user_id -> workspace_id
        self._lock = threading.Lock()

    def get(self, workspace_id: str) -> Workspace | None:
        with self._lock:
            return self._by_id.get(workspace_id)

    def get_by_owner(self, owner_user_id: str) -> Workspace | None:
        with self._lock:
            workspace_id = self._by_owner.get(owner_user_id)
            if workspace_id is None:
                return None
            return self._by_id.get(workspace_id)

    def save(self, workspace: Workspace) -> None:
        with self._lock:
            self._by_id[workspace.id] = workspace
            self._by_owner[workspace.owner_user_id] = workspace.id
