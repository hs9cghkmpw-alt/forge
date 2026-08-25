# FORGE-019 Semantic Design Revision + Visual Dev Loop v1 Report

## Baseline and reproduced gaps

- Branch `claude/forge-master-handoff-k46jns`; start HEAD `07bb8af6395d64a096c7298c226fafa61f6da0a6`; implementation/docs HEAD reviewed by CI `5646a2e224edd04e688f690d75ca0c9f5715802a`.
- Existing `/update` sent the complete document and raw request to a provider for full rewrite. It had no typed target resolution, artifact/version check, Critic, RevisionRecord, or REVISION Learning Event production write.
- Flutter discarded artifact capability and had no explicit accepted/correction controls. Evaluation decisions lacked complete policy context. No repeatable screenshot capture or visual completion rule existed.

## Architecture and implementation

- Natural language chooses intent; Forge alone resolves semantic identity to screen/widget IDs. Arbitrary JSON paths are rejected.
- The closed operation layer produces `SelectPrimaryMetric` in v1 and defines an extensible operation vocabulary. Local patching deep-copies the document, promotes the resolved target, demotes the old screen-local primary, and leaves unrelated subtrees canonically equal.
- `AMBIGUOUS` and `NEEDS_CLARIFICATION` fail closed. Only `UNSUPPORTED` can use explicit `FULL_REGEN_FALLBACK`.
- `/update` checks artifact/version, runs Validator and Semantic Design Critic, appends CORRECTED feedback and RevisionRecord, emits REVISION LearningEvent, rotates the version token, and returns the new document/capability.
- RevisionRecord stores mode, operation/target role facts, Validator/Critic results, language version, and visual manifest reference—never raw utterance.
- `EvaluationContextSnapshot` captures scope, residency, contribution target, app trust/reference, training use, provider terms, and consent/privacy/sanitizer/export/training policy versions without content or capability handles.
- Flutter domain/parser preserves artifact identity. Forge Host buttons post ACCEPTED or submit correction to `/update`; opening/cancelling the correction dialog creates no CORRECTED event.

## Production path and measured evidence

The HTTP E2E creates GenerationRecord/capability, posts `/update`, receives the typed local patch and rotated capability, and verifies stale-token 422. Isolated measured counts: RevisionRecord 1, REVISION LearningEvent 1, Feedback LearningEvent 1. Operation: `select_primary_metric`; target `home/balance`; role `metric.secondary → metric.primary`; Validator PASS; Critic PASS; runtime outcome honestly `UNKNOWN`.

## Visual Dev Loop

- Live preview: `scripts/start_dev.ps1`.
- Capture: `scripts/capture_forge_019_visual.ps1`; route `/?state=before|after`; viewport 390×844.
- Before: income 320,000円 is primary. After: balance 447,000円 is primary and income uses `finance.income`.
- Codex opened both PNGs. No overlap, overflow, clipping, broken alignment, or unusable mobile controls were found. Expense, headings, transaction rows, order, and spacing remain unchanged.
- Initial screenshots were rejected because one was blank and one rendered the error screen. A production parser test exposed invalid fixture structure; the fixture was fixed and recaptured.

## Regression and intentional break

- Backend full: 1,448 passed, 17 skipped in 27.118s with `FORGE_DEFAULT_PROVIDER=mock`.
- forge_ai full: 521 passed in 1.450s.
- Flutter full: 510 passed. Analyze PASS. Production `flutter build web` PASS.
- Visual parser/equality: 2 passed. Existing Golden Finance, `/generate`, `/converse`, `/feedback`, and renderer regressions are included in full runs.
- An initial backend run without explicitly pinning the test-only mock provider produced 8 provider-unavailable failures; it is not reported as PASS.
- Fifteen in-memory mutation guards cover all requested boundaries. A source-level mutation changed `残高 → balance` to `残高 → income`; the target test failed as expected. It was restored and 20 focused tests passed.

## Privacy, consent, learning, and Local AI

No raw correction utterance is stored in LearningEvent/RevisionRecord. ArtifactHandle/version token never enter learning lineage. Semantic-corrections consent remains required; usage-statistics consent cannot export REVISION. Screenshots are not uploaded or training data. Real Local Model runs: 0.

## CI, risk, and unverified work

GitHub Actions run `32811724667` completed successfully for `5646a2e`: Python 3.11, Python 3.12, backend smoke, and Flutter all passed. https://github.com/hs9cghkmpw-alt/forge/actions/runs/32811724667

- Browser capture and HTTP update are production-backed but not yet one browser automation transaction.
- There is no authenticated preview callback, so RevisionRecord runtime outcome remains UNKNOWN.
- Full fallback evidence remains less rich than local-patch evidence.
- Durable evidence/outbox, Auth, RLS, server identity, Supabase Learning tables, and cloud network export remain unimplemented.

## Next

After independent GO: FORGE-020 Real Local Model Runtime + Benchmark / Local Promotion v1. If review finds a blocking issue, perform FORGE-019A hardening first.
