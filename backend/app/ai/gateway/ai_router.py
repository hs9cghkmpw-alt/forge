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
* **品質スコアによる選択**(§13): Benchmark未接続。現状の並べ替えは
  **可用性**による。これを「品質で選んでいる」と表現しない。
* **Provider/Model二階層**(§11): 型は用意するが1:1で扱う。
  使われない抽象を増やさない。

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

from app.ai.gateway.ai_errors import ErrorKind, classify_exception
from app.ai.gateway.tasks import ForgeTask
from app.ai.gateway.provider_registry import (
    PROVIDER_REGISTRY,
    Deployment,
    ImplementationStatus,
    ProviderDefinition,
    configured_providers,
    definition_for,
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


@dataclass(frozen=True)
class RoutedResult:
    value: dict[str, Any]
    task: ForgeTask
    provider_used: str
    attempts: tuple[RouteAttempt, ...] = field(default_factory=tuple)

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
        now: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._resolve = resolve
        self._catalog = catalog
        self._states = state_store or ProviderStateStore(now=now)
        self._now = now
        self._monotonic = monotonic

    @property
    def states(self) -> ProviderStateStore:
        return self._states

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

        return tuple(self._order(eligible)), tuple(excluded)

    def _order(self, models: list[ModelDescriptor]) -> list[ModelDescriptor]:
        """並べ替え……を**しない**。宣言された`catalog`の順を使う。

        **なぜ並べ替えないのか(実装して考え直した点)**

        最初は「Localを先に(Quotaを消費しないから)」「連続失敗が
        少ない順」「latencyが短い順」で並べ替えていた。実際にテストを
        書いて走らせたところ、2つの問題が出た:

        1. **Circuit Breakerが発動しなくなる**。1回失敗したProviderが
           即座に後回しになるため、連続失敗が積み上がらず、OPENへ
           到達しない。健全性を「並べ替え」と「除外」の両方で表すと、
           片方がもう片方を無効化する。
        2. **Local優先は根拠が無い**。§5は「固定ルールで決め打ちせず
           Benchmarkで決定する」と明示している。Benchmarkが無い現状で
           Localを優先するのは、**測っていない品質を賭けてQuotaを
           節約している**だけで、Product Qualityを壊しうる(§21)。

        したがってMVPでは:

        * 順序 = `catalog`の宣言順(運用側が意図した優先順位)
        * 健全性 = **除外**でのみ表す(候補に入るか入らないか)

        latencyは記録するが選択には使わない。Task別品質スコアが
        Benchmarkから入ったとき、初めてここに並べ替えが戻る。
        """
        return list(models)

    # -- 実行 -------------------------------------------------------------

    def generate(
        self,
        task: ForgeTask,
        prompt: str,
        response_schema: dict[str, Any],
        *,
        provider: str | None = None,
    ) -> RoutedResult:
        """Taskを実行する。失敗したら次の候補を試す。

        `provider`を明示した場合、**Routingを迂回する**。HTTP APIの
        利用者が選んだProviderをRouterが勝手に上書きしないため
        (既存契約の維持)。Mockが使えるのもこの経路だけである。
        """
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
            elapsed_ms = (self._monotonic() - started) * 1000.0
            if elapsed_ms >= profile.latency_budget_ms:
                # §28: 何回もfallbackして数分待たせない。
                excluded = (*excluded, f"時間予算({profile.latency_budget_ms:.0f}ms)を超過")
                break
            if model.provider in attempted:
                continue  # §20: 同じProviderを二度試さない
            attempted.add(model.provider)

            state = self._states.get(model.provider)
            if state.availability is Availability.CIRCUIT_OPEN:
                self._states.note_half_open(model.provider)

            attempt, result = self._try_one(model.provider, prompt, response_schema)
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
        attempt, result = self._try_one(provider, prompt, response_schema)
        if result is None:
            raise NoProviderAvailableError(task, (attempt,), ())
        return RoutedResult(
            value=result, task=task, provider_used=provider, attempts=(attempt,),
        )

    def _try_one(
        self, provider: str, prompt: str, response_schema: dict
    ) -> tuple[RouteAttempt, dict[str, Any] | None]:
        started = self._monotonic()
        try:
            adapter = self._resolve(provider)
            value = adapter.complete_structured(prompt, response_schema)
        except Exception as exc:  # noqa: BLE001 — 分類して次の候補へ進むため
            error = classify_exception(exc, provider)
            latency = (self._monotonic() - started) * 1000.0
            self._states.record_failure(
                provider, error.kind, retry_after_seconds=error.retry_after_seconds
            )
            return RouteAttempt(
                provider=provider, ok=False, latency_ms=latency,
                error_kind=error.kind, detail=error.message,
            ), None

        latency = (self._monotonic() - started) * 1000.0
        if not isinstance(value, dict):
            # 構造化出力が壊れている。Provider障害として扱う。
            self._states.record_failure(provider, ErrorKind.STRUCTURED_OUTPUT_FAILURE)
            return RouteAttempt(
                provider=provider, ok=False, latency_ms=latency,
                error_kind=ErrorKind.STRUCTURED_OUTPUT_FAILURE,
                detail=f"dictではなく{type(value).__name__}が返った",
            ), None

        self._states.record_success(provider, latency_ms=latency)
        return RouteAttempt(provider=provider, ok=True, latency_ms=latency), value

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
    """直近の`complete_structured()`で**実際に**応答を返したProvider名。
    まだ呼ばれていなければ`None`。"""

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        result = self.router.generate(
            self.task, prompt, response_schema, provider=self.provider
        )
        self.last_provider_used = result.provider_used
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
        for d in PROVIDER_REGISTRY
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
        )
    return _default_router


def reset_default_router() -> None:
    """共有Routerを破棄する(テスト用)。

    Catalogが環境変数に依存するようになったため、環境を差し替える
    テストは**Routerも作り直さなければ**古いCatalogを見続ける。
    """
    global _default_router  # noqa: PLW0603
    _default_router = None
