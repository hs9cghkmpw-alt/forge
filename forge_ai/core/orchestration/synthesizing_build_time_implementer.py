"""**生成 → 実 build → 実 probe → PROMOTED** を1本に繋ぐ（020E-2）。

---

## これが無いと、両端があっても繋がらない

Forge は既に次の両端を持っていた。

| 端 | 状態 |
|---|---|
| 足りない能力を名指しする | Capability Gap → NeedsExtension（実在） |
| 与えられた実装を検証して取り込む | BUILD_TIME（実 subprocess で証明済み） |

そして 020E で、その間の**実装を作る段**（`CapabilityArtifactSynthesizer`）
を足した。

**しかし本番の `ExtensionImplementer` はまだ存在しなかった。**
`extension_cycle.py` の

```python
class ExtensionImplementer(Protocol): ...
```

へ渡されている実体は、これまで**テストの closure だけ**だった。
このモジュールがその本番実体である。

## Capability 専用の分岐を持たない

契約は Canonical Catalog から機械的に引く。コマンド計画は
**実装先の言語**から引く——`view.map` だから、`view.calendar` だから、
という枝はどこにも無い（`test_synthesizing_build_time_implementer.py`
が静的に固定する）。

言語ごとのコマンドは「その言語をどう試験して、どうビルドして、どう
起動確認するか」であって、能力の中身ではない。

## 作れなかったものを「作れた」と言わない

Synthesizer が `None` を返したら、ここで止める。
manifest を DRAFT のまま返して「実装した」と記録しない。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeExtensionError,
    implement_build_time_extension,
)
from forge_ai.core.orchestration.build_time_workspace import (
    BuildCommand,
    ManagedBuildExecution,
    ManagedBuildWorkspaceRunner,
)
from forge_ai.core.orchestration.capability_artifact_synthesis import (
    CapabilityArtifactSynthesizer,
    CapabilityImplementationContract,
)
from forge_ai.core.orchestration.extension_activation import ExtensionImplementation
from forge_ai.core.orchestration.extension_manifest import ExtensionManifest
from forge_ai.core.orchestration.managed_build_time_implementer import (
    ManagedBuildTimeImplementer,
)

__all__ = [
    "CapabilityImplementationUnavailable",
    "SynthesizingBuildTimeImplementer",
    "command_plan_for_language",
    "supported_host_languages",
]


class CapabilityImplementationUnavailable(BuildTimeExtensionError):
    """**実装を作れなかった。** 作れなかったことを、そう言う。"""


#: 言語ごとの「試験 / ビルド / 起動確認」の仕方。
#:
#: **能力ごとの表ではない。** 行が増えるのは対応言語を足したときだけで
#: あり、能力を1つ獲得するたびに増えることはない。
_LANGUAGE_COMMAND_PLANS: dict[str, tuple[BuildCommand, ...]] = {
    "python": (
        BuildCommand(
            kind="test",
            argv=("python", "-m", "unittest", "discover", "-s", ".", "-p", "*_test.py"),
            timeout_seconds=120.0,
        ),
        BuildCommand(
            kind="build",
            argv=("python", "-m", "compileall", "-q", "."),
            timeout_seconds=120.0,
        ),
        BuildCommand(
            kind="runtime_probe",
            argv=("python", "probe.py"),
            timeout_seconds=120.0,
        ),
    ),
}


def supported_host_languages() -> tuple[str, ...]:
    """実 build まで通せる言語。**通せないものを通せると言わない。**"""
    return tuple(sorted(_LANGUAGE_COMMAND_PLANS))


def command_plan_for_language(host_language: str) -> tuple[BuildCommand, ...]:
    """その言語の試験・ビルド・起動確認の手順。

    知らない言語は落とす——「とりあえず python で試す」のような
    楽観側への倒し方をしない。
    """
    plan = _LANGUAGE_COMMAND_PLANS.get(host_language.strip().lower())
    if plan is None:
        raise CapabilityImplementationUnavailable(
            f"no managed build plan for host language {host_language!r};"
            f" supported: {', '.join(supported_host_languages())}",
        )
    return plan


@dataclass(slots=True)
class SynthesizingBuildTimeImplementer:
    """本番の `ExtensionImplementer`。

    manifest を受け取り、実装を**生成し**、managed workspace で
    **実際に**試験・ビルド・起動確認し、exact build のみを activation
    として返す。
    """

    synthesizer: CapabilityArtifactSynthesizer
    contract_for: object
    """`(capability_id) -> CapabilityImplementationContract`。

    Canonical Catalog から引く関数を注入する。ここで表を持たない——
    持った時点で2つ目の Source of Truth になる。
    """

    known_source_digests: frozenset[str]
    """既存の出荷済み Source の digest。**丸写しを生成と数えないため。**"""

    runner: ManagedBuildWorkspaceRunner = field(
        default_factory=ManagedBuildWorkspaceRunner,
    )
    last_execution: ManagedBuildExecution | None = field(default=None, init=False)
    """直近の実コマンド証拠。Evidence 文書を書くために外から読む。"""

    synthesis_count: int = field(default=0, init=False)
    """**実装を作った回数。** 2回目の要求で増えないことを示すために数える。"""

    build_count: int = field(default=0, init=False)
    """**実 build を回した回数。**"""

    def __call__(self, manifest: ExtensionManifest) -> ExtensionImplementation:
        contract = self._contract(manifest.capability_id)
        if contract.capability_id != manifest.capability_id:
            raise BuildTimeExtensionError(
                "capability contract changed capability identity",
            )
        commands = command_plan_for_language(contract.host_language)

        self.synthesis_count += 1
        artifact = self.synthesizer.synthesize(
            contract, known_source_digests=self.known_source_digests,
        )
        if artifact is None:
            # **作れなかったものを「作れた」と言わない。**
            raise CapabilityImplementationUnavailable(
                f"no usable implementation was generated for {manifest.capability_id!r}",
            )

        managed = ManagedBuildTimeImplementer(
            capability_id=manifest.capability_id,
            commands=commands,
            runner=self.runner,
        )
        self.build_count += 1
        implementation = implement_build_time_extension(
            manifest,
            artifact,
            builder=managed.build,
            load_runtime=managed.load_runtime,
        )
        self.last_execution = managed.last_execution
        return implementation

    def _contract(self, capability_id: str) -> CapabilityImplementationContract:
        contract = self.contract_for(capability_id)  # type: ignore[operator]
        if not isinstance(contract, CapabilityImplementationContract):
            raise BuildTimeExtensionError(
                "contract_for must return a CapabilityImplementationContract",
            )
        return contract
