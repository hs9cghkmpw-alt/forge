"""**逃げようとするプログラムを実際に走らせて、逃げられないことを見る**（EXT-08 / SEC-04）。

---

## AST の禁止語チェックを Sandbox と呼ばない

「危ない単語が入っていないか読む」のは静的解析であって隔離ではない。
ここでは**本物の攻撃プログラムを本物の Sandbox で実行**し、OS の側で
止まることを確かめる。読み落としがあっても止まる、が隔離の意味である。

## 配線破壊試験

`runner.py` の隔離を 1 つずつ外すと、対応する試験が落ちる。

| 外すもの | 落ちる試験 |
|---|---|
| `unshare -n`（network namespace） | `test_network_is_unreachable` |
| `_child_env` の env 作り直し | `test_secrets_do_not_reach_the_child` |
| `RLIMIT_CPU` / timeout | `test_an_infinite_loop_is_killed` |
| `RLIMIT_AS` | `test_a_memory_bomb_is_refused` |
| PID namespace | `test_processes_cannot_see_or_signal_the_host` |
| `available_backend` の None 返し | `test_it_refuses_to_run_without_a_backend` |

## Windows

この Corpus は Linux backend を検査する。**Windows backend は未実装**で
あり、そこでは `SandboxUnavailable` で実行が拒否される
（`test_it_refuses_to_run_without_a_backend`）。Linux だけ通ったことを
「Sandbox 完成」と読まないこと。
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from forge_ai.core.sandbox import (  # noqa: E402
    ALLOW_POLICY_ONLY_ENV,
    SandboxPolicy,
    SandboxUnavailable,
    SandboxViolation,
    available_backend,
    describe_environment,
    os_isolation_available,
    pid_isolation_available,
    policy_only_allowed,
    run_in_sandbox,
)

_BACKEND = available_backend()
_NEEDS_BACKEND = unittest.skipUnless(
    _BACKEND is not None,
    f"この環境に隔離 backend が無い（{describe_environment()}）。"
    "**素通しで実行して PASS にしない**——skip する",
)


class _SandboxCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_python(self, source: str, *, policy: SandboxPolicy | None = None):
        script = self.workspace / "attempt.py"
        script.write_text(textwrap.dedent(source), encoding="utf-8")
        return run_in_sandbox(
            [sys.executable, str(script)],
            workspace=self.workspace,
            policy=policy or SandboxPolicy(timeout_seconds=15, cpu_seconds=8),
        )


@_NEEDS_BACKEND
class TestTheSandboxActuallyRunsThings(_SandboxCase):
    """まず、**普通のものは動く**こと。動かないなら隔離ではなく故障である。"""

    def test_a_harmless_program_succeeds(self) -> None:
        result = self.run_python("print('hello from inside')")
        self.assertTrue(result.ok, result.stderr)
        self.assertIn("hello from inside", result.stdout)

    def test_it_can_write_inside_its_own_workspace(self) -> None:
        result = self.run_python("""
            open('output.txt', 'w').write('ok')
            print('wrote')
        """)
        self.assertTrue(result.ok, result.stderr)
        self.assertEqual((self.workspace / "output.txt").read_text(), "ok")


@_NEEDS_BACKEND
class TestEscapeCorpus(_SandboxCase):
    """**逃げようとするプログラム。** どれも成功してはならない。"""

    def test_network_is_unreachable(self) -> None:
        """外へ出られない。**loopback すら無い。**"""
        result = self.run_python("""
            import socket
            try:
                socket.create_connection(('1.1.1.1', 80), timeout=5)
                print('ESCAPED')
            except Exception as error:
                print('blocked:', type(error).__name__)
        """)
        self.assertNotIn("ESCAPED", result.stdout, "Network namespace が効いていない")
        self.assertIn("blocked:", result.stdout)

    def test_dns_is_unreachable(self) -> None:
        result = self.run_python("""
            import socket
            try:
                socket.gethostbyname('example.com')
                print('ESCAPED')
            except Exception as error:
                print('blocked:', type(error).__name__)
        """)
        self.assertNotIn("ESCAPED", result.stdout)

    def test_secrets_do_not_reach_the_child(self) -> None:
        """**2026-09-02 の事故と同じ形を Sandbox の中で繰り返さない。**"""
        os.environ["FORGE_SANDBOX_FAKE_SECRET"] = "must-not-be-visible"
        self.addCleanup(os.environ.pop, "FORGE_SANDBOX_FAKE_SECRET", None)

        result = self.run_python("""
            import os
            leaked = [k for k in os.environ if 'SECRET' in k or 'API' in k or 'KEY' in k]
            print('LEAKED', leaked)
            print('COUNT', len(os.environ))
        """)
        self.assertIn("LEAKED []", result.stdout, "Secret が子プロセスへ漏れている")

    def test_the_host_environment_is_not_inherited(self) -> None:
        result = self.run_python("""
            import os
            print('VARS', sorted(os.environ))
        """)
        # 継承していれば数十〜数百個ある。作り直していれば数個で収まる。
        self.assertNotIn("GEMINI_API_KEY", result.stdout)
        self.assertNotIn("ANTHROPIC", result.stdout)

    def test_an_infinite_loop_is_killed_by_the_wall_clock(self) -> None:
        """壁時計の timeout が効くこと。"""
        result = self.run_python(
            "while True:\n    pass\n",
            policy=SandboxPolicy(timeout_seconds=5, cpu_seconds=600),
        )
        self.assertFalse(result.ok, "無限ループが止まっていない")
        self.assertTrue(result.timed_out, "timeout で止まっていない")
        self.assertLess(result.duration_seconds, 20)

    def test_cpu_time_is_capped_independently_of_the_wall_clock(self) -> None:
        """**CPU 上限そのもの**が効くこと。

        壁時計 timeout を十分長くしておく。それでも CPU 秒で殺されるなら、
        止めているのは `RLIMIT_CPU` である。この分離が無いと、CPU 上限を
        外しても timeout が代わりに拾ってしまい、試験が置物になる
        （2026-09-04 の配線破壊試験で実際にそうなっていた）。
        """
        result = self.run_python(
            "while True:\n    pass\n",
            policy=SandboxPolicy(timeout_seconds=60, cpu_seconds=2),
        )
        self.assertFalse(result.ok, "CPU を使い切っても止まっていない")
        self.assertFalse(
            result.timed_out,
            "壁時計で止まった。CPU 上限が効いているか分からない",
        )
        # `unshare` が SIGXCPU を受けて自分で終了報告するため、exit code は
        # signal 値にならない（実測: `unshare: sigprocmask unblock failed`）。
        # したがって**時間で見る**。CPU 上限 2 秒に対し壁時計は 60 秒なので、
        # 数秒で終わったなら止めたのは CPU 上限である。上限を外せば
        # 60 秒走って `timed_out` になり、この試験は落ちる。
        self.assertLess(
            result.duration_seconds, 15,
            f"CPU 上限で止まっていない（壁時計まで走った可能性）: {result.to_dict()}",
        )

    def test_a_memory_bomb_is_refused(self) -> None:
        result = self.run_python("""
            chunks = []
            try:
                while True:
                    chunks.append(bytearray(50 * 1024 * 1024))
            except MemoryError:
                print('blocked: MemoryError')
        """, policy=SandboxPolicy(timeout_seconds=20, cpu_seconds=10,
                                  memory_bytes=256 * 1024 * 1024))
        # **`MemoryError` が出ることを要求する。**
        # 「終わらなかった」で満足すると、上限を外しても timeout が
        # 代わりに拾ってしまい試験が置物になる（2026-09-04 に実際そうだった）。
        self.assertIn(
            "blocked: MemoryError", result.stdout,
            f"RLIMIT_AS で止まっていない（timeout で拾っただけの可能性）: {result.to_dict()}",
        )

    def test_processes_cannot_see_or_signal_the_host(self) -> None:
        """**PID namespace が本体の防御である。**

        中から見える process は自分たちだけで、host の process へは
        届かない。`RLIMIT_NPROC` は数の上限にすぎず、しかも root では
        強制されない（下の試験参照）。**数の上限だけに頼らない。**
        """
        if not pid_isolation_available():
            self.skipTest("PID namespace が取れない環境（弱い隔離である事実を skip として残す）")

        result = self.run_python("""
            import os, signal
            print('MYPID', os.getpid())
            # host の init へ signal を送れてしまうなら隔離が無い。
            try:
                os.kill(1, 0)
                print('CAN_SIGNAL_PID1')
            except Exception as error:
                print('cannot signal outside:', type(error).__name__)
        """)
        self.assertIn("MYPID 1", result.stdout,
                      "PID namespace の中で pid 1 になっていない（隔離されていない）")

    def test_a_fork_bomb_is_contained(self) -> None:
        """fork bomb が **host へ広がらない**こと。

        **正直に書く。** `RLIMIT_NPROC` は実効 UID が root のとき
        強制されない（実測 2026-09-04: 上限 16 で fork 400 が通った）。
        したがってここで確かめるのは「数が止まる」ではなく、
        「namespace の外へ出ない・後始末される」である。
        数の上限が効くのは非 root 実行のときだけであり、それは
        `describe_environment()['nproc_limit_effective']` に出る。
        """
        if not pid_isolation_available():
            self.skipTest("PID namespace が取れない環境")

        result = self.run_python("""
            import os, time
            made = 0
            try:
                for _ in range(200):
                    if os.fork() == 0:
                        time.sleep(60)
                        os._exit(0)
                    made += 1
            except OSError as error:
                print('blocked after', made, type(error).__name__)
            print('MADE', made)
        """, policy=SandboxPolicy(timeout_seconds=8, cpu_seconds=5, max_processes=16))

        # timeout で leader ごと落ちる。namespace の外に残骸を残さない。
        self.assertLess(result.duration_seconds, 30, "fork bomb の後始末が終わっていない")

    def test_the_nproc_limit_is_reported_honestly(self) -> None:
        """**効かない制限を「効く」と書かない。**"""
        described = describe_environment()
        self.assertIn("nproc_limit_effective", described)
        if os.geteuid() == 0:
            self.assertFalse(
                described["nproc_limit_effective"],
                "root なのに RLIMIT_NPROC が効くと報告している",
            )

    def test_a_huge_file_write_is_capped(self) -> None:
        result = self.run_python("""
            try:
                with open('big.bin', 'wb') as handle:
                    for _ in range(200):
                        handle.write(b'x' * (1024 * 1024))
                print('ESCAPED')
            except Exception as error:
                print('blocked:', type(error).__name__)
        """, policy=SandboxPolicy(timeout_seconds=20, cpu_seconds=10,
                                  max_file_bytes=2 * 1024 * 1024))
        self.assertNotIn("ESCAPED", result.stdout, "ファイルサイズ上限が効いていない")


class TestItFailsClosed(unittest.TestCase):
    """**隔離できない環境では動かさない。**"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_it_refuses_to_run_without_a_backend(self) -> None:
        """Windows / macOS で起きること。**素通しで実行しない。**

        `FORGE_SANDBOX_ALLOW_POLICY_ONLY` を明示的に外して確かめる——
        CI はこれを立てて走るので、外さないと「既定の拒否」を見ていない
        ことになる（環境の設定でテストの意味が変わる、を避ける）。
        """
        saved = os.environ.pop(ALLOW_POLICY_ONLY_ENV, None)
        if saved is not None:
            self.addCleanup(os.environ.__setitem__, ALLOW_POLICY_ONLY_ENV, saved)

        with patch("forge_ai.core.sandbox.runner.available_backend", return_value=None):
            with self.assertRaises(SandboxUnavailable):
                run_in_sandbox([sys.executable, "-c", "print(1)"], workspace=self.workspace)

    def test_a_non_linux_platform_has_no_backend(self) -> None:
        with patch("forge_ai.core.sandbox.runner.platform.system", return_value="Windows"):
            self.assertIsNone(
                available_backend(),
                "Windows backend は未実装である。**実装したことにしない**",
            )

    def test_network_cannot_be_opened_yet(self) -> None:
        """`allow_network=True` は未実装。**黙って通さない。**"""
        with self.assertRaises(SandboxViolation):
            run_in_sandbox(
                [sys.executable, "-c", "print(1)"],
                workspace=self.workspace,
                policy=SandboxPolicy(allow_network=True),
            )

    def test_a_missing_workspace_is_refused(self) -> None:
        with self.assertRaises(SandboxViolation):
            run_in_sandbox(
                [sys.executable, "-c", "print(1)"],
                workspace=self.workspace / "does-not-exist",
            )

    def test_an_empty_argv_is_refused(self) -> None:
        with self.assertRaises(SandboxViolation):
            run_in_sandbox([], workspace=self.workspace)


