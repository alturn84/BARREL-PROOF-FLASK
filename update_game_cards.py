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
from google.genai import types

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)


def load_api_key():
    import os
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        env_file = Path(__file__).resolve().parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    return key


def generate_game_summary(game, client):
    """Generate a human-written game summary using Gemini."""
    away = game.get("away_city", game.get("away_abbr", ""))
    home = game.get("home_city", game.get("home_abbr", ""))
    away_runs = game.get("away_runs", 0)
    home_runs = game.get("home_runs", 0)
    winner = away if game.get("winner") == "away" else home
    loser = home if game.get("winner") == "away" else away
    venue = game.get("venue", "")
    innings = len(game.get("innings", [])) or 9
    decisions = game.get("decisions", {})
    wp = decisions.get("W", "")
    lp = decisions.get("L", "")
    sv = decisions.get("SV", "")

    # Build pitcher context
    pitcher_lines = []
    for p in game.get("away_pitching", [])[:2]:
        pitcher_lines.append(f"{p['name']}: {p.get('ip','?')} IP, {p.get('er','?')} ER, {p.get('k','?')} K")
    for p in game.get("home_pitching", [])[:2]:
        pitcher_lines.append(f"{p['name']}: {p.get('ip','?')} IP, {p.get('er','?')} ER, {p.get('k','?')} K")

    # Build top offensive performers
    top_bats = []
    for side in ("away_batting", "home_batting"):
        team = game.get("away_abbr") if side == "away_batting" else game.get("home_abbr")
        for b in game.get(side, []):
            hr = b.get("hr", 0)
            h = b.get("h", 0)
            rbi = b.get("rbi", 0)
            if hr >= 1 or h >= 2 or rbi >= 2:
                top_bats.append(f"{b['name']} ({team}): {h}H {hr}HR {rbi}RBI")

    extra = f" ({innings} innings)" if innings > 9 else ""
    shutout = f" {loser} was held scoreless." if min(away_runs, home_runs) == 0 else ""

    # Detect game type for tone guidance
    margin = abs(away_runs - home_runs)
    is_walkoff = any(kw in str(decisions).lower() for kw in ["walk-off", "walkoff"]) or \
                 (innings == 9 and margin <= 2)
    is_blowout = margin >= 6
    is_extra = innings > 9
    is_shutout = min(away_runs, home_runs) == 0
    is_comeback = False  # detected from flags if available
    total_runs = away_runs + home_runs
    is_slugfest = total_runs >= 14

    if is_extra:
        game_type = "extra innings"
    elif is_blowout:
        game_type = "blowout"
    elif is_shutout:
        game_type = "shutout/pitcher's duel"
    elif is_slugfest:
        game_type = "slugfest"
    elif margin <= 1:
        game_type = "one-run game"
    else:
        game_type = "standard"

    # Build verified name list from batting and pitching data
    all_names = set()
    for side in ("away_batting", "home_batting"):
        for b in game.get(side, []):
            if b.get("name"):
                all_names.add(b["name"])
    for side in ("away_pitching", "home_pitching"):
        for p in game.get(side, []):
            if p.get("name"):
                all_names.add(p["name"])

    context = f"""Game: {away} at {home}{extra}
Final: {away} {away_runs}, {home} {home_runs}
Venue: {venue}
Winning pitcher: {wp}
Losing pitcher: {lp}
{"Save: " + sv if sv else ""}
Pitching lines: {"; ".join(pitcher_lines[:3])}
Key performers: {"; ".join(top_bats[:4]) if top_bats else "none notable"}
{shutout}
VERIFIED PLAYER NAMES — only use names from this list: {", ".join(sorted(all_names))}
DO NOT invent or alter player names."""

    prompt = f"""Write a 1-2 sentence baseball game summary. 35-60 words.
Game type: {game_type}

{context}

RULES:
- Use team nicknames not city names (Yankees not New York, Mets not New York, Dodgers not Los Angeles, Angels not Los Angeles)
- Write in a style that matches the game type:
  * extra innings: emphasize the length and tension, name who ended it
  * blowout: lead with the dominant performance, keep it brief
  * shutout/pitcher's duel: lead with the pitcher, make defense the story
  * slugfest: lead with the run total or a big individual performance
  * one-run game: convey the tightness, name the decisive moment
  * walk-off: name the player who ended it and how
  * standard: explain why the game turned with one key player or play
- Start with the key moment or player, not the winning team name
- Name one player who made the difference with a specific detail
- Mention the final score once
- No markdown, no bold, plain prose only
- CRITICAL: Only use player names from the VERIFIED PLAYER NAMES list. Never invent or alter names.

BANNED PHRASES:
- "proved the difference"
- "the decisive blow"
- "the contest"
- "hopes were dashed"
- "ultimately prevailed"
- "the affair"
- "the game unfolded"
- "allowed X earned runs"
- "strong performance"

GOOD EXAMPLES by game type:
- Walk-off: "Pete Alonso lined a single to right in the ninth to end it, giving the Mets a 4-3 win over Seattle after trailing by two."
- Blowout: "Tarik Skubal struck out nine and Detroit backed him with three home runs in a 9-2 rout of Tampa Bay."
- Shutout: "Sandy Alcantara went eight scoreless innings and the Marlins scratched out two runs to beat Washington, 2-0."
- Slugfest: "The teams combined for 19 runs, but it was Yordan Alvarez's two-homer, five-RBI afternoon that separated Houston from Texas in an 11-8 slugfest."
- One-run: "A Carlos Correa single in the seventh scored the go-ahead run and Minnesota held on for a 3-2 win over Cleveland."
- Extra innings: "Neither team could break through for nine innings, but Jazz Chisholm homered in the tenth to give the Yankees a 5-4 win over Baltimore."
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=2048),
        )
        summary = response.text.strip().replace("**", "").replace("*", "")
        if len(summary.split()) >= 20:
            return summary
    except Exception as e:
        print(f"  ⚠ Summary generation failed for {away}@{home}: {e}", flush=True)
    return None  # caller uses fallback

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


# ── Build AP-wire style summary ───────────────────────────────────────────────
def build_summary(game):
    """
    AP wire style — factual and readable, 3-4 sentences.
    Leads with the starter's outing woven into the result, covers key offensive
    contributors, notes anything that stands out. No adjectives or hyperbole.
    Placeholder until Hermes takes over.
    """
    ar  = game.get('away_runs', 0)
    hr  = game.get('home_runs', 0)
    dec = game['decisions']
    w   = dec.get('W', '')
    l   = dec.get('L', '')
    sv  = dec.get('SV', '')

    winner_city = game['away_city'] if game['winner'] == 'away' else game['home_city']
    loser_city  = game['home_city'] if game['winner'] == 'away' else game['away_city']
    venue       = game.get('venue', '')
    w_runs      = ar if game['winner'] == 'away' else hr
    l_runs      = hr if game['winner'] == 'away' else ar
    total_inn   = len(game['innings'])
    game_status = game.get('game_status', 'Final')

    if game_status == "POSTPONED":
        return "Game Postponed."

    win_pit = game['away_pitching'] if game['winner'] == 'away' else game['home_pitching']
    los_pit = game['home_pitching'] if game['winner'] == 'away' else game['away_pitching']
    win_bat = game['away_batting']  if game['winner'] == 'away' else game['home_batting']
    los_bat = game['home_batting']  if game['winner'] == 'away' else game['away_batting']

    sentences = []

    # ── S1: Lead with the winning starter's outing and the result
    if w:
        wp = next((p for p in win_pit if w.split()[-1].lower() in p['name'].lower()), None)
        if wp:
            er_val    = wp['er'] if wp['er'] else '0'
            k_clause  = f" with {wp['k']} strikeouts" if wp['k'] and wp['k'] != '0' else ''
            venue_str = f" at {venue}" if venue else ''
            sentences.append(
                f"{w} pitched {wp['ip']} innings, allowing {er_val} earned runs{k_clause}, "
                f"leading {winner_city} past {loser_city} {w_runs}-{l_runs}{venue_str}."
            )
        else:
            venue_str = f" at {venue}" if venue else ''
            sentences.append(f"{winner_city} beat {loser_city} {w_runs}-{l_runs}{venue_str}.")
    else:
        sentences.append(f"{winner_city} beat {loser_city} {w_runs}-{l_runs}.")

    # ── S2: Losing starter — how far they went and what did them in
    if l:
        lp = next((p for p in los_pit if l.split()[-1].lower() in p['name'].lower()), None)
        if lp:
            er_val = lp['er'] if lp['er'] else '0'
            k_str  = f", {lp['k']} strikeouts" if lp['k'] and lp['k'] != '0' else ''
            bb_str = f", {lp['bb']} walks" if lp['bb'] and lp['bb'] != '0' else ''
            sentences.append(
                f"{l} lasted {lp['ip']} innings, giving up {er_val} earned runs{k_str}{bb_str}."
            )

    # ── S3: Offensive contributors for the winner — HRs first, then multi-hit
    hr_hitters    = [p for p in win_bat if p['hr'] >= 1]
    multi_hitters = [p for p in win_bat if p['h'] >= 2 and p not in hr_hitters]
    rbi_hitters   = [p for p in win_bat if p['rbi'] >= 2 and p not in hr_hitters]

    off_parts = []
    for p in hr_hitters[:3]:
        rbi_str = f" with {p['rbi']} RBI" if p['rbi'] > 1 else ''
        off_parts.append(f"{p['name']} homered{rbi_str}")
    for p in multi_hitters[:2]:
        if len(off_parts) >= 3:
            break
        xbh = []
        if p['2b']: xbh.append(f"{p['2b']} double{'s' if p['2b'] > 1 else ''}")
        if p['3b']: xbh.append(f"{p['3b']} triple{'s' if p['3b'] > 1 else ''}")
        xbh_str = f", including {', '.join(xbh)}" if xbh else ''
        rbi_str = f" with {p['rbi']} RBI" if p['rbi'] else ''
        off_parts.append(f"{p['name']} went {p['h']}-for-{p['ab']}{xbh_str}{rbi_str}")
    if not off_parts:
        for p in rbi_hitters[:2]:
            off_parts.append(f"{p['name']} drove in {p['rbi']}")

    if off_parts:
        sentences.append(f"Offensively for {winner_city}: {'; '.join(off_parts)}.")

    # ── S4: Notable from the losing side
    los_hr = [p for p in los_bat if p['hr'] >= 1]
    if los_hr:
        names = ', '.join(p['name'] for p in los_hr[:3])
        sentences.append(f"{names} went deep for {loser_city}.")

    # ── Extras: save, extra innings, shutout
    extras = []
    if sv:
        extras.append(f"{sv} closed it out for the save.")
    if total_inn > 9:
        extras.append(f"The teams needed {total_inn} innings to decide it.")
    if l_runs == 0:
        extras.append(f"{loser_city} was held scoreless.")
    if extras:
        sentences.append(' '.join(extras))

    return ' '.join(sentences)


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

    api_key = load_api_key()
    gemini_client = None
    if api_key:
        try:
            import google.genai as genai
            from google.genai import types
            gemini_client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1"))
            print("  Gemini client initialized for summaries", flush=True)
        except Exception as e:
            print(f"  ⚠ Gemini init failed: {e}", flush=True)

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
            if gemini_client:
                ai_summary = generate_game_summary(g, gemini_client)
                if ai_summary:
                    g['summary'] = ai_summary
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
