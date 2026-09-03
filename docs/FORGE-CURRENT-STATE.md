# FORGE CURRENT STATE

**Mutable operational snapshot — update whenever the real repository state changes.**  
**Constitution:** `docs/FORGE-CORE-CONSTITUTION.md`  
**Detailed product authority:** `docs/PRODUCT-DIRECTION.md`  
**Operational handoff:** `docs/HANDOFF.md`

Last reviewed against GitHub code HEAD: **2026-09-04**

---

## 1. Repository / branch

- Repository: `hs9cghkmpw-alt/forge`
- Active/default branch at review time: `claude/forge-master-handoff-k46jns`
- Latest code HEAD reviewed before documentation-only checkpoint updates: `c2ec1529ce1c3eb97d456dc667a03cd1a3ee1ac7`
- Canonical CI for that code HEAD: run `33340554937` — **SUCCESS, 4/4 jobs**
- Physical-PC checkpoint: `docs/evidence/PHYSICAL-EXECUTION-CHECKPOINT-20260831.md`

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
- Physical/user-PC execution of this Local-Agent path: **UNVERIFIED**

This proves a real Local Model can produce a bounded agent tool plan and Forge can execute the selected read-only tools through the production Agent path. It does **not** prove full autonomous build/test/runtime/visual repair by the model, and it does not prove real-model authorship of a newly synthesized capability.

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

## 7. Self-extension — current proven boundary

Forge now has a production self-extension path that can:

- detect a Capability Gap,
- synthesize a build-time artifact through the production implementer,
- run real subprocess test/build/runtime-probe gates,
- refuse failed or unsafe artifacts,
- promote only verified artifacts,
- install the promoted capability,
- retry the original request,
- reuse the capability from a second different request without a second build.

Natural-language acquisition -> retry -> reuse is **PROVEN** using `view.calendar` as the unseen capability example. Compiler-side capability-name branching for widget emission is also removed; an acquired capability can register a document contribution and emit its widget through the production compiler path.

### 2026-09-01 — Real-hardware run: what passed, what failed

Measured on real hardware (Ollama + `qwen2.5:1.5b-instruct`), recorded without rounding:

| | |
|---|---|
| Frontend display / Frontend → Backend / Backend start / Ollama / real model | **PASS** |
| `/api/v1/ai/converse` with `provider=local` | **PASS** (HTTP 200, `simulated=false`) |
| Response time | **73.54s — FAIL** |
| Semantic judgement | **FAIL** |
| Chrome end to end | **FAIL** (Dio `receiveTimeout` was 10s) |

The semantic failure: for 「事務所の鍵を誰が持ち出していて、いつ返す予定か記録したい」
the engine treated who holds the key and when it returns as blocking unknowns and asked
back. Those are the **input fields of the tool being built**, not unknowns to resolve
before use.

Reading the code showed **reuse-first had never reached the product entry**.
`ConversationEngine.step()` built a large prompt and schema and called the model
unconditionally, before any decision. That call is the 73 seconds.

`backend/app/ai/runtime/conversation_fast_path.py` decides before that call whether
existing capabilities already cover the request, judging with what was already here
(`plan_capabilities` and `detect_risk_signals`) rather than a new classifier. Eight
conditions must all hold; anything else goes to the model as before.

Measured after: the same sentence takes **0.09ms with zero model calls and reaches
BUILD**. That number covers **only the ASK/BUILD decision**, not Forge's whole
request — what `PromptPipeline` costs is still unmeasured (TD98, TD102). Vague sentences still ASK and still cost a call; a missing capability is still
named. Guard-break 10/10 detected.

Still **UNPROVEN**:

- build-stage generation time on real hardware (**TD98**),
- Chrome driven end to end (**TD99**) — the wall should be gone, but it has not been watched,
- keyword-shaped comprehension gaps (**TD96**),
- **Real Local Model runs = 0** — this does not mean the local model is unused;
  the conversation path passed on real hardware. It counts how many times a real
  local model has carried a new capability all the way through generation,
  verification, installation and reuse (TD103).

