# FORGE CURRENT STATE

**Mutable operational snapshot — update whenever the real repository state changes.**  
**Constitution:** `docs/FORGE-CORE-CONSTITUTION.md`  
**Detailed product authority:** `docs/PRODUCT-DIRECTION.md`  
**Operational handoff:** `docs/HANDOFF.md`

Last reviewed against GitHub HEAD: **2026-08-29**

---

## 1. Repository / branch

- Repository: `hs9cghkmpw-alt/forge`
- Active/default branch at review time: `claude/forge-master-handoff-k46jns`
- Reviewed HEAD: `af66546b8ecb80b810daf489b15ae3816bdb39e2`
- Latest reviewed commit: `docs: record simulation loop vertical slice checkpoint`

This file is not a replacement for Git history, CI, evidence JSON, or `docs/HANDOFF.md`. It is a compact map of the current state so agents do not confuse old chat context with current repository facts.

---

## 2. Product direction — current canonical interpretation

Forge currently advances **two inseparable product axes**:

1. **Generated App Quality** — generated software must become beautiful, coherent, natural, practical, and publicly presentable rather than merely “AI UI that runs.”
2. **Forge-owned Local AI** — Forge must accumulate its own knowledge, retrieval, tools, episodes, evidence, datasets, evaluators, training/promotion history and progressively increase the task envelope handled locally without lowering the product bar.

These are one closed loop, not separate roadmaps:

```text
User Need
  ↓
Forge / Local Intelligence
  ↓
Capability + Design Language
  ↓
Forge Language
  ↓
Validator / Runtime
  ↓
Rendered / Running Software
  ↓
User + Runtime + Visual Evidence
  ↓
Experience / Dataset Candidate / Knowledge
  ↓
RAG / Training / Benchmark / Promotion
  ↓
Improved Local Capability
```

Golden Apps are quality bars, **not templates to copy**.

---

## 3. Generative-software boundary

Forge must not end as a finite Widget/Template Builder.

Target direction:

```text
Need
 → software architecture
 → capability decomposition
 → reuse existing capability
 → identify/synthesize missing capability under gates
 → generated logic/state/data
 → build
 → test
 → run
 → visual/runtime evaluation
 → repair
 → usable software
```

Capability identity is compositional. Structure mode, entity/fields, views, interactions, effects/runtime behavior, and support state are independent axes.

Adding a genre-specific widget/template is not evidence of improved novel-generation ability.

---

## 4. Local / Native Intelligence direction

The target is **not** “a local model returned one response.”

Long-term Forge Local Intelligence is the combination of:

- replaceable open-weight base model,
- Forge Knowledge / RAG,
- memory,
- tool use,
- web/browser research under trust boundaries,
- compiler/build/test/runtime/visual inspection,
- Generation Episodes,
- evaluators,
- reusable skills/capabilities,
- dataset pipeline,
- training / LoRA / adapters,
- benchmark,
- promotion / rollback.

The intended loop is:

```text
think → research → plan → build → run → inspect → repair → learn
```

Teacher/cloud output remains a **candidate**, never truth. Observable evidence decides quality.

---

## 5. Real Local-Agent evidence already proven

### FORGE-020B

A genuine GitHub-hosted run used a real Ollama runtime and real `qwen2.5:7b-instruct` model through Forge’s production generation path in agent verification mode.

- GitHub-hosted real-agent run: `33227448429` — **PASS**
- Durable evidence: `docs/evidence/agent020b/agent020b-20260829-015345.json`
- Physical/user-PC execution: **UNVERIFIED / NOT YET EXECUTED**

This proves a real Local Model can produce a bounded agent tool plan and Forge can execute the selected read-only tools through the production Agent path. It does **not** prove full autonomous build/test/runtime/visual repair by the model.

---

## 6. Objective generated-app verification / repair evidence already proven

### FORGE-020D / 020E

Forge has objective generated-artifact workspace materialization and command observation. A clean GitHub-hosted runner demonstrated:

```text
injected generated Flutter test failure
  ↓
objective failure observation
  ↓
one bounded Forge-side repair
  ↓
re-run verifier
  ↓
test PASS
  ↓
build PASS
  ↓
runtime PASS
```

Evidence:

- Run: `33236863659` — **SUCCESS / PASS**
- Durable evidence: `docs/evidence/agent020d/forge-020d-real-evidence-20260829.json`
- Initial test: `failed`
- Final test: `passed`
- Final build: `passed`
- Final runtime: `passed`
- Final visual: `unknown`
- Repair rounds: `1`
- `repair_succeeded=true`

