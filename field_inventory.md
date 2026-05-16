# Togga Boys Ref — Full UI Field Inventory

Source of truth: `index.html` (React app, in-browser Babel) and `fantrax_data.js` (live Fantrax export).

> **League rule note:** ToggaBoys plays a **38-week regular season with no playoff bracket**. After GW38 the standings are final.
> - **Champion** = team at rank 1 in final standings (the only "winner" concept used).
> The `PLAYOFFS` JS constant, the "Runner-up: …" sub-line on champion cards, the `Playoffs ✓` column in the manager modal, and the "(Championship)" suffix on the Wk 14 record card are leftover playoff-bracket filler and should be **removed** from the UI. Those rows are flagged below.

Legend:
- **FAKE** = hardcoded inline in `index.html` (MANAGERS / SEASONS / SEASON_STANDINGS / RECORDS / SIGS arrays) or synthesised via `seededRand()`.
- **REAL** = wired to a `FANTRAX_*` global from `fantrax_data.js` (sourced from a CSV in `fantrax_data/2026-05-16/`).
- **DERIVED** = computed at render time from one of the above.
- **REMOVE** = UI element implies playoffs and should be deleted from the page, not wired to data.

CSV column names (from `head -2` on each export):

- `standings.csv` → `Rk, Team, W, D, L, Points, Win%, Div, FPtsF, FPtsA, Streak`
- `roster.csv` → `ID, Pos, Player, Team, Eligible, Status, Opponent, Fantasy Points, Average Fantasy Points per Game, GP, GS, Min, MCS, GA, Sv, YC, RC, FS, PKS, PKD, PKM, TkW, DIS, G, A, A2, KP, AF, Int, IntB, CLR, CoS, AER, AC, HCS, Sm, OG, SOT` (grouped by position headers like `Goalkeeper`)
- `players.csv` → `ID, Player, Team, Position, RkOv, Status, Opponent, FPts, FP/G, Ros, +/-`
- `transaction_history.csv` → `Player, Team, Position, Type, Team, Bid, Pr, Date (EDT), Gameweek`

---

## hero

UI block in `HeroSection()` (lines ~571–617).

