"""Generic OpenAI-Compatible Adapter
(FORGE-AI-FOUNDATION-010 Phase E・G、2026-08-13)。

`/v1/chat/completions`という同じ形を話すProviderを、**1つの実装**で
賄う。Ollama / llama.cpp / LM Studio / vLLM といったLocal Runtimeも、
Groq / OpenRouter / Together / Cerebras といったCloudも、この契約を
共有している。

    OpenAICompatibleAdapter(base_url, model, api_key_env)
            ↓ HTTP POST /chat/completions
        任意のOpenAI互換エンドポイント

Providerを1つ足すのに必要なのは、**Registryへ1行**と、この
Adapterへ渡す`base_url`だけである(`provider_registry.py`)。
Provider実装を1つずつ書き起こすのは、同じバグを人数分書くのと
同じことになる。

---

## Phase G: 失敗の分類は「弱い証拠」を最後に使う

以前の分類は`classify_exception()`——**例外メッセージの文字列
マッチ**——しか無かった。実APIの文言が想定と違えば`UNKNOWN`へ
落ちるが、そのこと自体は検出されない(`ai_errors.py`の正直な
申告どおり、残リスクだった)。

このAdapterはHTTP応答を直接見られるので、**強い証拠から順に**使う:

1. **構造化エラー** — `{"error": {"type": "insufficient_quota"}}`。
   Providerが機械可読な種別を返しているなら、それが最も確かである。
2. **HTTPステータス** — 401/403/404/429/5xx。文言に依存しない。
3. **ヘッダ** — `Retry-After`・`x-ratelimit-*`。**いつ復帰するか**は
   ここにしか無い。429が流量制限か枠切れかの判別にも使う。
4. **本文テキスト** — 構造化されていないが応答本文ではある。
5. **例外メッセージの文字列マッチ** — 最後。HTTP応答すら得られな
   かった場合(接続失敗等)にしか到達しない。

この順序が要点である。逆順にすると、**429という明確な事実がある
のに「文言にrate limitが無いからUNKNOWN」**という判定が起きる。

分類済みの`ProviderError`をそのまま送出するので、`AIRouter`は
再分類しない(`classify_exception()`は`ProviderError`を素通しする)。

## 秘密の扱い(§14〜§18)

API Keyは`api_key_env`で**環境変数名**として受け取り、送信時に
`os.environ`から読む。インスタンスへ保持しない・ログへ出さない・
例外メッセージへ含めない。エラー本文をメッセージへ載せる際も、
`Authorization`ヘッダは元から本文に含まれないが、念のため
**リクエスト内容は一切載せない**(プロンプト自体が利用者の
入力である)。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from app.ai.gateway.ai_errors import ErrorKind, ProviderError

__all__ = [
    "OpenAICompatibleAdapter",
    "classify_http_failure",
    "extract_json_object",
]

_DEFAULT_TIMEOUT_SECONDS = 120.0

# ```json ... ``` のようなコードフェンス。小さいモデルは指示しても
# しばしばフェンスを付けてくるため、剥がしてからパースする。
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

_JSON_ONLY_SYSTEM_PROMPT = (
    "あなたはJSONのみを出力するAPIです。説明文・前置き・"
    "コードフェンスを一切付けず、有効なJSONオブジェクトだけを返してください。"
)


class ResponseFormatError(RuntimeError):
    """応答からJSONを取り出せなかった。

    `LocalModelError`(local_provider.py)がこれを継承する——既存の
    呼び出し側・テストとの後方互換のため。
    """


def extract_json_object(text: str, *, error_type: type[Exception] = ResponseFormatError) -> dict[str, Any]:
    """モデルの生応答からJSONオブジェクトを取り出す。

    小さいモデルは、素のJSONではなく「はい、こちらです: ```json {...} ```」
    のような応答を返しがちであるため、次の順に試す:

    1. そのままパース
    2. コードフェンスの中身をパース
    3. 最初の `{` から最後の `}` までを切り出してパース

    どれも駄目なら例外。**空dictを返して「成功」に見せかけない**
    (TD40の教訓——Geminiが空`{}`を返し、合成が静かに失敗し続けた)。
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
    raise error_type(
        f"モデルの応答からJSONを取り出せませんでした(先頭200文字: {stripped[:200]!r})"
    )


# ---------------------------------------------------------------------------
# Phase G: 失敗の正規化
# ---------------------------------------------------------------------------

