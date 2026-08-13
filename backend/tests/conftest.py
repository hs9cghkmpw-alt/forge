"""pytest共通設定(FORGE-HANDOFF-LOCAL-AI-UX-004 §9対応、2026-08-13新設)。

`ProviderRouter.default_provider_name()`が、`GEMINI_API_KEY`がある環境では
`"gemini"`を既定にするようになった(「Silent Mock fallbackは禁止」への
対応、`provider_router.py`参照)。`app.main`は`backend/.env`を読み込むため、
開発者の手元では**テストが実際にGemini APIを呼びに行ってしまう**
(実際に発生した: 全体で110秒かかり、既定Providerを検証する4件が落ちた)。

テストは決定的かつオフラインで走るべきなので、テスト実行時の既定Provider
をここで明示的に固定する。Provider解決そのものを検証するテストは、この
環境変数を自分で差し替えて振る舞いを確認すること
(`tests/test_ai_runtime.py`参照)。

`setdefault`ではなく代入にしているのは、`.env`由来の`GEMINI_API_KEY`が
既に入っている状態でも確実に上書きするため。実Providerを使う検証を
したい場合は、テストではなく実機確認(uvicorn)で行う。
"""

from __future__ import annotations

import os

os.environ["FORGE_DEFAULT_PROVIDER"] = "mock"
