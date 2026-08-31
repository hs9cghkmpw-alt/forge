"""獲得する Capability の**生成物そのもの**（試験用の Test Double が返す中身）。

2つの script が同じものを使う。片方だけ直して食い違うと、
「検査したもの」と「載せたもの」の議論が成立しなくなる。

**実 Model が書いた証拠ではない。** Real Local Model runs = 0 のままである。
"""

from __future__ import annotations

import json

from forge_ai.core.orchestration.capability_artifact_synthesis import (
    CapabilityImplementationContract,
)

CAPABILITY = "view.calendar"
WIDGET_TYPE = "calendar_view"

CALENDAR_CONTRACT = CapabilityImplementationContract(
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




CALENDAR_PAYLOAD = _payload()
