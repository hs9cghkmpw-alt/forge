# FORGE-019 Visual Evidence Manifest

- Task: FORGE-019 Semantic Design Revision + Visual Dev Loop v1
- Git baseline: `07bb8af6395d64a096c7298c226fafa61f6da0a6` (screenshots captured from the FORGE-019 working tree before final commit)
- Scenario: Golden Finance — 「残高をもっと目立たせて」
- Route: `http://localhost:7358/?state=before|after`
- Viewport: 390 × 844 CSS pixels
- Before: `finance-before.png`
- After: `finance-after-balance-emphasis.png`
- Semantic operation: `select_primary_metric`
- Semantic target: screen `home`, widget `balance`, identity `balance`
- Local patch: `income.style_role metric.primary → finance.income`; `balance.style_role metric.secondary → metric.primary`
- Validator: PASS (production schema fixture test and backend semantic patch test)
- Semantic Design Critic: PASS; no blocking issue
- Visual review: PASS after one correction cycle. The first capture exposed an invalid fixture and was rejected. The corrected images show no overlap, overflow, clipping, broken alignment, or unusable controls at the mobile viewport.
- Quality finding: the After view makes 残高 447,000円 the largest typographic metric; income, expense, headings, transaction rows, spacing, and ordering remain unchanged.
- Fixed finding: fixture record values were converted to the production `{id, fields}` contract; unsupported list fixture properties were removed.
- Remaining unverified: browser automation does not yet drive the live `/update` request and then capture that exact response document in one process; fixture equality is locked by backend and Flutter contract tests. Screenshot upload/training is not implemented.
