# Command: ig-bootstrap-strategy

## Purpose

Before multi-week strategy work, build a GPT-ready packet without dumping repo text.

Use for DOM pipeline redesign, new workflows, selector drift recovery, parser/`flatten_schema` redesign, Thor compatibility evolution, release planning, or session reliability planning.

## Modes

- roadmap
- unblock
- redesign
- release-hardening
- thor-integration
- parser-stabilization

Default: roadmap.

## Read order

1. `.ai/BOOT_CONTEXT.md`
2. `.ai/memory/CURRENT_STATE.md`
3. `.ai/memory/HANDOFF.md`

Then skim only relevant docs:

- [README.md](../../README.md)
- [docs/architecture.md](../../docs/architecture.md)
- [docs/contracts/thor-handshake.md](../../docs/contracts/thor-handshake.md)
- [docs/contracts/parser-output-contract.md](../../docs/contracts/parser-output-contract.md)
- [docs/contracts/scrape-run-contract.md](../../docs/contracts/scrape-run-contract.md)
- [docs/architecture/selector-inventory.md](../../docs/architecture/selector-inventory.md)
- [audit-output-igscraper/executive_summary.md](../../audit-output-igscraper/executive_summary.md)

## Output

Produce one paste-ready brief (max ~1200 words) with:

### Project
What IG Scraper is today.

### Mission
What must stay true:
- extraction reliability over hype
- safe parser contracts
- Thor compatibility maintained
- no blind DOM hacks
- packaging remains usable
- selectors remain maintainable

### Current Reality
- active priorities
- blocker bugs
- selector drift areas
- parser debt
- session/cookie issues
- release readiness

### Constraints
- Instagram DOM volatility
- auth/checkpoint risk
- founder bandwidth
- no big-bang rewrite
- backward compatibility where needed
- local browser validation often required

### Open Risks
- selectors stale
- login/session drift
- `flatten_schema` mismatch
- hidden `utils.py` coupling
- Thor contract drift
- packaging regressions

### Strategic Options
2-3 real paths with tradeoffs.

### Recommended Path
Best path now + why.

### Do Not Do
Examples:
- broad `utils.py` rewrite
- many workflows at once
- weaken preflight checks
- selector overfitting without proof
- parser rewrite without fixtures

### Ask Humans
1-3 forced-choice decisions only.

### GPT Request
Mode-specific ask:
- roadmap
- unblock
- redesign
- release-hardening
- Thor integration
- parser stabilization

## Done signal

A principal engineer can advise immediately without opening ten tabs.

## Guardrails

- Link docs; do not dump them.
- No generic startup advice.
- Scraper-specific output only.
- Optimize for decisions, not summaries.
