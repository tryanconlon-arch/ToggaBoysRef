"""
scrape_players.py
-----------------
Pulls the league-wide player stats table for every historical season — both
outfield (OF) and goalkeeper (GK) splits.

Per season:
  1. Navigate to /players
  2. Open the Status/Team filter dropdown, switch from "All Available" to "All"
  3. Click position toggle "OF" → export CSV → players_OF.csv
  4. Click position toggle "G"  → export CSV → players_GK.csv

Output:
  fantrax_data/historical/{year}/players_OF.csv
  fantrax_data/historical/{year}/players_GK.csv
  fantrax_data/historical/{year}/_debug_players_*.png  (on failure)

Prereqs (same as fantrax_history.py):
  - .env with FANTRAX_EMAIL and FANTRAX_PASSWORD
  - seasons_filtered.json with [{year, league_id}, ...]
  - playwright + chromium installed

Usage:
    python scrape_players.py
    python scrape_players.py --year 2024            # single season
    python scrape_players.py --headed               # watch the browser
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

EMAIL        = os.getenv("FANTRAX_EMAIL")
PASSWORD     = os.getenv("FANTRAX_PASSWORD")
SEASONS_PATH = Path("seasons_filtered.json")
OUTPUT_ROOT  = Path("fantrax_data") / "historical"

EXPORT_SELECTORS = [
    "button:has(mat-icon:has-text('get_app'))",
    "button:has(mat-icon:has-text('file_download'))",
    "button:has-text('Export')",
    "button:has-text('CSV')",
    "[aria-label='Export to CSV']",
    "[title='Export to CSV']",
]

# Status/Team filter is a mat-select dropdown. Try several anchors.
STATUS_DROPDOWN_TRIGGERS = [
    "mat-form-field:has-text('Status/Team') mat-select",
    "mat-form-field:has-text('Status') mat-select",
    "mat-select[aria-label*='Status' i]",
    "mat-select:has-text('All Available')",
    "mat-select:has-text('Available')",
]

# Position toggles — try literal labels first, then verbose alternatives.
# ── Helpers ──────────────────────────────────────────────────────────────────

def wait_ready(page, timeout=15000):
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


def close_any_open_panel(page):
    """Force-close any open mat-select / overlay panel by pressing Escape + clicking page edge."""
    try:
        page.keyboard.press("Escape")
        time.sleep(0.2)
        # Some Angular Material setups need a body click to fully dismiss the overlay.
        page.locator("body").click(position={"x": 5, "y": 5}, timeout=1500, force=True)
        time.sleep(0.2)
    except Exception:
        pass


def click_first_visible(page, selectors, description, timeout=3000):
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=timeout):
                el.click()
                print(f"    → {description} via: {sel}")
                return True
        except Exception:
            continue
    print(f"    ! Could not find {description}")
    return False


def click_position_toggle(page, label):
    """Enumerate mat-button-toggle elements and click the one whose inner text matches `label` exactly.
    `:has-text` is substring-matching; for short labels like 'G' that match too broadly,
    we walk the elements and compare normalized text."""
    candidates_locators = ["mat-button-toggle", "button"]
    for loc_sel in candidates_locators:
        try:
            els = page.locator(loc_sel).all()
        except Exception:
            els = []
        for el in els:
            try:
                if not el.is_visible(timeout=500):
                    continue
                txt = (el.inner_text() or "").strip()
            except Exception:
                continue
            if txt == label:
                try:
                    el.click()
                    print(f"    → Clicked position '{label}' (via {loc_sel}, exact-text)")
                    return True
                except Exception:
                    continue
    print(f"    ! No element with exact text '{label}' found")
    return False


def set_status_to_all(page):
    """Open Status/Team dropdown and click the 'All' option."""
    if not click_first_visible(page, STATUS_DROPDOWN_TRIGGERS, "Status/Team dropdown trigger"):
        return False
    time.sleep(0.6)
    # Inside the open mat-select panel, find the option whose visible text is exactly "All".
    try:
        opts = page.locator("mat-option").all()
        # Prefer an exact match on "All"
        for o in opts:
            try:
                txt = o.inner_text().strip()
            except Exception:
                continue
            if txt == "All":
                o.click()
                print(f"    → Selected status: 'All'")
                time.sleep(0.4)
                close_any_open_panel(page)
                return True
        # Fallback: anything starting with "All " that isn't "All Available"
        for o in opts:
            try:
                txt = o.inner_text().strip()
            except Exception:
                continue
            if txt.startswith("All") and "Available" not in txt:
                o.click()
                print(f"    → Selected status: {txt!r}")
                time.sleep(0.4)
                close_any_open_panel(page)
                return True
        print(f"    ! No 'All' option found in dropdown (options: {[o.inner_text().strip() for o in opts[:8]]}...)")
    except Exception as e:
        print(f"    ! Error reading dropdown options: {e}")
    return False


def try_export(page, dest):
    for sel in EXPORT_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                with page.expect_download(timeout=20000) as dl:
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
    wait_ready(page)
    dismiss_banners(page)

    # Poll for visible inputs to appear — Fantrax's Angular SPA can take 1-15s.
    inputs = []
    for attempt in range(30):
        inputs = page.locator("input:visible").all()
        if len(inputs) >= 2:
            break
        time.sleep(1)
        # Some pages need a second banner dismiss after late renders.
        if attempt == 5:
            dismiss_banners(page)

    if len(inputs) < 2:
        page.screenshot(path="_debug_login_no_inputs.png")
        # Dump a snippet of visible text to help debug.
        try:
            text = page.evaluate("() => document.body.innerText.slice(0, 400)")
            print(f"  ! Login form not found after 30s. {len(inputs)} input(s) visible.")
            print(f"    Page text snippet: {text!r}")
        except Exception:
            pass
        raise SystemExit("Login form not found — see _debug_login_no_inputs.png")

    inputs[0].fill(EMAIL)
    inputs[1].fill(PASSWORD)
    page.click(
        "button:has-text('Login'), button:has-text('Log In'), "
        "button:has-text('Sign In'), button[type='submit']"
    )
    wait_ready(page, timeout=20000)
    if "login" in page.url.lower():
        page.screenshot(path="_debug_login_failed.png")
        raise SystemExit("Login failed. See _debug_login_failed.png.")




# ── Stats period + gameweek selectors (weekly mode) ─────────────────────────

STATS_DROPDOWN_TRIGGERS = [
    "mat-form-field:has-text('Stats') mat-select",
    "mat-select:has-text('YTD')",
    "mat-select:has-text('Year to Date')",
]

# Anchors for the per-week selector. Confirmed label is "Gameweek" (one word) —
# distinct from the Stats dropdown whose display text contains "Game Week" after selection.
GAMEWEEK_DROPDOWN_TRIGGERS = [
    "mat-form-field:has(mat-label:has-text('Gameweek')) mat-select",
    "mat-form-field:has-text('Gameweek') mat-select",
    "mat-form-field:has-text('Period') mat-select",
]


def set_stats_to_gameweek(page):
    """Change Stats dropdown from default (e.g. '2024-25 - YTD') to 'Game Week'.
    This reveals a second dropdown for picking a specific week."""
    if not click_first_visible(page, STATS_DROPDOWN_TRIGGERS, "Stats dropdown trigger"):
        return False
    time.sleep(0.6)
    try:
        opts = page.locator("mat-option").all()
        for o in opts:
            try:
                txt = (o.inner_text() or "").strip()
            except Exception:
                continue
            if "Game Week" in txt or "Gameweek" in txt:
                o.click()
                print(f"    → Stats: {txt!r}")
                time.sleep(0.4)
                close_any_open_panel(page)
                return True
        print(f"    ! No 'Game Week' option in Stats dropdown (saw: {[o.inner_text().strip() for o in opts[:8]]})")
    except Exception as e:
        print(f"    ! Stats option select error: {e}")
    return False


def _gameweek_current_value(page):
    """Read what the Gameweek selector currently shows (e.g. '14 (Dec 4 - Dec 10)'). Returns '' on failure."""
    try:
        return page.evaluate("""
            () => {
                const f = Array.from(document.querySelectorAll('mat-form-field'))
                    .find(el => /Gameweek/i.test((el.querySelector('mat-label,label')||{}).textContent||''));
                if(!f) return '';
                const v = f.querySelector('mat-select .mat-mdc-select-value-text, mat-select .mat-select-value-text');
                return (v ? v.textContent : '').trim();
            }
        """) or ""
    except Exception:
        return ""


def _value_is_week(value_text, week):
    """True if a Gameweek dropdown's displayed text matches the given week (e.g. '14 (Dec 4 - Dec 10)' for week=14)."""
    import re as _re
    return bool(_re.match(rf'^\s*{week}\b', value_text or ""))


