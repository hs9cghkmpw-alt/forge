library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../runtime/forge_simulation.dart';
import '../runtime/forge_simulation_binding.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

void registerV1_13Widgets(ForgeWidgetRegistry registry) {
  registry.register('simulation_loop', _buildSimulationLoop);
}

Widget _buildSimulationLoop(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  return _ForgeSimulationLoop(
    node: node as ForgeSimulationLoopWidgetNode,
    runtimeState: state,
  );
}

/// Lifecycle owner for the deterministic simulation primitive.
///
/// Wall-clock scheduling is intentionally kept at this edge. Each timer callback
/// advances the pure engine by exactly one declared fixed step, so replay tests can
/// drive the same binding with the same deltas without depending on wall-clock time.
class _ForgeSimulationLoop extends StatefulWidget {
  final ForgeSimulationLoopWidgetNode node;
  final ForgeRuntimeState runtimeState;

  const _ForgeSimulationLoop({required this.node, required this.runtimeState});

  @override
  State<_ForgeSimulationLoop> createState() => _ForgeSimulationLoopState();
}

class _ForgeSimulationLoopState extends State<_ForgeSimulationLoop> {
  Timer? _timer;
  late ForgeSimulationBinding _binding;

  Duration get _step => Duration(milliseconds: widget.node.stepMilliseconds);

  @override
  void initState() {
    super.initState();
    _bindAndStart();
  }

  void _bindAndStart() {
    _binding = ForgeSimulationBinding(
      runtimeState: widget.runtimeState,
      stateRef: widget.node.stateRef,
      engine: ForgeSimulationEngine(
        step: _step,
        maxTicksPerAdvance: widget.node.maxTicksPerAdvance,
      ),
    );
    _binding.start();
    _timer = Timer.periodic(_step, (_) => _binding.advance(_step));
  }

  @override
  void didUpdateWidget(covariant _ForgeSimulationLoop oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtimeState != widget.runtimeState ||
        oldWidget.node.stateRef != widget.node.stateRef ||
        oldWidget.node.stepMilliseconds != widget.node.stepMilliseconds ||
        oldWidget.node.maxTicksPerAdvance != widget.node.maxTicksPerAdvance) {
      _timer?.cancel();
      _binding.pause();
      _bindAndStart();
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _binding.pause();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Behavior-only node: state changes are consumed by ordinary Forge widgets.
    return SizedBox.shrink(key: ValueKey('simulation_loop_${widget.node.id}'));
  }
}
