# FORGE-020A4 — LEVEL0 PREFLIGHT GUARD

- Date: 2026-08-28
- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD reviewed: `949ccb699a6a68cc3614e3acb9ed60a9595c3545`
- Implementation agent: ChatGPT
- Previous task: `FORGE-020A3B / CLOSEOUT-INTEGRITY-AND-CI-RECOVERY`

## 1. Independent review of 020A3B

`949ccb6` and GitHub Actions run `33065820365` were independently checked before
starting this task. The run completed **success**. 020A3B materially closed the earlier
false-PASS hole by requiring structure source, provider and task independently for Level 0;
it also stopped unknown Capability IDs from silently becoming MISSING and prevented PARTIAL
capabilities from being recorded as full successes.

`Real Local Model runs` remains **0**. No real model was executed in this task.

## 2. Remaining operational hole found

`verify_local_model_level0.py` already checked `domain_resolution` before spending a real
model call, but that is not sufficient.

A Need can be `domain_resolution=generated` and still fail to measure Local structure
generation because:

1. a deterministic Capability Plan makes the software structure before the model;
2. Entity Synthesis is attempted but rejected and a fallback wins;
3. the expected structure task/provider was not actually observed.

The previous real Qwen runs demonstrated this class of failure: HTTP 200 and Validator PASS
can still end as `INVALID_PROBE` when the Local Model did not own the structure.

For a CPU-only 7B model this can waste minutes per attempt. The verifier was strict enough
**after** the run, but did not provide a cheap typed diagnostic before the run.

## 3. Implemented: typed Level 0 Probe Preflight

Added:

- `backend/app/ai/gateway/level0_preflight.py`
- `scripts/preflight_local_model_level0.py`
- `backend/tests/test_forge_020a4_level0_preflight.py`
- `docs/evidence/level0-preflight/README.md`

The command:

```text
python scripts/preflight_local_model_level0.py
```

runs production `/api/v1/ai/generate` with `provider=mock`, then evaluates typed production
Evidence. It never imports or writes `RealLocalModelRunLog`.

`ELIGIBLE_FOR_REAL_RUN` is intentionally strict. The control facts must show:

- `domain_resolution=generated`
- `structure_source=AI_ENTITY_SYNTHESIS`
- `structure_provider=TEST_DOUBLE`
- `structure_task=ForgeTask.ENTITY_SYNTHESIS.value`
- AIRouter observation includes `ENTITY_SYNTHESIS`
- Entity Synthesis was attempted **and accepted**
- production `GenerationRecord.uid` exists
- Validator passed

This means only:

> production control flow demonstrably gave software-structure work to Entity Synthesis in
> the control run.

It does **not** mean Local Model success. It does **not** increment Real Local Model runs.

## 4. Failure taxonomy / diagnostic ordering

Preflight outcomes:

- `eligible_for_real_run`
- `curated_bypass`
- `deterministic_bypass`
- `synthesis_rejected`
- `wrong_provider`
- `wrong_task`
- `validation_failed`
- `unobservable`

The first CI run exposed an important ordering bug in the new evaluator. A generated-domain
request attempted Entity Synthesis, was rejected, and then used a fallback. Looking only at
the final fallback classified it as `deterministic_bypass`, hiding the actual cause.

The evaluator now prioritizes an **observed synthesis rejection** over the later fallback and
reports the closed rejection reason. Curated domains that never reach synthesis remain
`curated_bypass`.

No model raw output, prompt or generated document body is stored in typed preflight results.

## 5. What the first production CI run actually discovered

The initial integration test expected the existing default probe
`盆栽の水やりの記録をつけたい` to be eligible. That expectation was wrong.
GitHub CI correctly failed instead of being weakened to satisfy it.

Observed typed facts from the production `/generate` + `provider=mock` control run:

```text
domain_resolution: generated
structure_source: curated
structure_provider: none
structure_task: entity_synthesis_fallback
observed_tasks: [cognitive_stage]
validator_passed: true
generation_evidence_uid: present
entity_synthesis_attempted: true
entity_synthesis_accepted: false
entity_synthesis_rejection_reason: no_valid_fields
```

The test was changed to preserve this **current production fact**, not to fake eligibility.

### Blocker A — MockLLMAdapter nested structured output

`forge_ai_provider_bridge.py` gives the Entity Synthesis stage a proper schema where
`fields` is `array<object>`. The backend `MockLLMAdapter` currently handles generic arrays by
returning a list of words/strings. `EntitySynthesizer` therefore receives no valid Field
objects and rejects the response as `no_valid_fields`.

This is a **Test Double fidelity gap**, not evidence that a real Local Model cannot perform
Entity Synthesis. The preflight currently has false-negative risk until the production Mock
adapter can satisfy nested structured schemas generically.

Do not solve this with a bonsai/game/domain-specific response. The right fix is a generic,
schema-driven nested object/array synthesis path in `MockLLMAdapter`, with regression tests
against `_RESPONSE_SCHEMAS["entity_synthesis"]`.

### Blocker B — AIRouter task attribution is still pipeline-wide

