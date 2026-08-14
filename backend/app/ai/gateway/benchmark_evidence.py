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
3. `dataset_hash`があり、**比較する相手と一致する**(011 §3)
4. `schema_valid_rate`が`_MIN_SCHEMA_VALID_RATE`以上(011 §3)
5. 記録が`_MAX_AGE_SECONDS`以内
6. そのTaskについて2 Provider以上の記録がある(1つでは順位が無い)

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

import hashlib
import time
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "BenchmarkEvidenceStore",
    "BenchmarkRun",
    "Verification",
    "dataset_fingerprint",
    "default_evidence_store",
]


def dataset_fingerprint(prompts: "Iterable[str]") -> str:
    """Datasetの中身から指紋を作る(FORGE-AI-FOUNDATION-011 §3)。

    **順序に依存させない。** ケースを並べ替えただけで別Datasetと
    判定されると、実質同じものを比べられなくなる。逆に、1件でも
    文言が変われば指紋は変わる——それが検出したい変化である。

    暗号学的な強度は要らない(改竄対策ではなく取り違え防止)。
    短く読める16文字に切っている。
    """
    digest = hashlib.sha256()
    for prompt in sorted(prompts):
        digest.update(prompt.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:16]


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

_MIN_SCHEMA_VALID_RATE = 0.9
"""構造化出力の最低成功率。**順序ではなく足切りである**(011 §3)。

---

## 指示書の問いへの回答

    Provider A: task_accuracy 0.95 / schema_valid 0.40
    Provider B: task_accuracy 0.90 / schema_valid 1.00

**Aを優先してはならない。** Forgeの品質契約として、次の理由による。

**1. Forgeにとって構造が壊れた応答は「少し悪い答え」ではなく
「答えが無い」である。**

Forgeは応答をJSONとして解釈し、Forge Language Validatorへ通す。
構造が壊れれば、その呼び出しは失敗するかRepairへ回る。利用者から
見えるのは「精度が少し低い」ではなく「作れませんでした」か
「余計に待たされた」である。

**2. 2つの数字は同じ土俵に乗っていない。**

`task_accuracy`は「応答が返って、かつ正解だった割合」である。
schema適合が40%なら、残り60%は評価対象にすらなっていない。
0.95という数字は**生き残った40%の中での話**でありうる。
これを0.90と並べるのは、母数の違う数字を比べていることになる。

**3. 精度は連続量だが、契約は満たすか満たさないかである。**

Forgeの設計は一貫して「健全性は**除外**で表し、品質は**順序**で
表す」としてきた(`AIRouter._order()`)。構造化出力は健全性の側で
ある——**壊れているものを、少し後ろに置いて使うことはできない。**

## 010で「足切りしない」と書いたことの訂正

`benchmark_evidence.py`初版のコメントで「schema適合率で足切りしない
——`BenchmarkReport.winner()`が既に課しているので二重になる」と
書いた。これは誤りだった。

`winner()`が課すのはBenchmark**レポート**を読むときであり、
`BenchmarkEvidenceStore`へは`winner()`を通さずに記録を入れられる。
つまりRouting側は何も守られていなかった。実際、指摘3の再現で
schema適合40%のProviderが1位になることを確認した。

## 0.9という値の根拠

`BenchmarkReport.winner()`が既に使っている値に合わせた。**同じ
概念に2つの閾値を置かない**——片方だけ直して食い違うのが、
TD37で踏んだ形である。"""


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

    dataset_hash: str = ""
    """Dataset中身の指紋(FORGE-AI-FOUNDATION-011 §3)。

    **`dataset_id`だけでは同一性を保証できない。** 同じ`impact-v1`と
    いう名前のまま、ケースを足したり文言を直したりできてしまう。
    その状態で「Aは0.98、Bは0.80」と並べると、**Providerの差なのか
    Datasetの差なのかが分からない**。

    空文字は「指紋を取っていない」であり、**照合できない**という
    意味である。Routingへ使う比較では、空を許さない
    (`ranking_for()`)——「たぶん同じDatasetだろう」で本番の経路を
    決めない。"""

    verification: Verification = Verification.UNVERIFIED

    schema_valid_rate: float = 0.0
    task_accuracy: float = 0.0
    failure_rate: float = 0.0
    latency_p50_ms: float = 0.0

    recorded_at: float = 0.0

    @property
    def dataset_key(self) -> tuple[str, str]:
        """**同じ土俵かどうか**の判定キー(§19「同一Dataset」)。"""
        return (self.dataset_id, self.dataset_hash)

    def is_usable_for_routing(self, *, now: float) -> bool:
        """この1件を、本番のProvider選択の根拠にしてよいか。"""
        return self.unusable_reason(now=now) is None

    def unusable_reason(self, *, now: float) -> str | None:
        """使えない場合、**なぜ**か。理由を言えないと調査できない。"""
        if self.verification is not Verification.REAL:
            return f"{self.provider}: 実測ではない({self.verification.value})"
        if self.dataset_size < _MIN_DATASET_SIZE:
            return f"{self.provider}: 件数不足({self.dataset_size} < {_MIN_DATASET_SIZE})"
        if not self.dataset_hash:
            # §3: 「たぶん同じDatasetだろう」で本番の経路を決めない。
            return f"{self.provider}: Datasetの指紋(dataset_hash)が無く、同一性を照合できない"
        if self.schema_valid_rate < _MIN_SCHEMA_VALID_RATE:
            # 下記`_MIN_SCHEMA_VALID_RATE`のコメント参照。
            return (
                f"{self.provider}: 構造化出力の成功率が低すぎる"
                f"({self.schema_valid_rate:.0%} < {_MIN_SCHEMA_VALID_RATE:.0%})"
            )
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
            "dataset_hash": self.dataset_hash,
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

        ---

        ## 同じDatasetで測ったものだけを比べる(011 §3)

        `dataset_id`と`dataset_hash`が一致する記録だけを1つの群と
        して扱う。異なるDatasetの数字を並べると、

            A: easy-dataset  0.98
            B: hard-dataset  0.80

        から「AはBより優秀」と読んでしまう。実際に分かるのは
        「easyはhardより易しい」だけである。

        群が複数ある場合は**最も多くのProviderを含む群**を使う。
        比較の土台として最も広いものを選ぶ、という意味である。
        同数なら記録が新しい方を採る。
        """
        now = self._now()
        usable = [run for run in self.runs_for(task) if run.is_usable_for_routing(now=now)]
        if len(usable) < _MIN_PROVIDERS_FOR_RANKING:
            return None

        groups: dict[tuple[str, str], list[BenchmarkRun]] = {}
        for run in usable:
            groups.setdefault(run.dataset_key, []).append(run)

        best = max(
            groups.values(),
            key=lambda runs: (len(runs), max(r.recorded_at for r in runs)),
        )
        if len(best) < _MIN_PROVIDERS_FOR_RANKING:
            return None

        # 正答率が高い順。同率ならlatencyが短い順。
        # **schema適合率はここでは使わない**——足切り(`unusable_reason`)で
        # 既に済んでいる。健全性は除外で、品質は順序で表す
        # (`AIRouter._order()`と同じ方針)。
        best.sort(key=lambda run: (-run.task_accuracy, run.latency_p50_ms))
        return tuple(run.provider for run in best)

    def exclusion_reasons(self, task: ForgeTask) -> tuple[str, ...]:
        """順位が付かない場合に、**何が足りないか**を返す。"""
        now = self._now()
        reasons = [
            reason
            for run in self.runs_for(task)
            if (reason := run.unusable_reason(now=now)) is not None
        ]
        usable_runs = [r for r in self.runs_for(task) if r.is_usable_for_routing(now=now)]
        if usable_runs and len(usable_runs) < _MIN_PROVIDERS_FOR_RANKING:
            reasons.append(
                f"実測が{len(usable_runs)}Providerのみ"
                f"(順位付けには{_MIN_PROVIDERS_FOR_RANKING}以上必要)"
            )
        # §3: Datasetが割れている場合、それ自体が「比べられない理由」である。
        keys = {run.dataset_key for run in usable_runs}
        if len(keys) > 1 and all(
            sum(1 for r in usable_runs if r.dataset_key == key) < _MIN_PROVIDERS_FOR_RANKING
            for key in keys
        ):
            named = ", ".join(sorted(key[0] for key in keys))
            reasons.append(
                f"Datasetが揃っていない({named})。同一Datasetでなければ"
                f"Provider差を比較できない"
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
