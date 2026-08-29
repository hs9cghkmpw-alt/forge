library;

import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

void registerV1_15Widgets(ForgeWidgetRegistry registry) {
  registry.register('simulation_progress', _buildSimulationProgress);
}

Widget _buildSimulationProgress(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeSimulationProgressWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final tick = state.getNumber(n.stateRef).floor().clamp(0, 1 << 30);
      final rawStage = tick ~/ n.ticksPerStage;
      final stageIndex = rawStage.clamp(0, n.stages.length - 1);
      final stage = n.stages[stageIndex];
      final terminal = stageIndex == n.stages.length - 1;
      final within = tick % n.ticksPerStage;
      final progress = terminal ? 1.0 : within / n.ticksPerStage;
      return Card(
        key: const ValueKey('simulation_progress'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(n.title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text(stage, key: const ValueKey('simulation_stage'),
                   style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 10),
              LinearProgressIndicator(
                key: const ValueKey('simulation_stage_progress'),
                value: progress.clamp(0.0, 1.0),
              ),
            ],
          ),
        ),
      );
    },
  );
}
