"""Generation Episode — **一仕事の軌跡**（FORGE-020 §18、2026-08-25）。

---

## なぜ完成物だけでは足りないか

Forge がこれまで残してきたのは `GenerationRecord` / `RevisionRecord`
——「何ができたか」である。しかし Local AI を育てるのに要るのは

* **何を知らなかったか**
* 何を調べたか / どの資料を使ったか / 何を捨てたか
* どの道具を使ったか
* どこで落ちたか / どう診断したか / どう直したか

という**過程**である。完成 Document を何千個集めても、
「詰まったとき何をすればよいか」は学べない。

## 生の会話を溜め込まない

`raw conversation` を無差別に保存しない（§18 / 006 §22）。
Episode が持つのは**識別子と分類と結果**である。

| 持つ | 持たない |
|---|---|
| 使った道具の名前と結果 | 道具へ渡した本文そのもの |
| 参照した Knowledge の id | 参照した本文 |
| Web 出典の URL / domain | ページ本文 |
| build / test / runtime の結果 | 利用者の発話 |

## 収集してよいことと、学習に使ってよいことは別

`provenance` と `training_use` を分けて持つ（§40）。
`UNKNOWN` は**学習の重みを持たない**——分からないものを
「使ってよい」へ倒さない（`CLAUDE.md` §3）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from app.ai.gateway.learning_events import (
    Deployment,
    LearningDataProvenance,
    TrainingUse,
)

__all__ = [
    "EpisodeOutcome",
    "EpisodeStep",
    "EpisodeStore",
    "GenerationEpisode",
    "RepairRound",
    "StepKind",
    "VerificationOutcome",
    "default_episode_store",
]


class StepKind(str, Enum):
    """1手が**どの種類**か。"""

    UNDERSTAND = "understand"
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"
    TOOL_CALL = "tool_call"
    GENERATE = "generate"
    VALIDATE = "validate"
    BUILD = "build"
    TEST = "test"
    RUN = "run"
    VISUAL = "visual"
    DIAGNOSE = "diagnose"
    REPAIR = "repair"


class VerificationOutcome(str, Enum):
    """検証の結果。**「やっていない」と「通った」を混ぜない。**"""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    """該当しない（例: Runtime を持たない生成物）。"""

    UNSUPPORTED = "unsupported"
    """**Forge がまだその能力を持たない。** 正直に残す（§22）。"""

    UNKNOWN = "unknown"
    """**既定値。** 記録し損ねたものを `PASSED` へ倒さない。"""

    @property
    def is_evidence_of_success(self) -> bool:
        return self is VerificationOutcome.PASSED


class EpisodeOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    ABANDONED = "abandoned"
    """予算切れで諦めた（§24）。**失敗と区別する。**"""

    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EpisodeStep:
    """1手。**本文は持たない。**"""

    kind: StepKind
    name: str
    """道具名・段の名前など、**閉じた識別子**。"""

    succeeded: bool = False
    detail_code: str = ""
    """失敗の**分類**。例外メッセージそのものは入れない。"""

    references: tuple[str, ...] = ()
    """Knowledge id / URL / Evidence uid。**本文ではなく参照。**"""

    duration_ms: float = 0.0
    at: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value, "name": self.name,
            "succeeded": self.succeeded, "detail_code": self.detail_code,
            "references": list(self.references),
            "duration_ms": round(self.duration_ms, 2), "at": self.at,
        }


@dataclass(frozen=True)
class RepairRound:
    """1回の修正。**「何で落ちて、何をしたら通ったか」**（§28 の素材）。"""

    round_index: int
    failure_code: str
    """落ちた理由の分類（compile / validate / test / runtime / visual）。"""

    diagnosis_code: str = ""
    action: str = ""
    resolved: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "round_index": self.round_index, "failure_code": self.failure_code,
            "diagnosis_code": self.diagnosis_code, "action": self.action,
            "resolved": self.resolved,
        }


@dataclass
class GenerationEpisode:
    """一仕事ぶんの軌跡。"""

    episode_id: str = field(default_factory=lambda: uuid4().hex)
    task_id: str = ""
    """`TrainingGym` / `NovelBenchmark` の課題 id、または本番の task 種別。"""

    intent_reference: str = ""
    """**Need そのものではなく参照。** 生の発話を持たない。"""

    provider: str = ""
    model: str = ""
    deployment: Deployment = Deployment.UNKNOWN
    teacher_candidate: bool = False
    """Teacher として走らせた回か（§19）。**Truth ではない。**"""

    knowledge_references: tuple[str, ...] = ()
    retrieval_references: tuple[str, ...] = ()
    web_source_references: tuple[str, ...] = ()

    steps: tuple[EpisodeStep, ...] = ()
    repair_rounds: tuple[RepairRound, ...] = ()

    generation_evidence_uid: str = ""
    revision_evidence_uids: tuple[str, ...] = ()

    validator_outcome: VerificationOutcome = VerificationOutcome.UNKNOWN
    build_outcome: VerificationOutcome = VerificationOutcome.UNKNOWN
    test_outcome: VerificationOutcome = VerificationOutcome.UNKNOWN
    runtime_outcome: VerificationOutcome = VerificationOutcome.UNKNOWN
    visual_outcome: VerificationOutcome = VerificationOutcome.UNKNOWN

    final_outcome: EpisodeOutcome = EpisodeOutcome.UNKNOWN
    user_acceptance: str = "unknown"

    provenance: LearningDataProvenance = LearningDataProvenance.UNKNOWN
    training_use: TrainingUse = TrainingUse.UNKNOWN
    """**収集してよい ≠ 学習に使ってよい**（§40）。既定は `UNKNOWN`。"""

    started_at: float = 0.0
    finished_at: float = 0.0

    # -- 記録 -------------------------------------------------------------

    def record_step(self, step: EpisodeStep) -> None:
        self.steps = (*self.steps, step)

    def record_repair(self, repair: RepairRound) -> None:
        self.repair_rounds = (*self.repair_rounds, repair)

    # -- 判定 -------------------------------------------------------------

    @property
    def repair_succeeded(self) -> bool:
        """**落ちてから直して通った**か。§28 の最も価値ある対。"""
        return bool(self.repair_rounds) and self.repair_rounds[-1].resolved

    @property
    def verified_outcomes(self) -> dict[str, VerificationOutcome]:
        return {
            "validator": self.validator_outcome,
            "build": self.build_outcome,
            "test": self.test_outcome,
            "runtime": self.runtime_outcome,
            "visual": self.visual_outcome,
        }

    @property
    def has_usable_training_right(self) -> bool:
        """学習素材にしてよいか（**由来と権利の両方**）。

        `UNKNOWN` は通さない。「記録し忘れ」が「許諾済み」へ化ける
        向きに倒さない（`CLAUDE.md` §3）。
        """
        return (
            self.training_use is TrainingUse.ALLOWED
            and self.provenance is not LearningDataProvenance.UNKNOWN
        )

    def to_dict(self) -> dict[str, object]:
        """診断・Dataset 用。**本文が現れないことが不変条件である。**"""
        return {
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "intent_reference": self.intent_reference,
            "provider": self.provider,
            "model": self.model,
            "deployment": self.deployment.value,
            "teacher_candidate": self.teacher_candidate,
            "knowledge_references": list(self.knowledge_references),
            "retrieval_references": list(self.retrieval_references),
            "web_source_references": list(self.web_source_references),
            "steps": [s.to_dict() for s in self.steps],
            "repair_rounds": [r.to_dict() for r in self.repair_rounds],
            "generation_evidence_uid": self.generation_evidence_uid,
            "revision_evidence_uids": list(self.revision_evidence_uids),
            "outcomes": {k: v.value for k, v in self.verified_outcomes.items()},
            "final_outcome": self.final_outcome.value,
            "user_acceptance": self.user_acceptance,
            "provenance": self.provenance.value,
            "training_use": self.training_use.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class EpisodeStore:
    """Episode の保持。プロセス内メモリのみ（TD41）。

    **IN-MEMORY / NOT DURABLE.**
    """

    _MAX = 1000

    def __init__(self, *, now: object = time.time) -> None:
        self._episodes: dict[str, GenerationEpisode] = {}
        self._now = now

    def start(self, episode: GenerationEpisode) -> GenerationEpisode:
        if not episode.started_at:
            episode.started_at = float(self._now())
        self._episodes[episode.episode_id] = episode
        while len(self._episodes) > self._MAX:
            self._episodes.pop(next(iter(self._episodes)))
        return episode

    def finish(
        self, episode_id: str, outcome: EpisodeOutcome
    ) -> GenerationEpisode | None:
        episode = self._episodes.get(episode_id)
        if episode is None:
            return None
        episode.final_outcome = outcome
        episode.finished_at = float(self._now())
        return episode

    def get(self, episode_id: str) -> GenerationEpisode | None:
        return self._episodes.get(episode_id)

    def all_episodes(self) -> tuple[GenerationEpisode, ...]:
        return tuple(self._episodes.values())

    def for_task(self, task_id: str) -> tuple[GenerationEpisode, ...]:
        return tuple(e for e in self._episodes.values() if e.task_id == task_id)

    def reset(self) -> None:
        self._episodes.clear()

    def size(self) -> int:
        return len(self._episodes)


_DEFAULT_STORE = EpisodeStore()


def default_episode_store() -> EpisodeStore:
    return _DEFAULT_STORE
