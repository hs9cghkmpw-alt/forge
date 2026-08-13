"""Provider Registry(FORGE-AI-FOUNDATION-010 Phase C・D、2026-08-13)。

`provider_registry.py`が**唯一の宣言**であることを固定する。

TD37の教訓——Widget Registry・Validator・Runtimeの三者がずれていて、
どれも自分の分だけ見ていたのでテストは全部通り、実機で初めて分かった
——を、Provider側で繰り返さないための検査である。
"""

from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.provider_registry import (  # noqa: E402
    PROVIDER_REGISTRY,
    Deployment,
    ImplementationStatus,
    Protocol,
    configured_providers,
    definition_for,
)
from app.ai.runtime.provider_router import ProviderRouter  # noqa: E402


class TestRegistryAndImplementationAgree(unittest.TestCase):
    """宣言と実装がずれていないこと。"""

    def test_every_declared_provider_resolves_to_an_adapter(self) -> None:
        """Registryにある名前は、必ず`ProviderRouter`で解決できる。

        ずれると「宣言はあるが呼べない」Providerが候補に並び、
        Routingが1回分の試行を無駄にする。
        """
        router = ProviderRouter()
        for definition in PROVIDER_REGISTRY:
            with self.subTest(provider=definition.provider_id):
                self.assertTrue(router.is_registered(definition.provider_id))

    def test_every_alias_resolves_to_the_same_adapter(self) -> None:
        router = ProviderRouter()
        for definition in PROVIDER_REGISTRY:
            for alias in definition.aliases:
                with self.subTest(alias=alias):
                    self.assertIs(
                        router.resolve(alias), router.resolve(definition.provider_id)
                    )

    def test_every_resolvable_name_is_declared(self) -> None:
        """逆向き。実装だけあって宣言の無いProviderを残さない。

        宣言が無いと、Cloudかどうかも鍵が要るかも分からないまま
        `provider`指定で呼べてしまう。
        """
        router = ProviderRouter()
        for name in router.available_providers():
            with self.subTest(provider=name):
                self.assertIsNotNone(
                    definition_for(name), f"'{name}' がRegistryに宣言されていない"
                )

    def test_provider_ids_are_unique(self) -> None:
        ids = [d.provider_id for d in PROVIDER_REGISTRY]
        self.assertEqual(len(ids), len(set(ids)))

    def test_aliases_never_collide_with_a_provider_id(self) -> None:
        ids = {d.provider_id for d in PROVIDER_REGISTRY}
        for definition in PROVIDER_REGISTRY:
            for alias in definition.aliases:
                with self.subTest(alias=alias):
                    self.assertNotIn(alias, ids, f"別名'{alias}'がprovider_idと衝突している")


class TestOnlyUsableProvidersAreDiscovered(unittest.TestCase):
    """Phase F Auto Discovery: 3条件を満たすものだけが候補になる。"""

    def setUp(self) -> None:
        self._saved = {
            key: os.environ.get(key)
            for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        }
        for key in self._saved:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_a_stub_is_never_discovered_even_with_a_key(self) -> None:
        """**鍵があっても未実装なら候補にしない。**

        `openai`は`OPENAI_API_KEY`を宣言しているが実装はスタブである。
        鍵の有無だけで候補にすると、必ず`NotImplementedError`で
        失敗する相手に試行予算を1回渡すことになる。
        """
        os.environ["OPENAI_API_KEY"] = "dummy-value-not-a-real-key"
        self.assertNotIn("openai", [d.provider_id for d in configured_providers()])

    def test_an_implemented_cloud_provider_needs_its_key(self) -> None:
        self.assertNotIn("gemini", [d.provider_id for d in configured_providers()])
        os.environ["GEMINI_API_KEY"] = "dummy-value-not-a-real-key"
        self.assertIn("gemini", [d.provider_id for d in configured_providers()])

    def test_local_needs_no_key(self) -> None:
        """Runtimeが起動しているかは環境変数では分からない。
        呼んでみて`LOCAL_RESOURCE_ERROR`で学習する。"""
        self.assertIn("local", [d.provider_id for d in configured_providers()])

    def test_mock_is_never_discovered(self) -> None:
        """§22: 全Cloud失敗 → Mock → 偽のTool、を構造で塞ぐ。"""
        self.assertNotIn("mock", [d.provider_id for d in configured_providers()])


