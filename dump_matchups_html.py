"""
Quick diagnostic: dumps the matchups page HTML for 2024 so we can identify
the correct CSS selectors for team names and scores.
"""
import os, time, json
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

EMAIL    = os.getenv("FANTRAX_EMAIL")
PASSWORD = os.getenv("FANTRAX_PASSWORD")
LEAGUE   = "dsdrkvd6ly7km8nm"  # 2024 season


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
    print(f"Logged in at: {page.url}")

    url = f"https://www.fantrax.com/fantasy/league/{LEAGUE}/matchups"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    wait(page)
    dismiss(page)
    print(f"At: {page.url}")

    # Dump the first ~200KB of HTML
    html = page.content()
    out = Path("_debug_matchups_2024.html")
    out.write_text(html, encoding="utf-8")
    print(f"HTML written to {out}  ({len(html):,} chars)")

    # Also try to find any element with score-like class names
    for pattern in ["matchup", "score", "team", "week", "gw", "gameweek", "versus", "opponent"]:
        els = page.locator(f"[class*='{pattern}']").all()
        if els:
            print(f"\n[class*='{pattern}']: {len(els)} element(s)")
            for el in els[:3]:
                try:
                    cls = el.get_attribute("class") or ""
                    tag = el.evaluate("el => el.tagName")
                    txt = (el.inner_text() or "")[:80].replace("\n", " ")
                    print(f"  <{tag} class='{cls}'> → {txt!r}")
                except Exception:
                    pass

    browser.close()
    print("\nDone.")
