"""数値環境変数の共通境界
(FORGE-PRE-R1-INTEGRITY-GATE-013 §2、2026-08-17)。

---

## 直した実バグ

`.env.example` をコピーすると、この行が `.env` に入る。

    FORGE_GROQ_TIMEOUT_SECONDS=

「任意なので空でよい」という意図の行である。しかし読む側は

    float(os.environ.get("FORGE_GROQ_TIMEOUT_SECONDS", 60.0))

だった。**環境変数は存在する**(値が空文字)ので`os.environ.get`は
既定値を返さず`""`を返し、`float("")`が`ValueError`になる。

実測した影響は報告より広かった: `ProviderRouter`は起動時に**全Provider**
を構築するので、**1つ空なだけでForge全体が起動しない**。

## このファイルが守るもの

1. 契約(未設定/空/whitespace/整数/小数/不正/範囲外)
2. **本番の構築経路**が空文字で壊れないこと
3. **生の`float(os.environ...)`が再び現れないこと**(source scan)

3が要点である。1と2だけなら、新しいProviderを足す人が同じ書き方を
すればまた壊れる。「気を付ける」に依存する形は、Forgeが4回繰り返した
失敗と同じである(`CLAUDE.md` §3)。
"""

from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.env_settings import (  # noqa: E402
    ConfigurationError,
    env_float,
    env_int,
)

_NAME = "FORGE_TEST_ONLY_NUMERIC"


