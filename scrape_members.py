"""
scrape_members.py
-----------------
Captures each manager's stable Fantrax owner user ID and per-season team name
by intercepting the /fxpa/req API endpoint that Fantrax loads on every page.

The `userLeagueInfo.users[].id` field is a stable user ID across seasons
(confirmed: same user has the same id in 2024 and 2025/26 leagues).

Usage:
    python scrape_members.py        # full run

Output:
    owners.json  (repo root)

    Structure:
    {
      "<fantrax_user_id>": {
        "seasons": {"2018": "Team Name 2018", "2019": "Team Name 2019", ...},
        "color": null,    <-- fill in manually later
        "name": null      <-- fill in manually later
      },
      ...
    }

Credentials from .env:
    FANTRAX_EMAIL=your@email.com
    FANTRAX_PASSWORD=yourpassword
"""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

EMAIL        = os.getenv("FANTRAX_EMAIL")
PASSWORD     = os.getenv("FANTRAX_PASSWORD")
SEASONS_PATH = Path("seasons_filtered.json")
OUT_PATH     = Path("owners.json")


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


def parse_user_league_info(body: str):
    """
    Parse a /fxpa/req JSON response body and return (user_id, team_name) pairs
    from the first userLeagueInfo block found. Returns [] if not present.
    """
    try:
        data = json.loads(body)
    except Exception:
        return []
    for resp in data.get("responses", []):
        d = resp.get("data", {})
        if "userLeagueInfo" in d:
            users = d["userLeagueInfo"].get("users", [])
            pairs = []
            for u in users:
                uid  = (u.get("id") or "").strip()
                name = (u.get("name") or "").strip()
                if uid and name:
                    pairs.append((uid, name))
            if pairs:
                return pairs
    return []


def fetch_user_league_info(page, url, league_id, timeout=30000):
    """
    Navigate to `url` and wait for the fxpa/req response that contains
    userLeagueInfo. Returns list of (user_id, team_name) pairs, or [].
    """
    pairs = []

    def is_target(response):
        if "fantrax.com/fxpa/req" not in response.url:
            return False
        try:
            body = response.text()
            return '"userLeagueInfo"' in body
        except Exception:
            return False

    try:
        with page.expect_response(is_target, timeout=timeout) as resp_info:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            dismiss_banners(page)
        pairs = parse_user_league_info(resp_info.value.text())
    except PlaywrightTimeout:
        # userLeagueInfo didn't arrive in the initial load — try a reload.
        try:
            with page.expect_response(is_target, timeout=timeout) as resp_info:
                page.reload(wait_until="domcontentloaded", timeout=30000)
            pairs = parse_user_league_info(resp_info.value.text())
        except PlaywrightTimeout:
            pass

    return pairs


# ── Per-season scrape ─────────────────────────────────────────────────────────

def scrape_season_members(page, year, league_id, owners: dict):
    url = f"https://www.fantrax.com/fantasy/league/{league_id}/standings"

    print(f"\n=== Season {year}  ({league_id}) ===")
    pairs = fetch_user_league_info(page, url, league_id)

    if not pairs:
        page.screenshot(path=f"_debug_members_{year}_no_data.png")
        print(f"  ✗ No userLeagueInfo found — screenshot saved.")
        return

    print(f"  Found {len(pairs)} (user_id, team_name) pair(s)")

    seen_names = {}  # team_name → first user_id seen (for duplicate detection)
    for uid, name in pairs:
        if name in seen_names and seen_names[name] != uid:
            print(f"  ⚠ Team '{name}' has multiple owners: {seen_names[name]!r} and {uid!r}")
        seen_names[name] = uid

        if uid not in owners:
            owners[uid] = {"seasons": {}, "color": None, "name": None}
        # Store team name for this season; if uid already has an entry for this year,
        # keep existing (first occurrence wins).
        if str(year) not in owners[uid]["seasons"]:
            owners[uid]["seasons"][str(year)] = name

    print(f"  ✓ Captured teams for {len(seen_names)} unique team name(s)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not EMAIL or not PASSWORD:
        raise SystemExit("FANTRAX_EMAIL and FANTRAX_PASSWORD must be set in .env")
    if not SEASONS_PATH.exists():
        raise SystemExit(f"{SEASONS_PATH} not found. Run discover_seasons.py first.")

    seasons = json.loads(SEASONS_PATH.read_text())
    if not isinstance(seasons, list):
        raise SystemExit("seasons_filtered.json must be a list of {year, league_id} objects.")

    # Load existing owners.json if present (allows re-running incrementally).
    owners: dict = {}
    if OUT_PATH.exists():
        existing = json.loads(OUT_PATH.read_text())
        if isinstance(existing, dict):
            owners = existing
            print(f"Loaded {len(owners)} existing owner entries from {OUT_PATH}.")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        print("Logging in...")
        login(page)
        print(f"  ✓ Logged in (now at: {page.url})")

        for s in seasons:
            scrape_season_members(page, s["year"], s["league_id"], owners)
            # Save incrementally after each season.
            OUT_PATH.write_text(json.dumps(owners, indent=2, sort_keys=True))

        browser.close()

    OUT_PATH.write_text(json.dumps(owners, indent=2, sort_keys=True))
    print(f"\n── Done ───────────────────────────────────────────────────")
    print(f"  {len(owners)} unique owners found")
    print(f"  Wrote {OUT_PATH.resolve()}")
    print()
    print("  ⚠ NEXT STEP: fill in 'name' and 'color' for each owner in owners.json")
    print("    The 'name' field should be the real person's name.")
    print("    The 'color' field should be a hex color code (e.g. '#e74c3c').")


if __name__ == "__main__":
    main()