def select_gameweek(page, week):
    """Open the Gameweek dropdown, pick the given week, ensure panel closed.
    Options look like '1 (Aug 17 - Aug 19)' — match by leading numeric token, not by 'Game Week N'."""
    # Skip work if it already shows the right week.
    current = _gameweek_current_value(page)
    if _value_is_week(current, week):
        return True

    if not click_first_visible(page, GAMEWEEK_DROPDOWN_TRIGGERS, f"Gameweek dropdown"):
        return False
    time.sleep(0.4)

    import re as _re
    pattern = _re.compile(rf'^\s*{week}\b')

    selected = False
    try:
        opts = page.locator("mat-option").all()
        for o in opts:
            try:
                txt = (o.inner_text() or "").strip()
            except Exception:
                continue
            if pattern.match(txt):
                o.click()
                selected = True
                break
    except Exception as e:
        print(f"    ! Gameweek select error for wk{week}: {e}")
        close_any_open_panel(page)
        return False

    time.sleep(0.3)
    close_any_open_panel(page)
    time.sleep(0.4)
    if not selected:
        # Loud one-time message; outer loop will increment fail counter for this week.
        print(f"    ! No mat-option matched leading '{week}' (sample: {[(o.inner_text() or '').strip()[:30] for o in opts[:4]] if 'opts' in dir() else '—'})")
    return selected


