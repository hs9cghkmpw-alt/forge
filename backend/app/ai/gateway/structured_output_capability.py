"""Structured Output Capability
(FORGE-AI-FOUNDATION-011 §2、2026-08-14)。

**「Forgeの誤り」と「相手の対応範囲」を分ける。**

---

## 直した実バグ

010の`OpenAICompatibleAdapter`は常に`json_schema`で要求し、
Providerが`json_schema`を知らずにHTTP 400を返すと:

    HTTP 400 → INVALID_REQUEST → 「Forge側の誤り」→ 巡回停止

となった。`json_object`へのfallbackは**JSON抽出に失敗した場合**にしか
書かれておらず、400では`_chat()`の中で例外になって到達しなかった。

つまり`json_schema`非対応のProviderが候補に1つ混ざるだけで、
**Forge全体のAI呼び出しが止まりうる**状態だった。実際に再現して
確認した。

## なぜ1bitでは足りなかったか

`supports_structured_output: bool`しか無かったので、

* 対応している / していない

しか言えず、**何に対応していないのか**が言えなかった。
`StructuredOutputMode`(STRICT_JSON_SCHEMA → JSON_SCHEMA →
JSON_OBJECT → PROMPT_JSON)へ分けたことで、「json_schemaは駄目だが
json_objectなら通る」が表現できるようになった。

## 400をどう読み分けるか(証拠の強い順、Phase Gと同じ姿勢)

    A. 「そのmodeを知らない」と明示している
         → MODE_UNSUPPORTED。**1段だけ緩めて再試行する。**

    B. 「スキーマが不正だ」と明示している
         → FORGE_REQUEST_INVALID。**緩めない・巡回もしない。**
            ここで緩めると、Forge自身のバグを黙って回避して、
            検証されていない出力を「成功」として返すことになる。

    C. どちらとも言っていない(不透明な400)
         → AMBIGUOUS。**緩めないが、他のProviderへは進む。**

Cの扱いが要点である。緩めればForgeのバグを隠しうるし、巡回を
止めれば相手の癖1つでForgeが止まる。**「自分では回避しないが、
他をあたる」**が、どちらの害も避ける唯一の位置である。

Cを「たぶんmode非対応」と決めつけていない——**分類できていない
ことを分類結果に混ぜない**(`ai_errors.py`の`UNKNOWN`と同じ姿勢)。

## 学習(宣言より事実を優先する)

Registryの`structured_output_modes`は**公称**であって検証結果では
ない(§46「Cloud AI Output = Truth ではない」と同じ)。実際に400が
返れば、そのProviderについては事実の方を採り、以後は最初から
緩いmodeで始める。**同じ無駄を毎回繰り返さない。**

既知の制限: プロセス内メモリのみ(TD41と同じ)。再起動で忘れる。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.provider_registry import StructuredOutputMode, definition_for, weaker_mode

__all__ = [
    "FourHundredReading",
    "StructuredOutputCapabilityStore",
    "default_capability_store",
    "read_four_hundred",
]


class FourHundredReading(str, Enum):
    """HTTP 400 を**誰の問題として**読むか。"""

    MODE_UNSUPPORTED = "mode_unsupported"
    """相手がそのmodeを知らない。緩めて再試行してよい。"""

    FORGE_REQUEST_INVALID = "forge_request_invalid"
    """Forge側の誤り。緩めない・巡回しない。"""

    AMBIGUOUS = "ambiguous"
    """判別できない。緩めないが、他Providerへは進む。"""


# --- 証拠A: 「そのmodeを知らない」と言っている --------------------------
#
# `response_format`という語が出てくること自体が強い手掛かりである
# ——Forgeが送る`response_format`について相手が文句を言っている。
_MODE_FIELD_HINTS = (
    "response_format", "response format", "responseformat",
    "json_schema", "json schema", "json_object", "json object",
)
_UNSUPPORTED_HINTS = (
    "not supported", "unsupported", "not support", "does not support",
    "unrecognized", "unknown parameter", "unknown field", "invalid parameter",
    "is not available", "not implemented", "対応していません", "サポートされていません",
)

# --- 証拠B: 「スキーマが不正だ」と言っている ----------------------------
#
# **ここでmodeを緩めてはならない。** 緩めるとスキーマ制約が外れ、
# Forgeのバグを回避したまま「成功」してしまう。
_SCHEMA_INVALID_HINTS = (
    "invalid schema", "schema is invalid", "invalid_schema", "malformed schema",
    "failed to parse schema", "schema validation", "invalid json schema",
    "context_length", "context length", "too many tokens", "maximum context",
)


def read_four_hundred(body_text: str) -> FourHundredReading:
    """400の本文から、**誰の問題か**を読む。

    順序に意味がある。「スキーマが不正」を先に見るのは、その文言が
    `response_format`という語を含むことがあり、mode非対応と
    取り違えると**Forge自身のバグを黙って回避する**方向へ倒れる
    ためである。安全側は常に「緩めない」側である。
    """
    lowered = (body_text or "").lower()
    if not lowered:
        return FourHundredReading.AMBIGUOUS

    if any(hint in lowered for hint in _SCHEMA_INVALID_HINTS):
        return FourHundredReading.FORGE_REQUEST_INVALID

    mentions_mode = any(hint in lowered for hint in _MODE_FIELD_HINTS)
    says_unsupported = any(hint in lowered for hint in _UNSUPPORTED_HINTS)
    if mentions_mode and says_unsupported:
        return FourHundredReading.MODE_UNSUPPORTED

    return FourHundredReading.AMBIGUOUS


@dataclass(frozen=True)
class _Learned:
    unsupported: frozenset[StructuredOutputMode] = frozenset()
    confirmed: frozenset[StructuredOutputMode] = frozenset()


class StructuredOutputCapabilityStore:
    """Provider(+Model)ごとに、実際に通ったmode・弾かれたmodeを覚える。

    キーに`model`も含めるのは、同じProviderでもモデルによって
    `json_schema`対応が違うことがあるためである。Providerだけで
    覚えると、モデルを変えた瞬間に嘘になる。
    """

    def __init__(self) -> None:
        self._learned: dict[tuple[str, str], _Learned] = {}

    def _key(self, provider: str, model: str) -> tuple[str, str]:
        return (provider, model or "")

    def preferred_mode(
        self, provider: str, model: str, *, declared: tuple[StructuredOutputMode, ...]
    ) -> StructuredOutputMode:
        """今このProviderへ使うべきmode。

        宣言された順(強い順)のうち、**弾かれたと分かっているものを
        飛ばした**最初のものを返す。全部弾かれていれば`PROMPT_JSON`
        ——`response_format`を送らないので、どのProviderでも通る。
        """
        learned = self._learned.get(self._key(provider, model), _Learned())
        for mode in declared:
            if mode is StructuredOutputMode.UNSUPPORTED:
                continue
            if mode not in learned.unsupported:
                return mode
        return StructuredOutputMode.PROMPT_JSON

    def note_unsupported(self, provider: str, model: str, mode: StructuredOutputMode) -> None:
        """そのmodeが弾かれたという**事実**を記録する(宣言より優先)。"""
        key = self._key(provider, model)
        learned = self._learned.get(key, _Learned())
        self._learned[key] = _Learned(
            unsupported=learned.unsupported | {mode},
            confirmed=learned.confirmed - {mode},
        )

    def note_worked(self, provider: str, model: str, mode: StructuredOutputMode) -> None:
        """そのmodeで実際に応答が得られたことを記録する。

        **一度通ったmodeでの400は、Forge側の誤りとして扱う**根拠に
        なる——相手はそのmodeを理解できるのだから、断られたのは
        中身の問題である。
        """
        key = self._key(provider, model)
        learned = self._learned.get(key, _Learned())
        self._learned[key] = _Learned(
            unsupported=learned.unsupported - {mode},
            confirmed=learned.confirmed | {mode},
        )

    def has_worked(self, provider: str, model: str, mode: StructuredOutputMode) -> bool:
        return mode in self._learned.get(self._key(provider, model), _Learned()).confirmed

    def known_unsupported(self, provider: str, model: str) -> frozenset[StructuredOutputMode]:
        return self._learned.get(self._key(provider, model), _Learned()).unsupported

    def reset(self) -> None:
        self._learned.clear()


def declared_modes_for(provider: str) -> tuple[StructuredOutputMode, ...]:
    """Registryの宣言(強い順)。未知のProviderは保守的な既定を使う。"""
    definition = definition_for(provider)
    if definition is None:
        return (StructuredOutputMode.JSON_SCHEMA, StructuredOutputMode.JSON_OBJECT)
    return definition.declared_output_modes


def next_mode_after_rejection(mode: StructuredOutputMode) -> StructuredOutputMode | None:
    """弾かれたmodeの1段下。これ以上緩められなければ`None`。"""
    return weaker_mode(mode)


_default_store: StructuredOutputCapabilityStore | None = None


def default_capability_store() -> StructuredOutputCapabilityStore:
    """プロセス内で共有する学習結果(`ProviderStateStore`と同じ方針)。"""
    global _default_store  # noqa: PLW0603
    if _default_store is None:
        _default_store = StructuredOutputCapabilityStore()
    return _default_store