Two CI failures during this work were **my own process mistakes, not the fast path**
(committing acquired artifacts, and placing a script in a job without its dependencies).
Both are now checked by tests rather than by memory (**TD100**, **TD101**).

Primary evidence: `docs/evidence/CONVERSATION-FAST-PATH-20260901.md`.
Canonical CI: run **33471061839** / head `d34ffd6` / 4 jobs green.

### 020F (2026-08-31) — Validator and Dart runtime, measured separately

Two previously unproven items are now **PROVEN**, each within a stated boundary:

- **Validator PASS for an acquired widget.** Only a capability that is PROMOTED, carries a loaded BUILD_TIME activation, and declares a document contribution may widen the accepted widget set (`backend/app/ai/validators/runtime_attested_widgets.py`). `requested` does not widen it, DECLARATIVE does not widen it, and the default is the empty set. 14 tests, 9 wiring breaks all detected. A real ordering bug was fixed: `WIDGET_TYPES_ALL` was consulted before `allowed_widgets`, so acquired types failed as `unknown_widget`.
- **Real Flutter widget-runtime rendering of an acquired widget.** The parser, not the widget registry, was the closed extension point (TD93, measured before it was fixed). `frontend/lib/json_ui/schema/acquired_widget_types.dart` opens it. Both a parser declaration and a registry builder are required; either alone renders nothing. 7 tests, 4 wiring breaks all detected.
- **Generated Dart survives a real `dart` build** (`dart run capability_test.dart` / `dart analyze .` / `dart run probe.dart`), enforced in CI's frontend job with `FORGE_REQUIRE_DART_BUILD=1` so a missing `dart` fails rather than skips. 9 tests, 4 wiring breaks all detected.

Still **UNPROVEN**:

- real-model authorship of the synthesized capability source (`capability_implementation` still uses a Test Double in the proof),
- generated Dart loaded into the Forge Flutter app and rendered there — the isolated build workspace has no Flutter (**TD94**),
- a self-generated capability rendered in Chrome,
- full unseen request -> self-extension -> working rendered product E2E.

Primary evidence: `docs/evidence/ACQUIRED-CAPABILITY-VALIDATOR-BOUNDARY-20260831.md`, `docs/evidence/SELF-EXTENSION-BUILD-PIPELINE-20260831.md` and `docs/HANDOFF.md`.

---

## 8. Physical-PC execution checkpoint — 2026-08-31

A real Windows PC at ぱすとらる was used for Forge verification.

Observed session results:

- `flutter analyze`: **PASS / clean**
- `flutter test`: **PASS — 546 tests**
- `flutter build web`: **PASS**
- `flutter run -d chrome`: **BLOCKED before successful app startup**
- actual rendered app in Chrome: **UNVERIFIED**
- manual visual/behavioral interaction: **NOT EXECUTED**

The blocker is Flutter SDK / web SDK path resolution through Puro (Flutter version manager). The session observed a path shaped like:

```text
../../../.puro/envs/stable/flutter/bin/cache/flutter_web_sdk/
```

The exact local checkout SHA used for this physical run was **not durably captured**, so the next physical session must first record `git rev-parse HEAD` before attaching results to a commit.

Durable checkpoint and exact resume instructions:

- `docs/evidence/PHYSICAL-EXECUTION-CHECKPOINT-20260831.md`

This physical session is useful evidence that analyze/test/web-build work on that host, but it is **not physical runtime PASS**.

---

## 9. Golden Generated App Quality Gate

**CURRENT STATUS: FAIL**

Do not rewrite this as PASS because build/test/runtime passed in another episode.

The real repair episode left visual quality as `unknown`, and the latest Golden Generated App visual/behavioral quality evidence has not been superseded by a genuine passing rerun.

Current priority is therefore not merely “more tests”; it is closing real semantic/runtime capability gaps and then performing genuine runtime + visual quality reruns.

---

## 10. Simulation/runtime capability — latest vertical slice

