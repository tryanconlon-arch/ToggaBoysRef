# HANDOFF.md — ToggaBoys data pipeline status

Read this first. Then `CLAUDE.md` for immutable rules, then `field_inventory.md` for the UI field spec.

**Last updated:** 2026-05-16 (Ryan + Claude Code, Phase 6 complete).

---

## Phase status

| # | Phase | Status |
|---|---|---|
| 1 | UI field inventory (`field_inventory.md`) | DONE |
| 2 | Historical standings + transactions CSVs (7 seasons, 2018–2024) | DONE |
| 3 | Weekly matchups DOM scrape (7 seasons) | DONE — all 7 CSVs present |
| 4 | Owner registry (`owners.json`) — Fantrax user IDs captured | DONE (auto); 9 core managers have names + colors; 2024 champion non-core (name null) |
| 5 | `build_historical_data.py` — aggregate CSVs + owners → JS data file | DONE — emits `fantrax_historical.js` |
| 6 | Wire UI sections (hero, champions, seasons, records, h2h, managers) to real data | DONE |

---

## What's on disk right now

```
fantrax_data/historical/
  2018/  standings.csv  transactions.csv
  2019/  standings.csv  transactions.csv
  2020/  standings.csv  transactions.csv
  2021/  standings.csv  transactions.csv
  2022/  standings.csv  transactions.csv
  2023/  standings.csv  transactions.csv
  2024/  standings.csv  transactions.csv

matchups_2018.csv  ✓ done
matchups_2019.csv  ✓ done
matchups_2020.csv  ✓ done
matchups_2021.csv  ✓ done
matchups_2022.csv  -- pending
matchups_2023.csv  -- pending
matchups_2024.csv  -- pending

seasons_filtered.json    # 7 entries, year → league_id (canonical)
owners.json              # 46 owner entries; 9 are "core" (all 7 seasons)
```

Note: `scrape_matchups.py` writes `matchups_{year}.csv` at repo root, NOT inside `fantrax_data/historical/{year}/`. The script now skips seasons whose CSV already exists, so re-running `python scrape_matchups.py` will only do the missing ones.

**Verify before Phase 5:** run `ls matchups_*.csv` and `ls fantrax_data/historical/*/` to confirm all 7 years are present.

---

## owners.json — what Ryan still needs to do

The 9 core members (present in all 7 seasons) — Ryan fills in `name` + `color` by hand:

| Fantrax user ID | Most recent team name | Status |
|---|---|---|
| `72e9g51ajkhfl8ya` | Check Complete FC | name + color needed |
| `7kh2l9uqjk8tphpy` | Schärholder Value | name + color needed |
| `e44gvyjsjk90uswv` | Cruel Summerville | name + color needed |
| `ijur5702jk8kadcp` | Law of Averages | name + color needed |
| `n49bivscjjztp1no` | Tim's Team | name + color needed |
| `ne2zuh87jkhghgad` | Roy Kent's U8 Girls | name + color needed |
| `sjh9eqr4jk8nfodx` | Morgan Rodgers Neighborhood | name + color needed |
| `wd22oqeqjjzw73b3` | The Madd Hatters | name + color needed |
| `x46g9ztbjk06jgh0` | The Riesterer Bunny | name + color needed |

Non-core owners (37 entries) can keep `name`/`color` null. UI either hides them or shows a placeholder; decide in Phase 6.

Suggested color palette (dark-UI friendly):
```
#22d3ee  #f59e0b  #a78bfa  #34d399  #fb7185
#facc15  #60a5fa  #f97316  #c084fc
```

---

## Phase 5 — `build_historical_data.py` (next session)

Goal: read everything on disk + `owners.json` and emit a single JS file the React app can consume. Deliverable: `fantrax_historical.js` (or extend `fantrax_data.js`) exporting these globals:

- `MANAGERS_HISTORICAL` — array of `{id, name, color, championships: [year, ...]}`, one entry per Fantrax user ID with a non-null name in `owners.json`.
- `SEASON_STANDINGS_HISTORICAL` — `{ [year]: [{owner_id, rank, w, d, l, pf, pa, team_name}, ...] }` for years 2018–2024.
- `MATCHUPS_HISTORICAL` — array of `{year, week, m1_owner, m2_owner, m1_score, m2_score, winner_owner}`.
- `RECORDS_HISTORICAL` — computed: highest/lowest single-week score, biggest win margin, most/fewest PF in a season, best regular-season record, longest W/L streak, all-time win rate, most transactions in a season, highest-scoring player-week. See `field_inventory.md` records section for the 12 cards needed.
- `H2H_HISTORICAL` — `{ [`${ownerA}-${ownerB}`]: {w, l, pf, pa, matchups: [...]} }` for every pair.
- `CHAMPIONS_HISTORICAL` — `{ [year]: owner_id }` = whoever ranked 1st in standings that year.

