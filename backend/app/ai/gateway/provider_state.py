"""Provider Health / Quota State
(FORGE-QUOTA-AWARE-AI-ROUTER-008 §7〜§10、2026-08-13)。

`docs/spec/FORGE-QUOTA-AWARE-AI-ROUTER-ARCH-REVIEW.md` §8 の実装。

---

## 設計上の要点

**1. Quota「不明」を「無制限」と扱わない**(§9・§46)。

Providerが残量を返すとは限らない。単位もRPM/TPM/RPD/同時実行数と
まちまちで、粒度もModel単位・Project単位・Account単位が混在する。
したがって`UNKNOWN`という状態を正面から持つ。扱いは**楽観にも
悲観にも倒さない**——候補から外しはしないが、残量が分かっていて
余裕のあるProviderより優先はしない。

**2. 枠切れは「故障」ではない**。

`QUOTA_EXHAUSTED`をCircuit Breakerの失敗カウントに入れない。
枠切れは`reset_at`まで待てば直るが、故障はcooldown後に試して
みないと分からない。復帰条件が違うものを同じ仕組みで扱うと、
どちらの理由で除外されているのか分からなくなる。

**3. 状態は実際の利用結果からのみ更新する**(§30)。

health checkのために生成Requestを投げない——自分でQuotaを
食うことになる。

## 既知の制限

プロセス内メモリのみ。複数ワーカーでは共有されない
(`ConversationStore`と同じ制限、TD41)。複数プロセスで動かすと、
各プロセスが別々にQuota切れを学習することになる。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import Enum

from app.ai.gateway.ai_errors import ErrorKind

__all__ = [
    "Availability",
    "ProviderState",
    "ProviderStateStore",
    "QuotaKnowledge",
]


class Availability(str, Enum):
    """今このProviderを候補にしてよいか。"""

    AVAILABLE = "available"
    QUOTA_EXHAUSTED = "quota_exhausted"
    """枠切れ。`quota_reset_at`まで除外。"""

    RATE_LIMITED = "rate_limited"
    """一時的な流量制限。`cooldown_until`まで除外。"""

    CIRCUIT_OPEN = "circuit_open"
    """連続失敗でCircuit Breakerが開いた。`cooldown_until`まで除外。"""

    CIRCUIT_HALF_OPEN = "circuit_half_open"
    """cooldown経過。**1回だけ試す**。成功で復帰、失敗で再びOPEN。"""

    DISABLED = "disabled"
    """認証エラー・未実装など、設定を直すまで恒久的に除外。"""


class QuotaKnowledge(str, Enum):
    """残量について**何を知っているか**(§9)。"""

    EXACT = "exact"
    """Providerが明示した(ヘッダ等)。"""

    ESTIMATED = "estimated"
    """使用履歴からの推定。**MVPでは生成しない**——測っていない推定を
    Routingへ使うと、外れたときに原因が分からなくなる。"""

    UNKNOWN = "unknown"
    """不明。**無制限ではない**。"""


# 連続何回の故障でCircuit Breakerを開くか。
_FAILURE_THRESHOLD = 3
# 開いてから最初の再試行までの秒数。失敗を重ねるごとに倍にする。
_BASE_COOLDOWN_SECONDS = 30.0
_MAX_COOLDOWN_SECONDS = 600.0


@dataclass(frozen=True)
class ProviderState:
    """1 Providerの状態。不変オブジェクトとして持ち、更新は差し替える。"""

    provider: str
    availability: Availability = Availability.AVAILABLE
    quota_knowledge: QuotaKnowledge = QuotaKnowledge.UNKNOWN
    remaining_requests: int | None = None
    quota_reset_at: float | None = None
    cooldown_until: float | None = None
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    last_error: ErrorKind | None = None
    latency_samples_ms: tuple[float, ...] = field(default_factory=tuple)

    @property
    def average_latency_ms(self) -> float | None:
        if not self.latency_samples_ms:
            return None
        return sum(self.latency_samples_ms) / len(self.latency_samples_ms)

    def is_selectable(self, *, now: float) -> bool:
        """今この瞬間、候補にしてよいか。

        時間で復帰するもの(枠切れ・cooldown)は、**期限を過ぎていれば
        選べる**。状態遷移を別途走らせなくても判定できるようにして
        いるのは、遷移の呼び忘れで永久に除外されるのを避けるため。
        """
        if self.availability is Availability.DISABLED:
            return False
        if self.availability is Availability.QUOTA_EXHAUSTED:
            return self.quota_reset_at is not None and now >= self.quota_reset_at
        if self.availability in (Availability.RATE_LIMITED, Availability.CIRCUIT_OPEN):
            return self.cooldown_until is not None and now >= self.cooldown_until
        return True

    def exclusion_reason(self, *, now: float) -> str | None:
        """なぜ除外されているか。**理由を言えるようにしておく**
        ——「使えるProviderがありません」だけでは調査できない。"""
        if self.is_selectable(now=now):
            return None
        if self.availability is Availability.DISABLED:
            return f"{self.provider}: 設定エラーのため除外({self.last_error and self.last_error.value})"
        if self.availability is Availability.QUOTA_EXHAUSTED:
            return f"{self.provider}: 利用枠切れ"
        return f"{self.provider}: 一時的に利用不可({self.availability.value})"


class ProviderStateStore:
    """Provider状態の保持と遷移。

    **判断はしない**(どれを選ぶかはRouterの仕事)。ここは
    「何が起きたか」を状態へ写像するだけである。
    """

    def __init__(self, *, now: callable = time.time) -> None:
        self._states: dict[str, ProviderState] = {}
        self._now = now

    def get(self, provider: str) -> ProviderState:
        return self._states.get(provider) or ProviderState(provider=provider)

    def all_states(self) -> tuple[ProviderState, ...]:
        return tuple(self._states.values())

    def record_success(self, provider: str, *, latency_ms: float) -> ProviderState:
        """成功。**連続失敗をリセットし、Circuit Breakerを閉じる**。"""
        state = self.get(provider)
        samples = (state.latency_samples_ms + (latency_ms,))[-20:]
        updated = replace(
            state,
            availability=Availability.AVAILABLE,
            consecutive_failures=0,
            cooldown_until=None,
            total_successes=state.total_successes + 1,
            latency_samples_ms=samples,
        )
        self._states[provider] = updated
        return updated

    def record_failure(
        self, provider: str, kind: ErrorKind, *, retry_after_seconds: float | None = None
    ) -> ProviderState:
        """失敗。**種類ごとに違う状態遷移をする**——ここが
        「全部同じ失敗として扱わない」(§7)の実体である。"""
        state = self.get(provider)
        now = self._now()
        failures = state.total_failures + 1

        if kind.disables_provider:
            updated = replace(
                state, availability=Availability.DISABLED,
                last_error=kind, total_failures=failures,
            )
        elif kind is ErrorKind.QUOTA_EXHAUSTED:
            # 枠切れは故障ではない。連続失敗カウントを増やさない。
            reset_at = now + (retry_after_seconds if retry_after_seconds else _default_quota_window())
            updated = replace(
                state, availability=Availability.QUOTA_EXHAUSTED,
                quota_knowledge=(
                    QuotaKnowledge.EXACT if retry_after_seconds else QuotaKnowledge.UNKNOWN
                ),
                remaining_requests=0, quota_reset_at=reset_at,
                last_error=kind, total_failures=failures,
            )
        elif kind is ErrorKind.RATE_LIMITED:
            updated = replace(
                state, availability=Availability.RATE_LIMITED,
                cooldown_until=now + (retry_after_seconds or _BASE_COOLDOWN_SECONDS),
                last_error=kind, total_failures=failures,
            )
        elif kind.counts_toward_circuit_breaker:
            consecutive = state.consecutive_failures + 1
            if consecutive >= _FAILURE_THRESHOLD:
                # 失敗が続くほどcooldownを延ばす(壊れ続けている相手へ
                # 一定間隔で投げ続けない)。
                backoff = min(
                    _BASE_COOLDOWN_SECONDS * (2 ** (consecutive - _FAILURE_THRESHOLD)),
                    _MAX_COOLDOWN_SECONDS,
                )
                updated = replace(
                    state, availability=Availability.CIRCUIT_OPEN,
                    cooldown_until=now + backoff,
                    consecutive_failures=consecutive,
                    last_error=kind, total_failures=failures,
                )
            else:
                updated = replace(
                    state, consecutive_failures=consecutive,
                    last_error=kind, total_failures=failures,
                )
        else:
            # INVALID_REQUEST等。Provider側の問題ではないので状態を悪化させない。
            updated = replace(state, last_error=kind, total_failures=failures)

        self._states[provider] = updated
        return updated

    def note_half_open(self, provider: str) -> ProviderState:
        """cooldownが明けたProviderを「1回だけ試す」状態にする。"""
        state = self.get(provider)
        if state.availability is not Availability.CIRCUIT_OPEN:
            return state
        updated = replace(state, availability=Availability.CIRCUIT_HALF_OPEN)
        self._states[provider] = updated
        return updated

    def reset(self) -> None:
        self._states.clear()


def _default_quota_window() -> float:
    """Providerがreset時刻を教えなかった場合の既定待機。

    **1時間**にしている。無料枠は日次のことが多いが、日次だと仮定して
    24時間除外すると、実際には分単位で復帰するProviderを丸1日
    捨てることになる。短めに置いて、駄目ならまた枠切れとして
    学習し直す方が、誤りのコストが小さい。
    """
    return 3600.0
