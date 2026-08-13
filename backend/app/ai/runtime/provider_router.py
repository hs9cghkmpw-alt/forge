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

from typing import Protocol

from app.ai.foundation.interfaces import LLMAdapter
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

    def __init__(self) -> None:
        """既定で6つのProviderインスタンス(5つの元のスタブ + FORGE-
        MILESTONE-005で追加したmock)を構築し、8つの名前(6インスタンス +
        FORGE-MILESTONE-004で追加した2つのエイリアス)で登録する。
        エイリアスは新しいインスタンスではなく、既存インスタンスへの
        別名参照である(同一Providerを指す)。
        """
        forge_ai_provider = ForgeAIProvider()
        oss_provider = OSSProvider()
        self._providers: dict[str, AIProvider] = {
            "openai": OpenAIProvider(),
            "claude": ClaudeProvider(),
            "gemini": GeminiProvider(),
            "oss": oss_provider,
            "forge_ai": forge_ai_provider,
            # FORGE-MILESTONE-004 PHASE8で追加したエイリアス。
            "native": forge_ai_provider,
            # FORGE-QUALITY-AI-INDEPENDENCE-003 Phase G(2026-08-12):
            # `"local"`は以前`OSSProvider`(未実装スタブ)のエイリアス
            # だった。ローカル推論Runtime(Ollama等、OpenAI互換)へ実際に
            # 接続する`LocalModelProvider`へ差し替える。Runtimeが起動して
            # いない環境では、呼び出し時に`LocalModelError`となり
            # `ModelGateway`がfallbackする(登録自体は常に安全)。
            "local": LocalModelProvider(),
            # FORGE-MILESTONE-005 Task8で追加。唯一実際に動作するProvider。
            "mock": MockLLMAdapter(),
        }

    def available_providers(self) -> tuple[str, ...]:
        """登録済みProvider名の一覧を返す(エイリアス含め8件)。"""
        return tuple(self._providers.keys())

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
        """既定のProvider名を返す。FORGE-MILESTONE-005で`"forge_ai"`から
        `"mock"`へ修正した(`docs/spec/ADAPTER_CONTRACT_V1.md` 4.0節、
        CEOレビュー対応)。`forge_ai`はCognitive Engine名であり、
        Providerの既定名として使うべきではなかった。現在無料・未接続段階で
        実際に動作するProviderは`mock`のみであるため、これが正確な既定値。
        """
        return "mock"


class AIProviderFactory(Protocol):
    """将来、設定ファイル・環境変数等からProviderRouterを構築する処理を
    抽象化するためのProtocol(現時点では`ProviderRouter()`を直接構築すれば
    十分なため未実装。拡張点として型だけ用意する)。
    """

    def create_router(self) -> ProviderRouter:
        """設定からProviderRouterを構築する。"""
        ...
