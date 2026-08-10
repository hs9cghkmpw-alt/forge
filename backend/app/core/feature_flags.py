"""Feature Flag(FORGE V2 Phase 1、絶対条件「Feature Flag配下で実装
する」への対応)。

`FORGE-V2-IMPLEMENTATION-ROADMAP.md` 2章(Feature Flag First)・
9章(Rollback Strategy、「Feature FlagをOFFにするだけで即座に
無効化できる」)を実現する、最小の仕組み。**まだ複数Flagの管理・
リモート設定等は行わない**(現時点ではWorkspace機能1つだけを
ON/OFFする、最小限の実装。将来Phase 2以降で複数Flagが必要になった
場合、この関数の一般化——`os.environ`のプレフィックスで動的に
Flag名を解決する等——を検討する)。

既存の`app/main.py`が`FORGE_ENV`を`os.environ.get(...)`で直接読む、
という規約(Pydantic Settingsクラスを介さない、最小限の実装)を、
Feature Flagにもそのまま適用した——`core/config.py`(Pydantic
Settingsを使う、正式な設定管理)は`core/README.md`が「今後追加」と
している通り未実装であり、Phase 1のScopeでは新設しない。
"""

from __future__ import annotations

import os

_ENV_VAR_NAME = "FORGE_FEATURE_WORKSPACE"
_FOLDER_ENV_VAR_NAME = "FORGE_FEATURE_FOLDER"


def is_workspace_enabled() -> bool:
    """Workspace機能(Phase 1)が有効かどうかを返す。

    既定は無効(`False`)。既存ユーザーへの影響を避けるため、
    明示的に環境変数を`"true"`(大文字小文字を区別しない)へ
    設定しない限り、Workspace関連のRouterは登録されない
    (`app/main.py`参照)。
    """
    return os.environ.get(_ENV_VAR_NAME, "false").strip().lower() == "true"


def is_folder_enabled() -> bool:
    """Folder機能(Phase 2 Step 1)が有効かどうかを返す。

    `is_workspace_enabled()`とは**独立した、別のFlag**とした
    (Implementation Roadmap6章、Phase毎に専用ブランチ・専用Flagを
    持つという方針をそのまま踏襲)。Workspace機能がONでもFolder機能は
    OFFのまま、という段階的なロールアウトを可能にする。
    """
    return os.environ.get(_FOLDER_ENV_VAR_NAME, "false").strip().lower() == "true"