class TestPolicyOnlyIsAllowedButNamed(unittest.TestCase):
    """OS 層が無い環境でも Policy 層だけで走れる。**ただし名前に残す。**

    GitHub Actions の runner は `unshare` が在っても namespace を作れない
    （2026-09-04 実測）。そこで Policy 層（AST/import 検査・実行ファイル固定・
    env scrub）だけで走る道を用意した。**弱いが 0 ではない。**

    危ないのは「弱い隔離を強い隔離と同じ名前で記録すること」なので、
    そこを試験で固定する。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._saved = os.environ.get(ALLOW_POLICY_ONLY_ENV)
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        if self._saved is None:
            os.environ.pop(ALLOW_POLICY_ONLY_ENV, None)
        else:
            os.environ[ALLOW_POLICY_ONLY_ENV] = self._saved

    def test_without_the_opt_in_it_still_refuses(self) -> None:
        """**既定は拒否のまま。** 環境が弱いだけで勝手に開かない。"""
        os.environ.pop(ALLOW_POLICY_ONLY_ENV, None)
        with patch("forge_ai.core.sandbox.runner.available_backend", return_value=None):
            with self.assertRaises(SandboxUnavailable):
                run_in_sandbox([sys.executable, "-c", "print(1)"], workspace=self.workspace)

    def test_a_typo_does_not_open_it(self) -> None:
        for value in ("ture", "yes-please", "0", "", "  "):
            with self.subTest(value=value):
                os.environ[ALLOW_POLICY_ONLY_ENV] = value
                self.assertFalse(policy_only_allowed(), f"{value!r} を真と読んでいる")

    def test_the_opt_in_runs_but_names_the_weaker_backend(self) -> None:
        os.environ[ALLOW_POLICY_ONLY_ENV] = "1"
        with patch("forge_ai.core.sandbox.runner.available_backend", return_value=None):
            result = run_in_sandbox(
                [sys.executable, "-c", "print('ran')"], workspace=self.workspace,
            )
        self.assertTrue(result.ok, result.stderr)
        self.assertEqual(
            result.backend, "policy-only",
            "弱い隔離を強い隔離と同じ名前で記録している",
        )
        self.assertNotEqual(result.backend, "", "空は「隔離せず走った」の意味であり別物")

    def test_policy_only_is_not_os_isolation(self) -> None:
        """**名前を混ぜない。** Evidence を読む側が区別できること。"""
        os.environ[ALLOW_POLICY_ONLY_ENV] = "1"
        with patch("forge_ai.core.sandbox.runner.available_backend", return_value=None):
            self.assertFalse(os_isolation_available())
            self.assertTrue(policy_only_allowed())

    def test_a_bad_request_is_refused_before_the_environment_is_consulted(self) -> None:
        """要求そのものの不正は、環境の有無より先に落とす。"""
        os.environ[ALLOW_POLICY_ONLY_ENV] = "1"
        with patch("forge_ai.core.sandbox.runner.available_backend", return_value=None):
            with self.assertRaises(SandboxViolation):
                run_in_sandbox(
                    [sys.executable, "-c", "print(1)"],
                    workspace=self.workspace,
                    policy=SandboxPolicy(allow_network=True),
                )


if __name__ == "__main__":
    unittest.main()
