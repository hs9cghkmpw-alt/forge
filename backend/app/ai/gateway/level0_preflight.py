"""FORGE-020A4 — real Local Model を呼ぶ前の Level 0 probe 適格性判定。

この module が証明するのは **Level 0 そのものではない**。

Level 0 は実 open-weight model が production path で software structure を作り、
Validator と Evidence まで通った実測だけで成立する。一方、過去の実測では
``domain_resolution=generated`` でも、最終的な structure が Curated / 決定的
fallback になり、数分の実モデル推論を使った後で ``INVALID_PROBE`` になることが
あった。

そこで実モデルを呼ぶ前に、同じ production ``/generate`` 経路を ``mock``
provider で1回通し、**構造生成の仕事そのものが Entity Synthesis stage へ渡る
probe か**を確認する。

重要:

* ``ELIGIBLE_FOR_REAL_RUN`` は Level 0 PASS ではない。
* mock / Test Double の成果を Real Local Model run に数えない。
* Local Model が同じ構造を生成できる保証もしない。
* 利用者の発話や model の raw output は Evidence に保存しない。

この境界は「測定前の適格性確認」であって「測定条件の緩和」ではない。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.capability_evidence import (
    GenerationStructureSource,
    StructureProvider,
)
from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "Level0PreflightFacts",
    "Level0PreflightOutcome",
    "Level0PreflightResult",
    "evaluate_level0_probe_preflight",
]


class Level0PreflightOutcome(str, Enum):
    """実 Local Model を使う前に分かる probe の状態。"""

    ELIGIBLE_FOR_REAL_RUN = "eligible_for_real_run"
    CURATED_BYPASS = "curated_bypass"
    DETERMINISTIC_BYPASS = "deterministic_bypass"
    SYNTHESIS_REJECTED = "synthesis_rejected"
    WRONG_PROVIDER = "wrong_provider"
    WRONG_TASK = "wrong_task"
    VALIDATION_FAILED = "validation_failed"
    UNOBSERVABLE = "unobservable"


@dataclass(frozen=True)
class Level0PreflightFacts:
    """production path から観測した、probe 適格性に必要な事実だけ。

    Need本文や生成物本文は持たない。識別子・bool・closed reason codeだけである。
    """

    domain_resolution: str = ""
    structure_source: GenerationStructureSource = GenerationStructureSource.UNKNOWN
    structure_provider: StructureProvider = StructureProvider.NONE
    structure_task: str = ""
    observed_tasks: tuple[ForgeTask, ...] = ()
    validator_passed: bool = False
    generation_evidence_uid: str = ""
    entity_synthesis_attempted: bool = False
    entity_synthesis_accepted: bool = False
    entity_synthesis_rejection_reason: str | None = None


@dataclass(frozen=True)
class Level0PreflightResult:
    """probe を実モデルへ回してよいか。Real Local Model の成績ではない。"""

    outcome: Level0PreflightOutcome
    reasons: tuple[str, ...]
    facts: Level0PreflightFacts

    @property
    def eligible_for_real_run(self) -> bool:
        return self.outcome is Level0PreflightOutcome.ELIGIBLE_FOR_REAL_RUN

    def to_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "eligible_for_real_run": self.eligible_for_real_run,
            "reasons": list(self.reasons),
            "facts": {
                "domain_resolution": self.facts.domain_resolution,
                "structure_source": self.facts.structure_source.value,
                "structure_provider": self.facts.structure_provider.value,
                "structure_task": self.facts.structure_task,
                "observed_tasks": [task.value for task in self.facts.observed_tasks],
                "validator_passed": self.facts.validator_passed,
                "generation_evidence_uid": self.facts.generation_evidence_uid,
                "entity_synthesis_attempted": self.facts.entity_synthesis_attempted,
                "entity_synthesis_accepted": self.facts.entity_synthesis_accepted,
                "entity_synthesis_rejection_reason": (
                    self.facts.entity_synthesis_rejection_reason
                ),
            },
        }


def evaluate_level0_probe_preflight(
    facts: Level0PreflightFacts,
) -> Level0PreflightResult:
    """mock production run の typed Evidence から probe 適格性を判定する。

    判定順には意味がある。

    * Domain 自体が Curated なら、Entity Synthesisへ仕事が来ないので
      ``CURATED_BYPASS``。
    * ``generated`` まで来て Entity Synthesis を**実際に試した**のに
      sanitize/rejectionで落ち、その後 Curated/決定的fallbackが勝った場合は、
      fallbackだけを見て ``DETERMINISTIC_BYPASS`` と分類しない。
      原因は ``SYNTHESIS_REJECTED`` と closed reason code で残す。
    * Entity Synthesis自体を試していない決定的構造だけを
      ``DETERMINISTIC_BYPASS`` とする。

    これにより「最終構造はfallbackだった」という結果と「なぜそうなったか」を
    混同しない。
    """

    resolution = facts.domain_resolution.strip().lower()
    if not resolution:
        return Level0PreflightResult(
            Level0PreflightOutcome.UNOBSERVABLE,
            ("domain_resolution を観測できない",),
            facts,
        )
    if resolution == "curated":
        return Level0PreflightResult(
            Level0PreflightOutcome.CURATED_BYPASS,
            ("Curated Domain Library が先に構造を決める",),
            facts,
        )

    # 020A4 CI実測で、generated → Entity Synthesis attempted → no_valid_fields
    # → curated fallback という経路が確認された。最終fallbackだけを先に見ると
    # 本当の改善点（synthesis rejection）が隠れるため、attempt事実を優先する。
    if facts.entity_synthesis_attempted and not facts.entity_synthesis_accepted:
        reason = facts.entity_synthesis_rejection_reason or "unknown"
        return Level0PreflightResult(
            Level0PreflightOutcome.SYNTHESIS_REJECTED,
            (f"Entity Synthesis は試したが採用されなかった: {reason}",),
            facts,
        )

    if facts.structure_source in {
        GenerationStructureSource.CURATED,
        GenerationStructureSource.DETERMINISTIC_CAPABILITY_PLAN,
    }:
        return Level0PreflightResult(
            Level0PreflightOutcome.DETERMINISTIC_BYPASS,
            (
                "Entity Synthesis を採用せず決定的経路が software structure を決める",
            ),
            facts,
        )

    if facts.structure_source is not GenerationStructureSource.AI_ENTITY_SYNTHESIS:
        return Level0PreflightResult(
            Level0PreflightOutcome.UNOBSERVABLE,
            (
                "AI Entity Synthesis が software structure を作った証拠がない",
            ),
            facts,
        )

    # preflight は provider=mock で行う。ここが LOCAL なら preflight と実測を
    # 混ぜているし、CLOUD なら別経路を見ている。どちらも不適切。
    if facts.structure_provider is not StructureProvider.TEST_DOUBLE:
        return Level0PreflightResult(
            Level0PreflightOutcome.WRONG_PROVIDER,
            (
                "preflight の structure provider が Test Double ではない",
            ),
            facts,
        )

    expected_task = ForgeTask.ENTITY_SYNTHESIS.value
    if facts.structure_task != expected_task:
        return Level0PreflightResult(
            Level0PreflightOutcome.WRONG_TASK,
            (
                f"structure task が {expected_task} ではない",
            ),
            facts,
        )
    if ForgeTask.ENTITY_SYNTHESIS not in facts.observed_tasks:
        return Level0PreflightResult(
            Level0PreflightOutcome.WRONG_TASK,
            ("AIRouter の観測に entity_synthesis が無い",),
            facts,
        )

    if not facts.entity_synthesis_attempted or not facts.entity_synthesis_accepted:
        return Level0PreflightResult(
            Level0PreflightOutcome.UNOBSERVABLE,
            ("Entity Synthesis の attempted/accepted Evidence が揃っていない",),
            facts,
        )
    if not facts.generation_evidence_uid.strip():
        return Level0PreflightResult(
            Level0PreflightOutcome.UNOBSERVABLE,
            ("production Generation Evidence uid が無い",),
            facts,
        )
    if not facts.validator_passed:
        return Level0PreflightResult(
            Level0PreflightOutcome.VALIDATION_FAILED,
            ("mock production run が Validator を通っていない",),
            facts,
        )

    return Level0PreflightResult(
        Level0PreflightOutcome.ELIGIBLE_FOR_REAL_RUN,
        (
            "production path が Entity Synthesis を実際に呼び、Test Double の構造を採用した",
            "実 Local Model へ同じ仕事を渡す候補として適格（Level 0 PASS の意味ではない）",
        ),
        facts,
    )
