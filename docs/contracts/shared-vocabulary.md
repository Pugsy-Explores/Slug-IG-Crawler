# Shared contract vocabulary (cross-repo)

**Mirrored** in `pugsy_agent_os`, `thor`, and `ig_profile_scraper` with **identical canonical semantics**. This file is the **machine-readable meaning** layer for GPT, Cursor, dashboards, and adapters — not governance theater.

**Phase 1:** documentation only. Existing code may keep legacy strings; map them below.

---

## Canonical fields

### 1. `status` (string)

Coarse lifecycle of a **unit of work** (job, run, tool call, workflow step). Use **one** of these when emitting new payloads:

| Value | When to use |
|--------|-------------|
| `queued` | Accepted / waiting for a worker or slot (not executing yet). |
| `running` | Actively executing. |
| `success` | All requested work completed as specified. |
| `failed` | Stopped with error; not a partial completion story. |
| `partial_success` | Some requested work completed, some not (see `partial_success` flag below for strict JSON). |
| `cancelled` | Intentionally stopped; no further automatic work. |
| `retrying` | Temporary failure; same logical work will be attempted again automatically. |
| `blocked` | Cannot proceed without external action (policy, dependency, auth, quota). |
| `stale` | Output or input is older than policy allows (often paired with `freshness`). |

**Legacy aliases (do not use in new contracts):** `done` / `complete` → `success`; `error` → `failed`.

---

### 2. `retryable` (boolean)

- **`true`:** transient (rate limit, timeout, dependency blip) — safe to retry the **same** logical request without changing inputs.
- **`false`:** hard failure (invalid input, auth, contract mismatch, unrecoverable scrape) — fix inputs or system before retry.

---

### 3. `terminal` (boolean)

- **`true`:** no automatic progress expected (`success`, `failed`, `cancelled`, or terminal `blocked` with no retry path).
- **`false`:** still in flight or may move without human action (`queued`, `running`, `retrying`).

---

### 4. `freshness` (object, optional)

Use when **recency** matters (cache, scrape age, report validity).

```yaml
freshness:
  checked_at: <ISO-8601 or unix>
  source_timestamp: <when upstream data was produced>
  age_seconds: <number>
  stale_threshold_seconds: <policy limit; optional>
```

Omit the whole object if not applicable.

---

### 5. `partial_success` (boolean **or** `status`)

- Prefer **`status: partial_success`** in new event-style payloads **or** keep `status: success` with **`partial_success: true`** if you need backward compatibility — **pick one pattern per contract** and document it.
- Examples: 8/10 profiles scraped; comments OK but likes missing; report emitted with explicit stale-data warning.

---

### 6. `error_code` (string)

Short **stable** identifier. No prose, no stack traces.

Examples: `AUTH_REQUIRED`, `RATE_LIMITED`, `SELECTOR_DRIFT`, `SCHEMA_MISMATCH`, `DB_UNAVAILABLE`, `TIMEOUT`, `INVALID_INPUT`, `DEPENDENCY_DOWN`, `POLICY_BLOCKED`.

Human text lives in a separate `message` / `detail` field if needed.

---

### 7. `version` (string)

Contract or payload schema version, e.g. `v1`, `thor-jobevent-v1`, `igscraper-output-v1`. Bump when breaking field meaning.

---

### 8. `trace_id` (string)

End-to-end correlation: one PUGSY workflow, Thor job lineage, IG scraper run, and logs. **Emit on new integrations** where practical; join in dashboards later.

**This repo today:** use `[trace].thor_worker_id` and timing logs as correlation hooks; align naming with `trace_id` when payloads are extended (see [thor-handshake.md](thor-handshake.md)).

---

## Cross-repo tracing (mental model)

**PUGSY** orchestrates → **Thor** runs jobs → **IG Scraper** executes. A single `trace_id` should appear in: Agent OS run log, Thor worker log / job note, scraper `[trace]` / timing JSON — when systems are wired for it (phased).

---

## Examples: **this repository** (Slug-Ig-Crawler / `igscraper`)

1. CLI starts pipeline after preflight → `status: running`, `terminal: false`.
2. Postgres preflight `SystemExit` (tables missing) → `status: failed`, `error_code: DB_UNAVAILABLE`, `terminal: true`, `retryable: false` until schema fixed.
3. Run finishes all targets with full extraction → timing / logs `success` → shared `status: success`, `terminal: true`.
4. Run finishes but 2/10 profiles empty due to UI → `status: partial_success`, `partial_success: true`, `terminal: true`.
5. Login wall / bad cookies → `status: failed`, `error_code: AUTH_REQUIRED`, `retryable: false` until new cookie.
6. IG rate / soft block → `status: retrying` or `blocked`, `error_code: RATE_LIMITED`, `retryable: true` when backoff helps.
7. `flatten_schema` / parser mismatch → `status: failed`, `error_code: SCHEMA_MISMATCH`, `retryable: false` until code/schema fix.
8. DOM break (known selectors) → `status: failed`, `error_code: SELECTOR_DRIFT`, `retryable: false` until selector fix.
9. User interrupt / process kill → `status: cancelled` (if surfaced), `terminal: true`.
10. Output JSONL written but data older than policy → attach `freshness` or mark `stale` on **downstream** contract (scraper may still report `success` for the run slice).

---

## Thor ↔ PUGSY ↔ IG status mapping (quick reference)

| Thor `jobs.status` | Typical shared `status` | `terminal` |
|--------------------|-------------------------|------------|
| `PENDING` | `queued` | false |
| `CLAIMED` | `running` | false |
| `RUNNING` | `running` | false |
| `COMPLETED` | `success` | true |
| `FAILED` | `failed` | true |
| `BLOCKED` | `blocked` | true |

Decider / lease return to `PENDING`: still **`queued`** (or internal `retrying` in logs only — prefer **`queued`** for DB truth).

---

*Last updated: 2026-04-25*

---

## Phase 2 — Runtime embeddings (implemented)

**Principle:** additive only; legacy fields stay. No DB enum changes.

| Surface | Where | Key | `version` |
|---------|--------|-----|-----------|
| Thor | `jobs.job_params` (terminal transitions) | `_envelope` | `thor-jobevent-v1` |
| PUGSY Agent OS | Tool result dicts (`get_brand_posts`, `get_system_health`) | `envelope` | `pugsy-tool-result-v1` |
| IG Scraper | Structured timing log JSON (`logger.info`) | `envelope` | `igscraper-log-v1` |

**`trace_id`:** Thor uses `job_id` UUID string; PUGSY uses `run_id`; IG uses `thor_worker_id` until a single ID is propagated end-to-end.

**IG legacy:** top-level `status` remains `success` \| `error` (timing); use `envelope.status` for shared vocabulary.

