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
import re
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
    "StructuredOutputMode",
    "configured_providers",
    "extra_providers",
    "provider_registry",
    "weaker_mode",
    "definition_for",
]


class StructuredOutputMode(str, Enum):
    """構造化出力を**どうやって要求するか**
    (FORGE-AI-FOUNDATION-011 §2、2026-08-14)。

    ---

    ## なぜ真偽値では足りなかったか(実バグの原因)

    010では`supports_structured_output: bool`しか持っていなかった。
    そのためAdapterは常に`json_schema`で要求し、Providerが
    `json_schema`を知らずにHTTP 400を返すと、

        HTTP 400 → INVALID_REQUEST → 「Forge側の誤り」→ 全Routing停止

    となった。実際には**そのProviderがそのmodeを知らないだけ**で、
    緩いmodeなら答えられたし、他のProviderなら`json_schema`で
    答えられた。

    「対応しているか」を1bitに潰したことで、**何に対応していないか**が
    言えなくなっていた、というのが原因である。

    ## 強い順に並んでいる

    上ほど制約が強く、Forgeにとって望ましい。Adapterは対応modeの
    うち最も強いものから試し、mode非対応が原因の失敗に限り**1段だけ**
    緩める(§2「安全なdowngradeを1回だけ」)。
    """

    STRICT_JSON_SCHEMA = "strict_json_schema"
    """`response_format: json_schema` かつ `strict: true`。
    スキーマ違反をProvider側が構造的に防ぐ。"""

    JSON_SCHEMA = "json_schema"
    """`response_format: json_schema`(strictなし)。スキーマは
    **指示として**渡るが、守られる保証はない。"""

    JSON_OBJECT = "json_object"
    """`response_format: json_object`。JSONであることだけが保証され、
    形はプロンプト頼み。"""

    PROMPT_JSON = "prompt_json"
    """`response_format`を送らず、プロンプトだけでJSONを求める。
    最も弱いが、**どのProviderでも成立する**最後の手段。"""

    UNSUPPORTED = "unsupported"
    """構造化出力の概念が無い。Forgeの全Taskが成立しないので、
    `requires_strict_schema`なTaskの候補から外れる。"""


# 弱い方向への並び。downgradeは**この順で1段だけ**進む。
_DOWNGRADE_ORDER: tuple[StructuredOutputMode, ...] = (
    StructuredOutputMode.STRICT_JSON_SCHEMA,
    StructuredOutputMode.JSON_SCHEMA,
    StructuredOutputMode.JSON_OBJECT,
    StructuredOutputMode.PROMPT_JSON,
)


def weaker_mode(mode: StructuredOutputMode) -> StructuredOutputMode | None:
    """1段だけ弱いmode。これ以上緩められなければ`None`。"""
    try:
        index = _DOWNGRADE_ORDER.index(mode)
    except ValueError:
        return None
    if index + 1 >= len(_DOWNGRADE_ORDER):
        return None
    return _DOWNGRADE_ORDER[index + 1]