The production `PromptPipeline` currently binds the AIRouter once as
`ForgeTask.COGNITIVE_STAGE` and passes that bound adapter through the whole Cognitive
Pipeline. Therefore even an Entity Synthesis AI call is recorded in Experience as
`cognitive_stage`, not `entity_synthesis`.

This means the strict 020A3B Level 0 condition
`ENTITY_SYNTHESIS must be actually observed` cannot currently be satisfied by the real
production route. A unit-constructed `RealLocalModelRun` can pass, but production task
attribution is not yet wired at stage granularity.

**Do not weaken the Level 0 rule back to COGNITIVE_STAGE.** The next fix should make the
Bridge/Router task-aware so that `Prompt.stage == entity_synthesis` routes through
`ForgeTask.ENTITY_SYNTHESIS`, while other stages retain their truthful task identity.
Every AI call must still go through `AIRouter.generate`; no direct Provider bypass.

## 6. Tests / mutation guards

The new tests guard:

- a fully evidenced control fact set can be eligible in principle;
- curated probe cannot be eligible;
- deterministic structure cannot be eligible;
- synthesis rejection stays visible and carries the closed reason code;
- synthesis rejection is not hidden by a later fallback;
- CLOUD or LOCAL cannot masquerade as the Test Double control provider;
- `ENTITY_SYNTHESIS` task must be both attributed and observed for eligibility;
- lookalike task strings do not pass;
- missing Generation Evidence UID does not pass;
- Validator failure does not pass;
- serialized typed preflight result has no Need/raw-output/prompt field;
- the current default probe is fixed as `synthesis_rejected/no_valid_fields`, not fake PASS;
- the current production Experience fact (`cognitive_stage` only) is captured as a blocker;
- the household-budget Curated trap remains rejected.

The initial 020A4 CI failed exactly one new test because the test assumed eligibility.
After correcting the test to assert the measured production facts, a new CI run was started.
Final all-green run must be recorded before this report is considered closed.

## 7. Additional Evidence serialization debt

`GenerationRecord` contains:

- `entity_synthesis_attempted`
- `entity_synthesis_accepted`
- `entity_synthesis_rejection_reason`

but the currently reviewed `GenerationRecord.to_dict()` does **not** serialize those three
fields. The preflight JSON writes them explicitly so Level 0 diagnosis is not lost, but the
generic serializer gap remains.

Next implementation agent should re-check current HEAD and, if still true, add those closed,
privacy-safe fields to generic Evidence serialization with a regression test. Do not store
raw model output, prompt or user text while fixing it.

## 8. Product-direction check

This change does not add a Widget/template or narrow Forge generation. It improves the
measurement loop around Forge-owned Local AI:

`Need → production path → structure ownership Evidence → diagnose → real Local measurement`.

It also keeps Execution Host independence: the diagnostic can run without Ollama; actual
Level 0 remains bound to whichever environment currently has a real Local Runtime.

Mobile Product Direction is unchanged: Forge Client location and Execution Host location
remain independent.

## 9. Next implementation task — FORGE-020A4B

**Do not run another official real Level 0 attempt yet.** First close both production
blockers above.

Recipe for the next agent:

1. **Schema-faithful Mock structured output**
   - inspect `backend/app/ai/foundation/providers.py::MockLLMAdapter`;
   - add generic recursive synthesis for `array<object>` / `object.properties` and enum;
   - keep existing specialized UX behavior (`screens`, `example_items`, etc.) where needed;
   - no Need/domain-specific entity templates;
   - prove the Entity Synthesis response schema yields at least one valid Field object.

2. **Stage-aware AIRouter attribution**
   - keep `AIRouter.generate` as the only AI execution exit;
   - map structured `Prompt.stage` to `ForgeTask` before the call is recorded;
   - `entity_synthesis → ForgeTask.ENTITY_SYNTHESIS` is mandatory;
   - do not parse the flattened prompt string to guess the task if the structured Prompt is
     still available at the Bridge boundary;
   - preserve all Experience refs so final Validator outcome can still be attached.

3. **Production E2E**
   - rerun the default probe through `/generate` + Test Double;
   - require `AI_ENTITY_SYNTHESIS`, `TEST_DOUBLE`, structure task `entity_synthesis`,
     observed `ENTITY_SYNTHESIS`, accepted synthesis, UID, Validator PASS;
   - only then may preflight return `eligible_for_real_run`.

4. **Mutation**
   - nested fields → strings must fail;
   - remove stage→task mapping must fail;
   - route entity synthesis as `COGNITIVE_STAGE` must fail;
   - bypass AIRouter must fail;
   - provider CLOUD/LOCAL in preflight control must fail.

5. **Then** move to the Runtime-capable PC:
   - `python scripts/forge_doctor.py`
   - `python scripts/preflight_local_model_level0.py`
   - only if eligible, configure Qwen/Ollama and run
     `python scripts/verify_local_model_level0.py`.

Only an actual strict Level 0 PASS may change `Real Local Model runs` from 0 to 1.
If it fails/rejects, keep 0 and fix the observed reason; never loosen the gate.

After Level 0 passes and is independently reviewed, proceed to 020B Tool-Using Local Agent
production wiring.
