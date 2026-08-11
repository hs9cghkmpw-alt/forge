"""Forge Backend APIのエントリポイント。

**注記(2026-08-11更新)**: このセッションを通じて実際に何十回も
`uvicorn`を起動し、`POST /api/v1/ai/generate`への実リクエストで動作
確認している(TD15・TD31〜TD35等、TECH_DEBT.md参照)。かつては
「Claudeのサンドボックスにfastapiが無いため一度も起動できていない」
という記述だったが、その後fastapi等がインストール可能な環境が整い、
この記述は事実と異なるまま放置されていた(2026-08-11のドキュメント
棚卸しで発見・訂正)。

**起動方法(FORGE v1.0 Candidate Patch3で確定)**:

```
cd <repository root>
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

を、リポジトリルートから、追加の環境変数設定無しで実行できる。

**パッケージ構成についての注記(このPatchで修正した問題)**:

`backend/app`配下のコード(`app.routers.ai`・`app.ai.runtime.*`等)は、
歴史的経緯により`from app.X import Y`という、**`backend/`自体が
sys.pathに乗っている**ことを前提にした絶対importで書かれている
(`backend/tests/*.py`が`sys.path.insert(0, ".."))`で`backend/`を
追加した上でこの前提のまま動いてきたため)。一方、`forge_ai`パッケージ
は逆に**リポジトリルート**がsys.pathに乗っていることを前提にした
`from forge_ai.X import Y`という絶対importで書かれている。

`python -m uvicorn backend.app.main:app`をリポジトリルートから実行
すると、`-m`の仕様によりリポジトリルートはsys.pathへ自動的に追加
される(このため`forge_ai`は追加設定無しで解決できる、実際に
`python -c "import forge_ai"`が成功することからも確認できる)。
しかし`backend/`自体はsys.pathに含まれないため、上記の`app.X`という
importが解決できず`ModuleNotFoundError: app`になっていた(逆に
`backend/`内から`app.main:app`として起動すると、今度は`forge_ai`が
解決できず`ModuleNotFoundError: forge_ai`になっていた)。

この2つの絶対import規約(`app.X`はbackend相対、`forge_ai.X`は
リポジトリルート相対)を1つのプロセス内で両立させるため、**このモジュール
の最上部で、`backend/`とリポジトリルートの両方を明示的に
`sys.path`へ追加する**(`backend/tests/*.py`が既に行っている
`sys.path.insert`と同じ考え方を、テストコードだけでなく実行時
エントリポイント自身にも適用したもの)。これは「手動でのPYTHONPATH
設定」ではなく、コード自身が自己完結的に必要なパスを解決する処理で
あり、利用者側の環境変数設定は一切不要になる。

`backend/app/routers/ai.py`以下、間接的にimportされる全てのモジュールも、
Pythonの`sys.path`はプロセス全体で共有されるため、この最上部での
1回のパス追加だけで、以降のimport連鎖全体に反映される。
"""

from __future__ import annotations

import os
import sys

_THIS_FILE = os.path.abspath(__file__)
_BACKEND_DIR = os.path.dirname(os.path.dirname(_THIS_FILE))  # .../backend
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)  # リポジトリルート

