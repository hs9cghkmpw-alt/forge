"""Impact Classification Benchmark Dataset
(FORGE-QUALITY-AI-INDEPENDENCE-003 Phase H・I、2026-08-12)。

指示書16章が「Local化の第一候補」として挙げたTaskのうち、
**Impact classification**の評価データセット。

このTaskを最初に選んだ理由(指示書16章):

* 入出力が小さい(発話1つ → key/impactの数件)。小さいローカル
  モデルでも現実的に狙える。
* Forgeの品質に直接効く(誤ると「質問攻め」か「聞かずに作る」に
  なる)。
* **正解が決まる**。「家族と共有するか」がhighで「ボタンの色」が
  cosmeticであることは、Forgeの製品方針として確定しており、
  評価者の主観に依存しない。

Planner・Schema Compilerを最初にLocal化しない(指示書16章)という
制約に従い、ここでは会話判断だけを対象にしている。
"""

from __future__ import annotations

from typing import Any

from app.ai.gateway.benchmark import BenchmarkCase

__all__ = ["IMPACT_SCHEMA", "build_impact_cases"]

IMPACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "impact": {"type": "string", "enum": ["blocking", "high", "low", "cosmetic"]},
        "reason": {"type": "string"},
    },
    "required": ["key", "impact", "reason"],
}

_PROMPT_TEMPLATE = """あなたはForgeという製品の会話エンジンの一部です。
ユーザーの困りごとに対して、まだ分かっていないことが1つあります。
その「分かっていないこと」が、作る道具の構造をどれだけ左右するかを
4段階で分類してください。

- "blocking": これが分からないと、そもそも何を作るか決まらない。
- "high": 答えによって道具の構造が大きく変わる(保存場所・権限など)。
- "low": 構造は変わらない。既定値で進めてよい。
- "cosmetic": 色・配置・ボタンの位置など見た目のこと。

**色・レイアウト・ボタンの位置・画面数は必ず "cosmetic" にすること。**

[ユーザーの困りごと] {need}
[分かっていないこと] {unknown}

JSONだけを返してください。"""


# (困りごと, 分かっていないこと, 期待するimpact)。
# 期待値はForgeの製品方針(指示書5章のQuestion Policy)そのものであり、
# 評価者の好みではない。
_CASES: tuple[tuple[str, str, str], ...] = (
    # cosmetic — 絶対に質問してはいけないもの
    ("買い物のメモを取りたい", "ボタンの色", "cosmetic"),
    ("仕事のTodoを管理したい", "削除ボタンを右に置くか左に置くか", "cosmetic"),
    ("読書記録をつけたい", "一覧の余白の広さ", "cosmetic"),
    ("家計簿をつけたい", "画面の配色", "cosmetic"),
    ("日記を書きたい", "文字の大きさ", "cosmetic"),
    # high — 構造が変わるので聞くべきもの
    ("予定を管理したい", "家族と共有するかどうか", "high"),
    ("買い物リストを作りたい", "家族も追加できるようにするか", "high"),
    ("持ち物を記録したい", "他の人にも見せるかどうか", "high"),
    ("薬を飲んだか記録したい", "決まった時間に通知が必要かどうか", "high"),
    ("経費を記録したい", "他の人に承認してもらう必要があるか", "high"),
    # blocking — これが無いと何も作れないもの
    ("何か管理したい", "何を記録したいのか", "blocking"),
    ("便利なものが欲しい", "どんな困りごとなのか", "blocking"),
    ("記録をつけたい", "何についての記録なのか", "blocking"),
    # low — 既定で進めてよいもの
    ("買い物メモを作りたい", "一覧の並び順", "low"),
    ("読書記録をつけたい", "1ページに何件表示するか", "low"),
    ("Todoを管理したい", "完了した項目を下に移動するか", "low"),
)


def build_impact_cases() -> list[BenchmarkCase]:
    """指示書19章の「同一Dataset」。Provider間で完全に同じものを使う。"""
    cases: list[BenchmarkCase] = []
    for need, unknown, expected in _CASES:
        cases.append(BenchmarkCase(
            name=f"{expected}:{unknown}",
            prompt=_PROMPT_TEMPLATE.format(need=need, unknown=unknown),
            response_schema=IMPACT_SCHEMA,
            required_keys=("key", "impact", "reason"),
            check=_make_check(expected),
        ))
    return cases


def _make_check(expected: str):
    def check(value: dict[str, Any]) -> bool:
        return str(value.get("impact", "")).strip().lower() == expected

    return check