class _EnvCase(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop(_NAME, None)

    def tearDown(self) -> None:
        os.environ.pop(_NAME, None)


class TestTheContract(_EnvCase):
    def test_absent_uses_the_default(self) -> None:
        self.assertEqual(env_float(_NAME, 60.0), 60.0)

    def test_empty_uses_the_default(self) -> None:
        """**これが実バグである。**

        `.env`で任意項目を空にしておくのは普通の書き方であり、
        これをエラーにすると正しい使い方が壊れる。
        """
        os.environ[_NAME] = ""
        self.assertEqual(env_float(_NAME, 60.0), 60.0)

    def test_whitespace_only_uses_the_default(self) -> None:
        os.environ[_NAME] = "   "
        self.assertEqual(env_float(_NAME, 60.0), 60.0)

    def test_an_integer_string_is_read(self) -> None:
        os.environ[_NAME] = "30"
        self.assertEqual(env_float(_NAME, 60.0), 30.0)

    def test_a_float_string_is_read(self) -> None:
        os.environ[_NAME] = "30.5"
        self.assertEqual(env_float(_NAME, 60.0), 30.5)

    def test_surrounding_whitespace_is_tolerated(self) -> None:
        os.environ[_NAME] = "  30  "
        self.assertEqual(env_float(_NAME, 60.0), 30.0)

    def test_a_broken_value_is_not_silently_defaulted(self) -> None:
        """**黙って既定値へ倒さない。**

        倒すと「設定したつもりで効いていない」が静かに続く。
        空文字(=書いていない)と、壊れた値(=書いたが読めない)は違う。
        """
        for raw in ("abc", "30s", "1,000", "30 seconds", "true"):
            with self.subTest(raw=raw):
                os.environ[_NAME] = raw
                with self.assertRaises(ConfigurationError):
                    env_float(_NAME, 60.0)

    def test_python_accepts_full_width_digits_and_underscores(self) -> None:
        """**書いてみて分かったことを、そのまま固定しておく。**

        最初、全角の`３０`は「壊れた値」として弾かれると想定して
        テストを書いたが、落ちなかった。Pythonの`float()`は全角数字も
        桁区切りのアンダースコアも受け付け、**利用者が意図した値**に
        解釈する。

            float("３０")    -> 30.0
            float("1_000")  -> 1000.0

        つまりこれは「読めない値」ではないので、弾く理由が無い。
        私の想定の方が間違っていた——という事実を残しておく
        (次に見た人が「全角を弾く処理が抜けている」と誤解しないため)。
        """
        os.environ[_NAME] = "３０"
        self.assertEqual(env_float(_NAME, 60.0), 30.0)
        os.environ[_NAME] = "1_000"
        self.assertEqual(env_float(_NAME, 60.0), 1000.0)

    def test_out_of_range_is_an_error(self) -> None:
        for raw in ("0", "-5"):
            with self.subTest(raw=raw):
                os.environ[_NAME] = raw
                with self.assertRaises(ConfigurationError):
                    env_float(_NAME, 60.0, minimum=0.1)

    def test_infinity_and_nan_are_rejected(self) -> None:
        """`float()`は通してしまうが、timeoutにもsizeにも使えない。"""
        for raw in ("inf", "-inf", "nan", "Infinity"):
            with self.subTest(raw=raw):
                os.environ[_NAME] = raw
                with self.assertRaises(ConfigurationError):
                    env_float(_NAME, 60.0)

    def test_the_error_says_which_variable_and_what_to_do(self) -> None:
        os.environ[_NAME] = "abc"
        with self.assertRaises(ConfigurationError) as raised:
            env_float(_NAME, 60.0)
        message = str(raised.exception)
        self.assertIn(_NAME, message)
        self.assertIn("abc", message)
        self.assertIn("削除", message, "直し方が書かれていない。")

    def test_an_int_setting_does_not_silently_truncate(self) -> None:
        """整数を要求する場所で小数を切り捨てると、設定した値と動く値が
        ずれる。"""
        os.environ[_NAME] = "30.5"
        with self.assertRaises(ConfigurationError):
            env_int(_NAME, 60)

    def test_int_reads_integers(self) -> None:
        os.environ[_NAME] = "30"
        self.assertEqual(env_int(_NAME, 60), 30)
        self.assertIsInstance(env_int(_NAME, 60), int)


class TestTheProductionPathSurvivesAnEmptyValue(_EnvCase):
    """**契約だけでなく、本番の構築経路で確かめる。**

    `env_float`単体が正しくても、呼んでいなければ意味が無い。
    """

    _VARS = (
        "FORGE_LOCAL_TIMEOUT_SECONDS",
        "FORGE_GROQ_TIMEOUT_SECONDS",
        "FORGE_CEREBRAS_TIMEOUT_SECONDS",
        "FORGE_OPENROUTER_TIMEOUT_SECONDS",
        "FORGE_TOGETHER_TIMEOUT_SECONDS",
        "FORGE_DEEPINFRA_TIMEOUT_SECONDS",
    )

    def setUp(self) -> None:
        self._saved = {name: os.environ.get(name) for name in self._VARS}

    def tearDown(self) -> None:
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_the_router_still_builds_with_every_timeout_empty(self) -> None:
        """**Forge全体が起動しなくなっていた形の回帰。**

        `ProviderRouter`は起動時に全Providerを構築するので、1つ空な
        だけで全部落ちる。
        """
        from app.ai.runtime.provider_router import ProviderRouter  # noqa: PLC0415

        for name in self._VARS:
            os.environ[name] = ""
        router = ProviderRouter()
        self.assertTrue(router.available_providers())

    def test_the_local_provider_falls_back_to_its_default_timeout(self) -> None:
        from app.ai.foundation.local_provider import LocalModelProvider  # noqa: PLC0415

        os.environ["FORGE_LOCAL_TIMEOUT_SECONDS"] = ""
        empty = LocalModelProvider()
        os.environ.pop("FORGE_LOCAL_TIMEOUT_SECONDS")
        absent = LocalModelProvider()
        self.assertEqual(empty._timeout, absent._timeout)  # noqa: SLF001

    def test_a_generic_cloud_provider_survives_an_empty_timeout(self) -> None:
        from app.ai.foundation.cloud_provider import (  # noqa: PLC0415
            OpenAICompatibleCloudProvider,
        )

        os.environ["FORGE_GROQ_TIMEOUT_SECONDS"] = ""
        self.assertGreater(OpenAICompatibleCloudProvider("groq")._timeout, 0)  # noqa: SLF001

    def test_a_broken_timeout_is_reported_clearly_not_as_a_crash(self) -> None:
        from app.ai.foundation.local_provider import LocalModelProvider  # noqa: PLC0415

        os.environ["FORGE_LOCAL_TIMEOUT_SECONDS"] = "30秒"
        with self.assertRaises(ConfigurationError):
            LocalModelProvider()


class TestNobodyReadsNumbersFromTheEnvironmentDirectly(unittest.TestCase):
    """**新しいProviderを足す人が、同じ書き方でまた壊せないこと。**

    `test_router_anti_bypass.py`と同じ姿勢である——「共通関数がある」
    ではなく「共通関数を通らない経路が存在しない」を測る。

    ASTで見るのは、コメントや文字列の中に書かれた説明文
    (このファイルのdocstringを含む)を拾わないためである。
    """

    _ALLOWED = {"app/core/env_settings.py"}

    def test_no_source_file_calls_float_or_int_on_os_environ(self) -> None:
        root = pathlib.Path(__file__).resolve().parent.parent / "app"
        offenders: list[str] = []
        for path in root.rglob("*.py"):
            relative = path.relative_to(root.parent).as_posix()
            if relative in self._ALLOWED:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (isinstance(node.func, ast.Name) and node.func.id in ("float", "int")):
                    continue
                if any(_touches_environ(arg) for arg in node.args):
                    offenders.append(f"{relative}:{node.lineno}")
        self.assertEqual(
            offenders, [],
            "環境変数を直接数値化している箇所がある: "
            f"{offenders}。`app/core/env_settings.py`の`env_float`/`env_int`を"
            "使うこと——生の`float(os.environ.get(...))`は、`.env`の空欄で"
            "Forge全体を起動不能にする(013 §2で実際に踏んだ)。",
        )


def _touches_environ(node: ast.AST) -> bool:
    """その式が`os.environ`に触れているか。"""
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr == "environ":
            return True
        if isinstance(child, ast.Name) and child.id == "environ":
            return True
    return False


if __name__ == "__main__":
    unittest.main()
