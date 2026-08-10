"""Native AI Runtime(FORGE-MILESTONE-004 PHASE9)。

ここまでのPHASE1〜8で作った各コンポーネントを、1つの束(bundle)として
まとめる。**このモジュール自体はAI推論を一切行わない。** 単に各コンポーネントへの
参照を1箇所に集約するだけの、責務を持たない組み立て役である
(「巨大Manager」「God Class」を避けるため、判断ロジックは持たせていない。
実際のオーケストレーション処理は`prompt_pipeline.PromptPipeline`が担う)。

## 構成要素と、それぞれの実装状況

| コンポーネント | 由来 | 実装状況 |
|---|---|---|
| IntentParser | intent_parser.py(PHASE1/2) | Protocol + Stub |
| AIPlanner | planner.py(既存、FORGE-MILESTONE-003) | Protocol + Stub |
| TemplateRegistry | template_engine.py(PHASE4) | **実装済み**(既存3 Templateのカタログ化、AI推論を含まない) |
| TemplateSelector | template_selector.py(PHASE5) | Protocol + Stub |
| LanguageGenerator | foundation/interfaces.py(既存、FORGE-MILESTONE-002) | Protocol(実装無し) |
| AIRepair | repair.py(既存、FORGE-MILESTONE-003) | Protocol + Stub |
| AICritic | critic.py(既存、FORGE-MILESTONE-003) | Protocol + Stub |
| ProviderRouter | provider_router.py(既存+PHASE8で拡張) | **実装済み**(ルーティングのみ、推論はStub) |
| PromptPipeline | prompt_pipeline.py(既存、FORGE-MILESTONE-003) | オーケストレーションのみ実装済み、各段階はStub |

**「実装済み」と分類したものも、AI推論そのものは一切含まない**
(TemplateRegistryは既存Template関数へのカタログ・委譲のみ、ProviderRouterは
辞書引きによる名前解決のみ)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.runtime.context_builder import AIContextBuilder, StubAIContextBuilder
from app.ai.runtime.critic import AICritic, StubAICritic
from app.ai.runtime.intent_parser import IntentParser, StubIntentParser
from app.ai.runtime.planner import AIPlanner, StubAIPlanner
from app.ai.runtime.provider_router import ProviderRouter
from app.ai.runtime.repair import AIRepair, StubAIRepair
from app.ai.runtime.template_engine import TemplateRegistry
from app.ai.runtime.template_selector import StubTemplateSelector, TemplateSelector


@dataclass
class NativeAIRuntime:
    """Forge Native AI Runtimeの構成要素一式。

    既定値は全てStub実装(`StubXxx`)である。実際のAI推論を持つ実装への
    差し替えは、このdataclassのフィールドを置き換えるだけで完結する
    (DIによる差し替え可能性。特定のProvider・特定のモデルへの結合は
    どこにも無い)。
    """

    intent_parser: IntentParser = field(default_factory=StubIntentParser)
    planner: AIPlanner = field(default_factory=StubAIPlanner)
    template_registry: TemplateRegistry = field(default_factory=TemplateRegistry)
    template_selector: TemplateSelector = field(default_factory=StubTemplateSelector)
    repair: AIRepair = field(default_factory=StubAIRepair)
    critic: AICritic = field(default_factory=StubAICritic)
    context_builder: AIContextBuilder = field(default_factory=StubAIContextBuilder)
    provider_router: ProviderRouter = field(default_factory=ProviderRouter)

    def describe(self) -> dict[str, str]:
        """各構成要素の実装クラス名を返す(診断・デバッグ用)。
        AI推論は行わない、純粋なメタ情報の取得。"""
        return {
            "intent_parser": type(self.intent_parser).__name__,
            "planner": type(self.planner).__name__,
            "template_registry": f"{len(self.template_registry.all_templates())} templates",
            "template_selector": type(self.template_selector).__name__,
            "repair": type(self.repair).__name__,
            "critic": type(self.critic).__name__,
            "context_builder": type(self.context_builder).__name__,
            "provider_router": f"{len(self.provider_router.available_providers())} provider names",
        }

    def is_fully_stubbed(self) -> bool:
        """全ての推論系コンポーネントがStub実装のままかどうかを返す
        (「動いたふりをしていないか」を機械的に確認できるようにするための
        ヘルパー。TemplateRegistry・ProviderRouterは推論を持たないコンポーネント
        のため判定対象に含めない)。"""
        stub_type_names = {
            "StubIntentParser", "StubAIPlanner", "StubTemplateSelector",
            "StubAIRepair", "StubAICritic", "StubAIContextBuilder",
        }
        actual_type_names = {
            type(self.intent_parser).__name__,
            type(self.planner).__name__,
            type(self.template_selector).__name__,
            type(self.repair).__name__,
            type(self.critic).__name__,
            type(self.context_builder).__name__,
        }
        return actual_type_names.issubset(stub_type_names)
