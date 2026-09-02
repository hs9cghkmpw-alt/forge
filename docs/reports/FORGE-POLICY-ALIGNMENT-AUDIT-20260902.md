# Forge Policy Alignment Audit — 2026-09-02

**Status:** REVIEWED / CORRECTED / CONSTITUTION APPROVED AND APPLIED

**Start HEAD:** `d498283e9828226249abc09405cc6622fa5eb5c4`

**Runtime behavior changed:** No

**Governance and CI changed:** Yes

## 1. Audit scope

The audit compared the current zero-budget/99% strategy and operational documents with:

- Forge Core Constitution
- Product Direction
- Generative Software Direction
- Learnable Local AI Vision
- Machine-Independent Policy
- attached Forge vision and roadmap images
- CEO directions preserved in the current project context
- current architecture, HANDOFF, roadmap, technical debt, and Git state

The central test was not whether wording looked similar. It was whether a future agent
could follow the text and still build a Forge that violates the CEO's intended product.

## 2. Binding CEO policy reconstructed

| Policy | Required interpretation |
|---|---|
| Everyone receives high quality | Hardware, device, plan, model, and host never become output-quality tiers |
| Conversation is the product | Natural need expression, minimum necessary questions, revision through conversation |
| Speak and Forge handles the rest | Internal model/runtime/build choices stay inside Forge |
| Start with the smallest useful tool | Scope may start small only with agreement; quality inside that scope stays complete |
| AI chooses meaning; Forge guarantees quality | Semantic roles may vary; deterministic quality constraints do not |
| Capability is not Widget/Template | Templates and widgets remain reusable primitives, never the ceiling |
| Freedom and safety together | Unknown capability grows through contract, sandbox, tests, trust, and promotion |
| Local-first and provider-independent | Cloud can be optional teacher/host, never a permanent core-quality requirement |
| Use makes Forge grow | Evidence, correction, provenance, benchmark, and safe promotion form a closed loop |
| Honest evidence | Mock, unrun, unknown, or documentation-only work never becomes real PASS |
| Ordinary devices are first-class | Smartphone, tablet, web, and desktop all complete conversation/preview/revision/acceptance/use |
| No fake UI | No dead controls, false completion summaries, silent omission, or stale regeneration |

## 3. Findings and corrections

| Severity | Finding | Why it was misaligned | Correction |
|---|---|---|---|
| P0 | `Low resource PC -> small model` appeared in distribution architecture | It directly permits hardware-dependent intelligence quality | Replaced with Execution Resolver routes and mandatory common quality gates |
| P0 | Low-resource success only required OOM/Crash absence | A product can remain running while producing worse results | LOC-10/Q083 now require identical Task/Visual/Safety quality |
| P0 | Automatic model selection could optimize quality and speed per device without a common floor | This can silently select a weaker experience | Reframed as execution-route selection among common-gate-approved candidates only |
| P0 | Free/paid clause protected “essential experience” but not every quality dimension | It left room for rougher free output | Added cross-plan common-task Hard Gate and a Constitution proposal |
| P1 | “Visible degraded state” could be read as an acceptable release result | It normalizes a lower-quality success | Replaced with honest unsupported/repairing state; lower-quality artifact is never success |
| P1 | “Degraded core” wording during component failure was ambiguous | Isolation is valid; lower output quality is not | Clarified failure isolation and repair without degraded substitute success |
| P1 | “Smallest useful tool” and solution shrink were not explicitly separated from quality shrink | Scope reduction could hide semantic deletion | Added agreed-scope/full-quality rule and silent deletion Hard Gate |
| P1 | Mobile-first existed, but equal-quality cross-device testing was not a universal gate | First-class input client can still receive inferior output | Added Mobile/Tablet/Desktop/Web common Core UX and quality gates |
| P1 | Voice/text, dead controls, honest completion, current-state regeneration were not in the strategy Hard Gates | Prior CEO UX directions could regress while 121 technical items pass | Added Core UX invariants and zero-tolerance gates |
| P2 | Agent pre-work checklist did not explicitly reject hardware quality tiers | The same ambiguity could return in future changes | Added mandatory checks and canonical policy to read order |
| P2 | Alignment depended on human reading only | Wording could regress unnoticed | Added `check_universal_quality_policy.py` and CI execution |

