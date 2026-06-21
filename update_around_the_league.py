#!/usr/bin/env python3
"""
update_around_the_league.py — Barrel Proof Baseball
─────────────────────────────────────────────────────
Reads the daily MLB box score markdown (written by mlb_fetch.py),
extracts 5–10 newspaper-style bullet items, and writes:

    Site Data/around_the_league.json

Pipeline position:
    mlb_fetch.py  →  update_around_the_league.py  →  around_the_league.json  →  home.html

Cron (after update_game_of_day.py):
    25 9 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
        "/Users/allanturner/BARREL PROOF/update_around_the_league.py"

Usage:
    python3 update_around_the_league.py              # yesterday
    python3 update_around_the_league.py 2026-05-30  # specific date
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from edition_date_lib import read_edition_date

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

VAULT    = Path(__file__).resolve().parent
DAILY    = VAULT / "Daily"
OUT_FILE = VAULT / "Site Data" / "around_the_league.json"

MIN_ITEMS = 5
MAX_ITEMS = 10

# ── Team display names ────────────────────────────────────────────────────────
TEAM_NAMES = {
    "ARI": "Arizona", "ATL": "Atlanta", "BAL": "Baltimore",
    "BOS": "Boston",  "CHC": "Chicago Cubs", "CWS": "Chicago White Sox",
    "CIN": "Cincinnati", "CLE": "Cleveland", "COL": "Colorado",
    "DET": "Detroit", "HOU": "Houston", "KC": "Kansas City",
    "LAA": "the Angels", "LAD": "the Dodgers", "MIA": "Miami",
    "MIL": "Milwaukee", "MIN": "Minnesota", "NYM": "the Mets",
    "NYY": "the Yankees", "ATH": "the Athletics", "PHI": "Philadelphia",
    "PIT": "Pittsburgh", "SD": "San Diego", "SF": "San Francisco",
    "SEA": "Seattle", "STL": "St. Louis", "TB": "Tampa Bay",
    "TEX": "Texas", "TOR": "Toronto", "WSH": "Washington", "AZ": "Arizona",
}

def tn(abbr):
    name = TEAM_NAMES.get(abbr, abbr)
    return name[0].upper() + name[1:] if name else abbr

def short_name(full_name):
    """
    'Aaron Judge' → 'A. Judge'
    'Luis García Jr.' → 'L. García Jr.'
    Suffixes (Jr., Sr., II, III, IV) are preserved and never collapsed
    onto the initial — e.g. never produces 'L.Jr.'.
    """
    SUFFIXES = {"Jr.", "Sr.", "II", "III", "IV", "V"}
    parts = full_name.strip().split()
    if len(parts) < 2:
        return full_name
    # Strip any trailing suffix before taking last name
    suffix = ""
    if parts[-1] in SUFFIXES:
        suffix = " " + parts[-1]
        parts = parts[:-1]
    if len(parts) < 2:
        # Only one meaningful name part after stripping suffix
        return full_name
    return f"{parts[0][0]}. {parts[-1]}{suffix}"


# ── Markdown parser ───────────────────────────────────────────────────────────
def parse_games(text):
    text = re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL)
    games = []
    for block in re.split(r"\n(?=### )", text):
        block = block.strip()
        if not block.startswith("###"):
            continue
        g = parse_block(block)
        if g:
            games.append(g)
    return games


def parse_block(block):
    hm = re.match(r"### (\w+) @ (\w+)[^—\-]*[—\-]\s*(.*)", block.split("\n")[0])
    if not hm:
        return None
    away, home = hm.group(1), hm.group(2)
    sm = re.findall(r"\*?(\d+)\*?", hm.group(3))
    try:
        away_r, home_r = int(sm[0]), int(sm[1])
    except (IndexError, ValueError):
        return None

    # Innings count
    inn_m = re.search(r"\| Team \|(.+?)\| R \|", block)
    innings = 9
    if inn_m:
        cols = [c.strip() for c in inn_m.group(1).split("|") if c.strip().isdigit()]
        innings = max(len(cols), 9)

    # Decisions
    dec_m = re.search(r"\*\*Decisions:\*\*\s*(.+)", block)
    decisions = {"W": "", "L": "", "SV": ""}
    if dec_m:
        ds = dec_m.group(1)
        for key in ("W", "L", "SV"):
            km = re.search(rf"{key}:\s*([^·\n]+?)(?:\s*·|\s*$)", ds)
            if km:
                decisions[key] = km.group(1).strip()

    # Team stats from notes lines
    notes_raw = [l.strip() for l in block.split("\n")
                 if re.match(r"^\*\*(HR|2B|3B|SB|CS|LOB|WP):", l.strip())]

    # Parse batter rows for both teams
    away_batters = parse_batters(block, away)
    home_batters = parse_batters(block, home)
    away_pitchers = parse_pitchers(block, away)
    home_pitchers = parse_pitchers(block, home)

    # Team hit/run totals from linescore
    away_hits = _rhe_val(block, away, 1)
    home_hits = _rhe_val(block, home, 1)

    return {
        "away": away, "home": home,
        "away_r": away_r, "home_r": home_r,
        "innings": innings,
        "decisions": decisions,
        "away_batters": away_batters,
        "home_batters": home_batters,
        "away_pitchers": away_pitchers,
        "home_pitchers": home_pitchers,
        "away_hits": away_hits,
        "home_hits": home_hits,
        "notes_raw": notes_raw,
        "winner": away if away_r > home_r else home,
        "loser":  home if away_r > home_r else away,
        "winner_r": max(away_r, home_r),
        "loser_r":  min(away_r, home_r),
    }


def _rhe_val(block, abbr, idx):
    """Extract R/H/E column value for a team from linescore."""
    pattern = rf"\|\s*\*?\*?{re.escape(abbr)}\*?\*?\s*\|[^|]+\|\s*\*?(\d+)\*?\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
    m = re.search(pattern, block)
    if m:
        try:
            return int(m.group(idx + 1))
        except (IndexError, ValueError):
            pass
    return 0


def parse_batters(block, abbr):
    pattern = rf"\*\*{re.escape(abbr)} Batting\*\*\n\n\|[^\n]+\|\n\|[-|]+\|\n((?:\|[^\n]+\|\n?)+)"
    m = re.search(pattern, block)
    if not m:
        return []
    rows = []
    for line in m.group(1).strip().split("\n"):
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 10:
            continue
        # cols: Batter | PA | AB | R | H | 2B | 3B | HR | RBI | BB | SO | ...
        name_pos = cells[0]
        nm = re.match(r"(.+?)\s*\(([^)]+)\)", name_pos)
        name = nm.group(1).strip() if nm else name_pos
        try:
            pa  = int(cells[1])
            ab  = int(cells[2])
            r   = int(cells[3])
            h   = int(cells[4])
            d   = int(cells[5])
            t   = int(cells[6])
            hr  = int(cells[7])
            rbi = int(cells[8])
            bb  = int(cells[9])
            so  = int(cells[10]) if len(cells) > 10 else 0
        except (ValueError, IndexError):
            continue
        if pa == 0:
            continue
        rows.append({
            "name": name, "ab": ab, "r": r, "h": h,
            "2b": d, "3b": t, "hr": hr, "rbi": rbi,
            "bb": bb, "so": so,
        })
    return rows


def parse_pitchers(block, abbr):
    pattern = rf"\*\*{re.escape(abbr)} Pitching\*\*\n\n\|[^\n]+\|\n\|[-|]+\|\n((?:\|[^\n]+\|\n?)+)"
    m = re.search(pattern, block)
    if not m:
        return []
    rows = []
    for line in m.group(1).strip().split("\n"):
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 7:
            continue
        name = cells[0]
        ip_raw = cells[1]
        try:
            ip = float(ip_raw.replace(".1", ".33").replace(".2", ".67"))
            h   = int(cells[2])
            r   = int(cells[3])
            er  = int(cells[4])
            bb  = int(cells[5])
            k   = int(cells[6])
            hr  = int(cells[7]) if len(cells) > 7 else 0
        except (ValueError, IndexError):
            continue
        rows.append({
            "name": name, "ip": ip, "ip_raw": ip_raw,
            "h": h, "r": r, "er": er, "bb": bb, "k": k, "hr": hr,
        })
    return rows


# ── Item generators ───────────────────────────────────────────────────────────
# Each returns a list of (score, text) tuples. Higher score = higher priority.

def items_multi_hr(games):
    out = []
    for g in games:
        for side, batters in (("away", g["away_batters"]), ("home", g["home_batters"])):
            team = g["away"] if side == "away" else g["home"]
            for b in batters:
                if b["hr"] >= 2:
                    rbi_str = f", driving in {b['rbi']}" if b["rbi"] >= 3 else ""
                    score = 90 + b["hr"] * 5
                    if team == g["winner"]:
                        result = (f"as {tn(team)} beat {tn(g['loser'])}, "
                                  f"{g['winner_r']}-{g['loser_r']}")
                    else:
                        result = (f"in {tn(g['winner'])}'s "
                                  f"{g['winner_r']}-{g['loser_r']} win over {tn(g['loser'])}")
                    out.append((score,
                        f"{b['name']} homered {b['hr']} times{rbi_str} {result}."))
    return out


def items_dominant_pitching(games):
    out = []
    for g in games:
        for side, pitchers in (("away", g["away_pitchers"]), ("home", g["home_pitchers"])):
            team = g["away"] if side == "away" else g["home"]
            opp  = g["home"] if side == "away" else g["away"]
            for i, p in enumerate(pitchers):
                if i > 0:
                    break
                if p["ip"] >= 7.0 and p["er"] <= 1 and p["k"] >= 8:
                    score = 85 + p["k"] + (10 if p["er"] == 0 else 0)
                    verb  = "blanked" if p["er"] == 0 else "held down"
                    out.append((score,
                        f"{p['name']} {verb} {tn(opp)} for {p['ip_raw']} innings, "
                        f"striking out {p['k']} in {tn(team)}'s "
                        f"{g['winner_r']}-{g['loser_r']} win."))
    return out


def items_shutouts(games):
    out = []
    for g in games:
        if g["loser_r"] == 0:
            pitchers = g["away_pitchers"] if g["winner"] == g["away"] else g["home_pitchers"]
            allow_team = g["loser"]
            if len(pitchers) == 1:
                p = pitchers[0]
                out.append((80,
                    f"{p['name']} threw a complete-game shutout, "
                    f"blanking {tn(allow_team)}, {g['winner_r']}-0."))
            else:
                out.append((70,
                    f"{tn(g['winner'])} pitching combined to shut out "
                    f"{tn(allow_team)}, {g['winner_r']}-0."))
    return out


def items_k_performances(games):
    out = []
    for g in games:
        for side, pitchers in (("away", g["away_pitchers"]), ("home", g["home_pitchers"])):
            team = g["away"] if side == "away" else g["home"]
            opp  = g["home"] if side == "away" else g["away"]
            for i, p in enumerate(pitchers):
                if i > 0:
                    break
                if p["k"] >= 12:
                    score = 75 + p["k"]
                    out.append((score,
                        f"{p['name']} struck out {p['k']} in {p['ip_raw']} innings "
                        f"as {tn(team)} topped {tn(opp)}, "
                        f"{g['winner_r']}-{g['loser_r']}."))
    return out


def items_rbi_games(games):
    out = []
    for g in games:
        for side, batters in (("away", g["away_batters"]), ("home", g["home_batters"])):
            team = g["away"] if side == "away" else g["home"]
            for b in batters:
                if b["rbi"] >= 5:
                    hr_str = f", with {b['hr']} home run{'s' if b['hr'] > 1 else ''}" if b["hr"] else ""
                    score  = 70 + b["rbi"]
                    if team == g["winner"]:
                        result = (f"as {tn(team)} beat {tn(g['loser'])}, "
                                  f"{g['winner_r']}-{g['loser_r']}")
                    else:
                        result = (f"in {tn(g['winner'])}'s "
                                  f"{g['winner_r']}-{g['loser_r']} win over {tn(g['loser'])}")
                    out.append((score,
                        f"{b['name']} had {b['rbi']} RBI{hr_str} {result}."))
    return out


def items_stolen_bases(games):
    out = []
    for g in games:
        for note in g["notes_raw"]:
            if note.startswith("**SB:**"):
                sb_str = note.replace("**SB:**", "").strip()
                counts = re.findall(r"\((\d+)\)", sb_str)
                total  = sum(int(c) for c in counts)
                names  = re.findall(r"([A-Z][a-zA-Z\.\s]+?)\s*\(\d+\)", sb_str)
                if total >= 3:
                    name_str = ", ".join(names[:2]) if names else "Multiple runners"
                    out.append((55 + total,
                        f"{name_str} combined for {total} stolen bases."))
                elif total == 2 and len(counts) == 1 and names:
                    out.append((50,
                        f"{names[0].strip()} stole {total} bases."))
    return out


def items_extra_innings(games):
    out = []
    for g in games:
        if g["innings"] > 9:
            # Walk-off items take priority over extra-innings for the same game
            is_walk_off = g["home_r"] > g["away_r"] and (g["home_r"] - g["away_r"]) == 1
            if is_walk_off:
                continue
            score = 60 + (g["innings"] - 9) * 3
            out.append((score,
                f"{tn(g['winner'])} edged {tn(g['loser'])}, "
                f"{g['winner_r']}-{g['loser_r']}, in {g['innings']} innings."))
    return out


def items_cycles(games):
    out = []
    for g in games:
        for side, batters in (("away", g["away_batters"]), ("home", g["home_batters"])):
            team = g["away"] if side == "away" else g["home"]
            for b in batters:
                singles = b["h"] - b["2b"] - b["3b"] - b["hr"]
                if singles >= 1 and b["2b"] >= 1 and b["3b"] >= 1 and b["hr"] >= 1:
                    result = "win" if team == g["winner"] else "loss"
                    out.append((95,
                        f"{b['name']} hit for the cycle in {tn(team)}'s "
                        f"{g['winner_r']}-{g['loser_r']} {result}."))
    return out


def items_blowouts(games):
    out = []
    for g in games:
        margin = g["winner_r"] - g["loser_r"]
        if margin >= 8:
            out.append((30 + margin,
                f"{tn(g['winner'])} routed {tn(g['loser'])}, "
                f"{g['winner_r']}-{g['loser_r']}."))
    return out


def items_no_hitter(games):
    out = []
    for g in games:
        if g["home_hits"] == 0 and g["innings"] >= 9:
            pitchers = g["away_pitchers"]
            if len(pitchers) == 1:
                p = pitchers[0]
                out.append((130,
                    f"{p['name']} no-hit {tn(g['home'])} through nine, "
                    f"{g['away_r']}-0."))
        elif g["away_hits"] == 0 and g["innings"] >= 9:
            pitchers = g["home_pitchers"]
            if len(pitchers) == 1:
                p = pitchers[0]
                out.append((130,
                    f"{p['name']} no-hit {tn(g['away'])} through nine, "
                    f"{g['home_r']}-0."))
    return out


def items_walk_offs(games):
    """Home team wins by 1 run — one item max, mentioning others if multiple."""
    walk_offs = []
    for g in games:
        if g["home_r"] > g["away_r"] and (g["home_r"] - g["away_r"]) == 1:
            walk_offs.append(g)

    if not walk_offs:
        return []

    out = []
    g = walk_offs[0]  # lead with the best (already sorted by score upstream)
    score = 65 if g["innings"] > 9 else 55

    if len(walk_offs) == 1:
        out.append((score,
            f"{tn(g['home'])} walked off {tn(g['away'])}, "
            f"{g['home_r']}-{g['away_r']}."))
    else:
        others = len(walk_offs) - 1
        out.append((score,
            f"{tn(g['home'])} walked off {tn(g['away'])}, {g['home_r']}-{g['away_r']} "
            f"— one of {len(walk_offs)} one-run finishes across the league."))
    return out


# ── Dedup: suppress lower-priority items about the same game ─────────────────
def dedup(items, games):
    """
    If multiple items reference the same game matchup, keep the highest-scoring one
    unless the secondary item adds genuinely different news (different player).
    Simple heuristic: track (away, home) pairs and allow max 2 items per game.
    """
    seen = {}
    result = []
    for score, text in items:
        key = None
        for g in games:
            if tn(g["away"]) in text or g["away"] in text:
                key = (g["away"], g["home"])
                break
            if tn(g["home"]) in text or g["home"] in text:
                key = (g["away"], g["home"])
                break
        count = seen.get(key, 0)
        if key is None or count < 2:
            result.append((score, text))
            seen[key] = count + 1
    return result


# ── Main ──────────────────────────────────────────────────────────────────────
def run(date_str):
    try:
        edition_date = read_edition_date()
    except Exception as e:
        print(f"  ✗ {e}")
        sys.exit(1)

    md_file = DAILY / f"{date_str}-mlb-box-scores.md"
    if not md_file.exists():
        print(f"  No file found: {md_file}")
        return

    print(f"  Parsing {md_file.name}...")
    text  = md_file.read_text(encoding="utf-8")
    games = parse_games(text)
    print(f"  {len(games)} games parsed")

    # Collect all candidate items
    candidates = []
    candidates += items_no_hitter(games)
    candidates += items_cycles(games)
    candidates += items_dominant_pitching(games)
    candidates += items_multi_hr(games)
    candidates += items_rbi_games(games)
    candidates += items_k_performances(games)
    candidates += items_shutouts(games)
    candidates += items_extra_innings(games)
    candidates += items_walk_offs(games)
    candidates += items_stolen_bases(games)
    candidates += items_blowouts(games)

    # Sort by score descending, dedup, trim
    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = dedup(candidates, games)
    selected   = candidates[:MAX_ITEMS]

    # Pad with blowouts if under minimum
    if len(selected) < MIN_ITEMS:
        extras = [c for c in candidates if c not in selected]
        selected += extras[:MIN_ITEMS - len(selected)]

    items = [text for _, text in selected]

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    output = {
        "date":         edition_date,
        "game_date":    date_str,
        "date_display": dt.strftime("%A, %B %-d, %Y"),
        "updated":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "item_count":   len(items),
        "items":        items,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓  {len(items)} items written → {OUT_FILE}")
    print()
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    date_str = args[0] if args else (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    run(date_str)
