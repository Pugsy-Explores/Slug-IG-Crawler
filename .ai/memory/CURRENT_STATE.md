# CURRENT_STATE

**Branch / release:** `main` (post-merge stabilization)  
**Last touched:** 2026-04-25

## Active priorities (max 3)

1. Monitor first post-merge workflow-check cycle and keep parser/trace contracts stable.
2. Keep docs/contracts and runbook references aligned with merged behavior.
3. Monitor post-merge workflow-check stability on `main`.

## Drift / parser

- Open selector or `flatten_schema` follow-ups: none added in this closeout pass.
- Golden fixture gaps: no new known gaps from this workstream.

## Thor / integration

- Compose DB env / preflight issues: Thor-side validation now GREEN for tiny PROFILE; IG side consumed expected trace/preflight semantics.

## Next tasks

1. Run periodic `ig-workflow-check` bundle during first post-merge day and capture failures quickly.
2. Keep `IGSCRAPER_INTERACTIVE_GUARD` behavior documented as opt-in debug mode.

## Risks

- Runtime behavior still depends on external IG/session stability and valid cookies.
- Validation runs may skip GCS upload via Thor-scoped config guard; keep this explicitly marked as validation-path only.
