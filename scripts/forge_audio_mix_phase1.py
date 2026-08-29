from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(rel: str, old: str, new: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected exactly one target, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def write_tone(path: Path, frequency: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 22_050
    seconds = 0.5
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for i in range(frames):
            envelope = min(1.0, i / (rate * 0.02), (frames - i) / (rate * 0.04))
            sample = int(9_000 * envelope * math.sin(2 * math.pi * frequency * i / rate))
            wav.writeframesraw(struct.pack("<h", sample))


# ---------------------------------------------------------------------------
# Semantic planning: distinguish "mix sounds" from generic media composition.
# The Golden game uses an immediate local interaction, not a network/media export.
# Keep it PARTIAL until the real browser audio probe is green.
# ---------------------------------------------------------------------------
replace_once(
    "forge_ai/core/semantics/capabilities.py",
    '''    _c("interact.edit", _L.INTERACT, "後から直す", "記録を編集する", _S.IMPLEMENTED),\n    _c("interact.filter", _L.INTERACT, "絞り込む", "条件で絞って見る", _S.MISSING,\n''',
    '''    _c("interact.edit", _L.INTERACT, "後から直す", "記録を編集する", _S.IMPLEMENTED),\n    _c("interact.audio_mix", _L.INTERACT, "音を重ねて組み合わせる",\n       "内蔵された複数の音を同時に鳴らして組み合わせる", _S.PARTIAL,\n       detection_keywords=("音を組み合わせ", "音を重ね", "サウンドを組み合わせ"),\n       limitation="内蔵音源の組み合わせまで対応しています。任意の音声素材の取り込みはまだできません"),\n    _c("interact.filter", _L.INTERACT, "絞り込む", "条件で絞って見る", _S.MISSING,\n''',
)

plan_file = "forge_ai/core/semantics/capability_plan.py"
replace_once(
    plan_file,
    '''_ACTIVITY_CAPABILITIES: dict[str, tuple[str, ...]] = {\n    "combine": ("effect.media_compose",),\n}\n''',
    '''_ACTIVITY_CAPABILITIES: dict[str, tuple[str, ...]] = {}\n''',
)
replace_once(
    plan_file,
    '''    requested: set[str] = set()\n\n    # -- 1件ごとに残す値 ------------------------------------------------\n    fields: list[PlannedField] = []\n    for value in roles.of(SemanticRole.RECORDED_DATA):\n        blueprint = _FIELD_BLUEPRINT.get(value)\n''',
    '''    requested: set[str] = set()\n    activities = set(roles.of(SemanticRole.ACTIVITY))\n\n    # -- 1件ごとに残す値 ------------------------------------------------\n    fields: list[PlannedField] = []\n    for value in roles.of(SemanticRole.RECORDED_DATA):\n        # 「音を組み合わせる」の音は記録Fieldではなくミキサーの素材。\n        # 同じ表層語を無条件にdata.audioへ落とすと、ゲームに意味のない\n        # 音声ファイル名入力欄が生える。役の組み合わせで権限を限定する。\n        if value == "sound" and "combine" in activities:\n            continue\n        blueprint = _FIELD_BLUEPRINT.get(value)\n''',
)
replace_once(
    plan_file,
    '''    for value in roles.of(SemanticRole.ACTIVITY):\n        for capability_id in _ACTIVITY_CAPABILITIES.get(value, ()):\n            requested.add(capability_id)\n\n    # **ゲームは「育てる」と「組み合わせる」が揃ったときに要求される。**\n    activities = set(roles.of(SemanticRole.ACTIVITY))\n    if "grow" in activities and "combine" in activities:\n        requested.add("simulate.loop")\n''',
    '''    for value in roles.of(SemanticRole.ACTIVITY):\n        for capability_id in _ACTIVITY_CAPABILITIES.get(value, ()):\n            requested.add(capability_id)\n\n    if "combine" in activities:\n        recorded_values = set(roles.of(SemanticRole.RECORDED_DATA))\n        if "sound" in recorded_values:\n            requested.add("interact.audio_mix")\n        else:\n            # Object of "combine" is not resolved to sound. Do not pretend the\n            # narrower audio mixer satisfies generic image/media composition.\n            requested.add("effect.media_compose")\n\n    # **ゲームは「育てる」と「組み合わせる」が揃ったときに要求される。**\n    if "grow" in activities and "combine" in activities:\n        requested.add("simulate.loop")\n''',
)

# Runtime binding for PARTIAL is allowed and means "near implementation used".
replace_once(
    "backend/app/ai/runtime/capability.py",
    '''    "interact.edit": ("form", "record_list_view"),\n    "simulate.loop": ("simulation_loop",),\n''',
    '''    "interact.edit": ("form", "record_list_view"),\n    "interact.audio_mix": ("audio_mixer",),\n    "simulate.loop": ("simulation_loop",),\n''',
)

# ---------------------------------------------------------------------------
# Flutter dependency + built-in local tone assets.
# ---------------------------------------------------------------------------
replace_once(
    "frontend/pubspec.yaml",
    '''  speech_to_text: ^7.0.0\n''',
    '''  speech_to_text: ^7.0.0\n  # v1.14 local audio mixer. Multiple players may run simultaneously; no network\n  # source is accepted by Forge Language. Version verified on pub.dev 2026-08-29.\n  audioplayers: ^6.8.1\n''',
)
replace_once(
    "frontend/pubspec.yaml",
    '''  assets:\n    - assets/images/forge_f_mark.png\n''',
    '''  assets:\n    - assets/images/forge_f_mark.png\n    - assets/sounds/\n''',
)
write_tone(ROOT / "frontend/assets/sounds/forge_tone_pulse.wav", 220.0)
write_tone(ROOT / "frontend/assets/sounds/forge_tone_chime.wav", 440.0)
write_tone(ROOT / "frontend/assets/sounds/forge_tone_bass.wav", 110.0)

# ---------------------------------------------------------------------------
# Dart model/parser + registry.
# ---------------------------------------------------------------------------
dart_schema = "frontend/lib/json_ui/schema/forge_document.dart"
replace_once(
    dart_schema,
    '''      case 'simulation_loop':\n        // v1.13: deterministic fixed-step simulation lifecycle. The widget owns\n        // scheduling only; arithmetic remains in runtime/forge_simulation.dart.\n        final simulationStateRef = json['state_ref'];\n''',
    '''      case 'audio_mixer':\n        final rawTracks = json['tracks'];\n        if (rawTracks is! List || rawTracks.isEmpty) {\n          throw ForgeParseException('$path/tracks', 'audio_mixer.tracks is required');\n        }\n        return ForgeAudioMixerWidgetNode(\n          id,\n          title: json['title'] as String? ?? 'サウンドミックス',\n          tracks: rawTracks.cast<String>(),\n        );\n      case 'simulation_loop':\n        // v1.13: deterministic fixed-step simulation lifecycle. The widget owns\n        // scheduling only; arithmetic remains in runtime/forge_simulation.dart.\n        final simulationStateRef = json['state_ref'];\n''',
)
replace_once(
    dart_schema,
    '''/// v1.13: behavior-only fixed-step simulation loop. The referenced state must\n/// be a number and stores the deterministic emitted tick count.\nclass ForgeSimulationLoopWidgetNode extends ForgeWidgetNode {\n''',
    '''/// v1.14: user-driven local sound-layer mixer. Track identifiers are a closed\n/// Forge vocabulary and never arbitrary paths or URLs.\nclass ForgeAudioMixerWidgetNode extends ForgeWidgetNode {\n  final String title;\n  final List<String> tracks;\n  const ForgeAudioMixerWidgetNode(\n    super.id, {required this.title, required this.tracks}\n  );\n}\n\n/// v1.13: behavior-only fixed-step simulation loop. The referenced state must\n/// be a number and stores the deterministic emitted tick count.\nclass ForgeSimulationLoopWidgetNode extends ForgeWidgetNode {\n''',
)

registry_core = "frontend/lib/json_ui/widget_registry/widget_registry_core.dart"
replace_once(
    registry_core,
    '''      ForgeMetricViewWidgetNode() => 'metric_view',\n      ForgeSimulationLoopWidgetNode() => 'simulation_loop',\n''',
    '''      ForgeMetricViewWidgetNode() => 'metric_view',\n      ForgeAudioMixerWidgetNode() => 'audio_mixer',\n      ForgeSimulationLoopWidgetNode() => 'simulation_loop',\n''',
)

registry_main = "frontend/lib/json_ui/widget_registry/widget_registry.dart"
replace_once(
    registry_main,
    '''import 'widget_registry_v1_13.dart';\n''',
    '''import 'widget_registry_v1_13.dart';\nimport 'widget_registry_v1_14.dart';\n''',
)
replace_once(
    registry_main,
    '''  registerV1_13Widgets(registry);\n  return registry;\n''',
    '''  registerV1_13Widgets(registry);\n  registerV1_14Widgets(registry);\n  return registry;\n''',
)

(ROOT / "frontend/lib/json_ui/widget_registry/widget_registry_v1_14.dart").write_text(
    '''library;\n\nimport 'package:audioplayers/audioplayers.dart';\nimport 'package:flutter/material.dart';\n\nimport '../renderer/forge_runtime_state.dart';\nimport '../schema/forge_document.dart';\nimport 'widget_registry_core.dart';\n\nconst _assetByTrack = <String, String>{\n  'pulse': 'sounds/forge_tone_pulse.wav',\n  'chime': 'sounds/forge_tone_chime.wav',\n  'bass': 'sounds/forge_tone_bass.wav',\n};\n\nvoid registerV1_14Widgets(ForgeWidgetRegistry registry) {\n  registry.register('audio_mixer', _buildAudioMixer);\n}\n\nWidget _buildAudioMixer(\n  BuildContext context,\n  ForgeWidgetNode node,\n  ForgeRuntimeState state,\n  Widget Function(ForgeWidgetNode) build,\n) => _ForgeAudioMixer(node: node as ForgeAudioMixerWidgetNode);\n\nclass _ForgeAudioMixer extends StatefulWidget {\n  final ForgeAudioMixerWidgetNode node;\n  const _ForgeAudioMixer({required this.node});\n\n  @override\n  State<_ForgeAudioMixer> createState() => _ForgeAudioMixerState();\n}\n\nclass _ForgeAudioMixerState extends State<_ForgeAudioMixer> {\n  final Map<String, AudioPlayer> _players = {};\n  final Set<String> _active = {};\n  String? _error;\n\n  Future<void> _toggle(String track) async {\n    final asset = _assetByTrack[track];\n    if (asset == null) return;\n    try {\n      final player = _players.putIfAbsent(track, AudioPlayer.new);\n      if (_active.contains(track)) {\n        await player.stop();\n        if (mounted) setState(() => _active.remove(track));\n      } else {\n        await player.setReleaseMode(ReleaseMode.loop);\n        await player.play(AssetSource(asset));\n        if (mounted) setState(() {\n          _active.add(track);\n          _error = null;\n        });\n      }\n    } catch (error) {\n      if (mounted) setState(() => _error = '音を再生できませんでした');\n    }\n  }\n\n  @override\n  void dispose() {\n    for (final player in _players.values) {\n      player.dispose();\n    }\n    super.dispose();\n  }\n\n  @override\n  Widget build(BuildContext context) {\n    return Card(\n      child: Padding(\n        padding: const EdgeInsets.all(16),\n        child: Column(\n          crossAxisAlignment: CrossAxisAlignment.start,\n          children: [\n            Text(widget.node.title, style: Theme.of(context).textTheme.titleMedium),\n            const SizedBox(height: 8),\n            Wrap(\n              spacing: 8,\n              runSpacing: 8,\n              children: [\n                for (final track in widget.node.tracks)\n                  FilterChip(\n                    key: ValueKey('audio_mixer_$track'),\n                    label: Text(switch (track) {\n                      'pulse' => 'Pulse',\n                      'chime' => 'Chime',\n                      'bass' => 'Bass',\n                      _ => track,\n                    }),\n                    selected: _active.contains(track),\n                    onSelected: (_) => _toggle(track),\n                  ),\n              ],\n            ),\n            if (_error != null) ...[\n              const SizedBox(height: 8),\n              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),\n            ],\n          ],\n        ),\n      ),\n    );\n  }\n}\n''',
    encoding="utf-8",
)

# Exhaustive black-box duplicate switch must track the sealed vocabulary.
replace_once(
    "frontend/test/features/app_generation/data/datasources/mock_generator_renderer_contract_test.dart",
    '''      ForgeSimulationLoopWidgetNode() => 'simulation_loop',\n      ForgeUnknownWidgetNode() => 'unknown',\n''',
    '''      ForgeSimulationLoopWidgetNode() => 'simulation_loop',\n      ForgeAudioMixerWidgetNode() => 'audio_mixer',\n      ForgeUnknownWidgetNode() => 'unknown',\n''',
)

# ---------------------------------------------------------------------------
# Backend Forge Language v1.14 validator.
# ---------------------------------------------------------------------------
validator = "backend/app/ai/validators/schema_validator.py"
replace_once(
    validator,
    '''SUPPORTED_VERSIONS = {"1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13"}\n''',
    '''SUPPORTED_VERSIONS = {"1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13", "1.14"}\n''',
)
replace_once(
    validator,
    '''_VERSION_ORDER = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13")\n''',
    '''_VERSION_ORDER = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13", "1.14")\n''',
)
replace_once(
    validator,
    '''WIDGET_TYPES_V1_13_ADDITIONS = {"simulation_loop"}\n\nWIDGET_TYPES_BY_VERSION''',
    '''WIDGET_TYPES_V1_13_ADDITIONS = {"simulation_loop"}\nWIDGET_TYPES_V1_14_ADDITIONS = {"audio_mixer"}\n\nWIDGET_TYPES_BY_VERSION''',
)
replace_once(
    validator,
    '''    "1.13": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n    ),\n}\nWIDGET_TYPES_ALL = (\n''',
    '''    "1.13": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n    ),\n    "1.14": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n        | WIDGET_TYPES_V1_14_ADDITIONS\n    ),\n}\nWIDGET_TYPES_ALL = (\n''',
)
replace_once(
    validator,
    '''    | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n)  # 未知Widget判定用\n''',
    '''    | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n    | WIDGET_TYPES_V1_14_ADDITIONS\n)  # 未知Widget判定用\n''',
)
replace_once(
    validator,
    '''    "1.13": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n}\n''',
    '''    "1.13": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n    "1.14": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n}\n''',
)
replace_once(
    validator,
    '''    "1.13": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n}\n''',
    '''    "1.13": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n    "1.14": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n}\n''',
)
replace_once(
    validator,
    '''    elif t == "divider":\n''',
    '''    elif t == "audio_mixer":\n        errors.extend(_check_additional_properties(widget, {"type", "id", "title", "tracks"}, path))\n        if "title" in widget and not _is_nonempty_str(widget.get("title"), 80):\n            errors.append(_err(f"{path}/title", Category.SCHEMA, "string_length",\n                               "audio_mixer.titleは1〜80文字です。"))\n        tracks = widget.get("tracks")\n        allowed_tracks = {"pulse", "chime", "bass"}\n        if not isinstance(tracks, list) or not (1 <= len(tracks) <= 3):\n            errors.append(_err(f"{path}/tracks", Category.SCHEMA, "array_bounds",\n                               "audio_mixer.tracksは1〜3件です。"))\n        elif len(set(tracks)) != len(tracks) or any(track not in allowed_tracks for track in tracks):\n            errors.append(_err(f"{path}/tracks", Category.SCHEMA, "enum",\n                               "audio_mixer.tracksはpulse/chime/bassの重複なし配列です。"))\n\n    elif t == "divider":\n''',
)

# ---------------------------------------------------------------------------
# Production compiler attaches the mixer when the interaction plan asks for it.
# ---------------------------------------------------------------------------
compiler = "forge_ai/core/ir/forge_language_compiler.py"
replace_once(
    compiler,
    '''        layout_emphasis: str = "",\n        simulation_capabilities: tuple[str, ...] = (),\n    ) -> ForgeIRDocument:\n''',
    '''        layout_emphasis: str = "",\n        simulation_capabilities: tuple[str, ...] = (),\n        interaction_capabilities: tuple[str, ...] = (),\n    ) -> ForgeIRDocument:\n''',
)
replace_once(
    compiler,
    '''        if "simulate.loop" in simulation_capabilities:\n            document = self._attach_simulation_loop(document)\n        return document\n\n    @staticmethod\n    def _attach_simulation_loop''',
    '''        if "simulate.loop" in simulation_capabilities:\n            document = self._attach_simulation_loop(document)\n        if "interact.audio_mix" in interaction_capabilities:\n            document = self._attach_audio_mixer(document)\n        return document\n\n    @staticmethod\n    def _attach_audio_mixer(document: ForgeIRDocument) -> ForgeIRDocument:\n        widget_id = "audio_mixer"\n\n        def contains_id(node: ForgeIRWidget) -> bool:\n            return node.id == widget_id or any(contains_id(child) for child in node.children)\n\n        screens: list[ForgeIRScreen] = []\n        for screen in document.screens:\n            if contains_id(screen.body):\n                raise ForgeLanguageCompilationError(f"audio mixer widget id collision: {widget_id}")\n            mixer = ForgeIRWidget(\n                type="audio_mixer", id=widget_id,\n                properties={\n                    "title": "サウンドミックス",\n                    "tracks": ["pulse", "chime", "bass"],\n                },\n            )\n            if screen.body.type == "column":\n                body = ForgeIRWidget(\n                    type=screen.body.type, id=screen.body.id,\n                    properties=dict(screen.body.properties),\n                    children=(*screen.body.children, mixer),\n                )\n            else:\n                body = ForgeIRWidget(type="column", id="audio_root", children=(screen.body, mixer))\n            screens.append(ForgeIRScreen(\n                id=screen.id, title=screen.title, state=dict(screen.state), body=body,\n            ))\n        return ForgeIRDocument(\n            version="1.14", initial_screen_id=document.initial_screen_id,\n            screens=tuple(screens), app_title=document.app_title,\n            record_schemas=dict(document.record_schemas),\n            design_tokens=dict(document.design_tokens),\n        )\n\n    @staticmethod\n    def _attach_simulation_loop''',
)
replace_once(
    "forge_ai/core/orchestration/pipeline_orchestrator.py",
    '''                    simulation_capabilities=capability_plan.simulations,\n                )\n''',
    '''                    simulation_capabilities=capability_plan.simulations,\n                    interaction_capabilities=capability_plan.interactions,\n                )\n''',
)

# ---------------------------------------------------------------------------
# Tests: validator, parser/registry, semantic planning and generated output.
# ---------------------------------------------------------------------------
(ROOT / "backend/tests/test_forge_v1_14_audio_mixer.py").write_text(
    '''from app.ai.validators.schema_validator import validate_forge_document\n\n\ndef _doc(version="1.14"):\n    return {\n        "version": version,\n        "initial_screen_id": "home",\n        "screens": [{\n            "id": "home", "title": "Audio", "state": {},\n            "body": {"type": "audio_mixer", "id": "mixer",\n                     "title": "Mix", "tracks": ["pulse", "chime", "bass"]},\n        }],\n    }\n\n\ndef test_v114_accepts_closed_local_audio_mixer_vocabulary():\n    assert validate_forge_document(_doc()).valid\n\n\ndef test_v113_rejects_audio_mixer():\n    result = validate_forge_document(_doc("1.13"))\n    assert not result.valid\n    assert any(e.rule == "widget_not_allowed_in_version" for e in result.errors)\n\n\ndef test_audio_mixer_rejects_unknown_track():\n    doc = _doc()\n    doc["screens"][0]["body"]["tracks"] = ["https://example.com/audio.wav"]\n    result = validate_forge_document(doc)\n    assert not result.valid\n''',
    encoding="utf-8",
)

(ROOT / "frontend/test/json_ui/forge_audio_mixer_widget_test.dart").write_text(
    '''import 'package:flutter/material.dart';\nimport 'package:flutter_test/flutter_test.dart';\n\nimport 'package:forge_studio/json_ui/renderer/forge_runtime_state.dart';\nimport 'package:forge_studio/json_ui/schema/forge_document.dart';\nimport 'package:forge_studio/json_ui/widget_registry/widget_registry.dart';\n\nvoid main() {\n  test('audio_mixer parses closed track ids', () {\n    final node = ForgeWidgetNode.fromJson(const {\n      'type': 'audio_mixer', 'id': 'mixer', 'title': 'Mix',\n      'tracks': ['pulse', 'chime', 'bass'],\n    }, '/body');\n    expect(node, isA<ForgeAudioMixerWidgetNode>());\n    final mixer = node as ForgeAudioMixerWidgetNode;\n    expect(mixer.tracks, ['pulse', 'chime', 'bass']);\n  });\n\n  testWidgets('audio_mixer renders user-driven layer controls', (tester) async {\n    final node = ForgeWidgetNode.fromJson(const {\n      'type': 'audio_mixer', 'id': 'mixer', 'title': 'Mix',\n      'tracks': ['pulse', 'chime', 'bass'],\n    }, '/body');\n    final runtime = ForgeRuntimeState(const <String, ForgeStateValue>{});\n    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) =>\n      buildForgeWidget(context, node, runtime, buildDefaultForgeRegistry(), (_) => const SizedBox.shrink())\n    )));\n    expect(find.text('Mix'), findsOneWidget);\n    expect(find.byKey(const ValueKey('audio_mixer_pulse')), findsOneWidget);\n    expect(find.byKey(const ValueKey('audio_mixer_chime')), findsOneWidget);\n    expect(find.byKey(const ValueKey('audio_mixer_bass')), findsOneWidget);\n  });\n}\n''',
    encoding="utf-8",
)

(ROOT / "forge_ai/tests/test_audio_mix_capability_generation.py").write_text(
    '''from forge_ai.core.ir.capability_ir import entity_spec_from_plan\nfrom forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler\nfrom forge_ai.core.ir.ir_generator import IRGenerator\nfrom forge_ai.core.semantics.capability_plan import plan_capabilities\n\nGAME = "植物を育てながら音を組み合わせるゲームを作りたい"\n\n\ndef _walk(node):\n    yield node\n    for child in node.get("children", []):\n        yield from _walk(child)\n\n\ndef test_sound_combine_is_audio_mix_not_generic_media_export():\n    plan = plan_capabilities(GAME)\n    assert "interact.audio_mix" in plan.interactions\n    assert "effect.media_compose" not in plan.requested\n    assert all(field.capability != "data.audio" for field in plan.fields)\n\n\ndef test_audio_mix_materializes_real_v114_widget():\n    plan = plan_capabilities(GAME)\n    spec = entity_spec_from_plan(plan)\n    assert spec is not None\n    ir = IRGenerator().build_from_spec(spec)\n    doc = ForgeLanguageCompiler().compile(\n        ir, domain_category="generic", title="育成ゲーム",\n        simulation_capabilities=plan.simulations,\n        interaction_capabilities=plan.interactions,\n    ).to_json_dict()\n    assert doc["version"] == "1.14"\n    widgets = [w for screen in doc["screens"] for w in _walk(screen["body"])]\n    assert sum(w.get("type") == "simulation_loop" for w in widgets) == 1\n    assert sum(w.get("type") == "audio_mixer" for w in widgets) == 1\n''',
    encoding="utf-8",
)

# Production SoT evidence must see the PARTIAL mixer as used, not missing.
replace_once(
    "backend/tests/test_forge_020a2_capability_sot.py",
    '''            ("植物を育てながら音を組み合わせるゲームを作りたい",\n             ("simulate.loop",)),\n''',
    '''            ("植物を育てながら音を組み合わせるゲームを作りたい",\n             ("simulate.loop", "interact.audio_mix")),\n''',
)

# The generic missing-contract tests need a genuinely still-missing capability.
replace_once(
    "backend/tests/test_forge_020a3b_partial_is_not_success.py",
    '''MISSING_NEED = "植物を育てながら音を組み合わせるゲームを作りたい"\n''',
    '''MISSING_NEED = "釣った場所を地図に残して魚の種類を記録したい"\n''',
)
replace_once(
    "backend/tests/test_forge_020a3b_partial_is_not_success.py",
    '''        self.assertIn("unsupported:effect.media_compose", record.capabilities)\n        self.assertNotIn("effect.media_compose", record.capabilities)\n''',
    '''        self.assertIn("unsupported:view.map", record.capabilities)\n        self.assertNotIn("view.map", record.capabilities)\n''',
)
replace_once(
    "backend/tests/test_forge_020a3b_partial_is_not_success.py",
    '''        media = next(\n            u for u in record.capability_usage if u.capability_id == "effect.media_compose"\n        )\n        self.assertTrue(media.requested)\n        self.assertFalse(media.used)\n        self.assertIs(media.status, CapabilityUsageStatus.MISSING)\n''',
    '''        missing_view = next(\n            u for u in record.capability_usage if u.capability_id == "view.map"\n        )\n        self.assertTrue(missing_view.requested)\n        self.assertFalse(missing_view.used)\n        self.assertIs(missing_view.status, CapabilityUsageStatus.MISSING)\n''',
)

# Golden game evidence now records simulation success + partial local audio mixing.
replace_once(
    "backend/tests/test_forge_qg_v2_r4_capability_planning.py",
    '''        self.assertIn("simulate.loop", record.capabilities)\n        self.assertIn("unsupported:effect.media_compose", record.capabilities)\n''',
    '''        self.assertIn("simulate.loop", record.capabilities)\n        self.assertIn("partial:interact.audio_mix", record.capabilities)\n        self.assertNotIn("unsupported:effect.media_compose", record.capabilities)\n''',
)

# Disclosure: the game no longer has a critical MISSING capability; it has a\n# truthful partial limitation until the real-browser audio probe is green.
replace_once(
    "backend/tests/test_forge_020a2_capability_disclosure.py",
    '''        self.assertNotIn("simulate.loop", gap["missing"])\n        self.assertIn("effect.media_compose", gap["missing"])\n''',
    '''        self.assertNotIn("simulate.loop", gap["missing"])\n        self.assertNotIn("effect.media_compose", gap["missing"])\n        self.assertIn("interact.audio_mix", gap["partial"])\n''',
)
replace_once(
    "backend/tests/test_forge_020a2_capability_disclosure.py",
    '''        self.assertNotIn("simulate.loop", missing)\n        self.assertIn("effect.media_compose", missing)\n''',
    '''        self.assertNotIn("simulate.loop", missing)\n        self.assertNotIn("effect.media_compose", missing)\n''',
)

# Old "game must block" expectation is no longer true at capability-gap level.\n# Quality/visual gates remain separate and may still block release readiness.
replace_once(
    "backend/tests/test_forge_020a2_capability_disclosure.py",
    '''    def test_a_game_is_not_release_ready(self) -> None:\n        result = _generate(self.client, GAME)\n        self.assertTrue(result["capability_gap"]["blocks_completion"])\n        self.assertFalse(result["quality"]["release_ready"])\n''',
    '''    def test_a_game_has_no_critical_capability_gap(self) -> None:\n        result = _generate(self.client, GAME)\n        self.assertFalse(result["capability_gap"]["blocks_completion"])\n''',
)
replace_once(
    "backend/tests/test_forge_020a2_capability_disclosure.py",
    '''    def test_the_reason_appears_in_required_fixes(self) -> None:\n        result = _generate(self.client, GAME)\n        joined = " ".join(result["quality"]["required_fixes"])\n        self.assertIn("まだ作れません", joined)\n''',
    '''    def test_partial_audio_mix_is_disclosed(self) -> None:\n        result = _generate(self.client, GAME)\n        gap = result["capability_gap"]\n        self.assertIn("interact.audio_mix", gap["partial"])\n        self.assertTrue(gap["message"].strip())\n''',
)
