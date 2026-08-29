# FORGE-GOVERNANCE-001 — Core Constitution / Current State split

Date: 2026-08-29  
Type: Governance / documentation / agent protocol  
Runtime or product code changed by this task: **No**

## Purpose

Forge had accumulated several correct but differently scoped sources of truth: Product Direction, Generative Software Direction, Learnable Local AI Vision, operational HANDOFF, chat-era summaries, and agent instructions. The recurring risk was mixing long-lived product purpose with temporary architecture or stale implementation status.

This task introduces a deliberate two-layer model:

1. `docs/FORGE-CORE-CONSTITUTION.md` — immutable-by-default purpose and experience principles.
2. `docs/FORGE-CURRENT-STATE.md` — mutable implementation/evidence snapshot that must move with the repository.

The Constitution does **not** freeze provider names, model choices, framework choices, Forge Language versions, benchmark counts, UI screen names, or temporary pipeline structure.

## Evidence reviewed before writing

The text was checked against the current GitHub repository rather than chat memory alone, including:

- `docs/PRODUCT-DIRECTION.md`
- `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
- `docs/LEARNABLE-LOCAL-AI-VISION.md`
- `docs/HANDOFF.md`
- root `AGENTS.md`
- root `CLAUDE.md`
- current branch / HEAD / recent commits
- durable FORGE-020B and FORGE-020D/020E evidence references recorded in HANDOFF
- deterministic simulation runtime/state-binding work and its latest documented vertical-slice checkpoint through HEAD `af66546b8ecb80b810daf489b15ae3816bdb39e2`

## Important current facts preserved

- Product Direction remains two inseparable axes: Generated App Quality + Forge-owned Local AI.
- Golden Apps remain quality bars, not templates.
- Forge must not end as a finite Widget/Template Builder.
- Cloud/teacher output remains candidate, not truth.
- Real GitHub-hosted 020B Local-Agent evidence exists; physical-PC leg is still UNVERIFIED.
- Real GitHub-hosted generated Flutter fail→repair→test/build/runtime PASS evidence exists for 020D/020E.
- Visual result in that episode remains `unknown`.
- Golden Generated App Quality Gate remains **FAIL** and was not rewritten.
- The current branch now has a documented simulation-loop vertical slice wired through validator/runtime/state paths; this is real capability progress but not broad game/media or visual-quality completion evidence.

## Agent protocol changes

`AGENTS.md` and `CLAUDE.md` now require the following read order before work:

1. Core Constitution
2. Product Direction
3. Generative Software Direction
4. Learnable Local AI Vision
5. Current State
6. HANDOFF
7. agent-specific rules + relevant architecture/spec/report/evidence + latest GitHub facts

They also require a `FORGE CONSTITUTION CHANGE PROPOSAL` instead of silent edits when an agent believes the immutable core should change.

## What was deliberately NOT changed

- Product/runtime/backend/frontend code
- Forge Language / Schema
- Local AI provider routing
- Evidence JSON
- Golden quality result
- TECH_DEBT classifications
- ROADMAP priorities

## Verification

This is a documentation/protocol-only change. No code-path PASS is claimed from this task. Correctness was checked by comparing the governance documents against current committed product-direction, handoff, evidence references, branch state, and latest simulation/runtime integration commits.

## Future maintenance rule

- Constitution: change only after explicit CEO approval.
- Current State: update whenever newer repository evidence makes it stale.
- GitHub evidence beats stale chat summaries.