Important boundary: this was a bounded trusted Forge-side repair. It is **not** evidence that the Local Model autonomously diagnosed and selected the repair.

---

## 7. Golden Generated App Quality Gate

**CURRENT STATUS: FAIL**

Do not rewrite this as PASS because build/test/runtime passed in another episode.

The real repair episode left visual quality as `unknown`, and the latest Golden Generated App visual/behavioral quality evidence has not been superseded by a genuine passing rerun.

Current priority is therefore not merely “more tests”; it is closing real semantic/runtime capability gaps and then performing genuine runtime + visual quality reruns.

---

## 8. Simulation/runtime capability — latest vertical slice

The current branch now contains and documents a reusable deterministic simulation vertical slice through Forge’s normal runtime/validation surface.

Progress includes:

- deterministic simulation runtime primitive,
- integer-safe tick arithmetic,
- runtime-safe simulation construction,
- simulation bound into existing Forge runtime numeric state,
- persistence/pause/reset semantics tests,
- backend validator support for the simulation-loop document shape,
- Forge Document schema and widget-registry/runtime wiring,
- frontend tests that prove simulation state flows through the existing Forge state/runtime path,
- a committed checkpoint documenting the vertical slice at HEAD `af66546b8ecb80b810daf489b15ae3816bdb39e2`.

Key integration commit immediately before the checkpoint:

- `12ed096f389904809152f57786942849c49a07c1` — `forge-golden: wire simulation loop through runtime and validator`

This is material progress toward reusable simulation semantics and is preferable to adding a genre-specific game widget/template.

It is still **not** proof that all simulation/game/media requests are supported, that visual quality is good, or that the Golden Generated App Quality Gate has passed.

---

## 9. Current unverified / incomplete boundaries

Do not claim these as complete without new evidence:

- Physical/user-PC 020B Local-Agent execution
- Genuine visual PASS for the current generated Golden App gate
- Local model autonomously diagnosing and selecting a successful repair
- Complete production API exposure of all internal build/test/runtime/repair evidence
- Broad generative-software support for simulation/media/game semantics beyond the newly wired primitive
- Self-extension that safely synthesizes missing capabilities and promotes them after repeated evidence
- Broad local-model promotion: Local Promotion remains evidence-gated, not assumed
- Any benchmark axis that is unmeasured should remain `unsupported` or `unknown`, not fake zero/PASS

---

## 10. Current next-work direction

Order of attack should preserve the Product Direction closed loop:

1. **Continue closing semantic/runtime capability gaps** with reusable capabilities, not genre templates.
2. **Keep every new capability on the production generation/validator/runtime path**, with tests that fail when wiring is removed.
3. **Run objective generated-artifact verification** (validator/build/test/runtime) on representative Golden/novel tasks.
4. **Run genuine visual/behavioral review** and keep the Golden Gate FAIL until it passes.
5. **Preserve Generation Episode / evidence lineage** for both successes and repairs.
6. **Use accepted, rights-cleared, evidence-backed episodes** as Knowledge/Dataset candidates.
7. **Improve Local Intelligence / agent diagnosis and controlled repair selection** without weakening verifier boundaries.
8. **Promote Local routing only when held-out evidence meets the product bar.**

---

## 11. Agent read order

Before doing Forge work, read in this order:

1. `docs/FORGE-CORE-CONSTITUTION.md`
2. `docs/PRODUCT-DIRECTION.md`
3. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
4. `docs/LEARNABLE-LOCAL-AI-VISION.md`
5. `docs/FORGE-CURRENT-STATE.md`
6. `docs/HANDOFF.md`
7. `AGENTS.md`
8. `CLAUDE.md` when using Claude Code
9. relevant Architecture / Spec / report / evidence
10. latest GitHub HEAD / diff / CI

If this CURRENT STATE disagrees with newer GitHub evidence, **newer evidence wins** and this file must be updated in the same task.

---

## 12. State-management rule

`FORGE-CORE-CONSTITUTION.md` changes only through CEO-approved Constitution Change Proposal.

`FORGE-CURRENT-STATE.md` is deliberately mutable and should change whenever the real implementation/evidence state changes.

This separation prevents two recurring failures:

- freezing temporary architecture as eternal product truth,
- carrying stale chat-era facts forward after the repository has moved on.
