import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_simulation.dart';

void main() {
  group('ForgeSimulationEngine', () {
    test('does not advance while paused', () {
      const engine = ForgeSimulationEngine(step: Duration(milliseconds: 100));
      const state = ForgeSimulationState();

      final next = engine.advance(state, const Duration(seconds: 3));

      expect(next.tick, 0);
      expect(next.elapsed, Duration.zero);
      expect(next.running, isFalse);
    });

    test('converts elapsed time into deterministic fixed ticks', () {
      const engine = ForgeSimulationEngine(step: Duration(milliseconds: 100));
      final started = engine.start(const ForgeSimulationState());

      final first = engine.advance(started, const Duration(milliseconds: 250));
      expect(first.tick, 2);
      expect(first.elapsed, const Duration(milliseconds: 50));

      final second = engine.advance(first, const Duration(milliseconds: 50));
      expect(second.tick, 3);
      expect(second.elapsed, Duration.zero);
    });

    test('same trajectory always produces same state', () {
      const engine = ForgeSimulationEngine(step: Duration(milliseconds: 125));

      ForgeSimulationState replay() {
        var state = engine.start(const ForgeSimulationState());
        for (final delta in <Duration>[
          const Duration(milliseconds: 80),
          const Duration(milliseconds: 170),
          const Duration(milliseconds: 375),
        ]) {
          state = engine.advance(state, delta);
        }
        return state;
      }

      final a = replay();
      final b = replay();
      expect(a.tick, b.tick);
      expect(a.elapsed, b.elapsed);
      expect(a.running, b.running);
    });

    test('caps catch-up work per advance to avoid runaway frame stalls', () {
      const engine = ForgeSimulationEngine(
        step: Duration(milliseconds: 100),
        maxTicksPerAdvance: 5,
      );
      final started = engine.start(const ForgeSimulationState());

      final next = engine.advance(started, const Duration(seconds: 10));

      expect(next.tick, 5);
      expect(next.elapsed, const Duration(milliseconds: 9500));
    });

    test('pause and reset are explicit state transitions', () {
      const engine = ForgeSimulationEngine(step: Duration(milliseconds: 100));
      var state = engine.start(const ForgeSimulationState());
      state = engine.advance(state, const Duration(milliseconds: 300));
      state = engine.pause(state);

      expect(state.tick, 3);
      expect(state.running, isFalse);

      final reset = engine.reset();
      expect(reset.tick, 0);
      expect(reset.elapsed, Duration.zero);
      expect(reset.running, isFalse);
    });
  });
}
