"""Deadline伝播(FORGE-AI-FOUNDATION-011 §4、2026-08-14)。

Task全体の残り時間を、**実際にHTTPを叩く層まで届ける**ための境界。

---

## 直した問題

`TaskProfile.latency_budget_ms`は既定45秒だが、Providerのtimeoutは
Cloud 60秒・Local 120秒である。Routerは**呼ぶ前に**
`elapsed >= budget`を見るだけだったので、

    elapsed = 0 → 予算内と判定 → Provider呼び出し開始 → 120秒待つ

が成立した。45秒という宣言が、実行を何も拘束していなかった。

fallback後はさらに悪い。1つ目が30秒使っても、2つ目は自分の
timeout(60秒)で走るので、合計90秒になりうる。

**宣言した制約が、下位の実行へ伝わっていなかった。**

## なぜ`complete_structured()`に引数を足さなかったか

`LLMAdapter`は`complete_structured(prompt, response_schema) -> dict`
という契約で、`ConversationEngine`・`ForgeOperationEngine`・
`ForgeAIProviderBridge`・Mock・テストのFake が実装している。
ここへ引数を足すと**全実装とすべてのTest Doubleが同時に壊れる**。

得られるものは「deadlineを渡せる」ことだが、deadlineを扱えるのは
実際にHTTPを張る一部のAdapterだけである。扱えない実装にまで
引数を強制するのは、契約を広げすぎている。

## 採った形: 任意のCapability

    class SupportsDeadline(Protocol):
        def with_deadline(self, seconds: float) -> LLMAdapter: ...

Routerは`supports_deadline()`で確認し、対応していれば残り予算で
締めたAdapterを作って使う。**元のインスタンスは変更しない**
(`ProviderRouter`が保持する共有インスタンスなので、書き換えると
別のリクエストの予算まで動く)。

## 対応していないAdapterをどう扱うか

黙って予算超過を許さない。Registryの`nominal_timeout_seconds`と
残り予算を比べ、**入りきらないと分かっている試行は始めない**
——始めれば予算を超えることが確定しているからである。除外理由も
残す(「使えるProviderがありません」だけでは調査できない)。

Mockのように即答するものは`nominal_timeout_seconds`が小さいので、
残り予算が少なくても通る。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["SupportsDeadline", "apply_deadline", "supports_deadline"]


@runtime_checkable
class SupportsDeadline(Protocol):
    """残り時間を受け取れるAdapter。

    `LLMAdapter`本体の契約は変えない——これは**任意の追加能力**で
    あり、実装していなくても正しいAdapterである。
    """

    def with_deadline(self, seconds: float) -> Any:
        """`seconds`以内に応答を返す(または失敗する)Adapterを返す。

        **自分自身を書き換えない。** 共有インスタンスを書き換えると、
        同時に走る別のリクエストの予算まで動いてしまう。
        """
        ...


def supports_deadline(adapter: object) -> bool:
    """そのAdapterが残り時間を尊重できるか。

    `runtime_checkable`な`Protocol`の`isinstance`はメソッドの
    **存在**しか見ないが、ここで確かめたいのはまさにそれである。
    """
    return isinstance(adapter, SupportsDeadline)


def apply_deadline(adapter: object, seconds: float | None) -> object:
    """残り時間を適用したAdapterを返す。適用できなければそのまま返す。

    `seconds`が`None`(予算無し)なら何もしない。
    """
    if seconds is None or not supports_deadline(adapter):
        return adapter
    return adapter.with_deadline(seconds)
