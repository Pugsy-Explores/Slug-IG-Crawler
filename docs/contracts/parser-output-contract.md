**Cross-repo vocabulary:** [shared-vocabulary.md](shared-vocabulary.md).

# Contract: parser output (GraphQL → flattened rows)

## Sources of truth

1. **`src/igscraper/flatten_schema.yaml`** — ordered rules under `rules.data` and `rules.extensions` that drive `GraphQLModelRegistry.apply_nested_schema` / `flatten_response`.
2. **`MODEL_REGISTRY`** — `src/igscraper/models/common.py` plus `@register_model` on Pydantic models; consumed by `GraphQLModelRegistry` for typed parsing after flatten/match.
3. **Backend comment key allowlist** — `SeleniumBackend.COMMENT_MODEL_KEYS` in `src/igscraper/backends/selenium_backend.py` must stay **consistent** with which top-level `xdt_api__*` comment shapes the capture path treats as comment-bearing. (the child-comments key may remain in YAML while commented out in this set — intentional drift surface; un-comment or extend the set when the capture path uses it).

## Critical top-level `data` keys (must-pass for regression tests)

These names are **internal Instagram web client** identifiers; they change when IG ships a new client. When they change, update **YAML**, **registry**, **COMMENT_MODEL_KEYS**, and **golden fixtures** together.

| Key | Role |
|-----|------|
| `xdt_api__v1__feed__user_timeline_graphql_connection` | Profile timeline / grid connection |
| `xdt_api__v1__media__media_id__comments__connection` | Top-level comments connection |
| `xdt_api__v1__media__media_id__comments__parent_comment_id__child_comments__connection` | Reply / child comments |

## Golden JSON expectation

- **Fixtures:** `src/igscraper/tests/fixtures/sample_graphql_*.json` — minimal real-shaped `{"data": { ... }}` payloads.
- **Envelope:** `flatten_response` re-wraps inner GraphQL `data` to match `rules` and forwards optional top-level `extensions` when present.
- **Tests:** `src/igscraper/tests/test_parser_golden_contract.py` — assert that `GraphQLModelRegistry(...).flatten_response(fixture)` returns **non-empty** flattened rows for audited shapes.
- **CI:** default CI should run parser/schema tests **without** a browser; see [parser-fixture-truth.md](../architecture/parser-fixture-truth.md).

## Partial success

- **partial_success** at the parser layer means: some GraphQL captures flattened correctly while others were dropped or empty — must be logged with **error_code** or diagnostic keys, not silent truncation.
