import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# ------------------------------------------------------------------
# Paths (PINNED)
# ------------------------------------------------------------------
CHROME_BINARY = (
    "/Users/shang/my_work/ig_profile_scraper/"
    "chrome-mac-arm64/"
    "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
)
CHROMEDRIVER = "/opt/homebrew/bin/chromedriver"

# ------------------------------------------------------------------
# Chrome setup (Linux-ish)
# ------------------------------------------------------------------
options = Options()
options.binary_location = CHROME_BINARY

# Avoid macOS Chrome UI blockers
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")
options.add_argument("--disable-features=ChromeWhatsNewUI")

# Window parity with Docker
options.add_argument("--window-size=1920,1080")

# Linux-like UA (IMPORTANT)
LINUX_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36"
)
options.add_argument(f"--user-agent={LINUX_UA}")

# Required for modern Chromium
options.add_argument("--remote-debugging-pipe")

service = Service(CHROMEDRIVER)
driver = webdriver.Chrome(service=service, options=options)

try:
    # --------------------------------------------------------------
    # Early JS overrides (before any site loads)
    # --------------------------------------------------------------
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Linux x86_64'
                });
            """
        }
    )

    # --------------------------------------------------------------
    # Login flow
    # --------------------------------------------------------------
    driver.get("https://www.instagram.com/accounts/login/")
    input("👉 Log in manually, then press Enter here...")

    # Stabilize session (VERY important)
    driver.get("about:blank")
    time.sleep(2)

    driver.get("https://www.instagram.com/")
    time.sleep(5)

    cookies = driver.get_cookies()
    if not cookies:
        raise RuntimeError("No cookies captured — login likely failed")

    # --------------------------------------------------------------
    # Save cookies
    # --------------------------------------------------------------
    out_dir = Path("src/igscraper/cookies")
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = out_dir / f"cookies_chromium_linuxish_{int(time.time())}.json"
    with open(filename, "w") as f:
        json.dump(cookies, f, indent=2)

    print(f"✅ {len(cookies)} cookies saved to {filename}")

finally:
    driver.quit()
