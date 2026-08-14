"""AI Runtime — Provider Router(FORGE-MILESTONE-003 PHASE6/7/8、
FORGE-MILESTONE-004 PHASE8、FORGE-MILESTONE-005 Task8で更新)。

**責務定義のみ。実装は含まない(ただしmockのみ実装済み)。** ルーティングの
「選択ロジック」自体は実際に動作する(どのProviderを選ぶか、という判断は
AI呼び出しではないため)。選ばれたProviderを実際に呼び出すと、
`mock`以外は既存のスタブ(foundation/providers.py)が`NotImplementedError`
を投げる。`mock`(`MockLLMAdapter`)のみ、実際に動作する(FORGE-MILESTONE-005
Task7、`docs/spec/ADAPTER_CONTRACT_V1.md` 4.0節「無料・未接続段階では
'mock'を既定にするのが正確」に対応)。

Provider非依存の原則(PHASE8「Provider固有型は禁止」)を守るため、
このファイルはOpenAI SDK・Anthropic SDK・Google SDK等を一切importしない。

## FORGE-MILESTONE-005での変更: Engine/Provider分離、既定値をmockへ

CEOレビュー(ADAPTER_CONTRACT_V1.md 4.0節)により、`default_provider_name()`
が`"forge_ai"`(Cognitive Engine名)を返していたのはEngine名と
Provider名の混同であると指摘された。`forge_ai`という語は今後
「Engine名」としてのみ使い、Provider名としては使わない
(`"forge_ai"`という名前のProviderエントリ自体は、既存テストとの
後方互換のため削除していない。ただし新規コードは`"mock"`を使うこと)。

## FORGE-MILESTONE-004での変更: "native"/"local"エイリアス追加

FORGE-MILESTONE-004 PHASE8は、Provider名の語彙として
「Native / Claude / OpenAI / Gemini / Local」を要求した。既存
(FORGE-MILESTONE-003)の名前は「openai / claude / gemini / oss / forge_ai」
だった。実装(スタブ)は増やさず、"native"→`forge_ai`と同じインスタンス、
"local"→`oss`と同じインスタンス、というエイリアスとして追加した
(新しいProvider実装を増やしたわけではない。禁止事項「不要なDependency
追加」に抵触しない、名前解決の追加に過ぎない)。既存の5名前は
後方互換性のため削除していない(既存テストが依存しているため)。
"""

from __future__ import annotations

import os
from typing import Protocol

from app.ai.foundation.interfaces import LLMAdapter
from app.ai.gateway.provider_registry import Protocol as ProviderProtocol
from app.ai.gateway.provider_registry import provider_registry
from app.ai.foundation.cloud_provider import OpenAICompatibleCloudProvider
from app.ai.foundation.local_provider import LocalModelProvider
from app.ai.foundation.providers import (
    ClaudeProvider,
    ForgeAIProvider,
    GeminiProvider,
    MockLLMAdapter,
    OpenAIProvider,
    OSSProvider,
)

# PHASE7が要求する名前(`AIProvider`)を、既存のLLMAdapter Protocolの
# エイリアスとして提供する(意味は完全に同一)。
AIProvider = LLMAdapter


class ProviderNotAvailableError(Exception):
    """未登録のProvider名を要求した場合に送出する。"""


