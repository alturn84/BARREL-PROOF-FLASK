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

VAULT    = Path(__file__).resolve().parent
DAILY    = Path("/opt/data/workspace/barrel-proof/Daily")
OUT_FILE = Path("Site Data") / "game_cards.json"

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
    game['winner']    = 'away' if away_runs > home_runs else 'home'

    venue_m = re.search(r'\*\*Venue:\*\* ([^·]+)', block)
    game['venue'] = venue_m.group(1).strip() if venue_m else ''

    dur_m = re.search(r'\*\*Duration:\*\* ([^\s·]+)', block)
    game['duration'] = dur_m.group(1).strip() if dur_m else ''

    att_m = re.search(r'\*\*Attendance:\*\* ([\d,]+)', block)
    game['attendance'] = att_m.group(1).strip() if att_m else ''

    dec_m     = re.search(r'\*\*Decisions:\*\* (.+)', block)
    decisions = {'W': '', 'L': '', 'SV': ''}
    if dec_m:
        dec_str = dec_m.group(1)
        for key in ('W', 'L', 'SV'):
            km = re.search(rf'{key}: ([^·\n]+?)(?:\s*·|\s*$)', dec_str)
            if km:
                decisions[key] = km.group(1).strip()
    game['decisions'] = decisions

    # Infer game status for postponed/cancelled games (0-0 scores, no duration/attendance/decisions)
    if away_runs == 0 and home_runs == 0:
        is_postponed = (not dur_m or not dur_m.group(1)) and \
                       (not att_m or not att_m.group(1)) and \
                       (not dec_m or not dec_m.group(1))
        if is_postponed:
            game['game_status'] = "POSTPONED"
            game['is_final'] = False
            game['winner'] = '' # No winner for postponed games
        else:
            game['game_status'] = "Final"
            game['is_final'] = True
    else:
        game['game_status'] = "Final" # Explicitly mark as final for played games
        game['is_final'] = True
    game['winner']    = 'away' if away_runs > home_runs else 'home' if game['is_final'] else '' # Only set winner if game is final and not postponed
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

        def parse_data_row(row):
            # Preserve empty cells so column indices match the header
            cells = [c.strip().strip('*') for c in row.split('|')]
            # Drop only the first/last artifact from splitting on outer pipes
            if cells and cells[0] == '':
                cells = cells[1:]
            if cells and cells[-1] == '':
                cells = cells[:-1]
            return cells

        hdr   = parse_row(ls_m.group(1))
        arow  = parse_data_row(ls_m.group(2))
        hrow  = parse_data_row(ls_m.group(3))
        try:
            r_idx = next(i for i, h in enumerate(hdr) if h.strip().upper() == 'R')
        except StopIteration:
            r_idx = len(hdr) - 3
        innings   = hdr[:r_idx]
        away_line = [c if c != '' else '0' for c in arow[:r_idx]]
        home_line = [c if c != '' else '0' for c in hrow[:r_idx]]
        away_rhe  = [v for v in arow[r_idx:r_idx + 3] if v != '']
        home_rhe  = [v for v in hrow[r_idx:r_idx + 3] if v != '']

    game['innings']   = innings
    game['away_line'] = away_line
    game['home_line'] = home_line
    game['away_rhe']  = away_rhe
    game['home_rhe']  = home_rhe

    # Clamp runs to non-negative integers; re-derive from rhe if header parse failed
    try:
        parsed_away = int(away_rhe[0]) if away_rhe else 0
        parsed_home = int(home_rhe[0]) if home_rhe else 0
        game['away_runs'] = max(0, parsed_away)
        game['home_runs'] = max(0, parsed_home)
    except (ValueError, IndexError):
        # Keep values from header parse as fallback
        game['away_runs'] = max(0, game.get('away_runs', 0))
        game['home_runs'] = max(0, game.get('home_runs', 0))

    # Re-derive winner after run correction
    if game['away_runs'] > game['home_runs']:
        game['winner'] = 'away'
    elif game['home_runs'] > game['away_runs']:
        game['winner'] = 'home'
    # If tied (0-0 or genuine tie mid-parse), leave winner as previously set

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


