"""
Reads latest fantrax_data/ CSVs and writes fantrax_data.js for the website.
Run after fantrax_export.py: python generate_data.py
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
DATA_ROOT = ROOT / "fantrax_data"


def latest_dir():
    dirs = [d for d in DATA_ROOT.iterdir() if d.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', d.name)]
    return sorted(dirs)[-1]


def parse_num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def div_from_name(name):
    m = re.match(r'^(\d+)\s*[-–]', name)
    return int(m.group(1)) if m else 0


def clean_team_name(name):
    return re.sub(r'^\d+\s*[-–]\s*', '', name).strip()


def strip_html(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()


def parse_standings(path):
    rows = []
    with open(path, encoding='utf-8', newline='') as f:
        lines = f.readlines()

    # Find column header line (contains "Rk")
    header_idx = next((i for i, l in enumerate(lines) if '"Rk"' in l), None)
    if header_idx is None:
        return rows

    # Collect lines until blank (stops before Gameweek matchup section)
    data_lines = []
    for line in lines[header_idx:]:
        if not line.strip():
            break
        data_lines.append(line)

    for row in csv.DictReader(data_lines):
        team = row.get('Team', '').strip()
        rows.append({
            'rk':      int(row.get('Rk', 0) or 0),
            'team':    team,
            'name':    clean_team_name(team),
            'div':     div_from_name(team),
            'w':       int(row.get('W', 0) or 0),
            'd':       int(row.get('D', 0) or 0),
            'l':       int(row.get('L', 0) or 0),
            'pts':     int(row.get('Points', 0) or 0),
            'winPct':  row.get('Win%', '').strip(),
            'fptsF':   parse_num(row.get('FPtsF', 0)),
            'fptsA':   parse_num(row.get('FPtsA', 0)),
            'streak':  row.get('Streak', '').strip(),
        })
    return rows


def parse_roster(path):
    """Parse the two-section roster CSV (Goalkeeper / Outfielder)."""
    players = []
    with open(path, encoding='utf-8', newline='') as f:
        lines = f.readlines()

    # Locate section header indices
    section_starts = []
    for i, line in enumerate(lines):
        if '"Goalkeeper"' in line or '"Outfielder"' in line:
            section_starts.append(i + 1)  # header row follows

    section_starts.append(len(lines))  # sentinel

    for start, end in zip(section_starts, section_starts[1:]):
        # Stop each section at first blank line (avoids bleeding into next section header)
        section_raw = []
        for line in lines[start:end]:
            if not line.strip():
                break
            section_raw.append(line)
        if not section_raw:
            continue
        for row in csv.DictReader(section_raw):
            # row values may be None when the row has fewer columns than the header
            player = (row.get('Player') or '').strip()
            if not player:
                continue
            players.append({
                'player':   player,
                'team':     (row.get('Team') or '').strip(),
                'pos':      (row.get('Pos') or '').strip(),
                'status':   (row.get('Status') or '').strip(),
                'opponent': strip_html(row.get('Opponent') or ''),
                'fpts':     parse_num(row.get('Fantasy Points') or 0),
                'fpg':      parse_num(row.get('Average Fantasy Points per Game') or 0),
                'gp':       int(parse_num(row.get('GP') or 0)),
            })
    return players


def parse_players(path, top_n=150):
    rows = []
    with open(path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            player = row.get('Player', '').strip()
            if not player:
                continue
            rk_raw = row.get('RkOv', '').strip()
            rows.append({
                'player':   player,
                'team':     row.get('Team', '').strip(),
                'pos':      row.get('Position', '').strip(),
                'rank':     int(rk_raw) if rk_raw.isdigit() else 9999,
                'status':   strip_html(row.get('Status', '')),
                'opponent': strip_html(row.get('Opponent', '')),
                'fpts':     parse_num(row.get('FPts', 0)),
                'fpg':      parse_num(row.get('FP/G', 0)),
                'rostered': row.get('Ros', '').strip(),
            })
    rows.sort(key=lambda r: r['fpts'], reverse=True)
    return rows[:top_n]


def parse_transactions(path, recent_n=100):
    """
    Returns (recent_list, team_activity, player_moves).
    Note: 'Team' appears twice in the CSV header; csv.DictReader keeps the last
    value, which is the fantasy team name — exactly what we need here.
    """
    all_rows = []
    with open(path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            player = row.get('Player', '').strip()
            if not player:
                continue
            all_rows.append({
                'player':      player,
                'pos':         row.get('Position', '').strip(),
                'type':        row.get('Type', '').strip(),
                'fantasyTeam': row.get('Team', '').strip(),  # second "Team" col
                'date':        row.get('Date (EDT)', '').strip(),
                'gw':          row.get('Gameweek', '').strip(),
            })

    recent = all_rows[:recent_n]

    # Team activity totals
    team_counts = defaultdict(lambda: {'claims': 0, 'drops': 0, 'trades': 0})
    for r in all_rows:
        t = r['fantasyTeam']
        if not t:
            continue
        tp = r['type']
        if tp in ('Claim', 'Waiver'):
            team_counts[t]['claims'] += 1
        elif tp == 'Drop':
            team_counts[t]['drops'] += 1
        elif tp == 'Trade':
            team_counts[t]['trades'] += 1

    team_activity = sorted([
        {
            'team':    t,
            'name':    clean_team_name(t),
            'div':     div_from_name(t),
            'claims':  c['claims'],
            'drops':   c['drops'],
            'trades':  c['trades'],
            'total':   c['claims'] + c['drops'] + c['trades'],
        }
        for t, c in team_counts.items()
    ], key=lambda x: x['total'], reverse=True)

    # Most claimed / most dropped players
    claims_count = defaultdict(lambda: {'count': 0, 'pos': ''})
    drops_count  = defaultdict(lambda: {'count': 0, 'pos': ''})
    for r in all_rows:
        name, pos, tp = r['player'], r['pos'], r['type']
        if tp == 'Claim':
            claims_count[name]['count'] += 1
            claims_count[name]['pos'] = pos
        elif tp == 'Drop':
            drops_count[name]['count'] += 1
            drops_count[name]['pos'] = pos

    most_added   = sorted(
        [{'player': k, 'pos': v['pos'], 'count': v['count']} for k, v in claims_count.items()],
        key=lambda x: x['count'], reverse=True
    )[:10]
    most_dropped = sorted(
        [{'player': k, 'pos': v['pos'], 'count': v['count']} for k, v in drops_count.items()],
        key=lambda x: x['count'], reverse=True
    )[:10]

    return recent, team_activity, {'mostAdded': most_added, 'mostDropped': most_dropped}


def parse_trades(path):
    rows = []
    with open(path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            player = row.get('Player', '').strip()
            if not player:
                continue
            rows.append({
                'player':      player,
                'pos':         row.get('Position', '').strip(),
                'type':        row.get('Type', '').strip(),
                'fantasyTeam': row.get('Team', '').strip(),
                'date':        row.get('Date (EDT)', '').strip(),
                'gw':          row.get('Gameweek', '').strip(),
            })
    return rows


def parse_all_players(path, top_n=500):
    rows = []
    with open(path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            player = row.get('Player', '').strip()
            if not player:
                continue
            pos = row.get('Position', '').strip()
            if pos == 'GK':
                continue
            rk_raw = row.get('RkOv', '').strip()
            rows.append({
                'player':   player,
                'team':     row.get('Team', '').strip(),
                'pos':      pos,
                'rank':     int(rk_raw) if rk_raw.isdigit() else 9999,
                'status':   strip_html(row.get('Status', '')),
                'opponent': strip_html(row.get('Opponent', '')),
                'fpts':     parse_num(row.get('FPts', 0)),
                'fpg':      parse_num(row.get('FP/G', 0)),
                'rostered': row.get('Ros', '').strip(),
            })
    rows.sort(key=lambda r: r['fpts'], reverse=True)
    return rows[:top_n]


def main():
    data_dir = latest_dir()
    export_date = data_dir.name
    print(f"Processing: {export_date}")

    standings            = parse_standings(data_dir / "standings.csv")
    roster               = parse_roster(data_dir / "roster.csv")
    players              = parse_players(data_dir / "players.csv", top_n=150)
    recent, team_act, pm = parse_transactions(data_dir / "transaction_history.csv", recent_n=100)

    trades_path = data_dir / "trades.csv"
    trades = parse_trades(trades_path) if trades_path.exists() else []

    all_players_path = data_dir / "all_players.csv"
    all_players = parse_all_players(all_players_path) if all_players_path.exists() else []

    print(f"  Standings:    {len(standings)} teams")
    print(f"  Roster:       {len(roster)} players")
    print(f"  Player pool:  {len(players)} players (available)")
    print(f"  All players:  {len(all_players)} outfield players")
    print(f"  Transactions: {len(recent)} recent / {len(team_act)} teams tracked")
    print(f"  Trades:       {len(trades)} records")
    print(f"  Most added:   {[p['player'] for p in pm['mostAdded'][:3]]}")
    print(f"  Most dropped: {[p['player'] for p in pm['mostDropped'][:3]]}")

    out = ROOT / "fantrax_data.js"
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f"const FANTRAX_EXPORT_DATE = {json.dumps(export_date)};\n")
        f.write(f"const FANTRAX_STANDINGS = {json.dumps(standings, indent=2)};\n")
        f.write(f"const FANTRAX_ROSTER = {json.dumps(roster, indent=2)};\n")
        f.write(f"const FANTRAX_PLAYERS = {json.dumps(players, indent=2)};\n")
        f.write(f"const FANTRAX_TRANSACTIONS = {json.dumps(recent, indent=2)};\n")
        f.write(f"const FANTRAX_TEAM_ACTIVITY = {json.dumps(team_act, indent=2)};\n")
        f.write(f"const FANTRAX_PLAYER_MOVES = {json.dumps(pm, indent=2)};\n")
        f.write(f"const FANTRAX_TRADES = {json.dumps(trades, indent=2)};\n")
        f.write(f"const FANTRAX_ALL_PLAYERS = {json.dumps(all_players, indent=2)};\n")

    print(f"\nWrote {out}  ({out.stat().st_size // 1024} KB)")


if __name__ == '__main__':
    main()
