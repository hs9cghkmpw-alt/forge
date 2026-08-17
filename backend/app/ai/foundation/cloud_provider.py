"""OpenAI互換Cloud Providerの**インスタンス化**
(FORGE-AI-FOUNDATION-010 Phase H → 011 §1で再設計、2026-08-14)。

---

## 011で何を変えたか

010では`provider_name = "cloud"`固定の1枠だった。環境変数を
差し替えれば中身がGroqにもCerebrasにもなるが、**Forgeから見ると
常に同じ`cloud`**である。その結果:

    今日: cloud = Groq    → Quota学習・Benchmark・Provenance
    明日: cloud = Cerebras → 同じ`cloud`の記録へ混ざる

Circuit Breakerは「昨日Groqが落ちた」ことを理由に今日のCerebrasを
除外し、Benchmarkは別物の精度を平均する。**Identityが無いと、
記録が意味を失う。**

011では`provider_id`をコンストラクタで受け取る。`groq`と`cerebras`は
別インスタンス・別Identityであり、読む環境変数も
`FORGE_GROQ_*` / `FORGE_CEREBRAS_*` と分かれる。

**Protocolの共有はそのままである**——HTTP通信の実装は
`OpenAICompatibleAdapter`1つで、Providerが増えても増えない
(§1「Provider追加ごとにHTTP通信実装をコピーしないこと」)。

## 設定は規約で決まる

    FORGE_<PROVIDER_ID>_BASE_URL
    FORGE_<PROVIDER_ID>_API_KEY
    FORGE_<PROVIDER_ID>_MODEL
    FORGE_<PROVIDER_ID>_TIMEOUT_SECONDS   (任意)
    FORGE_<PROVIDER_ID>_EXTRA_HEADERS     (任意、JSON)

規約にしているのは、Providerを1つ足すのに覚えることを減らすため
である(`provider_registry.env_prefix_for()`)。

## base_urlを書いていない理由(正直な申告)

この開発環境はProvider公式ドキュメントのドメイン
(console.groq.com / openrouter.ai / docs.cerebras.ai)へのegressが
proxyで禁止されており、エンドポイント・モデル名を公式に確認
できなかった。記憶や検索結果から定数を書くと、未検証のものが
「実装済みProvider」として並ぶ(§39)。運用者が公式ドキュメントを
見て設定する形にしてある。
"""

from __future__ import annotations

import copy
import json
import os

from app.ai.foundation.openai_compatible import OpenAICompatibleAdapter
from app.core.env_settings import env_float
from app.ai.gateway.provider_registry import env_prefix_for

__all__ = ["OpenAICompatibleCloudProvider"]

_DEFAULT_TIMEOUT_SECONDS = 60.0


class OpenAICompatibleCloudProvider(OpenAICompatibleAdapter):
    """環境変数だけで構成される、OpenAI互換Cloud Providerへの接続。

    未設定の状態でも**構築はできる**(`base_url`が空になる)。
    Auto Discoveryが候補から外すので自動Routingには載らず、
    `provider`を明示して呼んだ場合だけ「設定されていない」ことが
    エラーとして現れる。構築時に例外を投げないのは、
    `ProviderRouter`が起動時に全Providerを構築するためである
    ——1つ未設定なだけでForge全体が起動しなくなってはならない。
    """

    def __init__(self, provider_id: str) -> None:
        self._prefix = env_prefix_for(provider_id)
        super().__init__(
            provider_name=provider_id,
            base_url="",  # 下のpropertyが環境から遅延解決する
            model="",
            api_key_env=f"{self._prefix}_API_KEY",
            # 013 §2: 空文字で落ちない共通境界を通す。**ここが一番効く**
            # ——`ProviderRouter`は起動時に全Providerを構築するので、
            # `FORGE_<ID>_TIMEOUT_SECONDS=`が1つ空なだけでForge全体が
            # 起動しなかった(`.env.example`にその行がある)。
            timeout_seconds=env_float(
                f"{self._prefix}_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS, minimum=0.1
            ),
        )

    # 設定は**呼ばれるたび**に環境から読む。`ProviderRouter`は起動時に
    # 全Providerを構築するため、構築時に環境を焼き付けると、後から
    # 設定を足しても反映されない(Auto Discoveryは環境を毎回見るので、
    # 「候補には載るが空のURLへ投げる」というずれが起きる)。
    @property
    def base_url(self) -> str:
        return os.environ.get(f"{self._prefix}_BASE_URL", "").strip().rstrip("/")

    @property
    def model(self) -> str:
        # **`with_model()`が指定したものを優先する。**
        # このクラスは`model`をpropertyで上書きしているので、親の
        # `with_model()`が`_model`へ書いても効かない(propertyが勝つ)。
        # 黙って無視されると「Modelを切り替えたつもりで切り替わって
        # いない」という一番調べにくい壊れ方になるので、明示的に見る。
        override = getattr(self, "_model_override", "")
        if override:
            return override
        return os.environ.get(f"{self._prefix}_MODEL", "").strip()

    def with_model(self, model: str) -> "OpenAICompatibleCloudProvider":
        """`SupportsModelChoice`。環境変数より優先する複製を返す。"""
        if not model or model == self.model:
            return self
        clone = copy.copy(self)
        clone._model_override = model  # noqa: SLF001 — 自分自身のコピー
        return clone

    def _headers(self) -> dict[str, str]:
        return {**super()._headers(), **self._extra()}

    def _extra(self) -> dict[str, str]:
        """`FORGE_<ID>_EXTRA_HEADERS`(JSONオブジェクト)を読む。

        追加ヘッダを要求するProvider(OpenRouterの`HTTP-Referer`等)の
        ためにある。**Provider名で分岐するコードを足さない**——
        1社増えるたびにif文が増える構造にしない。

        壊れたJSONは**黙って無視する**。ここで起動を止めると、
        追加ヘッダを使わないProviderまで巻き込んで動かなくなる
        ——ヘッダが無くて困るのはそれを要求するProviderだけであり、
        そのときは401として現れて分類される。
        """
        raw = os.environ.get(f"{self._prefix}_EXTRA_HEADERS", "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(key): str(value) for key, value in parsed.items()}
