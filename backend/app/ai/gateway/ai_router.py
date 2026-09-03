"""Quota-Aware AI Router
(FORGE-QUOTA-AWARE-AI-ROUTER-008、2026-08-13)。

`docs/spec/FORGE-QUOTA-AWARE-AI-ROUTER-ARCH-REVIEW.md` §5・§14 の実装。

---

## これが解く問題

Geminiの無料枠が切れると**Forgeが使えなくなる**。Providerを増やす
だけでは解決しない——「今どれが使えるか」を判断する層が要る。

## 上位ロジックはProviderを知らない(§1)

RouterはTaskを受け取り、Providerを選び、失敗したら次を試す。
`ConversationEngine`も`PromptPipeline`もProvider名を知らないまま
でよい。Routerは`bind()`で「Taskに束ねたAdapter」を返すので、
呼び出し側から見ると**ただのAdapter**である。

## MVPで意図的にやらないこと

* **並列hedging**(§29): Quota倍消費・cost倍・privacy露出増。逐次。
* **Quota推定**(§9): `ESTIMATED`は型として持つが値を作らない。
  測っていない推定でRoutingすると、外れたとき原因が分からない。
* **Provider/Model二階層**(§11): 型は用意するが1:1で扱う。
  使われない抽象を増やさない。

## 品質による並べ替え(Phase Jで配線済み・データ待ち)

`_order()`は`BenchmarkEvidenceStore`を見る。ただし順位が返るのは、
**実APIで測った**記録が十分な件数・鮮度で2 Provider以上そろった
ときだけである。今はその記録が無いので、実際の順序は`catalog`の
宣言順のままである。

したがって現状を「品質で選んでいる」と表現してはならない。
効いていないのは**コードが無いからではなくデータが無いから**で
あり、実測を入れれば自動的に効き始める。

## Mockの扱い(§22)

Mockは**自動Routingの候補にならない**。明示的に要求されたときだけ
使える。全Cloud失敗 → Mock → 偽のToolという経路を、構造として塞ぐ。
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from app.ai.foundation.deadline import apply_deadline, supports_deadline
from app.ai.foundation.model_choice import apply_model, supports_model_choice
from app.ai.gateway.model_call_ledger import record_routed_result
from app.ai.gateway.ai_errors import ErrorKind, classify_exception
from app.ai.gateway.benchmark_evidence import BenchmarkEvidenceStore, default_evidence_store
from app.ai.gateway.learning_foundation import (
    ExperienceRecord,
    ExperienceStore,
    default_experience_store,
)
from app.ai.gateway.tasks import ForgeTask
from app.ai.gateway.local_promotion import LocalPromotionGate
from app.ai.gateway.provider_registry import (
    Deployment,
    ImplementationStatus,
    ProviderDefinition,
    QuotaScope,
    configured_providers,
    definition_for,
    provider_registry,
)
from app.ai.gateway.provider_state import Availability, ProviderStateStore

__all__ = [
    "AIRouter",
    "NoProviderAvailableError",
    "RouteAttempt",
    "RoutedResult",
    "Sensitivity",
    "TaskProfile",
    "TASK_PROFILES",
    "ModelDescriptor",
    "default_catalog",
    "default_router",
    "reset_default_router",
]


class Sensitivity(str, Enum):
    """このTaskの内容を外部へ出してよいか(§25)。

    **現状すべて`CLOUD_ALLOWED`である。**値としては1つしか使って
    いないが、型を今入れておくのは、`LOCAL_ONLY`のTaskが出たときに
    Routerが構造的に外部送信を選べないようにするためである。
    後から足すと、既存の全経路を見直すことになる。

    Privacy Policy自体は未完成(TECH_DEBT参照)。健康情報等の
    自動判定は**行っていない**。
    """

    CLOUD_ALLOWED = "cloud_allowed"
    LOCAL_ONLY = "local_only"


@dataclass(frozen=True)
class TaskProfile:
    """Taskが実行環境へ要求すること。"""

    task: ForgeTask
    requires_strict_schema: bool = True
    """構造化出力が壊れると成立しないTaskか。`True`なら、
    構造化出力に対応しないModelを候補から外す(§17)。"""

    sensitivity: Sensitivity = Sensitivity.CLOUD_ALLOWED
    latency_budget_ms: float = 45_000.0
    """このTask全体(fallback込み)の時間予算(§28)。
    「1 Provider 60秒 × 4回」のような体験を構造的に防ぐ。"""

    max_attempts: int = 3
    """試行するProviderの上限(§20)。無限fallbackを防ぐ。"""


# Task別のprofile。**すべてのTaskを列挙しない**——未登録のTaskは
# 既定profileで動く。列挙を強制すると、Taskを増やすたびにここを
# 更新し忘れて落ちる(TD37と同じ形の事故)。
TASK_PROFILES: dict[ForgeTask, TaskProfile] = {}

_DEFAULT_PROFILE = TaskProfile(task=ForgeTask.CONVERSATION_STEP)


def profile_for(task: ForgeTask) -> TaskProfile:
    configured = TASK_PROFILES.get(task)
    if configured is not None:
        return configured
    return TaskProfile(
        task=task,
        requires_strict_schema=_DEFAULT_PROFILE.requires_strict_schema,
        sensitivity=_DEFAULT_PROFILE.sensitivity,
        latency_budget_ms=_DEFAULT_PROFILE.latency_budget_ms,
        max_attempts=_DEFAULT_PROFILE.max_attempts,
    )


@dataclass(frozen=True)
class ModelDescriptor:
    """候補となるProvider/Modelの性質。

    **Provider公称値を大量に固定しない**(§12)。ここにあるのは、
    Routingの判断に実際に使う最小限だけである。品質スコアは
    Benchmark接続後に足す——測る前に「このModelは賢い」と
    書き込むと、それが既成事実になる。
    """

    provider: str
    supports_structured_output: bool = True
    is_local: bool = True
    """`True`ならAPI Quotaを消費しない。Localを優先する根拠になる。"""

    test_only: bool = False
    """Mock等。**自動Routingの候補にしない**(§22)。"""


@dataclass(frozen=True)
class RouteAttempt:
    provider: str
    ok: bool
    latency_ms: float
    error_kind: ErrorKind | None = None
    detail: str = ""

    retry_after_seconds: float | None = None
    """Providerが明示した待ち時間。不明なら`None`
    ——**`None`を「すぐ再試行してよい」と読まないこと**。

    R0.1で`RouteAttempt`へ載せた。以前は`_try_one`が失敗した直後に
    Provider状態を更新していたので、その場の変数で足りていた。
    Model候補を巡るようになると、状態更新は**全Model試し終えてから**
    になるため、値を持ち運ぶ場所が要る。"""

    model: str = ""
    structured_output_mode: str = ""
    """実際に呼んだModel名。**Adapterが名乗った場合のみ**入る。

    R0(2026-08-17)で追加。Experienceは「geminiが答えた」ではなく
    「gemini-2.0-flashが答えた」の粒度で残さないと、Model入れ替えの
    前後を区別できず、後から学習素材として使えない。

    名乗らないAdapter(テストのFake等)は空文字のままにする——
    Provider名で代用すると、**Model名が分かっているように見える**
    記録が出来上がる。分からないものは分からないままにする。"""


@dataclass(frozen=True)
class RoutedResult:
    value: dict[str, Any]
    task: ForgeTask
    provider_used: str
    attempts: tuple[RouteAttempt, ...] = field(default_factory=tuple)

    experience_ref: int = 0
    """この呼び出しについて`ExperienceStore`が付けた通し番号
    (0は「記録していない」、R0)。

    呼び出し側は、**後から分かった事実**——Validatorの合否、
    利用者が承認したか訂正したか——をこの番号へ書き足す。
    ここで返さないと、記録は残るが**一番価値のある信号だけが
    永久に付かない**。"""

    @property
    def structured_output_mode(self) -> str:
        """成功した試行が実際に使った構造化出力 mode。"""
        for attempt in reversed(self.attempts):
            if attempt.ok:
                return attempt.structured_output_mode
        return ""

    @property
    def used_fallback(self) -> bool:
        return len(self.attempts) > 1

    @property
    def latency_ms(self) -> float:
        """この結果を得るまでに掛かった合計時間。

        **失敗した試行も含む**。利用者が待った時間はfallbackを含めた
        合計であり、成功した1回だけを報告すると体感より速く見える。
        """
        return sum(a.latency_ms for a in self.attempts)


# 残りがこれ未満なら、新しい試行を**始めない**。始めても意味のある
# 応答は返らず、待ち時間だけが伸びる(011 §4)。
_MIN_USEFUL_ATTEMPT_MS = 250.0


class _BudgetTooTight(RuntimeError):
    """残り予算に収まらないので試行を始めなかった(011 §4)。

    **Providerの失敗ではない**ので、Circuit BreakerにもBenchmarkにも
    記録しない。除外理由としてだけ残す。
    """


class NoProviderAvailableError(RuntimeError):
    """使えるProviderが1つも無かった。

    **理由を必ず持つ**。「使えるProviderがありません」だけでは、
    枠切れなのか設定ミスなのかネットワークなのか分からない。
    """

    def __init__(
        self, task: ForgeTask, attempts: tuple[RouteAttempt, ...], excluded: tuple[str, ...]
    ) -> None:
        self.task = task
        self.attempts = attempts
        self.excluded = excluded
        tried = ", ".join(f"{a.provider}({a.error_kind.value if a.error_kind else '?'})" for a in attempts)
        reasons = "; ".join(excluded)
        super().__init__(
            f"task={task.value} で利用可能なProviderがありません。"
            f"試行: [{tried or 'なし'}] 除外: [{reasons or 'なし'}]"
        )

    @property
    def is_quota_exhaustion(self) -> bool:
        """**全部が枠切れだったか**(R0.1、2026-08-17)。

        呼び出し側が利用者へ何と言うかを変えるための情報である。
        枠切れとサーバ障害では、待つべき時間も、打つべき手も違う:

            サーバ障害 → 数分待てば直る
            枠切れ     → 実測したGemini無料枠は**1日20回/Model**。
                         「しばらく待って」は嘘になりうる。

        `attempts`が空(候補が1つも無かった)の場合は`False`——
        呼んでもいないものを枠切れとは言わない。
        """
        return bool(attempts_all_quota(self.attempts))


def attempts_all_quota(attempts: tuple[RouteAttempt, ...]) -> bool:
    """試行がすべて枠切れだったか。1件も無ければ`False`。"""
    return bool(attempts) and all(
        a.error_kind is ErrorKind.QUOTA_EXHAUSTED for a in attempts
    )


class AIRouter:
    """Taskに対して、使えるProviderを選び、失敗したら次を試す。

    `resolve`は「Provider名 → Adapter」の解決関数。Router自身は
    具体的なProvider実装を一切importしない(§1の境界)。
    """

    def __init__(
        self,
        resolve: Callable[[str], Any],
        catalog: tuple[ModelDescriptor, ...],
        *,
        state_store: ProviderStateStore | None = None,
        evidence: BenchmarkEvidenceStore | None = None,
        experience: ExperienceStore | None = None,
        now: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._resolve = resolve
        self._catalog = catalog
        self._states = state_store or ProviderStateStore(now=now)
        # Phase J: 実測されたTask別品質。`None`なら宣言順のまま
        # (テストが並べ替えを意図的に切るために使う)。
        self._evidence = evidence
        # R0: 本番のAI呼び出しをExperienceへ残す先。`None`なら記録しない
        # ——ただし**既定はNoneではない**(`default_router()`が既定Storeを
        # 渡す)。記録しないのはテストが明示的にそうした場合だけである。
        self._experience = experience
        self._now = now
        self._monotonic = monotonic
        # 017A §7: Local昇格の判定。**同じEvidenceを見る**——別のStoreを
        # 渡せるようにすると、順位付けと昇格判定が別の実測で動きうる。
        self._promotion_gate = LocalPromotionGate(evidence)

    @property
    def states(self) -> ProviderStateStore:
        return self._states

    @property
    def experience(self) -> ExperienceStore | None:
        """記録先。**後から分かった事実を書き足す側**が使う(R0)。

        `None`は「このRouterは記録しない」であり、テストが明示的に
        そうした場合だけ起きる。"""
        return self._experience

    # -- 候補選び ---------------------------------------------------------

    def candidates_for(self, task: ForgeTask) -> tuple[tuple[ModelDescriptor, ...], tuple[str, ...]]:
        """`(候補, 除外理由)`を返す。**除外理由も返す**のが要点で、
        「使えるものが無い」となったときに調査できるようにする。"""
        profile = profile_for(task)
        now = self._now()
        eligible: list[ModelDescriptor] = []
        excluded: list[str] = []

        for model in self._catalog:
            if model.test_only:
                # §22: Mockは自動Routingに載せない。明示要求は別経路。
                excluded.append(f"{model.provider}: テスト専用のため自動選択しない")
                continue
            if profile.requires_strict_schema and not model.supports_structured_output:
                excluded.append(f"{model.provider}: 構造化出力に非対応")
                continue
            if profile.sensitivity is Sensitivity.LOCAL_ONLY and not model.is_local:
                excluded.append(f"{model.provider}: このTaskは外部送信不可")
                continue

            state = self._states.get(model.provider)
            if not state.is_selectable(now=now):
                reason = state.exclusion_reason(now=now)
                if reason:
                    excluded.append(reason)
                continue
            eligible.append(model)

        return tuple(self._order(eligible, task)), tuple(excluded)

    def _order(self, models: list[ModelDescriptor], task: ForgeTask) -> list[ModelDescriptor]:
        """並べ替えの根拠は**実測されたTask別品質だけ**である。

        **健全性では並べ替えない(実装して考え直した点)**

        最初は「Localを先に(Quotaを消費しないから)」「連続失敗が
        少ない順」「latencyが短い順」で並べ替えていた。実際にテストを
        書いて走らせたところ、2つの問題が出た:

        1. **Circuit Breakerが発動しなくなる**。1回失敗したProviderが
           即座に後回しになるため、連続失敗が積み上がらず、OPENへ
           到達しない。健全性を「並べ替え」と「除外」の両方で表すと、
           片方がもう片方を無効化する。
        2. **Local優先は根拠が無い**。§5は「固定ルールで決め打ちせず
           Benchmarkで決定する」と明示している。Benchmarkが無いのに
           Localを優先するのは、**測っていない品質を賭けてQuotaを
           節約している**だけで、Product Qualityを壊しうる(§21)。

        したがって:

        * 健全性 = **除外**でのみ表す(候補に入るか入らないか)
        * 品質   = **実測があるときだけ**並べ替えに使う
        * それ以外 = `catalog`の宣言順(運用側が意図した優先順位)

        **Phase J(FORGE-AI-FOUNDATION-010)で品質側を配線した。**
        `BenchmarkEvidenceStore.ranking_for()`は、実APIで測った記録が
        十分な件数・十分な鮮度で2 Provider以上そろったときだけ順位を
        返す。そろっていなければ`None`で、宣言順のまま動く。

        つまり**今これが効かないのは、コードが無いからではなく
        データが無いからである**。実測を入れれば自動的に効き始める
        ——「基盤はあるのに本番では使っていない」を3度繰り返した
        ので、今回は逆の状態(配線済み・データ待ち)にしてある。

        Test Doubleで測った数字は`ranking_for()`が弾く。Doubleは
        成功するAdapterをいくらでも作れるので、それがRoutingへ
        流れ込むと**測っていないもので本番の経路が決まる**。
        """
        if self._evidence is None:
            return list(models)

        ordered = list(models)
        ranking = self._evidence.ranking_for(task)
        if ranking:
            # 順位に載っていないProviderは**後ろへ回すだけで落とさない**。
            # 測っていないことは、悪いことの証拠ではない。
            priority = {provider: index for index, provider in enumerate(ranking)}
            ordered = sorted(
                ordered, key=lambda model: priority.get(model.provider, len(priority))
            )

        return self._local_first(ordered, task)

    def _local_first(self, models: list[ModelDescriptor], task: ForgeTask) -> list[ModelDescriptor]:
        """**製品水準を満たしたLocalを前へ出す**(FORGE-017A §7)。

        ---

        ## Best Score Wins をやめた

        上の`ranking_for()`だけで並べると、Cloudが1点でも高ければ毎回
        Cloudが選ばれる。**Localは永久に使われない。** それは
        「Local First」ではない。

        かといって「Localだから先」に戻すと、上のdocstringが退けた
        「測っていない品質を賭けてQuotaを節約する」へ戻る。

        そこで**Quality Gate**にした——`LocalPromotionGate`が
        「製品として通用する水準か」を実測から判定し、**満たしたものだけ**
        を前へ出す。一番良いものではなく、十分に良いかで決める。

        満たしていれば、Cloudが少し上でもLocalを選ぶ理由がある
        (Quotaを使わない・データを外へ出さない)。満たしていなければ
        従来どおりCloudへ落ちる。

        ## いま何件通るか

        **0件である。** Localのbenchmark記録が1件も無い(実測)。
        つまりこの配線は**今は何も変えない**。データが入れば効き始める
        ——「基盤はあるのに本番では使っていない」を繰り返さないため、
        配線済み・データ待ちの状態にしてある(`_order()`と同じ方針)。
        """
        promoted = set(
            self._promotion_gate.promoted_providers(
                task,
                [(model.provider, model.is_local) for model in models],
                now=self._now(),
            )
        )
        if not promoted:
            return models
        # **安定ソート。** 昇格したLocal同士の順序と、Cloud同士の順序は
        # 上で決めたものを保つ。
        return sorted(models, key=lambda model: 0 if model.provider in promoted else 1)

    # -- 実行 -------------------------------------------------------------

    def generate(
        self,
        task: ForgeTask,
        prompt: str,
        response_schema: dict[str, Any],
        *,
        provider: str | None = None,
    ) -> RoutedResult:
        """Taskを実行し、**起きたことをExperienceへ残す**。

        ---

        ## なぜ記録をここに置くのか(R0、2026-08-17)

        Forgeは同じ失敗を4回繰り返している——`ModelGateway`(TD59)、
        `classify_correction`(007 §10)、`/generate`・`/update`の
        Router迂回(010 Phase B)、`ExperienceStore`(TD64)。いずれも
        **基盤は作ったが、本番から呼ぶ人がいなかった**。

        共通の形は「呼び出し側が忘れずに呼ぶ」設計になっていたこと
        である。忘れずに呼ばれる保証が無いものは、忘れられる。

        だからここに置く。Phase Bの Anti-Bypass Regression が
        「本番のAI呼び出しは**必ず**Routerを通る」ことを証明済みで
        あり、そのRouterの唯一の入口がこのメソッドである。
        新しいEndpointが増えても、記録を書き忘れることが**できない**。

        `provider`を明示した場合、**Routingを迂回する**。HTTP APIの
        利用者が選んだProviderをRouterが勝手に上書きしないため
        (既存契約の維持)。Mockが使えるのもこの経路だけである。
        """
        try:
            result = self._route(task, prompt, response_schema, provider=provider)
        except NoProviderAvailableError as exc:
            # **失敗も記録する。** 成功だけ貯めると、
            # 「Providerは常に上手くいっている」という記録が出来上がる。
            self._note_experience(
                task, provider_used=exc.attempts[-1].provider if exc.attempts else "none",
                model=exc.attempts[-1].model if exc.attempts else "",
                attempts=exc.attempts, structured_output_valid=False,
            )
            raise
        ref = self._note_experience(
            task, provider_used=result.provider_used,
            model=next(
                (a.model for a in reversed(result.attempts) if a.provider == result.provider_used),
                "",
            ),
            attempts=result.attempts, structured_output_valid=True,
        )
        return replace(result, experience_ref=ref)

    def _note_experience(
        self,
        task: ForgeTask,
        *,
        provider_used: str,
        model: str,
        attempts: tuple[RouteAttempt, ...],
        structured_output_valid: bool,
    ) -> int:
        """1回の呼び出しをExperienceへ残す。**本文は渡らない**
        ——`ExperienceRecord`にはpromptも応答も入れる場所が無い
        (006 §22の担保、`learning_foundation.py`参照)。

        `latency_ms`は**失敗した試行も含む合計**である。利用者が
        待った時間はfallbackを含めた合計であり、成功した1回だけを
        記録すると体感より速い記録が残る。
        """
        if self._experience is None:
            return 0
        stored = self._experience.record(
            ExperienceRecord(
                task=task, provider=provider_used, model=model,
                structured_output_valid=structured_output_valid,
                latency_ms=sum(a.latency_ms for a in attempts),
                used_fallback=len(attempts) > 1,
            )
        )
        return stored.ref

    def _route(
        self,
        task: ForgeTask,
        prompt: str,
        response_schema: dict[str, Any],
        *,
        provider: str | None = None,
    ) -> RoutedResult:
        """候補を巡回して1つ成功させる。**記録はしない**
        (`generate()`が唯一の記録地点である)。"""
        if provider is not None:
            return self._generate_direct(task, prompt, response_schema, provider)

        profile = profile_for(task)
        eligible, excluded = self.candidates_for(task)
        attempts: list[RouteAttempt] = []
        started = self._monotonic()
        attempted: set[str] = set()

        for model in eligible:
            if len(attempts) >= profile.max_attempts:
                excluded = (*excluded, f"試行上限({profile.max_attempts}回)に達した")
                break

            # **残り予算を実際に計算する**(011 §4)。
            #
            # 010は`elapsed >= budget`しか見ていなかったので、
            # 「まだ0秒しか経っていない」→ Provider呼び出し開始 →
            # そのProviderのtimeout(60〜120秒)まで待つ、が成立した。
            # 45秒という宣言が実行を何も拘束していなかった。
            elapsed_ms = (self._monotonic() - started) * 1000.0
            remaining_ms = profile.latency_budget_ms - elapsed_ms
            if remaining_ms <= _MIN_USEFUL_ATTEMPT_MS:
                # §28: 何回もfallbackして数分待たせない。
                # 残りが極端に少ないなら**始めない**——始めても
                # 意味のある応答は返らず、待ち時間だけが伸びる。
                excluded = (*excluded, f"時間予算({profile.latency_budget_ms:.0f}ms)を使い切った")
                break
            if model.provider in attempted:
                continue  # §20: 同じProviderを二度試さない
            attempted.add(model.provider)

            state = self._states.get(model.provider)
            if state.availability is Availability.CIRCUIT_OPEN:
                self._states.note_half_open(model.provider)

            attempt, result = self._try_one(
                model.provider, prompt, response_schema, remaining_ms=remaining_ms
            )
            if attempt is None:
                # 予算に入りきらないので**始めなかった**。試行として
                # 数えない(Providerは何も悪くない)が、理由は残す。
                excluded = (*excluded, str(result))
                continue
            attempts.append(attempt)
            if result is not None:
                return RoutedResult(
                    value=result, task=task, provider_used=model.provider,
                    attempts=tuple(attempts),
                )
            if attempt.error_kind is not None and not attempt.error_kind.should_try_other_providers:
                # §19: Forge側の誤り。Providerを変えても同じ結果になる。
                break

        raise NoProviderAvailableError(task, tuple(attempts), tuple(excluded))

    def _generate_direct(
        self, task: ForgeTask, prompt: str, response_schema: dict, provider: str
    ) -> RoutedResult:
        # 明示指定の直接実行。`remaining_ms`は渡さない——Routingを
        # 迂回する経路であり、候補を巡回しないので配分すべき予算が無い。
        attempt, result = self._try_one(provider, prompt, response_schema)
        if result is None:
            assert attempt is not None  # noqa: S101 — remaining_ms=Noneなら必ず試行する
            raise NoProviderAvailableError(task, (attempt,), ())
        assert attempt is not None  # noqa: S101 — 同上
        return RoutedResult(
            value=result, task=task, provider_used=provider, attempts=(attempt,),
        )

    def _try_one(
        self,
        provider: str,
        prompt: str,
        response_schema: dict,
        *,
        remaining_ms: float | None = None,
    ) -> tuple[RouteAttempt | None, dict[str, Any] | None]:
        """1 Providerを試す。**そのProviderのModel候補を順に使う。**

        `remaining_ms`があれば、**Task全体の残り時間で締める**
        (011 §4)。締められないAdapterの場合、入りきらないと分かって
        いる試行は**始めない**——始めれば予算を超えることが確定して
        いるからである。

        戻り値の第1要素が`None`なら「始めなかった」を意味し、
        第2要素に理由(文字列)が入る。試行として数えないのは、
        Providerが失敗したわけではないためである(Circuit Breakerや
        Benchmarkの記録を汚さない)。

        ---

        ## Model候補を巡るのはここである(R0.1、2026-08-17)

        **Providerの外から見た振る舞いは変わらない。** 呼び出し側にも
        Circuit Breakerにも「geminiを1回試した」としか見えず、
        成否だけが伝わる。Model単位でCircuit Breakerを開いたり
        Quotaを数えたりはしない——それらの識別键は`provider_id`で
        あって、Modelではない(011 §1)。

        巡るのは**同じProviderの別Modelなら通りうる失敗**のときだけ
        である(`ErrorKind.another_model_may_work`)。認証エラーや
        Forge側のschema誤りでModelを変えても、鍵もschemaも同じなので
        意味が無い。
        """
        started = self._monotonic()
        try:
            adapter = self._resolve(provider)
            adapter = self._fit_to_budget(adapter, provider, remaining_ms)
        except _BudgetTooTight as tight:
            return None, str(tight)
        except Exception as exc:  # noqa: BLE001 — 解決失敗も分類して次へ
            error = classify_exception(exc, provider)
            self._states.record_failure(
                provider, error.kind, retry_after_seconds=error.retry_after_seconds
            )
            return RouteAttempt(
                provider=provider, ok=False,
                latency_ms=(self._monotonic() - started) * 1000.0,
                error_kind=error.kind, detail=error.message,
            ), None

        last: RouteAttempt | None = None
        for candidate in self._model_candidates(provider, adapter):
            attempt, value = self._call_once(
                provider, adapter, candidate, prompt, response_schema, started
            )
            if value is not None:
                self._states.record_success(provider, latency_ms=attempt.latency_ms)
                return attempt, value
            last = attempt
            assert attempt.error_kind is not None  # noqa: S101 — 失敗なら必ず分類済み
            if not self._another_model_may_work(provider, attempt.error_kind):
                break
            # 予算を食い破らない(011 §4)。残りが無ければ、次のModelは
            # 始めずにここまでの失敗を返す——始めても意味のある応答は
            # 返らず、待ち時間だけが伸びる。
            if remaining_ms is not None:
                spent = (self._monotonic() - started) * 1000.0
                if remaining_ms - spent <= _MIN_USEFUL_ATTEMPT_MS:
                    break

        assert last is not None  # noqa: S101 — 候補は必ず1つ以上ある(下記参照)
        # **Providerの失敗として記録するのは、全Modelで駄目だったときだけ。**
        # Model単位でCircuit Breakerを開くと、識別键がProviderから
        # ずれる(011 §1)。
        self._states.record_failure(
            provider, last.error_kind or ErrorKind.UNKNOWN,
            retry_after_seconds=last.retry_after_seconds,
        )
        return last, None

    def _call_once(
        self,
        provider: str,
        adapter: Any,
        model_name: str,
        prompt: str,
        response_schema: dict,
        started: float,
    ) -> tuple[RouteAttempt, dict[str, Any] | None]:
        """1 Modelで1回呼ぶ。**状態は更新しない**——Provider状態の
        更新は`_try_one`が全Model試し終えてから1回だけ行う。"""
        bound = apply_model(adapter, model_name)
        # 解決できたAdapterだけがModel名を名乗れる。名乗らないものを
        # Provider名で代用しない(分からないものは分からないまま)。
        model = str(getattr(bound, "model", "") or "")
        try:
            value = bound.complete_structured(prompt, response_schema)
        except Exception as exc:  # noqa: BLE001 — 分類して次の候補へ進むため
            error = classify_exception(exc, provider)
            return RouteAttempt(
                provider=provider, ok=False,
                latency_ms=(self._monotonic() - started) * 1000.0,
                error_kind=error.kind, detail=error.message, model=model,
                retry_after_seconds=error.retry_after_seconds,
            ), None

        latency = (self._monotonic() - started) * 1000.0
        if not isinstance(value, dict):
            # 構造化出力が壊れている。Provider障害として扱う。
            return RouteAttempt(
                provider=provider, ok=False, latency_ms=latency,
                error_kind=ErrorKind.STRUCTURED_OUTPUT_FAILURE,
                detail=f"dictではなく{type(value).__name__}が返った", model=model,
            ), None

        return RouteAttempt(
            provider=provider, ok=True, latency_ms=latency, model=model,
            structured_output_mode=str(
                getattr(bound, "last_structured_output_mode", "") or ""
            ),
        ), value

    def _another_model_may_work(self, provider: str, kind: ErrorKind) -> bool:
        """この失敗のあと、同じProviderの別Modelを試す意味があるか。

        大半は`ErrorKind`だけで決まる。**枠切れだけがProviderの宣言に
        依存する**——枠がModel単位で切れるのか、鍵/プロジェクト単位で
        切れるのかは、相手の課金設計であってエラーの種類ではない。

        実機で読んだGeminiの429本文:

            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
            "quotaValue": 20

        **Modelごとに1日20回**である。ここで諦めると、まだ20回残って
        いる別Modelを持っているのに「AIが使えません」と言うことになる。

        逆に、枠が鍵単位で切れる相手にModelを巡ると、確実に失敗する
        呼び出しを積むだけである。だから既定(`UNKNOWN`)では巡らない
        ——分からないものを楽観側へ倒さない。
        """
        if kind is ErrorKind.QUOTA_EXHAUSTED:
            definition = definition_for(provider)
            return definition is not None and definition.quota_scope is QuotaScope.PER_MODEL
        return kind.another_model_may_work

    def _model_candidates(self, provider: str, adapter: Any) -> tuple[str, ...]:
        """そのProviderで試すModel名を、順番に返す。

        **必ず1つ以上返す。** 先頭は空文字(=Adapterの既定Model)で
        あり、Model候補が宣言されていないProviderや、Modelを差し替え
        られないAdapterでは、これ1つだけになる——つまり**従来と
        まったく同じ動き**である。

        2つ目以降はRegistryの`models`宣言から採る。宣言は元々
        「診断とBenchmarkの対象指定のため」に持っていたもので、
        Routingには使っていなかった。実機で「既定Modelだけが混雑で
        503を返し、同じProviderの別Modelは応答していた」という状態に
        当たったので、実行にも使うようにした。

        既定Modelと同名のものは落とす(同じ相手へ二度聞かない)。
        """
        default = str(getattr(adapter, "model", "") or "")
        if not supports_model_choice(adapter):
            return ("",)
        definition = definition_for(provider)
        if definition is None:
            return ("",)
        rest = tuple(m for m in definition.models if m and m != default)
        return ("", *rest)

    def _fit_to_budget(
        self, adapter: Any, provider: str, remaining_ms: float | None
    ) -> Any:
        """残り予算をAdapterへ反映する(011 §4)。

        2つの場合がある:

        * **deadlineを受け取れるAdapter** — 残り時間で締めた複製を使う。
          `min(provider_timeout, remaining)`はAdapter側が取る。
        * **受け取れないAdapter** — Registryの`nominal_timeout_seconds`と
          比べ、入りきらないなら**始めない**。黙って予算超過を許すと、
          45秒と宣言しておいて120秒待たせることになる。

        Mockのように即答するものは`nominal_timeout_seconds`が小さいので、
        残り予算が少なくても通る。
        """
        if remaining_ms is None:
            return adapter
        remaining_seconds = remaining_ms / 1000.0
        if supports_deadline(adapter):
            return apply_deadline(adapter, remaining_seconds)

        definition = definition_for(provider)
        if definition is None:
            # Registryに宣言が無い(テストのFake等)。**判断の根拠が無い**。
            # 根拠なく除外すると、実際には即答するAdapterまで
            # 締め出すことになる——予算を守るための仕組みが、
            # 予算内で終わるものを止めるのは本末転倒である。
            return adapter

        nominal = definition.nominal_timeout_seconds
        if nominal > remaining_seconds:
            raise _BudgetTooTight(
                f"{provider}: 残り時間{remaining_seconds:.1f}秒では足りない"
                f"(想定{nominal:.0f}秒。このAdapterは締め切りを受け取れない)"
            )
        return adapter

    # -- 呼び出し側から見た顔 ---------------------------------------------

    def bind(self, task: ForgeTask, *, provider: str | None = None) -> "_BoundAdapter":
        """Taskに束ねたAdapterを返す。

        呼び出し側(`ConversationEngine`等)から見ると**ただのAdapter**
        であり、Providerの存在を知らないままでよい(§1・§46)。
        既存コードを1行も変えずにRouterを差し込めるのは、この形の
        おかげである。
        """
        return _BoundAdapter(self, task, provider)


@dataclass
class _BoundAdapter:
    """`LLMAdapter`と同じ形をした、Router経由の実行口。

    **`last_provider_used`を持つ理由**(FORGE-AI-FOUNDATION-010 Phase B)。

    以前`/converse`は、`ProviderRouter.default_provider_name()`が返した
    名前をそのままHTTPレスポンスの`provider`として返していた。これは
    「既定として選ばれるはずの名前」であって、**実際に応答を生成した
    Providerではない**。Routerがfallbackした場合も、運用者の指定を
    Routerが無視した場合も、レスポンスは嘘をつく。

    実際に使われた名前はRouterだけが知っている。呼び出し側が
    正直に報告できるよう、束ねたAdapter自身に記録させる。

    frozenを外しているのはこの記録のためである。インスタンスは
    リクエストごとに`bind()`で作られるので、共有されない。
    """

    router: AIRouter
    task: ForgeTask
    provider: str | None = None

    provider_name: str = "router"

    last_provider_used: str | None = field(default=None, init=False)
    last_model_used: str = field(default="", init=False)
    last_structured_output_mode: str = field(default="", init=False)
    """直近の`complete_structured()`で**実際に**応答を返したProvider名。
    まだ呼ばれていなければ`None`。"""

    experience_refs: tuple[int, ...] = field(default=(), init=False)
    """このAdapterを通した呼び出しの`ExperienceRecord`番号(R0)。

    **複数になる。** 1つのForge Documentは Cognitive Pipeline の
    十数段の呼び出しから出来ており、どの段が良かった/悪かったかは
    最終的なValidator結果からは分けられない。分けられないものを
    分けて記録すると嘘になるので、寄与した全部を持ち、同じ結果を
    後から付ける(`ExperienceStore.note_validator_outcome()`)。
    """

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        result = self.router.generate(
            self.task, prompt, response_schema, provider=self.provider
        )
        # TD104(2026-09-03): **ここが Model 呼び出しの唯一の口である。**
        # 数え忘れた経路が「0回」に見えると、間違いが楽観側へ倒れる
        # （呼んだのに呼んでいないことになる）ので、呼び出し側では
        # なくここで数える。記録先が無ければ素通りする。
        record_routed_result(result)
        self.last_provider_used = result.provider_used
        self.last_model_used = next(
            (
                attempt.model
                for attempt in reversed(result.attempts)
                if attempt.ok and attempt.provider == result.provider_used
            ),
            "",
        )
        self.last_structured_output_mode = result.structured_output_mode
        if result.experience_ref:
            self.experience_refs = (*self.experience_refs, result.experience_ref)
        return result.value


# ---------------------------------------------------------------------------
# 既定Catalog(FORGE-QUOTA-AWARE-AI-ROUTER-008 §36、
#             FORGE-AI-FOUNDATION-010 Phase Bで環境依存へ修正)
# ---------------------------------------------------------------------------
#
# **Providerを増やせば良くなるとは限らない**(§36)。Adapter保守・API変更・
# Secrets・Observabilityが増える。MVPは「実際に動く実装があるもの」だけを
# 載せ、Router Contractの正しさを証明することを優先する。
#
# 現在Adapterが実在するのは2つだけである:
#
#   gemini — 実装済み(`GeminiProvider`)
#   local  — 実装済み(`LocalModelProvider`、OpenAI互換)
#
# `openai`/`claude`/`oss`等は`NotImplementedError`を投げるスタブであり、
# 候補に入れると必ず失敗して試行予算を食う。**動かないものを候補に
# 並べない。**

def _descriptor_from(definition: ProviderDefinition) -> ModelDescriptor:
    """宣言(`ProviderDefinition`)からRouting用の性質へ落とす。

    Registryが持つ情報のうち、Routerが**判断に実際に使う**ものだけを
    取り出す。Registry全体をRouterへ渡さないのは、使わない属性まで
    見えると、そのうち使い始めてしまうためである(§12)。
    """
    return ModelDescriptor(
        provider=definition.provider_id,
        is_local=definition.deployment is Deployment.LOCAL,
        supports_structured_output=definition.supports_structured_output,
        test_only=definition.test_only,
    )


def _descriptor_for(provider: str) -> ModelDescriptor:
    """未知の名前は**Cloud・構造化出力あり**として扱う。

    Localと決めつけると`LOCAL_ONLY`のTaskへ誤って載せてしまう。
    分からないものは「外部かもしれない」側へ倒す。
    """
    known = definition_for(provider)
    if known is not None:
        return _descriptor_from(known)
    return ModelDescriptor(provider=provider, is_local=False, supports_structured_output=True)


def default_catalog() -> tuple[ModelDescriptor, ...]:
    """実運用の候補一覧を、**その環境で実際に使えるものから**組み立てる。

    順序が優先順位である(`AIRouter._order()`参照)。

    ---

    ## なぜ固定リストを止めたか(Phase Bで見つけた実バグ)

    以前ここは`(gemini, local, mock)`のハードコードだった。その結果、
    運用者が`FORGE_DEFAULT_PROVIDER=mock`と明示していても**Routerは
    それを読まず**、`/converse`の会話ステップを実Geminiへ送っていた。
    HTTPレスポンスは`provider: "mock"`, `simulated: true`と返しており、
    **利用者の入力が外部Cloudへ出ているのに、Mockだと表示していた**。
    実機で再現・確認した(Router state: `gemini available successes=1`)。

    「Silent Mock fallbackは禁止」(FORGE-HANDOFF-LOCAL-AI-UX-004 §9)の
    裏返しで、**Silent Cloud送信**の方が害が大きい。Providerの決定は
    1箇所でなければならない。

    ## 決定順序(すべて決定的、AI判断は入らない)

    1. `FORGE_DEFAULT_PROVIDER`があれば**それだけ**を候補にする。
       運用者の明示指定をRouterが上書きしない。このとき`test_only`は
       解除する——Mockが自動選択されないのは「黙って選ばれない」ため
       (§22)であって、名指しされた場合はその限りではない。
       ただし利用者へは`simulated: true`として必ず伝える。
    2. それ以外は`configured_providers()`——Registryのうち
       **実装があり・設定が揃っていて・テスト専用でない**もの——を
       宣言順に並べる(Phase F Auto Discovery)。鍵の無いCloud
       Providerや未実装スタブは、ここで自動的に落ちる。
    3. `test_only`のProviderは末尾に残す。自動選択はされないが、
       `provider`を明示したリクエストの解決先としては必要である。

    候補が`local`だけの環境(鍵なし・Runtimeなし)では
    `NoProviderAvailableError`になる。これは**正しい失敗**である
    ——偽のToolをMockで作って「できました」と言わない(§33)。

    ## Registryが唯一の宣言である(Phase C)

    以前ここには`_KNOWN_MODELS`という独自の表と、`GEMINI_API_KEY`という
    環境変数名の直書きがあった。Providerを1つ足すには
    `ProviderRouter._providers`・`_KNOWN_MODELS`・この関数の3箇所を
    揃える必要があり、揃え忘れてもテストは通った(TD37と同じ形)。
    今は`provider_registry.py`だけが宣言であり、ここは導出する。
    """
    pinned = os.environ.get("FORGE_DEFAULT_PROVIDER", "").strip()
    if pinned:
        return (replace(_descriptor_for(pinned), test_only=False),)

    catalog = [_descriptor_from(d) for d in configured_providers()]
    catalog.extend(
        _descriptor_from(d)
        for d in provider_registry()
        if d.test_only and d.implementation_status is ImplementationStatus.IMPLEMENTED
    )
    return tuple(catalog)


_default_router: AIRouter | None = None


def default_router() -> AIRouter:
    """アプリ全体で共有するRouter。

    Provider状態(枠切れ・Circuit Breaker)は**プロセス内で共有する**
    必要がある——リクエストごとに作り直すと、枠切れを毎回学習し直して
    しまい、Quotaを無駄にする。

    既知の制限: 複数ワーカー構成では共有されない(`ConversationStore`と
    同じ、TD41)。Catalogは**最初の呼び出し時の環境**で固定される
    (プロセス起動後に環境変数を変える運用は想定していない。テストは
    `reset_default_router()`で作り直すこと)。
    """
    global _default_router  # noqa: PLW0603 — プロセス内Singleton(既存のStoreと同じ方針)
    if _default_router is None:
        from app.ai.runtime.provider_router import ProviderRouter  # noqa: PLC0415 — 循環import回避

        _default_router = AIRouter(
            resolve=ProviderRouter().resolve,
            catalog=default_catalog(),
            # Phase J: 実測がそろえば品質順になる。今は記録が無いので
            # 宣言順のまま動く(`_order()`参照)。
            evidence=default_evidence_store(),
            # R0: **本番のAI呼び出しをここでExperienceへ残す。**
            # これを渡さなければ、`ExperienceStore`は今までどおり
            # 「実装はあるが本番から一度も呼ばれない」ままである
            # (Product Direction §7が名指しした状態)。
            experience=default_experience_store(),
        )
    return _default_router


def reset_default_router() -> None:
    """共有Routerを破棄する(テスト用)。

    Catalogが環境変数に依存するようになったため、環境を差し替える
    テストは**Routerも作り直さなければ**古いCatalogを見続ける。
    """
    global _default_router  # noqa: PLW0603
    _default_router = None
