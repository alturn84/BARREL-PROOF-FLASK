#!/usr/bin/env python3
"""
Game Cards Generator — Barrel Proof
─────────────────────────────────────
Parses the daily MLB box score markdown file from mlb_fetch.py and writes
Site Data/game_cards.json — structured game data the homepage template
uses to render game summaries and newspaper box scores.

Usage:
    python update_game_cards.py              # yesterday's games
    python update_game_cards.py 2026-05-29  # specific date

Schedule with cron (runs at 8:10 AM daily, after mlb_fetch.py):
    10 8 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 "/Users/allanturner/BARREL PROOF/update_game_cards.py"
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

VAULT    = Path("/Users/allanturner/BARREL PROOF")
DAILY    = VAULT / "Daily"
OUT_FILE = VAULT / "Site Data" / "game_cards.json"

# ── Team abbreviation → full city name ────────────────────────────────────────
TEAM_CITIES = {
    "SD": "San Diego", "WSH": "Washington", "KC": "Kansas City",
    "TEX": "Texas", "LAA": "Los Angeles", "TB": "Tampa Bay",
    "CHC": "Chicago", "STL": "St. Louis", "AZ": "Arizona",
    "SEA": "Seattle", "MIN": "Minnesota", "PIT": "Pittsburgh",
    "MIA": "Miami", "NYM": "New York", "PHI": "Philadelphia",
    "LAD": "Los Angeles", "MIL": "Milwaukee", "HOU": "Houston",
    "SF": "San Francisco", "COL": "Colorado", "BOS": "Boston",
    "CLE": "Cleveland", "ATL": "Atlanta", "CIN": "Cincinnati",
    "DET": "Detroit", "CWS": "Chicago", "TOR": "Toronto",
    "BAL": "Baltimore", "NYY": "New York", "ATH": "Athletics",
    "WAS": "Washington",
}

# ── Parse one game block from the markdown ────────────────────────────────────
def parse_game(block):
    """
    Parses a single game block from the markdown file.
    Returns a dict with all data needed to render the game card.
    """
    lines = block.strip().split('\n')
    game = {}

    # ── Header: ### SD @ WSH — **SD 7**, WSH 5
    header = lines[0] if lines else ''
    m = re.match(r'### (\w+) @ (\w+) — (.+)', header)
    if not m:
        return None
    away_abbr = m.group(1)
    home_abbr = m.group(2)
    score_str = m.group(3)

    # Parse winner/score — bold team is the winner
    score_m = re.findall(r'\*\*(\w+)\s+(\d+)\*\*|(\w+)\s+(\d+)', score_str)
    away_runs = home_runs = 0
    winner_abbr = ''
    for sm in score_m:
        if sm[0]:  # bolded = winner
            winner_abbr = sm[0]
            r = int(sm[1])
            if sm[0] == away_abbr:
                away_runs = r
            else:
                home_runs = r
        else:
            r = int(sm[3])
            if sm[2] == away_abbr:
                away_runs = r
            elif sm[2] == home_abbr:
                home_runs = r

    game['away_abbr']  = away_abbr
    game['home_abbr']  = home_abbr
    game['away_city']  = TEAM_CITIES.get(away_abbr, away_abbr)
    game['home_city']  = TEAM_CITIES.get(home_abbr, home_abbr)
    game['away_runs']  = away_runs
    game['home_runs']  = home_runs
    game['winner']     = 'away' if away_runs > home_runs else 'home'

    # ── Venue / metadata line
    venue_m = re.search(r'\*\*Venue:\*\* ([^·]+)', block)
    game['venue'] = venue_m.group(1).strip() if venue_m else ''

    dur_m = re.search(r'\*\*Duration:\*\* ([^\s·]+)', block)
    game['duration'] = dur_m.group(1).strip() if dur_m else ''

    att_m = re.search(r'\*\*Attendance:\*\* ([\d,]+)', block)
    game['attendance'] = att_m.group(1).strip() if att_m else ''

    # ── Decisions
    dec_m = re.search(r'\*\*Decisions:\*\* (.+)', block)
    decisions = {'W': '', 'L': '', 'SV': ''}
    if dec_m:
        dec_str = dec_m.group(1)
        for key in ('W', 'L', 'SV'):
            km = re.search(rf'{key}: ([^·\n]+?)(?:\s*·|\s*$)', dec_str)
            if km:
                decisions[key] = km.group(1).strip()
    game['decisions'] = decisions

    # ── Line score table
    ls_m = re.search(
        r'\| Team \|(.+?)\n\|[-|]+\|\n\| \*\*' + re.escape(away_abbr) + r'\*\* \|(.+?)\n\| \*\*' + re.escape(home_abbr) + r'\*\* \|(.+?)(?:\n|$)',
        block
    )
    if not ls_m:
        # Try unbolded version for loser rows
        ls_m = re.search(
            r'\| Team \|(.+?)\n\|[-|]+\|\n\|[^|]*' + re.escape(away_abbr) + r'[^|]* \|(.+?)\n\|[^|]*' + re.escape(home_abbr) + r'[^|]* \|(.+?)(?:\n|$)',
            block
        )

    innings = []
    away_line = []
    home_line = []
    if ls_m:
        def parse_row(row):
            cells = [c.strip().strip('*') for c in row.split('|')]
            cells = [c for c in cells if c]
            return cells

        header_cells = parse_row(ls_m.group(1))
        away_cells   = parse_row(ls_m.group(2))
        home_cells   = parse_row(ls_m.group(3))

        # innings are all columns before R H E
        # Last 3 are R H E
        n_inn = len(away_cells) - 3
        innings    = header_cells[:n_inn]
        away_line  = away_cells[:n_inn]  # inning scores
        home_line  = home_cells[:n_inn]
        away_rhe   = away_cells[-3:]
        home_rhe   = home_cells[-3:]
    else:
        away_rhe = [str(away_runs), '', '']
        home_rhe = [str(home_runs), '', '']

    game['innings']   = innings
    game['away_line'] = away_line
    game['home_line'] = home_line
    game['away_rhe']  = away_rhe
    game['home_rhe']  = home_rhe

    # ── Batting tables
    def parse_batting(team_abbr):
        pattern = rf'\*\*{re.escape(team_abbr)} Batting\*\*\n\n\|[^\n]+\|\n\|[-|]+\|\n((?:\|[^\n]+\|\n?)+)'
        m = re.search(pattern, block)
        if not m:
            return []
        rows = []
        for row in m.group(1).strip().split('\n'):
            cells = [c.strip() for c in row.split('|')]
            cells = [c for c in cells if c]
            if len(cells) < 5:
                continue
            # Batter (Pos) | PA | AB | R | H | 2B | 3B | HR | RBI | ...
            batter_pos = cells[0]
            bm = re.match(r'(.+?)\s*\((\w+)\)', batter_pos)
            if bm:
                name = bm.group(1).strip()
                pos  = bm.group(2).strip()
            else:
                name = batter_pos
                pos  = ''
            # Abbreviate name: First initial + Last name
            parts = name.split()
            short = f"{parts[0][0]}.{parts[-1]}" if len(parts) > 1 else name

            try:
                ab  = int(cells[2]) if len(cells) > 2 else 0
                r   = int(cells[3]) if len(cells) > 3 else 0
                h   = int(cells[4]) if len(cells) > 4 else 0
                rbi = int(cells[8]) if len(cells) > 8 else 0
            except (ValueError, IndexError):
                continue

            rows.append({
                'name': short,
                'pos':  pos,
                'ab':   ab,
                'r':    r,
                'h':    h,
                'rbi':  rbi,
            })
        return rows

    game['away_batting'] = parse_batting(away_abbr)
    game['home_batting'] = parse_batting(home_abbr)

    # ── Pitching tables
    def parse_pitching(team_abbr):
        pattern = rf'\*\*{re.escape(team_abbr)} Pitching\*\*\n\n\|[^\n]+\|\n\|[-|]+\|\n((?:\|[^\n]+\|\n?)+)'
        m = re.search(pattern, block)
        if not m:
            return []
        rows = []
        for row in m.group(1).strip().split('\n'):
            cells = [c.strip() for c in row.split('|')]
            cells = [c for c in cells if c]
            if len(cells) < 4:
                continue
            # Pitcher | IP | H | R | ER | BB | K | ...
            name = cells[0].strip()
            parts = name.split()
            short = f"{parts[0][0]}.{parts[-1]}" if len(parts) > 1 else name
            try:
                ip = cells[1]
                er = cells[4] if len(cells) > 4 else ''
                k  = cells[6] if len(cells) > 6 else ''
            except IndexError:
                continue
            rows.append({'name': short, 'ip': ip, 'er': er, 'k': k})
        return rows

    game['away_pitching'] = parse_pitching(away_abbr)
    game['home_pitching'] = parse_pitching(home_abbr)

    # ── Batting notes (HR, 2B etc) for summary generation
    away_notes_m = re.search(
        rf'\*\*{re.escape(away_abbr)} Batting\*\*.*?\n\n\*\*HR:\*\* ([^\n]+)',
        block, re.DOTALL
    )
    home_notes_m = re.search(
        rf'\*\*{re.escape(home_abbr)} Batting\*\*.*?\n\n\*\*HR:\*\* ([^\n]+)',
        block, re.DOTALL
    )
    game['away_hr_notes'] = away_notes_m.group(1).strip() if away_notes_m else ''
    game['home_hr_notes'] = home_notes_m.group(1).strip() if home_notes_m else ''

    return game


# ── Build a brief game summary from parsed data ───────────────────────────────
def build_summary(game):
    """Generate a 2-3 sentence newspaper-style summary from the structured data."""
    away  = game['away_city']
    home  = game['home_city']
    ar    = game['away_runs']
    hr    = game['home_runs']
    dec   = game['decisions']
    w     = dec.get('W', '')
    l     = dec.get('L', '')
    sv    = dec.get('SV', '')

    winner_city = away if game['winner'] == 'away' else home
    loser_city  = home if game['winner'] == 'away' else away
    w_runs      = ar if game['winner'] == 'away' else hr
    l_runs      = hr if game['winner'] == 'away' else ar

    # W pitcher line
    wp_line = ''
    if w:
        # Find winning pitcher's line from pitching data
        pit_list = game['away_pitching'] if game['winner'] == 'away' else game['home_pitching']
        for p in pit_list:
            if p['name'].split('.')[-1].lower() in w.split()[-1].lower() or \
               p['name'].lower() in w.lower():
                wp_line = f"{w} went {p['ip']} innings, allowing {p['er']} earned with {p['k']} strikeouts."
                break
        if not wp_line and w:
            wp_line = f"{w} picked up the win."

    sv_line = f" {sv} earned the save." if sv else ''

    hr_notes = game['away_hr_notes'] if game['winner'] == 'away' else game['home_hr_notes']
    opp_hr   = game['home_hr_notes'] if game['winner'] == 'away' else game['away_hr_notes']

    hr_line = ''
    if hr_notes:
        hr_line = f" {hr_notes} went deep for {winner_city}."
    elif opp_hr:
        hr_line = f" {opp_hr} homered for {loser_city} in a losing effort."

    summary = (
        f"{winner_city} defeated {loser_city} {w_runs}–{l_runs}. "
        f"{wp_line}{sv_line}{hr_line}"
    )
    return summary.strip()


# ── Build headline from game data ─────────────────────────────────────────────
def build_headline(game):
    away  = game['away_city']
    home  = game['home_city']
    ar    = game['away_runs']
    hr    = game['home_runs']
    dec   = game['decisions']
    w     = dec.get('W', '').split()[-1] if dec.get('W') else ''
    l     = dec.get('L', '').split()[-1] if dec.get('L') else ''
    diff  = abs(ar - hr)

    winner_city = away if game['winner'] == 'away' else home
    loser_city  = home if game['winner'] == 'away' else away

    if diff >= 6:
        return f"{winner_city} Rout {loser_city}, {max(ar,hr)}–{min(ar,hr)}"
    elif diff == 1:
        return f"{winner_city} Edge {loser_city} in One-Run Thriller"
    elif w:
        return f"{w} Leads {winner_city} Past {loser_city}"
    else:
        return f"{winner_city} Top {loser_city}, {max(ar,hr)}–{min(ar,hr)}"


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if args:
        date_str = args[0]
    else:
        yesterday = datetime.today() - timedelta(days=1)
        date_str  = yesterday.strftime('%Y-%m-%d')

    md_file = DAILY / f"{date_str}-mlb-box-scores.md"
    if not md_file.exists():
        print(f"  ✗ No file found: {md_file}", flush=True)
        sys.exit(1)

    print(f"  Parsing {md_file.name}...", flush=True)
    text = md_file.read_text(encoding='utf-8')

    # Split on game headers
    raw_blocks = re.split(r'\n(?=### )', text)
    raw_blocks = [b for b in raw_blocks if b.strip().startswith('###')]

    games = []
    for block in raw_blocks:
        g = parse_game(block)
        if g:
            g['headline'] = build_headline(g)
            g['summary']  = build_summary(g)
            games.append(g)

    print(f"  ✓ {len(games)} games parsed", flush=True)

    # Format display date
    dt           = datetime.strptime(date_str, '%Y-%m-%d')
    display_date = dt.strftime('%A, %B %-d, %Y')

    output = {
        'updated':      datetime.now().strftime('%Y-%m-%d %H:%M'),
        'date':         date_str,
        'display_date': display_date,
        'game_count':   len(games),
        'games':        games,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"  ✓ Written → {OUT_FILE}", flush=True)
    print(f"\n✓  Done. {datetime.now()}", flush=True)


if __name__ == '__main__':
    main()
