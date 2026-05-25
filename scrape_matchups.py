"""
scrape_matchups.py
------------------
DOM-scrapes weekly matchup scores from the Fantrax /livescoring page.

The /matchups page is only a schedule (shows "vs", no scores).
The /livescoring page has real scores accessible via a Gameweek dropdown.

Structure found on /livescoring sidebar:
  .matchup-list__wrapper  — one per matchup pair
    section.matchup-list (away team)
      h4.matchup-list__name
      h3.matchup-list__score-secondary   ← clean decimal "103.22"
    section.matchup-list (home team)
      h4.matchup-list__name
      h3.matchup-list__score-secondary

Week navigation: league-livescoring-filters-period mat-select dropdown.

Usage:
    DISCOVER=1 python3 scrape_matchups.py   # screenshot + stop after first week
    python3 scrape_matchups.py              # all seasons in seasons_filtered.json
    python3 scrape_matchups.py --year 2025  # single season only

Output:  matchups_{year}.csv  columns: year, week, t1_team, t2_team, t1_score, t2_score

Credentials from .env:
    FANTRAX_EMAIL=your@email.com
    FANTRAX_PASSWORD=yourpassword
"""

import os
import re
import csv
import time
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

EMAIL        = os.getenv("FANTRAX_EMAIL")
PASSWORD     = os.getenv("FANTRAX_PASSWORD")
SEASONS_PATH = Path("seasons_filtered.json")
DISCOVER     = os.getenv("DISCOVER", "0") == "1"
HEADLESS     = not DISCOVER


# ── Helpers ──────────────────────────────────────────────────────────────────

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


def open_gameweek_dropdown(page):
    """
    Click the Gameweek mat-select trigger to open the dropdown.
    If it's already open (aria-expanded=true), closes first then reopens.
    Returns True on success.
    """
    sel = "league-livescoring-filters-period mat-select"
    try:
        el = page.locator(sel).first
        el.wait_for(state="visible", timeout=8000)
        # If already open, close it first.
        expanded = el.get_attribute("aria-expanded") or ""
        if expanded.lower() == "true":
            page.keyboard.press("Escape")
            time.sleep(0.4)
        el.click()
        time.sleep(0.8)
        return True
    except Exception as e:
        print(f"    ✗ Could not open gameweek dropdown: {e}")
        return False


def get_dropdown_week_count(page):
    """Return the number of gameweeks available (dropdown must be open)."""
    try:
        page.wait_for_selector("mat-option", timeout=5000)
        time.sleep(0.3)
        return page.locator("mat-option").count()
    except PlaywrightTimeout:
        return 0


def close_dropdown(page):
    """Press Escape to close the dropdown without selecting."""
    try:
        page.keyboard.press("Escape")
        time.sleep(0.4)
    except Exception:
        pass


def select_week_by_number(page, week_num):
    """
    Open the dropdown fresh, find the option matching week_num, click it.
    Returns True on success.  Never stores stale option element references.
    """
    if not open_gameweek_dropdown(page):
        return False
    try:
        page.wait_for_selector("mat-option", timeout=5000)
        time.sleep(0.3)
        opts = page.locator("mat-option").all()
        for opt in opts:
            try:
                label = (opt.inner_text() or "").strip()
                if parse_week_number(label) == week_num:
                    opt.scroll_into_view_if_needed()
                    opt.click()
                    time.sleep(0.5)
                    wait_for_page_ready(page, timeout=10000)
                    return True
            except Exception:
                continue
    except PlaywrightTimeout:
        pass
    close_dropdown(page)
    return False