The current branch contains and documents a reusable deterministic simulation vertical slice through Forge’s normal runtime/validation surface.

Progress includes:

- deterministic simulation runtime primitive,
- integer-safe tick arithmetic,
- runtime-safe simulation construction,
- simulation bound into existing Forge runtime numeric state,
- persistence/pause/reset semantics tests,
- backend validator support for the simulation-loop document shape,
- Forge Document schema and widget-registry/runtime wiring,
- frontend tests that prove simulation state flows through the existing Forge state/runtime path.

Key integration commit:

- `12ed096f389904809152f57786942849c49a07c1` — `forge-golden: wire simulation loop through runtime and validator`

This is material progress toward reusable simulation semantics and is preferable to adding a genre-specific game widget/template.

It is still **not** proof that all simulation/game/media requests are supported, that visual quality is good, or that the Golden Generated App Quality Gate has passed.

---

## 10.1 Provider-independent UI and Core UX honesty — 2026-09-02

Proven in this repository, on this branch:

- The home screen no longer lets a user pick between provider identities. The
  `Gemini` / `Mock` toggle is gone; a non-interactive `AIモード` indicator
  replaces it. Route selection returns to Forge's `ProviderRouter`.
- Displayed state now tracks real state: `AIモード` / `AIが考えています…` /
  `お試しモード` / `AIに接続できません`. A mock build can never display as
  real AI; the resolver fails closed rather than optimistic.
- Provider identity is removed from **user-facing text only**. `exc.message`,
  logs, Evidence, `providerUsed` and provider implementation names keep the
  real provider and model.
- **TD92 closed.** Undrawable widgets no longer vanish in release; they render
  an honest placeholder in the user's language, with internal vocabulary kept
  to debug builds.
- **A real render found two lies that analyzer and widget tests did not.**
  Mock conversation output was labelled `Generated by Forge`; it now declares
  itself simulated, and the build-level fact is OR'd in so a forgotten flag
  cannot make fake data look real.

Evidence: `docs/evidence/visual/provider-independent-ui-20260902/` (Chromium,
1440 / 820 / 390 / 320 viewports plus two mock-build renders), report
`docs/reports/FORGE-PROVIDER-INDEPENDENT-UI-20260902-report.md`.

Not proven by this task: cross-profile universal quality, real-device Mobile /
Tablet, the `unavailable` / `preparing` states under a live backend, and any
real Local Model run.

---

## 10.2 Capability ledger and evidence integrity — 2026-09-03

The 121 detailed capabilities now exist as a machine-readable ledger rather than
prose: `docs/evidence/capability_matrix/capabilities.json`, checked in CI by
`scripts/check_capability_matrix.py`. The checker refuses claims the repository
cannot support — a single passing run recorded as `99_PROVEN`, an `IMPLEMENTED`
with no existing evidence path, a hand-written Wilson bound, a shrunken
denominator. Seven such inflations were injected and all seven were caught.

State on 2026-09-03: **`99_PROVEN` 0, `HARD_GATE_PROVEN` 0**, `IMPLEMENTED` 12,
`PARTIAL` 5, `NOT_STARTED` 2, `NOT_ASSESSED` 102. `NOT_ASSESSED` means *not yet
examined*, which is deliberately distinct from `NOT_STARTED` (*examined, absent*).

Two architectural holes were closed:

- **Real-provider egress is default-deny** (`external_call_policy.py`). The
  presence of an API key is no longer treated as consent — that was the exact
  shape of the 2026-09-02 incident. Cloud calls need an explicit flag; tests
  need a second one; anything that is not `1/true/yes/on` fails closed.
- **Provider attribution separates configured from actually used**
  (`model_call_ledger.py`, TD104). A request that calls no model reports
  `"none"` rather than inventing a provider name, and carries `model_calls`,
  `deterministic_path` and `fallback_used`.

