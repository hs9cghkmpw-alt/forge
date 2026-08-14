"""Provider Registry(FORGE-AI-FOUNDATION-010 Phase C、2026-08-13)。

「Forgeが知っているAI Providerは何か」を**1箇所で**宣言する。

---

## なぜ要るのか(直前まで3箇所に散っていた)

Phase Bの時点で、Providerに関する知識は3つの場所に別々にあった:

1. `ProviderRouter._providers` — 名前 → Adapterインスタンスの表
2. `ai_router._KNOWN_MODELS` — 名前 → Routing用の性質
3. `default_catalog()` — どの環境変数を見るか(`GEMINI_API_KEY`等)

Providerを1つ足すたびに3箇所を揃えなければならず、揃え忘れても
**テストは通る**(片方しか見ていないため)。TD37で同じ形の事故を
既に踏んでいる——Widget Registry・Validator・Runtimeの三者が
ずれていて、実機で初めて分かった。

したがってこのモジュールが唯一の宣言であり、上の3つはここから
導出する。

## Secretの扱い(§14〜§18)

`api_key_env`が持つのは**環境変数の名前**であって、値ではない。
このモジュールは値を読まない・保持しない・出力しない。値が要るのは
Adapter実装だけであり、そこでも`os.environ`から直接読む。

`is_configured`は「その環境変数が空でないか」という真偽値だけを返す。
**長さも先頭数文字も返さない**——診断に便利だが、ログや
レポートへ流れ出す経路を作ることになる。

## 「宣言されている」は「動く」ではない

`implementation_status`を持たせているのは、この2つを混同しないため
である。`openai`や`claude`は名前としては登録済みだが、実装は
`NotImplementedError`を投げるスタブでしかない。Routingの候補に
載せれば必ず失敗して試行予算を食う(§36)。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Deployment",
    "ErrorStrategy",
    "ImplementationStatus",
    "PROVIDER_REGISTRY",
    "Protocol",
    "ProviderDefinition",
    "QuotaStrategy",
    "configured_providers",
    "definition_for",
]


class Protocol(str, Enum):
    """どのAPI形式で話すか。

    **Adapterを再利用できる単位**である。`OPENAI_COMPATIBLE`が
    1つの値になっているのは、Ollama/vLLM/Groq/OpenRouter等が同じ
    `/v1/chat/completions`契約を共有しており、1つのAdapterで足りる
    ためである(Phase E)。
    """

    GEMINI_NATIVE = "gemini_native"
    """Google Gemini独自形式(`responseSchema`等)。"""

    OPENAI_COMPATIBLE = "openai_compatible"
    """OpenAI `/v1/chat/completions`互換。Local Runtimeも多くがこれ。"""

    ANTHROPIC_NATIVE = "anthropic_native"

    IN_PROCESS = "in_process"
    """外部通信をしない(Mock等)。"""


class Deployment(str, Enum):
    LOCAL = "local"
    """このマシン上で動く。API Quotaを消費せず、入力が外部へ出ない。"""

    CLOUD = "cloud"
    """外部サービス。Quotaを消費し、**入力が外部へ出る**。"""


class ImplementationStatus(str, Enum):
    """`ProviderDefinition`があることと、動くことは別である。"""

    IMPLEMENTED = "implemented"
    """実際に呼べるAdapterがある。"""

    STUB = "stub"
    """名前だけ登録済み。呼ぶと`NotImplementedError`。
    **自動Routingの候補にしない**。"""

    PLANNED = "planned"
    """Adapterすら無い。宣言だけ。"""


class QuotaStrategy(str, Enum):
    """残量について、そのProviderが**何を教えてくれるか**(§9)。

    「教えてくれない」を`NONE`として正面から持つ。**不明を無制限と
    扱わない**ため、この値は`QuotaKnowledge.UNKNOWN`へ写る。
    """

    RETRY_AFTER_HEADER = "retry_after_header"
    """`Retry-After`で復帰時刻が分かる。"""

    RATE_LIMIT_HEADERS = "rate_limit_headers"
    """`x-ratelimit-remaining`等で残量が分かる。"""

    NONE = "none"
    """何も返さない。枠切れは失敗して初めて分かる。"""

    NOT_APPLICABLE = "not_applicable"
    """Local / Mock。枠という概念が無い。"""


class ErrorStrategy(str, Enum):
    """失敗の**種類をどこから読めるか**(Phase Gの正規化順序で使う)。

    文字列マッチは最後の手段である。ここに宣言があることで、
    「このProviderは構造化エラーを返すのに、文字列で当てにいって
    いる」という状態を検出できる。
    """

    STRUCTURED = "structured"
    """例外/応答に機械可読なエラー種別がある。"""

    HTTP_STATUS = "http_status"
    """HTTPステータスコードで判断できる。"""

    MESSAGE_ONLY = "message_only"
    """メッセージ文字列しか無い。**最も弱い**。"""


@dataclass(frozen=True)
class ProviderDefinition:
    """1 Providerの宣言。**値は持たない**(§14〜§18)。"""

    provider_id: str
    protocol: Protocol
    deployment: Deployment
    implementation_status: ImplementationStatus
    supports_structured_output: bool
    quota_strategy: QuotaStrategy
    error_strategy: ErrorStrategy

    api_key_env: str | None = None
    """API Keyを読む環境変数の**名前**。`None`なら鍵不要
    (Local / Mock)。**ここに値を書かない。**"""

    base_url_env: str | None = None
    model_env: str | None = None

    required_env: tuple[str, ...] | None = None
    """**設定済みと見なすために必要な**環境変数名。

    `api_key_env`とは意味が違う:

    * `api_key_env` — どの変数が**秘密**か。`.env.example`の検査と
      診断出力の対象を決める。
    * `required_env` — 何が揃えば**動くか**。Auto Discoveryが見る。

    分けているのは、両者が一致しないProviderが実在するためである。
    `local`は鍵が不要だが`base_url`には既定値があるので必須では
    ない(何も設定しなくても動きうる)。逆に汎用Cloud枠は、鍵に
    加えてエンドポイントとモデル名が無ければ**どこへ何を投げれば
    よいのかが決まらない**。

    `None`なら`api_key_env`があればそれだけを必須とする。
    """

    models: tuple[str, ...] = ()
    """既知のモデル名。**Routingの判断には使わない**——公称値を
    大量に固定すると、API変更のたびに嘘になる(§12)。診断と
    Benchmarkの対象指定のために持つ。"""

    test_only: bool = False
    """Mock等。自動Routingの候補にしない(§22)。"""

    aliases: tuple[str, ...] = ()
    """後方互換のための別名。既存テスト・既存クライアントが使う。"""

    notes: str = ""

    @property
    def requires_api_key(self) -> bool:
        return self.api_key_env is not None

    @property
    def required_variables(self) -> tuple[str, ...]:
        if self.required_env is not None:
            return self.required_env
        return (self.api_key_env,) if self.api_key_env else ()

    @property
    def is_configured(self) -> bool:
        """この環境で**設定が揃っているか**。

        返すのは真偽値だけである。値の長さも先頭数文字も返さない
        ——診断には便利だが、ログやレポートへ実値の断片が流れ出す
        経路を作ることになる(§67)。
        """
        return all(
            os.environ.get(variable, "").strip() for variable in self.required_variables
        )

    def missing_variables(self) -> tuple[str, ...]:
        """設定が足りない場合に、**何が足りないか**を名前で返す。

        「使えるProviderがありません」だけでは運用者が直せない
        (`NoProviderAvailableError`が理由を必ず持つのと同じ理由)。
        返すのは変数名であって値ではない。
        """
        return tuple(
            variable for variable in self.required_variables
            if not os.environ.get(variable, "").strip()
        )

    @property
    def is_usable(self) -> bool:
        """自動Routingの候補にしてよいか。

        3つを**すべて**満たす必要がある。1つでも欠けた候補を並べると、
        必ず失敗して試行予算(§20)を食うだけになる。
        """
        return (
            self.implementation_status is ImplementationStatus.IMPLEMENTED
            and self.is_configured
            and not self.test_only
        )

    def describe(self) -> dict[str, object]:
        """診断用。**実値は一切含まない**(環境変数名と真偽値だけ)。"""
        return {
            "provider_id": self.provider_id,
            "protocol": self.protocol.value,
            "deployment": self.deployment.value,
            "implementation_status": self.implementation_status.value,
            "api_key_env": self.api_key_env,
            "required_env": list(self.required_variables),
            "missing_env": list(self.missing_variables()),
            "configured": self.is_configured,
            "usable": self.is_usable,
            "supports_structured_output": self.supports_structured_output,
            "quota_strategy": self.quota_strategy.value,
            "error_strategy": self.error_strategy.value,
            "models": list(self.models),
            "test_only": self.test_only,
        }


# ---------------------------------------------------------------------------
# 宣言
# ---------------------------------------------------------------------------
#
# 順序が既定の優先順位になる(`default_catalog()`が読む)。Geminiが先頭
# なのは、**現時点で唯一品質を実測済み**だからであって、Cloudが本質的に
# 優れているからではない(§5: Benchmarkで決める)。

PROVIDER_REGISTRY: tuple[ProviderDefinition, ...] = (
    ProviderDefinition(
        provider_id="gemini",
        protocol=Protocol.GEMINI_NATIVE,
        deployment=Deployment.CLOUD,
        implementation_status=ImplementationStatus.IMPLEMENTED,
        supports_structured_output=True,
        quota_strategy=QuotaStrategy.NONE,
        error_strategy=ErrorStrategy.MESSAGE_ONLY,
        api_key_env="GEMINI_API_KEY",
        models=("gemini-2.0-flash",),
        notes=(
            "`GeminiProvider`が実装済み。`responseSchema`は`$ref`非対応で、"
            "`properties`の無い`object`を渡すと黙って`{}`を返す(TD40)。"
            "現行Adapterは`RuntimeError`しか投げないため`error_strategy`は"
            "MESSAGE_ONLY——Phase Gで構造化する対象である。"
        ),
    ),
    ProviderDefinition(
        provider_id="local",
        protocol=Protocol.OPENAI_COMPATIBLE,
        deployment=Deployment.LOCAL,
        implementation_status=ImplementationStatus.IMPLEMENTED,
        supports_structured_output=True,
        quota_strategy=QuotaStrategy.NOT_APPLICABLE,
        error_strategy=ErrorStrategy.STRUCTURED,
        base_url_env="FORGE_LOCAL_BASE_URL",
        model_env="FORGE_LOCAL_MODEL",
        notes=(
            "`LocalModelProvider`(Ollama等のOpenAI互換Runtime)。"
            "**鍵が無くても設定済みとして扱う**——Runtimeが起動して"
            "いるかは環境変数からは判定できないので、呼んでみて"
            "`LOCAL_RESOURCE_ERROR`で学習する。"
        ),
    ),
    ProviderDefinition(
        provider_id="cloud",
        protocol=Protocol.OPENAI_COMPATIBLE,
        deployment=Deployment.CLOUD,
        implementation_status=ImplementationStatus.IMPLEMENTED,
        supports_structured_output=True,
        quota_strategy=QuotaStrategy.RATE_LIMIT_HEADERS,
        error_strategy=ErrorStrategy.STRUCTURED,
        api_key_env="FORGE_CLOUD_API_KEY",
        base_url_env="FORGE_CLOUD_BASE_URL",
        model_env="FORGE_CLOUD_MODEL",
        required_env=("FORGE_CLOUD_BASE_URL", "FORGE_CLOUD_API_KEY", "FORGE_CLOUD_MODEL"),
        notes=(
            "**2つ目のCloud枠**(Phase H)。OpenAI互換の`/v1/chat/completions`を"
            "話すCloud Providerなら、環境変数3つを設定するだけでRoutingへ"
            "載る(Groq / OpenRouter / Together / Cerebras / DeepInfra 等)。\n\n"
            "**特定Providerのbase_urlをここへ書いていない理由**: この開発"
            "環境はProvider公式ドキュメントのドメインへegress禁止であり、"
            "エンドポイントやモデル名を公式に確認できなかった。記憶や"
            "検索結果から定数を書き込むと、間違っていても『実装済み』に"
            "見えてしまう(§39: 未検証を検証済みとして書かない)。"
            "運用者が公式ドキュメントを見て設定する形にしてある。\n\n"
            "Gemini枠が尽きてもForgeが止まらない、という目的(§H)は"
            "これで満たされる——Providerを1つ足すのにコード変更が要らない。"
        ),
    ),
    ProviderDefinition(
        provider_id="mock",
        protocol=Protocol.IN_PROCESS,
        deployment=Deployment.LOCAL,
        implementation_status=ImplementationStatus.IMPLEMENTED,
        supports_structured_output=True,
        quota_strategy=QuotaStrategy.NOT_APPLICABLE,
        error_strategy=ErrorStrategy.STRUCTURED,
        test_only=True,
        notes=(
            "決定的な模擬応答。自動Routingには載らない(§22)。"
            "利用者へは必ず`simulated: true`として伝える。"
        ),
    ),
    ProviderDefinition(
        provider_id="forge_ai",
        protocol=Protocol.IN_PROCESS,
        deployment=Deployment.LOCAL,
        implementation_status=ImplementationStatus.STUB,
        supports_structured_output=False,
        quota_strategy=QuotaStrategy.NOT_APPLICABLE,
        error_strategy=ErrorStrategy.MESSAGE_ONLY,
        aliases=("native",),
        notes=(
            "**Engine名をProvider名として使ってしまった歴史的な名前**"
            "(`provider_router.py`のdocstring参照)。実装はスタブで、"
            "呼ぶと`NotImplementedError`。新規コードは`mock`を使うこと。"
            "既存テスト・既存クライアントとの後方互換のためだけに残す。"
        ),
    ),
    ProviderDefinition(
        provider_id="openai",
        protocol=Protocol.OPENAI_COMPATIBLE,
        deployment=Deployment.CLOUD,
        implementation_status=ImplementationStatus.STUB,
        supports_structured_output=True,
        quota_strategy=QuotaStrategy.RATE_LIMIT_HEADERS,
        error_strategy=ErrorStrategy.HTTP_STATUS,
        api_key_env="OPENAI_API_KEY",
        notes="スタブ。呼ぶと`NotImplementedError`。",
    ),
    ProviderDefinition(
        provider_id="claude",
        protocol=Protocol.ANTHROPIC_NATIVE,
        deployment=Deployment.CLOUD,
        implementation_status=ImplementationStatus.STUB,
        supports_structured_output=True,
        quota_strategy=QuotaStrategy.RATE_LIMIT_HEADERS,
        error_strategy=ErrorStrategy.HTTP_STATUS,
        api_key_env="ANTHROPIC_API_KEY",
        notes="スタブ。呼ぶと`NotImplementedError`。",
    ),
    ProviderDefinition(
        provider_id="oss",
        protocol=Protocol.OPENAI_COMPATIBLE,
        deployment=Deployment.LOCAL,
        implementation_status=ImplementationStatus.STUB,
        supports_structured_output=False,
        quota_strategy=QuotaStrategy.NOT_APPLICABLE,
        error_strategy=ErrorStrategy.MESSAGE_ONLY,
        notes="スタブ。`local`が実質的な後継。",
    ),
)


_BY_ID: dict[str, ProviderDefinition] = {}
for _definition in PROVIDER_REGISTRY:
    _BY_ID[_definition.provider_id] = _definition
    for _alias in _definition.aliases:
        _BY_ID[_alias] = _definition


def definition_for(provider_id: str) -> ProviderDefinition | None:
    """名前(別名を含む)から宣言を引く。未知なら`None`。"""
    return _BY_ID.get(provider_id)


def configured_providers() -> tuple[ProviderDefinition, ...]:
    """**この環境で実際に自動Routingへ載せられる**Providerだけを返す。

    Phase Fの Auto Discovery はこれ1本である。実装があり、設定が
    揃っていて、テスト専用でないもの——その3条件を満たさないものを
    候補に並べても、失敗を1回増やすだけになる。
    """
    return tuple(d for d in PROVIDER_REGISTRY if d.is_usable)
