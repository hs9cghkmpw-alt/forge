import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:forge_app/json_ui/renderer/forge_renderer.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

/// Objective browser entrypoint for the exact production-generated Golden game.
///
/// The workflow copies the generated Forge Document into the build as an asset.
/// This is a real Flutter Web application, not a widget-test harness, so browser
/// rendering and plugin registration follow the shipped application path.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    final source = await rootBundle.loadString('assets/forge_golden_game.json');
    final raw = jsonDecode(source) as Map<String, dynamic>;
    // Parse before reporting success so malformed generated documents fail closed.
    ForgeDocument.fromJson(raw);
    runApp(_GoldenProbeApp(raw: raw));
  } catch (error) {
    runApp(_GoldenProbeFailure(error: error.toString()));
  }
}

class _GoldenProbeApp extends StatefulWidget {
  final Map<String, dynamic> raw;
  const _GoldenProbeApp({required this.raw});

  @override
  State<_GoldenProbeApp> createState() => _GoldenProbeAppState();
}

class _GoldenProbeAppState extends State<_GoldenProbeApp> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      // Give periodic simulation + visible state one deterministic slice before
      // reporting. Chrome's virtual-time budget captures the resulting frame.
      await Future<void>.delayed(const Duration(milliseconds: 700));
      if (!mounted) return;
      try {
        await Dio().get<void>('/report', queryParameters: const {'status': 'pass'});
      } catch (_) {}
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: ForgeDocumentView(rawJson: widget.raw),
    );
  }
}

class _GoldenProbeFailure extends StatefulWidget {
  final String error;
  const _GoldenProbeFailure({required this.error});

  @override
  State<_GoldenProbeFailure> createState() => _GoldenProbeFailureState();
}

class _GoldenProbeFailureState extends State<_GoldenProbeFailure> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        await Dio().get<void>('/report', queryParameters: {
          'status': 'fail',
          'error': widget.error,
        });
      } catch (_) {}
    });
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        home: Scaffold(body: Center(child: Text('Golden render failed: ${widget.error}'))),
      );
}