# 証拠1: 構造化エラーの種別。OpenAI互換Providerが`error.type`/`error.code`で
# 返す値。**Provider横断で共通のものだけ**を書く——各社の独自コードを
# 網羅しようとすると、追随できずに古くなる。
_STRUCTURED_ERROR_KINDS: dict[str, ErrorKind] = {
    "insufficient_quota": ErrorKind.QUOTA_EXHAUSTED,
    "billing_hard_limit_reached": ErrorKind.QUOTA_EXHAUSTED,
    "quota_exceeded": ErrorKind.QUOTA_EXHAUSTED,
    "rate_limit_exceeded": ErrorKind.RATE_LIMITED,
    "requests_rate_limit_exceeded": ErrorKind.RATE_LIMITED,
    "tokens_rate_limit_exceeded": ErrorKind.RATE_LIMITED,
    "invalid_api_key": ErrorKind.AUTH,
    "authentication_error": ErrorKind.AUTH,
    "invalid_authentication": ErrorKind.AUTH,
    "permission_error": ErrorKind.AUTH,
    "model_not_found": ErrorKind.MODEL_UNAVAILABLE,
    "invalid_request_error": ErrorKind.INVALID_REQUEST,
    "context_length_exceeded": ErrorKind.INVALID_REQUEST,
    "server_error": ErrorKind.PROVIDER_SERVER_ERROR,
    "overloaded_error": ErrorKind.PROVIDER_SERVER_ERROR,
}

# 証拠2: HTTPステータス。文言に依存しない。
_STATUS_KINDS: dict[int, ErrorKind] = {
    400: ErrorKind.INVALID_REQUEST,
    401: ErrorKind.AUTH,
    403: ErrorKind.AUTH,
    404: ErrorKind.MODEL_UNAVAILABLE,
    408: ErrorKind.TIMEOUT,
    413: ErrorKind.INVALID_REQUEST,
    422: ErrorKind.INVALID_REQUEST,
    # 429は流量制限とも枠切れとも取れる。既定は**流量制限**
    # (cooldownで復帰しうる、軽い方)にしておき、枠切れの証拠が
    # あるときだけ重い方へ倒す。逆にすると、数分で直るものを
    # 1時間除外することになる。
    429: ErrorKind.RATE_LIMITED,
    500: ErrorKind.PROVIDER_SERVER_ERROR,
    502: ErrorKind.PROVIDER_SERVER_ERROR,
    503: ErrorKind.PROVIDER_SERVER_ERROR,
    504: ErrorKind.PROVIDER_SERVER_ERROR,
}

# 証拠4: 本文テキスト。枠切れは429以外(402等)でも来るため、
# ステータスだけでは足りない。
_QUOTA_BODY_HINTS = (
    "quota", "insufficient_quota", "exceeded your current quota",
    "billing", "credit", "上限に達し", "利用上限",
)


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    """証拠3: **いつ復帰するか**はヘッダにしか無い。

    `Retry-After`は秒数かHTTP日付を取りうるが、日付形式は
    Provider間で扱いが揺れるので秒数だけを読む。読めなければ
    `None`——**`None`を「すぐ再試行してよい」と読まないこと**
    (`ProviderError.retry_after_seconds`のdocstring参照)。
    """
    lowered = {key.lower(): value for key, value in headers.items()}
    for name in ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        raw = lowered.get(name)
        if not raw:
            continue
        try:
            seconds = float(str(raw).strip().rstrip("s"))
        except ValueError:
            continue
        if seconds >= 0:
            return seconds
    return None