Open questions to resolve while writing this:
1. **How to reconcile current-season `fantrax_data.js` standings with historical?** Strategy: keep current-season as-is, add historical as new globals. Component layer decides which to use per section.
2. **What does `transactions.csv` give us for record #11 (Best Trade Return)?** Probably not enough on its own — would need player FPts pre/post trade. Punt for now; emit a placeholder.

---

## Phase 6 — wire the UI

Component-by-component (see `field_inventory.md` for field-level detail):

- **hero** — three count-up tiles + champion badge. Drives from `SEASONS.length`, `MANAGERS_HISTORICAL.length`, `max(score)` from `MATCHUPS_HISTORICAL`, and `CHAMPIONS_HISTORICAL[2024]`.
- **champions** — carousel from `CHAMPIONS_HISTORICAL`, all-time leaderboard derived in JS from standings.
- **seasons** — year picker + standings table directly from `SEASON_STANDINGS_HISTORICAL[year]`.
- **records** — 12 cards from `RECORDS_HISTORICAL`. Drop the NFL "Mahomes" reference; replace with a real Premier League player from a real high-scoring week.
- **h2h** — picker + `H2H_HISTORICAL[pair_key]`. Drops the `seededRand`-based fake generator.
- **managers** — cards + modal from `MANAGERS_HISTORICAL` + per-manager career stats computed from `SEASON_STANDINGS_HISTORICAL`. Drop the `SIGS` editorial blurbs for now (no data source).

UI cleanup that must happen in Phase 6 (per `CLAUDE.md` rules):

- Delete `PLAYOFFS` constant. ✓ DONE
- Delete "Runner-up: …" sub-line on champion cards. ✓ DONE
- Delete the `Playoffs` (✓/—) column from the manager modal. ✓ DONE
- Strip the "(Championship)" suffix from records card #1. ✓ DONE (record ctx comes from HIST_RECORDS)
- Expand `SEASONS = [2018, 2019, ..., 2024]`. ✓ DONE (now `HIST_SEASONS`)

### What was wired in Phase 6

- `MANAGERS = HIST_MANAGERS.filter(m => m.has_name)` — 16 named managers
- `SEASONS = HIST_SEASONS` — [2018..2024]
- `SEASON_STANDINGS = HIST_STANDINGS` — real standings with `owner_id`, `d`, `pts`
- `RECORDS = HIST_RECORDS` — real computed records
- `computeAllTime()` — uses `owner_id`, includes draws in denominator
- `getH2HData()` — real HIST_H2H lookup with perspective flip
- `computeManagerCareer()` — uses `owner_id`
- `HeroSection` — Est. 2018, 7 seasons, real record score from HIST_RECORDS[0], champion from 2024 standings rank-1
- `HallOfChampions` — champion from standings rank-1 per year; deleted Runner-up line
- `SeasonResults` — real draws column, real pts, team_name from row, champion from `row.champion` boolean
- `HeadToHead` — string IDs (no `+m1` coercions), real HIST_H2H data
- `ManagerModal` — deleted Playoffs column, deleted SIGS editorial blurbs

### Known open items / Ryan action needed

- **2024 champion has no name**: `r8hjeqi3lkb4nu7q` (team "3-Young Munoz $$") has `name: null` in `owners.json`. The hero badge + champion carousel fall back to `team_name`. Fill in real name + color in `owners.json`, then re-run `python3 build_historical_data.py` to regenerate `fantrax_historical.js`.
- **Lowest score record is 0.0 pts** (100 Virgils, Week 21 · 2022) — may be a scraper artifact where one team's score wasn't loaded. Worth spot-checking `matchups_2022.csv` week 21.
- `sig-block` CSS class is now unused (safe to delete from `<style>` block if desired, but no functional impact).

---

## Don't-do list

- Don't fetch matchups via WebFetch from the live site — Fantrax is auth-walled. Use Playwright + saved CSVs.
- Don't add manager headshots.
- Don't try to fill in real names automatically — those come from Ryan.
- Don't include the current 2025-26 season in historical aggregates (that's `fantrax_data.js`'s job).
- Don't install anything without asking.

---

## How to resume in a new session

1. `Read HANDOFF.md` (this file)
2. `Read CLAUDE.md`
3. `Read field_inventory.md`
4. `ls fantrax_data/historical/*/` to confirm what's actually on disk
5. Pick up at the first phase still marked NOT STARTED / IN PROGRESS

When done with a phase: update the phase table at the top, append any new open questions to the relevant phase section, and commit.
