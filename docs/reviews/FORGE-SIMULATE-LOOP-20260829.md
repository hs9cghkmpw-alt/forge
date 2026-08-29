# FORGE simulate.loop vertical slice checkpoint — 2026-08-29

## Scope

This checkpoint records the first production-shaped runtime path for semantic capability `simulate.loop`.

Implemented in commit `12ed096f389904809152f57786942849c49a07c1`:

- Forge Language v1.13 accepts `simulation_loop`.
- Backend production validator gates the widget to v1.13 and bounds `step_ms` / `max_ticks_per_advance`.
- Flutter `ForgeWidgetNode.fromJson` parses a real `ForgeSimulationLoopWidgetNode`.
- Default Widget Registry resolves `simulation_loop`.
- The lifecycle widget starts a periodic fixed-step scheduler, advances `ForgeSimulationBinding`, writes emitted ticks into an existing `number` state, and cancels the timer on dispose.
- Tests cover parser identity, timer-driven state advancement, disposal stop behavior, v1.13 acceptance, v1.12 rejection, and unsafe frequency rejection.

## Truth boundary

`simulate.loop` is **not yet declared IMPLEMENTED** in the semantic capability catalog at this checkpoint. That declaration must wait for CI on the production-shaped path and for the capability adapter/catalog mapping to be updated together.

The Golden Generated App Quality Gate remains FAIL independently of this runtime slice; `effect.media_compose` and broader game/media semantics remain unresolved.