class Protocol(str, Enum):
    """どのAPI形式で話すか。

    **Adapterを再利用できる単位**である。`OPENAI_COMPATIBLE`が
    1つの値になっているのは、Ollama/vLLM/Groq/OpenRouter等が同じ
    `/v1/chat/completions`契約を共有しており、1つのAdapterで足りる
    ためである(Phase E)。

    **Protocolを共有することと、Identityを共有することは別である**
    (011 §1)。`groq`と`cerebras`は同じProtocolを話すが、Quota・
    Circuit Breaker・Benchmark・Provenanceの上では**別のProvider**で
    なければならない。010の`cloud`という1枠は、この2つを混同していた。
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
    """**このProviderの同一性**。Quota / Circuit Breaker / Benchmark /
    Experience / Provenance のすべてがこのキーで区別される。

    Protocolを共有していても、これが違えば別のProviderである
    (011 §1)。`cloud`のような、中身が入れ替わりうる名前を
    使ってはならない——昨日のGroqと今日のCerebrasが同じ統計へ
    混ざる。"""

    protocol: Protocol
    deployment: Deployment
    implementation_status: ImplementationStatus
    supports_structured_output: bool
    quota_strategy: QuotaStrategy
    error_strategy: ErrorStrategy

    structured_output_modes: tuple[StructuredOutputMode, ...] = ()
    """このProviderが対応すると**宣言している**構造化出力mode(強い順)。

    空なら`supports_structured_output`から推定する(後方互換)。

    **宣言は仮説である。** 実際に400が返れば、その事実の方を採る
    (`_LEARNED_MODES`)。Provider公称を検証済みとして扱わない(§46)。"""

    nominal_timeout_seconds: float = 60.0
    """このProviderが1回の応答に要しうる時間の目安。

    Task全体の予算(§4)を守るために使う。**Adapterがdeadlineを
    受け付けない場合**、Routerは「残り予算 < これ」なら試行を
    始めない——始めれば予算を超えることが分かっているからである。"""

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

    @property
    def declared_output_modes(self) -> tuple[StructuredOutputMode, ...]:
        """対応modeを強い順に返す(未宣言なら真偽値から推定)。"""
        if self.structured_output_modes:
            return self.structured_output_modes
        if not self.supports_structured_output:
            return (StructuredOutputMode.PROMPT_JSON,)
        return (StructuredOutputMode.JSON_SCHEMA, StructuredOutputMode.JSON_OBJECT)

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

def env_prefix_for(provider_id: str) -> str:
    """`groq` → `FORGE_GROQ`。環境変数名の**規約**。

    規約にしているのは、Providerを1つ足すのに覚えることを減らす
    ためである。`FORGE_<ID>_BASE_URL` / `_API_KEY` / `_MODEL` の3つで
    どのProviderも設定できる。
    """
    return "FORGE_" + provider_id.upper().replace("-", "_")


def _openai_compatible_cloud(
    provider_id: str,
    *,
    notes: str = "",
    implementation_status: ImplementationStatus = ImplementationStatus.IMPLEMENTED,
) -> ProviderDefinition:
    """OpenAI互換Cloud Providerの宣言を、規約から組み立てる。

    **HTTP通信実装は増えない**(011 §1)——`Protocol.OPENAI_COMPATIBLE`
    なので`OpenAICompatibleAdapter`がそのまま使われる。増えるのは
    宣言1行だけである。

    `base_url`をここに書かないのは010と同じ理由である: この開発環境は
    Provider公式ドキュメントのドメインへegress禁止であり、
    エンドポイントを公式に確認できなかった。記憶や検索結果から定数を
    書くと、未検証のものが「実装済み」の顔で並ぶ(§39)。
    運用者が公式ドキュメントを見て設定する。
    """
    prefix = env_prefix_for(provider_id)
    return ProviderDefinition(
        provider_id=provider_id,
        protocol=Protocol.OPENAI_COMPATIBLE,
        deployment=Deployment.CLOUD,
        implementation_status=implementation_status,
        supports_structured_output=True,
        # OpenAI互換を名乗るProviderでも`json_schema`の対応度には差が
        # ある。**宣言は仮説**であり、400が返れば事実の方を採る
        # (`structured_output_capability.py`)。
        structured_output_modes=(
            StructuredOutputMode.JSON_SCHEMA,
            StructuredOutputMode.JSON_OBJECT,
            StructuredOutputMode.PROMPT_JSON,
        ),
        quota_strategy=QuotaStrategy.RATE_LIMIT_HEADERS,
        error_strategy=ErrorStrategy.STRUCTURED,
        api_key_env=f"{prefix}_API_KEY",
        base_url_env=f"{prefix}_BASE_URL",
        model_env=f"{prefix}_MODEL",
        required_env=(f"{prefix}_BASE_URL", f"{prefix}_API_KEY", f"{prefix}_MODEL"),
        nominal_timeout_seconds=60.0,
        notes=notes or (
            f"OpenAI互換Cloud。`{prefix}_BASE_URL` / `{prefix}_API_KEY` / "
            f"`{prefix}_MODEL` を公式ドキュメントに従って設定すると"
            "Auto Discoveryが拾う。**Adapter実装は共有**(Protocol駆動)。"
        ),
    )


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
        nominal_timeout_seconds=30.0,
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
        nominal_timeout_seconds=120.0,
        notes=(
            "`LocalModelProvider`(Ollama等のOpenAI互換Runtime)。"
            "**鍵が無くても設定済みとして扱う**——Runtimeが起動して"
            "いるかは環境変数からは判定できないので、呼んでみて"
            "`LOCAL_RESOURCE_ERROR`で学習する。"
        ),
    ),
    # --- OpenAI互換のCloud Provider群 -------------------------------------
    #
    # **1つずつ別のIdentityを持つ**(011 §1)。Protocolは共有するので
    # Adapter実装は1つだが、Quota・Circuit Breaker・Benchmark・
    # Provenanceはこの`provider_id`で分かれる。
    #
    # 010の`cloud`という単一枠は、今日Groq・明日Cerebrasを同じ名前で
    # 受けてしまい、統計が混ざる構造だった。
    *(
        _openai_compatible_cloud(provider_id)
        for provider_id in ("groq", "cerebras", "openrouter", "together", "deepinfra")
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
        # プロセス内で即答する。予算がほとんど残っていなくても入る。
        nominal_timeout_seconds=1.0,
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


# ---------------------------------------------------------------------------
# 追加Provider(コード変更なしで増やす、011 §1)
# ---------------------------------------------------------------------------
#
#     FORGE_EXTRA_PROVIDERS=myhost,another
#     FORGE_MYHOST_BASE_URL=...
#     FORGE_MYHOST_API_KEY=...
#     FORGE_MYHOST_MODEL=...
#
# 上のRegistryに名前が無いOpenAI互換Providerを載せるための口である。
#
# **`provider_id`を必ず名指しさせる**のが要点で、010の`cloud`のような
# 「中身が入れ替わりうる汎用名」を作らせない。名前を書く手間が、
# そのままIdentityの分離になる。

_EXTRA_PROVIDERS_ENV = "FORGE_EXTRA_PROVIDERS"

# 予約語。既存Providerを環境変数から上書きさせない——`gemini`を
# 別のエンドポイントへ向けられると、Benchmarkの記録が意味を失う。
_RESERVED_IDS = frozenset(
    {d.provider_id for d in PROVIDER_REGISTRY}
    | {alias for d in PROVIDER_REGISTRY for alias in d.aliases}
)

_VALID_ID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def extra_providers() -> tuple[ProviderDefinition, ...]:
    """`FORGE_EXTRA_PROVIDERS`が宣言するProvider。

    不正な名前(予約語・記号入り)は**黙って捨てる**。ここで例外に
    するとForge全体が起動しなくなり、追加Providerの設定ミス1つで
    既存の経路まで止まる。捨てたことは`extra_provider_warnings()`で
    言えるようにしてある——黙って消えるだけにはしない。
    """
    return tuple(
        definition for definition, _ in _parse_extra_providers() if definition is not None
    )


def extra_provider_warnings() -> tuple[str, ...]:
    """`FORGE_EXTRA_PROVIDERS`のうち、載せられなかったものの理由。"""
    return tuple(reason for _, reason in _parse_extra_providers() if reason)


def _parse_extra_providers() -> tuple[tuple[ProviderDefinition | None, str], ...]:
    raw = os.environ.get(_EXTRA_PROVIDERS_ENV, "").strip()
    if not raw:
        return ()
    results: list[tuple[ProviderDefinition | None, str]] = []
    for token in raw.split(","):
        provider_id = token.strip().lower()
        if not provider_id:
            continue
        if not _VALID_ID.match(provider_id):
            results.append((None, f"{provider_id!r}: Provider名の形式が不正"))
            continue
        if provider_id in _RESERVED_IDS:
            results.append((None, f"{provider_id!r}: 既存Providerの名前は上書きできない"))
            continue
        results.append((_openai_compatible_cloud(provider_id), ""))
    return tuple(results)


def provider_registry() -> tuple[ProviderDefinition, ...]:
    """静的な宣言 + 環境が足したProvider。**唯一の一覧**である。"""
    return (*PROVIDER_REGISTRY, *extra_providers())


def definition_for(provider_id: str) -> ProviderDefinition | None:
    """名前(別名を含む)から宣言を引く。未知なら`None`。"""
    for definition in provider_registry():
        if provider_id == definition.provider_id or provider_id in definition.aliases:
            return definition
    return None


def configured_providers() -> tuple[ProviderDefinition, ...]:
    """**この環境で実際に自動Routingへ載せられる**Providerだけを返す。

    Auto Discovery(Phase F)はこれ1本である。実装があり、設定が
    揃っていて、テスト専用でないもの——その3条件を満たさないものを
    候補に並べても、失敗を1回増やすだけになる。
    """
    return tuple(d for d in provider_registry() if d.is_usable)
