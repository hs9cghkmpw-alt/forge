"""環境変数から**数値**を読む唯一の境界
(FORGE-PRE-R1-INTEGRITY-GATE-013 §2、2026-08-17)。

---

## 直した実バグ

`.env.example` をコピーして `.env` にすると、こういう行が入る。

    FORGE_GROQ_TIMEOUT_SECONDS=

「任意なので空のままでよい」という意図の行である。ところが読む側は

    float(os.environ.get("FORGE_GROQ_TIMEOUT_SECONDS", 60.0))

だった。**環境変数は存在する**(値が空文字)ので`os.environ.get`は
既定値を返さず`""`を返し、`float("")`が`ValueError`になる。

実測した影響範囲は、報告より広かった:

    ValueError: could not convert string to float: ''

`ProviderRouter`は起動時に**全Provider**を構築するので、
1つのProviderのtimeoutが空文字なだけで**Forge全体が起動しない**。
`.env.example`をそのままコピーした利用者が、必ず踏む。

## なぜLocalだけを直さないのか

同じ形が既に2箇所あり(Local / 汎用Cloud)、汎用Cloud側は
**Providerが増えるたびに増える**(`FORGE_<ID>_TIMEOUT_SECONDS`)。
「気を付けて書く」に依存する形は、Forgeが4回繰り返した失敗
(`CLAUDE.md` §3)と同じである。

したがって:

1. 数値envを読む関数をここ1つにする
2. **生の`float(os.environ...)`が再び現れたらテストが落ちる**ようにする
   (`tests/test_env_settings.py`のsource scan)

## 設計判断

### 空文字は「未設定」と同じに扱う

`.env`で「任意の項目を空にしておく」のは**普通の書き方**である。
これをエラーにすると、正しい使い方が壊れる。whitespaceのみも同じ。

### 壊れた値は**黙って既定値にしない**

    FORGE_GROQ_TIMEOUT_SECONDS=60s
    FORGE_GROQ_TIMEOUT_SECONDS=1,000

これらを既定値へ倒すと、**設定したつもりで効いていない**状態が
静かに続く。`ConfigurationError`として起動時に落とす。

「分からないものを楽観側へ倒さない」(`CLAUDE.md` §3)の適用である。
**空文字は「分からない」ではなく「書いていない」**なので既定へ倒す。
壊れた値は「書いたが読めない」なので落とす。

なお全角数字(`３０`)と桁区切り(`1_000`)は、Pythonの`float()`が
**利用者の意図どおりの値**へ解釈するので弾かない。テストを書く際に
「弾かれるはず」と想定して確かめたところ落ちなかった、という順序で
分かったことである(`tests/test_env_settings.py`に記録)。

### 範囲も同じ場所で見る

timeoutに`0`や`-1`を入れても意味が無い。「読めた」と「使える」は
別なので、`minimum`を渡せるようにした。範囲外も`ConfigurationError`。
"""

from __future__ import annotations

import os

__all__ = [
    "ConfigurationError",
    "env_float",
    "env_int",
]


class ConfigurationError(RuntimeError):
    """環境変数の値が読めない/使えない。

    **起動時に落とす**ためのものである。黙って既定値へ倒すと、
    設定したつもりで効いていない状態が続く。
    """

    def __init__(self, name: str, raw: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        # **値そのものは出す。** これはSecretではなくtimeout等の数値で
        # あり、出さないと利用者が自分の打ち間違いを直せない。
        # 鍵を読む経路はここを通らない(`api_key_env`はAdapterが直接読む)。
        super().__init__(
            f"環境変数 {name} の値 '{raw}' は{reason}。"
            f"設定を修正するか、行ごと削除して既定値を使ってください。"
        )


def _raw(name: str) -> str | None:
    """設定されていて、かつ空でない値。それ以外は`None`。

    `os.environ.get(name)`との違いがこの関数の全部である——
    **空文字とwhitespaceのみを「未設定」と同じに扱う**。
    """
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def env_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """数値(小数可)の環境変数を読む。

    未設定・空文字・whitespaceのみ → `default`。
    読めない値・範囲外 → `ConfigurationError`。
    """
    raw = _raw(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(name, raw, "数値として読めません") from exc
    if value != value or value in (float("inf"), float("-inf")):
        # NaN / inf。`float()`は通してしまうが、timeoutにもsizeにも
        # 使えない値である。
        raise ConfigurationError(name, raw, "有限の数値ではありません")
    return _checked(name, raw, value, minimum, maximum)


def env_int(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """整数の環境変数を読む。

    `"30.5"`は**通さない**——整数を要求している場所で小数を黙って
    切り捨てると、設定した値と動く値がずれる。
    """
    raw = _raw(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(name, raw, "整数として読めません") from exc
    return int(_checked(name, raw, value, minimum, maximum))


def _checked(
    name: str, raw: str, value: float, minimum: float | None, maximum: float | None
) -> float:
    if minimum is not None and value < minimum:
        raise ConfigurationError(name, raw, f"{minimum} 以上である必要があります")
    if maximum is not None and value > maximum:
        raise ConfigurationError(name, raw, f"{maximum} 以下である必要があります")
    return value
