# CLAUDE.md — ToggaBoys Reference Site

Auto-loaded by Claude Code on session start. Immutable project rules. Don't argue with these; if something here is wrong, ask Ryan before changing it.

## What this project is

A React-in-Babel single-page reference site (`index.html`) for the ToggaBoys fantasy Premier League. Most of the UI currently shows hardcoded placeholder data; the work in progress is replacing it with real historical data scraped from Fantrax via Playwright. The current-season Live Standings / Roster / Player Pool / Moves sections are already wired to real data and are out of scope for this work stream.

## League format — non-negotiable

- **38-week regular season.** No playoff bracket. No semis, no finals, no championship game.
- **Champion** = team that finishes 1st in the final standings after week 38. That's the only winner concept.
- **No runner-up concept.** Drop any "Runner-up: …" sub-line.
- **UI elements to delete (not populate):**
  - The `PLAYOFFS` JS constant in `index.html`.
  - The "Runner-up: …" sub-line on each Champions carousel card.
  - The `Playoffs` (✓/—) column in the manager modal's season-by-season table.
  - The "(Championship)" suffix on the Wk 14 records card.

## Year-labeling convention — starting year of the season

- 2018-19 → `2018`
- 2019-20 → `2019`
- 2020-21 → `2020`
- 2021-22 → `2021`
- 2022-23 → `2022`
- 2023-24 → `2023`
- 2024-25 → `2024`
- 2025-26 (current) → `2025`

Use this everywhere: filenames, JSON keys, the UI `SEASONS` array. The current `SEASONS = [2019, ..., 2024]` in `index.html` only goes back to 2019 — once 2018 data is in place, expand the array to include 2018.

## Manager identity

- The canonical manager key is the **Fantrax owner user ID** (e.g. `72e9g51ajkhfl8ya`). Stable across seasons. The team-name string changes yearly; the owner ID doesn't.
- Real names + accent colors live in `owners.json` and are filled in by hand. Don't invent names. If `name` is null, leave the manager out of the UI or render a placeholder — don't guess.
- No manager headshots. Don't add them.

## Scope — historical sections only

The data-population work covers: hero, champions, seasons, records, h2h, managers.

**Out of scope** for this work stream (already wired or current-season-only):
- Live Standings
- My Roster
- Player Pool
- Moves & Transactions tab

## Repo layout

```
index.html                # The React app
fantrax_data.js           # JS globals consumed by the app (current-season only today)
fantrax_export.py         # Existing Playwright scraper — CURRENT season only
discover_seasons.py       # Lists all leagues this account belongs to → seasons.json
fantrax_history.py        # Reads seasons_filtered.json, pulls standings + transactions per past season
scrape_matchups.py        # (added by Claude Code) DOM scraper for weekly matchups
scrape_members.py         # (added by Claude Code) Owner-registry scraper
build_historical_data.py  # (planned) Aggregates per-season CSVs + owners.json into a JS data file
seasons_filtered.json     # Authoritative {year, league_id} list — 7 historical seasons
owners.json               # Fantrax owner ID → {name, color, team_history} — partially filled
fantrax_data/             # All scraper outputs
  2026-05-16/             # Original single-day current-season export
  historical/{year}/      # Per-season CSVs: standings.csv, transactions.csv, matchups.csv
field_inventory.md        # Exhaustive UI field inventory (read this before wiring UI)
HANDOFF.md                # Current state of play — read this first
```

## Reusable Playwright patterns — don't reinvent

`fantrax_export.py` defines these helpers. Import or copy, don't reimplement:

- `wait_for_page_ready(page, timeout=15000)` — handles Angular SPA load + buffer.
- `dismiss_banners(page)` — clicks Never / Dismiss / No thanks.
- `try_export(page, label, download_dir)` — walks `EXPORT_SELECTORS` to find the CSV download button.
- `EXPORT_SELECTORS` — the working CSV-download selector list. The mat-icon `get_app` button is the one that actually works in production.

Login: read `FANTRAX_EMAIL` + `FANTRAX_PASSWORD` from `.env`. Login flow is fragile — copy verbatim from `fantrax_export.py` rather than re-deriving.

## Operating rules

- **Don't install anything without explicit consent.** Playwright + python-dotenv are already installed.
- **Don't paste large file contents into chat.** Use `Read` on the file path.
- **Keep `fantrax_export.py` working for current-season pulls.** Don't break it while adding historical capability.
- **Update `HANDOFF.md` at the end of every phase** so the next session can pick up cold.
- **Ask before making schema changes** to `fantrax_data.js` or the React component prop shapes — Ryan may have UI-side preferences.

## When in doubt

Read `HANDOFF.md` first (current state), then `field_inventory.md` (UI field-by-field spec), then this file. If those don't answer it, ask Ryan.
