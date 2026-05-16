"""
Try various Fantrax URLs to find per-week match scores for the 2024 season.
"""
import os, time, re
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()
EMAIL    = os.getenv("FANTRAX_EMAIL")
PASSWORD = os.getenv("FANTRAX_PASSWORD")
LEAGUE   = "dsdrkvd6ly7km8nm"  # 2024 season

CANDIDATE_URLS = [
    f"https://www.fantrax.com/fantasy/league/{LEAGUE}/scoreboard",
    f"https://www.fantrax.com/fantasy/league/{LEAGUE}/scoring",
    f"https://www.fantrax.com/fantasy/league/{LEAGUE}/livescoring",
    f"https://www.fantrax.com/fantasy/league/{LEAGUE}/matchups;view=SCORING",
    f"https://www.fantrax.com/fantasy/league/{LEAGUE}/matchups?view=scoring",
]

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

    for url in CANDIDATE_URLS:
        print(f"\n--- Trying: {url} ---")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            wait(page)
            dismiss(page)
            final_url = page.url
            print(f"  Final URL: {final_url}")

            # Look for score-like content
            html = page.content()
            # Check for decimal scores
            scores = re.findall(r'\b(\d{2,3}\.\d{1,2})\b', html)
            print(f"  Score-like decimals: {len(scores)} found — {scores[:10]}")

            # Check page title/heading
            try:
                heading = page.locator("h1, h2, [class*='title'], [class*='heading']").first
                print(f"  Heading: {heading.inner_text()[:100]!r}")
            except Exception:
                pass

            # Save HTML if it looks interesting
            if len(scores) > 10:
                slug = url.split("/")[-1].replace(";", "_").replace("?", "_")
                out = Path(f"_debug_{slug}.html")
                out.write_text(html)
                print(f"  ✓ Saved {out} ({len(html):,} chars)")

                # Show unique score-containing classes
                classes_near_scores = re.findall(r'class="([^"]*score[^"]*)"', html)
                unique = sorted(set(classes_near_scores))[:15]
                print(f"  Score-related classes: {unique}")

        except Exception as e:
            print(f"  Error: {e}")

    browser.close()
    print("\nDone.")
