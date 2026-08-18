"""Live API Test(FORGE-AI-FOUNDATION-010 Phase I、2026-08-13)。

**既定では走らない。** 実APIを叩くテストが既定で走ると、

* CIやチームメンバーの手元で、意図せず無料枠を消費する
* ネットワークやProvider障害で、コードと無関係に赤くなる
* 実行時間が数秒〜数十秒になり、他のテストの速さが失われる

ため、`FORGE_LIVE_TEST=1`を明示した場合だけ実行する。鍵が無ければ
その時点でSKIPする(**失敗にしない**——鍵が無いのは環境の状態で
あって、コードの誤りではない)。

    FORGE_LIVE_TEST=1 python -m pytest tests/test_live_api.py -v

---

## 消費量について(§38)

指示書:「429を出すために無料枠を大量消費しないでください」。

このファイル全体で**実API呼び出しは最大2回**である。1回は
「実際に応答が返るか」、もう1回は「Router経由でも同じか」。
Rate Limitや枠切れの挙動は**実際に枠を使い切って確かめない**
——`tests/test_ai_router.py`と`tests/test_openai_compatible.py`が
Test Doubleで検査している。

「実際に429が起きたときに正しく動くか」は、**このテストでは
確かめていない**(§39: 未検証を検証済みとして書かない)。

## 何を確かめるか

Test Doubleでは原理的に確かめられないことだけに絞る:

* Providerが**実際に応答を返す**こと(鍵・エンドポイント・
  モデル名・SDKバージョンが揃っていること)
* 構造化出力が**実際にスキーマを満たす**こと。Mockは常に
  満たすので、ここはDoubleでは測れない
* Router経由でも同じ結果になること(配線の実地確認)

## 秘密の扱い(§67)

鍵の値は読まない・出力しない。`os.environ`にあるかどうかだけを見る。
失敗時のメッセージにも応答本文の先頭しか載せない。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.ai_router import AIRouter, ModelDescriptor  # noqa: E402
from app.ai.gateway.provider_registry import (  # noqa: E402
    Deployment,
    ImplementationStatus,
    configured_providers,
    definition_for,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402
from app.ai.runtime.provider_router import ProviderRouter  # noqa: E402

_LIVE_ENABLED = os.environ.get("FORGE_LIVE_TEST", "").strip() == "1"

if _LIVE_ENABLED:
    # `backend/.env`を読む。**Live実行のときだけ**である。
    #
    # 運用者が鍵を置く場所は`.env`であり(`app/main.py`が本番でそこから
    # 読む)、それを読まないと「鍵は設定してあるのに全部SKIPされる」と
    # いう、原因の分からない無反応になる。逆に、通常のテスト実行で
    # `.env`を読み込んでしまうと、`conftest.py`がProviderをmockへ固定
    # している意味が薄れる(実鍵が環境に入る)。だから条件付きにする。
    #
    # `load_dotenv()`は既存の環境変数を上書きしない——CI等で明示的に
    # 渡された値の方が優先される。
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# 実APIへ投げる唯一のプロンプト。**短く・無害・決定的に判定できる**
# ものにする。長いプロンプトはトークンを食うだけで、確かめたいこと
# (応答が返るか・スキーマを満たすか)は変わらない。
_PROBE_PROMPT = (
    "次のJSONを返してください。"
    'キー"status"の値は文字列"ok"、キー"count"の値は整数3にしてください。'
)
_PROBE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "count": {"type": "integer"},
    },
    "required": ["status", "count"],
}


# 運用者が「このProviderを試したい」と名指しできる口。
#
# **無いと、新しく足したProviderを狙って試せない。** Registryの順で
# 選ぶと、既に設定済みのGeminiが常に先に当たり、今日追加したばかりの
# Providerには一度も届かない——「設定したのに何も起きない」になる。
_LIVE_PROVIDER_ENV = "FORGE_LIVE_PROVIDER"


class LiveProviderNotUsable(RuntimeError):
    """名指しされたProviderが叩けない。**黙ってSKIPしない**ためにある。"""


def _live_provider_id() -> str | None:
    """実際に叩ける実装済みCloud Providerを1つ選ぶ。

    複数設定されていても**1つだけ**にする——全部叩けば、その分だけ
    枠を消費する(§38)。

    ---

    ## 2026-08-17に直した実バグ

    以前はここが `("gemini", "cloud")` という**固定の名前**を見ていた。
    しかし`cloud`は011で廃止されている——「今日Groq・明日Cerebrasを
    同じ名前で受けると統計が混ざる」ため、`groq`/`cerebras`/…と
    Identityを分けたからである。

    結果として**第二CloudをどれだけきちんとdefaultしてもLive Testは
    Geminiしか叩かず、新しいProviderは黙ってSKIPされていた**。
    「設定したのに何も起きない」という、原因の分からない無反応である
    (TD67の検証がずっと進まなかった一因)。

    固定の名前をやめ、**Registryが実際に持っているもの**から選ぶ。
    Providerが増えてもここを直す必要が無い——直し忘れが起きない形に
    する(`CLAUDE.md` §3)。
    """
    named = os.environ.get(_LIVE_PROVIDER_ENV, "").strip()
    if named:
        definition = definition_for(named)
        if definition is None:
            raise LiveProviderNotUsable(
                f"{_LIVE_PROVIDER_ENV}={named!r} だが、その名前のProviderが無い。"
                f"FORGE_EXTRA_PROVIDERS への追加を忘れていないか。"
            )
        if not definition.is_usable:
            missing = [
                name for name in definition.required_variables
                if not os.environ.get(name, "").strip()
            ]
            raise LiveProviderNotUsable(
                f"{_LIVE_PROVIDER_ENV}={named!r} だが叩けない。"
                f"未設定の環境変数: {missing or '(不明)'}"
            )
        return named

    # 名指しが無ければ、**設定が揃っている実装済みCloud**から選ぶ。
    for definition in configured_providers():
        if (
            definition.deployment is Deployment.CLOUD
            and definition.implementation_status is ImplementationStatus.IMPLEMENTED
            and not definition.test_only
        ):
            return definition.provider_id
    return None


class TestTheLiveProviderSelection(unittest.TestCase):
    """**実APIを1回も呼ばない。** どのProviderを叩くかを決める部分だけを見る。

    このクラスは`FORGE_LIVE_TEST`で囲っていない——常に走る。

    理由: 2026-08-17に見つけた実バグは「`_live_provider_id()`が
    廃止済みの`cloud`という名前を見ていたため、第二Cloudを設定しても
    黙ってSKIPされる」というものだった。**選択ロジックの誤りは、
    Live実行しないと分からない**形になっていたので、いつまでも
    見つからなかった。

    ここを常時実行にすることで、同じ誤りは鍵が無くても落ちる。
    """

    _KEYS = (
        "FORGE_EXTRA_PROVIDERS", "FORGE_LIVE_PROVIDER",
        "FORGE_FAKECLOUD_BASE_URL", "FORGE_FAKECLOUD_API_KEY", "FORGE_FAKECLOUD_MODEL",
    )

    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in self._KEYS}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _configure_fake_cloud(self) -> None:
        os.environ["FORGE_EXTRA_PROVIDERS"] = "fakecloud"
        os.environ["FORGE_FAKECLOUD_BASE_URL"] = "http://127.0.0.1:9/v1"
        os.environ["FORGE_FAKECLOUD_API_KEY"] = "dummy-value-not-a-real-key"
        os.environ["FORGE_FAKECLOUD_MODEL"] = "some-model"

    def test_a_provider_added_by_configuration_can_be_selected(self) -> None:
        """**これが直したバグの本体。**

        以前は固定の名前(`gemini` / 廃止済みの`cloud`)しか見ていな
        かったので、設定で足したProviderには決して届かなかった。
        """
        self._configure_fake_cloud()
        os.environ["FORGE_LIVE_PROVIDER"] = "fakecloud"
        self.assertEqual(_live_provider_id(), "fakecloud")

    def test_naming_an_unknown_provider_fails_loudly(self) -> None:
        """**黙ってSKIPしない。** 「設定したのに何も起きない」を防ぐ。"""
        os.environ["FORGE_LIVE_PROVIDER"] = "no_such_provider"
        with self.assertRaises(LiveProviderNotUsable):
            _live_provider_id()

    def test_naming_a_half_configured_provider_says_what_is_missing(self) -> None:
        self._configure_fake_cloud()
        del os.environ["FORGE_FAKECLOUD_MODEL"]
        os.environ["FORGE_LIVE_PROVIDER"] = "fakecloud"
        with self.assertRaises(LiveProviderNotUsable) as caught:
            _live_provider_id()
        self.assertIn("FORGE_FAKECLOUD_MODEL", str(caught.exception))

    def test_it_never_selects_the_test_double(self) -> None:
        """`mock`を実APIテストの相手にしない。通ってしまうと
        「実APIで確認済み」という嘘の実績が残る(§22)。"""
        os.environ.pop("FORGE_LIVE_PROVIDER", None)
        self.assertNotEqual(_live_provider_id(), "mock")

    def test_it_never_selects_a_stub(self) -> None:
        """`openai`/`claude`はスタブ(呼ぶとNotImplementedError)である。"""
        os.environ.pop("FORGE_LIVE_PROVIDER", None)
        selected = _live_provider_id()
        if selected is None:
            self.skipTest("この環境には設定済みCloud Providerが無い")
        definition = definition_for(selected)
        self.assertIs(definition.implementation_status, ImplementationStatus.IMPLEMENTED)
        self.assertIs(definition.deployment, Deployment.CLOUD)

    def test_the_retired_cloud_id_no_longer_exists(self) -> None:
        """011で`cloud`という汎用名は廃止した。**この名前へ戻さない。**

        戻すと「今日Groq・明日Cerebras」が同じ名前になり、Benchmarkと
        Quotaの記録が混ざる。
        """
        self.assertIsNone(definition_for("cloud"))


@unittest.skipUnless(_LIVE_ENABLED, "FORGE_LIVE_TEST=1 のときだけ実行する(実APIを消費するため)")
class TestAProviderActuallyAnswers(unittest.TestCase):
    """実API 1回。Doubleでは確かめられないことだけを見る。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.provider_id = _live_provider_id()
        if cls.provider_id is None:
            raise unittest.SkipTest(
                "実装済みかつ設定済みのCloud Providerがありません"
                "(GEMINI_API_KEY もしくは FORGE_CLOUD_* を設定してください)"
            )

    def test_the_provider_returns_a_response_that_satisfies_the_schema(self) -> None:
        """**実API呼び出し 1回目**。

        Mockは常にスキーマを満たすので、「実モデルが本当に満たすか」は
        Doubleでは測れない。ここだけが実地の情報である。
        """
        adapter = ProviderRouter().resolve(self.provider_id)
        result = adapter.complete_structured(_PROBE_PROMPT, _PROBE_SCHEMA)

        self.assertIsInstance(result, dict, f"dictが返らなかった: {str(result)[:200]}")
        for key in ("status", "count"):
            self.assertIn(key, result, f"必須キー'{key}'が無い: {str(result)[:200]}")
        # 値そのものは断定しない。モデルは指示に**だいたい**従うのであって、
        # 「必ずcount=3を返す」と決めつけると、正常なのに落ちるテストになる。
        self.assertIsInstance(result["count"], int)


