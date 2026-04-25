# Ownership boundaries (Slug-Ig-Crawler)

Map of **concern → primary directories**. When changing behavior, touch the **owning** layer first; avoid "smart" shims in the wrong place.

| Layer | Owns | Primary paths |
|-------|------|----------------|
| **Workflow** | CLI entry, mode selection, Postgres preflight, pipeline orchestration | `src/igscraper/cli.py`, `src/igscraper/pipeline.py` |
| **Browser** | Chrome/Driver lifecycle, CDP enablement, session tabs | `src/igscraper/backends/selenium_backend.py`, `src/igscraper/chrome*.py` |
| **Capture** | Network log / GraphQL response harvesting, scroll helpers | `src/igscraper/utils.py` (high surface — avoid mega-refactors mixed with features) |
| **Pages / DOM** | Page objects, selectors, grid navigation | `src/igscraper/pages/` |
| **Parser** | YAML flatten rules, registry, model matching | `src/igscraper/flatten_schema.yaml`, `src/igscraper/models/` |
| **Session** | Cookies, login flows, checkpoint handling | `selenium_backend.py`, cookie paths in config |
| **Output / persistence** | JSONL layout, GCS upload, Postgres enqueue | `src/igscraper/services/enqueue_client.py`, pipeline write paths |
| **Integration** | Thor worker id, trace fields, ops env | `[trace]` config, `FileEnqueuer`, logging |
| **Release / bootstrap** | Packaging, browser cache, local DB setup | `pyproject.toml`, `src/igscraper/bootstrap*.py`, `scripts/postgres_setup.sql` |

**Audit reference:** [audit-output-igscraper/executive_summary.md](../../audit-output-igscraper/executive_summary.md).

**Deep dive (existing doc):** [architecture.md](../architecture.md) — prefer linking here over duplicating component prose.
