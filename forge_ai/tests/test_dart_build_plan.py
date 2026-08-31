"""**生成した Dart を、実 `dart` で試験・解析・起動確認する**（020F / TD94）。

---

## なぜ Dart なのか

Forge の生成物を実際に描くのは Flutter/Dart である。Python の実装を
いくら build できても、**描く側の言語を1行も検証していない**。

このテストは、生成 → 実 subprocess での試験 → 解析 → 起動確認 →
PROMOTED を、**Dart で**通す。fake builder も fake loader も使わない。

## 何を証明していて、何を証明していないか

証明する: 生成された Dart source が、本物の `dart` で

* テストが通る（`dart run capability_test.dart`）
* 静的解析が通る（`dart analyze .`）
* 実際に起動して出力を出す（`dart run probe.dart`）

証明**しない**: その widget が Forge の Flutter アプリで描かれること。
隔離 workspace は Flutter を持たない。描画側は
`frontend/test/json_ui/widget_registry/acquired_widget_renders_test.dart`
が別途押さえている。**2つは別の事実であり、片方でもう片方を語らない。**

## CI で skip させない

`dart` が無い環境では skip する。しかし **skip されたテストは何も
証明しない**ので、CI（Flutter を持つ job）では `FORGE_REQUIRE_DART_BUILD=1`
を立てて、skip ではなく **失敗**させる。
"""

from __future__ import annotations

import os
import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1].parent))

