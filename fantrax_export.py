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
import time
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
# Each entry: (label, url_suffix)
# URLs verified against live league navigation.
# Excluded: /matchups, /livescoring, /draft-results — visual-only pages, no CSV export.
SECTIONS = [
    ("standings",            "/standings"),
    ("roster",               "/team/roster"),
    ("players",              "/players"),
    ("transaction_history",  "/transactions/history"),
]

# Selectors for the CSV export button.
# Fantrax uses Angular Material with get_app mat-icon inside mdc-icon-button.
EXPORT_SELECTORS = [
    "button:has(mat-icon:has-text('get_app'))",   # confirmed via DOM inspection
    "button:has(mat-icon:has-text('file_download'))",
    "button:has-text('Export')",
    "button:has-text('CSV')",
    "a:has-text('Export')",
    "a:has-text('CSV')",
    "[aria-label='Export to CSV']",
    "[title='Export to CSV']",
    ".export-btn",
    ".csv-export",
    "[data-test='export-button']",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def wait_for_page_ready(page, timeout=15000):
    """Wait for the Angular/JS app to finish rendering."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeout:
        pass  # Angular SPAs often don't reach networkidle; fall through
    time.sleep(2)  # extra buffer for Angular change detection


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


# ── Custom exports ───────────────────────────────────────────────────────────

TRADE_TOGGLE_SELECTORS = [
    "button:has-text('Trades')",
    "mat-tab:has-text('Trades')",
    "[role='tab']:has-text('Trades')",
    "mat-button-toggle:has-text('Trades')",
    "label:has-text('Trades')",
]

ALL_PLAYERS_SELECTORS = [
    "button:has-text('All')",
    "mat-button-toggle:has-text('All')",
    "[role='tab']:has-text('All')",
    "label:has-text('All')",
]

OUTFIELD_SELECTORS = [
    "button:has-text('Outfield Players')",
    "mat-button-toggle:has-text('Outfield Players')",
    "button:has-text('Outfield')",
    "label:has-text('Outfield')",
]


def click_first_visible(page, selectors, description, timeout=3000):
    """Try selectors in order; click the first visible one. Returns True on success."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=timeout):
                el.click()
                print(f"  → Clicked {description} via: {sel}")
                return True
        except (PlaywrightTimeout, Exception):
            continue
    print(f"  ! Could not find {description}")
    return False


def export_trades(page, download_dir):
    """Navigate to transactions/history, toggle to Trades view, export CSV."""
    url = BASE_URL + "/transactions/history"
    print(f"[trades] {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        wait_for_page_ready(page)

        for banner_text in ["Never", "Dismiss", "No thanks"]:
            try:
                page.click(f"button:has-text('{banner_text}')", timeout=1500)
                time.sleep(0.3)
            except PlaywrightTimeout:
                pass

        # Expand Transactions nav if needed (same as existing pattern)
        try:
            page.click("button:has-text('Transactions')", timeout=3000)
            time.sleep(1)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            wait_for_page_ready(page)
        except PlaywrightTimeout:
            pass

        click_first_visible(page, TRADE_TOGGLE_SELECTORS, "Trades toggle")
        time.sleep(2)

        success = try_export(page, "trades", download_dir)
        if not success:
            screenshot(page, "trades", download_dir)
        return success
    except Exception as e:
        print(f"  ! Error on trades: {e}")
        screenshot(page, "trades", download_dir)
        return False


def export_all_players(page, download_dir):
    """Navigate to players, switch to All + Outfield Players filters, export CSV."""
    url = BASE_URL + "/players"
    print(f"[all_players] {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        wait_for_page_ready(page)

        for banner_text in ["Never", "Dismiss", "No thanks"]:
            try:
                page.click(f"button:has-text('{banner_text}')", timeout=1500)
                time.sleep(0.3)
            except PlaywrightTimeout:
                pass

        click_first_visible(page, ALL_PLAYERS_SELECTORS, "All players filter")
        time.sleep(2)

        click_first_visible(page, OUTFIELD_SELECTORS, "Outfield Players filter")
        time.sleep(2)

        success = try_export(page, "all_players", download_dir)
        if not success:
            screenshot(page, "all_players", download_dir)
        return success
    except Exception as e:
        print(f"  ! Error on all_players: {e}")
        screenshot(page, "all_players", download_dir)
        return False


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
        page.goto("https://www.fantrax.com/login", wait_until="domcontentloaded", timeout=30000)
        wait_for_page_ready(page)

        # Dismiss cookie banner if present
        try:
            page.click("button:has-text('Dismiss')", timeout=4000)
            time.sleep(0.5)
        except PlaywrightTimeout:
            pass

        # Handle the login form — Fantrax uses Angular Material inputs
        try:
            # Angular Material inputs: first input = email, second = password
            inputs = page.locator("input").all()
            if len(inputs) < 2:
                # Wait a bit more for Angular to render
                time.sleep(3)
                inputs = page.locator("input").all()
            inputs[0].fill(EMAIL)
            inputs[1].fill(PASSWORD)
            page.click("button:has-text('Login'), button:has-text('Log In'), button:has-text('Sign In'), button[type='submit']")
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
        for label, suffix in SECTIONS:
            url = BASE_URL + suffix
            print(f"[{label}] {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                wait_for_page_ready(page)

                # Dismiss notification/cookie banners that can block clicks
                for banner_text in ["Never", "Dismiss", "No thanks"]:
                    try:
                        page.click(f"button:has-text('{banner_text}')", timeout=1500)
                        time.sleep(0.3)
                    except PlaywrightTimeout:
                        pass

                # Transaction sub-pages require expanding the Transactions nav first
                if "transactions" in suffix:
                    try:
                        page.click("button:has-text('Transactions')", timeout=3000)
                        time.sleep(1)
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        wait_for_page_ready(page)
                    except PlaywrightTimeout:
                        pass

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

        # ── Step 3: Custom toggle/filter exports ──────────────────────────
        results["trades"]      = "✓" if export_trades(page, OUTPUT_DIR)      else "✗"
        results["all_players"] = "✓" if export_all_players(page, OUTPUT_DIR) else "✗"

        browser.close()

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n── Export Summary ──────────────────────────────────────────")
    for label, status in results.items():
        print(f"  {status:30s}  {label}")

    exported = [k for k, v in results.items() if v == "✓"]
    failed   = [k for k, v in results.items() if v != "✓"]

    print(f"\n  Exported: {len(exported)} / {len(results)} sections")
    if failed:
        print(f"  Failed:   {', '.join(failed)}")
        print("\n  Tip: Check the _debug_*.png screenshots in the output folder")
        print("  to see what the page looked like when export wasn't found.")
    print(f"\n  All files in: {OUTPUT_DIR.resolve()}\n")


if __name__ == "__main__":
    main()
