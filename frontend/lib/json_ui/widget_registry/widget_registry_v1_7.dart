/// v1.7で追加された2種のWidget(`date_field`・`tab_view`)の構築関数
/// (Widget Vocabulary Expansion第2弾、2026-08-11)。
///
/// CEO「全て実装してくれ。確認もしなくて良い、ゴールは示している。
/// つくってくれ。」という明示的な指示を受けて着手した
/// (`TECH_DEBT.md`参照)。v1.1・v1.3・v1.5・v1.6と同じ理由
/// (`widget_registry_v1_1.dart`冒頭コメント参照)で、別ファイルへ
/// 分離している。
///
/// **`tab_view`の実装方針(重要)**: 素朴には`DefaultTabController`+
/// `TabBar`+`TabBarView`で実装したくなるが、`TabBarView`は内部で
/// `PageView`を使っており、**高さが有限に制約された文脈でしか
/// レイアウトできない**。`ForgeScreenView.build()`
/// (`forge_renderer.dart`)は画面全体を`SingleChildScrollView`で
/// 包んでおり、その内部は高さが無制限になるため、`TabBarView`を
/// そのまま置くと典型的な「unbounded height」のレイアウトエラーに
/// なる(このサンドボックスには`flutter analyze`/実機確認の手段が
/// 無く、この種のレイアウトエラーは実行時にしか顕在化しないため、
/// 検証できない設計は避けるという判断)。
///
/// 代わりに、`TabBarView`(PageViewベース)を一切使わず、選択中の
/// タブ1つの中身だけを、既存の`build`コールバックでその場に描画する
/// (`_TabViewSwitcher`)。タブ切り替え自体は素の`int`状態で行う
/// (`TabController`/`vsync`も使わない、Widget構成として実績のある
/// `StatefulWidget`+`setState`のみで完結させる、最も検証が容易な
/// 構成を優先した)。
library;

import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

Widget buildDateField(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeDateFieldWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final currentValue = state.getString(n.stateRef);
      final error = state.getValidationError(n.stateRef);
      final parsedDate = currentValue.isEmpty ? null : DateTime.tryParse(currentValue);

      return InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () async {
          final now = DateTime.now();
          final picked = await showDatePicker(
            context: context,
            initialDate: parsedDate ?? now,
            firstDate: DateTime(1900),
            lastDate: DateTime(2100),
          );
          // choice_field(`widget_registry_v1_6.dart`)と同じ理由で
          // `notify`は既定値(true)のまま呼ぶ: 日付選択は1回で確定する
          // 離散的な操作であり、選択直後に自動保存機構が状態を保存
          // できるようにするため。
          if (picked != null) {
            state.setString(n.stateRef, _formatIsoDate(picked));
          }
        },
        child: InputDecorator(
          decoration: InputDecoration(
            labelText: n.label,
            hintText: n.placeholder,
            errorText: error,
            suffixIcon: const Icon(Icons.calendar_today_rounded, size: 18),
          ),
          child: Text(currentValue.isEmpty ? '' : currentValue),
        ),
      );
    },
  );
}

/// `DateTime`を`ForgeFieldValueParser._parseDate()`が要求する厳密な
/// ISO 8601形式(YYYY-MM-DD)へ変換する。`DateTime.toString()`は
/// 時刻・タイムゾーン情報まで含むため使えない(専用の整形が必要)。
String _formatIsoDate(DateTime date) {
  final y = date.year.toString().padLeft(4, '0');
  final m = date.month.toString().padLeft(2, '0');
  final d = date.day.toString().padLeft(2, '0');
  return '$y-$m-$d';
}

Widget buildTabView(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeTabViewWidgetNode;
  return _TabViewSwitcher(node: n, build: build);
}

class _TabViewSwitcher extends StatefulWidget {
  final ForgeTabViewWidgetNode node;
  final Widget Function(ForgeWidgetNode) build;
  const _TabViewSwitcher({required this.node, required this.build});

  @override
  State<_TabViewSwitcher> createState() => _TabViewSwitcherState();
}

class _TabViewSwitcherState extends State<_TabViewSwitcher> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            for (var i = 0; i < widget.node.tabTitles.length; i++)
              Expanded(
                child: _TabButton(
                  label: widget.node.tabTitles[i],
                  selected: i == _selectedIndex,
                  onTap: () => setState(() => _selectedIndex = i),
                ),
              ),
          ],
        ),
        const SizedBox(height: 16),
        // 選択中のタブの中身**だけ**をその場に描画する(TabBarViewの
        // ような「全タブを保持しつつオフスクリーンへ配置」はしない、
        // 最も単純で検証しやすい実装)。タブを切り替えるとその中身の
        // Widget(通常はcolumn)が丸ごと再構築されるため、フォームの
        // 入力中の値のような「タブをまたいで保持したい一時的な状態」は
        // 無い設計が前提(Forge Language Compiler側は、タブごとに
        // 独立したstate_refを割り当てるため問題にならない)。
        widget.build(widget.node.children[_selectedIndex]),
      ],
    );
  }
}

class _TabButton extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _TabButton({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final activeColor = Theme.of(context).colorScheme.primary;
    final inactiveColor = Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6);
    final color = selected ? activeColor : inactiveColor;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              textAlign: TextAlign.center,
              overflow: TextOverflow.ellipsis,
              maxLines: 1,
              style: TextStyle(color: color, fontWeight: selected ? FontWeight.w700 : FontWeight.w500, fontSize: 13),
            ),
            const SizedBox(height: 6),
            Container(
              height: 3,
              decoration: BoxDecoration(
                color: selected ? activeColor : Colors.transparent,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// `buildDefaultForgeRegistry()` から呼ばれる、v1.7 Widget群の一括登録。
void registerV1_7Widgets(ForgeWidgetRegistry registry) {
  registry.register('date_field', buildDateField);
  registry.register('tab_view', buildTabView);
}