from forge_ai.core.orchestration.capability_artifact_synthesis import (  # noqa: E402
    CapabilityArtifactSynthesizer,
    CapabilityImplementationContract,
)
from forge_ai.core.orchestration.extension_manifest import (  # noqa: E402
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute  # noqa: E402
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (  # noqa: E402
    CapabilityImplementationUnavailable,
    SynthesizingBuildTimeImplementer,
    entry_files_for_language,
    supported_host_languages,
)
from forge_ai.prompt.prompt_builder import Prompt  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402

CAPABILITY = "view.acquired_grid"

_IMPL = """/// 記録を列数で折り返して並べ替える、依存無しの実装。
List<List<T>> chunkRows<T>(List<T> items, int columns) {
  if (columns < 1) {
    throw ArgumentError.value(columns, 'columns', 'must be >= 1');
  }
  final rows = <List<T>>[];
  for (var i = 0; i < items.length; i += columns) {
    final end = i + columns > items.length ? items.length : i + columns;
    rows.add(items.sublist(i, end));
  }
  return rows;
}
"""

_TEST = """import 'capability_impl.dart';

void main() {
  final rows = chunkRows(<int>[1, 2, 3, 4, 5], 2);
  if (rows.length != 3) {
    throw StateError('expected 3 rows, got ${rows.length}');
  }
  if (rows.last.length != 1) {
    throw StateError('last row should hold the remainder');
  }
  var threw = false;
  try {
    chunkRows(<int>[1], 0);
  } on ArgumentError {
    threw = true;
  }
  if (!threw) {
    throw StateError('columns < 1 must be rejected');
  }
  print('tests ok');
}
"""

_PROBE = """import 'capability_impl.dart';

void main() {
  final rows = chunkRows(<String>['a', 'b', 'c'], 2);
  if (rows.toString() != '[[a, b], [c]]') {
    throw StateError('unexpected rows: $rows');
  }
  print('runtime probe ok');
}
"""

CONTRACT = CapabilityImplementationContract(
    capability_id=CAPABILITY,
    intent="記録を格子状に並べて見せる",
    data_contract=("items", "columns"),
    host_language="dart",
    binding_targets=("language", "validator", "runtime", "compiler"),
)


_BINDING = """import 'package:flutter/material.dart';

import 'package:forge_app/json_ui/acquired/acquired_capability.dart';
import 'package:forge_app/json_ui/schema/acquired_widget_types.dart';

import 'capability_impl.dart';

const ForgeAcquiredCapability capability = ForgeAcquiredCapability(
  capabilityId: 'view.acquired_grid',
  spec: ForgeAcquiredWidgetSpec(
    typeName: 'acquired_grid_view',
    requiredProperties: <String>['columns'],
  ),
  build: buildAcquiredGrid,
);
"""


def _payload(
    impl: str = _IMPL,
    test: str = _TEST,
    probe: str = _PROBE,
    binding: str = _BINDING,
) -> dict:
    return {
        "files": [
            {"path": "capability_impl.dart", "content": impl},
            {"path": "capability_test.dart", "content": test},
            {"path": "probe.dart", "content": probe},
            {"path": "flutter/forge_binding.dart", "content": binding},
        ],
        "reusable_contract": "列数で折り返して並べる再利用可能な実装",
    }


class _Provider:
    def __init__(self, structured: dict) -> None:
        self.structured = structured
        self.calls = 0

    def complete(self, prompt: Prompt) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(text="", structured=self.structured)


def _implementer(structured: dict) -> SynthesizingBuildTimeImplementer:
    return SynthesizingBuildTimeImplementer(
        synthesizer=CapabilityArtifactSynthesizer(provider=_Provider(structured)),
        contract_for=lambda _capability_id: CONTRACT,
        known_source_digests=frozenset(),
    )


def _manifest() -> ExtensionManifest:
    return ExtensionManifest(
        capability_id=CAPABILITY,
        label_ja="獲得した並び",
        route=ExtensionRoute.BUILD_TIME,
        requires_confirmation=False,
    )


def _dart_available() -> bool:
    return shutil.which("dart") is not None


def _dart_required() -> bool:
    return os.environ.get("FORGE_REQUIRE_DART_BUILD", "").strip() not in ("", "0")


class TestTheDartPlanIsDeclared(unittest.TestCase):
    """`dart` が無い環境でも成り立つ、宣言側の不変条件。"""

    def test_dart_is_a_supported_host_language(self) -> None:
        self.assertIn("dart", supported_host_languages())

    def test_the_plan_names_the_files_it_will_execute(self) -> None:
        """手順が名指しするファイルは、先に要求しておく。"""
        self.assertEqual(
            entry_files_for_language("dart"),
            (
                "capability_impl.dart",
                "capability_test.dart",
                "probe.dart",
                "flutter/forge_binding.dart",
            ),
        )


class _DartCase(unittest.TestCase):
    def setUp(self) -> None:
        if not _dart_available():
            if _dart_required():
                self.fail(
                    "FORGE_REQUIRE_DART_BUILD is set but `dart` is not on PATH."
                    " skip では何も証明できないので失敗させる",
                )
            self.skipTest("dart SDK が無い（skip は証拠にならない）")


class TestGeneratedDartSurvivesARealBuild(_DartCase):
    """**実 subprocess。** fake builder も fake loader も使わない。"""

    def test_generation_test_analyze_probe_and_activation(self) -> None:
        implementer = _implementer(_payload())
        implementation = implementer(_manifest())

        self.assertIs(implementation.manifest.status, ExtensionStatus.PROMOTED)
        self.assertIsNotNone(implementation.activation)
        assert implementation.activation is not None
        self.assertEqual(implementation.activation.capability_id, CAPABILITY)
        self.assertTrue(implementation.activation.loaded)

        execution = implementer.last_execution
        assert execution is not None
        for kind in ("test", "build", "runtime_probe"):
            with self.subTest(kind=kind):
                self.assertTrue(execution.evidence.passed(kind), kind)
        self.assertTrue(execution.result.build_id)
        self.assertTrue(execution.result.runtime_fingerprint)

    def test_the_output_is_real_dart_process_output(self) -> None:
        """**本当にその Dart が動いたことを、出力で確かめる。**"""
        implementer = _implementer(_payload())
        implementer(_manifest())
        execution = implementer.last_execution
        assert execution is not None
        probe = next(c for c in execution.evidence.commands if c.kind == "runtime_probe")
        self.assertIn("runtime probe ok", probe.stdout)
        test = next(c for c in execution.evidence.commands if c.kind == "test")
        self.assertIn("tests ok", test.stdout)


class TestBadDartIsNotPromoted(_DartCase):
    """**通らないものを通さない。**"""

    def test_a_failing_dart_test_blocks_promotion(self) -> None:
        broken = _TEST.replace("rows.length != 3", "rows.length != 99")
        implementer = _implementer(_payload(test=broken))
        implementation = implementer(_manifest())
        self.assertIsNot(implementation.manifest.status, ExtensionStatus.PROMOTED)
        self.assertIsNone(implementation.activation)

    def test_dart_that_does_not_analyze_blocks_promotion(self) -> None:
        """`dart analyze` が本当に効いていること。"""
        implementer = _implementer(
            _payload(impl=_IMPL + "\nint broken() { return 'not an int'; }\n"),
        )
        implementation = implementer(_manifest())
        self.assertIsNot(implementation.manifest.status, ExtensionStatus.PROMOTED)
        self.assertIsNone(implementation.activation)

    def test_a_failing_probe_blocks_promotion(self) -> None:
        implementer = _implementer(
            _payload(probe=_PROBE.replace("'[[a, b], [c]]'", "'never'")),
        )
        implementation = implementer(_manifest())
        self.assertIsNot(implementation.manifest.status, ExtensionStatus.PROMOTED)
        self.assertIsNone(implementation.activation)


class TestMissingEntryFilesFailAsGeneration(_DartCase):
    """手順が名指しするファイルが無いのは、**生成の失敗**である。

    build の失敗（ファイルが無くてコマンドが落ちた）に化けさせない。
    """

    def test_a_missing_probe_is_reported_as_generation_failure(self) -> None:
        payload = _payload()
        payload["files"] = [f for f in payload["files"] if f["path"] != "probe.dart"]
        implementer = _implementer(payload)
        with self.assertRaises(CapabilityImplementationUnavailable):
            implementer(_manifest())

    def test_a_wrongly_named_test_file_is_reported_as_generation_failure(self) -> None:
        payload = _payload()
        payload["files"][1]["path"] = "some_other_test.dart"
        implementer = _implementer(payload)
        with self.assertRaises(CapabilityImplementationUnavailable):
            implementer(_manifest())


if __name__ == "__main__":
    unittest.main()