# ── Build editorial game notes ────────────────────────────────────────────────
def build_game_notes(game, standings_data=None):
    """
    Builds 2-4 concise editorial notes per game from box score data.
    No LLM calls. Fully deterministic.
    """
    away = game.get("away_abbr", "")
    home = game.get("home_abbr", "")
    away_city = game.get("away_city", away)
    home_city = game.get("home_city", home)
    away_runs = int(game.get("away_runs") or 0)
    home_runs = int(game.get("home_runs") or 0)
    winner_abbr = away if game.get("winner") == "away" else home
    winner_city = away_city if game.get("winner") == "away" else home_city
    loser_city  = home_city if game.get("winner") == "away" else away_city
    innings_list = game.get("innings", [])
    total_inn = len(innings_list)
    decisions = game.get("decisions", {})
    sv = decisions.get("SV", "")
    game_status = game.get("game_status", "Final")

    if game_status == "POSTPONED":
        return {
            "key_moment": "Game postponed.",
            "standout": "",
            "why_it_mattered": "",
            "notable_stat": "",
        }

    # ── KEY MOMENT ────────────────────────────────────────────────────
    key_moment = ""
    winner_line = game.get("away_line", []) if game.get("winner") == "away" else game.get("home_line", [])
    try:
        max_runs = max((int(r) for r in winner_line if str(r).isdigit()), default=0)
        max_inn  = next(
            (i + 1 for i, r in enumerate(winner_line)
             if str(r).isdigit() and int(r) == max_runs),
            None,
        )
        ordinals = {
            1:"1st",2:"2nd",3:"3rd",4:"4th",5:"5th",
            6:"6th",7:"7th",8:"8th",9:"9th",10:"10th",
            11:"11th",12:"12th",13:"13th",14:"14th",
        }
        if max_runs >= 3 and max_inn:
            inn_label = ordinals.get(max_inn, f"{max_inn}th")
            key_moment = f"{winner_city} scored {max_runs} runs in the {inn_label} inning."
        elif total_inn > 9:
            key_moment = f"Neither team could separate in nine innings, requiring {total_inn} frames to decide it."
        elif min(away_runs, home_runs) == 0:
            key_moment = f"{winner_city} held {loser_city} scoreless, winning {max(away_runs, home_runs)}-0."
        elif abs(away_runs - home_runs) == 1:
            key_moment = f"{winner_city} edged {loser_city} by a single run, {max(away_runs, home_runs)}-{min(away_runs, home_runs)}."
        else:
            key_moment = f"{winner_city} defeated {loser_city}, {max(away_runs, home_runs)}-{min(away_runs, home_runs)}."
        if sv and key_moment:
            key_moment = key_moment.rstrip(".") + f", with {sv} closing it out."
    except Exception:
        key_moment = f"{winner_city} defeated {loser_city}."

    # ── STANDOUT PERFORMER ────────────────────────────────────────────
    standout = ""
    all_batters = (
        [(b, away_city) for b in game.get("away_batting", [])] +
        [(b, home_city) for b in game.get("home_batting", [])]
    )
    best_batter = None
    best_score  = 0
    for b, team in all_batters:
        score = int(b.get("hr", 0)) * 4 + int(b.get("rbi", 0)) * 2 + int(b.get("h", 0))
        if score > best_score:
            best_score  = score
            best_batter = (b, team)
    if best_batter and best_score >= 4:
        b, team = best_batter
        parts = []
        if int(b.get("hr", 0)) >= 1:
            hr_val = int(b["hr"])
            parts.append(f"homered{' twice' if hr_val == 2 else ' three times' if hr_val >= 3 else ''}")
        if int(b.get("rbi", 0)) >= 2:
            parts.append(f"drove in {b['rbi']} runs")
        if int(b.get("h", 0)) >= 3 and not parts:
            parts.append(f"went {b['h']}-for-{b['ab']}")
        if parts:
            standout = f"{b['name']} ({team}) {' and '.join(parts)}."

    if not standout:
        # Fall back to pitching gem
        all_pitchers = (
            [(p, away_city) for p in game.get("away_pitching", [])] +
            [(p, home_city) for p in game.get("home_pitching", [])]
        )
        for p, team in all_pitchers:
            try:
                ip = float(str(p.get("ip","0")).replace(".1",".33").replace(".2",".67"))
                er = int(p.get("er", 99) or 99)
                k  = int(p.get("k", 0) or 0)
                if ip >= 6.0 and er <= 2:
                    k_str = f" with {k} strikeouts" if k >= 5 else ""
                    standout = f"{p['name']} ({team}) threw {p['ip']} innings, allowing {er} earned runs{k_str}."
                    break
            except (ValueError, TypeError):
                pass

    # ── WHY IT MATTERED ───────────────────────────────────────────────
    why_it_mattered = ""
    if standings_data:
        try:
            leagues = standings_data.get("leagues", [])
            winner_record = loser_record = None
            winner_div = loser_div = ""
            for league in leagues:
                for div in league.get("divisions", []):
                    for team in div.get("teams", []):
                        city = team.get("city", "")
                        if city == winner_city:
                            winner_record = f"{team.get('w','—')}-{team.get('l','—')}"
                            winner_div = div.get("name", "")
                        elif city == loser_city:
                            loser_record = f"{team.get('w','—')}-{team.get('l','—')}"
                            loser_div = div.get("name", "")
            if winner_record and winner_div:
                why_it_mattered = (
                    f"{winner_city} improved to {winner_record} in the {winner_div}."
                )
        except Exception:
            pass
    if not why_it_mattered:
        why_it_mattered = f"{winner_city} takes the series game."

    # ── NOTABLE STAT (optional) ───────────────────────────────────────
    notable_stat = ""
    try:
        total_hits = (
            sum(int(b.get("h", 0)) for b in game.get("away_batting", [])) +
            sum(int(b.get("h", 0)) for b in game.get("home_batting", []))
        )
        total_hr_game = sum(
            int(b.get("hr", 0))
            for side in ("away_batting", "home_batting")
            for b in game.get(side, [])
        )
        if total_inn >= 12:
            notable_stat = (
                f"The teams needed {total_inn} innings and combined for "
                f"{total_hits} hits and {total_hr_game} home runs."
            )
        elif total_hits >= 24:
            notable_stat = f"The teams combined for {total_hits} hits."
        elif total_hr_game >= 5:
            notable_stat = f"The teams combined for {total_hr_game} home runs."
    except Exception:
        pass

    return {
        "key_moment":      key_moment,
        "standout":        standout,
        "why_it_mattered": why_it_mattered,
        "notable_stat":    notable_stat,
    }


