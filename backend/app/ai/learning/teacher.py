"""Teacher AI — **強いAIを「正解」にしない**（FORGE-020 §19・§20、2026-08-25）。

---

## Teacher output = Truth は禁止

Cloud の強い Model の出力をそのまま正解として Local に真似させると、
Forge が測っているのは「Cloud にどれだけ似ているか」になる。
それは Product の品質ではない。実際、Cloud が失敗して Local が成功する
場合もある——そのとき Local を悪い側に置いたら学習が逆へ進む。

## 同じ物差しへ通す

```
Task ──┬─ Teacher（Cloud / Open） ─┐
       └─ Local                    ├→ 同じ Evaluator → 比較
                                   ┘
```

Evaluator は Forge のものである。Validator / Build / Tests / Runtime /
Visual / Security / Intent fit / Latency。**どちらが書いたかを見ない。**

## Trajectory は「外から見えるもの」だけ

教師として価値があるのは完成物だけではない——いつ調べ、何を検索し、
どの資料を使い、何を捨て、どの道具を使い、何で失敗し、どう直したか。

ただし **Cloud Provider の内部 chain-of-thought は取得も保存もしない**
（§19）。記録するのは Tool / Action / Evidence という**外から観測可能な
事実**だけである。`GenerationEpisode` がその形をしている。

## Provider を誤帰属しない

019B で `revision_provider` を直した理由がここでも効く。「誰が作ったか」
が混ざると、Local と Cloud の比較そのものが壊れる。
`TeacherCandidate` は **Provider Registry の Provider をそのまま指す**
——Teacher 専用の並行 Router を作らない（§20）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.ai.gateway.learning_events import Deployment
from app.ai.learning.episode import GenerationEpisode, VerificationOutcome

__all__ = [
    "ComparisonVerdict",
    "EvaluationAxis",
    "EvaluationScore",
    "TeacherCandidate",
    "TeacherComparison",
    "evaluate_episode",
]


class EvaluationAxis(str, Enum):
    """**どちらが書いたかを見ない**物差し。"""

    VALIDATOR = "validator"
    BUILD = "build"
    TESTS = "tests"
    RUNTIME = "runtime"
    VISUAL = "visual"
    SECURITY = "security"
    INTENT_FIT = "intent_fit"
    USER_FEEDBACK = "user_feedback"
    EFFICIENCY = "efficiency"


@dataclass(frozen=True)
class EvaluationScore:
    """1回の生成の評価。**未検証を得点にしない。**"""

    axes: dict[EvaluationAxis, VerificationOutcome] = field(default_factory=dict)
    latency_ms: float = 0.0
    tool_calls: int = 0

    @property
    def passed_axes(self) -> int:
        return sum(1 for v in self.axes.values() if v.is_evidence_of_success)

    @property
    def failed_axes(self) -> int:
        return sum(1 for v in self.axes.values() if v is VerificationOutcome.FAILED)

    @property
    def unverified_axes(self) -> int:
        """**測っていない軸の数。** 多いほど、この比較の言えることは少ない。"""
        return sum(
            1 for v in self.axes.values()
            if v in {VerificationOutcome.UNKNOWN, VerificationOutcome.UNSUPPORTED}
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "axes": {k.value: v.value for k, v in self.axes.items()},
            "passed": self.passed_axes, "failed": self.failed_axes,
            "unverified": self.unverified_axes,
            "latency_ms": round(self.latency_ms, 2), "tool_calls": self.tool_calls,
        }


def evaluate_episode(episode: GenerationEpisode) -> EvaluationScore:
    """Episode を物差しへ通す。**Provider 名を見ない。**"""
    axes = {
        EvaluationAxis.VALIDATOR: episode.validator_outcome,
        EvaluationAxis.BUILD: episode.build_outcome,
        EvaluationAxis.TESTS: episode.test_outcome,
        EvaluationAxis.RUNTIME: episode.runtime_outcome,
        EvaluationAxis.VISUAL: episode.visual_outcome,
    }
    latency = max(0.0, (episode.finished_at - episode.started_at) * 1000.0)
    tool_calls = sum(1 for s in episode.steps if s.kind.value == "tool_call")
    return EvaluationScore(axes=axes, latency_ms=latency, tool_calls=tool_calls)


@dataclass(frozen=True)
class TeacherCandidate:
    """教師「候補」。**正解ではない。**

    既存の Provider をそのまま指す（§20）。Teacher 専用の並行 Router を
    作らない——作れば Provider 名の帰属が2系統になり、比較が壊れる。
    """

    provider: str
    model: str
    deployment: Deployment = Deployment.UNKNOWN
    teacher_candidate: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider, "model": self.model,
            "deployment": self.deployment.value,
            "teacher_candidate": self.teacher_candidate,
        }


class ComparisonVerdict(str, Enum):
    """比較の結論。"""

    LOCAL_BETTER = "local_better"
    TEACHER_BETTER = "teacher_better"
    EQUIVALENT = "equivalent"
    INCONCLUSIVE = "inconclusive"
    """**測れていない軸が多すぎる。** 「引き分け」と区別する。"""


@dataclass(frozen=True)
class TeacherComparison:
    """同じ Task を、同じ物差しで測った結果。"""

    task_id: str
    teacher: TeacherCandidate
    teacher_score: EvaluationScore
    local_provider: str
    local_score: EvaluationScore
    teacher_episode_id: str = ""
    local_episode_id: str = ""

    #: 結論を出すのに最低限必要な、両者で測れている軸の数。
    _MIN_COMPARABLE_AXES = 2

    @property
    def comparable_axes(self) -> int:
        """**両方で測れている軸**だけを数える。"""
        return sum(
            1 for axis in self.teacher_score.axes
            if self.teacher_score.axes[axis] not in {
                VerificationOutcome.UNKNOWN, VerificationOutcome.UNSUPPORTED,
            }
            and self.local_score.axes.get(axis) not in {
                None, VerificationOutcome.UNKNOWN, VerificationOutcome.UNSUPPORTED,
            }
        )

    @property
    def verdict(self) -> ComparisonVerdict:
        """**Teacher が上、を既定にしない。**

        測れている軸が少なければ `INCONCLUSIVE`。分からないものを
        「Teacher が正しい」へ倒すのは、Teacher = Truth と同じである。
        """
        if self.comparable_axes < self._MIN_COMPARABLE_AXES:
            return ComparisonVerdict.INCONCLUSIVE
        local = self.local_score.passed_axes
        teacher = self.teacher_score.passed_axes
        if local > teacher:
            return ComparisonVerdict.LOCAL_BETTER
        if teacher > local:
            return ComparisonVerdict.TEACHER_BETTER
        return ComparisonVerdict.EQUIVALENT

    @property
    def local_wins_where_teacher_failed(self) -> bool:
        """**Teacher が落ちて Local が通った軸**が在るか（§28 の対）。"""
        return any(
            self.teacher_score.axes.get(axis) is VerificationOutcome.FAILED
            and self.local_score.axes.get(axis) is VerificationOutcome.PASSED
            for axis in self.teacher_score.axes
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "teacher": self.teacher.to_dict(),
            "teacher_score": self.teacher_score.to_dict(),
            "local_provider": self.local_provider,
            "local_score": self.local_score.to_dict(),
            "comparable_axes": self.comparable_axes,
            "verdict": self.verdict.value,
            "local_wins_where_teacher_failed": self.local_wins_where_teacher_failed,
            "teacher_episode_id": self.teacher_episode_id,
            "local_episode_id": self.local_episode_id,
        }
