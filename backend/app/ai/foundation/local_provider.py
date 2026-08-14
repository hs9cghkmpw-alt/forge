"""Local Model Provider(FORGE-QUALITY-AI-INDEPENDENCE-003 Phase G、
2026-08-12。FORGE-AI-FOUNDATION-010 Phase Eで汎用Adapterの上へ載せ替え)。

ローカルで動く推論Runtime(Ollama等)へ、`LLMAdapter`契約で接続する。

**Ollama固定にしていない**(指示書17章): 実際に叩くのは
**OpenAI互換の`/v1/chat/completions`**であり、Ollamaはこれを標準で
提供する(`OLLAMA_HOST/v1`)。同じ形を話すRuntime(llama.cpp の
`llama-server`、LM Studio、vLLM、text-generation-webui 等)なら、
`base_url`を変えるだけで動く。したがってこのクラスは
「Ollama Provider」ではなく`LocalModelProvider`である。

    LocalModelProvider
            ↓  OpenAICompatibleAdapter(共通実装)
       Local Runtime(Ollama / llama.cpp / LM Studio / …)
            ↓
       Open-weight Model

---

## Phase Eで何を移したか

HTTP往復・`response_format`の組み立て・JSON抽出・1回だけの再試行は、
**Localに固有ではない**。同じ処理をCloudのOpenAI互換Provider
(Groq / OpenRouter 等)でも書くことになり、そのたびに同じバグを
書き直すことになる。`openai_compatible.py`へ移した。

ここに残しているのは**Localに固有な判断だけ**である:

* 既定の`base_url`と`model`(Ollamaの標準)
* 失敗を`LocalModelError`として見せること——運用者にとって
  「Ollamaが起動していない」と「ネットワークが落ちている」は
  取るべき対処が違う。`classify_exception()`はこの型を
  `LOCAL_RESOURCE_ERROR`へ写す。

## この環境では実行できていない(正直な申告)

開発サンドボックスは`huggingface.co`へのアクセスがネットワーク
ポリシーで拒否されており(CONNECT 403)、Ollamaも未インストール、
GPUも無い。したがって**モデル重みを取得できず、このProviderを
実モデルに対して動かした実績は無い**。HTTP契約・JSON抽出・再試行・
エラー処理は単体テストで検証済みだが、指示書31章 最低条件Eの
「実際にLocal Modelで実行してBenchmarkを取得する」は未達である。
実行に必要なものは`docs/development/LOCAL_MODEL_SETUP.md`に記載した。
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.ai.foundation.openai_compatible import (
    OpenAICompatibleAdapter,
    ResponseFormatError,
    extract_json_object as _extract_json_object,
)

__all__ = ["LocalModelProvider", "LocalModelError", "extract_json_object"]

_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
_DEFAULT_MODEL = "qwen2.5:1.5b-instruct"
_DEFAULT_TIMEOUT_SECONDS = 120.0


class LocalModelError(ResponseFormatError):
    """ローカルRuntimeへ接続できない、または使える応答が得られなかった。

    `ResponseFormatError`を継承しているのは型階層の都合であって、
    意味の中心は**「Local固有の問題である」**という点にある
    ——`classify_exception()`はクラス名を見て`LOCAL_RESOURCE_ERROR`へ
    写し、`ProviderStateStore`はそれをCircuit Breakerの対象として扱う。
    """


def extract_json_object(text: str) -> dict[str, Any]:
    """モデルの生応答からJSONオブジェクトを取り出す。

    実装は`openai_compatible.extract_json_object()`。ここでは
    失敗時の例外型を`LocalModelError`へ固定した薄い別名として残す
    (既存の呼び出し側・テストとの後方互換)。
    """
    return _extract_json_object(text, error_type=LocalModelError)


class LocalModelProvider(OpenAICompatibleAdapter):
    """`LLMAdapter` Protocolを満たす、ローカル推論Runtimeへの接続。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        super().__init__(
            provider_name="local",
            base_url=(
                base_url or os.environ.get("FORGE_LOCAL_BASE_URL") or _DEFAULT_BASE_URL
            ),
            model=model or os.environ.get("FORGE_LOCAL_MODEL") or _DEFAULT_MODEL,
            # Local Runtimeは認証を要求しない(§: 鍵不要)。
            api_key_env=None,
            timeout_seconds=timeout_seconds
            or float(os.environ.get("FORGE_LOCAL_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS)),
        )

    def _response_format_error_type(self) -> type[Exception]:
        return LocalModelError

    def _connection_error(self, exc: httpx.HTTPError) -> Exception:
        """「Ollamaが起動していない」という、**運用者が直せる**言葉にする。

        汎用Adapterの既定は`NETWORK`だが、Localでこれが起きる原因は
        ほぼ「Runtimeを起動していない」であり、ネットワーク障害を
        疑わせるメッセージは調査を遠回りさせる。
        """
        return LocalModelError(
            f"ローカル推論Runtimeへ接続できませんでした({self.base_url})。"
            f"Ollama等が起動しているか確認してください(詳細: {exc})"
        )
