"""Prompt Builder。

キックオフ指示書7章: 「Promptは Builder経由のみ生成。文字列連結は禁止。」

`Prompt`は単一の巨大文字列ではなく、`system`/`instruction`/`context`という
明確に分離されたフィールドを持つ構造化データである。各Providerの実装が
最終的にLLM APIへ渡す形式(1本の文字列、role配列など)へ変換する責務を負う。
forge_ai/のどのモジュールも、prompt文字列を`+`やf-stringで組み立てない
(`PromptBuilder`のメソッド経由でのみ`Prompt`を得る)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Prompt:
    """1回のAI呼び出しに対応する、構造化されたプロンプト。

    system: このAI呼び出しの役割・制約(常に一定のルールを表す)。
    instruction: 今回何をしてほしいかの指示。
    context: 参照データ(World/Meaning/Intent等)。呼び出し先が必要に応じて
        参照する構造化データであり、文字列へ事前結合しない。
    """

    stage: str  # "meaning" | "intent" | "planning" | "compile" | "repair"
    system: str
    instruction: str
    context: dict[str, Any] = field(default_factory=dict)


class PromptBuilder:
    """全Prompt生成の唯一の入口。個々のstageごとに専用メソッドを持つ。"""

    def build_meaning_prompt(self, *, user_text: str, domain_name: str) -> Prompt:
        """Meaning抽出段階のPromptを構築する。"""
        return Prompt(
            stage="meaning",
            system=(
                "あなたはユーザーの自然文から、対象領域(Domain)に関連する"
                "概念・行為・キーワードを抽出する。Worldを直接変更してはならない。"
            ),
            instruction="次のユーザー発話から意味を抽出せよ。",
            context={"user_text": user_text, "domain_name": domain_name},
        )

    def build_intent_prompt(self, *, meaning_summary: dict[str, Any], domain_name: str) -> Prompt:
        """Intent構築段階のPromptを構築する。"""
        return Prompt(
            stage="intent",
            system=(
                "あなたは抽出された意味(Meaning)を、Forgeが処理可能な"
                "Intent構造(目的・必要概念・必要操作・制約)へ変換する。"
            ),
            instruction="次のMeaningからIntentを構築せよ。",
            context={"meaning": meaning_summary, "domain_name": domain_name},
        )

    def build_planning_prompt(self, *, intent_summary: dict[str, Any]) -> Prompt:
        """Application Plan生成段階のPromptを構築する。"""
        return Prompt(
            stage="planning",
            system=(
                "あなたはIntentからApplication Planを設計する。"
                "Runtime(Widget種別・UIフレームワーク)を一切知らない前提で、"
                "画面構成と目的だけを抽象的に記述せよ。"
            ),
            instruction="次のIntentからApplication Planを生成せよ。",
            context={"intent": intent_summary},
        )

    def build_compile_prompt(self, *, plan_summary: dict[str, Any]) -> Prompt:
        """Forge IRコンパイル段階のPromptを構築する。"""
        return Prompt(
            stage="compile",
            system=(
                "あなたはApplication PlanをForge IR(構造化された中間表現)へ"
                "変換する。ForgeのWidget/Action/State語彙のみを使うこと。"
            ),
            instruction="次のApplication PlanをForge IRへコンパイルせよ。",
            context={"plan": plan_summary},
        )

    def build_repair_prompt(self, *, ir_summary: dict[str, Any], issues: tuple[dict[str, Any], ...]) -> Prompt:
        """Repair段階のPromptを構築する。"""
        return Prompt(
            stage="repair",
            system="あなたはForge IRの検証エラーを最小差分で修正する。",
            instruction="次のIRと検証エラー一覧をもとに、修正方針を示せ。",
            context={"ir": ir_summary, "issues": list(issues)},
        )
