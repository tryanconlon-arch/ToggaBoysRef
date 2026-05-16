"""
Dump standings page HTML and one team's roster page HTML to find owner selectors.
"""
import os, time, re
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()
EMAIL  = os.getenv("FANTRAX_EMAIL")
PASSWORD = os.getenv("FANTRAX_PASSWORD")
LEAGUE = "dsdrkvd6ly7km8nm"  # 2024

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

    # 1. Dump standings page
    page.goto(f"https://www.fantrax.com/fantasy/league/{LEAGUE}/standings",
              wait_until="domcontentloaded", timeout=30000)
    wait(page)
    dismiss(page)
    html = page.content()
    Path("_debug_standings_2024.html").write_text(html)
    print(f"Standings HTML: {len(html):,} chars")

    # Show team links found
    team_links = re.findall(
        r'href="(/fantasy/league/[^"]+/team/roster;teamId=[^"]+)"',
        html
    )
    # Also try legacy ?teamId= format
    if not team_links:
        team_links = [(h, "") for h in re.findall(
            r'href="(/fantasy/league/[^"]+/team/roster\?teamId=[^"]+)"', html
        )]
    else:
        team_links = [(h, "") for h in team_links]
    print(f"Found {len(team_links)} team links with teamId")
    for href, title in team_links[:5]:
        print(f"  title={title!r}  href={href}")

    # 2. Navigate to first real team page and dump HTML
    if team_links:
        first_href = "https://www.fantrax.com" + team_links[0][0]
        print(f"\nNavigating to: {first_href}")
        page.goto(first_href, wait_until="domcontentloaded", timeout=30000)
        wait(page)
        dismiss(page)
        team_html = page.content()
        Path("_debug_team_roster_2024.html").write_text(team_html)
        print(f"Team roster HTML: {len(team_html):,} chars")

        # Look for owner/profile links
        owner_links = re.findall(r'href="(/[^"]*(?:profile|user|newUser)[^"]*)"', team_html)
        print(f"Owner/profile links: {owner_links[:10]}")

        # Look for data-user-id or owner patterns
        owner_data = re.findall(r'(?:owner|manager|user)[^=]{0,20}=[\'"]([\w\-]{6,})[\'"]',
                                team_html, re.IGNORECASE)
        print(f"owner/user= patterns: {owner_data[:10]}")

        # Screenshot
        page.screenshot(path="_debug_team_roster_2024.png")
        print("Screenshot saved.")

    browser.close()
    print("\nDone.")
