/// v1.3で追加されたWidget(`record_list_view`)の構築関数
/// (FORGE v0.7 Record Runtime Phase1、FORGE v0.8 Record Runtime Phase2で
/// 選択機能を追加、FORGE v1.0でSchema-driven表示に対応)。
///
/// v1.1と同じ理由(widget_registry_v1_1.dart冒頭コメント参照)で、
/// 別ファイルへ分離している。Phase1では`record_list_view`の
/// `layout="card"`のみを実装する(`layout="table"`は指示書の制約により
/// 未実装、`ForgeParseException`にはならず、Backend Validatorの時点で
/// 弾かれる設計)。
///
/// **FORGE v0.8での追加**: `selectable`が`true`の場合、各Cardに
/// 「編集」ボタンが表示される。タップされたRecordの実際のid(この
/// Widgetのbuild時点で分かる、Compiler出力の静的なJSONには書けない
/// 情報)を`SelectRecordAction.withRecordId()`で補ってから
/// `state.dispatch()`する(`forge_document.dart`の`SelectRecordAction`
/// docコメント参照)。**「削除」ボタンはこのWidgetの責務ではない**:
/// `DeleteRecordAction`は`record_id_ref`(通常`selected_record`)経由の
/// 静的なActionであり、既存の汎用`button` Widget(`_buildButton`)から
/// 普通に発行できるため、record_list_view固有の実装を必要としない
/// (`forge_ai/core/ir/forge_language_compiler.py`が生成する構成と
/// 対称、責務分離)。
///
/// **FORGE v1.0での追加(Workstream D: Schema-driven Record
/// Display)**: `record_list`の`schema_ref`が解決できる場合、
/// 内部Field名ではなく[ForgeRecordSchema]の`label`を表示し、
/// 表示順もSchemaのField順に従う。Recordに存在しないField
/// (非必須で未入力)は安全にスキップする。**Schemaに定義が無い
/// FieldがRecordに存在する場合、表示しない**(指示書「Schemaに無い
/// 追加FieldがRecordに存在する場合の方針を明示」への回答:
/// 意図しないデータ漏洩を避けるため、Schema定義済みのFieldのみを
/// 表示対象とする、安全側の方針)。schema_refが無い(v1.3以前の
/// Legacy文書)場合は、従来通りField名をそのまま表示する
/// (指示書Workstream C.5と対になる、表示側のLegacy Behavior)。
library;

import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import '../validation/forge_value_formatter.dart';
import 'widget_registry_core.dart';

Widget buildRecordListView(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeRecordListViewWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final records = state.getRecordList(n.stateRef);
      if (records.isEmpty) {
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Text(n.emptyStateText, style: Theme.of(context).textTheme.bodyMedium),
        );
      }
      final selectedId = (n.selectable && n.selectedStateRef != null)
          ? state.getSelectedRecord(n.selectedStateRef!)?.id
          : null;

      // FORGE v1.0対応: schema_refが解決できれば、Schema-driven表示へ。
      final schemaRef = state.getRecordListSchemaRef(n.stateRef);
      final schema = schemaRef != null ? state.getRecordSchema(schemaRef) : null;

      final cards = [
        for (final record in records)
          _RecordCard(
            record: record,
            displayFields: n.displayFields,
            schema: schema,
            isSelected: n.selectable && record.id == selectedId,
            onSelect: (n.selectable && n.selectedStateRef != null)
                ? () => state.dispatch(
                      SelectRecordAction(
                        sourceStateRef: n.stateRef,
                        targetStateRef: n.selectedStateRef!,
                        recordId: '',
                        fieldBindings: n.selectFieldBindings ?? const {},
                      ).withRecordId(record.id),
                    )
                : null,
          ),
      ];

      // FORGE v1.0新規(Product Quality Sprint1)。`layout=="grid"`の
      // 場合、2列のGridで表示する(指示書「Field数が少なくコンパクトな
      // Domain」向け、`forge_language_compiler.py`が選択する)。
      // 未知のlayout値(Backend Validatorが弾くはずだが多重防御として)
      // も含め、"grid"以外は全てcard(縦並び)表示へ安全にフォールバック
      // する(既存の「未知Widgetは安全にFallback」という設計原則を
      // Widget内部の分岐にも適用する)。
      if (n.layout == 'grid') {
        return GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 8,
          crossAxisSpacing: 8,
          childAspectRatio: 1.1,
          children: cards,
        );
      }

      return Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: cards,
      );
    },
  );
}

class _RecordCard extends StatelessWidget {
  final ForgeRecordItem record;
  final List<String>? displayFields;
  final ForgeRecordSchema? schema;
  final bool isSelected;
  final VoidCallback? onSelect;

  static const _formatter = ForgeValueFormatter();

  const _RecordCard({
    required this.record,
    required this.displayFields,
    this.schema,
    this.isSelected = false,
    this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    final rows = schema != null ? _buildSchemaDrivenRows(context) : _buildLegacyRows(context);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      // FORGE v0.8対応: 選択中のCardを視覚的に区別する(指示書
      // 「デザイン改善は不要」に沿った、最小限の色分けのみ)。
      color: isSelected ? Theme.of(context).colorScheme.primaryContainer : null,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ...rows,
            if (onSelect != null)
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: onSelect,
                  child: Text(isSelected ? '選択中' : '編集'),
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// FORGE v1.0新規: Schemaが解決できる場合の表示行。label・Schema
  /// Field順・型に応じたFormatterを使う。
  List<Widget> _buildSchemaDrivenRows(BuildContext context) {
    final resolvedSchema = schema!;
    final fieldsToShow = displayFields != null
        ? resolvedSchema.fields.where((f) => displayFields!.contains(f.name))
        : resolvedSchema.fields;

    final rows = <Widget>[];
    for (final field in fieldsToShow) {
      if (!record.fields.containsKey(field.name)) {
        // 非必須Fieldが未入力の場合等。安全にスキップする(空欄表示はしない)。
        continue;
      }
      final formatted = _formatter.format(record.fields[field.name], field.type);
      rows.add(Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Text('${field.label}: $formatted', style: Theme.of(context).textTheme.bodyMedium),
      ));
    }
    return rows;
  }

  /// Legacy表示(schema_refが無い、v1.3以前の文書向け)。FORGE v0.7〜
  /// v0.9と全く同じロジック(内部Field名をそのまま表示する)。
  List<Widget> _buildLegacyRows(BuildContext context) {
    final fieldNames = displayFields ?? record.fields.keys.toList();
    final rows = <Widget>[];
    for (final fieldName in fieldNames) {
      if (!record.fields.containsKey(fieldName)) continue;
      rows.add(Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Text(
          '$fieldName: ${record.fields[fieldName]}',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ));
    }
    return rows;
  }
}

/// `buildDefaultForgeRegistry()` から呼ばれる、v1.3 Widget群の一括登録。
void registerV1_3Widgets(ForgeWidgetRegistry registry) {
  registry.register('record_list_view', buildRecordListView);
}
