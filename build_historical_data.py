"""
build_historical_data.py
------------------------
Reads all per-season CSVs + owners.json, computes derived datasets,
and writes fantrax_historical.js for the React app to consume.

Inputs expected:
    fantrax_data/historical/{year}/standings.csv   (2018-2024)
    fantrax_data/historical/{year}/transactions.csv (optional, for Most Transactions record)
    matchups_{year}.csv                            (optional, needed for weekly records + H2H)
    owners.json                                    (output of scrape_members.py)

Output:
    fantrax_historical.js

Globals written to fantrax_historical.js:
    HIST_SEASONS    -- [2018, 2019, ..., 2024]
    HIST_OWNERS     -- {owner_id: {seasons:{year:teamName}, color, name}}
    HIST_STANDINGS  -- {year: [{owner_id, rank, w, d, l, pts, pf, pa, champion, team_name}]}
    HIST_MATCHUPS   -- [{year, week, t1_owner, t2_owner, t1_score, t2_score}]
    HIST_H2H        -- {"id1_id2": {wins,losses,pf,pa,matches:[{year,week,t1,t2,s1,s2}]}}
    HIST_RECORDS    -- [{icon,label,value,unit,holder,ctx}]  (12 entries)

Run:
    python3 build_historical_data.py
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT          = Path(__file__).parent
HIST_ROOT     = ROOT / "fantrax_data" / "historical"
OWNERS_PATH   = ROOT / "owners.json"
OUT_PATH      = ROOT / "fantrax_historical.js"
SEASONS_PATH  = ROOT / "seasons_filtered.json"

# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def clean_team_name(name):
    return re.sub(r"^\d+\s*[-–]\s*", "", str(name)).strip()


def parse_tier(team_name):
    """
    Return tier (1, 2, or 3) parsed from the team-name prefix.
    Returns None for pre-tier era teams (2018-2021, no prefix).
    Tier 1 = Premier League, Tier 2 = Championship, Tier 3 = League One.
    """
    if not team_name:
        return None
    m = re.match(r"^([123])\s*[-–]\s*", str(team_name).strip())
    return int(m.group(1)) if m else None


def is_pl_eligible(tier):
    """A row qualifies for site-wide stats iff PL (tier=1) or pre-tier era (tier=None)."""
    return tier is None or tier == 1


def find_header_line(lines, marker):
    """Return the index of the first line containing marker, or None."""
    for i, line in enumerate(lines):
        if marker in line:
            return i
    return None


def parse_standings_csv(path):
    """
    Parse a Fantrax standings.csv.
    Returns list of dicts: {rank, team, w, d, l, pts, win_pct, pf, pa}.
    """
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        lines = f.readlines()

    header_idx = find_header_line(lines, '"Rk"')
    if header_idx is None:
        header_idx = find_header_line(lines, "Rk")
    if header_idx is None:
        return rows

    data_lines = []
    for line in lines[header_idx:]:
        if not line.strip():
            break
        data_lines.append(line)

    for row in csv.DictReader(data_lines):
        team = row.get("Team", "").strip()
        if not team:
            continue
        rk = row.get("Rk", "0").strip()
        rows.append({
            "rank":    int(rk) if rk.isdigit() else 0,
            "team":    team,
            "w":       int(parse_num(row.get("W", 0))),
            "d":       int(parse_num(row.get("D", 0))),
            "l":       int(parse_num(row.get("L", 0))),
            "pts":     int(parse_num(row.get("Points", 0))),
            "win_pct": row.get("Win%", "").strip(),
            "pf":      parse_num(row.get("FPtsF", 0)),
            "pa":      parse_num(row.get("FPtsA", 0)),
        })
    return rows


def parse_matchups_csv(path):
    """
    Parse a matchups_{year}.csv file.
    Returns deduplicated list: {year, week, t1_team, t2_team, t1_score, t2_score}.

    Fantrax scraper sometimes captures "cross-matchup" what-if rows in addition to
    real games.  We deduplicate by keeping only the first row per (year, week) in
    which each team appears — i.e. each team can play at most one real game per week.
    """
    raw = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                raw.append({
                    "year":     int(row["year"]),
                    "week":     int(row["week"]),
                    "t1_team":  row["t1_team"].strip(),
                    "t2_team":  row["t2_team"].strip(),
                    "t1_score": parse_num(row["t1_score"]),
                    "t2_score": parse_num(row["t2_score"]),
                })
            except (KeyError, ValueError):
                continue

    # Drop rows where both scores are 0 — these are unloaded/scraper-artifact weeks.
    raw = [r for r in raw if not (r["t1_score"] == 0.0 and r["t2_score"] == 0.0)]

    # Deduplicate: one real game per team per week.
    seen_teams: dict = {}   # (year, week) -> set of team names seen so far
    rows = []
    for r in raw:
        key = (r["year"], r["week"])
        seen = seen_teams.setdefault(key, set())
        if r["t1_team"] not in seen and r["t2_team"] not in seen:
            seen.add(r["t1_team"])
            seen.add(r["t2_team"])
            rows.append(r)
    return rows


def parse_transactions_csv(path):
    """Return total transaction count for the season."""
    count = 0
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("Player", "").strip():
                count += 1
    return count


# ── Owner / team name mapping ─────────────────────────────────────────────────

def build_team_to_owner(owners: dict):
    """
    Build a dict from raw Fantrax team-name string → owner_id.
    Handles both bare names ("Tonali Vision") and prefixed names ("3-Tonali Vision").
    """
    mapping = {}
    for owner_id, data in owners.items():
        for year, team_name in data.get("seasons", {}).items():
            mapping[team_name.strip()] = owner_id
            mapping[clean_team_name(team_name)] = owner_id
    return mapping


def resolve_owner(team_name: str, team_to_owner: dict):
    """Return owner_id for a team name string, or None."""
    t = team_name.strip()
    if t in team_to_owner:
        return team_to_owner[t]
    cleaned = clean_team_name(t)
    if cleaned in team_to_owner:
        return team_to_owner[cleaned]
    # Try case-insensitive match.
    t_lower = t.lower()
    c_lower = cleaned.lower()
    for k, v in team_to_owner.items():
        if k.lower() in (t_lower, c_lower):
            return v
    return None


# ── Core computations ─────────────────────────────────────────────────────────

def compute_standings(seasons, owners):
    """
    Build HIST_STANDINGS: {year: [{owner_id, rank, w, d, l, pts, pf, pa, champion, team_name}]}.
    Rows without a resolved owner_id are still included with owner_id=None for inspection.
    """
    team_to_owner = build_team_to_owner(owners)
    hist = {}

    for s in seasons:
        year = s["year"]
        csv_path = HIST_ROOT / str(year) / "standings.csv"
        if not csv_path.exists():
            print(f"  [{year}] standings.csv not found — skipping")
            continue

        raw = parse_standings_csv(csv_path)
        if not raw:
            print(f"  [{year}] standings.csv parsed 0 rows — check file")
            continue

        rows = []
        for r in raw:
            owner_id = resolve_owner(r["team"], team_to_owner)
            if not owner_id:
                print(f"  [{year}] WARNING: no owner match for team '{r['team']}'")
            tier = parse_tier(r["team"])
            rows.append({
                "owner_id":  owner_id,
                "team_name": clean_team_name(r["team"]),
                "tier":      tier,
                "rank":      r["rank"],
                "tier_rank": 0,        # filled in below
                "w":         r["w"],
                "d":         r["d"],
                "l":         r["l"],
                "pts":       r["pts"],
                "pf":        round(r["pf"], 3),
                "pa":        round(r["pa"], 3),
                "champion":  False,    # filled in below
            })
        # Compute tier_rank by grouping rows by tier and renumbering within group.
        by_tier = defaultdict(list)
        for row in rows:
            by_tier[row["tier"]].append(row)
        for tier_val, group in by_tier.items():
            group.sort(key=lambda x: x["rank"])
            for i, row in enumerate(group, start=1):
                row["tier_rank"] = i
                if i == 1 and is_pl_eligible(tier_val):
                    row["champion"] = True
        hist[year] = sorted(rows, key=lambda x: x["rank"])
        print(f"  [{year}] {len(rows)} teams in standings")

    return hist


def compute_matchups(seasons, owners):
    """
    Build HIST_MATCHUPS: flat list with owner IDs resolved.
    Returns (matchup_rows, unresolved_count).
    """
    team_to_owner = build_team_to_owner(owners)
    all_rows = []
    unresolved = 0

    for s in seasons:
        year = s["year"]
        # Look in HIST_ROOT/{year}/matchups_{year}.csv first; fall back to ROOT.
        csv_path = HIST_ROOT / str(year) / f"matchups_{year}.csv"
        if not csv_path.exists():
            csv_path = ROOT / f"matchups_{year}.csv"
        if not csv_path.exists():
            continue

        raw = parse_matchups_csv(csv_path)
        print(f"  [{year}] {len(raw)} matchup rows in CSV")
        for r in raw:
            t1_owner = resolve_owner(r["t1_team"], team_to_owner)
            t2_owner = resolve_owner(r["t2_team"], team_to_owner)
            if not t1_owner:
                print(f"    WARNING [{year} Wk{r['week']}]: no owner for '{r['t1_team']}'")
                unresolved += 1
            if not t2_owner:
                print(f"    WARNING [{year} Wk{r['week']}]: no owner for '{r['t2_team']}'")
                unresolved += 1
            t1_tier = parse_tier(r["t1_team"])
            t2_tier = parse_tier(r["t2_team"])
            # Same-tier always expected (verified: 0 cross-tier rows). Fall back to None if mismatch.
            mtier = t1_tier if t1_tier == t2_tier else None
            all_rows.append({
                "year":     r["year"],
                "week":     r["week"],
                "tier":     mtier,
                "t1_owner": t1_owner,
                "t2_owner": t2_owner,
                "t1_team":  clean_team_name(r["t1_team"]),
                "t2_team":  clean_team_name(r["t2_team"]),
                "t1_score": round(r["t1_score"], 2),
                "t2_score": round(r["t2_score"], 2),
            })

    return all_rows, unresolved


def compute_h2h(matchups):
    """
    Build HIST_H2H: {"ownA:ownB": {wins,losses,pf,pa,matches:[last 8 desc]}}.
    Key is always sorted(ownA, ownB) joined with ':' so each pair has one entry.
    wins/losses are from ownA's perspective (lower sorted id = "first").
    """
    pairs = defaultdict(lambda: {"wins": 0, "losses": 0, "pf": 0.0, "pa": 0.0, "matches": []})

    for m in matchups:
        if not is_pl_eligible(m.get("tier")):
            continue
        a, b = m["t1_owner"], m["t2_owner"]
        if not a or not b or a == b:
            continue
        # Normalise pair key: alphabetically sorted.
        first, second = (a, b) if a < b else (b, a)
        key = f"{first}:{second}"
        entry = pairs[key]

        t1_win = m["t1_score"] > m["t2_score"]
        if a == first:
            # first=a=t1
            if t1_win:
                entry["wins"] += 1
            else:
                entry["losses"] += 1
            entry["pf"] += m["t1_score"]
            entry["pa"] += m["t2_score"]
        else:
            # first=b=t2
            if not t1_win:
                entry["wins"] += 1
            else:
                entry["losses"] += 1
            entry["pf"] += m["t2_score"]
            entry["pa"] += m["t1_score"]

        entry["matches"].append({
            "year":  m["year"],
            "week":  m["week"],
            "t1":    a,
            "t2":    b,
            "s1":    m["t1_score"],
            "s2":    m["t2_score"],
        })

    # Sort match history desc, keep last 8.
    result = {}
    for key, entry in pairs.items():
        entry["matches"] = sorted(
            entry["matches"],
            key=lambda x: (x["year"], x["week"]),
            reverse=True,
        )[:8]
        entry["pf"] = round(entry["pf"], 2)
        entry["pa"] = round(entry["pa"], 2)
        result[key] = entry

    return result


def compute_records(hist_standings, matchups, owners, seasons):
    """
    Compute the 12 Records cards. Returns list of dicts.
    Each non-placeholder card also carries:
      - top_all: list of up to 10 instances ranked by the record metric (best first).
      - top_per_manager: same, but at most one entry per manager (best entry per owner).
    Placeholder records (#9, #11) have no top lists.

    All inputs are filtered to PL-eligible (tier 1) for 2022+ seasons; pre-tier
    seasons (2018-2021) count fully.
    """
    # Helper: get display name for an owner_id.
    def owner_name(owner_id):
        if not owner_id or owner_id not in owners:
            return "Unknown"
        data = owners[owner_id]
        if data.get("name"):
            return data["name"]
        seasons_map = data.get("seasons", {})
        if seasons_map:
            latest_yr = max(seasons_map.keys(), key=int)
            return clean_team_name(seasons_map[latest_yr])
        return owner_id

    def take_top_lists(candidates, n=10):
        """
        candidates: pre-sorted list of dicts each with {value, holder, ctx, owner_id, _sort}
        Returns (top_all, top_per_manager) — each up to n items, internal keys stripped.
        """
        def strip(x):
            return {k: v for k, v in x.items() if not k.startswith("_")}
        top_all = [strip(c) for c in candidates[:n]]
        seen = set()
        top_per_mgr = []
        for c in candidates:
            oid = c.get("owner_id")
            if oid in seen:
                continue
            seen.add(oid)
            top_per_mgr.append(strip(c))
            if len(top_per_mgr) >= n:
                break
        return top_all, top_per_mgr

    def empty_card(icon, label, unit, ctx_msg):
        return {"icon": icon, "label": label, "value": "—", "unit": unit,
                "holder": "—", "ctx": ctx_msg, "top_all": [], "top_per_manager": []}

    records = []

    # PL-eligible matchups only.
    pl_matchups = [m for m in matchups if is_pl_eligible(m.get("tier"))]

    # ── #1 Highest Single-Week Score ─────────────────────────────────────────
    if pl_matchups:
        cands = []
        for m in pl_matchups:
            for side in (1, 2):
                score = m[f"t{side}_score"]
                oid = m[f"t{side}_owner"]
                cands.append({
                    "value": f"{score:.1f}", "_sort": score, "unit": "pts",
                    "holder": owner_name(oid), "owner_id": oid,
                    "ctx": f"Week {m['week']} · {m['year']}",
                })
        cands.sort(key=lambda x: x["_sort"], reverse=True)
        top_all, top_per = take_top_lists(cands)
        records.append({
            "icon": "⚡", "label": "Highest Single-Week Score", "unit": "pts",
            "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
            "top_all": top_all, "top_per_manager": top_per,
        })
    else:
        records.append(empty_card("⚡", "Highest Single-Week Score", "pts", "Matchup data not yet collected"))

    # ── #2 Lowest Single-Week Score ──────────────────────────────────────────
    if pl_matchups:
        cands = []
        for m in pl_matchups:
            for side in (1, 2):
                score = m[f"t{side}_score"]
                oid = m[f"t{side}_owner"]
                cands.append({
                    "value": f"{score:.1f}", "_sort": score, "unit": "pts",
                    "holder": owner_name(oid), "owner_id": oid,
                    "ctx": f"Week {m['week']} · {m['year']}",
                })
        cands.sort(key=lambda x: x["_sort"])  # ascending — lowest first
        top_all, top_per = take_top_lists(cands)
        records.append({
            "icon": "📉", "label": "Lowest Single-Week Score", "unit": "pts",
            "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
            "top_all": top_all, "top_per_manager": top_per,
        })
    else:
        records.append(empty_card("📉", "Lowest Single-Week Score", "pts", "Matchup data not yet collected"))

    # ── #3 Biggest Win Margin ────────────────────────────────────────────────
    if pl_matchups:
        cands = []
        for m in pl_matchups:
            margin = abs(m["t1_score"] - m["t2_score"])
            t1_won = m["t1_score"] > m["t2_score"]
            win_oid = m["t1_owner"] if t1_won else m["t2_owner"]
            lose_oid = m["t2_owner"] if t1_won else m["t1_owner"]
            cands.append({
                "value": f"{margin:.1f}", "_sort": margin, "unit": "pts",
                "holder": owner_name(win_oid), "owner_id": win_oid,
                "ctx": f"def. {owner_name(lose_oid)} by {margin:.1f} · Wk {m['week']} · {m['year']}",
            })
        cands.sort(key=lambda x: x["_sort"], reverse=True)
        top_all, top_per = take_top_lists(cands)
        records.append({
            "icon": "🏃", "label": "Biggest Win Margin", "unit": "pts",
            "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
            "top_all": top_all, "top_per_manager": top_per,
        })
    else:
        records.append(empty_card("🏃", "Biggest Win Margin", "pts", "Matchup data not yet collected"))

    # ── #4 Most Points in a Season ───────────────────────────────────────────
    cands = []
    for year, rows in hist_standings.items():
        for r in rows:
            if not is_pl_eligible(r.get("tier")):
                continue
            if r["pf"] <= 0:
                continue
            cands.append({
                "value": f"{r['pf']:,.1f}", "_sort": r["pf"], "unit": "pts",
                "holder": owner_name(r["owner_id"]), "owner_id": r["owner_id"],
                "ctx": f"{year} Regular Season",
            })
    if cands:
        cands.sort(key=lambda x: x["_sort"], reverse=True)
        top_all, top_per = take_top_lists(cands)
        records.append({
            "icon": "📅", "label": "Most Points in a Season", "unit": "pts",
            "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
            "top_all": top_all, "top_per_manager": top_per,
        })
    else:
        records.append(empty_card("📅", "Most Points in a Season", "pts", "No standings data"))

    # ── #5 Fewest Points in a Season ─────────────────────────────────────────
    cands = []
    for year, rows in hist_standings.items():
        for r in rows:
            if not is_pl_eligible(r.get("tier")):
                continue
            if r["pf"] <= 0:
                continue
            cands.append({
                "value": f"{r['pf']:,.1f}", "_sort": r["pf"], "unit": "pts",
                "holder": owner_name(r["owner_id"]), "owner_id": r["owner_id"],
                "ctx": f"{year} Regular Season",
            })
    if cands:
        cands.sort(key=lambda x: x["_sort"])  # ascending — fewest first
        top_all, top_per = take_top_lists(cands)
        records.append({
            "icon": "📉", "label": "Fewest Points in a Season", "unit": "pts",
            "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
            "top_all": top_all, "top_per_manager": top_per,
        })
    else:
        records.append(empty_card("📉", "Fewest Points in a Season", "pts", "No standings data"))

    # ── #6 Best Regular Season Record ────────────────────────────────────────
    cands = []
    for year, rows in hist_standings.items():
        for r in rows:
            if not is_pl_eligible(r.get("tier")):
                continue
            total = r["w"] + r["l"] + r["d"]
            if total == 0:
                continue
            pct = r["w"] / total
            cands.append({
                "value": f"{r['w']}-{r['l']}", "_sort": pct, "unit": "",
                "holder": owner_name(r["owner_id"]), "owner_id": r["owner_id"],
                "ctx": f"{year} · {pct*100:.1f}% win rate",
            })
    if cands:
        cands.sort(key=lambda x: x["_sort"], reverse=True)
        top_all, top_per = take_top_lists(cands)
        records.append({
            "icon": "🏆", "label": "Best Regular Season Record", "unit": "",
            "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
            "top_all": top_all, "top_per_manager": top_per,
        })
    else:
        records.append(empty_card("🏆", "Best Regular Season Record", "", "No standings data"))

    # ── #7 + #8: streaks — enumerate every streak, take top 10 ───────────────
    def enumerate_streaks(season_results, win=True):
        out = []
        for year, omap in season_results.items():
            for oid, res_list in omap.items():
                cur, start_idx = 0, 0
                for i, outcome in enumerate(res_list):
                    if outcome == win:
                        if cur == 0:
                            start_idx = i
                        cur += 1
                    else:
                        if cur > 0:
                            out.append({"owner_id": oid, "year": year, "length": cur,
                                        "start_wk": start_idx + 1, "end_wk": i})
                        cur = 0
                if cur > 0:  # trailing
                    out.append({"owner_id": oid, "year": year, "length": cur,
                                "start_wk": start_idx + 1, "end_wk": len(res_list)})
        return out

    if pl_matchups:
        season_results = defaultdict(lambda: defaultdict(list))
        for m in sorted(pl_matchups, key=lambda m: (m["year"], m["week"])):
            if m["t1_owner"]:
                season_results[m["year"]][m["t1_owner"]].append(m["t1_score"] > m["t2_score"])
            if m["t2_owner"]:
                season_results[m["year"]][m["t2_owner"]].append(m["t2_score"] > m["t1_score"])

        # Winning streaks
        w_streaks = enumerate_streaks(season_results, win=True)
        w_cands = [{
            "value": str(s["length"]), "_sort": s["length"], "unit": "straight",
            "holder": owner_name(s["owner_id"]), "owner_id": s["owner_id"],
            "ctx": f"Weeks {s['start_wk']}–{s['end_wk']} · {s['year']}",
        } for s in w_streaks]
        w_cands.sort(key=lambda x: x["_sort"], reverse=True)
        if w_cands:
            top_all, top_per = take_top_lists(w_cands)
            records.append({
                "icon": "🔥", "label": "Longest Winning Streak", "unit": "straight",
                "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
                "top_all": top_all, "top_per_manager": top_per,
            })
        else:
            records.append(empty_card("🔥", "Longest Winning Streak", "straight", "No streaks computed"))

        # Losing streaks
        l_streaks = enumerate_streaks(season_results, win=False)
        l_cands = [{
            "value": str(s["length"]), "_sort": s["length"], "unit": "straight",
            "holder": owner_name(s["owner_id"]), "owner_id": s["owner_id"],
            "ctx": f"Weeks {s['start_wk']}–{s['end_wk']} · {s['year']}",
        } for s in l_streaks]
        l_cands.sort(key=lambda x: x["_sort"], reverse=True)
        if l_cands:
            top_all, top_per = take_top_lists(l_cands)
            records.append({
                "icon": "💀", "label": "Longest Losing Streak", "unit": "straight",
                "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
                "top_all": top_all, "top_per_manager": top_per,
            })
        else:
            records.append(empty_card("💀", "Longest Losing Streak", "straight", "No streaks computed"))
    else:
        records.append(empty_card("🔥", "Longest Winning Streak", "straight", "Matchup data not yet collected"))
        records.append(empty_card("💀", "Longest Losing Streak", "straight", "Matchup data not yet collected"))

    # ── #9 Highest Scoring Player Week (placeholder) ─────────────────────────
    records.append({
        "icon": "⭐", "label": "Highest Scoring Player Week",
        "value": "—", "unit": "pts", "holder": "—",
        "ctx": "Requires per-player weekly data (not in Fantrax CSV exports)",
        "top_all": [], "top_per_manager": [],
    })

    # ── #10 Most Transactions in a Season ────────────────────────────────────
    team_to_owner = build_team_to_owner(owners)
    tx_cands = []
    for s in seasons:
        year = s["year"]
        tx_path = HIST_ROOT / str(year) / "transactions.csv"
        if not tx_path.exists():
            continue
        try:
            team_counts = defaultdict(int)
            with open(tx_path, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    player = row.get("Player", "").strip()
                    team = row.get("Team", "").strip()
                    if player and team and is_pl_eligible(parse_tier(team)):
                        team_counts[team] += 1
            for team, count in team_counts.items():
                oid = resolve_owner(team, team_to_owner)
                tx_cands.append({
                    "value": str(count), "_sort": count, "unit": "moves",
                    "holder": owner_name(oid) if oid else clean_team_name(team),
                    "owner_id": oid, "ctx": f"{year} Season",
                })
        except Exception:
            pass

    if tx_cands:
        tx_cands.sort(key=lambda x: x["_sort"], reverse=True)
        top_all, top_per = take_top_lists(tx_cands)
        records.append({
            "icon": "🔄", "label": "Most Transactions in a Season", "unit": "moves",
            "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
            "top_all": top_all, "top_per_manager": top_per,
        })
    else:
        records.append(empty_card("🔄", "Most Transactions in a Season", "moves",
                                  "Historical transaction data not yet collected"))

    # ── #11 Best Trade Return (placeholder) ──────────────────────────────────
    records.append({
        "icon": "💰", "label": "Best Trade Return",
        "value": "—", "unit": "pts avg Δ", "holder": "—",
        "ctx": "Requires pre/post-trade FPts data (not in Fantrax CSV exports)",
        "top_all": [], "top_per_manager": [],
    })

    # ── #12 All-Time Win Rate ────────────────────────────────────────────────
    career = defaultdict(lambda: {"w": 0, "l": 0})
    for year, rows in hist_standings.items():
        for r in rows:
            if not is_pl_eligible(r.get("tier")):
                continue
            if r["owner_id"]:
                career[r["owner_id"]]["w"] += r["w"]
                career[r["owner_id"]]["l"] += r["l"]

    wr_cands = []
    for oid, rec in career.items():
        total = rec["w"] + rec["l"]
        if total == 0:
            continue
        pct = rec["w"] / total
        wr_cands.append({
            "value": f"{pct*100:.1f}", "_sort": pct, "unit": "%",
            "holder": owner_name(oid), "owner_id": oid,
            "ctx": f"{rec['w']}–{rec['l']} career record",
        })
    if wr_cands:
        wr_cands.sort(key=lambda x: x["_sort"], reverse=True)
        top_all, top_per = take_top_lists(wr_cands)
        # For this record, top_all and top_per_manager are identical (per-owner already).
        records.append({
            "icon": "📊", "label": "All-Time Win Rate", "unit": "%",
            "value": top_all[0]["value"], "holder": top_all[0]["holder"], "ctx": top_all[0]["ctx"],
            "top_all": top_all, "top_per_manager": top_per,
        })
    else:
        records.append(empty_card("📊", "All-Time Win Rate", "%", "No standings data"))

    return records


def build_managers_array(owners, hist_standings):
    """
    Derive the MANAGERS-compatible array from HIST_OWNERS + HIST_STANDINGS.
    Used by index.html to replace the hardcoded MANAGERS constant.
    This is emitted as HIST_MANAGERS for the React app.
    """
    team_to_owner = build_team_to_owner(owners)

    # Collect championship years per owner.
    champ_years = defaultdict(list)
    for year, rows in hist_standings.items():
        for r in rows:
            if r["champion"] and r["owner_id"]:
                champ_years[r["owner_id"]].append(year)

    managers = []
    for owner_id, data in owners.items():
        seasons_map = data.get("seasons", {})
        # Most recent team name.
        latest_team = ""
        if seasons_map:
            latest_yr = max(seasons_map.keys(), key=int)
            latest_team = clean_team_name(seasons_map[latest_yr])

        real_name = data.get("name")
        managers.append({
            "id":            owner_id,
            "has_name":      bool(real_name),
            "name":          real_name or latest_team or owner_id,
            "team":          latest_team,
            "color":         data.get("color") or "#555555",
            "championships": sorted(champ_years.get(owner_id, [])),
            "seasons":       seasons_map,
        })

    return sorted(managers, key=lambda m: m["id"])


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not SEASONS_PATH.exists():
        raise SystemExit(f"{SEASONS_PATH} not found. Run discover_seasons.py first.")

    seasons = json.loads(SEASONS_PATH.read_text())
    seasons_sorted = sorted(seasons, key=lambda s: s["year"])
    season_years = [s["year"] for s in seasons_sorted]

    print(f"Building historical data for seasons: {season_years}")

    # ── Load owners ──────────────────────────────────────────────────────────
    owners = {}
    if OWNERS_PATH.exists():
        owners = json.loads(OWNERS_PATH.read_text())
        print(f"Loaded {len(owners)} owners from {OWNERS_PATH}")
    else:
        print(f"WARNING: {OWNERS_PATH} not found — team→owner mapping will be empty.")
        print("Run scrape_members.py first for full owner resolution.")

    # ── Standings ────────────────────────────────────────────────────────────
    print("\nProcessing standings...")
    hist_standings = compute_standings(seasons_sorted, owners)

    # ── Matchups ─────────────────────────────────────────────────────────────
    print("\nProcessing matchups...")
    matchups, unresolved = compute_matchups(seasons_sorted, owners)
    if matchups:
        print(f"  Total matchup rows: {len(matchups)}")
        if unresolved:
            print(f"  WARNING: {unresolved} team names could not be resolved to owner IDs")
    else:
        print("  No matchups_{year}.csv files found yet.")
        print("  Run scrape_matchups.py to collect weekly scores.")

    # ── H2H ──────────────────────────────────────────────────────────────────
    print("\nComputing H2H...")
    h2h = compute_h2h(matchups)
    print(f"  {len(h2h)} unique H2H pairs")

    # ── Records ──────────────────────────────────────────────────────────────
    print("\nComputing records...")
    records = compute_records(hist_standings, matchups, owners, seasons_sorted)
    print(f"  {len(records)} records computed")

    # ── Managers array ───────────────────────────────────────────────────────
    managers = build_managers_array(owners, hist_standings)
    print(f"  {len(managers)} managers in HIST_MANAGERS")

    # ── Emit JS ──────────────────────────────────────────────────────────────
    print(f"\nWriting {OUT_PATH}...")

    # Convert hist_standings keys to int-keyed dict for JSON (years as ints).
    hist_standings_out = {str(yr): rows for yr, rows in hist_standings.items()}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("// Auto-generated by build_historical_data.py — do not edit by hand.\n")
        f.write(f"const HIST_SEASONS = {json.dumps(season_years)};\n")
        f.write(f"const HIST_OWNERS = {json.dumps(owners, indent=2)};\n")
        f.write(f"const HIST_MANAGERS = {json.dumps(managers, indent=2)};\n")
        f.write(f"const HIST_STANDINGS = {json.dumps(hist_standings_out, indent=2)};\n")
        f.write(f"const HIST_MATCHUPS = {json.dumps(matchups, indent=2)};\n")
        f.write(f"const HIST_H2H = {json.dumps(h2h, indent=2)};\n")
        f.write(f"const HIST_RECORDS = {json.dumps(records, indent=2)};\n")

    size_kb = OUT_PATH.stat().st_size // 1024
    print(f"  ✓ Wrote {OUT_PATH}  ({size_kb} KB)")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n── Summary ─────────────────────────────────────────────────")
    print(f"  Seasons:  {len(hist_standings)} / {len(season_years)} have standings data")
    print(f"  Matchups: {len(matchups)} weekly results across {len(season_years)} seasons")
    print(f"  H2H:      {len(h2h)} pairs")
    print(f"  Records:  {len(records)}")
    missing = [yr for yr in season_years if yr not in hist_standings]
    if missing:
        print(f"\n  Missing standings for: {missing}")
        print("  Run fantrax_history.py to collect them.")


if __name__ == "__main__":
    main()
