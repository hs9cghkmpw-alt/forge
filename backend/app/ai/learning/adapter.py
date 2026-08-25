"""Training / Adapter Promotion — **Base Model を替えても資産が残る形**
(FORGE-020 §29、2026-08-25)。

---

## 今回は契約だけ（正直な申告）

この環境には GPU も学習 Runtime も無く、model 重みの取得先
（huggingface / ollama）は network policy で拒否されている。
したがって **実 LoRA training は行っていない。NOT IMPLEMENTED。**

契約を先に作るのは、Dataset と Benchmark の形が**あとから決まると
作り直しになる**ためである。

```
Dataset Snapshot → SFT → Preference → LoRA/Adapter
   → held-out Benchmark → regression → Promotion → rollback
```

## Base Model 互換を Adapter が持つ

Adapter は特定の Base Model へ紐づく。別の Base へそのまま載せると
静かに壊れるので、`base_model_compatibility` を必須にする。

## 昇格は「前より良い」だけでは足りない

`benchmark_before` / `benchmark_after` の両方が要る。片方しか無い
昇格は**比較していない昇格**である。さらに `regression_passed` を
別に持つ——平均が上がっても、特定の課題で壊れていれば昇格しない。

## 巻き戻し先を必ず持つ

`rollback_target` が無い Adapter は昇格させない。戻せない変更を
本番へ入れない。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "AdapterMetadata",
    "AdapterPromotionDecision",
    "AdapterStatus",
    "DatasetSnapshot",
    "TrainingStage",
    "evaluate_adapter_promotion",
]


class TrainingStage(str, Enum):
    """どの段まで進んだか。**「やっていない」を「済み」と書かない。**"""

    DATASET_SNAPSHOT = "dataset_snapshot"
    SUPERVISED_FINE_TUNING = "supervised_fine_tuning"
    PREFERENCE_OPTIMIZATION = "preference_optimization"
    ADAPTER_BUILT = "adapter_built"
    BENCHMARKED = "benchmarked"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"


class AdapterStatus(str, Enum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class DatasetSnapshot:
    """学習に使った Dataset の**固定された姿**。

    id だけでなく `identity` を持つ——中身を差し替えたのに同じ id を
    名乗ると、Benchmark の前後比較が意味を失う（011 §3 と同じ形）。
    """

    dataset_version: str
    identity: str
    candidate_count: int
    preference_pair_count: int
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_version": self.dataset_version, "identity": self.identity,
            "candidate_count": self.candidate_count,
            "preference_pair_count": self.preference_pair_count,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AdapterMetadata:
    """Adapter 1つ。**Base Model 互換と巻き戻し先を必ず持つ。**"""

    adapter_id: str
    base_model_compatibility: tuple[str, ...]
    dataset: DatasetSnapshot
    training_config_identity: str
    stage: TrainingStage = TrainingStage.DATASET_SNAPSHOT
    status: AdapterStatus = AdapterStatus.DRAFT
    benchmark_before: float | None = None
    benchmark_after: float | None = None
    regression_passed: bool = False
    rollback_target: str = ""
    signature: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "base_model_compatibility": list(self.base_model_compatibility),
            "dataset": self.dataset.to_dict(),
            "training_config_identity": self.training_config_identity,
            "stage": self.stage.value, "status": self.status.value,
            "benchmark_before": self.benchmark_before,
            "benchmark_after": self.benchmark_after,
            "regression_passed": self.regression_passed,
            "rollback_target": self.rollback_target,
            "signature": self.signature,
        }


@dataclass(frozen=True)
class AdapterPromotionDecision:
    """昇格判定。**理由を必ず持つ。**"""

    adapter_id: str
    eligible: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id, "eligible": self.eligible,
            "reasons": list(self.reasons),
        }


def evaluate_adapter_promotion(
    adapter: AdapterMetadata, *, base_model: str, min_improvement: float = 0.0,
) -> AdapterPromotionDecision:
    """昇格してよいか。**1つでも欠けたら通さない**（`LocalPromotionGate` と同じ姿勢）。"""
    reasons: list[str] = []

    if base_model not in adapter.base_model_compatibility:
        reasons.append(f"Base Model が対象外（{base_model}）")
    if adapter.benchmark_before is None or adapter.benchmark_after is None:
        # **比較していない昇格を通さない。**
        reasons.append("Benchmark の前後が揃っていない")
    elif adapter.benchmark_after - adapter.benchmark_before < min_improvement:
        reasons.append(
            f"改善が足りない（{adapter.benchmark_before:.3f} → "
            f"{adapter.benchmark_after:.3f}）"
        )
    if not adapter.regression_passed:
        # 平均が上がっても、特定の課題で壊れていれば昇格しない。
        reasons.append("regression を通っていない")
    if not adapter.rollback_target:
        # 戻せない変更を本番へ入れない。
        reasons.append("巻き戻し先が無い")
    if adapter.stage not in {TrainingStage.BENCHMARKED, TrainingStage.ADAPTER_BUILT}:
        reasons.append(f"段が足りない（{adapter.stage.value}）")

    return AdapterPromotionDecision(
        adapter.adapter_id, eligible=not reasons, reasons=tuple(reasons),
    )
