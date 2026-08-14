"""Provider Error Taxonomy(FORGE-QUOTA-AWARE-AI-ROUTER-008 §19、2026-08-13)。

`docs/spec/FORGE-QUOTA-AWARE-AI-ROUTER-ARCH-REVIEW.md` §6 の実装。

---

## なぜ必要だったか

現行`ModelGateway.generate()`は`except Exception`で、**すべての失敗を
同じものとして扱っていた**。その結果:

* 400(schema不正)でも全Providerを巡回する。**どのProviderでも
  同じ失敗をする**のに、Quotaだけが減る。
* 401(認証)でも毎回試す。設定ミスが検出されない。
* 429(枠切れ)と500(一時障害)が区別できない。復帰戦略が立たない。

「失敗した」だけでは、**次に何をすべきかが決まらない**。

## 分類方法についての正直な申告

例外の**型と文字列の両方**を見る。既存Providerが
`RuntimeError("... 429 ...")`のような形で投げており、型だけでは
足りないためである。これは既存実装に合わせるための現実的な妥協で
あって、綺麗な設計ではない。Provider側を先に作り直す方が理想だが、
それは動いているものを壊すリスクの方が大きい。

**実APIのメッセージ形式が想定と違えば`UNKNOWN`へ落ちる。**
`UNKNOWN`はfallback可能として扱うので、安全側ではあるが、
分類できていないこと自体は検出されない(残リスク、レビュー §17-1)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ErrorKind",
    "ProviderError",
    "classify_exception",
]


class ErrorKind(str, Enum):
    """失敗の種類。**次に何をすべきか**で分けている。"""

    AUTH = "auth"
    """認証・権限。設定ミス。そのProviderは以後除外し、他へfallback。"""

    QUOTA_EXHAUSTED = "quota_exhausted"
    """枠切れ。`reset_at`まで除外。故障ではないのでCircuit Breakerとは別扱い。"""

    RATE_LIMITED = "rate_limited"
    """一時的な流量制限。cooldown後に再開。"""

    TIMEOUT = "timeout"
    NETWORK = "network"

    MODEL_UNAVAILABLE = "model_unavailable"
    """そのModelだけ使えない(廃止・未提供)。Provider自体は正常かもしれない。"""

    PROVIDER_SERVER_ERROR = "provider_server_error"
    """5xx。Circuit Breakerの主対象。"""

    INVALID_REQUEST = "invalid_request"
    """**fallbackしない**。Forge側のプロンプト/schemaの誤りであり、
    Providerを変えても同じ結果になる。巡回するとQuotaを捨てるだけで、
    原因も分からないままになる。"""

    STRUCTURED_OUTPUT_FAILURE = "structured_output_failure"
    """構造化出力が壊れていた。同Providerで1回だけ再試行の価値がある。"""

    UNSUPPORTED_OUTPUT_MODE = "unsupported_output_mode"
    """**そのProvider/Modelが、要求した構造化出力modeを知らない**
    (FORGE-AI-FOUNDATION-011 §2)。

    `INVALID_REQUEST`と厳密に分ける。両者はどちらもHTTP 400で来るが、
    意味が正反対である:

    * `INVALID_REQUEST` — **Forge側の誤り**。相手を変えても直らない
      ので、巡回を止める。
    * `UNSUPPORTED_OUTPUT_MODE` — **相手の対応範囲の問題**。
      緩いmodeなら答えられるかもしれないし、別のProviderなら
      そのまま答えられる。**巡回を止めてはならない。**

    011以前はこれが`INVALID_REQUEST`へ潰れており、`json_schema`を
    知らないProviderが1つあるだけで**全Routingが停止**しえた。

    故障ではないのでCircuit Breakerの失敗カウントには数えない
    ——何度呼んでも同じ結果になるが、それは壊れているのではなく、
    そういう仕様だというだけである。"""

    LOCAL_RESOURCE_ERROR = "local_resource_error"
    """Local固有(Runtime未起動・RAM不足・モデル未取得)。"""

    NOT_IMPLEMENTED = "not_implemented"
    """未実装のProviderスタブ。恒久的なので以後除外してよい。"""

    UNKNOWN = "unknown"
    """分類できなかった。安全側としてfallback可能に扱う。"""

    @property
    def should_try_other_providers(self) -> bool:
        """他のProviderを試す意味があるか。

        `INVALID_REQUEST`だけが`False`である——これはForge側の誤りなので、
        相手を変えても直らない。

        `UNSUPPORTED_OUTPUT_MODE`は`True`である(011 §2)。同じHTTP 400
        でも、**相手の対応範囲の問題なら別の相手には効く**。ここを
        混同していたために、`json_schema`非対応のProviderが1つあると
        全Routingが止まりえた。
        """
        return self is not ErrorKind.INVALID_REQUEST

    @property
    def counts_toward_circuit_breaker(self) -> bool:
        """Circuit Breakerの失敗カウントに数えるか。

        枠切れ・認証・未実装は「故障」ではない(それぞれ別の除外理由を
        持つ)。数えると、復帰条件が二重になって挙動が読めなくなる。
        """
        return self in {
            ErrorKind.TIMEOUT,
            ErrorKind.NETWORK,
            ErrorKind.PROVIDER_SERVER_ERROR,
            ErrorKind.STRUCTURED_OUTPUT_FAILURE,
            ErrorKind.LOCAL_RESOURCE_ERROR,
            ErrorKind.UNKNOWN,
        }

    @property
    def disables_provider(self) -> bool:
        """そのProviderを恒久的に候補から外すか(設定を直すまで)。"""
        return self in {ErrorKind.AUTH, ErrorKind.NOT_IMPLEMENTED}


@dataclass(frozen=True)
class ProviderError(Exception):
    """分類済みのProvider失敗。

    元の例外を握りつぶさず`cause`として保持する——分類が誤っていた
    ときに、元の情報が無いと調査できない。
    """

    kind: ErrorKind
    provider: str
    message: str
    retry_after_seconds: float | None = None
    """Providerが明示した待ち時間(`Retry-After`等)。不明なら`None`
    ——**`None`を「すぐ再試行してよい」と読まないこと**。"""

    def __str__(self) -> str:  # pragma: no cover - 表示用
        return f"[{self.kind.value}] {self.provider}: {self.message}"


# 文字列マッチの手掛かり。**順序に意味がある**(先に一致したものを採る)
# ため、より具体的なものを先に置く。
_MESSAGE_HINTS: tuple[tuple[ErrorKind, tuple[str, ...]], ...] = (
    # 「429」は流量制限にも枠切れにも使われる。文言で区別する。
    (ErrorKind.QUOTA_EXHAUSTED, (
        "quota", "exceeded your current quota", "insufficient_quota",
        "利用上限", "上限に達し", "resource_exhausted", "billing",
    )),
    (ErrorKind.RATE_LIMITED, ("rate limit", "rate_limit", "too many requests", "429")),
    (ErrorKind.AUTH, (
        "unauthorized", "401", "403", "permission denied", "api key", "api_key",
        "invalid authentication", "認証",
    )),
    (ErrorKind.MODEL_UNAVAILABLE, (
        "model not found", "model_not_found", "does not exist", "404", "unsupported model",
    )),
    (ErrorKind.INVALID_REQUEST, (
        "invalid request", "invalid_request", "400", "bad request",
        "schema", "unprocessable",
    )),
    (ErrorKind.PROVIDER_SERVER_ERROR, (
        "500", "502", "503", "504", "internal server error", "service unavailable",
        "overloaded", "server error",
    )),
    (ErrorKind.TIMEOUT, ("timeout", "timed out", "deadline")),
    (ErrorKind.NETWORK, ("connection", "network", "dns", "unreachable", "ssl")),
)


def classify_exception(exc: BaseException, provider: str) -> ProviderError:
    """例外を`ProviderError`へ正規化する。

    型を先に見て、決まらなければメッセージを見る。型で決まるものを
    優先するのは、文字列マッチより信頼できるからである。
    """
    if isinstance(exc, ProviderError):
        return exc

    # --- 型で決まるもの ---
    if isinstance(exc, NotImplementedError):
        return ProviderError(ErrorKind.NOT_IMPLEMENTED, provider, str(exc)[:200])
    if isinstance(exc, TimeoutError):
        return ProviderError(ErrorKind.TIMEOUT, provider, str(exc)[:200])
    if isinstance(exc, (ConnectionError, OSError)):
        return ProviderError(ErrorKind.NETWORK, provider, str(exc)[:200])

    # Local Providerの専用例外(importは遅延——このモジュールが
    # 具体的なProvider実装へ依存しないようにするため)。
    if type(exc).__name__ == "LocalModelError":
        return ProviderError(ErrorKind.LOCAL_RESOURCE_ERROR, provider, str(exc)[:200])

    # --- メッセージで推定するもの ---
    lowered = str(exc).lower()
    for kind, hints in _MESSAGE_HINTS:
        if any(hint in lowered for hint in hints):
            return ProviderError(kind, provider, str(exc)[:200])

    return ProviderError(ErrorKind.UNKNOWN, provider, str(exc)[:200])
