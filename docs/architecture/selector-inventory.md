# Selector inventory (starter)

**Purpose:** Fast triage when DOM breaks. Expand as you fix incidents. Full fragility discussion: [audit-output-igscraper/executive_summary.md](../../audit-output-igscraper/executive_summary.md) § "If Instagram Breaks Tomorrow".

| Feature | Primary file | Notes |
|---------|----------------|-------|
| Profile grid post links (`/p/`, `/reel/`) | `src/igscraper/pages/profile_page.py` | XPath / `_ac7v`-style minified classes — **high drift** |
| Comment container | `src/igscraper/backends/selenium_backend.py` | e.g. `find_comment_container`, `div.html-div` fallback |
| Reply expansion | `src/igscraper/services/replies_expander.py` | Click loops, rate heuristics |
| Carousel next / media list | `src/igscraper/utils.py` | `aria-label='Next'`, `ul._acay` / `li._acaz` patterns |
| Generic waits / clicks | `src/igscraper/utils.py`, `pages/` | Prefer consolidating new locators under `pages/` |

## When editing selectors

1. Run **`ig-selector-audit`** (`.ai/commands/ig-selector-audit.md`) grep steps.
2. Reproduce locally with **headed** Chrome and a known profile/post URL.
3. Add or update **fixtures/tests** only for parser/capture contracts — full E2E is manual unless you add dedicated automation.