def export_season_players_weekly(page, year, league_id):
    out_dir = OUTPUT_ROOT / str(year) / "weekly"
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.fantrax.com/fantasy/league/{league_id}/players"
    print(f"\n=== Season {year}  ({league_id}) weekly ===")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    wait_ready(page)
    dismiss_banners(page)

    # Status → All
    if not set_status_to_all(page):
        page.screenshot(path=str(out_dir / "_debug_status.png"))
        return {"weekly": "✗ status dropdown"}
    wait_ready(page, timeout=5000)

    # Stats → Game Week (reveals the second selector)
    if not set_stats_to_gameweek(page):
        page.screenshot(path=str(out_dir / "_debug_stats.png"))
        return {"weekly": "✗ stats dropdown"}
    # Force-close any lingering open panel so the newly-revealed gameweek selector is visible.
    close_any_open_panel(page)
    wait_ready(page, timeout=5000)
    # Debug: capture page state so I can see what selector to target for the week picker.
    page.screenshot(path=str(out_dir / "_debug_after_stats_gw.png"), full_page=True)
    print(f"    (debug screenshot saved: _debug_after_stats_gw.png)")
    # Dump every visible mat-form-field label + the mat-select's current display text.
    try:
        fields = page.evaluate("""
            () => Array.from(document.querySelectorAll('mat-form-field')).map(f => {
                const lbl = f.querySelector('mat-label, label');
                const val = f.querySelector('mat-select .mat-mdc-select-value-text, mat-select .mat-select-value-text, input');
                return {
                    label: lbl ? lbl.textContent.trim() : '',
                    value: val ? (val.textContent || val.value || '').trim() : '',
                    rect:  f.getBoundingClientRect().y | 0,
                };
            }).filter(f => f.label || f.value);
        """)
        print("    Visible mat-form-fields (label → value):")
        for f in fields:
            print(f"      y={f['rect']:>4}  {f['label']!r:<22} → {f['value']!r}")
    except Exception as e:
        print(f"    (couldn't inspect form fields: {e})")

    summary = {}
    for split_btn, split_label in [("OF", "OF"), ("G", "GK")]:
        print(f"  [{split_label}]")
        close_any_open_panel(page)
        if not click_position_toggle(page, split_btn):
            summary[split_label] = "✗ no toggle"
            continue
        time.sleep(1.0)
        wait_ready(page, timeout=5000)

        ok, skipped, fail = 0, 0, 0
        for wk in range(1, 39):
            dest = out_dir / f"players_{split_label}_wk{wk:02d}.csv"
            if dest.exists() and dest.stat().st_size > 200:
                skipped += 1
                continue
            if not select_gameweek(page, wk):
                fail += 1
                continue
            time.sleep(1.2)
            wait_ready(page, timeout=5000)
            if try_export(page, dest):
                ok += 1
                if ok % 10 == 0 or wk == 38:
                    print(f"    wk{wk:02d}: ✓ ({dest.stat().st_size:,}B; {ok}/{38-skipped} new)")
            else:
                fail += 1
                page.screenshot(path=str(out_dir / f"_debug_{split_label}_wk{wk:02d}.png"))

        summary[split_label] = f"{ok}✓ {skipped}↷ {fail}✗ (of 38)"
        print(f"    → {split_label}: {summary[split_label]}")

    return summary


