# Forge Handoff

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `07bb8af6395d64a096c7298c226fafa61f6da0a6`
- Final implementation/docs HEAD reviewed by CI: `5646a2e224edd04e688f690d75ca0c9f5715802a`
- Current phase: R1 Generated App Quality / Growing AI
- Current task: FORGE-019 Semantic Design Revision + Visual Dev Loop v1 — implementation complete, CI review pending

## Implemented

- Added a closed typed semantic-operation layer and Forge-owned `TargetResolver`.
- Production `/update` resolves 「残高をもっと目立たせて」 to `select_primary_metric`, performs a deep-copy local patch, and runs Forge Validator plus Semantic Design Critic.
- Added optimistic concurrency with frontend-held artifact capability and rotating version token. Old tokens fail closed.
- `/update` records CORRECTED feedback, a structured `RevisionRecord`, and a local `REVISION` Learning Event. Artifact handles never enter Learning Events.
- Added privacy-safe `EvaluationContextSnapshot` with consent/privacy/sanitizer/export/training policy lineage.
- Flutter preserves artifact identity and Forge Host exposes 「これでOK」「直したい」. Correction is recorded only after request submission.
- Added one-command dev startup, deterministic visual capture, Golden Finance Before/After images, and the permanent AGENTS visual-review rule.

## Production wiring

`Flutter Host → artifact/version → POST /update → TargetResolver → SelectPrimaryMetric → local patch → Validator → Semantic Design Critic → RevisionEvidenceStore.record → REVISION LearningEvent → CORRECTED FeedbackEvent → rotated artifact token → Flutter render`.

Full-regeneration remains an explicit fallback only for unsupported semantic intents. Ambiguous and missing targets fail closed instead of guessing.

## Tests and evidence

- Backend: 1,448 passed, 17 skipped (`FORGE_DEFAULT_PROVIDER=mock`).
- forge_ai: 521 passed.
- Flutter: 510 passed.
- `flutter analyze`: PASS, no issues.
- `flutter build web`: PASS.
- Golden Finance screenshots: 390×844, inspected by Codex; no overlap, clipping, overflow, or broken alignment. Balance becomes the largest metric while unrelated content stays unchanged.
- Mutation guards: 15/15 passed. A real temporary resolver miswiring produced the expected FAIL, was restored, then 20 focused tests passed.

## Intentional break / mutation

The resolver mapping was intentionally changed from `残高 → balance` to `残高 → income`. The primary-target test failed (`metric.secondary != metric.primary`). The source was restored and all focused tests passed. Fifteen named guards cover resolver bypass, full rebuild, wrong target, stale token, Revision/Learning wiring, consent, privacy, evaluation lineage, visual capture, before/after difference, unrelated subtree, Validator, Critic, and AGENTS protocol.

## CI

GitHub Actions run `32811724667` for `5646a2e` completed successfully: backend smoke, backend + forge_ai Python 3.11, backend + forge_ai Python 3.12, and Flutter were all green. Run: https://github.com/hs9cghkmpw-alt/forge/actions/runs/32811724667

## Unverified / Technical Debt

- Browser capture renders the real production Flutter renderer but does not yet drive live `/update` and capture its response in the same browser automation session.
- Runtime outcome remains `UNKNOWN`; screenshots prove the curated visual scenario rendered, but there is no authenticated runtime callback binding that fact to the RevisionRecord.
- Artifact registry/evidence/outbox are still process memory. Auth, subject binding, RLS, server-issued contributor identity, durable outbox, Supabase Learning tables, and cloud network export remain unimplemented.
- Full-regeneration fallback does not yet create the richer FORGE-019 RevisionRecord fields.
- Actual open-weight Local Model runs remain 0.

## Next task

FORGE-020 — Real Local Model Runtime + Benchmark / Local Promotion v1, unless independent review finds a blocking FORGE-019 hardening issue.

## Next three moves

1. Independent review of the pushed HEAD, diff, production E2E, screenshots, tests, and CI.
2. Harden the visual runner into a browser-driven `/update → render → feedback` scenario and add runtime-result acknowledgement.
3. Start FORGE-020 only after FORGE-019 receives GO.
