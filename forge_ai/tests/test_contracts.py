"""contracts/interfaces.py のテスト。各具体実装がProtocolを構造的に満たすことを
確認する(Interface First原則の回帰テスト)。"""

from __future__ import annotations

import unittest

from forge_ai.contracts.interfaces import (
    CompilerProtocol,
    DomainResolverProtocol,
    IntentBuilderProtocol,
    MeaningExtractorProtocol,
    PlannerProtocol,
    QualityEngineProtocol,
    RepairEngineProtocol,
    WorldModelBuilderProtocol,
)
from forge_ai.core.compiler import Compiler
from forge_ai.core.domain_model import DomainRegistry
from forge_ai.core.intent_model import IntentBuilder
from forge_ai.core.meaning_model import MeaningExtractor
from forge_ai.core.planner import Planner
from forge_ai.core.world_model import WorldModelBuilder
from forge_ai.provider.mock_provider import MockProvider
from forge_ai.quality.quality_engine import QualityEngine
from forge_ai.repair.repair_engine import RepairEngine


class TestContractConformance(unittest.TestCase):
    """`Protocol`はメソッドシグネチャの構造的一致を要求する。各具体クラスが
    対応するProtocolのメソッド名を実際に持つことを確認する
    (`typing.Protocol`は`@runtime_checkable`が無いとisinstanceできないため、
    ここでは`hasattr`によるメソッド存在確認で「契約を満たす形をしているか」を
    検証する)。"""

    def test_meaning_extractor_satisfies_protocol_shape(self) -> None:
        instance = MeaningExtractor(MockProvider())
        self.assertTrue(hasattr(instance, "extract"))
        self.assertTrue(callable(instance.extract))

    def test_intent_builder_satisfies_protocol_shape(self) -> None:
        instance = IntentBuilder(MockProvider())
        self.assertTrue(hasattr(instance, "build"))

    def test_planner_satisfies_protocol_shape(self) -> None:
        instance = Planner(MockProvider())
        self.assertTrue(hasattr(instance, "plan"))

    def test_compiler_satisfies_protocol_shape(self) -> None:
        instance = Compiler(MockProvider())
        self.assertTrue(hasattr(instance, "compile"))

    def test_repair_engine_satisfies_protocol_shape(self) -> None:
        instance = RepairEngine(MockProvider())
        self.assertTrue(hasattr(instance, "repair"))

    def test_quality_engine_satisfies_protocol_shape(self) -> None:
        instance = QualityEngine()
        self.assertTrue(hasattr(instance, "evaluate"))

    def test_domain_registry_satisfies_resolver_protocol_shape(self) -> None:
        instance = DomainRegistry()
        self.assertTrue(hasattr(instance, "resolve_from_keywords"))

    def test_world_model_builder_satisfies_protocol_shape(self) -> None:
        instance = WorldModelBuilder()
        self.assertTrue(hasattr(instance, "build"))

    def test_all_protocol_classes_importable(self) -> None:
        """契約(Protocol)そのものが正しくimportでき、具体実装クラスを
        importしていないこと(依存方向: 具体実装→Protocol)を確認する。"""
        import inspect

        import forge_ai.contracts.interfaces as contracts_module

        source = inspect.getsource(contracts_module)
        # 具体クラス名がimport文に出現しないことを確認する
        # (型のためだけの参照はデータクラス経由で許容されるが、
        # クラス実装そのものはimportしていないはず)。
        forbidden_concrete_imports = [
            "from forge_ai.core.meaning_model import MeaningExtractor\n",
            "from forge_ai.core.intent_model import IntentBuilder\n",
            "from forge_ai.core.planner import Planner\n",
            "from forge_ai.core.compiler import Compiler\n",
            "from forge_ai.repair.repair_engine import RepairEngine\n",
            "from forge_ai.quality.quality_engine import QualityEngine\n",
        ]
        for forbidden in forbidden_concrete_imports:
            self.assertNotIn(forbidden, source)
        protocols = [
            MeaningExtractorProtocol, IntentBuilderProtocol, PlannerProtocol,
            CompilerProtocol, RepairEngineProtocol, QualityEngineProtocol,
            DomainResolverProtocol, WorldModelBuilderProtocol,
        ]
        self.assertEqual(len(protocols), 8)


if __name__ == "__main__":
    unittest.main()