def extract_matchups_from_sidebar(page, year, week):
    """
    Extract all matchup scores from the sidebar.

    Structure: one .matchup-list__wrapper contains multiple <a> elements.
    Each <a> = one matchup, with two section.matchup-list children (away, home).
    """
    rows = []
    try:
        # Each <a> inside the wrapper is one matchup pair.
        anchors = page.locator(".matchup-list__wrapper a").all()
        for anchor in anchors:
            try:
                sections = anchor.locator("section.matchup-list").all()
                if len(sections) < 2:
                    continue

                names  = []
                scores = []
                for sec in sections[:2]:
                    try:
                        name_el  = sec.locator(".matchup-list__name").first
                        score_el = sec.locator(".matchup-list__score-secondary").first
                        n = (name_el.inner_text()  or "").strip()
                        s = (score_el.inner_text() or "").strip()
                        names.append(n)
                        scores.append(s)
                    except Exception:
                        names.append("")
                        scores.append("")

                if len(names) == 2 and names[0] and names[1]:
                    s1 = _parse_score(scores[0])
                    s2 = _parse_score(scores[1])
                    if s1 is None and s2 is None:
                        continue  # no scores yet (future/in-progress week)
                    rows.append({
                        "year": year,
                        "week": week,
                        "t1_team": names[0],
                        "t2_team": names[1],
                        "t1_score": s1 if s1 is not None else 0.0,
                        "t2_score": s2 if s2 is not None else 0.0,
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"    ✗ Error scraping sidebar: {e}")
    return rows


def _parse_score(text):
    text = (text or "").strip()
    try:
        return float(re.sub(r"[^\d.]", "", text))
    except (ValueError, TypeError):
        return None


def parse_week_number(label):
    """Extract integer week number from a label like 'Gameweek 1' or 'GW 5'."""
    m = re.search(r"\b(\d+)\b", label)
    return int(m.group(1)) if m else None


# ── Per-season scrape ─────────────────────────────────────────────────────────

def _read_done_weeks(out_path):
    """Return the set of week numbers already present in a matchups CSV."""
    done = set()
    try:
        with open(out_path, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    done.add(int(row["week"]))
                except (ValueError, KeyError, TypeError):
                    pass
    except Exception:
        pass
    return done


# Fast-skip threshold: if a CSV already contains weeks up to or beyond this,
# treat the season as complete and don't even load the page.
COMPLETE_WEEK_THRESHOLD = 35


def scrape_season(page, year, league_id):
    """
    Scrape one season. Writes incrementally to matchups_{year}.csv as each
    week completes, so an interrupted run loses at most one week of work.
    On restart, weeks already in the CSV are skipped.
    """
    url = f"https://www.fantrax.com/fantasy/league/{league_id}/livescoring"
    out_path = Path(f"matchups_{year}.csv")

    print(f"\n=== Season {year}  ({league_id}) ===")

    # Read prior progress (if any).
    done_weeks = _read_done_weeks(out_path) if (out_path.exists() and not DISCOVER) else set()

    # Fast-skip seasons that already look complete.
    if done_weeks and max(done_weeks) >= COMPLETE_WEEK_THRESHOLD:
        print(f"  ✓ {out_path} appears complete "
              f"({len(done_weeks)} weeks, max wk {max(done_weeks)}) — skipping")
        return []

    if done_weeks:
        print(f"  Resuming: {len(done_weeks)} week(s) already scraped "
              f"(max wk {max(done_weeks)}). Continuing from where it left off.")

    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    wait_for_page_ready(page)
    dismiss_banners(page)

    # Open the Gameweek dropdown once to count available weeks.
    if not open_gameweek_dropdown(page):
        page.screenshot(path=f"_debug_matchups_{year}_no_dropdown.png")
        print(f"  ✗ Gameweek dropdown not found — screenshot saved. Skipping.")
        return []

    if DISCOVER:
        page.screenshot(path=f"_debug_matchups_{year}_dropdown_open.png", full_page=False)

    n_weeks = get_dropdown_week_count(page)
    print(f"  Found {n_weeks} gameweek option(s) in dropdown")

    if n_weeks == 0:
        close_dropdown(page)
        page.screenshot(path=f"_debug_matchups_{year}_no_options.png")
        print(f"  ✗ No options in dropdown — screenshot saved. Skipping.")
        return []

    # Close dropdown; select_week_by_number will reopen fresh each time.
    close_dropdown(page)

    if DISCOVER:
        print(f"  [DISCOVER] Selecting week 1 and screenshotting...")
        if select_week_by_number(page, 1):
            rows = extract_matchups_from_sidebar(page, year, 1)
            print(f"  [DISCOVER] Found {len(rows)} matchup row(s) in sidebar")
        page.screenshot(path=f"_debug_matchups_{year}_wk1.png", full_page=False)
        return []

    # Open CSV in append mode; write header only if the file is new.
    write_header = not out_path.exists()
    csv_file = open(out_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        csv_file,
        fieldnames=["year", "week", "t1_team", "t2_team", "t1_score", "t2_score"],
    )
    if write_header:
        writer.writeheader()
        csv_file.flush()

    new_count = 0
    try:
        for week_num in range(1, n_weeks + 1):
            if week_num in done_weeks:
                continue  # already scraped on a prior run

            if not select_week_by_number(page, week_num):
                print(f"  Week {week_num:2d}: ✗ could not select — skipping")
                continue

            rows = extract_matchups_from_sidebar(page, year, week_num)
            if rows:
                writer.writerows(rows)
                csv_file.flush()  # checkpoint to disk after every week
                new_count += len(rows)
                print(f"  Week {week_num:2d}: {len(rows)} matchup(s)")
            else:
                page.screenshot(path=f"_debug_matchups_{year}_wk{week_num}.png")
                print(f"  Week {week_num:2d}: 0 matchups — screenshot saved")
    finally:
        csv_file.close()

    if new_count:
        print(f"  ✓ Appended {new_count} new row(s) to {out_path}")
    else:
        print(f"  (no new rows added)")

    return []


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, help="Only scrape this one year")
    args = ap.parse_args()

    if not EMAIL or not PASSWORD:
        raise SystemExit("FANTRAX_EMAIL and FANTRAX_PASSWORD must be set in .env")
    if not SEASONS_PATH.exists():
        raise SystemExit(f"{SEASONS_PATH} not found.")

    seasons = json.loads(SEASONS_PATH.read_text())
    if not isinstance(seasons, list):
        raise SystemExit("seasons_filtered.json must be a list of {year, league_id} objects.")

    if args.year is not None:
        seasons = [s for s in seasons if s["year"] == args.year]
        if not seasons:
            raise SystemExit(f"No season with year={args.year} in {SEASONS_PATH}")
        print(f"Filtering to year={args.year} only.")

    if DISCOVER:
        print("DISCOVER mode: screenshot dropdown + first week, then stop per season.\n")

    summary = {}

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

        for s in seasons:
            rows = scrape_season(page, s["year"], s["league_id"])
            summary[s["year"]] = len(rows)

        browser.close()

    print("\n── Summary ─────────────────────────────────────────────────")
    for yr in sorted(summary):
        print(f"  {yr}: {summary[yr]} matchup rows")
    if DISCOVER:
        print("\nRe-run without DISCOVER=1 once selectors look correct.")


if __name__ == "__main__":
    main()
