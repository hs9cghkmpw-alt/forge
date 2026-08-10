"""AI Providerの抽象契約(Provider Interface)。

forge_ai全体は、この`AIProvider` Protocolにのみ依存する。Claude/OpenAI/Gemini等の
具体的な実装はforge_ai/には一切含まれない(今回のスコープ外。禁止事項参照)。
テスト・開発では`provider.mock_provider.MockProvider`のみを使う。

設計方針:
- Provider Independence: 上位モジュール(core/*, repair/*)は`AIProvider`という
  Protocolだけを知り、具体的なProvider実装(Mock含む)のクラス名を知らない。
  DIで注入する。
- Providerが1つも実装されていなくても(Mockすら無くても)、`AIProvider`という
  型そのものは定義できる。ただし実際にテストを動かすにはMockProviderが要る
  (キックオフ指示書9章: 全テストはMockのみで実行可能、という要件を満たす)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from forge_ai.prompt.prompt_builder import Prompt


@dataclass(frozen=True)
class ProviderResponse:
    """Providerからの応答。

    `text`は人間可読な説明・理由付け、`structured`は後続モジュールが
    プログラム的に解釈するための構造化データ(dict)を持つ。
    実際のLLM Providerは`structured`をJSONパース等で埋める想定だが、
    このクラス自体はどのLLMにも依存しない。
    """

    text: str
    structured: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AIProvider(Protocol):
    """全AI呼び出し箇所が依存する、唯一の抽象契約。

    具体的な実装(MockProvider等)はこのProtocolを満たしさえすればよく、
    forge_ai/の他のモジュールは実装クラスを一切importしない
    (Dependency InjectionでAIProviderとして受け取るのみ)。
    """

    def complete(self, prompt: Prompt) -> ProviderResponse:
        """1つのPromptに対して1つの応答を返す。副作用(状態保持)を持たない
        ことを推奨する(会話履歴が必要な場合はPrompt.context側に含める)。"""
        ...