class TestSecretsStayOutOfTheRegistry(unittest.TestCase):
    """§14〜§18: Git追跡対象には**環境変数名だけ**を置く。"""

    def test_the_registry_holds_variable_names_not_values(self) -> None:
        """`api_key_env`は名前であって値ではない。

        名前として妥当な形(英大文字・数字・アンダースコア)だけを
        許す。実値が紛れ込めば、この形から外れる。
        """
        for definition in PROVIDER_REGISTRY:
            if definition.api_key_env is None:
                continue
            with self.subTest(provider=definition.provider_id):
                self.assertRegex(definition.api_key_env, r"^[A-Z][A-Z0-9_]*$")
                self.assertTrue(definition.api_key_env.endswith(("_KEY", "_TOKEN")))

    def test_the_registry_source_contains_no_key_shaped_literal(self) -> None:
        """ソースに鍵らしき文字列が無いこと。

        完全な検出はできない(任意の文字列は鍵になりうる)。ここで
        見るのは**実際に起きやすい形**——長い英数字の連続と、
        既知のProviderの鍵接頭辞——に限る。検出漏れがありうることを
        承知の上での、安価な最後の防波堤である。
        """
        import app.ai.gateway.provider_registry as module

        with open(module.__file__, encoding="utf-8") as handle:
            source = handle.read()
        for prefix in ("AIzaSy", "sk-", "sk-ant-", "gsk_", "hf_"):
            self.assertNotIn(prefix, source, f"鍵らしき接頭辞'{prefix}'がソースにある")
        # 24文字以上で、英字と数字が**両方**混ざった連続。鍵はこの形を
        # 取る。区切り線(`---...`)や識別子(`FORGE_...`)は英数字混在の
        # 条件で落ちる。
        suspicious = [
            token for token in re.findall(r"[A-Za-z0-9\-]{24,}", source)
            if any(c.isdigit() for c in token) and any(c.isalpha() for c in token)
        ]
        self.assertEqual(suspicious, [], f"鍵らしき長い文字列がある: {suspicious}")

    def test_describe_never_leaks_a_value(self) -> None:
        """診断出力(§67)に実値が出ない。**長さも先頭数文字も出さない。**"""
        os.environ["GEMINI_API_KEY"] = "dummy-value-not-a-real-key"
        try:
            described = definition_for("gemini").describe()
        finally:
            os.environ.pop("GEMINI_API_KEY", None)
        flattened = repr(described)
        self.assertNotIn("dummy-value-not-a-real-key", flattened)
        self.assertIn("GEMINI_API_KEY", flattened)
        self.assertIs(described["configured"], True)

    def test_env_example_declares_names_without_values(self) -> None:
        """`backend/.env.example`はGit追跡対象である。値を書かない。"""
        path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        assignments = [
            line for line in lines
            if "=" in line and not line.strip().startswith("#")
        ]
        self.assertTrue(assignments, ".env.exampleに変数が1つも無い")
        for line in assignments:
            name, _, value = line.partition("=")
            with self.subTest(line=line):
                if name.strip() in ("FORGE_ENV", "FORGE_LOCAL_MODEL", "FORGE_LOCAL_BASE_URL"):
                    continue  # 秘密ではない設定値。例を書いてよい。
                self.assertEqual(
                    value.strip(), "", f"{name.strip()} に値が書かれている"
                )

    def test_every_secret_variable_in_the_registry_is_documented(self) -> None:
        """Registryが読む環境変数名は、`.env.example`に載っていること。

        載っていないと、運用者はどれを設定すればProviderが増えるのか
        分からない(Phase Fの Auto Discovery は環境変数が入口である)。
        """
        path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        with open(path, encoding="utf-8") as handle:
            example = handle.read()
        for definition in PROVIDER_REGISTRY:
            for variable in (definition.api_key_env, definition.base_url_env, definition.model_env):
                if variable is None:
                    continue
                with self.subTest(variable=variable):
                    self.assertIn(variable, example, f"{variable} が.env.exampleに無い")


class TestDeclarationsAreHonest(unittest.TestCase):
    """宣言が事実と食い違っていないこと。"""

    def test_in_process_providers_are_local_and_keyless(self) -> None:
        for definition in PROVIDER_REGISTRY:
            if definition.protocol is not Protocol.IN_PROCESS:
                continue
            with self.subTest(provider=definition.provider_id):
                self.assertIs(definition.deployment, Deployment.LOCAL)
                self.assertIsNone(definition.api_key_env)

    def test_cloud_providers_declare_a_key_variable(self) -> None:
        """外部サービスなのに鍵を宣言していない、という状態を作らない。"""
        for definition in PROVIDER_REGISTRY:
            if definition.deployment is not Deployment.CLOUD:
                continue
            with self.subTest(provider=definition.provider_id):
                self.assertIsNotNone(
                    definition.api_key_env,
                    f"{definition.provider_id} はCloudなのに鍵の宣言が無い",
                )

    def test_a_planned_provider_is_never_usable(self) -> None:
        for definition in PROVIDER_REGISTRY:
            if definition.implementation_status is ImplementationStatus.IMPLEMENTED:
                continue
            with self.subTest(provider=definition.provider_id):
                self.assertFalse(definition.is_usable)


if __name__ == "__main__":
    unittest.main()
