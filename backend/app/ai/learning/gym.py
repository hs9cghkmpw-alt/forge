"""Forge Training Gym — **本番データだけでAIを育てない**
(FORGE-020 §21、2026-08-25)。

---

## なぜ本番だけでは育たないのか

本番で来る Need は偏る。よく来るものは何度も学べるが、
**来なかったものは永久に学べない**。しかも本番データは

* 利用者の許諾が要る
* 個人情報が混ざりうる
* 失敗例が集まりにくい（利用者は途中でやめる）

Gym は Forge が自分で用意する課題集である。許諾も個人情報も関係ない。

## カテゴリ

| | 何を鍛えるか |
|---|---|
| `KNOWN` | 定番（calculator / todo / form） |
| `VARIATION` | 定番の条件違い |
| `COMPOSITION` | 掛け合わせ（家計簿 + ゲーム、学習 + 地図） |
| `REPAIR` | **壊れた状態から直す**（compile error / runtime bug） |
| `INTERACTIVE` | drag / realtime state / game loop |
| `NOVEL` | 専用 template が無い未知の組み合わせ |

## training と held-out を分ける

同じ課題で鍛えて同じ課題で測ると、**測っているのは暗記である**。
`split` を課題自身が持ち、`held_out` は training set から必ず外れる。

課題は versioned にする。課題を書き換えたのに同じ id のままだと、
昔の Benchmark と比べられなくなる（011 §3 の dataset identity と
同じ問題）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "GymTask",
    "TaskCategory",
    "TaskSplit",
    "TrainingGym",
    "default_training_gym",
]


class TaskCategory(str, Enum):
    KNOWN = "known"
    VARIATION = "variation"
    COMPOSITION = "composition"
    REPAIR = "repair"
    INTERACTIVE = "interactive"
    NOVEL = "novel"


class TaskSplit(str, Enum):
    TRAINING = "training"
    HELD_OUT = "held_out"
    """**鍛えるのに使わない。** 測るためだけ。"""


@dataclass(frozen=True)
class GymTask:
    """課題1つ。**versioned。**"""

    task_id: str
    category: TaskCategory
    split: TaskSplit
    need: str
    """課題文。**利用者の発話ではなく Forge が書いたもの**なので保存してよい。"""

    version: int = 1
    required_capabilities: tuple[str, ...] = ()
    """この課題を解くのに要る能力。**足りなければ `unsupported` と記録する**（§22）。"""

    expected_axes: tuple[str, ...] = ("validator", "build")
    notes: str = ""

    @property
    def identity(self) -> str:
        """課題の**中身の同一性**。書き換えたのに同じ id を名乗らせない。"""
        payload = json.dumps(
            {
                "task_id": self.task_id, "version": self.version,
                "category": self.category.value, "need": self.need,
                "required_capabilities": list(self.required_capabilities),
            },
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id, "version": self.version,
            "identity": self.identity, "category": self.category.value,
            "split": self.split.value, "need": self.need,
            "required_capabilities": list(self.required_capabilities),
            "expected_axes": list(self.expected_axes), "notes": self.notes,
        }


#: 最初の課題集。**専用 template を足して増やす類のものではない。**
_SEED_TASKS: tuple[GymTask, ...] = (
    GymTask("gym.known.todo", TaskCategory.KNOWN, TaskSplit.TRAINING,
            "やることを追加して、終わったら消せるリストが欲しい",
            required_capabilities=("record_list", "form")),
    GymTask("gym.known.expense", TaskCategory.KNOWN, TaskSplit.TRAINING,
            "毎日の支出を記録して合計を見たい",
            required_capabilities=("record_list", "metric")),
    GymTask("gym.known.contact_form", TaskCategory.KNOWN, TaskSplit.TRAINING,
            "問い合わせを受け取るフォームが欲しい",
            required_capabilities=("form", "validation")),
    GymTask("gym.variation.expense_by_category", TaskCategory.VARIATION,
            TaskSplit.TRAINING,
            "支出をカテゴリ別に分けて、月ごとの推移も見たい",
            required_capabilities=("record_list", "metric", "chart")),
    GymTask("gym.composition.study_map", TaskCategory.COMPOSITION,
            TaskSplit.TRAINING,
            "行った場所を地図に残しながら、その土地の言葉を覚えたい",
            required_capabilities=("record_list", "map", "quiz")),
    GymTask("gym.repair.broken_state_ref", TaskCategory.REPAIR, TaskSplit.TRAINING,
            "壊れた state 参照を直して、アプリが起動するようにする",
            required_capabilities=("diagnose", "patch")),
    GymTask("gym.repair.validation_failure", TaskCategory.REPAIR, TaskSplit.TRAINING,
            "Validator が落ちる Document を、意図を保ったまま通るように直す",
            required_capabilities=("diagnose", "patch")),
    GymTask("gym.interactive.drag_sort", TaskCategory.INTERACTIVE, TaskSplit.HELD_OUT,
            "並べ替えをドラッグでできるようにしたい",
            required_capabilities=("drag", "realtime_state")),
    GymTask("gym.novel.plant_sound", TaskCategory.NOVEL, TaskSplit.HELD_OUT,
            "植物を育てながら音を組み合わせるゲーム",
            required_capabilities=("game_loop", "audio", "realtime_state")),
    GymTask("gym.novel.walk_vocabulary", TaskCategory.NOVEL, TaskSplit.HELD_OUT,
            "街を歩きながら英単語を覚える",
            required_capabilities=("location", "quiz", "persistence")),
    GymTask("gym.novel.fish_puzzle", TaskCategory.NOVEL, TaskSplit.HELD_OUT,
            "釣った魚でパズル対戦する",
            required_capabilities=("game_loop", "grid_interaction", "matching_rule")),
)


@dataclass
class TrainingGym:
    """課題集。**training と held-out を混ぜない。**"""

    tasks: tuple[GymTask, ...] = field(default_factory=lambda: _SEED_TASKS)

    def for_split(self, split: TaskSplit) -> tuple[GymTask, ...]:
        return tuple(t for t in self.tasks if t.split is split)

    def for_category(self, category: TaskCategory) -> tuple[GymTask, ...]:
        return tuple(t for t in self.tasks if t.category is category)

    def get(self, task_id: str) -> GymTask | None:
        return next((t for t in self.tasks if t.task_id == task_id), None)

    def held_out_ids(self) -> frozenset[str]:
        return frozenset(t.task_id for t in self.for_split(TaskSplit.HELD_OUT))

    def assert_disjoint(self) -> None:
        """**同じ課題が両方に居ないこと。** 居たら測っているのは暗記である。"""
        training = {t.task_id for t in self.for_split(TaskSplit.TRAINING)}
        overlap = training & self.held_out_ids()
        if overlap:
            msg = f"training と held-out が重なっている: {sorted(overlap)}"
            raise ValueError(msg)


_DEFAULT_GYM = TrainingGym()


def default_training_gym() -> TrainingGym:
    return _DEFAULT_GYM
