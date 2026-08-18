/// v1.1で追加された6つのWidgetの構築関数(FORGE-MILESTONE-002 PHASE1/2)。
///
/// 意図的に`widget_registry.dart`本体とは別ファイルにしている。これにより
/// 「新しいWidgetを追加する = このファイルのような新規ファイルを1つ書き、
/// `buildDefaultForgeRegistry()`へ登録を1行足すだけ」という開発体験を
/// 実際に体現している(PHASE2「Widget追加時にRegistryだけ追加で済む方向へ改善」)。
/// v1.0の6 Widget実装(`widget_registry.dart`本体)は、動作実績を尊重し
/// 変更していない。
library;

import 'package:flutter/material.dart';

import '../renderer/design_language.dart';
import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

Widget buildHeading(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeHeadingWidgetNode;
  final style = n.level == 1
      ? Theme.of(context).textTheme.headlineMedium
      : Theme.of(context).textTheme.titleMedium;
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: Text(n.value, style: style),
  );
}

Widget buildCheckbox(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeCheckboxWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      // 標準のCheckboxListTileを使う(FORGE-RUNTIME-003の教訓: 自作の
      // GestureDetector+素のWidgetより、実績のあるMaterial標準Widgetを使う方が安全)。
      final error = state.getValidationError(n.stateRef);
      return CheckboxListTile(
        value: state.getBoolean(n.stateRef),
        // FORGE-MILESTONE-003 Task 4: 個別にsetBooleanを呼ぶのではなく、
        // 他のAction同様Action Dispatcherを経由する(toggle_state)。
        // CheckboxListTileが渡すnewValueは常に「現在値の反転」なので、
        // ToggleStateActionの意味論と完全に一致する。
        onChanged: (_) => state.dispatch(ToggleStateAction(n.stateRef)),
        title: Text(n.label),
        subtitle: error != null
            ? Text(error, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12))
            : null,
        controlAffinity: ListTileControlAffinity.leading,
        contentPadding: EdgeInsets.zero,
      );
    },
  );
}

Widget buildCard(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeCardWidgetNode;
  return Card(
    margin: const EdgeInsets.symmetric(vertical: 8),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: n.children.map(build).toList(),
      ),
    ),
  );
}

Widget buildList(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeListWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final items = state.getStringList(n.stateRef);
      if (items.isEmpty) {
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Text(n.emptyStateText, style: Theme.of(context).textTheme.bodyMedium),
        );
      }
      return Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final item in items)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Text('•  $item'),
            ),
        ],
      );
    },
  );
}

Widget buildDivider(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  return const Divider(height: 24);
}

Widget buildForm(BuildContext context, ForgeWidgetNode node, ForgeRuntimeState state, Widget Function(ForgeWidgetNode) build) {
  final n = node as ForgeFormWidgetNode;
  return Column(
    mainAxisSize: MainAxisSize.min,
    // FORGE-RUNTIME-003で確立した安全な全幅化パターン(Buttonの`minimumSize`自体を
    // infinite widthにするのではなく、親Columnのcross-axisをstretchにする)。
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      ...n.children.map(build),
      const SizedBox(height: 12),
      // v1.12(§6.1)。formに付いた role の強弱を、**送信ボタンへ**渡す。
      // formの主役は送信ボタンなので、面を被せるのではなくボタンの
      // 種類を変えるのが正しい反映のしかたである。
      forgeEmphasisButton(
        emphasis: buttonEmphasisFor(ForgeRoleScope.roleOf(context)),
        // FORGE-MILESTONE-003 Task 4/5: formの送信ボタン自身も、他の場所から
        // form_refで参照する場合と同じ経路(submit_form Action)を通す。
        // n.submitAction(JSON上のsubmit_action)を直接dispatchしていた以前の実装では、
        // Validationが一切実行されなかった。
        onPressed: () => state.dispatch(SubmitFormAction(formRef: n.id, successAction: n.submitAction)),
        child: Text(n.submitLabel),
      ),
    ],
  );
}

/// `buildDefaultForgeRegistry()` から呼ばれる、v1.1 Widget群の一括登録。
/// 新しいWidgetを追加する場合、この関数へ1行足すだけでよい。
void registerV1_1Widgets(ForgeWidgetRegistry registry) {
  registry.register('heading', buildHeading);
  registry.register('checkbox', buildCheckbox);
  registry.register('card', buildCard);
  registry.register('list', buildList);
  registry.register('divider', buildDivider);
  registry.register('form', buildForm);
}
