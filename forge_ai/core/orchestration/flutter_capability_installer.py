"""**獲得した Capability を Forge の Flutter アプリへ載せる**（TD94）。

---

## これが無いと、獲得は隔離 workspace で終わる

020F で次の2つを開けた。

| 段 | 状態 |
|---|---|
| Parser 側の受け口（`forgeAcquiredWidgetTypes`） | 開いた |
| Widget Registry の解決 | 開いた |

しかし**生成された Dart が Forge アプリのビルド対象へ入る経路**が
無かった。BUILD_TIME の検証は一時ディレクトリで行われ、そこで捨てられる。
つまり「描ける形の Dart を作った」と「Forge が描ける」の間が空いていた。

このモジュールがその間を埋める。

## 何をするか

1. 生成された binding を `frontend/lib/json_ui/acquired/<slug>/` へ書く
2. 登録表 `acquired_registrations.g.dart` を**丸ごと作り直す**

2 が重要である。追記ではなく**全体を宣言から作り直す**ので、
「installer を呼ばなかった能力が残り続ける」ことが無い。
表であることが本質であり、枝を足す形にしてはならない。

## 緩めない向き

* 隔離 workspace 用の harness（テスト・probe）は**載せない**。
  あれは検証の道具であって製品ではない
* パスが `frontend/lib/json_ui/acquired/` の外へ出る artifact は**落とす**
* binding が無い artifact は**落とす**。描けないものを載せない
* 生成物を書く先は**この1ディレクトリだけ**。既存の出荷 source は触らない
* Sandbox が検査した Host Projection と**同じ規則**で配置し、投影先が
  衝突する artifact は1byteも書く前に拒否する
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from hashlib import sha256
import json

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeExtensionError,
)
from forge_ai.core.orchestration.build_time_host_projection import (
    BuildTimeHostProjection,
    HostProjectionError,
)
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (
    VerifiedCapabilityArtifact,
)

__all__ = [
    "AcquiredCapabilityInstallation",
    "FlutterCapabilityInstaller",
    "InstallationError",
    "PROVENANCE_FILE",
    "capability_slug",
    "verify_installed_capability",
]

#: 獲得能力の binding が公開する記号。**能力ごとに変えない。**
BINDING_FILE = "forge_binding.dart"
BINDING_SYMBOL = "capability"

#: 生成物を書き込んでよい唯一の場所（`frontend/` からの相対）。
INSTALL_ROOT = Path("lib/json_ui/acquired")
REGISTRATIONS_FILE = "acquired_registrations.g.dart"

#: 何を載せたのかの記録。**あとから中身が変わっていないか確かめるため。**
PROVENANCE_FILE = "capability_provenance.json"

_SLUG_UNSAFE = re.compile(r"[^a-z0-9]+")


class InstallationError(BuildTimeExtensionError):
    """**載せられなかった。** 載せられなかったことを、そう言う。"""


def capability_slug(capability_id: str) -> str:
    """`view.calendar` → `view_calendar`。**決定的で、衝突しない。**"""
    slug = _SLUG_UNSAFE.sub("_", capability_id.strip().lower()).strip("_")
    if not slug:
        raise InstallationError(f"capability id has no usable slug: {capability_id!r}")
    return slug


def _digest_of(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AcquiredCapabilityInstallation:
    capability_id: str
    slug: str
    installed_files: tuple[str, ...]
    """`frontend/` からの相対パス。**証拠として読む。**"""

    source_digest: str
    """検査を通った生成物の digest。install 後の照合に使う。"""

    build_id: str
    runtime_fingerprint: str


@dataclass(slots=True)
class FlutterCapabilityInstaller:
    """獲得能力を Forge の Flutter アプリへ載せる。

    `harness_files` と `host_prefix` は言語ごとの build plan が持つ宣言で
    あり、**能力ごとの表ではない**。
    """

    frontend_root: Path
    harness_files: frozenset[str]
    host_prefix: str = "flutter/"

    def _projection(self) -> BuildTimeHostProjection:
        return BuildTimeHostProjection(
            host_prefix=self.host_prefix,
            excluded_paths=self.harness_files,
        )

    def install(
        self, verified: VerifiedCapabilityArtifact,
    ) -> AcquiredCapabilityInstallation:
        """**検査を通ったものだけを、通ったそのままの形で載せる。**

        受け取るのは `VerifiedCapabilityArtifact` だけである。生の artifact を
        渡す口を用意しない——用意すると「検査していないものを載せる」経路が
        できてしまう。受け取った直後に digest を照合するので、検査のあとに
        1byte でも変わっていれば落ちる。
        """
        verified.verify()
        artifact = verified.artifact
        artifact.validate()
        slug = capability_slug(artifact.capability_id)
        target_dir = (self.frontend_root / INSTALL_ROOT / slug).resolve()
        root = (self.frontend_root / INSTALL_ROOT).resolve()
        if not root.is_dir():
            raise InstallationError(f"acquired capability root does not exist: {root}")

        projection = self._projection()
        try:
            projection.projected_paths(source.path for source in artifact.files)
        except HostProjectionError as exc:
            raise InstallationError(str(exc)) from exc

        planned: list[tuple[Path, str]] = []
        for source in artifact.files:
            try:
                relative = projection.project(source.path)
            except HostProjectionError as exc:
                raise InstallationError(str(exc)) from exc
            if relative is None:
                continue
            destination = (target_dir / relative).resolve()
            try:
                destination.relative_to(root)
            except ValueError as exc:
                raise InstallationError(
                    f"generated source escapes the acquired capability root: {source.path!r}",
                ) from exc
            planned.append((destination, source.content))

        if not any(path.name == BINDING_FILE for path, _ in planned):
            # **描けないものを載せない。**
            raise InstallationError(
                f"{artifact.capability_id!r} has no {BINDING_FILE};"
                " a capability with no Flutter binding cannot be rendered",
            )

        # **保存先名の衝突を検出する。** 別の能力が同じ slug を取っていたら、
        # 黙って上書きせずに落とす（古いコードが混ざる原因になる）。
        existing = target_dir / PROVENANCE_FILE
        if existing.is_file():
            try:
                previous = json.loads(existing.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise InstallationError(
                    f"unreadable provenance at {existing}; refusing to overwrite",
                ) from exc
            if previous.get("capability_id") != artifact.capability_id:
                raise InstallationError(
                    f"install slug {slug!r} is already taken by "
                    f"{previous.get('capability_id')!r}; "
                    f"{artifact.capability_id!r} cannot reuse it",
                )
        elif target_dir.exists() and any(target_dir.iterdir()):
            raise InstallationError(
                f"{target_dir} holds files with no provenance; refusing to mix "
                "unknown source into an acquired capability",
            )

        # **古いファイルを残さない。** 前回の生成物が混ざると、
        # 「いま検査したもの」と「いま動いているもの」がずれる。
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        written: list[str] = []
        file_digests: dict[str, str] = {}
        for destination, content in planned:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
            relative = str(destination.relative_to(target_dir)).replace("\\", "/")
            file_digests[relative] = _digest_of(content)
            written.append(
                str(destination.relative_to(self.frontend_root.resolve())).replace("\\", "/"),
            )

        (target_dir / PROVENANCE_FILE).write_text(
            json.dumps(
                {
                    "capability_id": artifact.capability_id,
                    "source_digest": verified.source_digest,
                    "build_id": verified.build_id,
                    "runtime_fingerprint": verified.runtime_fingerprint,
                    "files": file_digests,
                },
                ensure_ascii=False, indent=2, sort_keys=True,
            ) + "\n",
            encoding="utf-8", newline="\n",
        )

        return AcquiredCapabilityInstallation(
            capability_id=artifact.capability_id,
            slug=slug,
            installed_files=tuple(sorted(written)),
            source_digest=verified.source_digest,
            build_id=verified.build_id,
            runtime_fingerprint=verified.runtime_fingerprint,
        )

    def rewrite_registrations(self) -> Path:
        """**表を丸ごと作り直す。** 追記しない。

        いま置かれている binding だけが登録される。installer を通って
        いない能力が登録表に残り続ける形にしない。
        """
        root = (self.frontend_root / INSTALL_ROOT).resolve()
        slugs = sorted(
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and (entry / BINDING_FILE).is_file()
        )
        lines = [
            "// GENERATED FILE — 手で編集しない。",
            "//",
            "// Self-Extension で獲得した Capability の登録表。",
            "// `forge_ai` の installer（`flutter_capability_installer.py`）が、",
            "// 獲得のたびにこのファイルを丸ごと書き直す。",
            "//",
            "// **出荷状態では空である。** 何も獲得していないのだから、何も登録しない。",
            "",
        ]
        if slugs:
            lines.append("import 'acquired_capability.dart';")
        for index, slug in enumerate(slugs):
            lines.append(f"import '{slug}/{BINDING_FILE}' as capability_{index};")
        lines.append("")
        lines.append("void registerAcquiredCapabilities() {")
        if not slugs:
            lines.append("  // 獲得した Capability はここへ書き出される。")
        for index in range(len(slugs)):
            lines.append(
                f"  registerAcquiredCapability(capability_{index}.{BINDING_SYMBOL});",
            )
        lines.append("}")
        target = root / REGISTRATIONS_FILE
        target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return target

    def _host_path(self, path: str) -> str | None:
        """artifact のパス → アプリ内の相対パス。載せないものは `None`。"""
        try:
            return self._projection().project(path)
        except HostProjectionError as exc:
            raise InstallationError(str(exc)) from exc


def verify_installed_capability(frontend_root: Path, slug: str) -> str:
    """**載っているものが、検査したときのままか。**

    install 後に誰かが手で書き換えていないかを、記録した digest と
    突き合わせて確かめる。ずれていれば落ちる——「Flutter 側だけ直す」
    という抜け道を塞ぐためである。

    戻り値は検査を通した生成物の `source_digest`。
    """
    directory = (frontend_root / INSTALL_ROOT / slug).resolve()
    record = directory / PROVENANCE_FILE
    if not record.is_file():
        raise InstallationError(f"no provenance for installed capability at {directory}")
    try:
        provenance = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallationError(f"unreadable provenance at {record}") from exc

    expected: dict[str, str] = provenance.get("files", {})
    present = {
        str(path.relative_to(directory)).replace("\\", "/")
        for path in directory.rglob("*")
        if path.is_file() and path.name != PROVENANCE_FILE
    }
    if present != set(expected):
        raise InstallationError(
            f"installed files for {slug!r} do not match the record: "
            f"unexpected={sorted(present - set(expected))} "
            f"missing={sorted(set(expected) - present)}",
        )
    for relative, digest in sorted(expected.items()):
        actual = _digest_of((directory / relative).read_text(encoding="utf-8"))
        if actual != digest:
            raise InstallationError(
                f"installed file {relative!r} of {slug!r} was modified after inspection",
            )
    return str(provenance.get("source_digest", ""))