## 4. What was already aligned

- Generated App Quality and Forge-owned Local AI remain inseparable.
- Golden Apps remain quality oracles, not fixed templates.
- Cloud output remains a teacher candidate, not truth.
- Reuse-first, provider independence, Local-first, privacy, and user permission remain intact.
- Unknown capabilities follow typed contract, sandbox, validation, promotion, reuse, and evidence.
- Average scores cannot hide one weak item; unknown and unverified evidence do not pass.
- PWA client and Execution Host are separable; smartphones are not permanent second-class clients.
- The 99% result is End-to-End after repair/fallback, with semantic and safety Hard Gates.

## 4.1 Multi-disciplinary challenge results

| Expert lens | Strict question | Result after correction |
|---|---|---|
| Product strategy | Does plan or hardware segmentation change the promise? | No; segmentation may change volume/breadth/route, not common-task quality |
| UX research | Does the user have to understand models, hosts, or build systems? | No; Forge resolves them and shows only honest progress/actions |
| Service design | Can the journey finish on ordinary mobile/tablet devices? | Core conversation/preview/revision/acceptance/use are universal gates |
| ML engineering | Can a smaller/quantized model silently reduce reasoning quality? | No; only candidates passing the same final Task gates are approved |
| Distributed systems | What happens when one device lacks compute? | Execution moves or splits with permission; the contract stays fixed |
| Security | Can fallback remove checks to preserve success rate? | No; Safety/Privacy gates are invariant and never averaged away |
| Accessibility | Can low-resource/mobile variants ship simpler inaccessible UI? | No; identical Accessibility gates apply across Profiles |
| Visual design | Can device class receive a rougher generated app? | No; Visual and information-design gates are common |
| Reliability | Can degraded operation be counted as task completion? | Only unaffected tasks continue; failed tasks enter repair, not fake success |
| Statistics | Can average results hide weak hardware slices? | No; every hardware/device slice needs its own lower-bound pass |
| QA | Can policy remain advisory and regress later? | No; agent pre-check and CI policy check now fail on known regressions |
| Governance | Can the immutable Constitution be silently reinterpreted? | No; exact proposal created and explicit approval preserved |
| Economics | Does zero budget force quality reduction? | No; time, reuse, routing, OSS, existing hosts, and automation replace spend |
| Learning systems | Can data from weaker modes train Forge downward? | No; only common-gate evidence can enter promotion decisions |

The 256 doubts in the zero-budget strategy remain assigned to closure evidence. This
audit adds universal-quality conditions across them; it does not replace or reduce the
individual 99% requirements.

## 5. Final policy architecture

```text
One user contract
  -> same Product Quality Contract
  -> Execution Resolver absorbs hardware/host differences
  -> full Task + Visual + Safety + Privacy + Recovery gates
  -> same high-quality result
```

Speed may improve on stronger hardware. Local resource use and execution location may
change. The quality floor does not.

## 6. Constitution boundary

The prior Constitution was compatible in intent but not explicit enough to prevent a
future narrow reading. Its protocol forbids silent edits. Therefore this task created:

- `FORGE-CONSTITUTION-CHANGE-PROPOSAL-UNIVERSAL-QUALITY-20260902.md`

The CEO reviewed the exact proposed wording and replied `いいよ、すべて承認` on
2026-09-02. Constitution §13 now contains the Universal Quality Invariant, and the
proposal status is `APPROVED BY CEO / APPLIED`.

## 7. Verification

- Repository-wide searches for hardware/quality/model-tier wording
- Manual comparison of all top-level direction documents and attached diagrams
- `python3 scripts/check_universal_quality_policy.py`
- `git diff --check`
- No runtime/product success is claimed; this task changes policy, enforcement, and plan

## 8. Remaining implementation evidence

The rule is now explicit and CI-guarded, but the product has not yet demonstrated equal
quality across the complete hardware/device matrix. Z2, Z9, and Z12 must produce the
cross-profile Task/Visual/Safety evidence. Until then the state is `DESIGNED / GUARDED`,
not `VERIFIED`.
