"""Tool Sandbox — **道具が触れてよい範囲**（FORGE-020 §14、2026-08-25）。

---

## Model へ任意の path を渡させない

Agent へ `write_file(path, content)` を渡すと、`path` は Model が決める。
Model の入力には Web ページも Provider の出力も混ざるので、
`../../.env` や `/etc/passwd` が現れうる。

境界の判定を**呼ぶ側の礼儀**にしない。ここを通らなければ file 系の
道具が動かない形にする。

## 何を見るか

* 実体 path へ正規化してから比較する（`..` も symlink も畳む）
* workspace の**外**なら拒否
* 拒否リスト（`.env` / `.git` / 鍵ファイル）は workspace の中でも拒否
* 大きすぎる出力は切る（Model の窓を1ファイルで潰さない）

## 拒否リストを「名前に含むか」で書かない

`".env" in name` にすると `environment.md` まで拒否する。逆に
`.env.local` を見落とすような書き方もしない。**部品ごとに**見る。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

__all__ = [
    "SandboxViolation",
    "ToolSandbox",
    "ViolationKind",
]


class ViolationKind(str, Enum):
    OUTSIDE_WORKSPACE = "outside_workspace"
    DENIED_PATH = "denied_path"
    NOT_A_FILE = "not_a_file"
    TOO_LARGE = "too_large"


class SandboxViolation(Exception):
    """境界の外を触ろうとした。"""

    def __init__(self, kind: ViolationKind, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


#: workspace の中でも触らせないもの。
#:
#: **完全一致か、その配下か**で見る。部分一致にすると
#: `environment.md` まで巻き込む。
_DENIED_NAMES: frozenset[str] = frozenset({
    ".env", ".git", ".ssh", ".aws", ".npmrc", ".netrc",
    "id_rsa", "id_ed25519", "credentials", "secrets.json",
})

#: `.env.local` / `.env.production` のような派生。
_DENIED_PREFIXES: tuple[str, ...] = (".env.",)


@dataclass(frozen=True)
class ToolSandbox:
    """道具が触れてよい根。**ここを通さずに file を開かない。**"""

    root: Path
    max_read_bytes: int = 256_000

    @classmethod
    def at(cls, root: str | os.PathLike[str], **kwargs: object) -> "ToolSandbox":
        return cls(root=Path(root).resolve(), **kwargs)  # type: ignore[arg-type]

    def resolve(self, candidate: str | os.PathLike[str]) -> Path:
        """`candidate` を実体へ正規化し、境界の中であることを確かめる。

        **`..` を数えて弾く実装にしない。** symlink や絶対 path を
        見落とす。実体まで解決してから根と比べる。
        """
        target = (self.root / Path(candidate)).resolve()
        if target != self.root and self.root not in target.parents:
            raise SandboxViolation(
                ViolationKind.OUTSIDE_WORKSPACE,
                "作業領域の外は触らない",
            )
        self._reject_denied(target)
        return target

    def _reject_denied(self, target: Path) -> None:
        relative = target.relative_to(self.root) if target != self.root else Path()
        for part in relative.parts:
            if part in _DENIED_NAMES or part.startswith(_DENIED_PREFIXES):
                raise SandboxViolation(
                    ViolationKind.DENIED_PATH,
                    "secret / credential を含みうる path は読み書きしない",
                )

    def read_text(self, candidate: str | os.PathLike[str]) -> str:
        target = self.resolve(candidate)
        if not target.is_file():
            raise SandboxViolation(ViolationKind.NOT_A_FILE, "file ではない")
        data = target.read_bytes()
        if len(data) > self.max_read_bytes:
            # **切る。** 1ファイルで Model の窓を潰さない。
            data = data[: self.max_read_bytes]
        return data.decode("utf-8", errors="replace")

    def write_text(self, candidate: str | os.PathLike[str], content: str) -> Path:
        target = self.resolve(candidate)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def list_files(self, candidate: str | os.PathLike[str] = ".") -> tuple[str, ...]:
        target = self.resolve(candidate)
        if not target.is_dir():
            raise SandboxViolation(ViolationKind.NOT_A_FILE, "directory ではない")
        found: list[str] = []
        for entry in sorted(target.iterdir()):
            try:
                self._reject_denied(entry.resolve())
            except SandboxViolation:
                # 拒否対象は**存在も見せない**。名前だけでも手掛かりになる。
                continue
            found.append(str(entry.relative_to(self.root)))
        return tuple(found)

    def contains(self, candidate: str | os.PathLike[str]) -> bool:
        try:
            self.resolve(candidate)
        except SandboxViolation:
            return False
        return True