ADR-015 records that generated Dart is intentional architecture evolution, not
drift — Constitution §8 names `controlled synthesis` and §10 names
`promotion gates`, and GEN-09/10/11 plus EXT-04/06 are unreachable through the
typed IR vocabulary alone. But the gate chain is incomplete: **no sandbox, no
permission manifest, no tier enforcement, no dependency allowlist**. Generated
test/build steps run with host privileges. EXT-08 was therefore lowered to
`NOT_STARTED` and EXT-03/AI-06 to `PARTIAL`.

---

## 10.3 Generated code now runs isolated — 2026-09-04

Until this date, generated Dart's test/build steps ran **with host privileges**:
network reachable, host environment inherited, no CPU/memory ceiling. That is
now closed on Linux (`forge_ai/core/sandbox/`), and the isolation sits on the
one path that actually executes generated code
(`build_time_workspace._execute`), with `CommandEvidence.sandbox_backend`
recording where each command ran — empty means it was not isolated.

Closed: network namespace, PID namespace, environment rebuilt from empty,
`RLIMIT_CPU` / `RLIMIT_AS` / `RLIMIT_FSIZE`, wall-clock timeout, explicit
workspace, no shell. Escape corpus 8/8 blocked; 13 wiring mutations all
detected — including two placebos in the tests themselves (CPU and memory
limits were being caught by the wall clock rather than by their own rlimit).

Alongside it: a Permission Manifest whose **tier is computed from permissions
rather than declared**, a human gate on tier C, and a dependency allowlist that
also refuses build-time acquisition (`pub get`, `pip install`, `curl`, …).

**Not complete.** Windows and macOS have no backend, so Self-Extension refuses
to run there (fail closed) — Windows is a primary distribution target, so
EXT-08 and SEC-04 stay `PARTIAL`, not `IMPLEMENTED`. `RLIMIT_NPROC` is not
enforced for root (measured), so process defence rests on the PID namespace.

ADR-015 dropped from `ACCEPTED` to `PROVISIONAL`: its original case rested on
"the current typed IR cannot express GEN-09/10/11", which is a different claim
from "an extended typed IR cannot". A 14-axis comparison now favours extending
the IR first and treating source synthesis as the last resort.

Four capability assignments made on 2026-09-02/03 were wrong (SEC-06, SEC-07,
QA-05, UI-11 had been filled with unrelated implementations because the search
terms were written without reading the capability names). Correcting them
lowered `IMPLEMENTED` from 21 to 17.

Verified on CI at `59e38d6` (run `33813646772`, all four jobs green). The heavy
step — 「生成 Dart の実ビルド経路」 — actually executed inside the sandbox
(`test exit=0` / `build exit=0` / `runtime_probe exit=0` / `PROMOTED`), so the
isolation is on the real path rather than only in unit tests. Getting there
took three red runs whose causes were all different: runners cannot create
namespaces; the opt-in was set per-step and forgotten in another job; and the
default `RLIMIT_AS` of 512MB is below what the Dart VM reserves as virtual
address space (measured, not guessed — a 2GB reservation probe fails at 512MB
and succeeds at 8GB).

Counts after this task: `NOT_ASSESSED` 102 → 58, `IMPLEMENTED` 12 → 17,
`PARTIAL` 5 → 26, `NOT_STARTED` 2 → 19. `99_PROVEN` and `HARD_GATE_PROVEN`
remain **0**. Real local-model runs 0, real provider calls 0, device evidence 0,
human evidence 0 people. What narrowed is the security foundation; generation
capability (GEN / UI / LRN) did not move.

---

## 11. Current unverified / incomplete boundaries

Do not claim these as complete without new evidence:

