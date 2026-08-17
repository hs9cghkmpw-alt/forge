"""同一Provider内のModel選択(FORGE-ROADMAP R0.1、2026-08-17)。

`deadline.py`と同じ「任意のCapability」の形である。

---

## 直した問題(実機で再現した実バグ)

CEOが実際に使ったところ、AI連携が失敗した。再現した結果は
**6回中6回失敗**である。

    試行: [gemini(provider_server_error), local(local_resource_error)]
    除外: [mock: テスト専用のため自動選択しない]

原因は3つ重なっていた。

### 1. 環境 — 使っていたModelが混んでいた

同時刻に実測した成功率(同じ鍵・同じPayload・各3回):

    gemini-flash-latest        [200, 503, 503]   ← Forgeの既定
    gemini-flash-lite-latest   [200, 200, 200]
    gemini-3.5-flash           [200, 200, 200]

Google自身が「一時的だ」と言っている503である。

    "This model is currently experiencing high demand.
     Spikes in demand are usually temporary."

### 2. 設計 — 一時的な失敗でも1回しか試さなかった

§20「同じProviderを二度試さない」は**恒久的な失敗**については
正しい。鍵が無いProviderに二度聞いても同じである。しかし一時的な
失敗に同じ規則を当てると、**混雑がそのまま「AIが使えません」に
なる**。

### 3. 設計 — ProviderにModelが1つしか無かった

`ProviderDefinition.models`は存在したが「診断とBenchmarkの対象
指定のため」であり、**Routingには使っていなかった**。だから
「別のModelなら通る」という事実が、実行に反映されなかった。

---

## なぜProvider Identityを増やさないのか

`gemini-flash-latest`と`gemini-flash-lite-latest`を別Providerとして
登録すれば、既存の巡回だけで解決する。**しかしそれをやってはいけない。**

011 §1で決めたとおり、`provider_id`はQuota・Circuit Breaker・
Benchmark・Experience・Provenanceの**唯一の識別键**である。
同じ鍵・同じ枠を共有する2つを別Providerにすると、

* 枠切れ(429)を片方で学習しても、もう片方が同じ枠へ突っ込む
* Circuit Breakerが「gemini」ではなく「gemini-flash-latest」単位に
  なり、Provider障害を検出できなくなる
* Benchmarkの比較单位がずれる

**Modelは Provider Identity ではなく、Provider内部の実行選択肢**で
ある。したがってここでは、Providerの外から見た振る舞いを一切変えず
——Circuit Breakerには「geminiが1回失敗した」ではなく「geminiが
**全Modelで**失敗した」だけが伝わる——内部でだけ切り替える。

## 対応していないAdapter

そのまま1つのModelで動く。`LLMAdapter`の契約は変えていない。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["SupportsModelChoice", "apply_model", "supports_model_choice"]


@runtime_checkable
class SupportsModelChoice(Protocol):
    """Model名を差し替えたAdapterを作れること。

    `LLMAdapter`本体の契約は変えない——**任意の追加能力**であり、
    実装していなくても正しいAdapterである。
    """

    def with_model(self, model: str) -> Any:
        """`model`を使うAdapterを返す。

        **自分自身を書き換えない**(`SupportsDeadline.with_deadline`と
        同じ理由——`ProviderRouter`が保持する共有インスタンスなので、
        書き換えると同時に走る別のリクエストのModelまで動く)。
        """
        ...


def supports_model_choice(adapter: object) -> bool:
    return isinstance(adapter, SupportsModelChoice)


def apply_model(adapter: object, model: str | None) -> object:
    """Model名を適用したAdapterを返す。適用できなければそのまま返す。

    `model`が空/`None`なら何もしない——**空文字で上書きしない**。
    「候補が書かれていない」を「Model名なしで呼べ」と読むと、
    今まで動いていたAdapterの既定Modelを壊す。
    """
    if not model or not supports_model_choice(adapter):
        return adapter
    return adapter.with_model(model)
