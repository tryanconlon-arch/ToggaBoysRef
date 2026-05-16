"""
discover_seasons.py
-------------------
Logs into Fantrax, visits the leagues archive, and dumps every league this
account has access to (across all years) to `seasons.json`. Also saves
`_debug_archive.png` so you can sanity-check the page.

Why this exists: the ToggaBoys league has run since 2018 with a NEW
Fantrax league_id every season. To pull historical data we first need to
know every past league_id.

Usage:
    python discover_seasons.py

Credentials are read from .env:
    FANTRAX_EMAIL=your@email.com
    FANTRAX_PASSWORD=yourpassword

After it runs:
    1. Open `seasons.json`. It contains every league this account belongs to.
    2. Keep only the ToggaBoys entries, set the `year` field on each, and
       save the result as `seasons_filtered.json` in this format:

        [
            {"year": 2018, "league_id": "abc123..."},
            {"year": 2019, "league_id": "def456..."},
            ...
        ]

    3. Then run `fantrax_history.py` to pull standings + transactions for
       each season.
"""

import os
import re
import json
import time
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

EMAIL       = os.getenv("FANTRAX_EMAIL")
PASSWORD    = os.getenv("FANTRAX_PASSWORD")
ARCHIVE_URL = "https://www.fantrax.com/fantasy/league/all;view=LEAGUES"
OUT_JSON    = Path("seasons.json")
DEBUG_PNG   = Path("_debug_archive.png")

# Headless=False on first run so you can watch what's happening; flip later.
HEADLESS = False


# ── Helpers (mirrors fantrax_export.py) ─────────────────────────────────────

def wait_for_page_ready(page, timeout=15000):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeout:
        pass
    time.sleep(2)


def dismiss_banners(page):
    for txt in ["Never", "Dismiss", "No thanks"]:
        try:
            page.click(f"button:has-text('{txt}')", timeout=1500)
            time.sleep(0.3)
        except PlaywrightTimeout:
            pass


def login(page):
    page.goto("https://www.fantrax.com/login", wait_until="domcontentloaded", timeout=30000)
    wait_for_page_ready(page)
    dismiss_banners(page)

    inputs = page.locator("input").all()
    if len(inputs) < 2:
        time.sleep(3)
        inputs = page.locator("input").all()
    inputs[0].fill(EMAIL)
    inputs[1].fill(PASSWORD)
    page.click(
        "button:has-text('Login'), button:has-text('Log In'), "
        "button:has-text('Sign In'), button[type='submit']"
    )
    wait_for_page_ready(page, timeout=20000)
    if "login" in page.url.lower():
        page.screenshot(path="_debug_login_failed.png")
        raise SystemExit("Login failed. See _debug_login_failed.png.")


# ── Discovery ───────────────────────────────────────────────────────────────

LEAGUE_HREF_RE = re.compile(r"/fantasy/league/([a-z0-9]{12,})", re.IGNORECASE)


def scrape_archive(page):
    """Return a list of dicts describing every league found on the archive page."""
    page.goto(ARCHIVE_URL, wait_until="domcontentloaded", timeout=30000)
    wait_for_page_ready(page)
    dismiss_banners(page)
    # Let lazy-loaded league cards render.
    time.sleep(3)
    # Scroll to ensure everything is laid out.
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)

    page.screenshot(path=str(DEBUG_PNG), full_page=True)

    anchors = page.locator("a[href*='/fantasy/league/']").all()
    leagues = []
    seen = set()

    for a in anchors:
        try:
            href = a.get_attribute("href") or ""
        except Exception:
            continue
        m = LEAGUE_HREF_RE.search(href)
        if not m:
            continue
        league_id = m.group(1)
        # Skip the archive page itself ("all").
        if league_id.lower() == "all":
            continue
        if league_id in seen:
            continue
        seen.add(league_id)

        link_text = ""
        try:
            link_text = (a.inner_text() or "").strip()
        except Exception:
            pass

        # Grab surrounding row text for context (year, sport, etc.).
        row_text = link_text
        try:
            row = a.locator("xpath=ancestor::*[self::tr or self::li or "
                            "contains(@class,'card') or contains(@class,'row') or "
                            "contains(@class,'league')][1]")
            if row.count():
                row_text = (row.first.inner_text() or "").strip()
        except Exception:
            pass

        year_match = re.search(r"\b(20\d{2})\b", row_text)
        year_guess = int(year_match.group(1)) if year_match else None

        leagues.append({
            "league_id": league_id,
            "label": link_text,
            "year_guess": year_guess,
            "context_text": row_text[:300],
            "href": href,
        })

    return leagues


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not EMAIL or not PASSWORD:
        raise SystemExit("FANTRAX_EMAIL and FANTRAX_PASSWORD must be set in .env")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        print("Logging in...")
        login(page)
        print(f"  ✓ Logged in (now at: {page.url})")

        print(f"\nNavigating to leagues archive...\n  {ARCHIVE_URL}")
        leagues = scrape_archive(page)

        OUT_JSON.write_text(json.dumps(
            {
                "discovered_at": date.today().isoformat(),
                "archive_url":   ARCHIVE_URL,
                "league_count":  len(leagues),
                "leagues":       leagues,
            },
            indent=2,
        ))

        print(f"\nFound {len(leagues)} leagues.")
        print(f"  Wrote {OUT_JSON.resolve()}")
        print(f"  Wrote {DEBUG_PNG.resolve()}")
        print()
        print("Next: open seasons.json, keep only the ToggaBoys leagues, fill in")
        print("the correct `year` for each, and save as seasons_filtered.json:")
        print('  [{"year": 2018, "league_id": "..."}, {"year": 2019, ...}, ...]')

        browser.close()


if __name__ == "__main__":
    main()
