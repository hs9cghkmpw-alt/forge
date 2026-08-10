"""共通例外クラス(`core/README.md`が予告していた`exceptions.py`)。

`FORGE-V2-TYPE-DESIGN-REVIEW.md` 15章のError Modelを、実際の
Python例外として実装したもの。**Phase 1(Workspace Foundation)が
実際に必要とする種別のみを実装する**(`ConflictError`・
`ValidationError`・`NotFoundError`・`PermissionError`)。
`VersionMismatchError`・`MigrationError`はPhase 6・Phase 8で
必要になった時点で追加する(Phase 1のScope外)。

`middleware/`(将来)またはRouter層で、これらをHTTP Status(API Design
Specification6章)へ変換する。このファイル自体はfastapi/pydanticに
一切依存しない、純粋なPython例外である。
"""

from __future__ import annotations


class ForgeDomainError(Exception):
    """FORGE V2のDomain層が送出する例外の共通基底クラス。"""


class ValidationError(ForgeDomainError):
    """入力値の形式・内容が不正な場合(Type Design15章)。HTTP 400相当。"""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class NotFoundError(ForgeDomainError):
    """指定されたEntityが存在しない場合(Type Design15章)。HTTP 404相当。"""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} not found: {entity_id}")


class ConflictError(ForgeDomainError):
    """状態上の矛盾(例: 1 User=1 Workspaceの重複作成試行)。HTTP 409相当。"""

    def __init__(self, entity_type: str, entity_id: str, reason: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.reason = reason
        super().__init__(f"{entity_type} {entity_id}: {reason}")


class PermissionError_(ForgeDomainError):
    """Owner以外によるアクセス(Type Design15章)。HTTP 403相当。

    組み込みの`PermissionError`(builtins)と名前が衝突するため、
    末尾に`_`を付けた。Router層でのimport時は`as`で読み替えることを
    推奨する(例: `from app.core.exceptions import PermissionError_ as
    ForgePermissionError`)。
    """

    def __init__(self, user_id: str, action: str, reason: str) -> None:
        self.user_id = user_id
        self.action = action
        self.reason = reason
        super().__init__(f"user {user_id} cannot {action}: {reason}")
