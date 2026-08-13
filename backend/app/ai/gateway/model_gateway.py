"""Model Gateway(FORGE-QUALITY-AI-INDEPENDENCE-003 Phase F、2026-08-12)。

指示書1章「ForgeをGeminiを使うアプリにしてはならない」への対応。

    Forge Brain
        ↓
    Model Gateway   ← このモジュール
        ↓
    Provider(Gemini / Local / Mock / …)

**既存の`LLMAdapter`を作り直していない**(指示書4章「既存抽象化が
十分なら作り直さない」)。監査の結果、`LLMAdapter.complete_structured(
prompt, response_schema) -> dict`というProvider非依存契約は既に存在し、
`ConversationEngine`・`ForgeOperationEngine`はProvider実装を一切
知らなかった。したがってGatewayは**その上に薄く載る**。

監査で見つかった、Gatewayが埋める不足は4つだけである:

1. **Task概念が無い**。すべてが1つの`complete_structured`であり、
   「Impact分類はLocal、Planningはgemini」というTask単位の使い分け
   (指示書3章・20章)が表現できなかった。
2. **計測が無い**。latency・失敗率・schema適合率を取る場所が無く、
   指示書19章のBenchmarkが成立しなかった。
3. **Fallbackが無い**。Providerが落ちたら即座に上位へ例外が飛ぶ
   (指示書21章)。
4. **Routingが無い**。Provider選択が呼び出し側のベタ書きだった。

**Provider固有の知識をここへ持ち込まない**: Gatewayは
`LLMAdapter`しか知らない。Geminiの`responseSchema`の癖も、Ollamaの
エンドポイント形式も、各Provider実装の内側に閉じる。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.ai.foundation.interfaces import LLMAdapter

__all__ = [
    "ForgeTask",
    "GatewayResult",
    "ModelGateway",
    "ProviderAttempt",
    "TaskRoute",
]


class ForgeTask(str, Enum):
    """Forge AIが行う仕事の単位(指示書3章)。

    「GeminiとLocalのどちらが優秀か」という大雑把な比較は禁止されており
    (指示書3章)、評価もRoutingもこの単位で行う。

    ここに挙げるのは**現に実装が存在する**Taskだけである。指示書3章の
    候補のうち`solution_hypothesis`・`product_planning`等は、現状
    `PromptPipeline`/`forge_ai`の内部で分離されておらず、単独で呼べる
    入口が無い。存在しないTaskを先に列挙しても、Routing表に永久に
    使われない行が並ぶだけなので入れていない(指示書5章「今すぐ不要な
    Providerを空実装しない」と同じ理由)。
    """

    CONVERSATION_STEP = "conversation_step"
    """1ターン分の会話判断(Problem/Need/Unknown/Impact抽出 +
    ASK/BUILD候補)。`conversation_engine.py`が呼ぶ。"""

    ENTITY_SYNTHESIS = "entity_synthesis"
    """「このアプリが繰り返し記録する1件分のデータ」の設計。
    `forge_ai/core/ir/entity_synthesizer.py`が呼ぶ。"""

    FORGE_LANGUAGE_UPDATE = "forge_language_update"
    """既存Forge Documentの更新(Forming)。`forge_operation.py`が呼ぶ。"""

    COGNITIVE_STAGE = "cognitive_stage"
    """Cognitive Pipelineの各段(meaning/intent/planning/compile/repair)。
    現状これらは`ForgeAIProviderBridge`が1つの入口でまとめて扱っており、
    段ごとの分離はしていない。"""


@dataclass(frozen=True)
class TaskRoute:
    """あるTaskをどのProviderで実行するか(指示書20章)。

    `primary`が失敗したら`fallback`を順に試す。**Benchmarkの結果で
    決めるべき値**であり、既定値は「実測前の暫定」でしかない。
    """

    primary: str
    fallback: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderAttempt:
    """1 Providerへの1回の試行の記録(指示書19章のBenchmark指標)。"""

    provider: str
    ok: bool
    latency_ms: float
    error: str | None = None


@dataclass(frozen=True)
class GatewayResult:
    """Gatewayの戻り値。

    `value`は`LLMAdapter.complete_structured()`と同じ`dict`であり、
    既存の呼び出し側はここだけ見れば従来どおり動く。周辺の
    メタデータ(どのProviderが答えたか、何ms掛かったか、fallbackしたか)
    はBenchmarkとDebugのために付随させる。
    """

    value: dict[str, Any]
    task: ForgeTask
    provider_used: str
    attempts: tuple[ProviderAttempt, ...] = ()

    @property
    def latency_ms(self) -> float:
        return sum(a.latency_ms for a in self.attempts)

    @property
    def used_fallback(self) -> bool:
        return len(self.attempts) > 1


class ModelGatewayError(RuntimeError):
    """全Providerが失敗した。個々の失敗理由は`attempts`に残る。"""

    def __init__(self, task: ForgeTask, attempts: tuple[ProviderAttempt, ...]) -> None:
        detail = "; ".join(f"{a.provider}: {a.error}" for a in attempts) or "(試行なし)"
        super().__init__(f"Task '{task.value}' を実行できるProviderがありませんでした({detail})")
        self.task = task
        self.attempts = attempts


# 既定のRouting。**実測前の暫定値**であり、すべてのTaskを既存の挙動
# (呼び出し側が指定したProvider)のまま通す。Benchmarkが揃うまで
# 勝手にLocalへ倒さない(指示書20章「実測で決定する」)。
_DEFAULT_ROUTES: dict[ForgeTask, TaskRoute] = {}


class ModelGateway:
    """Task単位でProviderを選び、計測し、必要ならfallbackする。

    `resolve_provider`は「Provider名 → `LLMAdapter`」の解決関数
    (実運用では`ProviderRouter().resolve`)。Gateway自身は具体的な
    Provider実装を一切importしない——ここが「上位ロジックがProviderを
    知らない」(指示書1章)の実装上の境界である。
    """

    def __init__(
        self,
        resolve_provider: Callable[[str], LLMAdapter],
        *,
        routes: dict[ForgeTask, TaskRoute] | None = None,
        default_provider: str = "mock",
    ) -> None:
        self._resolve = resolve_provider
        self._routes = dict(_DEFAULT_ROUTES)
        if routes:
            self._routes.update(routes)
        self._default_provider = default_provider

    def route_for(self, task: ForgeTask, *, requested: str | None = None) -> TaskRoute:
        """このTaskをどう実行するか。

        優先順位は「呼び出し側の明示指定 > Task別Routing > 既定」。
        呼び出し側の指定を最優先にしているのは、HTTP APIの
        `generation_options.provider`(利用者が選べる)を、Routing表が
        勝手に上書きしてはならないためである。
        """
        if requested:
            configured = self._routes.get(task)
            return TaskRoute(primary=requested, fallback=configured.fallback if configured else ())
        return self._routes.get(task) or TaskRoute(primary=self._default_provider)

    def generate(
        self,
        task: ForgeTask,
        prompt: str,
        response_schema: dict[str, Any],
        *,
        provider: str | None = None,
    ) -> GatewayResult:
        """Taskを実行する。

        `prompt`/`response_schema`という引数の形は、既存の
        `LLMAdapter.complete_structured()`にそのまま合わせている
        (指示書5章「現行実装に適したinterfaceを設計すること」)。
        抽象的な`input`/`context`/`constraints`へ作り変えると、
        既存の全呼び出し側とMockの契約を同時に壊すことになり、
        得られるものが「概念的な綺麗さ」しか無い。
        """
        route = self.route_for(task, requested=provider)
        candidates = (route.primary, *route.fallback)
        attempts: list[ProviderAttempt] = []

        for name in candidates:
            started = time.perf_counter()
            try:
                adapter = self._resolve(name)
                value = adapter.complete_structured(prompt, response_schema)
            except Exception as exc:  # noqa: BLE001 — 次のProviderを試すため、ここで捕まえる
                attempts.append(ProviderAttempt(
                    provider=name, ok=False,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    error=str(exc)[:200],
                ))
                continue
            attempts.append(ProviderAttempt(
                provider=name, ok=True,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            ))
            return GatewayResult(
                value=value, task=task, provider_used=name, attempts=tuple(attempts),
            )

        raise ModelGatewayError(task, tuple(attempts))
