"""**API キーがそこにあることは、呼んでよいという同意ではない。**

---

## 何の回帰テストか

2026-09-02、Visual Evidence を撮るために作業ホストで backend を起動した。
そのコンテナの `backend/.env` に実 API キーが入っており、`/converse` を
2 回叩いた時点で実 Gemini API が呼ばれた。誰も「実 API を呼べ」とは
言っていない。**キーがそこにあったから呼ばれた。**

運用の不注意である前に Architecture の穴である。ここはその穴を塞いだ
ことを固定する。

## 配線破壊試験

`openai_compatible.py` / `providers.py` の `assert_external_call_allowed(...)`
を削ると、このファイルの `TestTheEgressPointsAreGuarded` が落ちる。
落ちなければ置物である。
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
import unittest
from unittest.mock import patch

_ROOT = pathlib.Path(__file__).resolve().parents[2]
for path in (str(_ROOT), str(_ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

import httpx  # noqa: E402

from app.ai.foundation.local_provider import LocalModelProvider  # noqa: E402
from app.ai.foundation.openai_compatible import OpenAICompatibleAdapter  # noqa: E402
from app.ai.foundation.providers import GeminiProvider  # noqa: E402
from app.ai.gateway.external_call_policy import (  # noqa: E402
    ALLOW_REAL_PROVIDER_CALLS_ENV,
    REAL_PROVIDER_TEST_ENV,
    ExternalCallDenied,
    allow_mocked_transport,
    assert_external_call_allowed,
    describe_policy,
    external_provider_calls_allowed,
    local_provider_calls_allowed,
)

_SCHEMA: dict = {"type": "object", "properties": {}}


class _EnvBase(unittest.TestCase):
    """環境変数を一時的に置き換える（他テストへ漏らさない）。"""

    def _env(self, **values: str | None) -> None:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
            self.addCleanup(self._restore, name, os.environ.get(name))

    @staticmethod
    def _restore(name: str, _current: str | None) -> None:
        os.environ.pop(name, None)


class TestTheDefaultIsDeny(_EnvBase):
    def setUp(self) -> None:
        self._env(**{ALLOW_REAL_PROVIDER_CALLS_ENV: None, REAL_PROVIDER_TEST_ENV: None})

    def test_nothing_set_means_no_external_calls(self) -> None:
        self.assertFalse(external_provider_calls_allowed())

    def test_a_cloud_call_is_refused(self) -> None:
        with self.assertRaises(ExternalCallDenied) as caught:
            assert_external_call_allowed(provider_id="gemini", deployment="cloud")
        self.assertEqual(caught.exception.provider_id, "gemini")

    def test_an_api_key_is_not_consent(self) -> None:
        """**これが事故の核心である。** キーの存在で開かない。"""
        self._env(GEMINI_API_KEY="dummy-value-not-a-real-key")
        self.assertFalse(external_provider_calls_allowed())
        with self.assertRaises(ExternalCallDenied):
            assert_external_call_allowed(provider_id="gemini", deployment="cloud")

    def test_an_unknown_deployment_is_treated_as_external(self) -> None:
        """分からないものを楽観側へ倒さない。"""
        with self.assertRaises(ExternalCallDenied):
            assert_external_call_allowed(provider_id="mystery", deployment="")
        with self.assertRaises(ExternalCallDenied):
            assert_external_call_allowed(provider_id="mystery", deployment="edge")


class TestItFailsClosedOnBadValues(_EnvBase):
    def test_a_typo_does_not_open_the_gate(self) -> None:
        for value in ("ture", "TRUE-ish", "0", "no", "", "  ", "maybe", "2"):
            with self.subTest(value=value):
                self._env(**{
                    ALLOW_REAL_PROVIDER_CALLS_ENV: value,
                    REAL_PROVIDER_TEST_ENV: "1",
                })
                self.assertFalse(
                    external_provider_calls_allowed(),
                    f"{value!r} を「真」と解釈している",
                )

    def test_the_accepted_values_are_explicit(self) -> None:
        for value in ("1", "true", "TRUE", " yes ", "on"):
            with self.subTest(value=value):
                self._env(**{
                    ALLOW_REAL_PROVIDER_CALLS_ENV: value,
                    REAL_PROVIDER_TEST_ENV: "1",
                })
                self.assertTrue(external_provider_calls_allowed())


class TestTestsNeedASecondExplicitOptIn(_EnvBase):
    """通常の unit / integration test からは、opt-in 1つでは開かない。"""

    def test_the_allow_flag_alone_is_not_enough_under_pytest(self) -> None:
        self._env(**{ALLOW_REAL_PROVIDER_CALLS_ENV: "1", REAL_PROVIDER_TEST_ENV: None})
        self.assertIn("PYTEST_CURRENT_TEST", os.environ, "このテストは pytest で動く前提")
        self.assertFalse(external_provider_calls_allowed())

    def test_both_flags_open_it(self) -> None:
        self._env(**{ALLOW_REAL_PROVIDER_CALLS_ENV: "1", REAL_PROVIDER_TEST_ENV: "1"})
        self.assertTrue(external_provider_calls_allowed())


class TestLocalIsAllowedInProductionButNotInTests(_EnvBase):
    def test_local_is_denied_while_testing(self) -> None:
        self._env(**{REAL_PROVIDER_TEST_ENV: None})
        self.assertFalse(local_provider_calls_allowed())
        with self.assertRaises(ExternalCallDenied):
            assert_external_call_allowed(provider_id="local", deployment="local")

    def test_local_needs_no_env_var_outside_tests(self) -> None:
        """Local-first は製品の中核である。**利用者に環境変数を触らせない。**"""
        self._env(**{REAL_PROVIDER_TEST_ENV: None})
        with patch(
            "app.ai.gateway.external_call_policy.running_under_test",
            return_value=False,
        ):
            self.assertTrue(local_provider_calls_allowed())
            assert_external_call_allowed(provider_id="local", deployment="local")


class TestMockedTransportIsNotACall(_EnvBase):
    def test_declaring_a_mocked_transport_permits_the_call(self) -> None:
        self._env(**{ALLOW_REAL_PROVIDER_CALLS_ENV: None})
        with allow_mocked_transport():
            assert_external_call_allowed(provider_id="gemini", deployment="cloud")

    def test_the_declaration_does_not_leak_past_the_block(self) -> None:
        with allow_mocked_transport():
            pass
        with self.assertRaises(ExternalCallDenied):
            assert_external_call_allowed(provider_id="gemini", deployment="cloud")


class TestTheEgressPointsAreGuarded(_EnvBase):
    """**配線試験の本体。** 実際の Provider から出ようとして止まること。"""

    def setUp(self) -> None:
        # 「キーはあるが同意は無い」状態を作る。値は本物ではない。
        self._env(**{
            ALLOW_REAL_PROVIDER_CALLS_ENV: None,
            REAL_PROVIDER_TEST_ENV: None,
            "GEMINI_API_KEY": "dummy-value-not-a-real-key",
        })

    def test_gemini_with_a_key_but_no_consent_is_refused(self) -> None:
        """2026-09-02 の事故そのものの形。"""
        provider = GeminiProvider()
        with self.assertRaises(ExternalCallDenied):
            provider.complete_structured("何か作りたい", _SCHEMA)

    def test_an_injected_mock_client_still_works(self) -> None:
        """MockTransport を注いだ Test は外へ出ていないので止めない。"""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
            })

        provider = GeminiProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.assertEqual(provider.complete_structured("何か", _SCHEMA), {})

    def test_the_local_runtime_is_refused_while_testing(self) -> None:
        provider = LocalModelProvider(base_url="http://127.0.0.1:11434/v1", model="x")
        with self.assertRaises(ExternalCallDenied):
            provider.complete_structured("何か作りたい", _SCHEMA)

    def test_the_generic_adapter_defaults_to_cloud(self) -> None:
        """**既定を `local` にすると穴が開く。**

        `OpenAICompatibleAdapter` は Cloud にも Local にも使われる。既定が
        `"local"` だと、名乗り忘れた Cloud Provider が本番で無承認のまま
        外へ出てしまう（テスト中しか止まらない）。既定は `"cloud"` で
        なければならない——分からないものを楽観側へ倒さない。

        `running_under_test` を偽装して「本番相当」で確かめる。ここを
        偽装しないと、local 既定でもテスト中は止まるため差が見えない。
        """
        self.assertEqual(OpenAICompatibleAdapter.deployment, "cloud")

        adapter = OpenAICompatibleAdapter(
            provider_name="some-cloud", base_url="https://example.invalid/v1",
            model="m", api_key_env=None,
        )
        with patch(
            "app.ai.gateway.external_call_policy.running_under_test",
            return_value=False,
        ):
            with self.assertRaises(ExternalCallDenied):
                adapter.complete_structured("何か作りたい", _SCHEMA)

            # 同じ条件で、Local は通る（差が Deployment だけであること）。
            LocalModelProvider(
                base_url="http://127.0.0.1:11434/v1", model="x",
            )  # 構築は常に自由
            assert_external_call_allowed(provider_id="local", deployment="local")


class TestNoUnguardedEgressPointAppears(unittest.TestCase):
    """**新しい出口が増えても気付ける。**

    「呼び出し側が忘れずに Policy を確認する」設計は忘れられる
    （CLAUDE.md §3）。`app/ai/foundation` に新しい `httpx.Client(` が
    増えたら、このテストが名指しで落ちる。
    """

    #: すでに Policy を通していると確認済みの出口。
    KNOWN_GUARDED = {
        ("providers.py", "GeminiProvider"),
        ("openai_compatible.py", "OpenAICompatibleAdapter._chat"),
    }

    def test_every_client_construction_sits_next_to_the_policy_check(self) -> None:
        foundation = _ROOT / "backend" / "app" / "ai" / "foundation"
        offenders: list[str] = []
        for path in sorted(foundation.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for match in re.finditer(r"^\s*(?:\w+\s*=\s*)?(?:with\s+)?httpx\.Client\(", source, re.M):
                line_no = source[: match.start()].count("\n") + 1
                window = "\n".join(source.split("\n")[max(0, line_no - 12) : line_no])
                if "assert_external_call_allowed" not in window:
                    offenders.append(f"{path.name}:{line_no}")
        self.assertEqual(
            offenders, [],
            "Policy を通さずに httpx.Client を作っている箇所がある: "
            f"{offenders}。`assert_external_call_allowed(...)` を直前へ置くこと。",
        )


class TestThePolicyIsReportableWithoutLeakingValues(unittest.TestCase):
    def test_describe_policy_has_no_values(self) -> None:
        described = describe_policy()
        self.assertIn("external_provider_calls_allowed", described)
        for value in described.values():
            self.assertNotIsInstance(
                value, bytes, "Policy の説明に生の値が混じっている",
            )
        # 変数「名」は返すが、値は返さない。
        self.assertEqual(described["allow_env_name"], ALLOW_REAL_PROVIDER_CALLS_ENV)
        self.assertNotIn("api_key", str(described).lower())


if __name__ == "__main__":
    unittest.main()
