"""
fantrax_export.py
-----------------
Downloads all available CSV exports from a Fantrax fantasy league.

Requirements:
    pip install playwright python-dotenv
    playwright install chromium

Usage:
    python fantrax_export.py

Credentials are read from a .env file in the same directory:
    FANTRAX_EMAIL=your@email.com
    FANTRAX_PASSWORD=yourpassword

Output is saved to: ./fantrax_data/YYYY-MM-DD/
"""

import os
import re
import time
import shutil
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Config ──────────────────────────────────────────────────────────────────

load_dotenv()

LEAGUE_ID   = "q5ykvvbmmdj5i0kx"
BASE_URL    = f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}"
EMAIL       = os.getenv("FANTRAX_EMAIL")
PASSWORD    = os.getenv("FANTRAX_PASSWORD")
OUTPUT_DIR  = Path("fantrax_data") / str(date.today())

# Fantrax sections to visit, in order.
# Each entry: (label, url_suffix, needs_export_click)
SECTIONS = [
    ("standings",       "/standings",                       True),
    ("rosters",         "/rosters",                         True),
    ("players",         "/players",                         True),
    ("scoring",         "/scoring",                         True),
    ("matchups",        "/matchups",                        True),
    ("transactions",    "/transactions",                    True),
    ("draft_results",   "/draft/results",                   True),
    ("team_stats",      "/stats/team",                      True),
    ("schedule",        "/schedule",                        True),
    ("trade_history",   "/transactions/trades",             True),
    ("waiver_history",  "/transactions/waivers",            True),
]

# Selectors for the CSV export button — Fantrax uses several patterns
EXPORT_SELECTORS = [
    "button:has-text('Export')",
    "button:has-text('CSV')",
    "a:has-text('Export')",
    "a:has-text('CSV')",
    "[aria-label='Export to CSV']",
    "[title='Export to CSV']",
    ".export-btn",
    ".csv-export",
    "mat-icon:has-text('file_download')",       # Angular Material icon
    "[data-test='export-button']",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def wait_for_page_ready(page, timeout=15000):
    """Wait for the Angular/JS app to finish rendering."""
    page.wait_for_load_state("networkidle", timeout=timeout)
    time.sleep(1.5)  # extra buffer for Angular change detection


def try_export(page, label, download_dir):
    """
    Attempt to find and click an export/CSV button on the current page.
    Returns True if a download was triggered, False otherwise.
    """
    for selector in EXPORT_SELECTORS:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=2000):
                print(f"  → Found export button via: {selector}")
                with page.expect_download(timeout=15000) as dl_info:
                    btn.click()
                download = dl_info.value
                dest = download_dir / f"{label}.csv"
                download.save_as(dest)
                print(f"  ✓ Saved: {dest}")
                return True
        except PlaywrightTimeout:
            continue
        except Exception as e:
            print(f"  ! Error with selector '{selector}': {e}")
            continue

    # Fallback: look for any link whose href looks like a CSV download
    try:
        csv_links = page.locator("a[href*='export'], a[href*='.csv'], a[href*='download']").all()
        for link in csv_links:
            href = link.get_attribute("href") or ""
            if any(k in href.lower() for k in ["export", "csv", "download"]):
                print(f"  → Found CSV link: {href}")
                with page.expect_download(timeout=15000) as dl_info:
                    link.click()
                download = dl_info.value
                dest = download_dir / f"{label}.csv"
                download.save_as(dest)
                print(f"  ✓ Saved: {dest}")
                return True
    except Exception as e:
        print(f"  ! Fallback link search failed: {e}")

    return False


def screenshot(page, label, download_dir):
    """Save a screenshot for debugging when export fails."""
    path = download_dir / f"_debug_{label}.png"
    page.screenshot(path=str(path))
    print(f"  ⚠ No export found. Debug screenshot: {path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not EMAIL or not PASSWORD:
        raise SystemExit(
            "FANTRAX_EMAIL and FANTRAX_PASSWORD must be set in your .env file."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nFantrax Export — {date.today()}")
    print(f"Output dir: {OUTPUT_DIR.resolve()}\n")

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            accept_downloads=True,
        )
        page = context.new_page()

        # ── Step 1: Log in ────────────────────────────────────────────────
        print("Logging in...")
        page.goto("https://www.fantrax.com/login", wait_until="networkidle")
        wait_for_page_ready(page)

        # Handle the login form — Fantrax uses Angular reactive forms
        try:
            page.fill("input[type='email'], input[name='email'], #email", EMAIL)
            page.fill("input[type='password'], input[name='password'], #password", PASSWORD)
            page.click("button[type='submit'], button:has-text('Log In'), button:has-text('Sign In')")
            wait_for_page_ready(page, timeout=20000)
        except Exception as e:
            page.screenshot(path=str(OUTPUT_DIR / "_debug_login.png"))
            raise SystemExit(f"Login failed: {e}\nSee _debug_login.png for the page state.")

        # Verify login succeeded
        if "login" in page.url.lower():
            page.screenshot(path=str(OUTPUT_DIR / "_debug_login_failed.png"))
            raise SystemExit(
                "Still on login page after submit — check credentials or see _debug_login_failed.png"
            )
        print(f"  ✓ Logged in (landed on: {page.url})\n")

        # ── Step 2: Visit each section and export ─────────────────────────
        for label, suffix, _ in SECTIONS:
            url = BASE_URL + suffix
            print(f"[{label}] {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                wait_for_page_ready(page)

                success = try_export(page, label, OUTPUT_DIR)
                results[label] = "✓" if success else "✗ (no export button found)"

                if not success:
                    screenshot(page, label, OUTPUT_DIR)

            except PlaywrightTimeout:
                print(f"  ! Timed out loading {url}")
                results[label] = "✗ (page timeout)"
                screenshot(page, label, OUTPUT_DIR)
            except Exception as e:
                print(f"  ! Error on {label}: {e}")
                results[label] = f"✗ ({e})"

        browser.close()

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n── Export Summary ──────────────────────────────────────────")
    for label, status in results.items():
        print(f"  {status:30s}  {label}")

    exported = [k for k, v in results.items() if v == "✓"]
    failed   = [k for k, v in results.items() if v != "✓"]

    print(f"\n  Exported: {len(exported)} / {len(SECTIONS)} sections")
    if failed:
        print(f"  Failed:   {', '.join(failed)}")
        print("\n  Tip: Check the _debug_*.png screenshots in the output folder")
        print("  to see what the page looked like when export wasn't found.")
    print(f"\n  All files in: {OUTPUT_DIR.resolve()}\n")


if __name__ == "__main__":
    main()