for _path in (_BACKEND_DIR, _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# TD35(2026-08-11、FORGE-AI-QUALITY-001)で発見・修正した実バグ:
# `backend/.env`・`backend/.env.example`はGEMINI_API_KEYの設定場所として
# 案内していた(GETTING_STARTED.md・providers.pyのdocコメント等)。
# `requirements.txt`にも`python-dotenv`が依存として入っていたが、
# **実際にこのファイルを読み込むコードがどこにも存在しなかった**。
# そのためGEMINI_API_KEYは、利用者が`.env`に書くだけでは一切反映されず、
# 別途OSの環境変数として明示的にexportした場合のみ動作する、という
# 実質的に無意味な状態になっていた。
#
# 発見の経緯: `choice_field`/`bar_chart`(TD34)の実機検証中、
# 「あるDomainのプロンプトは成功するのに、別のプロンプトだけ
# 『GEMINI_API_KEYが設定されていません』という(実際にはキーが.envに
# 存在するのに)エラーで失敗する」という現象を発見した。調査の結果、
# household_budget等7 Domain(`forge_ai/core/ir/`経由)は
# `ForgeLanguageCompiler`が完全に決定的(Provider呼び出し無し)である
# ため、キーの有無に関わらず「成功」していただけで、実際にGeminiへ
# 到達していたのは`Compiler.compile()`(Legacy Domain・
# `forge_ai/core/compiler.py`)を経由するリクエストだけだった——そして
# そちらは`.env`が読み込まれないため常に失敗していた。
#
# `os.environ`に既存の値がある場合は上書きしない(`load_dotenv()`の
# 既定動作、`override=False`)ため、本番デプロイ環境で実際の環境変数
# として設定されているケースには影響しない。
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.feature_flags import is_folder_enabled, is_workspace_enabled
from app.exception_handlers import register_exception_handlers
from app.routers.ai import router as ai_router

# FORGE-MERGE-001 縦の一本(Home→Confirm→Mock Generator→Validator→Renderer)により
# 最初のrouterを追加した。FORGE-MILESTONE-005で、`/api/v1/ai/generate`を
# AI Runtime Pipeline(`PromptPipeline`、M004↔M005接続)経由の実装へ全面改訂し、
# 共通Error Envelope(指示書12章)を返す例外ハンドラを登録した。
app = FastAPI(title="Forge API", version="0.1.0")

app.include_router(ai_router)
register_exception_handlers(app)

# FORGE V2 Phase 1(Workspace Foundation)。既存ユーザーへの影響を避ける
# ため、Feature Flag(`FORGE_FEATURE_WORKSPACE=true`)が有効な場合のみ
# Routerを登録する(`FORGE-V2-IMPLEMENTATION-ROADMAP.md` 2章「Feature
# Flag First」原則)。Flag OFF(既定)の場合、`/v1/workspace`は
# 404(未登録のパス)のままであり、既存の挙動には一切影響しない。
if is_workspace_enabled():
    from app.routers.workspace import router as workspace_router

    app.include_router(workspace_router)

# FORGE V2 Phase 2 Step 1(Folder)。Workspace機能とは独立したFeature
# Flag(`FORGE_FEATURE_FOLDER=true`)で制御する(Workspaceのみ有効化
# したまま、Folderは無効のままにしておく段階的ロールアウトを許す)。
if is_folder_enabled():
    from app.routers.folder import router as folder_router

    app.include_router(folder_router)


# ---------------------------------------------------------------------------
# CORS(Flutter Backend接続対応で新設)
#
# Flutter Web(`flutter run -d chrome`)は、ランダムなポート番号の
# `http://localhost:<port>`から起動することが多く、開発時に固定の
# Originを1つだけ許可するのは非現実的。一方、無条件の`allow_origins=
# ["*"]`を本番設定として固定することも禁止事項(指示書「無条件の
# ワイルドカード設定を本番設定として固定しないでください」)に反する。
#
# `FORGE_ENV`環境変数(既定"development")で開発/本番を分離する。
# - development: `http://localhost:<任意のポート>`・
#   `http://127.0.0.1:<任意のポート>`のみを正規表現で許可する
#   (ワイルドカード`*`は使わない)。
# - production等それ以外: `FORGE_CORS_ALLOWED_ORIGINS`(カンマ区切り)で
#   明示的に指定されたOriginのみを許可する。未設定の場合、Originを
#   一切許可しない(安全側のデフォルト。無条件許可はしない)。
# ---------------------------------------------------------------------------

_FORGE_ENV = os.environ.get("FORGE_ENV", "development")

if _FORGE_ENV == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    _explicit_origins = [
        origin.strip()
        for origin in os.environ.get("FORGE_CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_explicit_origins,  # 未設定なら空リスト = 全て拒否(安全側)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