@unittest.skipUnless(_LIVE_ENABLED, "FORGE_LIVE_TEST=1 のときだけ実行する(実APIを消費するため)")
class TestTheRouterReachesTheProviderForReal(unittest.TestCase):
    """実API 1回。**配線の実地確認**。

    Phase Bで直したのは「Routerを通っているか」であり、それは
    Doubleで固定した。ここで見るのは、そのRouterが**実Providerへ
    到達して応答を持ち帰るか**——Doubleを外しても同じ形で動くか、
    である。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.provider_id = _live_provider_id()
        if cls.provider_id is None:
            raise unittest.SkipTest("実装済みかつ設定済みのCloud Providerがありません")

    def test_a_routed_task_reaches_the_real_provider(self) -> None:
        """**実API呼び出し 2回目(最後)**。"""
        definition = definition_for(self.provider_id)
        router = AIRouter(
            resolve=ProviderRouter().resolve,
            catalog=(
                ModelDescriptor(
                    provider=self.provider_id,
                    is_local=False,
                    supports_structured_output=definition.supports_structured_output,
                ),
            ),
        )
        result = router.generate(ForgeTask.CONVERSATION_STEP, _PROBE_PROMPT, _PROBE_SCHEMA)

        self.assertEqual(result.provider_used, self.provider_id)
        self.assertIn("status", result.value)
        # Router側の記録が実際に更新されていること(Quota/Circuit Breakerの
        # 土台。ここが動いていなければ、枠切れの学習も起きない)。
        state = router.states.get(self.provider_id)
        self.assertEqual(state.total_successes, 1)
        self.assertIsNotNone(state.average_latency_ms)


@unittest.skipUnless(_LIVE_ENABLED, "FORGE_LIVE_TEST=1 のときだけ実行する")
class TestLiveTestingDoesNotLeakSecrets(unittest.TestCase):
    """§67: 鍵の値をレポートへ出さない。実API呼び出しは**0回**。"""

    def test_the_diagnostic_view_shows_names_and_booleans_only(self) -> None:
        provider_id = _live_provider_id()
        if provider_id is None:
            self.skipTest("設定済みProviderがありません")
        definition = definition_for(provider_id)
        described = repr(definition.describe())

        if definition.api_key_env:
            actual_key = os.environ.get(definition.api_key_env, "")
            self.assertTrue(actual_key, "設定済みのはずなのに鍵が読めない")
            self.assertNotIn(actual_key, described)
            # 断片も出さない。先頭数文字は「鍵の確認に便利」だが、
            # ログへ流れ出す経路を作ることになる。
            self.assertNotIn(actual_key[:8], described)
            self.assertIn(definition.api_key_env, described)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
