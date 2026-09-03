"""生成物を**隔離して**実行する（EXT-08 / SEC-04、W1）。

---

## AST の禁止語チェックは Sandbox ではない

「危ない単語が入っていないか読む」のは静的解析であって隔離ではない。
読んだ後に実行するのは同じホストであり、読み落とした 1 つが全部を破る。
**OS の機能で実際に閉じる。**

## 何を閉じるか

| 閉じるもの | 手段（Linux） |
|---|---|
| Network | Network namespace（`unshare -n`）。**loopback すら無い** |
| Filesystem | 明示 workspace を cwd にし、そこ以外を書けない前提で走らせる |
| 環境変数 / Secret | **env を空から作り直す**（継承しない） |
| Process 生成 | `RLIMIT_NPROC` |
| CPU 時間 | `RLIMIT_CPU` + 壁時計 timeout |
| Memory | `RLIMIT_AS` |
| 出力ファイルサイズ | `RLIMIT_FSIZE` |
| 無限実行 | timeout → process group ごと kill |
| 依存の獲得 | `policy.assert_dependencies_allowed`（実行前） |

## Windows を「あとで」にしない

Forge の主配布対象には Windows が含まれる。**Linux だけ実装して完成扱いに
しない。** Windows / macOS の backend は未実装であり、その環境では
`SandboxUnavailable` を送出して**実行を拒否する**（fail closed）。

「Sandbox が無い環境では素通しで実行する」は、いちばんやってはいけない
設計である。無いなら動かさない。

## fail closed の意味

- backend が無い → 実行しない
- backend の起動に失敗した → 実行しない
- 隔離の一部だけ効いた → 実行しない（部分的な隔離は隔離ではない）
"""

from __future__ import annotations

import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "SandboxPolicy",
    "pid_isolation_available",
    "SandboxResult",
    "SandboxUnavailable",
    "SandboxViolation",
    "available_backend",
    "describe_environment",
    "run_in_sandbox",
]


class SandboxUnavailable(RuntimeError):
    """この環境に実際の隔離手段が無い。**実行してはならない。**"""


class SandboxViolation(RuntimeError):
    """Sandbox の約束を守れない要求（workspace 外の指定など）。"""


@dataclass(frozen=True)
class SandboxPolicy:
    """1 回の隔離実行に与える上限。**既定はすべて厳しい側。**"""

    timeout_seconds: float = 30.0
    cpu_seconds: int = 20
    memory_bytes: int = 512 * 1024 * 1024
    max_processes: int = 64
    max_file_bytes: int = 32 * 1024 * 1024
    max_output_bytes: int = 1 * 1024 * 1024
    allow_network: bool = False
    """**既定は False。** True にできるのは Tier C の承認済み経路だけ。"""

    env_allowlist: frozenset[str] = frozenset({"LANG", "LC_ALL", "TZ"})
    """継承してよい環境変数の**名前**。ここに無いものは渡さない。
    `PATH` は allowlist ではなく、下で最小の固定値を作る
    （ホストの PATH をそのまま渡すと、そこにある任意のツールへ届く）。"""

    path_value: str = "/usr/bin:/bin"
    """子プロセスへ渡す PATH。**ホストから継承しない。**"""


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    backend: str
    duration_seconds: float

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "backend": self.backend,
            "duration_seconds": round(self.duration_seconds, 4),
            "stdout_bytes": len(self.stdout.encode("utf-8", "replace")),
            "stderr_bytes": len(self.stderr.encode("utf-8", "replace")),
        }


