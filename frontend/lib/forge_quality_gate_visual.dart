import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme/forge_theme.dart';
import 'forge_quality_gate_fixture.dart';
import 'shared_widgets/generated_app_host_shell.dart';

/// Generated UI Quality Gate v2 の撮影ハーネス
/// (`docs/spec/GENERATED-UI-QUALITY-GATE-V2.md`)。
///
/// `?app=<key>` で撮影対象を選ぶ。Document は
/// `scripts/export_quality_gate_fixtures.py` が**本番の `/generate`**
/// から作った生成物であり、手書きではない。
///
/// **同じ Renderer / Design Language** で性格の違うアプリを描くことが
/// 目的なので、ここでアプリごとの分岐を書いてはならない。書いた時点で
/// 測りたいものが測れなくなる。
void main() => runApp(const ProviderScope(child: ForgeQualityGateApp()));

class ForgeQualityGateApp extends StatelessWidget {
  const ForgeQualityGateApp({super.key});

  @override
  Widget build(BuildContext context) {
    final key = Uri.base.queryParameters['app'] ?? 'finance';
    final document = forgeQualityGateDocuments[key];
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ForgeTheme.theme,
      home: Scaffold(
        body: SafeArea(
          child: document == null
              ? _UnknownApp(requested: key)
              : GeneratedAppHostShell(forgeDocument: document),
        ),
      ),
    );
  }
}

/// 撮影対象が無いときに**黙って空を描かない**。
///
/// 真っ白な PNG は「描けた」と見分けが付かない（019C で実際に踏んだ）。
class _UnknownApp extends StatelessWidget {
  const _UnknownApp({required this.requested});

  final String requested;

  @override
  Widget build(BuildContext context) {
    final available = forgeQualityGateDocuments.keys.join(', ');
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          'MISSING FIXTURE: $requested\n\navailable: $available',
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 18, color: Colors.red),
        ),
      ),
    );
  }
}
