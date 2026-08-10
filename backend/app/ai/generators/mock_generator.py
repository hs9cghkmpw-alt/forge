"""Deterministic Mock Generator v2(FORGE-MILESTONE-002 PHASE5)。

v1(FORGE-MERGE-001)との違い: 生成ロジックを「Category判定」と「Template実行」の
2層に分離した。Categoryは「どのTemplateを、どんなパラメータで呼ぶか」だけを
決め、実際の画面構造(Widget構成)はTemplate側(generators/templates/)が持つ。
新しいCategoryを追加する際、多くの場合Template自体は増やさず、
既存Templateへ渡すパラメータを増やすだけで済む(下記 CATEGORIES 参照)。

Python版・Dart版の互換性維持方針は docs/spec/MOCK_GENERATOR_CONTRACT.md 参照。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .templates.checklist_template import ChecklistTemplateParams, build_checklist_template
from .templates.form_template import FormQuestion, FormTemplateParams, build_form_template
from .templates.memo_template import MemoTemplateParams, build_memo_template


@dataclass(frozen=True)
class Category:
    keywords: tuple[str, ...]
    build: Callable[[], dict[str, Any]]


def _checklist(title: str, items: tuple[str, ...]) -> Callable[[], dict[str, Any]]:
    return lambda: build_checklist_template(ChecklistTemplateParams(title=title, items=items))


# 判定順が重要: 「子ども」「ペット」判定を「旅行」より先に置くことで、
# 「子どもの持ち物チェック」が「持ち物」キーワードにより誤って旅行カテゴリへ
# 分類されることを防いでいる(既存の回帰テストで固定済み)。
# 「メモ」は最も汎用的なキーワードのため、他の全カテゴリより後ろに置く。
#
# FORGE-MILESTONE-005: 元は`_CATEGORIES`(private)という名前だったが、
# `app.ai.native._04_generator`(Native AI v0のGenerator)が、この同じ
# カテゴリ別具体アイテムデータを再利用できるよう、公開名(`CATEGORIES`)へ
# 変更した。この変更は名前のみであり、`generate_forge_document()`の
# 挙動は一切変えていない(既存テストで無変更のまま合格することを確認済み)。
CATEGORIES: tuple[Category, ...] = (
    Category(("買い物", "スーパー", "食材", "shopping"),
              _checklist("買い物メモ", ("卵", "牛乳", "食パン", "野菜", "洗剤"))),
    Category(("todo", "タスク", "やること", "仕事"),
              _checklist("Todo", ("メールを返す", "資料を準備する", "打ち合わせに出る"))),
    Category(("ご飯", "晩ご飯", "夕食", "献立"),
              _checklist("今日のご飯メモ", ("主菜を決める", "副菜を決める", "足りない食材を確認する", "買い出しに行く"))),
    Category(("家計簿", "家計", "貯金", "支出"),
              _checklist("家計簿", ("今月の収入を記録する", "固定費を確認する", "今日の支出を記録する", "来月の予算を立てる"))),
    Category(("予定", "スケジュール", "schedule"),
              _checklist("今日の予定", ("午前のタスクを確認する", "午後のタスクを確認する", "夜までにやることを確認する"))),
    Category(("子ども", "こども", "子供"),
              _checklist("子どもの持ち物チェック", ("着替え", "オムツ", "水筒", "タオル", "お気に入りのおもちゃ"))),
    Category(("ペット", "pet"),
              _checklist("ペットのお世話チェック", ("ごはん", "お水の交換", "散歩", "トイレ掃除"))),
    Category(("プレゼント", "ギフト", "gift"),
              _checklist("プレゼントのアイデア", ("予算を決める", "候補を3つ挙げる", "相手の好みを思い出す"))),
    Category(("家事", "片付け", "そうじ", "掃除"),
              _checklist("今日の家事", ("掃除機をかける", "洗濯をする", "食器を洗う", "ゴミ出しをする"))),
    Category(("旅行", "持ち物", "パッキング", "出張"),
              _checklist("旅行の持ち物チェック", ("パスポート", "充電器", "着替え", "歯ブラシ", "常備薬"))),
    Category(
        ("アンケート", "survey", "満足度"),
        lambda: build_form_template(FormTemplateParams(
            title="満足度アンケート",
            questions=(
                FormQuestion(key="q_satisfied", label="今回のサービスに満足しましたか", kind="checkbox"),
                FormQuestion(key="q_recommend", label="友人に勧めたいと思いますか", kind="checkbox"),
                FormQuestion(key="q_comment", label="ご意見・ご感想（任意）", kind="text"),
            ),
        )),
    ),
    Category(("メモ", "memo", "ノート"),
              lambda: build_memo_template(MemoTemplateParams(title="メモ"))),
)


def generate_forge_document(raw_input: str) -> dict[str, Any]:
    """ユーザーの自然言語入力から、Forge Language準拠の文書(dict)を1件生成する。

    戻り値のversionはTemplateごとに異なる(1.0または1.1)。呼び出し側は
    必ずvalidate_forge_document()で検証してから使うこと(v1と同じ運用方針)。
    """
    text = raw_input.strip()
    lower = text.lower()

    builder = _match_category(lower)
    if builder is not None:
        return builder()

    title = text if text else "新しいリスト"
    return build_checklist_template(ChecklistTemplateParams(title=title, items=("最初のアイテム",)))


def _match_category(lower_text: str) -> Callable[[], dict[str, Any]] | None:
    for category in CATEGORIES:
        if any(keyword in lower_text for keyword in category.keywords):
            return category.build
    return None