# ── Build headline ────────────────────────────────────────────────────────────
def build_headline(game):
    ar  = game.get('away_runs', 0)
    hr  = game.get('home_runs', 0)
    dec = game['decisions']
    w   = dec.get('W', '').split()[-1] if dec.get('W') else ''

    winner_city = game['away_city'] if game['winner'] == 'away' else game['home_city']
    loser_city  = game['home_city'] if game['winner'] == 'away' else game['away_city']
    w_runs      = max(ar, hr)
    l_runs      = min(ar, hr)
    diff        = abs(ar - hr)
    total_inn   = len(game['innings'])
    game_status = game.get('game_status', 'Final')

    if game_status == "POSTPONED":
        return "POSTPONED"
    elif total_inn > 9:
        return f"{winner_city} {w_runs}, {loser_city} {l_runs} (F/{total_inn})"
    elif l_runs == 0:
        return f"{winner_city} Blank {loser_city}, {w_runs}-0"
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

    standings_data = {}
    standings_path = Path("Site Data") / "standings.json"
    if standings_path.exists():
        try:
            standings_data = json.loads(
                standings_path.read_text(encoding="utf-8")
            )
        except Exception:
            pass

    games = []
    for block in raw_blocks:
        g = parse_game(block)
        if g:
            g['headline'] = build_headline(g)
            g['notes']    = build_game_notes(g, standings_data)
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

    # ── Write scoreboard.json ─────────────────────────────────────────
    total_hr = sum(
        int(b.get("hr", 0))
        for g in games
        for side in ("away_batting", "home_batting")
        for b in g.get(side, [])
    )
    extra_inn = sum(1 for g in games if len(g.get("innings", [])) > 9)
    shutouts  = sum(
        1 for g in games
        if int(g.get("away_runs") or 0) == 0 or int(g.get("home_runs") or 0) == 0
    )
    try:
        dt_sb = datetime.strptime(date_str, "%Y-%m-%d")
        sb_date = dt_sb.strftime("%B %-d, %Y").upper() + " EDITION"
    except Exception:
        sb_date = date_str.upper() + " EDITION"

    scoreboard_data = {
        "date":       date_str,
        "games":      len(games),
        "home_runs":  total_hr,
        "extras":     extra_inn,
        "shutouts":   shutouts,
        "edition":    sb_date,
        "updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    sb_file = Path("Site Data") / "scoreboard.json"
    sb_file.write_text(
        json.dumps(scoreboard_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"  ✓ scoreboard.json written → {sb_file}", flush=True)

    print(f"\n✓  Done. {datetime.now()}", flush=True)


if __name__ == '__main__':
    main()
