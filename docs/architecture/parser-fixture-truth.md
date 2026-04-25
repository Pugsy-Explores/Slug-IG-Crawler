# Parser fixtures and CI truth

## Where golden samples live

| Path | Role |
|------|------|
| `src/igscraper/tests/fixtures/sample_graphql_timeline_min.json` | Minimal `xdt_api__v1__feed__user_timeline_graphql_connection` shape |
| `src/igscraper/tests/fixtures/sample_graphql_comments_min.json` | Minimal comments connection shape |
| `src/igscraper/tests/sample_graphql_*.json` | Older/larger samples in `tests/` (not CI-golden); prefer `fixtures/` for new contract tests |
| `src/igscraper/flatten_schema.yaml` | Bundled schema shipped with the package — **source of truth** for flatten rules |

## What tests cover (no browser)

| Test module | Covers |
|-------------|--------|
| `src/igscraper/tests/test_load_schema.py` | Bundled YAML loads; `load_schema` path resolution |
| `src/igscraper/tests/test_flatten_schema_contract.py` | Critical `rules.data` keys present; alignment note for `COMMENT_MODEL_KEYS` |
| `src/igscraper/tests/test_parser_golden_contract.py` | Golden fixtures → non-empty rows via `GraphQLModelRegistry.flatten_response` |
| `src/igscraper/tests/test_thor_worker_id.py` | `[trace].thor_worker_id` and enqueue SQL (not parser) |

## CI

- Prefer **`pytest`** on the above modules in default CI — fast, deterministic.
- **Selenium** suites are optional / manual unless the project adds a dedicated job with browser infrastructure.

## When IG changes GraphQL shape

1. Capture new response (dev only, respect ToS).
2. Update **`flatten_schema.yaml`** and **`MODEL_REGISTRY`** / backend key sets.
3. Update **fixtures** and run `pytest src/igscraper/tests/test_parser_golden_contract.py src/igscraper/tests/test_flatten_schema_contract.py -q`.
