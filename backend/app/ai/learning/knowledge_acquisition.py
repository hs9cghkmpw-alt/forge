"""Knowledge Acquisition — **読んだだけでは知識にしない**
(FORGE-020 §25・§26、2026-08-25)。

---

## Web を読んだだけで Forge Knowledge へ昇格させない

Web には間違いも、古い情報も、悪意も在る。読めたことは
「正しいと確かめた」ではない。

```
Web info
  → implementation        実際にそれで作ってみる
  → Build PASS
  → Test PASS
  → Runtime / Visual（該当するなら）
  → Evaluator / User Evidence
  → Knowledge Candidate
  → review / promotion
```

**動いたことを根拠にする。** これは §22 の「Fake PASS 禁止」と同じ姿勢で
あり、Forge の Knowledge が「AIが言っていた」の集積にならないための
唯一の防ぎ方である。

## 成功コードを丸ごと巨大 Template として登録しない

一度うまくいった Match3 を `match3_template` として覚えると、
次に来る「釣った魚でパズル対戦」には**使えない**。ジャンルが1つ
増えただけで、生成力は1ミリも増えていない。

覚えるのは**一般化した部品**である。

| 覚える | 覚えない |
|---|---|
| Grid Interaction | `match3_template` |
| Drag Semantics | `jrpg_widget` |
| Matching Rule / Gravity / Cascade | `puzzle_rpg_widget` |
| Animation Sequencing | 「このアプリのコード全文」 |
| Failure Fix / Constraint | |
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.ai.learning.episode import GenerationEpisode, VerificationOutcome
from app.ai.learning.self_extension import SkillLifecycle

__all__ = [
    "AcquisitionRejection",
    "ExtractedSkill",
    "KnowledgeCandidate",
    "SkillKind",
    "evaluate_knowledge_acquisition",
]


class SkillKind(str, Enum):
    """**ジャンル名ではなく部品の種類**（§26）。"""

    PATTERN = "pattern"
    CAPABILITY = "capability"
    CONSTRAINT = "constraint"
    FAILURE_FIX = "failure_fix"
    INTERACTION = "interaction"


class AcquisitionRejection(str, Enum):
    NO_IMPLEMENTATION = "no_implementation"
    BUILD_NOT_PASSED = "build_not_passed"
    TESTS_NOT_PASSED = "tests_not_passed"
    RUNTIME_FAILED = "runtime_failed"
    NO_SOURCE = "no_source"
    """出典が無い。**「AIが言っていた」を知識にしない。**"""

    NOT_GENERALIZED = "not_generalized"
    """一般化されていない（アプリ丸ごと・ジャンル名だけ）。"""


#: ジャンル名で覚えようとしているものを拒む語（§26 / §33）。
_GENRE_SHAPED = ("_template", "_widget", "jrpg", "match3", "puzzle_rpg")


@dataclass(frozen=True)
class ExtractedSkill:
    """一般化した部品1つ。**アプリ丸ごとではない。**"""

    skill_id: str
    kind: SkillKind
    summary: str
    lifecycle: SkillLifecycle = SkillLifecycle.PROVISIONAL
    learned_from_episodes: tuple[str, ...] = ()

    @property
    def looks_like_a_genre_template(self) -> bool:
        """**ジャンル専用の塊になっていないか。**"""
        lowered = self.skill_id.lower()
        return any(token in lowered for token in _GENRE_SHAPED)

    def to_dict(self) -> dict[str, object]:
        return {
            "skill_id": self.skill_id, "kind": self.kind.value,
            "summary": self.summary, "lifecycle": self.lifecycle.value,
            "learned_from_episodes": list(self.learned_from_episodes),
        }


@dataclass(frozen=True)
class KnowledgeCandidate:
    """昇格候補。**まだ Knowledge ではない。**"""

    candidate_id: str
    skills: tuple[ExtractedSkill, ...]
    source_references: tuple[str, ...] = field(default_factory=tuple)
    episode_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "skills": [s.to_dict() for s in self.skills],
            "source_references": list(self.source_references),
            "episode_id": self.episode_id,
        }


def evaluate_knowledge_acquisition(
    episode: GenerationEpisode, skills: "tuple[ExtractedSkill, ...]",
) -> tuple[KnowledgeCandidate | None, tuple[AcquisitionRejection, ...]]:
    """Web で読んだことを Knowledge 候補にしてよいか。

    **動いた証拠が要る**（§25）。読めただけでは通さない。
    """
    reasons: list[AcquisitionRejection] = []

    if not skills:
        reasons.append(AcquisitionRejection.NOT_GENERALIZED)
    elif any(s.looks_like_a_genre_template for s in skills):
        # ジャンル専用の塊を Knowledge にしない（§26 / §33）。
        reasons.append(AcquisitionRejection.NOT_GENERALIZED)

    if not episode.generation_evidence_uid:
        reasons.append(AcquisitionRejection.NO_IMPLEMENTATION)
    if episode.build_outcome is not VerificationOutcome.PASSED:
        reasons.append(AcquisitionRejection.BUILD_NOT_PASSED)
    if episode.test_outcome is not VerificationOutcome.PASSED:
        reasons.append(AcquisitionRejection.TESTS_NOT_PASSED)
    if episode.runtime_outcome is VerificationOutcome.FAILED:
        reasons.append(AcquisitionRejection.RUNTIME_FAILED)
    if not episode.web_source_references and not episode.knowledge_references:
        # 出典が無いものを知識にしない。
        reasons.append(AcquisitionRejection.NO_SOURCE)

    if reasons:
        return (None, tuple(reasons))

    return (
        KnowledgeCandidate(
            candidate_id=f"know-{episode.episode_id[:12]}",
            skills=skills,
            source_references=episode.web_source_references,
            episode_id=episode.episode_id,
        ),
        (),
    )
