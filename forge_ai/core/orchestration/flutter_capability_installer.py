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
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
)

__all__ = [
    "AcquiredCapabilityInstallation",
    "FlutterCapabilityInstaller",
    "InstallationError",
    "capability_slug",
]

#: 獲得能力の binding が公開する記号。**能力ごとに変えない。**
BINDING_FILE = "forge_binding.dart"
BINDING_SYMBOL = "capability"

#: 生成物を書き込んでよい唯一の場所（`frontend/` からの相対）。
INSTALL_ROOT = Path("lib/json_ui/acquired")
REGISTRATIONS_FILE = "acquired_registrations.g.dart"

_SLUG_UNSAFE = re.compile(r"[^a-z0-9]+")


class InstallationError(BuildTimeExtensionError):
    """**載せられなかった。** 載せられなかったことを、そう言う。"""


def capability_slug(capability_id: str) -> str:
    """`view.calendar` → `view_calendar`。**決定的で、衝突しない。**"""
    slug = _SLUG_UNSAFE.sub("_", capability_id.strip().lower()).strip("_")
    if not slug:
        raise InstallationError(f"capability id has no usable slug: {capability_id!r}")
    return slug


@dataclass(frozen=True, slots=True)
class AcquiredCapabilityInstallation:
    capability_id: str
    slug: str
    installed_files: tuple[str, ...]
    """`frontend/` からの相対パス。**証拠として読む。**"""


@dataclass(slots=True)
class FlutterCapabilityInstaller:
    """獲得能力を Forge の Flutter アプリへ載せる。

    `harness_files` と `host_prefix` は言語ごとの build plan が持つ宣言で
    あり、**能力ごとの表ではない**。
    """

    frontend_root: Path
    harness_files: frozenset[str]
    host_prefix: str = "flutter/"

    def install(
        self, artifact: BuildTimeCapabilityArtifact,
    ) -> AcquiredCapabilityInstallation:
        artifact.validate()
        slug = capability_slug(artifact.capability_id)
        target_dir = (self.frontend_root / INSTALL_ROOT / slug).resolve()
        root = (self.frontend_root / INSTALL_ROOT).resolve()
        if not root.is_dir():
            raise InstallationError(f"acquired capability root does not exist: {root}")

        planned: list[tuple[Path, str]] = []
        for source in artifact.files:
            relative = self._host_path(source.path)
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

        target_dir.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for destination, content in planned:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
            written.append(
                str(destination.relative_to(self.frontend_root.resolve())).replace("\\", "/"),
            )

        return AcquiredCapabilityInstallation(
            capability_id=artifact.capability_id,
            slug=slug,
            installed_files=tuple(sorted(written)),
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
        if path in self.harness_files:
            # 検証の道具は製品ではない。
            return None
        if path.startswith(self.host_prefix):
            return path[len(self.host_prefix):]
        return path
