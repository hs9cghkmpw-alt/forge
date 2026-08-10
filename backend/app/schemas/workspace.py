"""Workspace関連のRequest/Response DTO(FORGE V2 Phase 1)。

`FORGE-V2-API-DESIGN-SPECIFICATION.md` 4.1節(`GET`/`PATCH
/v1/workspace`)・5章(DTO Mapping)、`FORGE-V2-TYPE-DESIGN-REVIEW.md`
8章の`WorkspaceDetailDTO`をそのまま実装したもの。

**注記(重要)**: このファイルはpydanticに依存する。Claudeのサンド
ボックスにはpydantic・fastapiがインストールされておらず、ネット
ワークも無いため導入できなかった(`app/schemas/ai.py`と同じ制限)。
したがってこのファイル自体は一度もimport・実行できていない
(構文は目視で確認したが、Pydantic v2の実際の挙動での検証はできて
いない)。CEO環境で`pip install -r requirements.txt`実行後、初めて
動作確認できる。

Architecture Principles AP-015(Domain Objects Do Not Cross API
Boundaries)に従い、`app.domain.entities.workspace.Workspace`を
そのまま返さず、このDTOへ変換してから返す(`app/routers/
workspace.py`参照)。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.entities.workspace import VALID_VIEW_TYPES


class WorkspaceDetailDTO(BaseModel):
    """`GET`/`PATCH /v1/workspace`のResponse Body。

    `FORGE-V2-TYPE-DESIGN-REVIEW.md` 8章の`WorkspaceDetailDTO`を、
    Phase 1の実装範囲(Folder/Collection一覧はまだ存在しないため
    空配列)に合わせて簡略化した。Phase 2でFolder/Collectionが
    実装され次第、`folders`/`collections`フィールドを追加する
    (Additive-Only、AP-018)。
    """

    id: str
    display_default_view: str = Field(description=f"one of {VALID_VIEW_TYPES}")
    structure_version: int


class UpdateWorkspaceSettingsRequestDTO(BaseModel):
    """`PATCH /v1/workspace`のRequest Body。

    `display_default_view`のみ更新可能(API Design Specification
    4.1節)。指定しない場合は無変更。
    """

    display_default_view: str | None = None


def workspace_to_detail_dto(workspace) -> WorkspaceDetailDTO:  # type: ignore[no-untyped-def]
    """`Workspace`(Domain Entity)を`WorkspaceDetailDTO`(API境界用)へ
    変換する。Domain EntityをAPI外へ直接公開しないための、唯一の
    変換経路(AP-015)。

    引数の型ヒントを省略しているのは、このファイル自体が
    `Workspace`をimportすると、`app.domain.entities.workspace`
    経由でpydantic非依存のコードとpydantic依存のコードが1ファイル内で
    混在するため、意図的に緩くしている(呼び出し側=Router層で正しい
    型を渡す責務を持つ)。
    """
    return WorkspaceDetailDTO(
        id=workspace.id,
        display_default_view=workspace.display_default_view,
        structure_version=workspace.structure_version,
    )
