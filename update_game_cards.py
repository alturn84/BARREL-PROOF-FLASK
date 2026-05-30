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
    lines = block.strip().split('\n')
    game  = {}

    # Header: ### SD @ WSH — **SD 7**, WSH 5
    header = lines[0] if lines else ''
    m = re.match(r'### (\w+) @ (\w+) — (.+)', header)
    if not m:
        return None
    away_abbr = m.group(1)
    home_abbr = m.group(2)
    score_str = m.group(3)

    score_m   = re.findall(r'\*\*(\w+)\s+(\d+)\*\*|(\w+)\s+(\d+)', score_str)
    away_runs = home_runs = 0
    for sm in score_m:
        if sm[0]:
            r = int(sm[1])
            if sm[0] == away_abbr: away_runs = r
            else: home_runs = r
        else:
            r = int(sm[3])
            if sm[2] == away_abbr: away_runs = r
            elif sm[2] == home_abbr: home_runs = r

    game['away_abbr'] = away_abbr
    game['home_abbr'] = home_abbr
    game['away_city'] = TEAM_CITIES.get(away_abbr, away_abbr)
    game['home_city'] = TEAM_CITIES.get(home_abbr, home_abbr)
    game['away_runs'] = away_runs
    game['home_runs'] = home_runs
    game['winner']    = 'away' if away_runs > home_runs else 'home'

    venue_m = re.search(r'\*\*Venue:\*\* ([^·]+)', block)
    game['venue'] = venue_m.group(1).strip() if venue_m else ''

    dur_m = re.search(r'\*\*Duration:\*\* ([^\s·]+)', block)
    game['duration'] = dur_m.group(1).strip() if dur_m else ''

    att_m = re.search(r'\*\*Attendance:\*\* ([\d,]+)', block)
    game['attendance'] = att_m.group(1).strip() if att_m else ''

    # Decisions
    dec_m     = re.search(r'\*\*Decisions:\*\* (.+)', block)
    decisions = {'W': '', 'L': '', 'SV': ''}
    if dec_m:
        dec_str = dec_m.group(1)
        for key in ('W', 'L', 'SV'):
            km = re.search(rf'{key}: ([^·\n]+?)(?:\s*·|\s*$)', dec_str)
            if km:
                decisions[key] = km.group(1).strip()
    game['decisions'] = decisions

    # Line score
    ls_m = re.search(
        r'\| Team \|(.+?)\n\|[-|]+\|\n\| \*\*' + re.escape(away_abbr) + r'\*\* \|(.+?)\n\| \*\*' + re.escape(home_abbr) + r'\*\* \|(.+?)(?:\n|$)',
        block
    )
    if not ls_m:
        ls_m = re.search(
            r'\| Team \|(.+?)\n\|[-|]+\|\n\|[^|]*' + re.escape(away_abbr) + r'[^|]* \|(.+?)\n\|[^|]*' + re.escape(home_abbr) + r'[^|]* \|(.+?)(?:\n|$)',
            block
        )

    innings = away_line = home_line = []
    away_rhe = [str(away_runs), '', '']
    home_rhe = [str(home_runs), '', '']

    if ls_m:
        def parse_row(row):
            cells = [c.strip().strip('*') for c in row.split('|')]
            return [c for c in cells if c]

        hdr   = parse_row(ls_m.group(1))
        arow  = parse_row(ls_m.group(2))
        hrow  = parse_row(ls_m.group(3))
        n_inn = len(arow) - 3
        innings   = hdr[:n_inn]
        away_line = arow[:n_inn]
        home_line = hrow[:n_inn]
        away_rhe  = arow[-3:]
        home_rhe  = hrow[-3:]

    game['innings']   = innings
    game['away_line'] = away_line
    game['home_line'] = home_line
    game['away_rhe']  = away_rhe
    game['home_rhe']  = home_rhe

    # Batting tables — capture full rows including 2B/3B/HR for summary use
    def parse_batting(team_abbr):
        pattern = rf'\*\*{re.escape(team_abbr)} Batting\*\*\n\n\|[^\n]+\|\n\|[-|]+\|\n((?:\|[^\n]+\|\n?)+)'
        m = re.search(pattern, block)
        if not m:
            return []
        rows = []
        for row in m.group(1).strip().split('\n'):
            cells = [c.strip() for c in row.split('|')]
            cells = [c for c in cells if c]
            if len(cells) < 9:
                continue
            batter_pos = cells[0]
            bm = re.match(r'(.+?)\s*\((\w+)\)', batter_pos)
            name = bm.group(1).strip() if bm else batter_pos
            pos  = bm.group(2).strip() if bm else ''
            parts = name.split()
            short = f"{parts[0][0]}.{parts[-1]}" if len(parts) > 1 else name
            try:
                ab  = int(cells[2])
                r   = int(cells[3])
                h   = int(cells[4])
                dbl = int(cells[5])
                trp = int(cells[6])
                hr  = int(cells[7])
                rbi = int(cells[8])
            except (ValueError, IndexError):
                continue
            rows.append({
                'name': short, 'pos': pos,
                'ab': ab, 'r': r, 'h': h,
                '2b': dbl, '3b': trp, 'hr': hr, 'rbi': rbi,
            })
        return rows

    game['away_batting'] = parse_batting(away_abbr)
    game['home_batting'] = parse_batting(home_abbr)

    # Pitching tables — capture full lines including BB
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
            name  = cells[0].strip()
            parts = name.split()
            short = f"{parts[0][0]}.{parts[-1]}" if len(parts) > 1 else name
            try:
                ip = cells[1]
                h  = cells[2]
                r  = cells[3]
                er = cells[4] if len(cells) > 4 else ''
                bb = cells[5] if len(cells) > 5 else ''
                k  = cells[6] if len(cells) > 6 else ''
            except IndexError:
                continue
            rows.append({
                'name': short, 'ip': ip,
                'h': h, 'r': r, 'er': er, 'bb': bb, 'k': k,
            })
        return rows

    game['away_pitching'] = parse_pitching(away_abbr)
    game['home_pitching'] = parse_pitching(home_abbr)

    return game


