"""Local Model Provider(FORGE-QUALITY-AI-INDEPENDENCE-003 Phase G、
2026-08-12)。

ローカルで動く推論Runtime(Ollama等)へ、`LLMAdapter`契約で接続する。

**Ollama固定にしていない**(指示書17章): 実際に叩くのは
**OpenAI互換の`/v1/chat/completions`**であり、Ollamaはこれを標準で
提供する(`OLLAMA_HOST/v1`)。同じ形を話すRuntime(llama.cpp の
`llama-server`、LM Studio、vLLM、text-generation-webui 等)なら、
`base_url`を変えるだけで動く。したがってこのクラスは
「Ollama Provider」ではなく`LocalModelProvider`である。

    LocalModelProvider
            ↓  OpenAI互換 HTTP
       Local Runtime(Ollama / llama.cpp / LM Studio / …)
            ↓
       Open-weight Model

**Structured Outputの扱い**: OpenAI互換APIの`response_format`
(`json_schema` / `json_object`)を使う。小さいローカルモデルは
`json_schema`を完全には守れないことが多いため、

1. `response_format={"type": "json_schema", ...}`で要求する
2. 応答からJSONを抽出する(```json フェンス等の混入に耐える)
3. パースできなければ`json_object`で1回だけ再試行する

という段構えにしている。**それでも駄目なら例外**であり、
`ModelGateway`がfallback Providerへ回す(指示書21章)。ここで
黙って空dictを返すと、TD40(Geminiが空`{}`を返して合成が静かに
失敗し続けた事故)と同じことが起きる。

**この環境では実行できていない(正直な申告)**: 開発サンドボックスは
`huggingface.co`へのアクセスがネットワークポリシーで拒否されており
(CONNECT 403)、Ollamaも未インストール、GPUも無い。したがって
**モデル重みを取得できず、このProviderを実モデルに対して動かした
実績は無い**。HTTP契約・JSON抽出・再試行・エラー処理は単体テストで
検証済みだが、指示書31章 最低条件Eの「実際にLocal Modelで実行して
Benchmarkを取得する」は未達である。実行に必要なものは
`docs/development/LOCAL_MODEL_SETUP.md`に記載した。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

__all__ = ["LocalModelProvider", "LocalModelError", "extract_json_object"]

_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
_DEFAULT_MODEL = "qwen2.5:1.5b-instruct"
_DEFAULT_TIMEOUT_SECONDS = 120.0

# ```json ... ``` のようなコードフェンス。小さいモデルは指示しても
# しばしばフェンスを付けてくるため、剥がしてからパースする。
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class LocalModelError(RuntimeError):
    """ローカルRuntimeへ接続できない、または使える応答が得られなかった。"""


def extract_json_object(text: str) -> dict[str, Any]:
    """モデルの生応答からJSONオブジェクトを取り出す。

    小さいローカルモデルは、素のJSONではなく
    「はい、こちらです: ```json {...} ```」のような応答を返しがちで
    あるため、次の順に試す:

    1. そのままパース
    2. コードフェンスの中身をパース
    3. 最初の `{` から最後の `}` までを切り出してパース

    どれも駄目なら`LocalModelError`。**空dictを返して「成功」に
    見せかけない**(TD40の教訓)。
    """
    candidates: list[str] = []
    stripped = (text or "").strip()
    if stripped:
        candidates.append(stripped)
    fenced = _FENCE_RE.search(text or "")
    if fenced:
        candidates.append(fenced.group(1).strip())
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    raise LocalModelError(
        f"ローカルモデルの応答からJSONを取り出せませんでした(先頭200文字: {stripped[:200]!r})"
    )


class LocalModelProvider:
    """`LLMAdapter` Protocolを満たす、ローカル推論Runtimeへの接続。

    `provider_name`は`GeminiProvider`等と同じく、Routing表・Benchmark
    結果の見出しに使われる識別子。
    """

    provider_name = "local"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._base_url = (base_url or os.environ.get("FORGE_LOCAL_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
        self._model = model or os.environ.get("FORGE_LOCAL_MODEL") or _DEFAULT_MODEL
        self._timeout = timeout_seconds or float(
            os.environ.get("FORGE_LOCAL_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS)
        )

    @property
    def model(self) -> str:
        return self._model

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        """`LLMAdapter`契約の実装。

        `response_schema`が空dictの場合、`GeminiProvider`と同じ意味
        (=スキーマ強制なしの自由JSON)として扱う。この「空スキーマ=
        freeform」という規約は`forge_operation.py`が既に依存している
        ため、Provider間で揃える必要がある。
        """
        try:
            content = self._chat(prompt, response_schema)
        except httpx.HTTPError as exc:
            raise LocalModelError(
                f"ローカル推論Runtimeへ接続できませんでした({self._base_url})。"
                f"Ollama等が起動しているか確認してください(詳細: {exc})"
            ) from exc

        try:
            return extract_json_object(content)
        except LocalModelError:
            if not response_schema:
                raise
            # json_schemaを守れなかった場合の1回だけの再試行。
            # 小さいモデルでは頻繁に起きるため、即失敗にせず
            # 緩い`json_object`で取り直す。
            try:
                retried = self._chat(prompt, {})
            except httpx.HTTPError as exc:
                raise LocalModelError(f"再試行にも失敗しました: {exc}") from exc
            return extract_json_object(retried)

    def _chat(self, prompt: str, response_schema: dict[str, Any]) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "あなたはJSONのみを出力するAPIです。説明文・前置き・"
                        "コードフェンスを一切付けず、有効なJSONオブジェクトだけを返してください。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            # 構造化出力を安定させるため、決定的寄りにする
            # (Benchmarkの再現性のためでもある)。
            "temperature": 0.0,
            "stream": False,
        }
        if response_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "forge_result", "schema": response_schema, "strict": False},
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(f"{self._base_url}/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()

        try:
            return str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalModelError(
                f"ローカルRuntimeの応答形式が想定と異なります(OpenAI互換ではない?): {str(body)[:200]}"
            ) from exc