# ── Per-season export ───────────────────────────────────────────────────────

def export_season_players(page, year, league_id):
    out_dir = OUTPUT_ROOT / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.fantrax.com/fantasy/league/{league_id}/players"
    print(f"\n=== Season {year}  ({league_id}) ===")
    print(f"  goto: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    wait_ready(page)
    dismiss_banners(page)

    # Status → All
    if not set_status_to_all(page):
        page.screenshot(path=str(out_dir / "_debug_players_status.png"))
        print(f"    ⚠ Could not set Status to All — screenshot saved")
    wait_ready(page, timeout=5000)

    results = {}

    # OF
    print(f"  [OF]")
    if click_position_toggle(page, "OF"):
        time.sleep(2)
        wait_ready(page, timeout=5000)
        dest = out_dir / "players_OF.csv"
        if try_export(page, dest):
            size = dest.stat().st_size
            print(f"    ✓ {dest}  ({size:,} bytes)")
            results["OF"] = "✓"
        else:
            page.screenshot(path=str(out_dir / "_debug_players_OF.png"))
            print(f"    ✗ export failed — screenshot saved")
            results["OF"] = "✗"
    else:
        page.screenshot(path=str(out_dir / "_debug_players_OF_toggle.png"))
        results["OF"] = "✗ (no OF toggle)"

    # G
    print(f"  [G]")
    if click_position_toggle(page, "G"):
        time.sleep(2)
        wait_ready(page, timeout=5000)
        dest = out_dir / "players_GK.csv"
        if try_export(page, dest):
            size = dest.stat().st_size
            print(f"    ✓ {dest}  ({size:,} bytes)")
            results["GK"] = "✓"
        else:
            page.screenshot(path=str(out_dir / "_debug_players_GK.png"))
            print(f"    ✗ export failed — screenshot saved")
            results["GK"] = "✗"
    else:
        page.screenshot(path=str(out_dir / "_debug_players_GK_toggle.png"))
        results["GK"] = "✗ (no G toggle)"

    return results


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, help="Only scrape this one year")
    ap.add_argument("--headed", action="store_true", help="Run browser visible (debugging)")
    ap.add_argument("--weekly", action="store_true", help="Per-gameweek scrape mode (38 weeks × OF+GK per season). Skips files already on disk.")
    args = ap.parse_args()

    if not EMAIL or not PASSWORD:
        raise SystemExit("FANTRAX_EMAIL and FANTRAX_PASSWORD must be set in .env")
    if not SEASONS_PATH.exists():
        raise SystemExit(f"{SEASONS_PATH} not found.")

    seasons = json.loads(SEASONS_PATH.read_text())
    if args.year:
        seasons = [s for s in seasons if int(s["year"]) == args.year]
        if not seasons:
            raise SystemExit(f"No season found for year {args.year}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not args.headed,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            accept_downloads=True,
        )
        page = ctx.new_page()

        print("Logging in...")
        login(page)
        print(f"  ✓ Logged in")

        exporter = export_season_players_weekly if args.weekly else export_season_players
        for s in seasons:
            try:
                summary[s["year"]] = exporter(page, s["year"], s["league_id"])
            except Exception as e:
                print(f"  ! Error for {s['year']}: {e}")
                summary[s["year"]] = {"OF": f"✗ ({e})", "GK": "✗"}

        browser.close()

    print("\n── Summary ─────────────────────────────────────────────────")
    for year in sorted(summary):
        st = summary[year]
        parts = [f"{k}={v}" for k, v in st.items()]
        print(f"  {year}:  " + "  ".join(parts))
    print(f"\n  Data root: {OUTPUT_ROOT.resolve()}\n")


if __name__ == "__main__":
    main()
