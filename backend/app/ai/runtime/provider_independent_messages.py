"""利用者へ返す文言から、**Provider の身元を出さない**（Constitution §9）。

---

## なぜ要るのか

Forge は OpenAI でも Claude でも Gemini でも Ollama でもない。Provider と
base model は差し替え可能な実装手段であって、製品の正体ではない。ところが
実際のエラー経路は、Provider が投げた文字列をそのまま利用者まで運んでいた。

```text
GeminiProvider  -> RuntimeError("Gemini APIの無料枠の利用上限に達しました…")
routers/ai.py   -> ProviderError(str(exc))
exception_handlers -> ErrorEnvelope(message=…)   ← 利用者の画面
```

利用者は「Gemini」という単語を受け取り、しかも「別の AI Provider を設定
してください」と**Provider 選択の責任まで**渡されていた。

## どう直すか

**文字列を部分置換しない。** 「Gemini API」を「AI」に差し替えるような直し方は
壊れやすく、日本語も壊れる。ここでやるのは判定と**差し替え**である。

1. 利用者向け文言に Provider の身元が含まれるかを検出する
2. 含まれていたら、`sub_reason` に対応する**Provider 非依存の文言へ丸ごと
   置き換える**

## 消してよいのは「利用者向け表示」だけである

Evidence・診断・ログ・Provider 実装名・過去の実測記録は、**実際に使った
Provider と Model を正確に記録し続ける**。ここで扱うのは
`ErrorEnvelope.message`（利用者の画面に出る1本の文字列）だけである。
"""

from __future__ import annotations

import re

# Provider / base model / runtime の身元を示す語。**小文字で比較する。**
#
# 「利用者向け文言に出てはいけない語」であって、コードや Evidence から
# 消す語ではない。
PROVIDER_IDENTITY_TOKENS: tuple[str, ...] = (
    "gemini",
    "openai",
    "chatgpt",
    "gpt-",
    "anthropic",
    "claude",
    "ollama",
    "llama",
    "qwen",
    "mistral",
    "gemma",
    "phi-3",
    "vertex",
    "bedrock",
    "huggingface",
    "mock",
    "forge_ai",
    "provider",
    "llm",
    "api key",
    "api_key",
    "apikey",
)

# 日本語表記の身元。上の小文字比較では拾えない。
_JA_IDENTITY_TOKENS: tuple[str, ...] = (
    "プロバイダ",
    "プロバイダー",
    "モック",
    "疑似応答",
)

# `sub_reason` ごとの、Provider 非依存な利用者向け文言。
#
# **打つ手が違うものを同じ文言にしない**（`routers/ai.py` の
# `_no_provider_message` が既に守っている区別を、ここでも保つ）。
_BY_SUB_REASON: dict[str, str] = {
    "quota_exhausted": (
        "今日のAI利用枠を使い切りました。日付が変わってからもう一度お試しください。"
    ),
    "rate_limited": (
        "AIの利用上限に達したため、いまは応答できませんでした。"
        "少し時間をおいてから、もう一度お試しください。"
    ),
    "timeout": (
        "AIの応答に時間がかかりすぎたため、いったん中止しました。"
        "もう一度お試しください。"
    ),
    "auth_failed": (
        "AIを利用する設定に問題があるため、いまは応答できませんでした。"
        "しばらくしてからもう一度お試しください。"
    ),
    "invalid_response": (
        "AIからの応答を読み取れませんでした。もう一度お試しください。"
    ),
    "unavailable": (
        "いまAIを利用できませんでした。しばらくしてからもう一度お試しください。"
    ),
}

_DEFAULT_MESSAGE = (
    "いまAIを利用できませんでした。しばらくしてからもう一度お試しください。"
)


def mentions_provider_identity(text: str) -> bool:
    """利用者向け文言に Provider / base model の身元が含まれるか。

    **含まれていたら「表示してよくない」という意味である。** 判定を
    楽観側へ倒さないため、単語境界を要求せず部分一致で見る
    （`gemini-2.5-flash` や `Gemini API` を取りこぼさない）。
    """
    lowered = text.lower()
    if any(token in lowered for token in PROVIDER_IDENTITY_TOKENS):
        return True
    return any(token in text for token in _JA_IDENTITY_TOKENS)


def user_facing_message(message: str, *, sub_reason: str | None) -> str:
    """利用者の画面に出してよい文言を返す。

    身元が含まれていなければ**そのまま返す**（せっかく丁寧に書かれた
    文言を無駄に潰さない）。含まれていたら `sub_reason` に対応する
    Provider 非依存の文言へ**丸ごと**差し替える。
    """
    if not mentions_provider_identity(message):
        return message
    return _BY_SUB_REASON.get(sub_reason or "", _DEFAULT_MESSAGE)


def redact_provider_identity_for_logs(text: str) -> str:
    """ログ用。**身元を消さない。** 秘密（API キー等）だけを落とす。

    Evidence と診断は実 Provider 名を正確に持ち続けるべきなので、ここで
    Provider 名を消してはならない。落とすのは鍵らしき長い連続文字だけで
    ある（CLAUDE.md §4「ログにも出さない。長さや先頭数文字も出さない」）。
    """
    return re.sub(r"(?i)\b(?:sk|key|token)[-_a-z0-9]{12,}", "[REDACTED]", text)
