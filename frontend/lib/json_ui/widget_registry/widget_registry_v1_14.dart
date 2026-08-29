library;

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

const _assetByTrack = <String, String>{
  'pulse': 'sounds/forge_tone_pulse.wav',
  'chime': 'sounds/forge_tone_chime.wav',
  'bass': 'sounds/forge_tone_bass.wav',
};

void registerV1_14Widgets(ForgeWidgetRegistry registry) {
  registry.register('audio_mixer', _buildAudioMixer);
}

Widget _buildAudioMixer(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) => _ForgeAudioMixer(node: node as ForgeAudioMixerWidgetNode);

class _ForgeAudioMixer extends StatefulWidget {
  final ForgeAudioMixerWidgetNode node;
  const _ForgeAudioMixer({required this.node});

  @override
  State<_ForgeAudioMixer> createState() => _ForgeAudioMixerState();
}

class _ForgeAudioMixerState extends State<_ForgeAudioMixer> {
  final Map<String, AudioPlayer> _players = {};
  final Set<String> _active = {};
  String? _error;

  Future<void> _toggle(String track) async {
    final asset = _assetByTrack[track];
    if (asset == null) {
      return;
    }
    try {
      final player = _players.putIfAbsent(track, AudioPlayer.new);
      if (_active.contains(track)) {
        await player.stop();
        if (mounted) {
          setState(() => _active.remove(track));
        }
      } else {
        await player.setReleaseMode(ReleaseMode.loop);
        await player.play(AssetSource(asset));
        if (mounted) {
          setState(() {
            _active.add(track);
            _error = null;
          });
        }
      }
    } catch (error, stackTrace) {
      // Keep the user-facing message bounded, but make browser CI preserve the
      // objective backend failure instead of swallowing the only diagnostic.
      debugPrint('Forge audio mixer playback failed for $track: $error');
      debugPrintStack(stackTrace: stackTrace);
      if (mounted) {
        setState(() => _error = '音を再生できませんでした');
      }
    }
  }

  @override
  void dispose() {
    for (final player in _players.values) {
      player.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.node.title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final track in widget.node.tracks)
                  FilterChip(
                    key: ValueKey('audio_mixer_$track'),
                    label: Text(switch (track) {
                      'pulse' => 'Pulse',
                      'chime' => 'Chime',
                      'bass' => 'Bass',
                      _ => track,
                    }),
                    selected: _active.contains(track),
                    onSelected: (_) => _toggle(track),
                  ),
              ],
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
          ],
        ),
      ),
    );
  }
}
