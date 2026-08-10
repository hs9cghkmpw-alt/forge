"""LLMAdapter の Provider別スタブ(FORGE-MILESTONE-002 PHASE6)。

**Mock以外はすべて未実装。** `complete_structured()` は呼ばれると
`NotImplementedError`を投げる。目的は「型としてどのProviderも差し替え
可能である」ことを示すことであり、実際にAPIキーを使って外部サービスへ
接続する処理は一切含まない。

FORGE-MILESTONE-005 Task7で、`MockLLMAdapter`のみを実際に動作する
実装として追加した(指示書「実装するProviderはMockのみ」)。

将来これら(Mock以外)を実装する際に必要になる外部Dependency
(例: `openai`パッケージ、`google-generativeai`パッケージ等)は、
指示書「CEO承認が必要: 外部Dependency追加」に該当するため、
実装着手前に必ずCEO確認を取ること。
"""

from __future__ import annotations

import re
from typing import Any

from .interfaces import LLMAdapter


class _UnimplementedProvider:
    """全Providerスタブの共通基底。"""

    provider_name: str = "unimplemented"

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.provider_name} はまだ実装されていません(FORGE-MILESTONE-002 PHASE6は"
            f"インターフェース設計のみ)。実装するには外部Dependency追加のCEO承認が必要です。"
        )


class OpenAIProvider(_UnimplementedProvider):
    """OpenAI(GPT系)向けAdapterのスタブ。"""

    provider_name = "openai"


class ClaudeProvider(_UnimplementedProvider):
    """Anthropic Claude向けAdapterのスタブ。"""

    provider_name = "claude"


class GeminiProvider(_UnimplementedProvider):
    """Google Gemini向けAdapterのスタブ。"""

    provider_name = "gemini"


class OSSProvider(_UnimplementedProvider):
    """OSSモデル(Llama/Qwen/Mistral/Phi/Gemma等、Ollama等のローカル推論を想定)
    向けAdapterのスタブ。FORGE-MERGE-001 9章で検討したOllama連携は、
    実装時にこのクラスが受け皿になる想定。"""

    provider_name = "oss"


class ForgeAIProvider(_UnimplementedProvider):
    """将来の自作Forge専用AI向けAdapterのスタブ。FORGE-ARCH-001の最終目標
    (Forge専用モデル)がここに実装される想定。

    注記(FORGE-MILESTONE-005): この`provider_name = "forge_ai"`は
    Provider名としての`forge_ai`であり、Cognitive Engineとしての
    `forge_ai/`パッケージそのものとは別概念である
    (`docs/spec/ADAPTER_CONTRACT_V1.md` 4.0節、Engine/Provider分離)。
    """

    provider_name = "forge_ai"


