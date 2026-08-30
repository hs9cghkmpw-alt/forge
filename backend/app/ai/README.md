# Forge AI layer

This directory participates in Forge's natural-language software-generation pipeline. It is **not** defined as a finite UI-template selector and it must not narrow Forge's product goal to "generate JSON for known screens".

Canonical direction:

1. `docs/FORGE-CORE-CONSTITUTION.md`
2. `docs/PRODUCT-DIRECTION.md`
3. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
4. `docs/FORGE-WHOLE-SCAN-PROTOCOL.md`

Core invariant:

> **持っている能力は組み合わせる。足りない能力は作る。作った能力は検証し、再利用可能な Forge Capability として取り込む。**

## Responsibilities

The AI/generation path should move from user intent toward verified software through semantic decomposition and capability planning:

```text
natural-language need
 -> candidacy / intent understanding
 -> capability decomposition
 -> compose existing capabilities
 -> identify exact missing capability when composition is insufficient
 -> safe synthesis / extension route when feasible
 -> Forge IR / versioned language / generated workspace
 -> validator / compiler / runtime
 -> test / build / runtime evidence
 -> repair if needed
 -> evidence-backed capability promotion when a new reusable capability was created
```

Some production paths still emit versioned Forge JSON. JSON is a transport/language boundary for those paths, **not the definition of Forge itself**.

## Rules

- Do not map an unsupported request to the nearest easy app shape and call that success.
- Do not add domain-specific templates just to pass a Golden request.
- Prefer reusable semantic capabilities and primitives over one-off widgets.
- If the current runtime cannot express a requirement, return an exact Capability Gap and enter the applicable extension/synthesis path rather than silently deleting the requirement.
- Never fabricate unknown schema types to bypass validation.
- Keep effects, permissions, secrets, irreversible operations, and trust boundaries explicit.
- `PARTIAL`, `MISSING`, `MOCK`, `STUB`, and `UNVERIFIED` must remain distinct from `IMPLEMENTED` / `PASS`.
- A generated result is not complete merely because a model returned text or JSON; production validation and evidence are required.

Historical fixed-template experiments may still exist in git history or old reports. They are not authoritative product direction.