class ProviderRouter:
    """Provider名(文字列)から、対応する`AIProvider`実装を解決する。

    **重要**: `mock`以外は、いずれも`foundation/providers.py`の
    未実装スタブである。`ProviderRouter`自体は「どれを選ぶか」を決定できるが、
    選んだ結果を実際に呼び出す(`complete_structured()`)と
    (`mock`を除き)`NotImplementedError`になる。これは意図的な設計であり、
    「AI実装したふり」(禁止事項)を避けるための境界線である:
    ルーティング(選択)は実装済みの機能、推論そのものは(mock以外)未実装、
    という区別を明確にしている。
    """

    # **このモジュールが持つのは「実装」だけ**であり、「どの名前が
    # 存在するか」「鍵はどの環境変数か」「Cloudかどうか」といった
    # 宣言的な情報は`provider_registry.py`が唯一持つ(010 Phase C)。
    #
    # **provider_idごとの専用実装**。ここに名前を書くのは、その名前が
    # 固有の実装を必要とする場合だけである。
    _SPECIFIC_FACTORIES: dict[str, type] = {
        "gemini": GeminiProvider,      # Gemini独自Protocol
        "local": LocalModelProvider,   # OpenAI互換だが既定値と失敗の言葉が固有
        "mock": MockLLMAdapter,
        # 以下は未実装スタブ(呼ぶとNotImplementedError)。
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "oss": OSSProvider,
        "forge_ai": ForgeAIProvider,
    }

    # **Protocolごとの汎用実装**(FORGE-AI-FOUNDATION-011 §1)。
    #
    # 専用実装が無いProviderは、Protocolを見てここから作る。これにより
    # `groq`・`cerebras`・`openrouter`… が増えても**HTTP通信の実装は
    # 1つのまま**である(§1「Provider追加ごとにHTTP通信実装を
    # コピーしないこと」)。
    #
    # 増えるのはRegistryの宣言1行だけで、`FORGE_EXTRA_PROVIDERS`を
    # 使えばコード変更すら要らない。
    _PROTOCOL_FACTORIES: dict[ProviderProtocol, object] = {
        ProviderProtocol.OPENAI_COMPATIBLE: OpenAICompatibleCloudProvider,
    }

    def __init__(self) -> None:
        """Registryが宣言するProviderをすべて構築する。

        **Registryにあるのに構築できない名前は起動時に落とす**
        ——「宣言はあるが呼べない」という食い違いを実行時まで
        持ち越さない。別名は新しいインスタンスではなく、既存
        インスタンスへの別名参照である(同一Providerを指す)。
        """
        self._providers: dict[str, AIProvider] = {}
        for definition in provider_registry():
            self._providers[definition.provider_id] = self._build(definition)
        for definition in provider_registry():
            target = self._providers[definition.provider_id]
            for alias in definition.aliases:
                self._providers.setdefault(alias, target)

    def _build(self, definition) -> AIProvider:  # noqa: ANN001 — ProviderDefinition
        """宣言からAdapterを作る。専用実装 → Protocol汎用実装 の順。"""
        specific = self._SPECIFIC_FACTORIES.get(definition.provider_id)
        if specific is not None:
            return specific()
        generic = self._PROTOCOL_FACTORIES.get(definition.protocol)
        if generic is not None:
            # 汎用実装は`provider_id`を受け取る——**Identityは
            # Protocolに潰さない**(§1)。読む環境変数も
            # `FORGE_<ID>_*`とProviderごとに分かれる。
            return generic(definition.provider_id)
        raise ProviderNotAvailableError(
            f"Registryが宣言するProvider '{definition.provider_id}' "
            f"(protocol={definition.protocol.value}) に対応する実装がありません。"
            f"専用実装を`_SPECIFIC_FACTORIES`へ、または該当Protocolの"
            f"汎用実装を`_PROTOCOL_FACTORIES`へ追加してください。"
        )

    def available_providers(self) -> tuple[str, ...]:
        """登録済みProvider名の一覧を返す(エイリアス含め8件)。"""
        return tuple(self._providers.keys())

    def is_registered(self, provider_name: str) -> bool:
        """その名前のProviderが登録されているか。**Adapterは渡さない**
        (FORGE-AI-FOUNDATION-010 Phase B)。

        名前の存在確認に`resolve()`を使うと、「名前を確かめただけ」と
        「Adapterを取ってAIを呼んだ」が区別できなくなる。Anti-Bypass
        Regression(`tests/test_router_anti_bypass.py`)は
        `resolve()`の呼び出しを迂回の証拠として扱うので、**確認だけの
        用途にはこちらを使うこと**。
        """
        return provider_name in self._providers

    def resolve(self, provider_name: str) -> AIProvider:
        """provider_nameに対応するAIProviderを返す。未登録の名前なら
        `ProviderNotAvailableError`を送出する(クラッシュではなく、
        呼び出し側が判定できる例外型で失敗させる)。
        """
        provider = self._providers.get(provider_name)
        if provider is None:
            raise ProviderNotAvailableError(
                f"Provider '{provider_name}' is not registered. "
                f"Available: {', '.join(self.available_providers())}"
            )
        return provider

    def default_provider_name(self) -> str:
        """既定のProvider名を返す。

        FORGE-MILESTONE-005で`"forge_ai"`から`"mock"`へ修正した
        (`docs/spec/ADAPTER_CONTRACT_V1.md` 4.0節、CEOレビュー対応)。
        `forge_ai`はCognitive Engine名であり、Providerの既定名として
        使うべきではなかった。

        **FORGE-HANDOFF-LOCAL-AI-UX-004 §9(2026-08-13)で修正した実バグ**:
        既定が無条件に`"mock"`だったため、`GEMINI_API_KEY`を設定済みの
        環境でも、Provider名を送らないクライアント(Flutterは送っていない)
        には**黙ってMockの出力が返っていた**。CEOの実機確認で
        「mock resultがあると楽そう」という会話が出たのはこれが原因である。
        指示書は「Silent Mock fallbackは禁止」と明示している。

        解決順序(全て決定的、AI判断は入らない):

        1. `FORGE_DEFAULT_PROVIDER`が設定されていればそれを使う
           (運用側の明示的な指定を最優先する)。未登録の名前なら
           `ProviderNotAvailableError`——黙って別のProviderへ倒れない。
        2. `GEMINI_API_KEY`があれば`"gemini"`。実際に動く実Providerが
           あるなら、それが既定であるべき。
        3. どちらも無ければ`"mock"`。この場合Mockは**唯一動く選択肢**で
           あって、隠れたfallbackではない。呼び出し側はレスポンスの
           `simulated`フィールドで、これがMock出力であることを必ず
           利用者へ伝える(`app/routers/ai.py`参照)。
        """
        configured = os.environ.get("FORGE_DEFAULT_PROVIDER", "").strip()
        if configured:
            if configured not in self._providers:
                raise ProviderNotAvailableError(
                    f"FORGE_DEFAULT_PROVIDER='{configured}' は未登録のProvider名です。"
                    f"利用可能: {', '.join(self.available_providers())}"
                )
            return configured
        if os.environ.get("GEMINI_API_KEY", "").strip():
            return "gemini"
        return "mock"

    def is_simulated(self, provider_name: str) -> bool:
        """そのProviderの出力が「実際の推論結果」ではなく**模擬**かどうか。

        FORGE-HANDOFF-LOCAL-AI-UX-004 §9対応。Mockの出力をProduction UXへ
        本物として出さないため、呼び出し側がこれを見て利用者へ明示する。
        Provider名の文字列比較を各所へ散らかさないよう、判定はここに1つだけ置く。
        """
        return provider_name == "mock"


class AIProviderFactory(Protocol):
    """将来、設定ファイル・環境変数等からProviderRouterを構築する処理を
    抽象化するためのProtocol(現時点では`ProviderRouter()`を直接構築すれば
    十分なため未実装。拡張点として型だけ用意する)。
    """

    def create_router(self) -> ProviderRouter:
        """設定からProviderRouterを構築する。"""
        ...
