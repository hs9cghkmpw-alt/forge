"""Forge Native AI v0 — Intent Recognizer(`_01_intent`)。

自然文からIntentIR(`app.ai.foundation.interfaces.IntentIR`、
FORGE-MILESTONE-004で拡張済み)を構築する、**実際に動作する**
ルールベースの実装。推論(LLM呼び出し)は一切行わない
(指示書10章「Rule Based Engine」の実装)。

## 既存資産との関係

キーワード判定ロジックは、`app.ai.generators.mock_generator`の
`_CATEGORIES`(9〜12カテゴリ、実績のある判定順序)を土台にしている。
`mock_generator.py`自体は変更していない(指示書15章「Mock Generator削除禁止」
「MockはFallbackとして維持」に対応。Native AI v0はMock Generatorを
**置き換える**が、削除はしない)。

このモジュールは、Mock Generatorと同じキーワード集合を使いながら、
単に「どのTemplateを呼ぶか」だけでなく、IntentIRの全フィールド
(goal・entities・category・output_type・complexity等)を埋める。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.foundation.interfaces import Complexity, IntentIR, Platform


@dataclass(frozen=True)
class CategoryDefinition:
    """1カテゴリの判定ルールとIntentIRへの写像情報。"""

    name: str  # 英語識別子(例: "shopping")
    keywords: tuple[str, ...]
    goal_template: str  # 例: "買い物リストを管理する"
    entities: tuple[str, ...]  # 例: ("item", "price")
    output_type: str  # "checklist" | "memo" | "form"
    complexity: Complexity = Complexity.SIMPLE


# 判定順序はmock_generator.pyの_CATEGORIESと完全に一致させている
# (「子ども」「ペット」を「旅行」より先に判定する等、既存の衝突回避ルールを
# そのまま踏襲する)。
CATEGORY_DEFINITIONS: tuple[CategoryDefinition, ...] = (
    CategoryDefinition(
        name="shopping", keywords=("買い物", "スーパー", "食材", "shopping"),
        goal_template="買い物リストを管理する", entities=("item", "price", "store"),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="todo", keywords=("todo", "タスク", "やること", "仕事"),
        goal_template="タスクを管理する", entities=("task", "deadline"),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="meal", keywords=("ご飯", "晩ご飯", "夕食", "献立"),
        goal_template="今日の食事を計画する", entities=("dish", "ingredient"),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="budget", keywords=("家計簿", "家計", "貯金", "支出"),
        goal_template="家計を記録・管理する", entities=("income", "expense"),
        output_type="checklist", complexity=Complexity.MEDIUM,
    ),
    CategoryDefinition(
        name="schedule", keywords=("予定", "スケジュール", "schedule"),
        goal_template="今日の予定を管理する", entities=("task", "time"),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="child", keywords=("子ども", "こども", "子供"),
        goal_template="子どもの持ち物を管理する", entities=("item",),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="pet", keywords=("ペット", "pet"),
        goal_template="ペットの世話を管理する", entities=("task",),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="gift", keywords=("プレゼント", "ギフト", "gift"),
        goal_template="プレゼントのアイデアを管理する", entities=("idea", "budget"),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="household", keywords=("家事", "片付け", "そうじ", "掃除"),
        goal_template="家事を管理する", entities=("task",),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="travel", keywords=("旅行", "持ち物", "パッキング", "出張"),
        goal_template="旅行の持ち物を管理する", entities=("item",),
        output_type="checklist",
    ),
    CategoryDefinition(
        name="survey", keywords=("アンケート", "survey", "満足度"),
        goal_template="満足度調査を実施する", entities=("question", "response"),
        output_type="form", complexity=Complexity.MEDIUM,
    ),
    CategoryDefinition(
        name="diary", keywords=("日記", "diary", "振り返り"),
        goal_template="日々の記録を残す", entities=("entry", "date"),
        output_type="memo",
    ),
    CategoryDefinition(
        name="memo", keywords=("メモ", "memo", "ノート"),
        goal_template="自由にメモを残す", entities=("note",),
        output_type="memo",
    ),
)

_UNKNOWN_CATEGORY = CategoryDefinition(
    name="generic", keywords=(), goal_template="リストを管理する",
    entities=("item",), output_type="checklist",
)


class IntentRecognizer:
    """自然文からIntentIRを構築する。ルールベースであり、LLM呼び出しを
    一切行わない(`app.ai.runtime.intent_parser.IntentParser` Protocolと
    構造的に互換だが、Stubではなく実装済みである点が異なる)。
    """

    def recognize(self, natural_language_input: str, conversation_history: tuple[str, ...] = ()) -> IntentIR:
        """natural_language_inputからIntentIRを構築する。未知の入力でも
        必ず何らかのIntentIR(genericカテゴリ)を返し、例外を投げない。"""
        text = natural_language_input.strip()
        lowered = text.lower()
        category_def = self._match_category(lowered) or _UNKNOWN_CATEGORY

        return IntentIR(
            purpose=category_def.goal_template if category_def is not _UNKNOWN_CATEGORY else (text or "リストを管理する"),
            required_features=(category_def.output_type,),
            entities=category_def.entities,
            platform=Platform.CROSS_PLATFORM,
            complexity=category_def.complexity,
            category=category_def.name,
            output_type=category_def.output_type,
        )

    def _match_category(self, lowered_text: str) -> CategoryDefinition | None:
        for category_def in CATEGORY_DEFINITIONS:
            if any(keyword in lowered_text for keyword in category_def.keywords):
                return category_def
        return None
