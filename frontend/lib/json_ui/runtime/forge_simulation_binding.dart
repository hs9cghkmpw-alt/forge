/// Runtime-state binding for Forge deterministic simulation.
///
/// The pure [ForgeSimulationEngine] owns simulation arithmetic; this binding only
/// connects its tick count to an existing numeric Forge state reference. It does
/// not schedule wall-clock work. A future `simulation_loop` widget may supply
/// observed frame/timer deltas, while tests and Generation Episodes can replay the
/// exact same deltas deterministically.
library;

import '../renderer/forge_runtime_state.dart';
import 'forge_simulation.dart';

class ForgeSimulationBinding {
  final ForgeRuntimeState runtimeState;
  final String stateRef;
  final ForgeSimulationEngine engine;

  ForgeSimulationState _simulation;

  ForgeSimulationBinding({
    required this.runtimeState,
    required this.stateRef,
    ForgeSimulationEngine? engine,
  })  : engine = engine ?? ForgeSimulationEngine(),
        _simulation = ForgeSimulationState(
          tick: runtimeState.getNumber(stateRef).toInt(),
        );

  ForgeSimulationState get simulation => _simulation;

  void start() {
    _simulation = engine.start(_simulation);
  }

  void pause() {
    _simulation = engine.pause(_simulation);
  }

  void reset() {
    _simulation = engine.reset();
    runtimeState.setNumber(stateRef, 0);
  }

  void advance(Duration delta) {
    final next = engine.advance(_simulation, delta);
    if (next.tick == _simulation.tick &&
        next.elapsed == _simulation.elapsed &&
        next.running == _simulation.running) {
      return;
    }
    _simulation = next;
    runtimeState.setNumber(stateRef, next.tick.toDouble());
  }
}
