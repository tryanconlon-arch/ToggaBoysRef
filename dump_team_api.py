"""
Intercept Fantrax API calls on a team roster page to find owner ID structure.
Navigates to 2024 season, first team, captures XHR/fetch responses.
"""
import os, time, json, re
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()
EMAIL    = os.getenv("FANTRAX_EMAIL")
PASSWORD = os.getenv("FANTRAX_PASSWORD")
LEAGUE   = "dsdrkvd6ly7km8nm"

api_responses = []

def wait(page, timeout=15000):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeout:
        pass
    time.sleep(2)

def dismiss(page):
    for txt in ["Never", "Dismiss", "No thanks"]:
        try:
            page.click(f"button:has-text('{txt}')", timeout=1500)
            time.sleep(0.3)
        except PlaywrightTimeout:
            pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    # Intercept API responses
    def on_response(response):
        url = response.url
        if any(kw in url.lower() for kw in ['api', 'fantasy', 'fantrax']) and \
           any(kw in url.lower() for kw in ['team', 'roster', 'member', 'owner', 'user', 'scoring']):
            try:
                body = response.text()
                if any(kw in body.lower() for kw in ['ownerid', 'userid', 'owner', 'manager']):
                    api_responses.append({"url": url, "body": body[:2000]})
            except Exception:
                pass

    page.on("response", on_response)

    # Login
    page.goto("https://www.fantrax.com/login", wait_until="domcontentloaded", timeout=30000)
    wait(page)
    dismiss(page)
    inputs = page.locator("input").all()
    if len(inputs) < 2:
        time.sleep(3)
        inputs = page.locator("input").all()
    inputs[0].fill(EMAIL)
    inputs[1].fill(PASSWORD)
    page.click("button:has-text('Login'), button[type='submit']")
    wait(page, 20000)
    print(f"Logged in: {page.url}")

    # Get standings page to find team IDs
    page.goto(f"https://www.fantrax.com/fantasy/league/{LEAGUE}/standings",
              wait_until="domcontentloaded", timeout=30000)
    wait(page)
    dismiss(page)
    html = page.content()
    team_ids = re.findall(r'/team/roster;teamId=([A-Za-z0-9]+)', html)
    team_ids = list(dict.fromkeys(team_ids))  # deduplicate preserving order
    print(f"Found {len(team_ids)} team IDs")
    if team_ids:
        print(f"First 3: {team_ids[:3]}")

    # Navigate to first team's roster page
    if team_ids:
        team_url = f"https://www.fantrax.com/fantasy/league/{LEAGUE}/team/roster;teamId={team_ids[0]}"
        print(f"\nNavigating to: {team_url}")
        api_responses.clear()
        page.goto(team_url, wait_until="domcontentloaded", timeout=30000)
        wait(page)
        dismiss(page)

        print(f"\n── API responses with owner/user/manager content ────────────────")
        print(f"Captured {len(api_responses)} relevant API response(s)")
        for r in api_responses[:10]:
            print(f"\nURL: {r['url']}")
            print(f"Body: {r['body'][:800]}")

        if not api_responses:
            print("  (none captured - trying to look at all API responses)")
            # Try capturing everything
            page.goto(team_url, wait_until="domcontentloaded", timeout=30000)

        # Capture ALL fantrax.com JSON/JS responses on reload
        all_fantrax = []
        def on_all_response(response):
            url = response.url
            if 'fantrax.com' in url:
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct or "javascript" in ct:
                        body = response.text()
                        all_fantrax.append({"url": url, "body": body[:400]})
                except Exception:
                    pass

        page.on("response", on_all_response)
        page.reload(wait_until="domcontentloaded", timeout=30000)
        wait(page)
        print(f"\n── All fantrax.com JSON/JS responses ───────────────────────────────")
        for r in all_fantrax[:30]:
            print(f"\nURL: {r['url']}")
            print(f"Body: {r['body'][:300]}")

    browser.close()
    print("\nDone.")
