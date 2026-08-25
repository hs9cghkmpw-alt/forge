"""Self-Extension — **足りない能力を、作って、確かめて、昇格させる**
(FORGE-020 §30、2026-08-25)。

---

## 「対応Widgetがない」を作れない理由にしない

Product Direction は finite Widget Builder を禁じている。将来
「その Widget が無いので作れません」で止まらないためには、
**足りない能力を Forge 自身が作る**道が要る。

```
missing capability detected
  → Capability Spec
  → generated implementation
  → sandbox
  → build → tests → security → runtime
  → provisional
  → 繰り返し成功した Evidence
  → Capability Registry promotion
```

## AIが本番のprimitiveを勝手に書き換えることはしない

生成された実装が最初に入るのは `PROVISIONAL` である。本番の primitive を
直接触る経路は**作らない**。昇格には

* sandbox で build / tests / security / runtime を通ること
* **1回ではなく、繰り返し**成功していること

を要求する。1回の成功で昇格させると、たまたま通った実装が本番の
土台になる。

## 今回は契約と Gate だけ（正直な申告）

実際にコードを生成して sandbox で走らせる経路は **NOT IMPLEMENTED**。
ここに在るのは、その経路が満たすべき条件である。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "CapabilityLifecycle",
    "CapabilitySpec",
    "ExtensionEvidence",
    "PromotionVerdict",
    "SkillLifecycle",
    "evaluate_capability_promotion",
]


class CapabilityLifecycle(str, Enum):
    """能力の段。**`PROVISIONAL` を飛ばして本番へ行けない。**"""

    REQUESTED = "requested"
    SPECIFIED = "specified"
    GENERATED = "generated"
    PROVISIONAL = "provisional"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class SkillLifecycle(str, Enum):
    """Skill の段（§26）。

    **成功した Match3 を `match3_template` としてしか覚えない**設計を
    禁じるための語彙である。覚えるのは
    `Grid Interaction` / `Drag Semantics` / `Matching Rule` /
    `Gravity` / `Cascade` / `Animation Sequencing` のような**部品**で
    あって、ジャンル名ではない。
    """

    PROVISIONAL = "provisional"
    TESTED = "tested"
    VALIDATED = "validated"
    REUSED = "reused"
    PROMOTED = "promoted"
    DEPRECATED = "deprecated"


@dataclass(frozen=True)
class CapabilitySpec:
    """足りない能力の**仕様**。

    `generalized_from` を持つのは、「このアプリのため」ではなく
    「この種の問題のため」に作らせるためである（§26）。
    """

    capability_id: str
    summary: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    generalized_from: tuple[str, ...] = ()
    """どの Episode から要求が出たか。**複数から出ているほど一般的。**"""

    lifecycle: CapabilityLifecycle = CapabilityLifecycle.REQUESTED

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id, "summary": self.summary,
            "inputs": list(self.inputs), "outputs": list(self.outputs),
            "generalized_from": list(self.generalized_from),
            "lifecycle": self.lifecycle.value,
        }


@dataclass(frozen=True)
class ExtensionEvidence:
    """sandbox で確かめた1回分。"""

    sandboxed: bool = False
    build_passed: bool = False
    tests_passed: bool = False
    security_passed: bool = False
    runtime_passed: bool = False

    @property
    def fully_passed(self) -> bool:
        return all((
            self.sandboxed, self.build_passed, self.tests_passed,
            self.security_passed, self.runtime_passed,
        ))

    def to_dict(self) -> dict[str, object]:
        return {
            "sandboxed": self.sandboxed, "build_passed": self.build_passed,
            "tests_passed": self.tests_passed, "security_passed": self.security_passed,
            "runtime_passed": self.runtime_passed, "fully_passed": self.fully_passed,
        }


@dataclass(frozen=True)
class PromotionVerdict:
    capability_id: str
    eligible: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id, "eligible": self.eligible,
            "reasons": list(self.reasons),
        }


#: 昇格に要る「繰り返し成功」の回数。**1回では通さない。**
_MIN_SUCCESSFUL_RUNS = 3


def evaluate_capability_promotion(
    spec: CapabilitySpec,
    evidence: "list[ExtensionEvidence] | tuple[ExtensionEvidence, ...]",
    *,
    min_successful_runs: int = _MIN_SUCCESSFUL_RUNS,
) -> PromotionVerdict:
    """Capability Registry へ昇格してよいか。**Gate を全部通ること。**"""
    reasons: list[str] = []

    if spec.lifecycle is not CapabilityLifecycle.PROVISIONAL:
        # **`PROVISIONAL` を飛ばして本番へ行けない。**
        reasons.append(f"provisional ではない（{spec.lifecycle.value}）")

    successful = [e for e in evidence if e.fully_passed]
    if len(successful) < min_successful_runs:
        reasons.append(
            f"繰り返し成功していない（{len(successful)} < {min_successful_runs}）"
        )
    if any(not e.sandboxed for e in evidence):
        # sandbox の外で通した実績を根拠にしない。
        reasons.append("sandbox の外で実行した記録が混ざっている")
    if not any(e.security_passed for e in evidence):
        reasons.append("security を1度も通っていない")

    return PromotionVerdict(
        spec.capability_id, eligible=not reasons, reasons=tuple(reasons),
    )
