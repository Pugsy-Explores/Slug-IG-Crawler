# Command: ig-selector-audit

## Purpose

**Locate and triage** DOM/CSS/XPath surfaces when IG breaks or before a risky change.

## When to use

Empty post lists, wrong grid, modal failures, comment container not found, carousel stuck.

## Flow

1. Read [audit-output-igscraper/executive_summary.md](../../audit-output-igscraper/executive_summary.md) “If Instagram Breaks Tomorrow”.
2. **Grep** selectors (run from repo root):
   ```bash
   rg -n "By\.|CSS_SELECTOR|XPath|aria-label|_ac[0-9a-z]+|html-div" src/igscraper/pages src/igscraper/backends --glob '*.py' | head -80
   rg -n "POST_SELECTOR|find_element|WebDriverWait" src/igscraper/pages --glob '*.py'
   ```
3. Map **symptom → file → function** (note [docs/architecture/selector-inventory.md](../../docs/architecture/selector-inventory.md) when present).
4. Decide: **minimal selector patch** vs **structural** change (new page helper).
5. If changing selectors, plan a **local** repro (profile/post URL) — CI rarely covers browser.

## Output format

- hotspot list (file:line, purpose)  
- recommended first edit  
- **retryable** after fix? (usually yes for pure selector; no if login wall)  
- confidence score (0-100) that first edit fixes the reported break  

## Done signal

You can name the **single best file** to open first.

## Guardrails

- Prefer `pages/` over new one-off locators in `utils.py` when practical.  
- Do not “fix” by disabling waits without evidence.