_WORD_RE = re.compile(r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+")

# FORGE_v0.2_最終修正指示(Final Gate)P3対応で新設。
# `_flatten_prompt_to_string()`は`prompt.context`を`repr()`でそのまま
# 文字列化するため(`forge_ai_provider_bridge.py`参照)、この文字列には
# `{'plan': {'title': '...', 'screens': [...], ...}}`のような、Pythonの
# dict構文がそのまま現れる。このパターンで既存の`title`/`goal`/`purpose`
# キーの値を直接抜き出せる場合は、それを**そのまま再利用する**
# (キー名自体("title"・"screens"・"plan"等)が単語抽出に混入し、
# 「plan title x 買い物リストです screens」のような、内部表現が漏れた
# 破綻したタイトルになるバグを修正する。実際に発生することを確認した
# 上で修正した)。
_LABELED_VALUE_RE = re.compile(r"'(title|goal|purpose)':\s*'([^']*)'")


class MockLLMAdapter:
    """実際に動作する、唯一のProvider実装(FORGE-MILESTONE-005 Task7)。

    実LLMを一切呼ばない、決定的なMock実装。`ForgeAIProviderBridge`から
    `complete_structured(prompt: str, response_schema: dict) -> dict`
    として呼ばれることを想定する。

    設計方針: `response_schema["properties"]`に列挙されたフィールド名を
    見て、名前ベースの簡易ヒューリスティックで値を合成する
    (`forge_ai.provider.mock_provider.MockProvider`と同じ「決定的・
    キーワードベース」という思想を、フラットな文字列プロンプトの上で
    再現したもの。forge_ai/側のMockProviderを直接importして使い回すことは
    しない。Adapter層のみがforge_ai/へ依存する、というADR 7.3節の制約を
    守るため)。

    既知の制限: 単純な名前ベースヒューリスティックであり、本物の
    自然言語理解ではない。`docs/spec/ADAPTER_CONTRACT_V1.md`が要求する
    「Mockのみ実装」の範囲内での、決定的な代替実装である。
    """

    provider_name = "mock"

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        # [CONTEXT]セクション以降だけから単語を抽出する。[SYSTEM]/[INSTRUCTION]
        # は定型文であり、そこから単語を拾うと実際のユーザー入力・中間データとは
        # 無関係な語(定型文の単語)ばかりになってしまう(実際に実行して確認した、
        # 品質上の問題)。
        context_marker = "[CONTEXT]\n"
        idx = prompt.find(context_marker)
        relevant_text = prompt[idx + len(context_marker):] if idx != -1 else prompt

        words = tuple(dict.fromkeys(w.lower() for w in _WORD_RE.findall(relevant_text)))
        # 既にPlan/Intentが持っている`title`/`goal`/`purpose`をそのまま
        # 再利用できる場合の候補(P3対応、下記`_synthesize_field`参照)。
        labeled_values = {m.group(1): m.group(2) for m in _LABELED_VALUE_RE.finditer(relevant_text)}
        properties: dict[str, Any] = response_schema.get("properties", {})

        result: dict[str, Any] = {}
        for name, spec in properties.items():
            result[name] = self._synthesize_field(name, spec, words, prompt, labeled_values)
        return result

    def _synthesize_field(
        self,
        name: str,
        spec: dict[str, Any],
        words: tuple[str, ...],
        prompt: str,
        labeled_values: dict[str, str],
    ) -> Any:
        field_type = spec.get("type")

        if field_type == "array":
            # 既知のフィールド名ごとに、意味の近い単語だけへ絞り込む
            # (forge_ai.MockProviderの`_handle_meaning`と同じ発想:
            # 完全な自然言語理解はしないが、明らかに無関係な結果にはしない)。
            if name == "screens":
                # "screens"はオブジェクト(name/purpose/key_elements)の配列を
                # 期待される(forge_ai.core.planner.Planner.plan()参照)。
                # 単純な文字列リストを返すと`s.get("name", ...)`で例外になる
                # (実際に実行して確認した実バグ)。あえて空リストを返し、
                # forge_ai側が既に持つ「screensが空ならintentの概念から
                # 単一画面のデフォルトを組み立てる」というフォールバックへ
                # 委ねる(forge_ai/自身のロジックを信頼し、Mock側で
                # オブジェクト構造を再現しようとしない)。
                return []
            if name in ("mentioned_actions", "required_actions"):
                action_like = tuple(w for w in words if w.endswith(("する", "したい", "add", "track")))
                return list(action_like) or list(words[:3])
            return list(words[:5])

        if field_type == "integer":
            return 0

        if field_type == "object":
            return {}

        # デフォルトは文字列。フィールド名に応じて、多少意味のある値を返す。
        if name in ("goal", "title", "purpose"):
            # FORGE v0.2 Final Gate P3対応: 上流(Planner/Intent側)が既に
            # 決定した値がプロンプト内に存在する場合、それを**そのまま
            # 再利用する**(単語抽出で作り直さない)。これにより、
            # "compile" stageの"title"が"planning" stageで既に決定した
            # 妥当なtitleをそのまま維持できる(以前は単語抽出のやり直しで
            # 内部キー名が混入し破綻していた)。
            if name in labeled_values and labeled_values[name].strip():
                return labeled_values[name]
            return " ".join(words[:5]) if words else "mock_result"
        return "mock_result"


# 型チェック用の確認(実行時には意味を持たないが、各スタブが本当に
# LLMAdapter Protocolを満たす形になっているかを明示する)。
_PROVIDERS: tuple[LLMAdapter, ...] = (
    OpenAIProvider(),
    ClaudeProvider(),
    GeminiProvider(),
    OSSProvider(),
    ForgeAIProvider(),
    MockLLMAdapter(),
)
