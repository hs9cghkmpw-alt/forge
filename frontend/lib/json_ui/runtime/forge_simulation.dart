/// Deterministic simulation primitive for Forge-generated apps.
///
/// This is the first runtime substrate for semantic capability `simulate.loop`.
/// It deliberately contains no Flutter timer and no rendering concerns: callers
/// provide elapsed time explicitly, making behavior deterministic, testable and
/// replayable inside Generation Episodes.
library;

/// Immutable state for a bounded fixed-step simulation.
class ForgeSimulationState {
  final int tick;
  final Duration elapsed;
  final bool running;

  const ForgeSimulationState({
    this.tick = 0,
    this.elapsed = Duration.zero,
    this.running = false,
  });

  ForgeSimulationState copyWith({
    int? tick,
    Duration? elapsed,
    bool? running,
  }) {
    return ForgeSimulationState(
      tick: tick ?? this.tick,
      elapsed: elapsed ?? this.elapsed,
      running: running ?? this.running,
    );
  }
}

/// Pure fixed-step simulation engine.
///
/// The engine never reads wall-clock time. `advance()` accepts an observed elapsed
/// duration and converts it into discrete ticks. This avoids hidden timing state and
/// makes the same input trajectory replay to the same output trajectory.
class ForgeSimulationEngine {
  final Duration step;
  final int maxTicksPerAdvance;

  const ForgeSimulationEngine({
    this.step = const Duration(milliseconds: 250),
    this.maxTicksPerAdvance = 40,
  })  : assert(step > Duration.zero),
        assert(maxTicksPerAdvance > 0);

  ForgeSimulationState start(ForgeSimulationState state) =>
      state.copyWith(running: true);

  ForgeSimulationState pause(ForgeSimulationState state) =>
      state.copyWith(running: false);

  ForgeSimulationState reset() => const ForgeSimulationState();

  ForgeSimulationState advance(
    ForgeSimulationState state,
    Duration delta,
  ) {
    if (!state.running || delta <= Duration.zero) return state;

    final accumulated = state.elapsed + delta;
    final rawTicks = accumulated.inMicroseconds ~/ step.inMicroseconds;
    final emittedTicks = rawTicks.clamp(0, maxTicksPerAdvance);
    final consumed = step * emittedTicks;

    return ForgeSimulationState(
      tick: state.tick + emittedTicks,
      elapsed: accumulated - consumed,
      running: true,
    );
  }
}