| Field | Type | Status | Source needed |
|---|---|---|---|
| Site logo (nav + here, base64 png) | image (data URI) | FAKE (inline base64 `LOGO` const at line 291) | Provide real league/team logo asset |
| "Est. 2019 · Official League Archive" eyebrow text | string | FAKE (hardcoded literal) | Confirm founding year; no source |
| "TOGGA / BOYS / REF" hero title | string | FAKE (hardcoded `<h1>` literal) | League name — no source needed |
| Hero subtitle ("Six seasons of glory, heartbreak, and questionable roster decisions.") | string | FAKE (hardcoded literal) | Copy only |
| Stat tile #1: "Seasons" value (animates 0→6) | number (count-up) | FAKE (literal `6` passed to `useCountUp`) | Derive from count of seasons available (currently hardcoded `SEASONS = [2019..2024]`) |
| Stat tile #2: "Managers" value (animates 0→10) | number (count-up) | FAKE (literal `10`) | Derive from MANAGERS.length (currently hardcoded 10) |
| Stat tile #3: "Record Score" value (animates 0→196.8) | number (count-up, 1dp) | FAKE (literal `196.8`) | Compute highest single-week score across all seasons — not in current Fantrax exports (would need weekly matchup history) |
| "2024 Champion · {name} — {team}" badge | string | FAKE (derived from `PLAYOFFS[2024].champion` → `MANAGERS`) | Derive from final 2024 regular-season standings (manager finishing #1). Needs the season-history standings dataset; no separate playoff/championship file needed. |
| Pulsing green dot indicator | decorative | FAKE (CSS) | n/a |
| Background ring SVG + green stripe + bottom fade | decorative | FAKE (CSS) | n/a |

**Derived/computed fields needing logic**: All three count-up KPIs are currently literal constants — to be wired they need:
- `Seasons` = `SEASONS.length`
- `Managers` = `MANAGERS.length`
- `Record Score` = `max(weekScore)` over all weeks — requires a not-yet-exported `matchups.csv`/`schedule.csv` (the `_debug_matchups.png` / `_debug_schedule.png` screenshots exist but no CSV).

---

## champions  (Hall of Champions)

UI block in `HallOfChampions()` (lines ~646–730). Two sub-views: horizontal "champion cards" carousel + sortable all-time leaderboard table.

### Champion card carousel (one card per `SEASONS` year)

| Field | Type | Status | Source needed |
|---|---|---|---|
| Trophy icon (🏆) | emoji | FAKE (literal) | n/a |
| Season year `cc-yr` | number (year) | FAKE (`SEASONS` array `2019..2024`) | Future season-history export |
| Champion name `cc-name` | string | FAKE (`MANAGERS[champion.id].name`) | Need season-by-season champion history (no Fantrax CSV today) |
| Champion team `cc-team` | string | FAKE (`MANAGERS[champion.id].team`) | Same — also tied to current team-name history |
| Regular-season record `cc-rec` ("W–L") | string | FAKE (`SEASON_STANDINGS[yr][champ].w/l`) | Same |
| Regular-season points-for `cc-pf` ("xxx.x PF") | number, 1 dp | FAKE | Same |
| "Runner-up: {name}" | string | **REMOVE** — no runner-up concept in this league. Drop the sub-line from the champion card. | n/a |
| Active-champ ring (`.active-champ`) on most recent | CSS state | FAKE (CSS class, currently unused) | n/a |

### All-time leaderboard table (driven by `ALL_TIME = computeAllTime()`)

| Column | Type | Status | Source needed |
|---|---|---|---|
| `#` rank index (gold/silver/bronze styling for top 3) | number | DERIVED (row index after sort) | sort order from underlying fake data |
| Manager avatar (colored initials block) | colored block w/ initials | FAKE (color from `MANAGERS[].color`, initials from `name`) | Need real manager photos/avatars (no Fantrax source) |
| Manager `name` | string | FAKE (`MANAGERS[].name`) | Manager registry — not in Fantrax exports |
| `Nx🏆` champion badge (next to name) | string | DERIVED from `MANAGERS[].championships.length` | Season champion history |
| Manager `team` (subtext) | string | FAKE (`MANAGERS[].team` — single hardcoded team per manager) | Real teams change yearly; current Fantrax `standings.csv` has 30 team rows for 2025/26 only |
| `Titles` (championship count) | number | FAKE (`MANAGERS[].championships.length`) | Need championship history |
| `Wins` (career) | number | DERIVED via `computeAllTime()` summing `SEASON_STANDINGS[yr].w` | Per-season historical standings |
| `Win %` | % (1 dp) | DERIVED (wins/(wins+losses)) | Same |
| `Total PF` | number (1 dp) | DERIVED (sum of `pf` across years) | Same |
| `Avg PF/Szn` | number (1 dp) | DERIVED (total PF / seasons) | Same |
| Column sort affordance (▲/▼ arrows on header click) | UI control | DERIVED (sort state) | n/a |

**Derived/computed fields needing logic**: The whole table is derived by `computeAllTime()` from the fake `SEASON_STANDINGS` map. To populate from real data you need a **season-history dataset** (one row per manager per year with W/L/PF/PA/finish/champion-flag) that Fantrax does not currently export — the current `standings.csv` only shows the current 2025/26 season.

---

## seasons  (Season Results)

UI block in `SeasonResults()` (lines ~732–807). Year-picker pills + two KPI tiles + standings table.

### Year picker

| Field | Type | Status | Source needed |
|---|---|---|---|
| Year pill buttons (2019, 2020, 2021, 2022, 2023, 2024) | enum buttons | FAKE (`SEASONS` array) | Season list — same season-history dependency |

### Top KPI tiles for the selected year

| Field | Type | Status | Source needed |
|---|---|---|---|
| "Champion" tile — manager name | string | FAKE (`PLAYOFFS[yr].champion` → `MANAGERS.name`) | Derive from final regular-season standings for `yr` (manager finishing #1). No separate playoff dataset. |
| Champion subtext — manager `team` | string | FAKE (`MANAGERS[].team`) | Season-historical team names (from same standings dataset) |
| "Top Scorer" tile — manager name | string | DERIVED (`standings.reduce` max on `pf`) | Per-season PF data |
| Top scorer subtext — "{pf.toFixed(1)} pts · {yr} season" | composite | DERIVED (`row.pf` + year label) | Same |

### Final standings table for the selected year

| Column | Type | Status | Source needed |
|---|---|---|---|
| `Rk` (rank, with gold/silver/bronze color) | number | FAKE (`SEASON_STANDINGS[yr][].rank`) | Per-season final standings |
| `Team` cell — colored avatar (initials) + manager name + "Champ" badge if `row.champion` + team subtext | composite | FAKE (`MANAGERS` + `SEASON_STANDINGS`) | Season standings export |
| `W` (wins) | number | FAKE | Per-season W/L |
| `D` (draws) | string `—` placeholder, always dash | HARDCODED dash (no draw data in fake standings) | Per-season draws if any |
| `L` (losses) | number | FAKE | Per-season L |
| `Pts` — computed as `3 * row.w` (no draws) | number | DERIVED (3·W; bug-prone if draws exist) | Real points incl. draws |
| `FPts For` | number (1 dp) | FAKE (`row.pf`) | Per-season fantasy PF |
| `FPts Ag` | number (1 dp) | FAKE (`row.pa`) | Per-season fantasy PA |

**Derived/computed fields needing logic**:
- Champion tile = manager at rank 1 in final standings for the year. Top Scorer tile = manager with max `pf`. Both derive from the season-history standings dataset; the `PLAYOFFS` constant should be deleted.
- `Pts` is `3·W` only — would break if real data has draws (which current `FANTRAX_STANDINGS` does have a `d` column, so the logic differs from live standings).
- Whole section duplicates the season-history dependency: nothing here comes from a Fantrax CSV.

---

## records  (Records Vault)

UI block in `RecordsVault()` (lines ~809–834). 12-tile responsive grid driven by `RECORDS` array.

Every record card has the same shape:

| Field | Type | Status | Source needed |
|---|---|---|---|
| `icon` (emoji) | string | FAKE (hardcoded per record) | n/a (decorative) |
| `label` (record name) | string | FAKE | n/a |
| `value` (big number) | string/number | FAKE | computed from real history |
| `unit` (small suffix, e.g. "pts", "%", "straight", "moves", "pts avg Δ") | string | FAKE | n/a |
| `holder` (manager surname) | string | FAKE | manager registry + winning lookup |
| `ctx` (subtext: "Week X · YYYY" / "def. X by Y · Wk Z · YYYY" / etc.) | string | FAKE | requires weekly matchup history |

The 12 specific records (all currently fake literals):

1. Highest Single-Week Score — 196.8 pts — Conlon — Wk 14 (Championship) · 2023  *(strip the "(Championship)" suffix — no playoffs in this league; just the week number)*
2. Lowest Single-Week Score — 42.2 pts — Brennan — Week 4 · 2020
3. Biggest Win Margin — 94.6 pts — Conlon — def. Malone by 94.6 · Wk 11 · 2023
4. Most Points in a Season — 1,923.4 pts — Conlon — 2023 Regular Season
5. Fewest Points in a Season — 1,234.5 pts — Brennan — 2020 Regular Season
6. Best Regular Season Record — 12-1 — Conlon — 2023 · 92.3% win rate
7. Longest Winning Streak — 9 straight — Murphy — Weeks 2–10 · 2019
8. Longest Losing Streak — 8 straight — Quinn — Weeks 5–12 · 2022
9. Highest Scoring Player Week — 52.3 pts — Conlon — Mahomes · Wk 11 · 2023 (note: NFL player name in an EPL fantasy app)
10. Most Transactions in a Season — 47 moves — Ryan — 2021 Season
11. Best Trade Return — +38.4 pts avg Δ — O'Brien — Acquired CMC for picks · 2020
12. All-Time Win Rate — 71.6% — Conlon — 58–23 career record

**Derived/computed fields needing logic**: To fill any of these from real exports you need:
- A weekly matchup/score table per season (records 1, 2, 3, 9 — not currently exported)
- Season-aggregated PF (records 4, 5 — needs historical standings)
- Season records W/L (record 6 — historical standings)
- Win/loss streak walking algorithm over weekly results (records 7, 8 — needs weekly results)
- Per-season transaction counts (record 10 — derivable from per-season `transaction_history.csv`, but only current season is exported)
- Trade-return delta (record 11 — requires player FPts before/after trade date)
- All-time win % (record 12 — historical standings sum)

---

## h2h  (Head-to-Head)

UI block in `HeadToHead()` (lines ~836–931). Two-manager picker + record + bar split + recent matchups list.

### Selectors

| Field | Type | Status | Source needed |
|---|---|---|---|
| Manager 1 dropdown options ("{name} — {team}", excluding picked m2) | enum | FAKE (`MANAGERS`) | Manager registry |
| "VS" pill (decorative) | string | FAKE | n/a |
| Manager 2 dropdown options | enum | FAKE (`MANAGERS`, excluding m1) | Manager registry |
| Placeholder copy ("Pick two managers above…") | string | hardcoded | n/a |

### Stats panel (only when both selected)

| Field | Type | Status | Source needed |
|---|---|---|---|
| "{wins}–{losses}" big record (greens if wins ≥ losses, else neutral) | number pair | **FAKE / SYNTHETIC** — generated by `getH2HData()` using `seededRand()` based on a deterministic seed of `m1id*1000+m2id*100+yr`. Not real H2H. | Real head-to-head requires weekly matchup history (who-played-who-each-week-each-season). Not in current exports. |
| "{m1.name} record vs {m2.name}" subtext | string | DERIVED (label) | manager names |
| "{pf} — {pa}" PF/PA in matchups | numbers (1 dp) | SYNTHETIC (`getH2HData`) | Same as above |
| "PF vs PA in H2H matchups" subtext | string | hardcoded | n/a |

### Win-split horizontal bar

| Field | Type | Status | Source needed |
|---|---|---|---|
| m1 color dot + "{m1.name} ({wins}W)" label (left) | color + label | FAKE (manager.color) + SYNTHETIC (wins) | matchup history |
| m2 color dot + "{m2.name} ({losses}W)" label (right) | color + label | FAKE + SYNTHETIC | same |
| Stacked bar fill: `wins/total` proportion in m1 color, remainder in m2 color | progress bar (%) | DERIVED from synthetic wins/losses | same |
| "{m1pct}% win rate for {m1.name}" caption | % | DERIVED | same |

### Recent matchups list (last 8 weeks descending)

| Column | Type | Status | Source needed |
|---|---|---|---|
| "{yr} Wk {wk}" cell | composite | SYNTHETIC (seeded random `wk` 1–13, ordered by yr/wk desc) | real matchups |
| m1 name (win-highlighted) | string | DERIVED | manager registry |
| m1 score (`sc1`, 2 dp) | number | SYNTHETIC | weekly score export |
| separator dash | decorative | n/a | n/a |
| m2 score (`sc2`, 2 dp) | number | SYNTHETIC | weekly score export |
| m2 name (win-highlighted) | string | DERIVED | manager registry |
| "{winner.name} W" tag | string | DERIVED | matchup result |

**Derived/computed fields needing logic**: The whole panel is fake even before the table is sorted — `getH2HData()` synthesises 1–2 matchups per season per pair using `Math.sin`-based seeded RNG keyed on the two manager IDs and year. Replacing with real data requires a season-by-week matchup table with both teams' scores.

---

## managers  (Manager Profiles)

UI block in `ManagerProfiles()` (lines ~1049–1093) plus `ManagerModal()` (lines ~933–1047). Grid of 10 cards + click-to-open modal.

### Manager card (per `ALL_TIME` row)

| Field | Type | Status | Source needed |
|---|---|---|---|
| Ribbon "{n}× Champ" (only if `championships > 0`) | string | FAKE (championships count) | championship history |
| Card avatar (large colored block with initials) | color block + initials | FAKE (`MANAGERS[].color` + initials of name) | real manager headshot URLs |
| `name` | string | FAKE | manager registry |
| `team` (single team string) | string | FAKE | season-historical teams (today: one hardcoded "current" team per manager) |
| Stat #1: "Career Record" = `{wins}–{losses}` | composite | DERIVED via `computeAllTime` | per-season W/L history |
| Stat #2: "Win Rate" = `{winPct}%` | % | DERIVED | per-season W/L history |
| Stat #3: "Avg PF/Szn" | number (1 dp) | DERIVED | per-season PF history |
| Stat #4: "Titles" (count, gold or dim) | number | FAKE | championship history |
| "View full profile →" CTA | string | hardcoded | n/a |

### Manager modal (`ManagerModal`, opens on card click)

| Field | Type | Status | Source needed |
|---|---|---|---|
| Header avatar (color block, 52×52) | color block + initials | FAKE | real headshot |
| Modal title `name` | string | FAKE | manager registry |
| "{n}× Champ" badge in title | string | FAKE | championship history |
| Subtext team name | string | FAKE | season-historical teams |
| Close button (✕) | UI control | n/a | n/a |
| KPI tile 1: "Career Record" = `{totalW}–{totalL}` | composite | DERIVED via `computeManagerCareer` | per-season W/L |
| KPI tile 2: "Win Rate" % (green) | % (1 dp) | DERIVED | per-season W/L |
| KPI tile 3: "Career PF" | number (0 dp) | DERIVED | per-season PF |
| KPI tile 4: "Championships" count (gold if >0) | number | FAKE | championship history |
| **Season-by-Season table**: | | | |
| Col `Season` | year | FAKE (career rows from `SEASON_STANDINGS`) | season history |
| Col `Finish` (#1/#2/#3 colored, with "Champ" badge if `row.champion`) | composite | FAKE | season history |
| Col `W` | number | FAKE | season history |
| Col `L` | number | FAKE | season history |
| Col `PF` | number (1 dp) | FAKE | season history |
| Col `PA` | number (1 dp) | FAKE | season history |
| Col `Playoffs` (✓ if `row.playoffs`, else `—`) | boolean | **REMOVE** — league has no playoffs; drop this column from the season-by-season table | n/a |
| **Personal Bests** panel: | | | |
| "Best Season PF" big number + year subtext | number, year | DERIVED (`career.reduce` max on `pf`) | season PF history |
| "Championships Won" comma-joined years (or `—`) | string | FAKE (`MANAGERS[].championships`) | championship history |
| **Manager Profile** narrative `SIGS[manager.id]` paragraph | long string | FAKE (hardcoded blurbs for ids 1–10) | Editorial copy — not in any data source |

**Derived/computed fields needing logic**: The cards and modal pull entirely from the fake `MANAGERS` + `SEASON_STANDINGS` + `PLAYOFFS` constants via `computeAllTime` and `computeManagerCareer`. There is no Fantrax data behind any of it. To wire it up you need:

1. A persistent manager identity registry (id → real name, headshot URL, accent color)
2. A mapping of Fantrax `fantasyTeam` strings (e.g. `"3-Tonali Vision"`, `"3 - Bags"`) → manager id
3. A historical standings table per year per manager (W/L/PF/PA/finish). Championship status is just `finish == 1` — no separate playoff/champion file needed.

---

## standings  (Live Standings)

UI block in `LiveStandings()` (lines ~1131–1205). **This section is wired to real data via `FANTRAX_STANDINGS` (`fantrax_data.js`, sourced from `standings.csv`).**

### Header / metadata

| Field | Type | Status | Source needed |
|---|---|---|---|
| "Live Data · GW37" eyebrow label | string | FAKE — gameweek "GW37" is hardcoded literal | Should be derived from latest GW in `transaction_history.csv`/`schedule` |
| Section title "Current Standings" | string | hardcoded | n/a |
| Subtitle "Full league table — all three divisions." | string | hardcoded | n/a |
| "Exported {FANTRAX_EXPORT_DATE}" line | date string | REAL (`FANTRAX_EXPORT_DATE = "2026-05-16"` from `fantrax_data.js`) | already wired |

### Division filter tabs

| Field | Type | Status | Source needed |
|---|---|---|---|
| Tabs: "All", "Division 1", "Division 2", "Division 3" | enum buttons | hardcoded labels, REAL filter against `r.div` | already wired |

### Standings table columns

Driven by `FANTRAX_STANDINGS` array; each row keys: `rk, team, name, div, w, d, l, pts, winPct, fptsF, fptsA, streak`.

| Column | Type | Status | Source CSV column |
|---|---|---|---|
| `Rk` (with gold/silver/bronze styling for top 3) | number | REAL | `standings.csv → Rk` |
| `Team` cell — `DivBadge` ("D1/D2/D3" colored pill) + team name (`name`, stripped of `"3-"` prefix) | composite | REAL | `standings.csv → Div, Team` |
| `W` (green) | number | REAL | `standings.csv → W` |
| `D` (draws) | number | REAL | `standings.csv → D` |
| `L` | number | REAL | `standings.csv → L` |
| `Pts` (bold) | number | REAL | `standings.csv → Points` |
| `FPts For` (1 dp) | number | REAL | `standings.csv → FPtsF` |
| `FPts Ag` (1 dp) | number | REAL | `standings.csv → FPtsA` |
| `Streak` (colored green for W, red for L, neutral else) — value like `"2 (W)"`, `"10 (W)"`, `"4 (L)"`, `"19 (Wnl)"` | string | REAL | `standings.csv → Streak` |
| Column sort arrows (▲/▼) — sortable on `rk`, `w`, `pts`, `fptsF`, `fptsA` | UI control | REAL | client-side sort |

**Derived/computed fields needing logic**:
- `Win%` from `standings.csv` exists in the data (`r.winPct`) but is **not displayed** in the live standings table.
- "GW37" header label should be wired to a real gameweek (currently a literal string).
- The team-name prefix stripping ("`3-Tonali Vision`" → "Tonali Vision") is done in JSX via regex.

---

## roster  (My Roster)

UI block in `MyRoster()` (lines ~1209–1285). **Wired to real data via `FANTRAX_ROSTER` (`fantrax_data.js`, sourced from `roster.csv`).**

### Tabs

| Field | Type | Status | Source needed |
|---|---|---|---|
| "Active" tab (filters `status === 'Act'`) | enum | REAL filter | already wired |
| "Reserve / IR" tab (filters `status === 'Res' || status === 'IR'`) | enum | REAL filter | already wired |

### Position grouping

Group headers (single-cell row spanning the full table) for each non-empty group, in order: `GK, DEF, MID, FWD` (mapped from `G/D/M/F`).

| Field | Type | Status | Source |
|---|---|---|---|
| Position group header | string | DERIVED from `posLabel` map of `pos` | `roster.csv → Pos` (or `Eligible`) |

### Roster table columns

Each row keys (from `FANTRAX_ROSTER`): `player, team, pos, status, opponent, fpts, fpg, gp`.

| Column | Type | Status | Source CSV column |
|---|---|---|---|
| `Player` (bold) | string | REAL | `roster.csv → Player` |
| `Pos` (muted) | string | REAL | `roster.csv → Pos` (`G/D/M/F`) |
| `Team` (3-letter club code, muted) | string | REAL | `roster.csv → Team` |
| `Status` — colored pill: "Active" / "Reserve" / "IR" (via `statusEl`) | enum | REAL | `roster.csv → Status` (`Act` / `Res` / `IR`) |
| `Next Match` (`opponent` string like "NOT Sun 7:30AM" or "@BOU Tue 2:30PM"; `—` if blank) | string | REAL | `roster.csv → Opponent` |
| `FPts` (green, 2 dp) | number | REAL | `roster.csv → Fantasy Points` |
| `FP/G` (2 dp) | number | REAL | `roster.csv → Average Fantasy Points per Game` |
| `GP` | number | REAL | `roster.csv → GP` |
| Empty-state row ("No players in this group.") | string | hardcoded | n/a |

**Derived/computed fields needing logic**: None — UI matches available `FANTRAX_ROSTER` fields exactly. The CSV exposes ~30 deeper per-position stats (GS, Min, MCS, Sv, YC, RC, G, A, KP, AF, Int, CLR, etc.) that are **not surfaced anywhere in the UI** — opportunity to expand. Also, the current page assumes "my" roster but no manager-selector exists (the roster.csv export is single-team).

---

## players  (Player Pool)

UI block in `PlayerPool()` (lines ~1289–1390). **Wired to real data via `FANTRAX_ALL_PLAYERS || FANTRAX_PLAYERS` (sourced from `players.csv`).**

### Filters and search

| Field | Type | Status | Source |
|---|---|---|---|
| Search input ("Search player…") with search SVG icon | text input | REAL (filters `player` substring, case-insensitive) | client-side filter |
| Position tabs: `All Pos`, `G`, `D`, `M`, `F` | enum | REAL | filters `p.pos` |
| Availability tabs: `All`, `Free Agents` (`FA`), `Waivers` (matches `status.startsWith('W')`) | enum | REAL | filters `p.status` |

### Players table columns (top 100 of filtered+sorted)

Each row keys (from `FANTRAX_PLAYERS`): `player, team, pos, rank, status, opponent, fpts, fpg, rostered` (note: the loader prefers `FANTRAX_ALL_PLAYERS` which is currently undefined in `fantrax_data.js`).

| Column | Type | Status | Source CSV column |
|---|---|---|---|
| `Rank` (no medal colors here) | number | REAL | `players.csv → RkOv` |
| `Player` (bold) | string | REAL | `players.csv → Player` |
| `Team` (3-letter club code, muted) | string | REAL | `players.csv → Team` |
| `Pos` (muted) | string | REAL | `players.csv → Position` |
| `Avail` — colored badge: "FA" (purple), "W" (green) via `availEl`, else raw status (dim) | enum | REAL | `players.csv → Status` |
| `Next` (`opponent`, dim) | string | REAL | `players.csv → Opponent` |
| `FPts` (green, 2 dp) | number | REAL | `players.csv → FPts` |
| `FP/G` (2 dp) | number | REAL | `players.csv → FP/G` |
| `Ros%` (e.g. "59%") | string % | REAL | `players.csv → Ros` |
| Sort arrows on `Rank`, `FPts`, `FP/G` | UI control | REAL | client-side sort |
| "Showing top 100 of N matches…" footer caption (only when >100) | string | DERIVED | computed |
| Empty state "No players match your filters." | string | hardcoded | n/a |

**Derived/computed fields needing logic**: None for the displayed fields. `players.csv` has an extra `+/-` (roster-percentage change) column that is **not surfaced**. The component also references `FANTRAX_ALL_PLAYERS` which doesn't exist in the current `fantrax_data.js` (only `FANTRAX_PLAYERS` is defined), so the all-outfield-players promise might be capped to the smaller list actually present.

---

## moves  (Moves & Transactions)

UI block in `RecentMoves()` (lines ~1394–1651). Four tabs: Move Log / Trade History / Busiest Teams / Most Moved Players. Wired to real data via `FANTRAX_TRANSACTIONS`, `FANTRAX_TRADES`, `FANTRAX_TEAM_ACTIVITY`, `FANTRAX_PLAYER_MOVES`.

### Tab navigation

| Field | Type | Status | Source |
|---|---|---|---|
| Tabs: "Move Log", "Trade History", "Busiest Teams", "Most Moved Players" | enum buttons | hardcoded labels | client state |

---

### Tab 1: Move Log

Type sub-filter pills: `All`, `Claim`, `Drop`, `Trade`, `Waiver` (when `Trade` is picked and trade data exists, swaps the data source to `FANTRAX_TRADES`).

Table columns — driven by `FANTRAX_TRANSACTIONS` array, each row: `player, pos, type, fantasyTeam, date, gw`.

| Column | Type | Status | Source CSV column |
|---|---|---|---|
| `Player` (bold) | string | REAL | `transaction_history.csv → Player` |
| `Pos` (muted) | string | REAL | `transaction_history.csv → Position` |
| `Type` (colored move badge: Claim=green, Drop=red, Trade=purple, Waiver=yellow via `moveBadge`) | enum | REAL | `transaction_history.csv → Type` |
| `Fantasy Team` — `DivBadge` (parsed from leading digit of `r.fantasyTeam`) + name (stripped of `"3-"` prefix) | composite | REAL | `transaction_history.csv → Team` (the 2nd "Team" column — fantasy team name) |
| `Date` (e.g. "Fri May 15, 2026, 3:35PM") | string | REAL | `transaction_history.csv → Date (EDT)` |
| `GW` (gameweek number, right-aligned) | number | REAL | `transaction_history.csv → Gameweek` |
| Empty state "No moves match filter." | string | hardcoded | n/a |

**Not surfaced from `transaction_history.csv`**: `Team` (player's club, e.g. "BRF"), `Bid`, `Pr` (price).

---

### Tab 2: Trade History

Currently `FANTRAX_TRADES` is **not defined** in `fantrax_data.js`, so the tab shows: "Trade data will appear here after the next export." (line 1521).

When data is present, three blocks render:

#### Leader card 1 — "Most Traded Players" (top 10 of `tradesData` grouped by player)

| Field | Type | Status | Source |
|---|---|---|---|
| Position tag (`leader-pos` pill) | string | DERIVED from grouped `p.pos` | future trades CSV |
| Player name | string | DERIVED | future trades CSV |
| Trade count "Nx" (purple bold) | number | DERIVED (count of trade rows per player) | future trades CSV |

#### Leader card 2 — "Most Active Traders" (ordered by trade events per team)

| Field | Type | Status | Source |
|---|---|---|---|
| `DivBadge` (parsed from leading digit of team string) | enum | DERIVED | trades CSV |
| Team name (stripped of `"3-"` prefix) | string | DERIVED | trades CSV |
| "N trade(s)" (purple) | number | DERIVED (count of unique trade dates per team) | trades CSV |

#### Trade event cards (one per unique date)

| Field | Type | Status | Source |
|---|---|---|---|
| "Trade" move badge | enum | hardcoded | trades CSV (event type) |
| "GW {ev.gw}" | string | REAL (when present) | trades CSV |
| Trade date | string | REAL (when present) | trades CSV |
| Per-team row: "rcvd" tag + `DivBadge` + team name + list of player tags (`{pos} {player}`) | composite | DERIVED | trades CSV |

**Note**: `FANTRAX_TRADES` schema (inferred from the code) needs at minimum: `{date, gw, fantasyTeam, player, pos}` per row (one row per player in a multi-player trade). Source: a future trade-history Fantrax export (`_debug_trade_history.png` screenshot exists but no CSV).

---

### Tab 3: Busiest Teams

Sortable table driven by `FANTRAX_TEAM_ACTIVITY` array (each row: `team, name, div, claims, drops, trades, total`). The page overlays per-team trade counts from `FANTRAX_TRADES` if present.

| Column | Type | Status | Source |
|---|---|---|---|
| `Team` — `DivBadge` + name | composite | REAL | `FANTRAX_TEAM_ACTIVITY` (derived from `transaction_history.csv` group-by, plus `div` lookup) |
| `Claims` (green) | number | REAL | aggregated from `transaction_history.csv` (Type == Claim) per team |
| `Drops` (red) | number | REAL | aggregated from `transaction_history.csv` (Type == Drop) |
| `Trades` (purple) | number | REAL (currently always 0 in `FANTRAX_TEAM_ACTIVITY`; overlaid from `FANTRAX_TRADES` count of unique dates) | future trades CSV |
| `Total` (bold) | number | DERIVED (claims + drops + trades) | computed |
| Sort arrows on Claims/Drops/Trades/Total | UI control | DERIVED | client-side sort |
| Empty state "No data." | string | hardcoded | n/a |

---

### Tab 4: Most Moved Players

Two side-by-side leader cards driven by `FANTRAX_PLAYER_MOVES = {mostAdded: [...10], mostDropped: [...10]}`. Each list entry: `{player, pos, count}`.

#### Most Added Players

| Field | Type | Status | Source |
|---|---|---|---|
| Position tag (`leader-pos`) | string | REAL | `transaction_history.csv` Position (aggregated where Type=Claim) |
| Player name | string | REAL | same |
| Count "Nx" (purple bold) | number | REAL | same (count per player) |

#### Most Dropped Players

| Field | Type | Status | Source |
|---|---|---|---|
| Position tag | string | REAL | `transaction_history.csv` (Type=Drop) |
| Player name | string | REAL | same |
| Count "Nx" (red bold) | number | REAL | same |

**Derived/computed fields needing logic**:
- "Total" column in Busiest Teams is recomputed as `claims + drops + trades`.
- All Trade History sub-tabs depend on a `FANTRAX_TRADES` export that doesn't yet exist (Fantrax trade-history endpoint is captured in `_debug_trade_history.png` but no CSV).
- `FANTRAX_TEAM_ACTIVITY` is itself a precomputed group-by of `transaction_history.csv` (with `Type ∈ {Claim, Drop}` counted, `trades` left 0); regenerate per export.
- `FANTRAX_PLAYER_MOVES` is the same: a per-player group-by precomputed from `transaction_history.csv`.

---

## Cross-cutting gaps (data referenced across multiple views)

| Concern | Used in | Currently | Needed source |
|---|---|---|---|
| **Manager registry** — id, name, color, current team, championships[] | champions, seasons, h2h, managers, hero ("2024 Champion") | `MANAGERS` array hardcoded inline (10 fake Irish surnames) | A persistent JSON/CSV mapping Fantrax `fantasyTeam` strings (e.g. `"3-Tonali Vision"`) → manager identity. Today the live data has 30 teams (3 divisions × 10) while the fake registry has 10 managers — the two worlds don't reconcile. |
| **Manager avatars/headshots** | champions table, seasons table, managers grid, manager modal | Colored block of initials (`m-avatar` div) generated from `name` + `MANAGERS[].color` | Real image URLs per manager (not in any Fantrax export). |
| **Team logos** | nowhere currently (only the site `LOGO` is referenced, twice — nav + footer; both use the same base64 PNG) | Inline base64 data URI as `LOGO` const at line 291 | Future enhancement: per-fantasy-team or per-club logo URLs. |
| **Per-season standings** (year × manager × W/L/PF/PA/rank) | champions table, seasons table, h2h, managers cards, manager modal, hero champion badge | `SEASON_STANDINGS` hardcoded object with 6 years × 10 managers | No Fantrax CSV today (`standings.csv` covers only current season). Would require Fantrax season-history export or a manually maintained file. Champion per year = `rank == 1` — no separate playoff file needed. |
| **Weekly matchup history** (year × week × home_id × away_id × home_score × away_score) | records (records 1, 2, 3, 9), h2h matchups list, h2h W/L tallies, h2h PF/PA | `RECORDS` array hardcoded; H2H synthesised via `seededRand` | Critical gap. The `_debug_matchups.png` and `_debug_schedule.png` screenshots exist but **no CSV is exported** yet. |
| **Streak and trade-return analytics** | records (records 7, 8, 11) | Hardcoded literals | Derive from weekly matchups + trade dates (both missing). |
| **Gameweek indicator** ("GW37") | standings header eyebrow | Hardcoded string | Derive from max(`Gameweek`) in `transaction_history.csv` or matchups CSV. |
| **DivBadge** ("D1/D2/D3" pill) | standings, moves log, busiest teams, trade leaderboards, trade event cards | DERIVED (parses leading digit of `fantasyTeam` like `"3-Tonali…"`); also stored as `div` int in `FANTRAX_STANDINGS`/`FANTRAX_TEAM_ACTIVITY` | already real |
| **Manager biographical narrative** (`SIGS`) | manager modal "Manager Profile" tab | 10 hardcoded blurbs in `ManagerModal` (lines 939–950) | Editorial copy; no data source |
| **Section-card emojis** (🏆, ⚡, 📉, 🔥, 💀, ⭐, 🔄, 💰, 📊, 📅, 🏃) | champions cards, records cards | Hardcoded inline | n/a (decorative) |

### Data not in any current Fantrax export

The following are referenced (mostly fake) in the UI but have **no corresponding CSV** in `fantrax_data/2026-05-16/`:

1. **Season-history standings / final standings per year** — not in `standings.csv` (current season only). Powers Champions, Seasons, Manager cards, Manager modal, H2H aggregates, Hero "Champion" badge. Champion per year is just `rank == 1` in this dataset — no separate playoff file is needed.
2. **Weekly matchups / weekly scores** — Powers Records cards (1, 2, 3, 6, 7, 8, 9), H2H tab in entirety, Hero "Record Score" KPI.
3. **Trade history CSV** — `FANTRAX_TRADES` referenced in Moves tab but not defined in `fantrax_data.js`. The `_debug_trade_history.png` screenshot exists but no CSV is exported. Powers Trade History tab, trade leaderboards, and the `trades` column in Busiest Teams (currently always 0).
4. **Per-season transaction counts** — Records card 10 ("Most Transactions in a Season"). Could be derived if Fantrax `transaction_history.csv` were exported per season, but today only the current season is captured.
5. **Trade return analytics** (pre/post FPts deltas) — Records card 11 ("Best Trade Return").
6. **Persistent manager registry** mapping Fantrax `fantasyTeam` strings → manager identity (name, headshot, accent color). Currently `MANAGERS` is a parallel fake universe of 10 Irish-named managers that doesn't reconcile with the 30 Fantrax teams in `FANTRAX_STANDINGS`.
7. **Manager headshots / team logos** — image URLs.
8. **Active gameweek indicator** — derivable from `transaction_history.csv` but hardcoded as "GW37" in the standings eyebrow today.
9. **Editorial manager bios** (`SIGS` blurbs) — pure copy, no data source.

### UI elements to remove (not populate) — playoff-related leftovers

The following are filler that should be **deleted from the page** rather than fed real data, because ToggaBoys has no playoff bracket:

- `PLAYOFFS` JS constant (definition + every reference) in `index.html`.
- "Runner-up: {name}" sub-line on each champion card in the Champions carousel.
- `Playoffs` (✓/—) column in the Manager modal's Season-by-Season table.
- "(Championship)" suffix on the Records card #1 "Highest Single-Week Score" subtext — just show the week number.
- Any other inline copy that implies a playoff/championship game (none others found in the current `index.html`).

### Real-data fields available but NOT yet surfaced

These exist in the CSVs / `fantrax_data.js` but the UI doesn't display them:

- `standings.csv → Win%` — value is in `FANTRAX_STANDINGS[].winPct` but the Live Standings table omits it.
- `players.csv → +/-` (roster-% change) — not displayed in the Player Pool.
- `roster.csv` per-position deep stats (`GS, Min, MCS, GA, Sv, YC, RC, FS, PKS, PKD, PKM, TkW, DIS, G, A, A2, KP, AF, Int, IntB, CLR, CoS, AER, AC, HCS, Sm, OG, SOT`) — none of these surface in the Roster table.
- `transaction_history.csv → Team` (player's real club) and `Bid` and `Pr` (waiver bid / claim price) — not displayed in the Move Log.
