import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/runtime/forge_simulation.dart';
import 'package:forge_app/json_ui/runtime/forge_simulation_binding.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  group('ForgeSimulationBinding', () {
    test('writes deterministic ticks into existing number state', () {
      final runtime = ForgeRuntimeState({
        'ticks': const ForgeNumberState(0),
      });
      final binding = ForgeSimulationBinding(
        runtimeState: runtime,
        stateRef: 'ticks',
        engine: ForgeSimulationEngine(
          step: const Duration(milliseconds: 100),
        ),
      );

      binding.start();
      binding.advance(const Duration(milliseconds: 250));

      expect(runtime.getNumber('ticks'), 2);
      expect(binding.simulation.elapsed, const Duration(milliseconds: 50));
    });

    test('starts from persisted numeric tick state', () {
      final runtime = ForgeRuntimeState({
        'ticks': const ForgeNumberState(7),
      });
      final binding = ForgeSimulationBinding(
        runtimeState: runtime,
        stateRef: 'ticks',
        engine: ForgeSimulationEngine(
          step: const Duration(milliseconds: 100),
        ),
      );

      binding.start();
      binding.advance(const Duration(milliseconds: 100));

      expect(runtime.getNumber('ticks'), 8);
    });

    test('paused binding does not mutate runtime state', () {
      final runtime = ForgeRuntimeState({
        'ticks': const ForgeNumberState(3),
      });
      final binding = ForgeSimulationBinding(
        runtimeState: runtime,
        stateRef: 'ticks',
        engine: ForgeSimulationEngine(
          step: const Duration(milliseconds: 100),
        ),
      );

      binding.advance(const Duration(seconds: 1));

      expect(runtime.getNumber('ticks'), 3);
      expect(binding.simulation.tick, 3);
    });

    test('reset clears both simulation and runtime tick state', () {
      final runtime = ForgeRuntimeState({
        'ticks': const ForgeNumberState(4),
      });
      final binding = ForgeSimulationBinding(
        runtimeState: runtime,
        stateRef: 'ticks',
      );

      binding.start();
      binding.reset();

      expect(runtime.getNumber('ticks'), 0);
      expect(binding.simulation.tick, 0);
      expect(binding.simulation.running, isFalse);
    });
  });
}
