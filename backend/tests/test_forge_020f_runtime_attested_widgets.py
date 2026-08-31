"""**獲得した widget が Validator を通ること**、そして**通りすぎないこと**（020F）。

---

## なぜ要るのか

Validator（生成物を検査する仕組み）の許可 widget は版ごとの固定表
だった。人が書き足す表なので、Self-Extension で獲得した能力の widget は
永久に「未知の widget」として弾かれる——獲得しても検査を通れない。

## しかし緩めてはいけない

「宣言したから通す」にすると、**Dart（実際に描く側）が知らない widget**
を通してしまう。Validator は通るのに実行時に描けない——fail-open である。

通す条件は**2つとも**要る。

1. PROMOTED である（Evidence Gate を通った）
2. **loaded な BUILD_TIME activation を持つ**（新しい runtime を実際に
   ビルドして載せた）

`requested` では広がらない。`DECLARATIVE` でも広がらない。
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
for path in (str(_ROOT), str(_ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.ai.validators.runtime_attested_widgets import (  # noqa: E402
    runtime_attested_widget_types,
)
from app.ai.validators.schema_validator import (  # noqa: E402
    WIDGET_TYPES_BY_VERSION,
    validate_forge_document,
)
from forge_ai.core.ir.capability_document_contribution import (  # noqa: E402
    CapabilityDocumentContribution,
    register_document_contribution,
)
from forge_ai.core.orchestration.extension_manifest import (  # noqa: E402
    ExtensionEvidence,
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute  # noqa: E402
from forge_ai.core.orchestration.extension_registry import (  # noqa: E402
    PROMOTED_CAPABILITIES,
)

ACQUIRED = "view.acquired_grid"
WIDGET = "acquired_grid_view"


def _document(widget_type: str) -> dict:
    return {
        "version": "1.16",
        "initial_screen_id": "s1",
        "screens": [{
            "id": "s1", "title": "t", "state": {},
            "body": {"type": "column", "id": "root", "children": [
                {"type": widget_type, "id": "w1", "properties": {}},
            ]},
        }],
    }


class _LoadedActivation:
    """BUILD_TIME の loaded activation を模した最小の形。"""

    def __init__(self, *, loaded: bool = True) -> None:
        self.capability_id = ACQUIRED
        self.build_id = "build-abc"
        self.runtime_fingerprint = "fp-abc"
        self.source_digest = "digest-abc"
        self.loaded = loaded


def _promoted_manifest(route: ExtensionRoute) -> ExtensionManifest:
    return ExtensionManifest(
        capability_id=ACQUIRED, label_ja="獲得した並び", route=route,
        requires_confirmation=False, status=ExtensionStatus.PROMOTED,
        evidence=ExtensionEvidence(
            semantic_decomposition=True, reusable_primitive=True,
            language_binding=True, validator_binding=True,
            runtime_binding=True, compiler_binding=True,
            tests_pass=True, build_pass=True, runtime_evidence=True,
            safety_review=True,
        ),
    )


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        PROMOTED_CAPABILITIES.clear()
        self.addCleanup(PROMOTED_CAPABILITIES.clear)
        from forge_ai.core.ir import capability_document_contribution as module

        saved = dict(module._CONTRIBUTIONS)
        self.addCleanup(
            lambda: (module._CONTRIBUTIONS.clear(),
                     module._CONTRIBUTIONS.update(saved)),
        )
        register_document_contribution(CapabilityDocumentContribution(
            capability_id=ACQUIRED, widget_type=WIDGET,
            widget_id="acquired_grid", document_version="1.16",
        ))


class TestUnacquiredWidgetsAreRejected(_Base):
    """**既定は閉じている。**"""

    def test_nothing_is_attested_before_acquisition(self) -> None:
        self.assertEqual(runtime_attested_widget_types(), frozenset())

    def test_an_unknown_widget_fails_validation(self) -> None:
        result = validate_forge_document(_document(WIDGET))
        self.assertFalse(result.valid, "獲得していない widget が通っている")

    def test_declaring_a_contribution_alone_does_not_open_the_validator(self) -> None:
        """**宣言だけでは通らない。** PROMOTED でなければ広がらない。"""
        self.assertNotIn(WIDGET, runtime_attested_widget_types())


class TestARuntimeAttestedWidgetPasses(_Base):
    def setUp(self) -> None:
        super().setUp()
        PROMOTED_CAPABILITIES.install(
            _promoted_manifest(ExtensionRoute.BUILD_TIME), _LoadedActivation(),
        )

    def test_the_widget_is_attested(self) -> None:
        self.assertIn(WIDGET, runtime_attested_widget_types())

    def test_the_document_now_validates(self) -> None:
        result = validate_forge_document(_document(WIDGET))
        self.assertTrue(
            result.valid,
            f"獲得した widget が Validator を通らない: {result.errors}",
        )

    def test_other_unknown_widgets_are_still_rejected(self) -> None:
        """**1つ通したせいで全部通る、にしない。**"""
        result = validate_forge_document(_document("something_never_acquired"))
        self.assertFalse(result.valid)

    def test_the_shipped_version_table_is_not_mutated(self) -> None:
        """版ごとの表を書き換えない（他の検査へ漏れない）。"""
        self.assertNotIn(WIDGET, WIDGET_TYPES_BY_VERSION["1.16"])


class TestOnlyABuiltRuntimeOpensTheValidator(_Base):
    """**「PROMOTED である」だけでは足りない。**"""

    def test_a_declarative_promotion_does_not_open_it(self) -> None:
        """DECLARATIVE は既存 widget の組み替えであり、新しい型を持たない。"""
        PROMOTED_CAPABILITIES.install(
            _promoted_manifest(ExtensionRoute.DECLARATIVE), _LoadedActivation(),
        )
        self.assertNotIn(WIDGET, runtime_attested_widget_types())
        self.assertFalse(validate_forge_document(_document(WIDGET)).valid)

    def test_a_promotion_without_a_declared_widget_opens_nothing(self) -> None:
        from forge_ai.core.ir import capability_document_contribution as module

        module._CONTRIBUTIONS.pop(ACQUIRED, None)
        PROMOTED_CAPABILITIES.install(
            _promoted_manifest(ExtensionRoute.BUILD_TIME), _LoadedActivation(),
        )
        self.assertEqual(runtime_attested_widget_types(), frozenset())

    def test_an_unloaded_activation_cannot_even_be_installed(self) -> None:
        """載っていない build は Registry が受け取らない（既存の門）。"""
        with self.assertRaises(ValueError):
            PROMOTED_CAPABILITIES.install(
                _promoted_manifest(ExtensionRoute.BUILD_TIME),
                _LoadedActivation(loaded=False),
            )


class TestTheAttestationIsRecheckedNotCachedFromInstall(_Base):
    """**Registry が入口で見たことを、そのまま信用しない。**

    入口の検査（install）を通った後に activation が壊れる／降ろされる場合が
    ある。Validator の語彙は**その時点の事実**で決めるので、ここで
    もう一度見る。この class が無いと、下の再確認は「外しても誰も気づかない
    置物」になる。
    """

    def setUp(self) -> None:
        super().setUp()
        self.activation = _LoadedActivation()
        PROMOTED_CAPABILITIES.install(
            _promoted_manifest(ExtensionRoute.BUILD_TIME), self.activation,
        )
        self.assertIn(WIDGET, runtime_attested_widget_types())

    def test_a_runtime_that_was_unloaded_stops_being_attested(self) -> None:
        self.activation.loaded = False
        self.assertNotIn(WIDGET, runtime_attested_widget_types())
        self.assertFalse(validate_forge_document(_document(WIDGET)).valid)

    def test_a_lost_build_id_stops_being_attested(self) -> None:
        self.activation.build_id = ""
        self.assertNotIn(WIDGET, runtime_attested_widget_types())

    def test_a_lost_runtime_fingerprint_stops_being_attested(self) -> None:
        self.activation.runtime_fingerprint = ""
        self.assertNotIn(WIDGET, runtime_attested_widget_types())

    def test_an_activation_for_another_capability_stops_being_attested(self) -> None:
        """能力の身元が入れ替わったものは通さない。"""
        self.activation.capability_id = "view.something_else"
        self.assertNotIn(WIDGET, runtime_attested_widget_types())


if __name__ == "__main__":
    unittest.main()
