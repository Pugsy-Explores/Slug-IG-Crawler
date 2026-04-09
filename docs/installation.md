# Slug-Ig-Crawler — reference

This document is part of the [Slug-Ig-Crawler](../README.md) documentation. Paths are relative to the repository root unless noted.


# Installation

**Slug-Ig-Crawler** is the project name. **PyPI package:** `slug-ig-crawler`. **CLI:** `Slug-Ig-Crawler` (import package remains **`igscraper`**).

| Install | Command |
|--------|---------|
| Latest release from PyPI | `pip install slug-ig-crawler` |
| With screenshot → MP4 helpers (`imageio`) | `pip install "slug-ig-crawler[video]"` |
| Optional JSON5 parsing in the sorter | `pip install "slug-ig-crawler[json5]"` |
| Video + JSON5 together | `pip install "slug-ig-crawler[all]"` |

After install, the **`Slug-Ig-Crawler`** console script is on your `PATH` (legacy alias `igscraper` is still provided for compatibility). Dependencies are declared in **`pyproject.toml`**.

**Chrome / ChromeDriver (macOS and Linux):** `pip` does not download browsers. After `pip install "slug-ig-crawler[all]"` (or any install), run **`Slug-Ig-Crawler bootstrap`** once to fetch Chrome for Testing + matching ChromeDriver for **pinned full version `143.0.7499.169`** (from Google’s known-good index) into **`~/.slug/browser/<platform>/`**, and install a sample **`~/.slug/config.toml`** if missing. Override the build with **`IGSCRAPER_CFT_FULL_VERSION`** (must be a version listed in Google’s JSON). Until binaries exist, the first pipeline run prints a **stderr warning** suggesting bootstrap (silence with `IGSCRAPER_SILENT_BROWSER_CACHE_WARN=1`). Inspect templates with **`Slug-Ig-Crawler show-config`**.

**Publishing to PyPI (maintainers):** see [PYPI_RELEASE.md](PYPI_RELEASE.md) (Trusted Publishing + release checklist; canonical org repo **Pugsyfy/Slug-IG-Crawler**). Release notes are tracked in [CHANGELOG.md](../CHANGELOG.md).



---

## Development from source (git clone)

Use this only when you want to hack on code, run tests, or make local edits.

```bash
git clone https://github.com/Pugsyfy/Slug-IG-Crawler.git
cd Slug-IG-Crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

This installs editable mode with dev/video/json5 extras via `requirements.txt` (`-e .[dev,video,json5]`).
