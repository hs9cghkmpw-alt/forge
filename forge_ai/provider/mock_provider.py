"""Mock Provider。

`AIProvider` Protocolを満たす、決定的でLLMを一切呼ばない実装。
キックオフ指示書3章「全機能がMock Providerで動作すること」
「Providerが存在しなくても全Unit Testが通ること」に対応する
唯一の同梱Provider実装。

設計方針: stageごとに、そのstageで期待される`structured`出力の"形"を
決定的なルールで埋める。実際のLLMのように自由な文章を生成するのではなく、
Prompt.context に含まれる情報から、後続モジュールが必要とする最小限の
構造化データを機械的に組み立てる。
"""

from __future__ import annotations

from typing import Any

from forge_ai.prompt.prompt_builder import Prompt
from forge_ai.provider.provider_interface import ProviderResponse


class MockProvider:
    """`AIProvider` Protocolの決定的な実装。テスト・開発専用。"""

    def complete(self, prompt: Prompt) -> ProviderResponse:
        """Prompt.stageに応じたハンドラへ振り分け、決定的な応答を返す。"""
        handler = _STAGE_HANDLERS.get(prompt.stage, _handle_unknown_stage)
        return handler(prompt)


def _handle_meaning(prompt: Prompt) -> ProviderResponse:
    """meaning stageの決定的処理: 空白区切りでトークン化するのみ。"""
    # 既知の制限: 単純な空白区切りトークナイズであり、分かち書きされていない
    # 日本語文(例: 「買い物リストを記録したい」)は1トークンとして扱われる。
    # 実際の形態素解析はforge_ai/の対象外(Mockは決定的な簡易実装であることを
    # 意図しており、本物のNLPの代替ではない)。IMPLEMENTATION_REPORT.mdにも
    # 既知の制限として明記する。
    text: str = prompt.context.get("user_text", "")
    lowered = text.lower()
    words = [w.strip(".,!?、。") for w in lowered.replace("　", " ").split() if w.strip(".,!?、。")]
    return ProviderResponse(
        text=f"'{text}' から {len(words)} 個のキーワード候補を抽出しました。",
        structured={
            "mentioned_concepts": tuple(dict.fromkeys(words)),
            "mentioned_actions": tuple(w for w in words if w.endswith(("する", "したい", "add", "track"))),
            "keywords": tuple(dict.fromkeys(words)),
        },
    )


def _handle_intent(prompt: Prompt) -> ProviderResponse:
    """intent stageの決定的処理: meaningの概念・行為をそのままIntentへ写す。"""
    meaning: dict[str, Any] = prompt.context.get("meaning", {})
    domain_name: str = prompt.context.get("domain_name", "generic")
    concepts = tuple(meaning.get("mentioned_concepts", ()))
    actions = tuple(meaning.get("mentioned_actions", ())) or ("add_item",)
    return ProviderResponse(
        text=f"{domain_name}領域のIntentを構築しました。",
        structured={
            "goal": f"{domain_name}に関する記録・管理を行う",
            "required_concepts": concepts,
            "required_actions": actions,
            "constraints": (),
        },
    )


def _handle_planning(prompt: Prompt) -> ProviderResponse:
    """planning stageの決定的処理: 単一画面のApplication Planを組み立てる。"""
    intent: dict[str, Any] = prompt.context.get("intent", {})
    concepts = tuple(intent.get("required_concepts", ())) or ("item",)
    return ProviderResponse(
        text="Application Planを構築しました。",
        structured={
            "title": str(intent.get("goal", "新しいアプリ")),
            "screens": (
                {
                    "name": "main",
                    "purpose": "主要な記録・一覧を表示する",
                    "key_elements": concepts,
                },
            ),
            "data_entities": concepts,
            "primary_flow": ("入力する", "一覧を確認する"),
        },
    )


def _handle_compile(prompt: Prompt) -> ProviderResponse:
    """compile stageの決定的処理: titleの決定のみ担当する
    (画面構造そのものはCompiler側の決定的Pythonロジックが担う)。"""
    plan: dict[str, Any] = prompt.context.get("plan", {})
    return ProviderResponse(
        text="Application PlanをForge IRへコンパイルする方針を決定しました。",
        structured={"title": plan.get("title", "新しいアプリ")},
    )


def _handle_repair(prompt: Prompt) -> ProviderResponse:
    """repair stageの決定的処理: 件数を集計して返すのみ
    (実際の修正はRepairEngine側の決定的Pythonロジックが担う)。"""
    issues: list[dict[str, Any]] = list(prompt.context.get("issues", []))
    return ProviderResponse(
        text=f"{len(issues)}件の問題に対する修正方針を決定しました。",
        structured={"addressed_issue_count": len(issues)},
    )


def _handle_unknown_stage(prompt: Prompt) -> ProviderResponse:
    """未知のstage名を渡された場合の安全なフォールバック(クラッシュしない)。"""
    return ProviderResponse(text=f"未知のstage '{prompt.stage}' です。", structured={})


_STAGE_HANDLERS = {
    "meaning": _handle_meaning,
    "intent": _handle_intent,
    "planning": _handle_planning,
    "compile": _handle_compile,
    "repair": _handle_repair,
}
