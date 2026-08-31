"""**獲得した Capability を Forge の Flutter アプリまで通す**（TD94）。

---

## 何を通すか

```text
未知の要求
  → Capability Plan が gap を名指しする           (view.calendar が missing)
  → 実装を生成する                                 (Dart)
  → 隔離 workspace で実 dart による試験・解析・起動確認
  → PROMOTED
  → Forge の Flutter アプリへ install               ← ここが TD94
  → 生成 Document を本番 compiler で作る
  → Flutter が Parser → Registry → 実 Widget まで解決する
```

最後の1行は Dart 側で確かめる（`frontend/test_acquired/`）。
この script はそこまでの下ごしらえを**本番の関数で**行い、
生成 Document を JSON として置く。

## 通らないものを通ったことにしない

各段で条件を確かめ、満たさなければ**即座に落とす**。
「install したつもり」「Document に出たつもり」を残さない。

## 秘密情報

Provider は Test Double である。実 API を呼ばない。
API キー・token の類は一切扱わない。
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge_ai.core.ir.capability_document_contribution import (  # noqa: E402
    CapabilityDocumentContribution,
    register_document_contribution,
)
from forge_ai.core.ir.capability_ir import entity_spec_from_plan  # noqa: E402
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler  # noqa: E402
from forge_ai.core.ir.ir_generator import IRGenerator  # noqa: E402
from forge_ai.core.orchestration.capability_artifact_synthesis import (  # noqa: E402
    CapabilityArtifactSynthesizer,
    CapabilityImplementationContract,
)
from forge_ai.core.orchestration.extension_manifest import (  # noqa: E402
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute  # noqa: E402
from forge_ai.core.orchestration.flutter_capability_installer import (  # noqa: E402
    INSTALL_ROOT,
    FlutterCapabilityInstaller,
)
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (  # noqa: E402
    SynthesizingBuildTimeImplementer,
    build_plan_for_language,
)
from forge_ai.core.semantics.capability_plan import plan_capabilities  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402

FRONTEND = ROOT / "frontend"
DOCUMENT_OUT = FRONTEND / "test_acquired" / "generated_document.json"

NEED = "通院の記録を残して、日付をカレンダーで確認したい"
CAPABILITY = "view.calendar"
WIDGET_TYPE = "calendar_view"

CONTRACT = CapabilityImplementationContract(
    capability_id=CAPABILITY,
    intent="記録を月ごとにまとめてカレンダーの形で見せる",
    data_contract=("date",),
    host_language="dart",
    binding_targets=("language", "validator", "runtime", "compiler"),
)

# ---------------------------------------------------------------------------
# 生成される Dart（この script では Test Double が返す）。
#
# **実 Model が書いたことは証明していない。** Real Local Model runs = 0 の
# ままである。ここで証明するのは「生成された Dart が Forge のアプリへ載り、
# 実際に描けるところまで通る」ことだけである。
# ---------------------------------------------------------------------------

_IMPL = '''/// 記録の日付を月ごとにまとめる、依存無しの実装。
///
/// 入力は `YYYY-MM-DD` 形式の文字列。読めないものは捨てずに
/// `unparsed` へ集める——黙って無かったことにしない。
class CalendarGrouping {
  final Map<String, List<String>> byMonth;
  final List<String> unparsed;
  const CalendarGrouping(this.byMonth, this.unparsed);
}

CalendarGrouping groupByMonth(List<String> dates) {
  final byMonth = <String, List<String>>{};
  final unparsed = <String>[];
  for (final raw in dates) {
    final value = raw.trim();
    if (value.length < 7 || value[4] != '-') {
      unparsed.add(raw);
      continue;
    }
    final month = value.substring(0, 7);
    byMonth.putIfAbsent(month, () => <String>[]).add(value);
  }
  for (final entry in byMonth.entries) {
    entry.value.sort();
  }
  return CalendarGrouping(byMonth, unparsed);
}

List<String> monthsInOrder(CalendarGrouping grouping) {
  final months = grouping.byMonth.keys.toList()..sort();
  return months;
}
'''

_TEST = '''import 'capability_impl.dart';

void main() {
  final grouping = groupByMonth(<String>[
    '2026-08-03', '2026-07-31', '2026-08-01', 'いつか',
  ]);
  if (monthsInOrder(grouping).join(',') != '2026-07,2026-08') {
    throw StateError('unexpected months: ${monthsInOrder(grouping)}');
  }
  if (grouping.byMonth['2026-08']!.first != '2026-08-01') {
    throw StateError('dates within a month must be sorted');
  }
  if (grouping.unparsed.length != 1) {
    throw StateError('unreadable dates must be kept, not dropped');
  }
  print('tests ok');
}
'''

_PROBE = '''import 'capability_impl.dart';

void main() {
  final grouping = groupByMonth(<String>['2026-01-05']);
  if (monthsInOrder(grouping).join() != '2026-01') {
    throw StateError('probe failed: $grouping');
  }
  print('runtime probe ok');
}
'''

_BINDING = '''import 'package:flutter/material.dart';

import 'package:forge_app/json_ui/acquired/acquired_capability.dart';
import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/acquired_widget_types.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

import 'capability_impl.dart';

/// 記録を月ごとにまとめて見せる。
Widget buildCalendarView(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode child) recurse,
) {
  final acquired = node as ForgeAcquiredWidgetNode;
  final stateRef = acquired.properties['state_ref'] as String? ?? 'records';
  final dateField = acquired.properties['date_field'] as String? ?? 'date';
  final title = acquired.properties['title'] as String? ?? 'カレンダー';
  final emptyText = acquired.properties['empty_text'] as String? ?? '記録がありません';

  final records = state.getRecordList(stateRef);
  final dates = <String>[];
  for (final record in records) {
    final value = record.fields[dateField];
    if (value is String && value.trim().isNotEmpty) {
      dates.add(value);
    }
  }

  final grouping = groupByMonth(dates);
  final months = monthsInOrder(grouping);

  return Card(
    key: const ValueKey('acquired_calendar_view'),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (months.isEmpty)
            Text(emptyText)
          else
            for (final month in months)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text('$month: ${grouping.byMonth[month]!.length}件'),
              ),
        ],
      ),
    ),
  );
}

const ForgeAcquiredCapability capability = ForgeAcquiredCapability(
  capabilityId: 'view.calendar',
  spec: ForgeAcquiredWidgetSpec(
    typeName: 'calendar_view',
    requiredProperties: <String>['state_ref', 'date_field'],
  ),
  build: buildCalendarView,
);
'''

_CONTRIBUTION = json.dumps(
    {
        "capability_id": CAPABILITY,
        "widget_type": WIDGET_TYPE,
        "widget_id": "record_calendar",
        "document_version": "1.16",
        "properties": [
            ["state_ref", "records"],
            ["date_field", "date"],
            ["title", "カレンダー"],
            ["empty_text", "日付を記録するとカレンダーに表示されます"],
        ],
        "fallback_container_id": "calendar_root",
    },
    ensure_ascii=False,
    indent=2,
) + "\n"


def _payload() -> dict:
    return {
        "files": [
            {"path": "capability_impl.dart", "content": _IMPL},
            {"path": "capability_test.dart", "content": _TEST},
            {"path": "probe.dart", "content": _PROBE},
            {"path": "flutter/forge_binding.dart", "content": _BINDING},
            {"path": "capability_contribution.json", "content": _CONTRIBUTION},
        ],
        "reusable_contract": "日付の記録を月ごとにまとめて見せる再利用可能な実装",
    }


class _TestDoubleProvider:
    """**実 Model ではない。** 実 Model が書いた証拠はまだ無い。"""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt):  # noqa: ANN001, ANN202
        self.calls += 1
        return ProviderResponse(text="", structured=_payload())


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def restore() -> None:
    """獲得物を取り除き、登録表を出荷状態へ戻す。"""
    root = FRONTEND / INSTALL_ROOT
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            shutil.rmtree(entry)
    installer = FlutterCapabilityInstaller(
        frontend_root=FRONTEND, harness_files=frozenset(),
    )
    installer.rewrite_registrations()
    if DOCUMENT_OUT.exists():
        DOCUMENT_OUT.unlink()
    print("restored: no acquired capability is installed")


def main() -> None:
    if "--restore" in sys.argv:
        restore()
        return

    print("=== BEFORE: Capability Plan ===")
    plan = plan_capabilities(NEED)
    print(f"  need    : {NEED}")
    print(f"  missing : {plan.missing}")
    if CAPABILITY not in plan.missing:
        _fail(f"{CAPABILITY} should be missing before acquisition; got {plan.missing}")

    print("=== 生成 → 実 dart による試験・解析・起動確認 → PROMOTED ===")
    provider = _TestDoubleProvider()
    implementer = SynthesizingBuildTimeImplementer(
        synthesizer=CapabilityArtifactSynthesizer(provider=provider),
        contract_for=lambda _capability_id: CONTRACT,
        known_source_digests=frozenset(),
    )
    manifest = ExtensionManifest(
        capability_id=CAPABILITY, label_ja="カレンダーで見る",
        route=ExtensionRoute.BUILD_TIME, requires_confirmation=False,
    )
    implementation = implementer(manifest)
    execution = implementer.last_execution
    if execution is None:
        _fail("no managed build execution was recorded")
    for kind in ("test", "build", "runtime_probe"):
        if not execution.evidence.passed(kind):
            _fail(f"{kind} did not pass in the isolated dart workspace")
        print(f"  {kind:<14} exit=0")
    if implementation.manifest.status is not ExtensionStatus.PROMOTED:
        _fail(f"manifest is {implementation.manifest.status}, not PROMOTED")
    if implementation.activation is None or not implementation.activation.loaded:
        _fail("no loaded activation")
    print(f"  PROMOTED  build_id={implementation.activation.build_id}")

    print("=== install: Forge の Flutter アプリへ載せる ===")
    plan_for_dart = build_plan_for_language(CONTRACT.host_language)
    installer = FlutterCapabilityInstaller(
        frontend_root=FRONTEND,
        harness_files=frozenset(
            (*plan_for_dart.harness_files, "capability_contribution.json"),
        ),
        host_prefix=plan_for_dart.host_prefix,
    )
    artifact = implementer.synthesizer.synthesize(
        CONTRACT,
        known_source_digests=frozenset(),
        required_files=plan_for_dart.entry_files,
    )
    if artifact is None:
        _fail("artifact could not be rebuilt for installation")
    installation = installer.install(artifact)
    registrations = installer.rewrite_registrations()
    for path in installation.installed_files:
        print(f"  installed  {path}")
    print(f"  registrations rewritten: {registrations.relative_to(ROOT)}")
    body = registrations.read_text(encoding="utf-8")
    if installation.slug not in body:
        _fail("the regenerated registration table does not mention the capability")

    print("=== 生成 Document（本番 compiler） ===")
    declaration = json.loads(
        next(f.content for f in artifact.files if f.path == "capability_contribution.json"),
    )
    register_document_contribution(CapabilityDocumentContribution(
        capability_id=declaration["capability_id"],
        widget_type=declaration["widget_type"],
        widget_id=declaration["widget_id"],
        document_version=declaration["document_version"],
        properties=tuple((key, value) for key, value in declaration["properties"]),
        fallback_container_id=declaration.get("fallback_container_id", "contribution_root"),
    ))
    spec = entity_spec_from_plan(plan)
    if spec is None:
        _fail("the plan produced no entity spec")
    document = ForgeLanguageCompiler().compile(
        IRGenerator().build_from_spec(spec),
        domain_category="generic",
        title="通院の記録",
        promoted_capabilities=(CAPABILITY,),
    )
    payload = document.to_json_dict()
    types = json.dumps(payload, ensure_ascii=False)
    if f'"{WIDGET_TYPE}"' not in types:
        _fail(f"the compiled document does not contain {WIDGET_TYPE!r}")
    DOCUMENT_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENT_OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"  {WIDGET_TYPE} is in the compiled document")
    print(f"  written: {DOCUMENT_OUT.relative_to(ROOT)}")

    print("=== まだ言えないこと ===")
    print("  実 Model が書いた証拠は無い（Provider は Test Double）")
    print("  Real Local Model runs = 0 のまま")
    print("  Flutter が実際に描くかどうかは frontend/test_acquired/ が確かめる")


if __name__ == "__main__":
    main()