# ── Build fact-driven summary ─────────────────────────────────────────────────
def build_summary(game):
    """
    Strictly factual 3-4 sentence summary.
    Covers: final score + SP line, multi-hit/RBI performers, HR, extras if notable.
    No adjectives, no narrative framing — placeholder until Hermes takes over.
    """
    away = game['away_city']
    home = game['home_city']
    ar   = game['away_runs']
    hr   = game['home_runs']
    dec  = game['decisions']
    w    = dec.get('W', '')
    l    = dec.get('L', '')
    sv   = dec.get('SV', '')

    winner_city = away if game['winner'] == 'away' else home
    loser_city  = home if game['winner'] == 'away' else away
    w_runs      = ar   if game['winner'] == 'away' else hr
    l_runs      = hr   if game['winner'] == 'away' else ar

    sentences = []

    # ── Sentence 1: score + winning pitcher
    win_pit_list = game['away_pitching'] if game['winner'] == 'away' else game['home_pitching']
    wp_stat = ''
    if w:
        w_last = w.split()[-1].lower()
        for p in win_pit_list:
            if w_last in p['name'].lower():
                ks   = f", {p['k']} K" if p['k'] and p['k'] != '0' else ''
                bbs  = f", {p['bb']} BB" if p['bb'] and p['bb'] != '0' else ''
                wp_stat = f" {w}: {p['ip']} IP, {p['er']} ER{ks}{bbs}."
                break
        if not wp_stat:
            wp_stat = f" {w} (W)."

    sv_stat = f" {sv} (SV)." if sv else ''
    sentences.append(f"{winner_city} {w_runs}, {loser_city} {l_runs}.{wp_stat}{sv_stat}")

    # ── Sentence 2: losing pitcher
    los_pit_list = game['home_pitching'] if game['winner'] == 'away' else game['away_pitching']
    if l:
        l_last = l.split()[-1].lower()
        for p in los_pit_list:
            if l_last in p['name'].lower():
                ks  = f", {p['k']} K" if p['k'] and p['k'] != '0' else ''
                bbs = f", {p['bb']} BB" if p['bb'] and p['bb'] != '0' else ''
                sentences.append(f"{l} (L): {p['ip']} IP, {p['er']} ER{ks}{bbs}.")
                break

    # ── Sentence 3: multi-hit performers + HR
    def get_notable_hitters(bat_list):
        multi_h = [p for p in bat_list if p['h'] >= 2]
        hr_list = [p for p in bat_list if p['hr'] >= 1]
        notes   = []
        for p in multi_h:
            xbh = []
            if p['2b']: xbh.append(f"{p['2b']} 2B")
            if p['3b']: xbh.append(f"{p['3b']} 3B")
            if p['hr']: xbh.append(f"{p['hr']} HR")
            xbh_str = f" ({', '.join(xbh)})" if xbh else ''
            rbi_str = f", {p['rbi']} RBI" if p['rbi'] else ''
            notes.append(f"{p['name']} {p['h']}-for-{p['ab']}{xbh_str}{rbi_str}")
        for p in hr_list:
            if p not in multi_h:
                rbi_str = f", {p['rbi']} RBI" if p['rbi'] else ''
                notes.append(f"{p['name']} HR{rbi_str}")
        return notes

    win_bat  = game['away_batting'] if game['winner'] == 'away' else game['home_batting']
    los_bat  = game['home_batting'] if game['winner'] == 'away' else game['away_batting']

    win_notes = get_notable_hitters(win_bat)
    los_notes = get_notable_hitters(los_bat)

    if win_notes:
        sentences.append(f"{winner_city}: {'; '.join(win_notes[:4])}.")
    if los_notes:
        sentences.append(f"{loser_city}: {'; '.join(los_notes[:3])}.")

    # ── Extras: extra innings, shutout, walk-off etc
    extras = []
    total_inn = len(game['innings'])
    if total_inn > 9:
        extras.append(f"Final: {total_inn} innings.")
    if l_runs == 0:
        extras.append("Shutout.")
    if extras:
        sentences.append(' '.join(extras))

    return ' '.join(sentences)


# ── Build headline ────────────────────────────────────────────────────────────
def build_headline(game):
    away = game['away_city']
    home = game['home_city']
    ar   = game['away_runs']
    hr   = game['home_runs']
    dec  = game['decisions']
    w    = dec.get('W', '').split()[-1] if dec.get('W') else ''
    diff = abs(ar - hr)

    winner_city = away if game['winner'] == 'away' else home
    loser_city  = home if game['winner'] == 'away' else away
    w_runs      = max(ar, hr)
    l_runs      = min(ar, hr)

    total_inn = len(game['innings'])

    if total_inn > 9:
        return f"{winner_city} {w_runs}, {loser_city} {l_runs} (F/{total_inn})"
    elif l_runs == 0:
        return f"{winner_city} Shut Out {loser_city}, {w_runs}-0"
    elif diff >= 6:
        return f"{winner_city} {w_runs}, {loser_city} {l_runs}"
    elif w:
        return f"{winner_city} {w_runs}, {loser_city} {l_runs} — {w} (W)"
    else:
        return f"{winner_city} {w_runs}, {loser_city} {l_runs}"


# ── Main ──────────────────────────────────────────────────────────────────────
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
