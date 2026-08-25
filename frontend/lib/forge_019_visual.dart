import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme/forge_theme.dart';
import 'forge_019a_visual_fixture.dart';
import 'shared_widgets/generated_app_host_shell.dart';

void main() => runApp(const ProviderScope(child: Forge019VisualApp()));

class Forge019VisualApp extends StatelessWidget {
  const Forge019VisualApp({super.key});

  @override
  Widget build(BuildContext context) {
    final after = Uri.base.queryParameters['state'] == 'after';
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ForgeTheme.theme,
      home: Scaffold(body: SafeArea(child: GeneratedAppHostShell(
        forgeDocument: forge019FinanceDocument(after: after),
      ))),
    );
  }
}

/// 撮影に使う文書。
///
/// **FORGE-019A §7**: After は手書きをやめ、本番の `RevisionService` が
/// 実際に返した文書（`forge_019a_visual_fixture.dart`、生成物）を使う。
///
/// 019では Before と After の両方をここへ手で書いていたため、
/// 「Backendが作るAfter」と「絵のAfter」が別々のSource of Truthになって
/// いた。実装を直しても絵が変わらないので、その絵は変更の証拠にならない。
Map<String, dynamic> forge019FinanceDocument({required bool after}) =>
    after ? forge019aAfterDocument() : forge019aBeforeDocument();
