"""FORGE-019C §9 — **enumに在ることと、使えることは違う**。

---

## 何を固定するか

1. すべての `SemanticOperationKind` が分類されている（忘れたら落ちる）
2. `PRODUCTION_SUPPORTED` は**自然言語から実際に到達できるものだけ**
3. 本番の経路が、分類されていない操作を記録しない

3 が要点である。表を書くだけなら誰でも書けるが、
**表と実装がずれたときに落ちる**ようにしないと、また嘘になる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.runtime.operation_support import (  # noqa: E402
    OperationSupportLevel,
    UnsupportedOperation,
    operation_support_table,
    production_supported_operations,
    require_production_supported,
    support_level,
)
from app.ai.runtime.semantic_revision import (  # noqa: E402
    SemanticOperation,
    SemanticOperationKind,
)


class TestEveryOperationIsClassified(unittest.TestCase):
    def test_no_operation_is_left_unclassified(self) -> None:
        """**足したのに分類し忘れた**を通さない。"""
        table = operation_support_table()
        missing = [k.value for k in SemanticOperationKind if k not in table]
        self.assertEqual(missing, [], f"分類されていない意味的操作がある: {missing}")

    def test_an_unclassified_operation_raises(self) -> None:
        """未分類は `RESERVED` へ倒さない。**例外にする。**"""

        class _Fake(str):
            value = "not_declared_anywhere"

        with self.assertRaises(UnsupportedOperation):
            support_level(_Fake("not_declared_anywhere"))  # type: ignore[arg-type]


class TestDeclaredIsNotSupported(unittest.TestCase):
    """**宣言 ≠ 本番で使える。** ここが今回の主張である。"""

    def test_most_declared_operations_are_not_production_supported(self) -> None:
        declared = set(SemanticOperationKind)
        supported = production_supported_operations()
        self.assertLess(
            len(supported), len(declared),
            "宣言と本番対応が一致しているなら、この表は要らない。"
            "一致していないからこそ分けている",
        )

    def test_only_select_primary_metric_is_production_supported(self) -> None:
        self.assertEqual(
            production_supported_operations(),
            frozenset({SemanticOperationKind.SELECT_PRIMARY_METRIC}),
        )

    def test_set_design_role_is_engine_only(self) -> None:
        """型も適用実装もあるが、**自然言語からは到達しない**。"""
        self.assertIs(
            support_level(SemanticOperationKind.SET_DESIGN_ROLE),
            OperationSupportLevel.ENGINE_ONLY,
        )

    def test_operations_without_a_type_are_reserved(self) -> None:
        """`SemanticOperation` の union に型が無いものは `RESERVED`。

        **実装の有無を目視で決めない。** union に現れる `kind` の
        既定値を集めて、表と突き合わせる。
        """
        typed: set[SemanticOperationKind] = set()
        for member in SemanticOperation.__args__:  # type: ignore[attr-defined]
            default = member.__dataclass_fields__["kind"].default
            typed.add(default)
        for kind in SemanticOperationKind:
            if kind in typed:
                continue
            self.assertIs(
                support_level(kind), OperationSupportLevel.RESERVED,
                f"{kind.value} には型が無いのに reserved 以外になっている",
            )


class TestProductionRefusesUnsupported(unittest.TestCase):
    """**表が実装から離れたら落ちる。** 置物にしないための守り。"""

    def test_require_accepts_the_supported_one(self) -> None:
        require_production_supported(SemanticOperationKind.SELECT_PRIMARY_METRIC)

    def test_require_refuses_engine_only(self) -> None:
        with self.assertRaises(UnsupportedOperation):
            require_production_supported(SemanticOperationKind.SET_DESIGN_ROLE)

    def test_require_refuses_reserved(self) -> None:
        with self.assertRaises(UnsupportedOperation):
            require_production_supported(SemanticOperationKind.SET_THEME_TONE)


try:
    from fastapi.testclient import TestClient

    from app.main import app

    from tests.revision_fixtures import provision_artifact

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestReachableFromNaturalLanguage(unittest.TestCase):
    """**本番の経路が実際に何へ届くか**を測る。

    表を人が書き写すのではなく、`/update` を通して届いた `kind` を
    集める。実装が広がって表を直し忘れたら、ここが落ちる。
    """

    def setUp(self) -> None:
        from app.ai.gateway.artifact_feedback import (
            default_artifact_registry,
            default_feedback_log,
        )
        from app.ai.gateway.generation_evidence import default_generation_store
        from app.ai.gateway.learning_events import default_learning_event_service
        from app.ai.gateway.learning_outbox import default_projection_outbox
        from app.ai.gateway.revision_evidence import default_revision_store
        from app.ai.runtime.revision_service import default_replay_log

        for store in (
            default_generation_store(), default_revision_store(),
            default_artifact_registry(), default_feedback_log(),
            default_learning_event_service(), default_replay_log(),
            default_projection_outbox(),
        ):
            store.reset()
        self.client = TestClient(app)

    def test_reached_operations_match_the_declared_production_set(self) -> None:
        intents = [
            "収入をもっと目立たせて",
            "支出をもっと目立たせて",
            "残高を強調して",
            "収入を主指標にして",
            "配色を落ち着いた感じにして",
            "この項目を隠して",
            "並びをグループでまとめて",
        ]
        reached: set[str] = set()
        for intent in intents:
            artifact = provision_artifact(self.client)
            response = self.client.post(
                "/api/v1/ai/update", json=artifact.update_payload(intent),
            )
            if response.status_code != 200:
                continue
            operation = response.json()["result"].get("semantic_operation")
            if operation:
                reached.add(operation)

        declared = {k.value for k in production_supported_operations()}
        self.assertTrue(reached, "本番経路がどの意味的操作にも届かなかった")
        self.assertTrue(
            reached <= declared,
            f"表に無い操作へ本番が届いている: {sorted(reached - declared)}",
        )


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestProductionRefusesAnUnsupportedOperation(TestReachableFromNaturalLanguage):
    """**表と実装がずれたら、記録の前に止まる。**

    ---

    ## これが無いと表は置物になる

    最初は「本番が届いた操作 ⊆ 表」だけを見ていた。しかし本番が届く
    操作は現在1つしか無いので、**`require_production_supported()` を
    丸ごと外しても何も落ちなかった**（mutation M10 で判明）。

    つまり「表に無い操作が来たら止める」という主張を、1本も検査して
    いなかった。

    そこで、`ENGINE_ONLY` の操作（`SetDesignRole` — 型も適用実装も
    あるが自然言語からは到達しない）を無理やり組み立てて流し込む。
    本番はこれを**記録する前に**断らなければならない。
    """

    def _force_engine_only_operation(self):  # noqa: ANN202
        """`apply_semantic_intent` が `SetDesignRole` を返すようにする。

        将来 `SetDesignRole` を本番で使えるようにするなら、この
        テストは「別の `ENGINE_ONLY` / `RESERVED` な操作」へ張り替える
        ——**表を直さずに実装だけ広げる**ことを許さないための検査である。
        """
        from unittest.mock import patch

        from app.ai.runtime import revision_service as module
        from app.ai.runtime.semantic_revision import (
            AppliedSemanticRevision,
            SetDesignRole,
            apply_semantic_intent,
        )

        def _engine_only(document, intent):  # noqa: ANN001, ANN202
            applied = apply_semantic_intent(document, intent)
            if not isinstance(applied, AppliedSemanticRevision):
                return applied
            return AppliedSemanticRevision(
                document=applied.document,
                operation=SetDesignRole(
                    target=applied.operation.target, role_id="metric.primary",
                ),
                changed_widget_ids=applied.changed_widget_ids,
                validation=applied.validation,
                critic=applied.critic,
            )

        return patch.object(module, "apply_semantic_intent", _engine_only)

    def test_an_engine_only_operation_is_refused(self) -> None:
        artifact = provision_artifact(self.client)
        with self._force_engine_only_operation():
            response = self.client.post(
                "/api/v1/ai/update",
                json=artifact.update_payload("収入をもっと目立たせて"),
            )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(
            response.json()["error"]["reached_stage"], "unsupported_operation",
        )

    def test_an_unsupported_operation_records_nothing(self) -> None:
        """**断るのは記録の前。** lineage を汚さない。"""
        from app.ai.gateway.artifact_feedback import default_feedback_log
        from app.ai.gateway.revision_evidence import default_revision_store

        artifact = provision_artifact(self.client)
        with self._force_engine_only_operation():
            self.client.post(
                "/api/v1/ai/update",
                json=artifact.update_payload("収入をもっと目立たせて"),
            )
        self.assertEqual(default_revision_store().size(), 0)
        self.assertEqual(default_feedback_log().size(), 0)

    def test_an_unsupported_operation_does_not_advance_the_version(self) -> None:
        from app.ai.gateway.artifact_feedback import default_artifact_registry

        artifact = provision_artifact(self.client)
        before = default_artifact_registry().resolve(artifact.artifact_id).version_token
        with self._force_engine_only_operation():
            self.client.post(
                "/api/v1/ai/update",
                json=artifact.update_payload("収入をもっと目立たせて"),
            )
        self.assertEqual(
            default_artifact_registry().resolve(artifact.artifact_id).version_token,
            before,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
