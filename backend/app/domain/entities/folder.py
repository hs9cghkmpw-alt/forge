"""Folder Entity(FORGE V2 Phase 2 Step 1、Folder実装)。

`FORGE-V2-TYPE-DESIGN-REVIEW.md` 3.13節の`Folder`定義をそのまま
実装したもの。**fastapi/pydantic/supabaseのいずれにも依存しない、
純粋なPythonのみで構成する**(Phase 1と同じ規約)。

**Type変更禁止という絶対条件への対応(重要な注記)**: Type Design
Reviewは`Folder.application_ids: tuple[str, ...]`(排他的所属)を
定義しているが、`Application`はPhase 3まで実装されない。DB設計
(`FORGE-V2-DATABASE-DESIGN-SPECIFICATION.md` 4.5節)でも、この
関係は`applications.folder_id`という**Application側のFK**として
正規化されており、`folders`テーブル自体には`application_ids`という
列は無い(4.2節、今回のMigrationにも含めない)。

したがって、Type定義上のフィールド自体は維持しつつ(Type変更禁止を
文字通り守る)、**Phase 2 Step 1の実装では、この値は常に空タプルの
ままであり、DB往復では一切使われない、計算専用の補助フィールド**と
して位置づける。Phase 3でApplicationが実装された時点で、
Repository層が実際にJOIN等で値を埋める形になる想定である
(Final Report・Remaining Risksへ記録済み)。
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Folder:
    """Folder(排他的な階層まとめ)。

    更新は`dataclasses.replace()`による新インスタンス生成で行う
    (Phase 1の`Workspace`と同じ不変更新パターン)。
    """

    id: str
    workspace_id: str
    name: str
    parent_folder_id: str | None = None
    created_at: str = ""
    application_ids: tuple[str, ...] = ()  # 上記docstring参照、Phase 3まで常に空

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Folder.id must not be empty")
        if not self.workspace_id:
            raise ValueError("Folder.workspace_id must not be empty")
        if not self.name or not self.name.strip():
            raise ValueError("Folder.name must not be empty")
        if self.parent_folder_id == self.id:
            raise ValueError("Folder.parent_folder_id must not reference itself directly")

    def with_name(self, name: str) -> "Folder":
        """`name`だけを変更した、新しいFolderを返す。空文字の場合、
        `__post_init__`のValidationにより`ValueError`を送出する。"""
        return dataclasses.replace(self, name=name)

    def with_parent_folder_id(self, parent_folder_id: str | None) -> "Folder":
        """`parent_folder_id`だけを変更した、新しいFolderを返す。

        **循環検出はここでは行わない**(Entity自身は「直接の自己
        参照」だけを`__post_init__`で拒否する。祖先を辿る循環検出は
        `FolderService`の責務、Type Design Review・Database Design
        Specification8章のBusiness Constraintで既に整理済みの
        設計方針をそのまま踏襲する)。
        """
        return dataclasses.replace(self, parent_folder_id=parent_folder_id)
