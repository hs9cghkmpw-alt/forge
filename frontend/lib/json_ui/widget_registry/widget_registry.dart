/// v1.0で確定した6つのWidgetの構築関数(text/text_field/button/column/row/checklist)。
///
/// FORGE-MILESTONE-002 PHASE2で、Registry機構そのものは`widget_registry_core.dart`へ
/// 分離した。このファイルにはv1.0時代からの実装だけが残っている
/// (動作実績を尊重し、ロジック自体は変更していない)。
/// v1.1の6 Widgetは`widget_registry_v1_1.dart`にある。
library;

import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';
import 'widget_registry_v1_1.dart';
import 'widget_registry_v1_3.dart';
import 'widget_registry_v1_5.dart';
import 'widget_registry_v1_6.dart';

export 'widget_registry_core.dart' show ForgeWidgetRegistry, ForgeWidgetBuilder, ForgeFallbackWidget, buildForgeWidget;

/// v1.0の6種 + v1.1の6種 + v1.3の1種 + v1.5の1種 + v1.6の2種、計16種類
/// すべてを登録した既定のRegistryを組み立てる。
///
/// 修正の記録: 当初`ForgeWidgetRegistry`への`extension`として`static withBuiltins()`を
/// 追加しようとしたが、Dartの`extension`は既存クラスへの**インスタンス**メンバー追加の
/// ための機構であり、`ClassName.staticMethod()`の形で呼べる静的メンバーを外部から
/// 追加することはできない(コンパイルエラーになる)。トップレベル関数として
/// 定義し直した。呼び出し側(forge_renderer.dart等)もこの名前に合わせている。
ForgeWidgetRegistry buildDefaultForgeRegistry() {
  final registry = ForgeWidgetRegistry();
  registry.register('text', _buildText);
  registry.register('text_field', _buildTextField);
  registry.register('button', _buildButton);
  registry.register('column', _buildColumn);
  registry.register('row', _buildRow);
  registry.register('checklist', _buildChecklist);
  // v1.1で追加された6種(FORGE-MILESTONE-002 PHASE1/2)。
  // 新Widgetの追加は、このように別ファイルの登録関数を1行呼ぶだけで完結する。
  registerV1_1Widgets(registry);
  // v1.3で追加された1種(FORGE v0.7 Record Runtime Phase1)。
  registerV1_3Widgets(registry);
  // v1.5で追加された1種(FORGE v1.0 Product Quality Sprint1)。
  registerV1_5Widgets(registry);
  // v1.6で追加された2種(Widget Vocabulary Expansion、2026-08-11)。
  registerV1_6Widgets(registry);
  return registry;
}

// ---------------------------------------------------------------------------
// 組み込みWidgetの実装(v1.0、FORGE-MERGE-001〜FORGE-RUNTIME-003で確立)
// ---------------------------------------------------------------------------

Widget _buildText(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeTextWidgetNode;
  final text = n.stateRef != null ? state.getString(n.stateRef!) : n.value;
  final theme = Theme.of(context).textTheme;
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Text(text, style: theme.bodyLarge),
  );
}

Widget _buildTextField(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeTextFieldWidgetNode;
  return _BoundTextField(stateRef: n.stateRef, placeholder: n.placeholder, state: state);
}

Widget _buildButton(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeButtonWidgetNode;
  return ElevatedButton(
    onPressed: () => state.dispatch(n.action),
    child: Text(n.label),
  );
}

Widget _buildColumn(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeColumnWidgetNode;
  return Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    mainAxisSize: MainAxisSize.min,
    children: n.children.map(build).toList(),
  );
}

Widget _buildRow(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeRowWidgetNode;
  // 修正(FORGE-MERGE-002 Task 2, Rendering Error): 以前は全childrenを一律Expandedで
  // 包んでいたため、Row内のbuttonまで横幅いっぱいに引き伸ばされてしまい、
  // Prototype v0.1.3のtool_screen.dartが持っていた「テキスト欄は伸びる/ボタンは
  // 本来の大きさのまま」という見た目と食い違っていた。text_fieldのように
  // 「伸びないとFlutterのレイアウトエラーになる/伸びるのが自然な」Widgetだけを
  // Expandedにし、それ以外は素のまま(本来のサイズ)にする。
  return Row(
    children: n.children.map((c) {
      final child = build(c);
      if (c is ForgeTextFieldWidgetNode) {
        return Expanded(child: child);
      }
      return child;
    }).toList(),
  );
}

Widget _buildChecklist(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeChecklistWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final items = state.getChecklist(n.stateRef);
      if (items.isEmpty) {
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 24),
          child: Center(
            child: Text(n.emptyStateText, style: Theme.of(context).textTheme.bodyMedium),
          ),
        );
      }
      // FORGE-RUNTIME-002 Task 4での修正(理由はFORGE-RUNTIME-002-report.md参照):
      // 1. 外側のColumn(_buildColumn)は`mainAxisSize: MainAxisSize.min`を
      //    明示しているのに対し、この内側のColumnは既定値(MainAxisSize.max)の
      //    ままだった。SingleChildScrollView配下という高さ無制限の文脈で
      //    一貫性が無かったため、明示的に`min`へ揃えた。
      // 2. 各ListTileに`item.id`由来の安定したKeyを付与した(以前はKey無し)。
      //    チェック/追加/削除で件数が変わるリストにKeyが無いと、
      //    FlutterのReconciliationが位置ベースで対応付けを行おうとし、
      //    再構築時に食い違いが起こりうる。
      // 3. leadingのタップ領域を素の`GestureDetector`+`Icon`から`IconButton`へ
      //    変更した(trailingの削除ボタンは元々IconButtonで問題が起きていなかった
      //    ため、同じ標準的なMaterialウィジェットへ統一した)。
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final item in items)
            ListTile(
              key: ValueKey('checklist_item_${item.id}'),
              leading: IconButton(
                icon: Icon(item.done ? Icons.check_circle_rounded : Icons.circle_outlined),
                onPressed: () => state.toggleChecklistItem(n.stateRef, item.id),
              ),
              title: Text(
                item.text,
                style: TextStyle(decoration: item.done ? TextDecoration.lineThrough : null),
              ),
              trailing: IconButton(
                icon: const Icon(Icons.close_rounded, size: 18),
                onPressed: () => state.deleteChecklistItem(n.stateRef, item.id),
              ),
            ),
        ],
      );
    },
  );
}

class _BoundTextField extends StatefulWidget {
  final String stateRef;
  final String? placeholder;
  final ForgeRuntimeState state;
  const _BoundTextField({required this.stateRef, required this.placeholder, required this.state});

  @override
  State<_BoundTextField> createState() => _BoundTextFieldState();
}

class _BoundTextFieldState extends State<_BoundTextField> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.state.getString(widget.stateRef));
    widget.state.addListener(_syncFromState);
  }

  void _syncFromState() {
    final external = widget.state.getString(widget.stateRef);
    if (external != _controller.text) {
      _controller.text = external;
    }
    // FORGE-MILESTONE-003 Task 5: validation errorが変化した場合も
    // (テキスト自体は変わらなくても)再描画してエラー表示を更新する必要がある。
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.state.removeListener(_syncFromState);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: _controller,
      decoration: InputDecoration(
        hintText: widget.placeholder,
        errorText: widget.state.getValidationError(widget.stateRef),
      ),
      onChanged: (value) => widget.state.setString(widget.stateRef, value, notify: false),
      onSubmitted: (_) {},
    );
  }
}