def classify_http_failure(
    *,
    provider: str,
    status_code: int,
    headers: dict[str, str] | None = None,
    body_text: str = "",
) -> ProviderError:
    """HTTP応答から`ProviderError`を組み立てる(証拠の強い順)。

    この関数が**文字列マッチを最後にしか使わない**ことが Phase G の
    実体である。
    """
    headers = headers or {}
    retry_after = _retry_after_seconds(headers)
    detail = (body_text or "").strip()[:200]

    # -- 証拠1: 構造化エラー ---------------------------------------------
    structured_kind: ErrorKind | None = None
    try:
        parsed = json.loads(body_text) if body_text else None
    except (json.JSONDecodeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        error_obj = parsed.get("error")
        if isinstance(error_obj, dict):
            for field in ("type", "code"):
                value = error_obj.get(field)
                if isinstance(value, str) and value in _STRUCTURED_ERROR_KINDS:
                    structured_kind = _STRUCTURED_ERROR_KINDS[value]
                    break
            message = error_obj.get("message")
            if isinstance(message, str) and message:
                detail = message[:200]
    if structured_kind is not None:
        return ProviderError(structured_kind, provider, detail, retry_after)

    # -- 証拠2: HTTPステータス --------------------------------------------
    kind = _STATUS_KINDS.get(status_code)
    if kind is None:
        kind = (
            ErrorKind.PROVIDER_SERVER_ERROR if status_code >= 500
            else ErrorKind.UNKNOWN if status_code < 400
            else ErrorKind.INVALID_REQUEST
        )

    # -- 証拠4: 本文テキスト(枠切れは429以外でも来る) --------------------
    lowered_body = (body_text or "").lower()
    if any(hint in lowered_body for hint in _QUOTA_BODY_HINTS) and kind in (
        ErrorKind.RATE_LIMITED, ErrorKind.INVALID_REQUEST, ErrorKind.UNKNOWN
    ):
        kind = ErrorKind.QUOTA_EXHAUSTED

    return ProviderError(kind, provider, detail or f"HTTP {status_code}", retry_after)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class OpenAICompatibleAdapter:
    """`LLMAdapter` Protocolを満たす、OpenAI互換エンドポイントへの接続。

    `provider_name`は`GeminiProvider`等と同じく、Routing表・Benchmark
    結果の見出しに使われる識別子。
    """

    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        model: str,
        api_key_env: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.provider_name = provider_name
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key_env = api_key_env
        self._timeout = timeout_seconds
        self._extra_headers = dict(extra_headers or {})

    @property
    def model(self) -> str:
        """送信するモデル名。

        propertyにしているのは、環境変数から遅延解決するsubclass
        (`CloudCompatibleProvider`)のためである。`ProviderRouter`は
        起動時に全Providerを構築するので、構築時に環境を焼き付けると
        後から設定を足しても反映されない。
        """
        return self._model

    @property
    def base_url(self) -> str:
        """接続先。空文字なら未設定(Auto Discoveryが候補から外す)。"""
        return self._base_url

    # -- LLMAdapter契約 ----------------------------------------------------

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        """`response_schema`が空dictなら、スキーマ強制なしの自由JSONとして扱う。

        この「空スキーマ=freeform」という規約は`forge_operation.py`が
        既に依存しているため、Provider間で揃える必要がある
        (`GeminiProvider`も同じ扱い)。
        """
        content = self._chat(prompt, response_schema)
        try:
            return extract_json_object(content, error_type=self._response_format_error_type())
        except Exception:
            if not response_schema:
                raise
            # `json_schema`を守れなかった場合の**1回だけ**の再試行。
            # 小さいモデルでは頻繁に起きるため即失敗にせず、緩い
            # `json_object`で取り直す。2回目は無い(無限に粘らない)。
            retried = self._chat(prompt, {})
            return extract_json_object(retried, error_type=self._response_format_error_type())

    # -- 差し替え点 --------------------------------------------------------

    def _response_format_error_type(self) -> type[Exception]:
        """JSONを取り出せなかったときに送出する例外型。

        Localは`LocalModelError`(→`LOCAL_RESOURCE_ERROR`)へ倒したい
        ——運用者にとって「Ollamaが妙な応答を返している」と
        「Cloudの構造化出力が壊れた」は、取るべき対処が違う。
        """
        return ResponseFormatError

    def _connection_error(self, exc: httpx.HTTPError) -> Exception:
        """接続そのものに失敗したときの例外。

        Cloudは`NETWORK`。Localは「Runtimeが起動していない」であり、
        利用者へ見せるべき言葉が違うのでsubclassが差し替える。
        """
        return ProviderError(
            ErrorKind.NETWORK, self.provider_name,
            f"{self.base_url} へ接続できませんでした({exc})",
        )

    # -- HTTP --------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """送信ヘッダ。**API Keyはここで初めて環境から読む**。

        インスタンスへ保持しない(§14〜§18)。鍵が未設定でも例外に
        しないのは、鍵不要のLocal Runtimeと同じコードで動かすため
        ——鍵が要るのに無ければ、Providerが401を返し、Phase Gの
        分類が`AUTH`として扱う。**推測でエラーを作らず、相手に
        答えさせる。**
        """
        headers = {"Content-Type": "application/json", **self._extra_headers}
        if self._api_key_env:
            key = os.environ.get(self._api_key_env, "").strip()
            if key:
                headers["Authorization"] = f"Bearer {key}"
        return headers

    def _payload(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _JSON_ONLY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            # 構造化出力を安定させるため決定的寄りにする
            # (Benchmarkの再現性のためでもある)。
            "temperature": 0.0,
            "stream": False,
        }
        if response_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "forge_result", "schema": response_schema, "strict": False,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _chat(self, prompt: str, response_schema: dict[str, Any]) -> str:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json=self._payload(prompt, response_schema),
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise self._connection_error(exc) from exc

        if response.status_code >= 400:
            # **本文は載せるがリクエストは載せない**——プロンプトは
            # 利用者の入力そのものである。
            raise classify_http_failure(
                provider=self.provider_name,
                status_code=response.status_code,
                headers=dict(response.headers),
                body_text=response.text,
            )

        try:
            body = response.json()
            return str(body["choices"][0]["message"]["content"])
        except (json.JSONDecodeError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                ErrorKind.STRUCTURED_OUTPUT_FAILURE, self.provider_name,
                f"応答形式がOpenAI互換ではありません: {response.text[:200]}",
            ) from exc
