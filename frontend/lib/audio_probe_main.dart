import 'package:audioplayers/audioplayers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

/// Browser-only objective probe for Forge's bundled audio layering substrate.
///
/// This entrypoint is built by the one-shot Chrome evidence workflow, not by the
/// product launcher. Because it is a real Flutter Web build target, Flutter's
/// generated plugin registrant initializes `audioplayers_web` exactly as it does
/// for the shipped application. The result is reported back to the same-origin
/// evidence server rather than inferred from a test harness MethodChannel mock.
void main() {
  runApp(const _AudioProbeApp());
}

class _AudioProbeApp extends StatefulWidget {
  const _AudioProbeApp();

  @override
  State<_AudioProbeApp> createState() => _AudioProbeAppState();
}

class _AudioProbeAppState extends State<_AudioProbeApp> {
  final _pulse = AudioPlayer();
  final _chime = AudioPlayer();
  String _status = 'running';

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_run);
  }

  Future<void> _report(String status, {String? error}) async {
    try {
      await Dio().get<void>(
        '/report',
        queryParameters: <String, String>{
          'status': status,
          if (error != null) 'error': error,
        },
      );
    } catch (_) {
      // The workflow separately fails when the report file is absent. Do not let
      // reporting failure conceal the audio result behind a second exception.
    }
  }

  Future<void> _run() async {
    try {
      await _pulse.setReleaseMode(ReleaseMode.loop);
      await _chime.setReleaseMode(ReleaseMode.loop);
      await _pulse.play(AssetSource('sounds/forge_tone_pulse.wav'));
      await _chime.play(AssetSource('sounds/forge_tone_chime.wav'));
      if (mounted) {
        setState(() => _status = 'pass');
      }
      await _report('pass');
    } catch (error) {
      final bounded = error.toString();
      if (mounted) {
        setState(() => _status = 'fail: $bounded');
      }
      await _report('fail', error: bounded);
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    _chime.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Center(
          child: Text(_status, key: const ValueKey('forge_audio_probe_status')),
        ),
      ),
    );
  }
}
