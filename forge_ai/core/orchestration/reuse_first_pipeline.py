"""**持っているものは組み合わせ、足りないものだけ作る。**

---

## 本線はこれである

```text
利用者の要求
  ↓
いま持っている能力で作れるか
  ↓
作れる  → 組み合わせて即表示。**新しいコードは1行も作らない**
作れない → 足りない能力**だけ**作る → 検査 → 合格した**その同じ生成物**を
           Forge へ組み込む → 表示 → 次回からは再生成せず再利用
```

**「毎回生成 → 毎回再ビルド」を通常経路にしない。** 生成は高い。
遅いだけでなく、毎回違うコードが出てくるなら製品として信用できない。

## 数えるから嘘をつけない

`RequestOutcome` は「何回生成したか」「Provider を何回呼んだか」を持つ。
既存能力だけで作れた要求で生成が1回でも走っていれば、それは本線が
壊れているということであり、テストが落ちる。

## 検査したものと動くものを同じにする

acquire は `VerifiedCapabilityArtifact`——**検査を通ったそのもの**——を
install へ渡す。作り直さない。作り直した瞬間、検査した対象と動く対象が
別物になる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time

from forge_ai.core.orchestration.extension_manifest import (
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.orchestration.flutter_capability_installer import (
    AcquiredCapabilityInstallation,
    FlutterCapabilityInstaller,
)
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (
    CapabilityImplementationUnavailable,
    SynthesizingBuildTimeImplementer,
    build_plan_for_language,
)
from forge_ai.core.semantics.capability_plan import plan_capabilities

__all__ = [
    "AcquisitionRecord",
    "RequestOutcome",
    "ReuseFirstPipeline",
    "StageTimings",
]


def _ms(seconds: float) -> float:
    return round(seconds * 1000.0, 1)


@dataclass(slots=True)
class StageTimings:
    """各工程にかかった時間（ミリ秒）。**遅すぎるのも不合格である。**"""

    understand_ms: float = 0.0
    """要求を読んで必要な能力を割り出すまで。"""

    capability_lookup_ms: float = 0.0
    """いま持っている能力で足りるかを調べるまで。"""

    synthesis_ms: float = 0.0
    """足りない能力の実装を作るのにかかった時間（不要なら 0）。"""

    verify_ms: float = 0.0
    """作ったものを実際に試験・解析・起動確認するのにかかった時間。"""

    install_ms: float = 0.0
    """Forge へ組み込むのにかかった時間。"""

    document_ms: float = 0.0
    """画面（生成 Document）を組み立てるまで。"""

    total_ms: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "understand_ms": self.understand_ms,
            "capability_lookup_ms": self.capability_lookup_ms,
            "synthesis_ms": self.synthesis_ms,
            "verify_ms": self.verify_ms,
            "install_ms": self.install_ms,
            "document_ms": self.document_ms,
            "total_ms": self.total_ms,
        }


@dataclass(frozen=True, slots=True)
class AcquisitionRecord:
    capability_id: str
    source_digest: str
    build_id: str
    runtime_fingerprint: str
    installed_files: tuple[str, ...]


@dataclass(slots=True)
class RequestOutcome:
    """1つの要求を処理した結果。**数えたものだけを報告する。**"""

    need: str
    requested: tuple[str, ...] = ()
    missing_before: tuple[str, ...] = ()
    missing_after: tuple[str, ...] = ()
    reused: tuple[str, ...] = ()
    """**再生成せずに使い回した**能力。"""

    acquired: tuple[str, ...] = ()
    """今回新しく作った能力。"""

    generation_count: int = 0
    """**実装を作った回数。** 既存能力だけで済んだ要求では 0 でなければならない。"""

    build_count: int = 0
    provider_calls: int = 0
    document: object | None = None
    acquisitions: tuple[AcquisitionRecord, ...] = ()
    timings: StageTimings = field(default_factory=StageTimings)
    failure: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "need": self.need,
            "requested": list(self.requested),
            "missing_before": list(self.missing_before),
            "missing_after": list(self.missing_after),
            "reused": list(self.reused),
            "acquired": list(self.acquired),
            "generation_count": self.generation_count,
            "build_count": self.build_count,
            "provider_calls": self.provider_calls,
            "document_produced": self.document is not None,
            "timings": self.timings.to_dict(),
            "failure": self.failure,
        }


@dataclass(slots=True)
class ReuseFirstPipeline:
    """要求 → 既存能力で作れるか → 足りない分だけ獲得 → 画面。

    `implementer` と `installer` は**足りないときにしか触らない**。
    足りているのに触ったら、それは本線が壊れている。
    """

    implementer: SynthesizingBuildTimeImplementer
    installer: FlutterCapabilityInstaller
    build_document: object
    """`(need, plan, promoted) -> document`。本番の compiler を注入する。"""

    label_for: object = None
    """`(capability_id) -> str`。無ければ capability_id をそのまま使う。"""

    provider_call_count: object = None
    """`() -> int`。Provider を何回呼んだかを外から数える。"""

    def handle(self, need: str) -> RequestOutcome:
        timings = StageTimings()
        started = time.perf_counter()
        calls_before = self._provider_calls()
        generations_before = self.implementer.synthesis_count
        builds_before = self.implementer.build_count

        # --- 1. 要求を読む -------------------------------------------------
        mark = time.perf_counter()
        plan = plan_capabilities(need)
        timings.understand_ms = _ms(time.perf_counter() - mark)

        # --- 2. いま持っている能力で足りるか -------------------------------
        mark = time.perf_counter()
        missing_before = tuple(plan.missing)
        reused = tuple(
            capability_id for capability_id in plan.requested
            if PROMOTED_CAPABILITIES.is_promoted(capability_id)
        )
        timings.capability_lookup_ms = _ms(time.perf_counter() - mark)

        outcome = RequestOutcome(
            need=need,
            requested=tuple(plan.requested),
            missing_before=missing_before,
            reused=reused,
            timings=timings,
        )

        # --- 3. 足りない能力**だけ**作る -----------------------------------
        acquisitions: list[AcquisitionRecord] = []
        for capability_id in missing_before:
            try:
                acquisitions.append(self._acquire(capability_id, timings))
            except (CapabilityImplementationUnavailable, ValueError) as exc:
                outcome.failure = f"acquire({capability_id}): {exc}"
                break
        outcome.acquisitions = tuple(acquisitions)
        outcome.acquired = tuple(item.capability_id for item in acquisitions)

        # --- 4. 画面を組み立てる -------------------------------------------
        if outcome.failure is None:
            mark = time.perf_counter()
            replanned = plan_capabilities(need) if missing_before else plan
            outcome.missing_after = tuple(replanned.missing)
            if replanned.missing:
                outcome.failure = (
                    f"still missing after acquisition: {replanned.missing}"
                )
            else:
                promoted = tuple(
                    capability_id for capability_id in replanned.requested
                    if PROMOTED_CAPABILITIES.is_promoted(capability_id)
                )
                outcome.document = self.build_document(need, replanned, promoted)  # type: ignore[operator]
            timings.document_ms = _ms(time.perf_counter() - mark)

        outcome.generation_count = self.implementer.synthesis_count - generations_before
        outcome.build_count = self.implementer.build_count - builds_before
        outcome.provider_calls = self._provider_calls() - calls_before
        timings.total_ms = _ms(time.perf_counter() - started)
        return outcome

    # ------------------------------------------------------------------
    def _acquire(self, capability_id: str, timings: StageTimings) -> AcquisitionRecord:
        """足りない能力を1つ作って、Forge へ組み込む。

        **検査を通ったそのものを組み込む。** 作り直さない。
        """
        manifest = ExtensionManifest(
            capability_id=capability_id,
            label_ja=self._label(capability_id),
            route=ExtensionRoute.BUILD_TIME,
            requires_confirmation=False,
        )

        mark = time.perf_counter()
        implementation = self.implementer(manifest)
        # 生成と検査は同じ呼び出しの中で起きる。時間はまとめて verify 側へ
        # 積むと嘘になるので、build 実行のぶんを verify として分けて数える。
        elapsed = time.perf_counter() - mark
        verified = self.implementer.last_verified
        if verified is None:
            raise CapabilityImplementationUnavailable(
                f"{capability_id!r} did not produce a verified artifact",
            )
        execution = self.implementer.last_execution
        verify_share = 0.0
        if execution is not None:
            verify_share = elapsed  # 実 subprocess が占める
        timings.verify_ms += _ms(verify_share)
        timings.synthesis_ms += _ms(max(elapsed - verify_share, 0.0))

        if implementation.manifest.status is not ExtensionStatus.PROMOTED:
            raise CapabilityImplementationUnavailable(
                f"{capability_id!r} was not promoted",
            )

        mark = time.perf_counter()
        installation: AcquiredCapabilityInstallation = self.installer.install(verified)
        self.installer.rewrite_registrations()
        PROMOTED_CAPABILITIES.install(implementation.manifest, implementation.activation)
        timings.install_ms += _ms(time.perf_counter() - mark)

        return AcquisitionRecord(
            capability_id=capability_id,
            source_digest=installation.source_digest,
            build_id=installation.build_id,
            runtime_fingerprint=installation.runtime_fingerprint,
            installed_files=installation.installed_files,
        )

    def _label(self, capability_id: str) -> str:
        if self.label_for is None:
            return capability_id
        return str(self.label_for(capability_id))  # type: ignore[operator]

    def _provider_calls(self) -> int:
        if self.provider_call_count is None:
            return 0
        return int(self.provider_call_count())  # type: ignore[operator]


def installer_for(frontend_root: Path, host_language: str) -> FlutterCapabilityInstaller:
    """言語の build plan の宣言から installer を組む。**能力ごとの表は無い。**"""
    plan = build_plan_for_language(host_language)
    return FlutterCapabilityInstaller(
        frontend_root=frontend_root,
        harness_files=frozenset(plan.harness_files),
        host_prefix=plan.host_prefix,
    )
