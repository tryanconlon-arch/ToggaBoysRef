"""
Intercept and dump the /fxpa/req API response containing userLeagueInfo.
This is Fantrax's internal API gateway that returns member/team data.
"""
import os, time, json
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()
EMAIL    = os.getenv("FANTRAX_EMAIL")
PASSWORD = os.getenv("FANTRAX_PASSWORD")
LEAGUE   = "dsdrkvd6ly7km8nm"

captured = []

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

    def on_response(response):
        url = response.url
        if "fantrax.com/fxpa/req" in url:
            try:
                body = response.text()
                data = json.loads(body)
                captured.append({"url": url, "data": data})
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

    # Navigate to standings for this league
    page.goto(f"https://www.fantrax.com/fantasy/league/{LEAGUE}/standings",
              wait_until="domcontentloaded", timeout=30000)
    wait(page)
    dismiss(page)

    print(f"\nCaptured {len(captured)} /fxpa/req response(s)\n")

    for i, c in enumerate(captured):
        print(f"=== Response {i+1}  URL: {c['url']}")
        data = c["data"]
        # Look for userLeagueInfo
        for resp in data.get("responses", []):
            d = resp.get("data", {})
            if "userLeagueInfo" in d:
                info = d["userLeagueInfo"]
                users = info.get("users", [])
                print(f"  userLeagueInfo.users ({len(users)} entries):")
                for u in users:
                    print(f"    id={u.get('id')!r:25s}  memInfoId={u.get('memInfoId')!r:22s}  name={u.get('name')!r}")
            if "fantasyTeams" in d:
                teams = d["fantasyTeams"]
                print(f"  fantasyTeams ({len(teams)} entries):")
                for t in teams[:5]:
                    print(f"    id={t.get('id')!r:22s}  name={t.get('name')!r}")
        print()

    # Save full dump
    Path("_debug_fxpa_dump.json").write_text(json.dumps(captured, indent=2))
    print(f"Full dump saved to _debug_fxpa_dump.json")

    browser.close()
    print("Done.")
