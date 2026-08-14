"""Benchmark Evidence(FORGE-AI-FOUNDATION-010 Phase J、2026-08-13)。

Benchmarkの**結果**を、Routingが使ってよい形で保持する。

---

## これが解く問題

`benchmark.py`は`BenchmarkReport`を返すが、返すだけである。
Routingは`_order()`が宣言順を返すだけで、品質を見ていない
(§13: 「Benchmark未接続」)。つまり、

* 測っても、次の判断に使われない
* 使おうとすると、**どの数字を信じてよいか**が決まっていない

という状態だった。ここが埋めるのは後者である。

## 数字だけでは判断できない(§39)

`task_accuracy = 0.85`という数字には、それ単体では意味が無い。

* **いつ**測ったか — Providerは黙ってモデルを差し替える
* **何を**測ったか — datasetが違えば比較にならない(§19「同一Dataset」)
* **何件**測ったか — 3件の0.85と200件の0.85は別物である
* **どうやって**測ったか — **Test Doubleで測った0.85は、その
  Providerについて何も言っていない**

最後の1つが決定的である。`AIRouter`のテストはTest Doubleで
「成功するAdapter」を作れるので、それをBenchmarkに通せば
task_accuracy=1.0が出る。その数字がProduction Routingへ流れ込むと、
**測っていないものを測ったことにして本番の経路が決まる**。

したがって`BenchmarkRun`は測定条件を必ず携える。条件を持たない
数字はこの型で表現できない。

## Routingへの接続(§5・§13・§21)

`ranking_for()`は、次を**すべて**満たすときだけ順位を返す:

1. `verification`が`REAL`(実APIを叩いた記録)
2. 件数が`_MIN_DATASET_SIZE`以上
3. 記録が`_MAX_AGE_SECONDS`以内
4. そのTaskについて2 Provider以上の記録がある(1つでは順位が無い)

満たさなければ`None`——`AIRouter`は宣言順のまま動く。
**「Benchmarkが無いからLocalを優先」といった、測っていない
決め打ちはしない**(§21: 測っていない品質を賭けてQuotaを節約
すると、Product Qualityを壊しうる)。

配線は`AIRouter`側で済ませてある。今それが効かないのは
**コードが無いからではなくデータが無いから**であり、実測を
入れれば自動的に効き始める。この区別は重要である
——「基盤はあるが本番では使っていない」を3度繰り返したので、
今回は逆に「配線済みで、データ待ち」という状態にした。

## 既知の制限

プロセス内メモリのみ(`ProviderStateStore`と同じ、TD41)。
再起動で消える。永続化は、実際に測った記録が出てから決める
——保存形式を先に決めても、何を保存すべきかがまだ分かっていない。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "BenchmarkEvidenceStore",
    "BenchmarkRun",
    "Verification",
    "default_evidence_store",
]


class Verification(str, Enum):
    """その数字を**どうやって得たか**(§39)。

    型として持つのは、区別を書き忘れられないようにするためである。
    レポートの文章で「Doubleです」と書く運用は、いずれ書き漏れる。
    """

    REAL = "real"
    """実APIを実際に叩いて測った。**Routingへ使ってよい唯一の区分。**"""

    DOUBLE = "double"
    """Test Doubleで測った。Adapterの契約は検査できるが、
    **Providerの品質については何も言っていない。**"""

    FIXTURE = "fixture"
    """記録済み応答の再生。回帰検出には使えるが、現在のProviderの
    実力ではない(モデルは黙って差し替わる)。"""

    UNVERIFIED = "unverified"
    """出所が分からない。**既定値**——分からないものを
    「実測」に格上げしない。"""


# Routingへ使うための下限。**根拠を述べられる値にしてある。**
_MIN_DATASET_SIZE = 16
"""16件。`impact_benchmark.py`のdatasetがこの規模であり、
4段階のimpactを各4件ずつ含む。これ未満だと、1件の当たり外れが
6%以上動かし、Provider間の差と区別できない。"""

_MAX_AGE_SECONDS = 30 * 24 * 3600.0
"""30日。Providerはモデルを黙って差し替える(Geminiの`-latest`系は
特にそう)。古い記録で今日のRoutingを決めない。"""

_MIN_PROVIDERS_FOR_RANKING = 2
"""1 Providerしか測っていなければ、順位という概念が無い。
「唯一測ったものが最良」は、測っていないものについての主張である。"""


@dataclass(frozen=True)
class BenchmarkRun:
    """1回の測定。**測定条件を必ず携える。**"""

    task: ForgeTask
    provider: str
    model: str
    """実際に叩いたモデル識別子。Provider名だけでは足りない
    ——同じ`gemini`でもモデルが違えば別物である。"""

    dataset_id: str
    dataset_size: int
    verification: Verification = Verification.UNVERIFIED

    schema_valid_rate: float = 0.0
    task_accuracy: float = 0.0
    failure_rate: float = 0.0
    latency_p50_ms: float = 0.0

    recorded_at: float = 0.0

    def is_usable_for_routing(self, *, now: float) -> bool:
        """この1件を、本番のProvider選択の根拠にしてよいか。"""
        return (
            self.verification is Verification.REAL
            and self.dataset_size >= _MIN_DATASET_SIZE
            and self.recorded_at > 0
            and (now - self.recorded_at) <= _MAX_AGE_SECONDS
        )

    def unusable_reason(self, *, now: float) -> str | None:
        """使えない場合、**なぜ**か。理由を言えないと調査できない。"""
        if self.verification is not Verification.REAL:
            return f"{self.provider}: 実測ではない({self.verification.value})"
        if self.dataset_size < _MIN_DATASET_SIZE:
            return f"{self.provider}: 件数不足({self.dataset_size} < {_MIN_DATASET_SIZE})"
        if self.recorded_at <= 0:
            return f"{self.provider}: 測定時刻が記録されていない"
        if (now - self.recorded_at) > _MAX_AGE_SECONDS:
            days = (now - self.recorded_at) / 86400.0
            return f"{self.provider}: 記録が古い({days:.0f}日前)"
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "task": self.task.value,
            "provider": self.provider,
            "model": self.model,
            "dataset_id": self.dataset_id,
            "dataset_size": self.dataset_size,
            "verification": self.verification.value,
            "schema_valid_rate": round(self.schema_valid_rate, 3),
            "task_accuracy": round(self.task_accuracy, 3),
            "failure_rate": round(self.failure_rate, 3),
            "latency_p50_ms": round(self.latency_p50_ms, 1),
            "recorded_at": self.recorded_at,
        }


class BenchmarkEvidenceStore:
    """Task × Provider ごとに、最新の測定を1件だけ持つ。

    履歴を貯めないのは、Routingが使うのは常に最新だからである。
    傾向分析が要るようになったら、そのときに履歴を足す
    ——使い道の無い蓄積を先に作らない。
    """

    def __init__(self, *, now: object = time.time) -> None:
        self._runs: dict[tuple[ForgeTask, str], BenchmarkRun] = {}
        self._now = now

    def record(self, run: BenchmarkRun) -> BenchmarkRun:
        """1件記録する。`recorded_at`が未設定なら今の時刻を入れる。"""
        if run.recorded_at <= 0:
            from dataclasses import replace  # noqa: PLC0415

            run = replace(run, recorded_at=self._now())
        self._runs[(run.task, run.provider)] = run
        return run

    def runs_for(self, task: ForgeTask) -> tuple[BenchmarkRun, ...]:
        return tuple(run for (t, _), run in self._runs.items() if t is task)

    def ranking_for(self, task: ForgeTask) -> tuple[str, ...] | None:
        """このTaskのProvider優先順位。使える根拠が無ければ`None`。

        `None`は「順位が無い」であって「全部同じ」ではない。
        呼び出し側(`AIRouter._order()`)は宣言順のままにする。
        """
        now = self._now()
        usable = [run for run in self.runs_for(task) if run.is_usable_for_routing(now=now)]
        if len(usable) < _MIN_PROVIDERS_FOR_RANKING:
            return None
        # 正答率が高い順。同率ならlatencyが短い順。
        # **schema適合率で足切りしない**——`BenchmarkReport.winner()`が
        # 採用可否として既に課しており、ここで二重に課すと、
        # 「候補から外す」と「後ろに回す」が混ざる(Phase Bで
        # `_order()`から健全性を外したのと同じ理由)。
        usable.sort(key=lambda run: (-run.task_accuracy, run.latency_p50_ms))
        return tuple(run.provider for run in usable)

    def exclusion_reasons(self, task: ForgeTask) -> tuple[str, ...]:
        """順位が付かない場合に、**何が足りないか**を返す。"""
        now = self._now()
        reasons = [
            reason
            for run in self.runs_for(task)
            if (reason := run.unusable_reason(now=now)) is not None
        ]
        usable = len(self.runs_for(task)) - len(reasons)
        if usable and usable < _MIN_PROVIDERS_FOR_RANKING:
            reasons.append(
                f"実測が{usable}Providerのみ(順位付けには{_MIN_PROVIDERS_FOR_RANKING}以上必要)"
            )
        if not self.runs_for(task):
            reasons.append(f"task={task.value} のBenchmark記録がまだ無い")
        return tuple(reasons)

    def reset(self) -> None:
        self._runs.clear()


_default_store: BenchmarkEvidenceStore | None = None


def default_evidence_store() -> BenchmarkEvidenceStore:
    """アプリ全体で共有するBenchmark記録。

    `ProviderStateStore`と同じくプロセス内Singleton。複数ワーカー
    構成では共有されない(TD41)。
    """
    global _default_store  # noqa: PLW0603
    if _default_store is None:
        _default_store = BenchmarkEvidenceStore()
    return _default_store
