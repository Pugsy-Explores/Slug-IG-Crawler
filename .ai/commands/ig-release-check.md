# Command: ig-release-check

## Purpose

**Release hygiene** for PyPI / consumers (Thor, ops): version, packaging smoke, and contract pointers.

## When to use

Before tagging or publishing; after dependency or entrypoint changes.

## Flow

1. Read [docs/PYPI_RELEASE.md](../../docs/PYPI_RELEASE.md) and [CHANGELOG.md](../../CHANGELOG.md) (if present).
2. `python -m build` locally; install wheel in a fresh venv; `Slug-Ig-Crawler --help`.
3. Confirm **bundled** `flatten_schema.yaml` matches what tests assert ([parser-fixture-truth.md](../../docs/architecture/parser-fixture-truth.md)).
4. Skim [docs/contracts/thor-handshake.md](../../docs/contracts/thor-handshake.md) for breaking `[trace]` / DB expectations.
5. Assign ship gate:
   - **Green**: build/install/help + contract checks pass, no known breaker.
   - **Yellow**: ships with bounded known issue + explicit workaround.
   - **Red**: packaging, contract, or preflight break with no safe workaround.

## Output format

- version bump recommendation  
- smoke test result  
- breaking / non-breaking  
- ship gate (red / yellow / green) + one-line reason  

## Done signal

Clear ship/no-ship with one reason.

## Guardrails

- Do not publish with failing CI matrix without an explicit exception note.
