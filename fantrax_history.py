"""
fantrax_history.py
------------------
Pulls standings.csv and transaction_history.csv for every past Fantrax league
listed in `seasons_filtered.json`.

Prereq:
    1. Run `discover_seasons.py` once.
    2. Open the resulting `seasons.json`, keep only the ToggaBoys entries,
       set `year` on each, and save as `seasons_filtered.json`:

        [
            {"year": 2018, "league_id": "abc123..."},
            {"year": 2019, "league_id": "def456..."},
            ...
        ]

Usage:
    python fantrax_history.py

Output:
    fantrax_data/historical/{year}/standings.csv
    fantrax_data/historical/{year}/transactions.csv
    fantrax_data/historical/{year}/_debug_*.png   (only if an export failed)

Credentials are read from .env (same as fantrax_export.py).
"""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

EMAIL         = os.getenv("FANTRAX_EMAIL")
PASSWORD      = os.getenv("FANTRAX_PASSWORD")
SEASONS_PATH  = Path("seasons_filtered.json")
OUTPUT_ROOT   = Path("fantrax_data") / "historical"

EXPORT_SELECTORS = [
    "button:has(mat-icon:has-text('get_app'))",
    "button:has(mat-icon:has-text('file_download'))",
    "button:has-text('Export')",
    "button:has-text('CSV')",
    "a:has-text('Export')",
    "a:has-text('CSV')",
    "[aria-label='Export to CSV']",
    "[title='Export to CSV']",
]

HEADLESS = True


# ── Helpers ─────────────────────────────────────────────────────────────────

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


def try_export(page, dest: Path) -> bool:
    for sel in EXPORT_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                with page.expect_download(timeout=15000) as dl:
                    btn.click()
                dl.value.save_as(str(dest))
                return True
        except PlaywrightTimeout:
            continue
        except Exception:
            continue
    return False


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


# ── Per-season export ───────────────────────────────────────────────────────

def export_season(page, year, league_id):
    out_dir = OUTPUT_ROOT / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"https://www.fantrax.com/fantasy/league/{league_id}"

    print(f"\n=== Season {year}  ({league_id}) ===")
    results = {}

    # ── Standings ──────────────────────────────────────────────────────────
    url = f"{base}/standings"
    print(f"[standings] {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        wait_for_page_ready(page)
        dismiss_banners(page)
        dest = out_dir / "standings.csv"
        if try_export(page, dest):
            print(f"  ✓ {dest}")
            results["standings"] = "✓"
        else:
            page.screenshot(path=str(out_dir / "_debug_standings.png"))
            print(f"  ✗ no export button found — screenshot saved")
            results["standings"] = "✗"
    except Exception as e:
        print(f"  ! {e}")
        results["standings"] = f"✗ ({e})"

    # ── Transactions ───────────────────────────────────────────────────────
    url = f"{base}/transactions/history"
    print(f"[transactions] {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        wait_for_page_ready(page)
        dismiss_banners(page)
        # The Transactions nav sometimes needs to be expanded; mirrors fantrax_export.py.
        try:
            page.click("button:has-text('Transactions')", timeout=3000)
            time.sleep(1)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            wait_for_page_ready(page)
        except PlaywrightTimeout:
            pass
        dest = out_dir / "transactions.csv"
        if try_export(page, dest):
            print(f"  ✓ {dest}")
            results["transactions"] = "✓"
        else:
            page.screenshot(path=str(out_dir / "_debug_transactions.png"))
            print(f"  ✗ no export button found — screenshot saved")
            results["transactions"] = "✗"
    except Exception as e:
        print(f"  ! {e}")
        results["transactions"] = f"✗ ({e})"

    return results


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not EMAIL or not PASSWORD:
        raise SystemExit("FANTRAX_EMAIL and FANTRAX_PASSWORD must be set in .env")
    if not SEASONS_PATH.exists():
        raise SystemExit(
            f"{SEASONS_PATH} not found.\n"
            "Run discover_seasons.py first, then filter the output to the ToggaBoys leagues."
        )

    seasons = json.loads(SEASONS_PATH.read_text())
    if not isinstance(seasons, list):
        raise SystemExit("seasons_filtered.json must be a list of {year, league_id} objects.")
    for s in seasons:
        if "year" not in s or "league_id" not in s:
            raise SystemExit(f"Bad season entry (need 'year' and 'league_id'): {s}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            accept_downloads=True,
        )
        page = ctx.new_page()

        print("Logging in...")
        login(page)
        print(f"  ✓ Logged in (now at: {page.url})")

        for s in seasons:
            summary[s["year"]] = export_season(page, s["year"], s["league_id"])

        browser.close()

    print("\n── Summary ─────────────────────────────────────────────────")
    for year in sorted(summary):
        st = summary[year]
        print(f"  {year}:  standings={st.get('standings')}  transactions={st.get('transactions')}")
    print(f"\n  Data root: {OUTPUT_ROOT.resolve()}\n")


if __name__ == "__main__":
    main()
