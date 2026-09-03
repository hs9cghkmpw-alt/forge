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
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
    implement_build_time_extension,
)
from forge_ai.core.orchestration.build_time_host_projection import (
    BuildTimeHostProjection,
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
from forge_ai.core.orchestration.extension_manifest import (
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.managed_build_time_implementer import (
    ManagedBuildTimeImplementer,
)

__all__ = [
    "CapabilityImplementationUnavailable",
    "VerifiedCapabilityArtifact",
    "LanguageBuildPlan",
    "SynthesizingBuildTimeImplementer",
    "build_plan_for_language",
    "command_plan_for_language",
    "entry_files_for_language",
    "supported_host_languages",
]


class CapabilityImplementationUnavailable(BuildTimeExtensionError):
    """**実装を作れなかった。** 作れなかったことを、そう言う。"""


@dataclass(frozen=True, slots=True)
class VerifiedCapabilityArtifact:
    """**検査を通ったそのもの。**

    Forge へ組み込んでよいのは、検査したものと**同一の**生成物だけである。
    検査したあとに作り直したものを組み込むと、
    「検査した対象」と「動く対象」が別物になり、証拠の鎖が切れる。

    そこで検査を通した生成物そのものをここへ包み、install する側は
    この型しか受け取らない。`source_digest` は build 実行時に materialize
    された workspace の digest と一致したものである——1byte でも違えば
    ここまで来ない。
    """

    artifact: BuildTimeCapabilityArtifact
    source_digest: str
    build_id: str
    runtime_fingerprint: str

    def verify(self) -> None:
        """**いま持っている中身が、検査したときのままか。**"""
        if self.artifact.source_digest != self.source_digest:
            raise BuildTimeExtensionError(
                "verified artifact changed after inspection: "
                f"{self.artifact.capability_id!r} digest "
                f"{self.artifact.source_digest} != {self.source_digest}",
            )


@dataclass(frozen=True, slots=True)
class LanguageBuildPlan:
    """その言語を**どう試験し、どうビルドし、どう起動確認するか**。

    `entry_files` は手順が名指しで実行するファイルである。宣言しておかないと
    「生成物にその名前が無く、コマンドがファイル不在で落ちる」形になり、
    **生成の失敗が build の失敗に化ける**。先に名前を要求して、
    足りなければ生成側の失敗として落とす。
    """

    commands: tuple[BuildCommand, ...]
    entry_files: tuple[str, ...]

    harness_files: tuple[str, ...] = ()
    """隔離 workspace での**検証の道具**。製品へは載せない。"""

    host_prefix: str = ""
    """製品側（Forge アプリ）へ載せるファイルの接頭辞。載せるとき剥がす。"""


#: 言語ごとの「試験 / ビルド / 起動確認」の仕方。
#:
#: **能力ごとの表ではない。** 行が増えるのは対応言語を足したときだけで
#: あり、能力を1つ獲得するたびに増えることはない。
_LANGUAGE_COMMAND_PLANS: dict[str, LanguageBuildPlan] = {
    "python": LanguageBuildPlan(
        commands=(
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
        entry_files=("probe.py",),
    ),
    # Dart は package を取りに行かない構成にしてある。`dart pub get` を
    # 挟むと外向き通信が要り、**ネットワークの都合が build の成否に化ける**。
    # 依存無しで書けるように、テストも probe も素の Dart entrypoint とする。
    # `flutter/` 以下は Flutter を要るので、隔離 workspace では解析しない
    # （Flutter が無いため）。あちらは install 後の `flutter analyze` /
    # `flutter test` / `flutter build web` が見る。**2つは別の事実である。**
    "dart": LanguageBuildPlan(
        commands=(
            BuildCommand(
                kind="test",
                argv=("dart", "run", "capability_test.dart"),
                timeout_seconds=300.0,
            ),
            BuildCommand(
                kind="build",
                argv=(
                    "dart", "analyze",
                    "capability_impl.dart", "capability_test.dart", "probe.dart",
                ),
                timeout_seconds=300.0,
            ),
            BuildCommand(
                kind="runtime_probe",
                argv=("dart", "run", "probe.dart"),
                timeout_seconds=300.0,
            ),
        ),
        entry_files=(
            "capability_impl.dart",
            "capability_test.dart",
            "probe.dart",
            "flutter/forge_binding.dart",
        ),
        harness_files=("capability_test.dart", "probe.dart"),
        host_prefix="flutter/",
    ),
}


def supported_host_languages() -> tuple[str, ...]:
    """実 build まで通せる言語。**通せないものを通せると言わない。**"""
    return tuple(sorted(_LANGUAGE_COMMAND_PLANS))


def build_plan_for_language(host_language: str) -> LanguageBuildPlan:
    """その言語の手順一式。

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


def command_plan_for_language(host_language: str) -> tuple[BuildCommand, ...]:
    """その言語の試験・ビルド・起動確認の手順。"""
    return build_plan_for_language(host_language).commands


def entry_files_for_language(host_language: str) -> tuple[str, ...]:
    """手順が名指しで実行するファイル名。"""
    return build_plan_for_language(host_language).entry_files


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

    last_verified: VerifiedCapabilityArtifact | None = field(default=None, init=False)
    """**検査を通った生成物そのもの。**

    install する側はこれを使う。もう一度生成し直してはならない
    ——作り直した瞬間、検査した対象と動く対象が別物になる。
    """

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
        plan = build_plan_for_language(contract.host_language)

        self.synthesis_count += 1
        artifact = self.synthesizer.synthesize(
            contract,
            known_source_digests=self.known_source_digests,
            required_files=plan.entry_files,
        )
        if artifact is None:
            # **作れなかったものを「作れた」と言わない。**
            raise CapabilityImplementationUnavailable(
                f"no usable implementation was generated for {manifest.capability_id!r}",
            )
        produced = {source.path for source in artifact.files}
        missing = tuple(name for name in plan.entry_files if name not in produced)
        if missing:
            # 生成の失敗を build の失敗に化けさせない。
            raise CapabilityImplementationUnavailable(
                f"generated implementation for {manifest.capability_id!r} is missing"
                f" required entry files: {', '.join(missing)}",
            )

        host_projection = BuildTimeHostProjection(
            host_prefix=plan.host_prefix,
            excluded_paths=frozenset(plan.harness_files),
        )
        managed = ManagedBuildTimeImplementer(
            capability_id=manifest.capability_id,
            commands=plan.commands,
            runner=self.runner,
            host_projection=host_projection,
        )
        self.build_count += 1
        self.last_verified = None
        implementation = implement_build_time_extension(
            manifest,
            artifact,
            builder=managed.build,
            load_runtime=managed.load_runtime,
        )
        self.last_execution = managed.last_execution

        # **検査を通ったものだけを、通ったそのままの形で残す。**
        execution = managed.last_execution
        activation = implementation.activation
        # 「証拠がこの artifact のものであること」は
        # `implement_build_time_extension()` が既に強制している
        # （`build.source_digest != artifact.source_digest` で落ちる）。
        # ここで同じ検査をもう一度書いても**到達しない**ので書かない
        # ——到達しないコードは、外しても誰も気づかない置物である。
        if (
            execution is not None
            and activation is not None
            and getattr(activation, "loaded", False) is True
            and implementation.manifest.status is ExtensionStatus.PROMOTED
        ):
            self.last_verified = VerifiedCapabilityArtifact(
                artifact=artifact,
                source_digest=artifact.source_digest,
                build_id=execution.result.build_id,
                runtime_fingerprint=execution.result.runtime_fingerprint,
            )
        return implementation

    def _contract(self, capability_id: str) -> CapabilityImplementationContract:
        contract = self.contract_for(capability_id)  # type: ignore[operator]
        if not isinstance(contract, CapabilityImplementationContract):
            raise BuildTimeExtensionError(
                "contract_for must return a CapabilityImplementationContract",
            )
        return contract