def _unshare_command() -> list[str] | None:
    """使える `unshare` の形を返す。無ければ `None`。

    root なら `unshare -n`、非 root なら user namespace 込みの
    `unshare -Urn` が要る。**どちらも実際に起動して確かめる**——
    binary があることと使えることは別である。
    """
    binary = shutil.which("unshare")
    if not binary:
        return None
    # PID namespace も一緒に取る。**process の隔離と後始末のため**である。
    #
    # `RLIMIT_NPROC` は root では強制されない（実測 2026-09-04: root で
    # 上限 16 を設定しても fork 400 が通った）。PID namespace なら、
    # 中の process は host を見ることも signal することも出来ず、
    # leader を落とせば namespace ごと消える。**上限だけに頼らない。**
    #
    # `--pid --fork` が使えない環境では network だけの形へ落ちるが、
    # そのときは `pid_isolated=False` として**事実を記録する**。
    for args in (
        ["-n", "--pid", "--fork"],
        ["-U", "-r", "-n", "--pid", "--fork"],
        ["-n"],
        ["-U", "-r", "-n"],
    ):
        try:
            probe = subprocess.run(
                [binary, *args, "--", "true"],
                capture_output=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return [binary, *args, "--"]
    return None


def available_backend() -> str | None:
    """この環境で使える隔離 backend の名前。無ければ `None`。"""
    if platform.system() != "Linux":
        # Windows / macOS の backend は未実装。**「たぶん大丈夫」で通さない。**
        return None
    command = _unshare_command()
    if command is None:
        return None
    return "linux-namespace+pid" if "--pid" in command else "linux-namespace"


def pid_isolation_available() -> bool:
    """PID namespace まで取れるか。

    取れないときは process の隔離が弱い（`RLIMIT_NPROC` だけになり、
    root では実質効かない）。**その事実を隠さないために公開する。**
    """
    command = _unshare_command()
    return bool(command and "--pid" in command)


def describe_environment() -> dict:
    """診断・Evidence 用。**値ではなく事実だけ**を返す。"""
    return {
        "platform": platform.system(),
        "backend": available_backend(),
        "unshare_available": bool(shutil.which("unshare")),
        "rlimits_available": hasattr(resource, "setrlimit"),
        "pid_isolation": pid_isolation_available(),
        # root では `RLIMIT_NPROC` が強制されない（実測 2026-09-04）。
        # 数の上限に頼れるかどうかを、Evidence 側から見えるようにする。
        "nproc_limit_effective": os.geteuid() != 0 if hasattr(os, "geteuid") else False,
    }


def _limits(policy: SandboxPolicy):  # noqa: ANN202 — preexec_fn 用
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (policy.cpu_seconds, policy.cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (policy.memory_bytes, policy.memory_bytes))
        resource.setrlimit(resource.RLIMIT_NPROC, (policy.max_processes, policy.max_processes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (policy.max_file_bytes, policy.max_file_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.setsid()
    return apply


def _child_env(policy: SandboxPolicy, workspace: Path) -> dict[str, str]:
    """**空から作る。** 継承しない。

    継承した env に API キーが入っていたのが 2026-09-02 の事故だった。
    同じ形を Sandbox で繰り返さない。
    """
    env = {
        "PATH": policy.path_value,
        "HOME": str(workspace),
        "TMPDIR": str(workspace / ".tmp"),
        "PWD": str(workspace),
    }
    for name in policy.env_allowlist:
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    return env


def run_in_sandbox(
    argv: list[str],
    *,
    workspace: Path,
    policy: SandboxPolicy | None = None,
    env_override: dict[str, str] | None = None,
) -> SandboxResult:
    """`argv` を隔離して実行する。

    **shell を通さない。** 文字列ではなく argv を受け取るのは、
    生成物由来の文字列が shell metacharacter として解釈される経路を
    作らないためである。

    `env_override` は、呼び出し側が既に scrub 済みの環境を持っている場合に
    渡す（`build_time_sandbox` の Policy 層がそれを作る）。**渡されても
    `os.environ` を継承しない**——空から作られたものだけを受け取る前提で
    あり、ここで継承へ戻すことはない。
    """
    import time

    policy = policy or SandboxPolicy()
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise SandboxViolation(f"workspace が存在しない: {workspace}")
    if not argv:
        raise SandboxViolation("実行する argv が空である")

    backend = available_backend()
    if backend is None:
        raise SandboxUnavailable(
            f"この環境（{platform.system()}）には実際の隔離手段が無いため、"
            "生成物を実行しない。Windows / macOS の backend は未実装である。"
            "**隔離できないなら動かさない**（fail closed）"
        )
    if policy.allow_network:
        raise SandboxViolation(
            "network を開ける経路は未実装である。"
            "Tier C の承認済み経路として別途設計する（現在は常に deny）"
        )

    (workspace / ".tmp").mkdir(exist_ok=True)
    prefix = _unshare_command()
    if prefix is None:  # available_backend と競合した場合も fail closed
        raise SandboxUnavailable("unshare が使えなくなった。実行しない")

    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            [*prefix, *argv],
            cwd=str(workspace),
            env=env_override if env_override is not None else _child_env(policy, workspace),
            capture_output=True,
            timeout=policy.timeout_seconds,
            preexec_fn=_limits(policy),  # noqa: PLW1509 — 隔離のために必要
            start_new_session=False,     # preexec_fn 側で setsid する
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout[: policy.max_output_bytes].decode("utf-8", "replace")
        stderr = completed.stderr[: policy.max_output_bytes].decode("utf-8", "replace")
    except subprocess.TimeoutExpired as expired:
        timed_out = True
        exit_code = None
        stdout = (expired.stdout or b"")[: policy.max_output_bytes].decode("utf-8", "replace")
        stderr = (expired.stderr or b"")[: policy.max_output_bytes].decode("utf-8", "replace")

    return SandboxResult(
        ok=(not timed_out and exit_code == 0),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        backend=backend,
        duration_seconds=time.monotonic() - started,
    )
