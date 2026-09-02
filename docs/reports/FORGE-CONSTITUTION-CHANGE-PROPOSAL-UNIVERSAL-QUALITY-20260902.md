# FORGE CONSTITUTION CHANGE PROPOSAL — Universal Quality

**Status:** APPROVED BY CEO / APPLIED

**Date:** 2026-09-02

**Runtime change:** None

**Approval record:** The CEO reviewed the exact proposed wording and replied
`いいよ、すべて承認` on 2026-09-02. The wording was then added to Constitution §13.

## 1. Current clause

Constitution §13 currently says:

> The free product must not be a degraded version of the core experience.
>
> Differences may be imposed mainly on breadth, usage volume, advanced capabilities,
> complexity, or customization.
>
> Same essential experience; different capability envelope.

Constitution §14 says the client and execution/intelligence host may differ and that
execution location is resolved by capability, performance, privacy, and permission.

## 2. Newly observed conflict

The CEO has made the intended invariant explicit: PC specifications must not raise or
lower Forge quality, and everyone must receive the same high quality. Existing
architecture text allowed a reading of `low resource PC -> small model` without an
explicit same-output-quality requirement. Section 13 also says “same essential
experience,” but does not explicitly protect full output quality across hardware,
device, plan, or execution route.

## 3. Why the current wording is insufficient

- “Essential experience” can be interpreted more narrowly than generated-app quality.
- “Different capability envelope” can be misused to create free/paid quality tiers.
- Section 14 permits routing by performance but does not say performance differences
  must be absorbed internally.
- A future implementation could pass formal reading while giving low-resource users a
  smaller model, rougher design, fewer checks, or missing functions.

## 4. Risk of no change

- Hardware-dependent output quality becomes normalized.
- Mobile or free users become second-class despite receiving the same task.
- Local AI optimization rewards speed/RAM at the expense of meaning and design.
- Benchmark results hide Profile-specific regressions behind a global average.
- “Smallest useful tool” is misread as permission for silent feature deletion.

## 5. Proposed wording

Add the following to Constitution §13 after its current final line:

> **Universal quality invariant.** For the same supported task and agreed scope, Forge
> must apply the same product-quality floor regardless of computer specifications,
> GPU/RAM, operating system, client device, free/paid plan, model profile, or execution
> location. Hardware and plan differences may change usage volume, breadth, execution
> route, resource use, or time within a published limit; they must not lower meaning,
> functionality, generated-app quality, safety, privacy, reliability, accessibility,
> data protection, or evidence standards. Forge must resolve resource differences
> internally or through an explicitly permitted execution host, not by silently
> producing a lower-quality result.
>
> A smaller agreed scope may be delivered first, but that scope must meet the same
> quality floor. Silent semantic deletion or degraded substitutes are not successful
> completion.

## 6. Side effects / trade-offs

- Low-resource devices may wait longer within a declared upper limit or delegate work
  to a permitted host.
- Some tasks require capability acquisition before they can be honestly completed.
- Every approved model/profile needs cross-profile task, visual, safety, and recovery
  evidence; simple OOM-free evidence is insufficient.
- Paid differentiation must focus on volume, breadth, administration, and convenience,
  not inferior core output for free users.
- Product claims become narrower but more honest until all profiles pass.

## 7. Recommended decision

**APPROVE.** This does not change Forge's intended identity; it closes an ambiguity that
could otherwise undermine the CEO's existing equality, mobile-first, quality-first,
and local-first direction.

**Decision:** Approved. The proposed wording was copied into §13 without changing its
meaning. The Repository commit containing this report is the durable approval record.
