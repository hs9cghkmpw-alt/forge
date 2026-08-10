"""WorkspaceFactory(FORGE V2 Phase 1)。

`FORGE-V2-TYPE-DESIGN-REVIEW.md` 11章の`WorkspaceFactory`をそのまま
実装したもの。Architecture Principles AP-033(Factory Construction
Must Preserve Invariants)に従い、**途中状態が外へ見えない**形で
初期Workspaceを組み立てる。

このFactory自体はRepositoryを呼ばない(値の組み立てのみ担当し、
実際の永続化はUseCase層が単一トランザクションとして行う、
`FORGE-V2-TYPE-DESIGN-REVIEW.md` 11章のコメントをそのまま踏襲)。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domain.entities.workspace import Workspace


def create_initial_workspace(owner_user_id: str) -> Workspace:
    """新規User登録時、一貫性の取れた初期Workspaceを構築する。

    - `id`はここで新規採番する(UUID、Database Design Specification
      5章「PKにUUIDを採用する理由」——分散生成が可能、連番から件数を
      推測されない——をそのままEntity生成レベルでも踏襲する)。
    - `created_at`はUTCの現在時刻(ISO8601)。
    - `structure_version`・`display_default_view`は既定値
      (`Workspace`の`__post_init__`で検証済みの値)のまま。

    戻り値はまだ永続化されていない、メモリ上の値である
    (Repository/UseCase層が、この戻り値をそのまま`save()`する
    責務を持つ)。
    """
    if not owner_user_id:
        raise ValueError("create_initial_workspace() requires a non-empty owner_user_id")

    return Workspace(
        id=str(uuid.uuid4()),
        owner_user_id=owner_user_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
