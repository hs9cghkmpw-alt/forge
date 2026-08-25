"""Dataset Builder — **Episode から学習候補を作る**
(FORGE-020 §27・§28、2026-08-25)。

---

## 品質Gateを全部通ったものだけ

1つでも欠けたら候補にしない。「だいたい満たしている」で通すと、
**何が理由で入ったのか**が後から分からなくなる
（`LocalPromotionGate` と同じ姿勢、017A §7）。

| Gate | 落とすもの |
|---|---|
| provenance known | 由来を記録し忘れたもの |
| training right allowed | 収集はしてよいが学習はだめなもの |
| validator pass | Forge Language として壊れているもの |
| build/test evidence | 動く証拠が無いもの |
| runtime evidence | Runtime を持つのに測っていないもの |
| no secret | 秘密が混ざったもの |
| dedup | 同じもの |
| poison / anomaly | 異常なもの |

## `UNKNOWN` / Mock / TEST_DOUBLE を正例にしない

Mock の出力を教師にすると**Mockの癖を学ぶ**。テストは `mock` Provider で
大量に走るので、放っておくと実運用よりテストの方が正例を多く生む
（017A §1 で `RevisionRecord` に対して塞いだのと同じ穴）。

**Cloud Teacher も同じ Gate を通す。** 強いAIの出力だからという理由で
Gate を抜けさせない（§19）。

## Preference pair

「良い/悪い」の対にしてよいのは、**何が正しいか分かっている**場合だけ。

```
✅  Local BAD → repair GOOD          直したら通った
✅  Teacher BAD → Local GOOD         同じ物差しで Local が勝った
✅  CORRECTED before → ACCEPTED after 利用者が直して受け入れた
✅  compile FAIL → repaired PASS
✅  visual FAIL → repaired PASS

❌  「違う」と言われただけ            何が正しいかは分かっていない
```

最後が要点である。否定だけを根拠に「別のものが正しい」と決めると、
**Forge の思い込みを正例として学習する**。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum

from app.ai.gateway.learning_events import LearningDataProvenance, TrainingUse
from app.ai.learning.episode import (
    EpisodeOutcome,
    GenerationEpisode,
    VerificationOutcome,
)
from app.ai.learning.teacher import ComparisonVerdict, TeacherComparison

__all__ = [
    "DatasetCandidate",
    "DatasetRejection",
    "PreferencePair",
    "PreferenceReason",
    "build_dataset_candidates",
    "build_preference_pairs",
    "evaluate_episode_for_dataset",
]


class DatasetRejection(str, Enum):
    """候補にしなかった理由。**「だめ」だけ返さない。**"""

    PROVENANCE_UNKNOWN = "provenance_unknown"
    TRAINING_RIGHT_MISSING = "training_right_missing"
    NOT_USABLE_PROVENANCE = "not_usable_provenance"
    """Mock / TEST_DOUBLE / 未検証の出所。"""

    VALIDATOR_NOT_PASSED = "validator_not_passed"
    NO_BUILD_EVIDENCE = "no_build_evidence"
    NO_TEST_EVIDENCE = "no_test_evidence"
    RUNTIME_FAILED = "runtime_failed"
    OUTCOME_NOT_SUCCESSFUL = "outcome_not_successful"
    DUPLICATE = "duplicate"
    ANOMALOUS = "anomalous"


#: 学習に使ってよい出所。**ここに無いものは正例にしない。**
#:
#: `TEST_DOUBLE` を外してあるのが要点である——Mock の出力を教師にすると
#: **Mock の癖を学ぶ**。テストは `mock` Provider で大量に走るので、
#: 放っておくと実運用よりテストの方が正例を多く生む（017A §1 で
#: `RevisionRecord` に対して塞いだのと同じ穴）。
#:
#: `UNKNOWN` も当然外す（`CLAUDE.md` §3）。
_USABLE_PROVENANCE: frozenset[LearningDataProvenance] = frozenset({
    LearningDataProvenance.CURATED,
    LearningDataProvenance.LOCAL_AI_OUTPUT,
    LearningDataProvenance.CLOUD_AI_OUTPUT,
    LearningDataProvenance.USER_EXPLICIT_FEEDBACK,
    LearningDataProvenance.USER_CORRECTION,
    LearningDataProvenance.DETERMINISTIC_RUNTIME,
})

#: 1 Episode が持ってよい手数の上限。**極端なものは異常として弾く。**
_MAX_REASONABLE_STEPS = 500


@dataclass(frozen=True)
class DatasetCandidate:
    """学習素材の候補1件。**本文は持たない——参照だけ。**"""

    candidate_id: str
    episode_id: str
    task_id: str
    provider: str
    model: str
    provenance: LearningDataProvenance
    training_use: TrainingUse
    generation_evidence_uid: str = ""
    revision_evidence_uids: tuple[str, ...] = ()
    content_identity: str = ""
    """重複判定用。**中身ではなく指紋。**"""

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id, "episode_id": self.episode_id,
            "task_id": self.task_id, "provider": self.provider, "model": self.model,
            "provenance": self.provenance.value, "training_use": self.training_use.value,
            "generation_evidence_uid": self.generation_evidence_uid,
            "revision_evidence_uids": list(self.revision_evidence_uids),
            "content_identity": self.content_identity,
        }


def _content_identity(episode: GenerationEpisode) -> str:
    """同じ生成を2度数えないための指紋。"""
    parts = "|".join((
        episode.task_id, episode.provider, episode.model,
        episode.generation_evidence_uid, *sorted(episode.revision_evidence_uids),
    ))
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:16]


def evaluate_episode_for_dataset(
    episode: GenerationEpisode, *, seen: frozenset[str] = frozenset()
) -> tuple[DatasetCandidate | None, tuple[DatasetRejection, ...]]:
    """1件を Gate へ通す。**全部通らなければ候補にしない。**"""
    reasons: list[DatasetRejection] = []

    if episode.provenance is LearningDataProvenance.UNKNOWN:
        reasons.append(DatasetRejection.PROVENANCE_UNKNOWN)
    elif episode.provenance not in _USABLE_PROVENANCE:
        # Mock / TEST_DOUBLE / 未検証の出所。**Cloud Teacher も同じ。**
        reasons.append(DatasetRejection.NOT_USABLE_PROVENANCE)

    if episode.training_use is not TrainingUse.ALLOWED:
        reasons.append(DatasetRejection.TRAINING_RIGHT_MISSING)

    if episode.validator_outcome is not VerificationOutcome.PASSED:
        reasons.append(DatasetRejection.VALIDATOR_NOT_PASSED)
    if episode.build_outcome is not VerificationOutcome.PASSED:
        reasons.append(DatasetRejection.NO_BUILD_EVIDENCE)
    if episode.test_outcome is not VerificationOutcome.PASSED:
        reasons.append(DatasetRejection.NO_TEST_EVIDENCE)
    if episode.runtime_outcome is VerificationOutcome.FAILED:
        reasons.append(DatasetRejection.RUNTIME_FAILED)
    if episode.final_outcome is not EpisodeOutcome.SUCCEEDED:
        reasons.append(DatasetRejection.OUTCOME_NOT_SUCCESSFUL)

    if len(episode.steps) > _MAX_REASONABLE_STEPS:
        # 手数が極端なものは、道具の暴走か記録の壊れである。
        reasons.append(DatasetRejection.ANOMALOUS)

    identity = _content_identity(episode)
    if identity in seen:
        reasons.append(DatasetRejection.DUPLICATE)

    if reasons:
        return (None, tuple(reasons))

    return (
        DatasetCandidate(
            candidate_id=f"cand-{identity}",
            episode_id=episode.episode_id, task_id=episode.task_id,
            provider=episode.provider, model=episode.model,
            provenance=episode.provenance, training_use=episode.training_use,
            generation_evidence_uid=episode.generation_evidence_uid,
            revision_evidence_uids=episode.revision_evidence_uids,
            content_identity=identity,
        ),
        (),
    )


def build_dataset_candidates(
    episodes: "list[GenerationEpisode] | tuple[GenerationEpisode, ...]",
) -> tuple[tuple[DatasetCandidate, ...], dict[str, tuple[DatasetRejection, ...]]]:
    """まとめて Gate へ通す。**落とした理由も返す。**"""
    accepted: list[DatasetCandidate] = []
    rejected: dict[str, tuple[DatasetRejection, ...]] = {}
    seen: set[str] = set()
    for episode in episodes:
        candidate, reasons = evaluate_episode_for_dataset(
            episode, seen=frozenset(seen),
        )
        if candidate is None:
            rejected[episode.episode_id] = reasons
            continue
        seen.add(candidate.content_identity)
        accepted.append(candidate)
    return (tuple(accepted), rejected)


# ---------------------------------------------------------------------------
# Preference pairs（§28）
# ---------------------------------------------------------------------------


class PreferenceReason(str, Enum):
    """**なぜ片方が良いと言えるのか。** 理由の無い対を作らない。"""

    REPAIRED_TO_PASS = "repaired_to_pass"
    LOCAL_BEAT_TEACHER = "local_beat_teacher"
    CORRECTED_THEN_ACCEPTED = "corrected_then_accepted"


@dataclass(frozen=True)
class PreferencePair:
    """良い側と悪い側の対。**識別子だけ。**"""

    reason: PreferenceReason
    task_id: str
    rejected_reference: str
    preferred_reference: str
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "reason": self.reason.value, "task_id": self.task_id,
            "rejected_reference": self.rejected_reference,
            "preferred_reference": self.preferred_reference,
            "evidence": list(self.evidence),
        }


def build_preference_pairs(
    *,
    episodes: "list[GenerationEpisode] | tuple[GenerationEpisode, ...]" = (),
    comparisons: "list[TeacherComparison] | tuple[TeacherComparison, ...]" = (),
) -> tuple[PreferencePair, ...]:
    """対を作る。**「違う」と言われただけのものは対にしない**（§28）。"""
    pairs: list[PreferencePair] = []

    for episode in episodes:
        if not episode.repair_succeeded:
            continue
        if episode.final_outcome is not EpisodeOutcome.SUCCEEDED:
            # 直したが最後まで通っていない。**良い側が確定していない。**
            continue
        first = episode.repair_rounds[0]
        pairs.append(PreferencePair(
            reason=PreferenceReason.REPAIRED_TO_PASS,
            task_id=episode.task_id,
            rejected_reference=f"{episode.episode_id}#before:{first.failure_code}",
            preferred_reference=f"{episode.episode_id}#after",
            evidence=(episode.episode_id,),
        ))

    for comparison in comparisons:
        if comparison.verdict is not ComparisonVerdict.LOCAL_BETTER:
            continue
        if not comparison.local_wins_where_teacher_failed:
            # 点差だけでは対にしない。**どの軸で勝ったか**が要る。
            continue
        pairs.append(PreferencePair(
            reason=PreferenceReason.LOCAL_BEAT_TEACHER,
            task_id=comparison.task_id,
            rejected_reference=comparison.teacher_episode_id
            or f"teacher:{comparison.teacher.provider}",
            preferred_reference=comparison.local_episode_id
            or f"local:{comparison.local_provider}",
            evidence=(comparison.task_id,),
        ))

    return tuple(pairs)