- Physical/user-PC 020B Local-Agent execution
- Successful Chrome startup for the 2026-08-31 physical-PC checkpoint
- Genuine visual PASS for the current generated Golden App gate
- Real-model authorship of a new capability during self-extension
- Build-stage generation time on real hardware: the conversation decision is now fast, but what `PromptPipeline` costs on a small local model is unmeasured (TD98)
- Chrome driven end to end on real hardware (TD99): the 10s wall should be gone, but it has not been watched, so it is not a PASS
- Local model autonomously diagnosing and selecting a successful repair
- Complete production API exposure of all internal build/test/runtime/repair evidence
- Broad generative-software support for simulation/media/game semantics beyond the newly wired primitive
- Broad local-model promotion: Local Promotion remains evidence-gated, not assumed
- Any benchmark axis that is unmeasured should remain `unsupported` or `unknown`, not fake zero/PASS
- Real-device Mobile/Tablet rendering: only Chromium viewport emulation has been run (2026-09-02)
- The `AIモード` `unavailable` / `preparing` states under a live backend: unrendered, because this host must not start the backend (a real `GEMINI_API_KEY` sits in its `backend/.env`)
- ~~Provider attribution in Evidence (TD104)~~ — closed 2026-09-03
- **Frozen Final Holdout is created only after RC freeze**, outside the repository (`docs/evidence/holdout/`). Its absence blocks final 99% certification, **not implementation** — that distinction was wrong in the 2026-09-03 entry and is corrected here
- **Human Evidence: 0 participants.** Still unsecured, but this too blocks certification rather than implementation; capabilities needing it stop at `PRE_HUMAN_READY`
- **Sandbox exists on Linux only** (TD110). Windows and macOS refuse to run rather than running unprotected, so Self-Extension does not work there at all
- **Capability Tier is not enforced in code** (TD108); Tier C can traverse the Tier A path
- Security corpora are undefined, so no security item can claim `HARD_GATE_PROVEN`
- Outcome metrics beyond success rate (repair count, p95 latency, peak RSS, crash, data loss) are not recorded in episodes

---

## 12. Current next-work direction

Order of attack should preserve the Product Direction closed loop and the physical checkpoint:

1. **Resume the physical-PC blocker first**: start PowerShell transcript, capture `git rev-parse HEAD`, `where.exe flutter`, `flutter --version`, `flutter doctor -v`, then fix the Puro/Flutter SDK path issue.
2. **Get `flutter run -d chrome` to a visibly rendered Forge app** before claiming physical runtime PASS.
3. **Measure the build stage on real hardware** (TD98) and drive Chrome end to end (TD99). The conversation decision is fast now; what remains unmeasured is what generation itself costs on a small local model.
4. **Then run one real unseen request through self-extension to the real Flutter/Dart runtime**, including Validator evidence and a genuinely acquired capability.
4. **Keep every new capability on the production generation/validator/runtime path**, with tests that fail when wiring is removed.
5. **Run genuine visual/behavioral review** and keep the Golden Gate FAIL until it passes.
6. **Preserve Generation Episode / evidence lineage** for both successes and repairs.
7. **Improve Local Intelligence / agent diagnosis and controlled repair selection** without weakening verifier boundaries.
8. **Promote Local routing only when held-out evidence meets the product bar.**

---

## 13. Agent read order

Before doing Forge work, read in this order:

1. `docs/FORGE-CORE-CONSTITUTION.md`
2. `docs/PRODUCT-DIRECTION.md`
3. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
4. `docs/LEARNABLE-LOCAL-AI-VISION.md`
5. `docs/FORGE-CURRENT-STATE.md`
6. `docs/HANDOFF.md`
7. `docs/evidence/PHYSICAL-EXECUTION-CHECKPOINT-20260831.md` when resuming the current physical-PC work
8. `AGENTS.md`
9. `CLAUDE.md` when using Claude Code
10. relevant Architecture / Spec / report / evidence
11. latest GitHub HEAD / diff / CI

If this CURRENT STATE disagrees with newer GitHub evidence, **newer evidence wins** and this file must be updated in the same task.

---

## 14. State-management rule

`FORGE-CORE-CONSTITUTION.md` changes only through CEO-approved Constitution Change Proposal.

`FORGE-CURRENT-STATE.md` is deliberately mutable and should change whenever the real implementation/evidence state changes.

This separation prevents two recurring failures:

- freezing temporary architecture as eternal product truth,
- carrying stale chat-era facts forward after the repository has moved on.
