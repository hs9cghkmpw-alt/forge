"""DIコンテナ(`core/README.md`が予告していた`di.py`)。

`domain/repositories/`の**インターフェース**に、`app/repositories/`の
**実装**を束縛する(`domain/README.md`の依存ルール図の通り)。
FORGE V2 Phase 1では、`WorkspaceRepository`の束縛のみを行う。

**環境変数`FORGE_WORKSPACE_REPOSITORY_BACKEND`で切り替える**:
- `"memory"`(既定): `InMemoryWorkspaceRepository`。このサンドボックス
  も含め、`supabase`パッケージが無い環境でも動作する。
- `"supabase"`: `SupabaseWorkspaceRepository`。**未検証**
  (`supabase_workspace_repository.py`のdocstring参照)、CEO環境での
  利用を想定する。

`app/main.py`が直接`os.environ`を読む既存の規約(`core/config.py`と
いうPydantic Settingsクラスを介さない、Phase 1時点での最小実装)を
そのまま踏襲した。
"""

from __future__ import annotations

import os

from app.domain.repositories.workspace_repository import WorkspaceRepository
from app.repositories.in_memory_workspace_repository import InMemoryWorkspaceRepository

_ENV_VAR_NAME = "FORGE_WORKSPACE_REPOSITORY_BACKEND"

# プロセス内で使い回す、単一のRepositoryインスタンス
# (InMemory実装の場合、複数箇所で別インスタンスを作ると、それぞれが
# 独立したメモリを持ってしまい、1 User=1 Workspaceの保証が崩れるため、
# モジュールレベルのシングルトンとして保持する)。
_workspace_repository_singleton: WorkspaceRepository | None = None


def get_workspace_repository() -> WorkspaceRepository:
    """設定された環境変数に応じたWorkspaceRepository実装を返す
    (プロセス内で使い回すシングルトン)。"""
    global _workspace_repository_singleton
    if _workspace_repository_singleton is not None:
        return _workspace_repository_singleton

    backend_name = os.environ.get(_ENV_VAR_NAME, "memory").strip().lower()
    if backend_name == "supabase":
        # 未検証経路(supabase_workspace_repository.pyのdocstring参照)。
        # 実際のsupabaseクライアントの構築方法(URL/Keyの環境変数名等)は
        # Phase 1のScope外とし、CEO環境での実装に委ねる
        # (Remaining Risksへ記録済み)。
        raise NotImplementedError(
            "FORGE_WORKSPACE_REPOSITORY_BACKEND=supabase requires a live Supabase "
            "client, which cannot be constructed in this sandbox (network unavailable, "
            "'supabase' package not installed). CEO environment must wire an actual "
            "supabase.Client instance into SupabaseWorkspaceRepository here."
        )
    elif backend_name == "memory":
        _workspace_repository_singleton = InMemoryWorkspaceRepository()
        return _workspace_repository_singleton
    else:
        raise ValueError(
            f"Unknown {_ENV_VAR_NAME}={backend_name!r}, expected 'memory' or 'supabase'"
        )


def reset_workspace_repository_singleton_for_testing() -> None:
    """テスト間でシングルトンをリセットするためのヘルパー。本番
    コードパスからは呼ばれない(テストの独立性を保つためだけに存在
    する)。"""
    global _workspace_repository_singleton
    _workspace_repository_singleton = None
