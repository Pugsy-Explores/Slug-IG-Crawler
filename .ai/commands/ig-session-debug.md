# Command: ig-session-debug

## Purpose

Diagnose **session / cookie / login / checkpoint** failures without guessing.

## When to use

`login_required`, empty timeline after “success”, checkpoint loops, stale cookies, wrong account context.

## Flow

1. Read `HANDOFF.md` for last known-good profile and mode.
2. Check cookie path and age (see [README.md](../../README.md) `generate_cookies.py`, `cookies.json`).
3. **Grep** session gates:
   ```bash
   rg -n "login_required|checkpoint|LoginRequired|two_factor|challenge|cookies" src/igscraper --glob '*.py' | head -60
   ```
4. Classify: **retryable** (refresh cookie, backoff) vs **terminal** (account action required).
5. If CDP/capture path: note `backends/selenium_backend.py` and capture helpers — do not conflate with parser errors.
6. Apply quick-fix ladder (stop at first success):
   - A) refresh cookie + rerun one target
   - B) verify account/checkpoint state in IG UI
   - C) isolate backend/session code path with focused repro logs
   - D) code fix only after A-C fail

## Output format

- failure class (cookie / checkpoint / rate / unknown)  
- next concrete action  
- **freshness** note (how old is the cookie file?)  

## Done signal

Clear “try X before code change” or “must fix in IG account”.

## Guardrails

- Do not commit real cookies or secrets.  
- Do not disable security checks to “unstick” a run.
