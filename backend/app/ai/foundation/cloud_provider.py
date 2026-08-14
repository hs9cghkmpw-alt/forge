"""Cloud OpenAI-Compatible Provider(FORGE-AI-FOUNDATION-010 Phase H、
2026-08-13)。

**2つ目のCloud Provider枠**。目的は「Geminiの無料枠が尽きてもForgeが
止まらないこと」(§H)であり、そのために必要なのは*特定の会社*では
なく、*Geminiとは独立した別の経路*である。

    FORGE_CLOUD_BASE_URL=https://<provider>/v1
    FORGE_CLOUD_API_KEY=<key>
    FORGE_CLOUD_MODEL=<model>

この3つを設定すると、Auto Discovery(`provider_registry.py`)が
拾ってRoutingへ載せる。**コード変更は要らない。**

---

## なぜ特定Providerのbase_urlを書かなかったか(正直な申告)

指示書§Hは「実装時に公式ドキュメントから選定」とある。この開発環境は
Provider公式ドキュメントのドメイン(console.groq.com / openrouter.ai /
docs.cerebras.ai)へのegressが proxy で禁止されており、**公式の
エンドポイント・モデル名・レート制限を確認できなかった**。

記憶や検索結果から`https://api.groq.com/openai/v1`のような定数を
書き込むことはできる。しかしそれをすると、

* 実際に検証していないものが「実装済みProvider」として並ぶ
* 間違っていた場合、404/401として現れるまで誰も気付かない

——§39が禁じている「未検証を検証済みとして扱う」そのものになる。
したがって定数は書かず、**運用者が公式ドキュメントを見て設定する**
形にした。設定さえすれば、Adapterは既に完成している。

## Provider固有の癖について

OpenAI互換を名乗っていても、`response_format`の対応度はProviderに
よって差がある。`OpenAICompatibleAdapter`は`json_schema`で要求し、
駄目なら`json_object`で1回だけ取り直す段構えになっているので、
どちらか一方しか対応していないProviderでも動く。

追加ヘッダが要るProvider(OpenRouterの`HTTP-Referer`/`X-Title`等)は
`FORGE_CLOUD_EXTRA_HEADERS`にJSONで渡せる。**Provider名で分岐する
コードを足さない**——1社増えるたびにif文が増える構造にしない。
"""

from __future__ import annotations

import json
import os

from app.ai.foundation.openai_compatible import OpenAICompatibleAdapter

__all__ = ["CloudCompatibleProvider"]

_DEFAULT_TIMEOUT_SECONDS = 60.0


def _extra_headers() -> dict[str, str]:
    """`FORGE_CLOUD_EXTRA_HEADERS`(JSONオブジェクト)を読む。

    壊れたJSONは**黙って無視する**。ここで起動を止めると、
    追加ヘッダを使わないProviderまで巻き込んで動かなくなる
    ——ヘッダが無くて困るのはそれを要求するProviderだけであり、
    そのときは401として現れて分類される。
    """
    raw = os.environ.get("FORGE_CLOUD_EXTRA_HEADERS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


class CloudCompatibleProvider(OpenAICompatibleAdapter):
    """環境変数だけで構成される、OpenAI互換Cloud Providerへの接続。

    未設定の状態でも**構築はできる**(`base_url`が空になる)。
    Auto Discoveryが候補から外すので自動Routingには載らず、
    `provider`を明示して呼んだ場合だけ「設定されていない」ことが
    エラーとして現れる。構築時に例外を投げないのは、
    `ProviderRouter`が起動時に全Providerを構築するためである
    ——1つ未設定なだけでForge全体が起動しなくなってはならない。
    """

    def __init__(self) -> None:
        super().__init__(
            provider_name="cloud",
            base_url="",  # 下のpropertyが環境から遅延解決する
            model="",
            api_key_env="FORGE_CLOUD_API_KEY",
            timeout_seconds=float(
                os.environ.get("FORGE_CLOUD_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS)
            ),
        )

    # 設定は**呼ばれるたび**に環境から読む。`ProviderRouter`は起動時に
    # 全Providerを構築するため、構築時に環境を焼き付けると、後から
    # 設定を足しても反映されない(Auto Discoveryは環境を毎回見るので、
    # 「候補には載るが空のURLへ投げる」というずれが起きる)。
    @property
    def base_url(self) -> str:
        return os.environ.get("FORGE_CLOUD_BASE_URL", "").strip().rstrip("/")

    @property
    def model(self) -> str:
        return os.environ.get("FORGE_CLOUD_MODEL", "").strip()

    def _headers(self) -> dict[str, str]:
        return {**super()._headers(), **_extra_headers()}
