"""Local Promotion Gate — **Local Firstを「本当にLocal First」にする**
(FORGE-017A §7、2026-08-24)。

---

## 何が矛盾していたか

Growing AI Architecture は

    Qualified Local → Local

と書きながら、実装側の説明は

    Local優先は Benchmark 順位が同点のときだけ

だった。同点のときだけ効く優先は、**実質的にLocal Firstではない**。
Cloudが1点高ければ毎回Cloudが選ばれるので、Localは永久に使われない。

## しかし過去の教訓も正しい

`AIRouter._order()` のdocstringに、実装して考え直した記録がある。

> Local優先は根拠が無い。Benchmarkが無いのにLocalを優先するのは、
> **測っていない品質を賭けてQuotaを節約している**だけで、Product
> Qualityを壊しうる。

これは正しい。**未測定のLocalを優先してはいけない。**

## 解: Best Score Wins をやめ、Quality Gate にする

2つの主張は、比べ方を変えると両立する。

```
❌ Best Score Wins
     Local 0.91 vs Cloud 0.93 → 毎回Cloud（Localは永久に使われない）

✅ Local Meets Product Bar → Local First
     Localが「製品として通用する水準」を満たしているなら、
     Cloudが少し上でもLocalを使う
```

**「一番良いもの」ではなく「十分に良いか」で判断する。** 十分に良い
なら、Quotaを使わない・外へデータを出さない方を選ぶ理由がある
（Product Direction §6、Privacy First）。

満たしていなければCloudへ落ちる。ここは従来どおりである。

## Gateは全部満たさないと通らない

1つでも欠けたら`eligible=False`にする。「だいたい満たしている」で
通すと、**何が理由で通ったのか**が後から分からなくなる。

`UNKNOWN`・未測定は**通さない**。分からないものを楽観側へ倒さない
（`CLAUDE.md` §3）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.gateway.benchmark_evidence import (
    BenchmarkEvidenceStore,
    BenchmarkRun,
    Verification,
)
from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "LocalPromotionGate",
    "PromotionDecision",
    "default_promotion_gate",
]


#: Productとして通用する水準（017A §7 `quality_threshold`）。
#:
#: **Cloudより高い必要は無い。** 「十分か」を見る値である。
_MIN_TASK_ACCURACY = 0.85

#: 構造化出力の成功率（`BenchmarkRun`側のGateと同じ水準に合わせる）。
_MIN_SCHEMA_SUCCESS = 0.9

#: 応答時間の上限。これを超えると、品質が足りていても製品として使えない。
_MAX_LATENCY_P50_MS = 8000.0


@dataclass(frozen=True)
class PromotionDecision:
    """あるProviderが、あるTaskでLocal昇格に値するか。

    **理由を必ず持つ。** 「通らなかった」だけ返すと、Providerを
    設定した人が何を直せばよいか分からない。
    """

    provider: str
    task: ForgeTask
    eligible: bool
    reasons: tuple[str, ...] = field(default=())
    """通らなかった理由。`eligible`なら空。"""

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "task": self.task.value,
            "eligible": self.eligible,
            "reasons": list(self.reasons),
        }


class LocalPromotionGate:
    """Local昇格の判定（017A §7）。

    **Provider rankingはしない。** ここが答えるのは「このLocalは製品
    水準を満たすか」だけで、順位付けは`AIRouter`の仕事である
    （017A §8、責務を混ぜない）。
    """

    def __init__(self, evidence: BenchmarkEvidenceStore | None = None) -> None:
        self._evidence = evidence

    def evaluate(
        self,
        *,
        provider: str,
        task: ForgeTask,
        is_local: bool,
        now: float,
        latency_budget_ms: float | None = None,
    ) -> PromotionDecision:
        """昇格判定。**全条件を満たさなければ通さない。**"""
        reasons: list[str] = []

        if not is_local:
            reasons.append("Localではない")
            return PromotionDecision(provider, task, eligible=False, reasons=tuple(reasons))

        run = self._latest_run(provider, task)
        if run is None:
            # **未測定は通さない。** ここを緩めると、過去に退けた
            # 「測っていない品質を賭けてQuotaを節約する」へ戻る。
            reasons.append("このTaskでの実測が無い（capability_supported / benchmark_verified 未達）")
            return PromotionDecision(provider, task, eligible=False, reasons=tuple(reasons))

        if run.verification is not Verification.REAL:
            reasons.append(f"実測ではない({run.verification.value})")

        unusable = run.unusable_reason(now=now)
        if unusable:
            # 件数・鮮度・dataset同一性・schema成功率。既存のGateを再利用する
            # ——同じ判断を2箇所に書くと、片方だけ緩む。
            reasons.append(unusable)

        if run.task_accuracy < _MIN_TASK_ACCURACY:
            reasons.append(
                f"品質が製品水準に届かない({run.task_accuracy:.0%} < {_MIN_TASK_ACCURACY:.0%})"
            )
        if run.schema_valid_rate < _MIN_SCHEMA_SUCCESS:
            reasons.append(
                f"構造化出力の成功率が低い({run.schema_valid_rate:.0%} < {_MIN_SCHEMA_SUCCESS:.0%})"
            )

        budget = latency_budget_ms if latency_budget_ms is not None else _MAX_LATENCY_P50_MS
        if run.latency_p50_ms <= 0:
            reasons.append("応答時間が記録されていない")
        elif run.latency_p50_ms > budget:
            reasons.append(f"応答が遅すぎる({run.latency_p50_ms:.0f}ms > {budget:.0f}ms)")

        return PromotionDecision(
            provider, task, eligible=not reasons, reasons=tuple(reasons)
        )

    def promoted_providers(
        self, task: ForgeTask, candidates: "list[tuple[str, bool]]", *, now: float
    ) -> tuple[str, ...]:
        """このTaskで昇格しているLocal Providerの名前。

        `candidates`は`(provider, is_local)`。**順位は付けない**
        ——「昇格しているかどうか」だけを返す。
        """
        return tuple(
            provider
            for provider, is_local in candidates
            if self.evaluate(provider=provider, task=task, is_local=is_local, now=now).eligible
        )

    def _latest_run(self, provider: str, task: ForgeTask) -> BenchmarkRun | None:
        if self._evidence is None:
            return None
        runs = [r for r in self._evidence.runs_for(task) if r.provider == provider]
        if not runs:
            return None
        return max(runs, key=lambda r: r.recorded_at)


def default_promotion_gate(evidence: BenchmarkEvidenceStore | None = None) -> LocalPromotionGate:
    return LocalPromotionGate(evidence)
