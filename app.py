#!/usr/bin/env python3
"""
Barrel Proof Baseball — Flask Web Server
"""

import json
import os
from pathlib import Path
from flask import Flask, render_template, abort, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "Site Data")))
VAULT = Path(os.environ.get("VAULT_DIR", str(BASE_DIR)))

CITY_TO_TEAM = {
    "Arizona":       "Arizona Diamondbacks",
    "Atlanta":       "Atlanta Braves",
    "Athletics":     "Athletics",
    "Baltimore":     "Baltimore Orioles",
    "Boston":        "Boston Red Sox",
    "Chicago":       "Chicago Cubs",
    "Cincinnati":    "Cincinnati Reds",
    "Cleveland":     "Cleveland Guardians",
    "Colorado":      "Colorado Rockies",
    "Detroit":       "Detroit Tigers",
    "Houston":       "Houston Astros",
    "Kansas City":   "Kansas City Royals",
    "Los Angeles":   "Los Angeles Angels",
    "Miami":         "Miami Marlins",
    "Milwaukee":     "Milwaukee Brewers",
    "Minnesota":     "Minnesota Twins",
    "New York":      "New York Yankees",
    "Oakland":       "Oakland Athletics",
    "Philadelphia":  "Philadelphia Phillies",
    "Pittsburgh":    "Pittsburgh Pirates",
    "San Diego":     "San Diego Padres",
    "San Francisco": "San Francisco Giants",
    "Seattle":       "Seattle Mariners",
    "St. Louis":     "St. Louis Cardinals",
    "Tampa Bay":     "Tampa Bay Rays",
    "Texas":         "Texas Rangers",
    "Toronto":       "Toronto Blue Jays",
    "Washington":    "Washington Nationals",
}

CITY_LEAGUE_TO_TEAM = {
    ("Chicago", "AL"):     "Chicago White Sox",
    ("Chicago", "NL"):     "Chicago Cubs",
    ("Los Angeles", "AL"): "Los Angeles Angels",
    ("Los Angeles", "NL"): "Los Angeles Dodgers",
    ("New York", "AL"):    "New York Yankees",
    ("New York", "NL"):    "New York Mets",
}

VALID_SOURCE_TYPES = {"ap", "getty", "mlb", "team", "manual", "illustrated"}
MEDIA_DIR = BASE_DIR / "media" / "lead-images"

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))


def load_json(filename, fallback=None):
    path = DATA_DIR / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if filename == "game_cards.json" and isinstance(data, dict) and "games" in data:
            for g in data["games"]:
                if isinstance(g, dict) and "home_runs" not in g:
                    home_rhe = g.get("home_rhe", [])
                    if home_rhe and len(home_rhe) > 0 and home_rhe[0] != '':
                        try:
                            g["home_runs"] = int(home_rhe[0])
                        except (ValueError, TypeError):
                            g["home_runs"] = 0
                    else:
                        g["home_runs"] = 0
        return data
    except Exception as e:
        print(f"  ⚠ Could not load {filename}: {e}")
        return fallback if fallback is not None else {}


def get_standings():
    data = load_json("standings.json")
    return data.get("leagues", []), data.get("updated", "")


def get_schedule():
    data = load_json("schedule.json")
    return (
        data.get("today", {}),
        data.get("rail_date", "Today"),
        data.get("games_date_full", ""),
        data.get("updated", ""),
    )


def get_game_cards():
    data = load_json("game_cards.json")
    return data.get("games", []), data.get("display_date", ""), data.get("game_count", 0)


def get_all_teams():
    data = load_json("teams.json", fallback={})
    teams = data.get("teams", [])
    return sorted(teams, key=lambda t: (t.get("league", ""), t.get("division", ""), t.get("name", "")))

def get_team_nicknames():
    """Returns dict mapping abbr -> nickname, e.g. 'NYY' -> 'Yankees'"""
    data = load_json("teams.json", fallback={})
    return {t["abbr"]: t["nickname"] for t in data.get("teams", []) if t.get("abbr") and t.get("nickname")}

def load_roster_md(team_name):
    """
    Load a team roster from Rosters/ markdown files.
    Returns list of dicts with keys: number, name, pos, bats, throws
    Returns empty list if file not found.
    """
    import re
    roster_dirs = [
        VAULT / "Rosters" / "American League" / "American League East",
        VAULT / "Rosters" / "American League" / "American League Central",
        VAULT / "Rosters" / "American League" / "American League West",
        VAULT / "Rosters" / "National League" / "National League East",
        VAULT / "Rosters" / "National League" / "National League Central",
        VAULT / "Rosters" / "National League" / "National League West",
    ]
    for d in roster_dirs:
        p = d / f"{team_name}.md"
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8")
                players = []
                for line in text.splitlines():
                    if line.startswith("| #") and "Name" not in line and "---" not in line:
                        parts = [x.strip() for x in line.split("|")]
                        parts = [x for x in parts if x]
                        if len(parts) >= 3:
                            players.append({
                                "number": parts[0].lstrip("#"),
                                "name": parts[1],
                                "pos": parts[2],
                                "bats": parts[3] if len(parts) > 3 else "",
                                "throws": parts[4] if len(parts) > 4 else "",
                            })
                return players
            except Exception:
                return []
    return []

def get_team_by_slug(slug):
    for team in get_all_teams():
        if team.get("slug") == slug:
            return team
    return None

def get_team_record(team_abbr):
    leagues, _ = get_standings()
    # Build city + league lookup from teams.json for disambiguation
    # (standings.json stores city only, not abbr)
    teams_meta = {t["abbr"]: t for t in load_json("teams.json", fallback={}).get("teams", [])}
    meta = teams_meta.get(team_abbr, {})
    expected_city   = meta.get("city", "")
    expected_league = meta.get("division", "").split()[0]  # "AL East" -> "AL"
    for league in leagues:
        league_name = league.get("league", "")
        for division in league.get("divisions", []):
            teams = division.get("teams", [])
            for idx, team in enumerate(teams, start=1):
                # Direct abbr match (future-proof if standings gains abbr field)
                if team.get("abbr") == team_abbr or team.get("team_abbr") == team_abbr:
                    return {
                        "wins": team.get("w"),
                        "losses": team.get("l"),
                        "record": f"{team.get('w', '—')}-{team.get('l', '—')}",
                        "position": idx,
                        "division": division.get("name", ""),
                        "games_back": team.get("gb", team.get("games_back", "—"))
                    }
                # Fallback: city + league match (handles NY/CHI/LA disambiguation)
                if expected_city and team.get("city") == expected_city and league_name == expected_league:
                    return {
                        "wins": team.get("w"),
                        "losses": team.get("l"),
                        "record": f"{team.get('w', '—')}-{team.get('l', '—')}",
                        "position": idx,
                        "division": division.get("name", ""),
                        "games_back": team.get("gb", team.get("games_back", "—"))
                    }
    return None

def team_in_game(game, team_abbr):
    return team_abbr in [
        game.get("away_abbr"),
        game.get("home_abbr"),
        game.get("away"),
        game.get("home"),
    ]

def is_game_postponed(game):
    """Helper to determine if a game is postponed based on its status."""
    return game.get("game_status") == "POSTPONED"

@app.context_processor
def inject_is_game_postponed():
    return dict(is_game_postponed=is_game_postponed)

def get_team_recent_games(team_abbr):
    games, _, _ = get_game_cards()
    return [g for g in games if team_in_game(g, team_abbr)][:5]

def get_team_upcoming_games(team_abbr):
    today_slate, _, _, _ = get_schedule()
    games = today_slate.get("games", []) if isinstance(today_slate, dict) else []
    return [g for g in games if team_in_game(g, team_abbr)][:5]

def get_latest_team_box_score(team_abbr):
    recent = get_team_recent_games(team_abbr)
    return recent[0] if recent else None


def get_odds():
    data = load_json("odds.json", fallback={})
    return data.get("games", []), data.get("updated", "")

def get_game_of_day():
    data = load_json("game_of_day.json", fallback={})
    return data if data else None

def get_around_the_league():
    data = load_json("around_the_league.json", fallback={})
    return data if data else None

def get_game_to_watch():
    data = load_json("game_to_watch.json", fallback={})
    if not data:
        return None
    gtw_date = data.get("updated", "")[:10]
    sched_data = load_json("schedule.json", fallback={})
    schedule_date = sched_data.get("updated", "")[:10]
    if gtw_date and schedule_date and gtw_date != schedule_date:
        print(f"  ⚠ DATA-003: game_to_watch suppressed — gtw date ({gtw_date}) != schedule slate date ({schedule_date})")
        return None
    # Clean internal scoring language from reason field
    bad_phrases = [
        "composite score", "ranking score", "algorithm",
        "model output", "best composite", "score on today's slate",
        "highest composite", "slate score"
    ]
    reason = data.get("reason", "")
    reason_lower = reason.lower()
    if any(phrase in reason_lower for phrase in bad_phrases):
        # Replace with editorial explanation based on breakdown
        breakdown = data.get("breakdown", {})
        away_full = data.get("away_full", data.get("away", ""))
        home_full = data.get("home_full", data.get("home", ""))
        away_pitcher = data.get("away_pitcher", "")
        home_pitcher = data.get("home_pitcher", "")
        if breakdown.get("pitching_matchup", 0) >= 30:
            data["reason"] = f"Features one of the stronger pitching matchups on the slate — {away_pitcher} against {home_pitcher}."
        elif breakdown.get("national_relevance", 0) >= 20:
            data["reason"] = f"Two nationally relevant clubs meet in a game with playoff implications."
        elif breakdown.get("division_race", 0) >= 20:
            data["reason"] = f"A division matchup with standings implications."
        else:
            data["reason"] = f"{away_full} and {home_full} meet in today's featured game."
    return data

def get_press_box():
    data = load_json("press_box.json", fallback={})
    if not data or not data.get("passed_validation"):
        return None
    # Date guard: compare ISO date in press_box.json against
    # ISO date in game_cards.json — both are YYYY-MM-DD format
    gc = load_json("game_cards.json", fallback={})
    gc_date = gc.get("date", "")
    pb_date = data.get("date", "")
    if gc_date and pb_date and pb_date != gc_date:
        print(f"  press_box date {pb_date} != game_cards date {gc_date} — suppressing")
        return None
    return data


# ── BOX SCORES HELPERS ────────────────────────────────────────────────────────

AL_TEAMS = {
    "BAL","BOS","CWS","CLE","DET","HOU","KC","LAA",
    "MIN","NYY","ATH","SEA","TB","TEX","TOR"
}
NL_TEAMS = {
    "AZ","ATL","CHC","CIN","COL","LAD","MIA","MIL",
    "NYM","PHI","PIT","SD","SF","STL","WSH","WAS"
}

def get_team_league(abbr):
    if abbr in AL_TEAMS: return "AL"
    if abbr in NL_TEAMS: return "NL"
    return "NL"

def group_games_by_league(games):
    al, nl = [], []
    for g in games:
        league = get_team_league(g.get("home_abbr", ""))
        if league == "AL":
            al.append(g)
        else:
            nl.append(g)
    return al, nl

def build_day_summary(games):
    total     = len(games)
    one_run   = sum(1 for g in games
                    if abs(int(g.get("away_runs") or 0) - int(g.get("home_runs") or 0)) == 1)
    shutouts  = sum(1 for g in games
                    if int(g.get("away_runs") or 0) == 0 or int(g.get("home_runs") or 0) == 0)
    home_runs = sum(
        sum(int(b.get("hr", 0)) for b in g.get("away_batting", []))
        + sum(int(b.get("hr", 0)) for b in g.get("home_batting", []))
        for g in games
    )
    extra_inn = sum(1 for g in games if len(g.get("innings", [])) > 9)
    return {
        "total":     total,
        "one_run":   one_run,
        "shutouts":  shutouts,
        "home_runs": home_runs,
        "extra_inn": extra_inn,
    }

def build_key_note(g):
    away  = g.get("away_abbr", "")
    home  = g.get("home_abbr", "")
    aR    = g.get("away_runs", 0)
    hR    = g.get("home_runs", 0)
    notes = []

    # Extra innings
    inn_count = len(g.get("innings", []))
    if inn_count > 9:
        notes.append(f"Game required {inn_count} innings.")

    # Shutout
    if aR == 0:
        notes.append(f"{home} blanked {away}.")
    elif hR == 0:
        notes.append(f"{away} blanked {home}.")

    # Decisive inning
    winner_line = g.get("away_line", []) if aR > hR else g.get("home_line", [])
    winner_name = away if aR > hR else home
    if winner_line:
        try:
            max_runs = max(int(r) for r in winner_line if str(r).isdigit())
            max_inn  = next(
                (i + 1 for i, r in enumerate(winner_line)
                 if str(r).isdigit() and int(r) == max_runs),
                None
            )
            if max_runs >= 3 and max_inn:
                ordinals = {
                    1:"1st",2:"2nd",3:"3rd",4:"4th",5:"5th",
                    6:"6th",7:"7th",8:"8th",9:"9th",10:"10th",
                    11:"11th",12:"12th"
                }
                inn_label = ordinals.get(max_inn, f"{max_inn}th")
                notes.append(
                    f"{winner_name} scored {max_runs} in the {inn_label}."
                )
        except (ValueError, TypeError):
            pass

    # Home run notes (cap at 3)
    all_batters = (
        [(b, away) for b in g.get("away_batting", [])] +
        [(b, home) for b in g.get("home_batting", [])]
    )
    hr_batters = [
        f"{b['name']} ({t})" + (" (2)" if int(b.get("hr", 0)) >= 2 else "")
        for b, t in all_batters if int(b.get("hr", 0)) >= 1
    ]
    if hr_batters:
        notes.append("HR: " + ", ".join(hr_batters[:3]) + ".")

    # Pitching gem: 6+ IP, <= 2 ER
    all_pitchers = (
        [(p, away) for p in g.get("away_pitching", [])] +
        [(p, home) for p in g.get("home_pitching", [])]
    )
    for p, t in all_pitchers:
        try:
            ip_str = str(p.get("ip", "0"))
            ip = float(ip_str.replace(".1", ".33").replace(".2", ".67"))
            er = int(p.get("er", 99))
            k  = int(p.get("k", 0))
            if ip >= 6.0 and er <= 2:
                k_note = f", {k} K" if k >= 6 else ""
                notes.append(f"{p['name']} ({t}): {p['ip']} IP{k_note}.")
                break
        except (ValueError, TypeError):
            pass

    return "  ".join(notes) if notes else ""

def build_press_wire_bullets(games):
    return build_around_baseball(games)

def build_around_baseball(games):
    bullets = []

    for g in games:
        away  = g.get("away_abbr", "")
        home  = g.get("home_abbr", "")
        aR    = g.get("away_runs", 0)
        hR    = g.get("home_runs", 0)
        wR    = max(aR, hR)
        lR    = min(aR, hR)
        winner = away if aR > hR else home
        loser  = home if aR > hR else away
        inn_count = len(g.get("innings", []))

        # Shutout
        if lR == 0:
            bullets.append(f"{winner} blanked {loser}, {wR}\u20130")
            continue

        # Extra innings
        if inn_count > 9:
            bullets.append(f"{winner} walked off {loser} in {inn_count} innings, {wR}\u2013{lR}")
            continue

        # Blowout
        if abs(aR - hR) >= 7:
            bullets.append(f"{winner} routed {loser}, {wR}\u2013{lR}")
            continue

        # One-run game
        if abs(aR - hR) == 1:
            bullets.append(f"{winner} edged {loser} in a one-run game, {wR}\u2013{lR}")
            continue

        bullets.append(f"{winner} defeated {loser}, {wR}\u2013{lR}")

    # Notable batting \u2014 multi-HR games
    for g in games:
        away = g.get("away_abbr", "")
        home = g.get("home_abbr", "")
        all_batters = (
            [(b, away) for b in g.get("away_batting", [])] +
            [(b, home) for b in g.get("home_batting", [])]
        )
        for b, t in all_batters:
            try:
                hr = int(b.get("hr", 0))
                if hr >= 2:
                    bullets.append(f"{b['name']} ({t}) homered {hr} times")
            except (ValueError, TypeError):
                pass

    # Notable pitching \u2014 dominant starts (7+ IP, \u2264 1 ER, 7+ K)
    for g in games:
        away = g.get("away_abbr", "")
        home = g.get("home_abbr", "")
        all_pitchers = (
            [(p, away) for p in g.get("away_pitching", [])] +
            [(p, home) for p in g.get("home_pitching", [])]
        )
        for p, t in all_pitchers:
            try:
                ip_str = str(p.get("ip", "0"))
                ip = float(ip_str.replace(".1", ".33").replace(".2", ".67"))
                er = int(p.get("er", 99))
                k  = int(p.get("k", 0))
                if ip >= 7.0 and er <= 1 and k >= 7:
                    bullets.append(
                        f"{p['name']} ({t}) dominant: {p['ip']} IP, {k} K, {er} ER"
                    )
                    break
            except (ValueError, TypeError):
                pass

    # High RBI games (4+)
    for g in games:
        away = g.get("away_abbr", "")
        home = g.get("home_abbr", "")
        all_batters = (
            [(b, away) for b in g.get("away_batting", [])] +
            [(b, home) for b in g.get("home_batting", [])]
        )
        for b, t in all_batters:
            try:
                rbi = int(b.get("rbi", 0))
                if rbi >= 4:
                    bullets.append(f"{b['name']} ({t}) drove in {rbi} runs")
            except (ValueError, TypeError):
                pass

    return bullets

def get_scoreboard_data():
    data = load_json("game_cards.json")
    return {
        "games":        data.get("games", []),
        "display_date": data.get("display_date", ""),
        "date":         data.get("date", ""),
        "game_count":   data.get("game_count", 0),
        "updated":      data.get("updated", ""),
    }

def build_game_slug(away_abbr, home_abbr, date_str):
    """
    Build URL slug from game identifiers.
    Example: build_game_slug("SD", "PHI", "2026-06-04") -> "sd-phi-2026-06-04"
    """
    return f"{away_abbr.lower()}-{home_abbr.lower()}-{date_str}"

def find_game_by_slug(slug, games, date_str):
    """
    Find a game dict by slug.
    Slug format: away_abbr-home_abbr-YYYY-MM-DD (all lowercase)
    Returns game dict or None.
    """
    if not slug or not games:
        return None
    parts = slug.split("-")
    if len(parts) < 5:
        return None
    # Last 3 parts are the date: YYYY-MM-DD
    date_part = "-".join(parts[-3:])
    away = parts[0].upper()
    home = parts[1].upper()
    if date_part != date_str:
        return None
    for g in games:
        if g.get("away_abbr", "").upper() == away and \
           g.get("home_abbr", "").upper() == home:
            return g
    return None

def build_star_performers(game):
    """
    Derive top performers from batting and pitching data.
    Returns dict with batters and pitchers lists.
    """
    away = game.get("away_abbr", "")
    home = game.get("home_abbr", "")
    batters = []
    pitchers = []

    all_batters = (
        [(b, away) for b in game.get("away_batting", [])] +
        [(b, home) for b in game.get("home_batting", [])]
    )
    for b, team in all_batters:
        highlights = []
        try:
            if int(b.get("hr", 0)) >= 1:
                highlights.append(f"{b['hr']} HR")
            if int(b.get("rbi", 0)) >= 3:
                highlights.append(f"{b['rbi']} RBI")
            if int(b.get("h", 0)) >= 3:
                highlights.append(f"{b['h']}-for-{b['ab']}")
            if highlights:
                batters.append({
                    "name": b["name"],
                    "team": team,
                    "ab": b.get("ab", 0),
                    "r":  b.get("r", 0),
                    "h":  b.get("h", 0),
                    "hr": b.get("hr", 0),
                    "rbi": b.get("rbi", 0),
                    "highlight": " · ".join(highlights),
                })
        except (ValueError, TypeError):
            pass

    all_pitchers = (
        [(p, away) for p in game.get("away_pitching", [])] +
        [(p, home) for p in game.get("home_pitching", [])]
    )
    for p, team in all_pitchers:
        try:
            ip_str = str(p.get("ip", "0"))
            ip = float(ip_str.replace(".1", ".33").replace(".2", ".67"))
            er = int(p.get("er", 99))
            k  = int(p.get("k", 0))
            highlight = None
            if ip >= 6.0 and er <= 2:
                highlight = f"{p['ip']} IP, {k} K, {er} ER"
            elif k >= 8:
                highlight = f"{k} K, {p['ip']} IP"
            if highlight:
                pitchers.append({
                    "name": p["name"],
                    "team": team,
                    "ip":   p.get("ip", ""),
                    "er":   p.get("er", 0),
                    "k":    p.get("k", 0),
                    "bb":   p.get("bb", 0),
                    "highlight": highlight,
                })
        except (ValueError, TypeError):
            pass

    return {"batters": batters[:4], "pitchers": pitchers[:3]}

def build_turning_point(game):
    """
    Identify the decisive inning from the line score.
    Returns dict with inning, team, runs, description.
    """
    away = game.get("away_abbr", "")
    home = game.get("home_abbr", "")
    aR   = game.get("away_runs", 0)
    hR   = game.get("home_runs", 0)
    winner = away if aR > hR else home
    winner_line = game.get("away_line", []) if aR > hR else game.get("home_line", [])

    ordinals = {
        1:"1st",2:"2nd",3:"3rd",4:"4th",5:"5th",
        6:"6th",7:"7th",8:"8th",9:"9th",10:"10th",
        11:"11th",12:"12th"
    }

    try:
        max_runs = max(int(r) for r in winner_line if str(r).isdigit())
        max_inn  = next(
            (i + 1 for i, r in enumerate(winner_line)
             if str(r).isdigit() and int(r) == max_runs),
            None
        )
        if max_runs >= 2 and max_inn:
            inn_label = ordinals.get(max_inn, f"{max_inn}th")
            return {
                "inning": max_inn,
                "inn_label": inn_label,
                "team": winner,
                "runs": max_runs,
                "description": (
                    f"{winner} scored {max_runs} run{'s' if max_runs > 1 else ''} "
                    f"in the {inn_label} inning to take control of the game."
                )
            }
    except (ValueError, TypeError):
        pass

    return {
        "inning": None,
        "inn_label": "",
        "team": winner,
        "runs": 0,
        "description": ""
    }


def build_todays_board(games):
    """
    Derive slate overview features from game data.
    Returns dict with up to 5 features.
    Only includes features that can be safely derived.
    """
    board = {}

    if not games:
        return board

    # Game of the Night — priority: extra innings > one-run > highest run total
    game_of_night = None
    for g in games:
        inn_count = len(g.get("innings", []))
        if inn_count > 9:
            game_of_night = g
            break
    if not game_of_night:
        one_run = [g for g in games
                   if abs(int(g.get("away_runs") or 0) - int(g.get("home_runs") or 0)) == 1]
        if one_run:
            game_of_night = one_run[0]
    if not game_of_night:
        game_of_night = max(games,
            key=lambda g: int(g.get("away_runs") or 0) + int(g.get("home_runs") or 0))
    if game_of_night:
        aR = int(game_of_night.get("away_runs") or 0)
        hR = int(game_of_night.get("home_runs") or 0)
        winner = game_of_night.get("away_city") if aR > hR \
            else game_of_night.get("home_city")
        loser  = game_of_night.get("home_city") if aR > hR \
            else game_of_night.get("away_city")
        wR = max(aR, hR)
        lR = min(aR, hR)
        inn_count = len(game_of_night.get("innings", []))
        suffix = f" (F/{inn_count})" if inn_count > 9 else ""
        board["game_of_night"] = {
            "label": "Game of the Night",
            "headline": game_of_night.get("headline", ""),
            "summary": f"{winner} {wR}, {loser} {lR}{suffix}",
            "note": game_of_night.get("summary", ""),
            "slug": build_game_slug(
                game_of_night["away_abbr"],
                game_of_night["home_abbr"],
                ""  # filled in route
            ),
            "away_abbr": game_of_night["away_abbr"],
            "home_abbr": game_of_night["home_abbr"],
        }

    # Best Finish — extra innings first, then closest margin
    best_finish = None
    extras = [g for g in games if len(g.get("innings", [])) > 9]
    if extras:
        best_finish = extras[0]
    else:
        one_run = [g for g in games
                   if abs(int(g.get("away_runs") or 0) - int(g.get("home_runs") or 0)) == 1]
        if one_run:
            best_finish = one_run[0]
    if best_finish and best_finish is not game_of_night:
        aR = int(best_finish.get("away_runs") or 0)
        hR = int(best_finish.get("home_runs") or 0)
        inn_count = len(best_finish.get("innings", []))
        suffix = f" in {inn_count} innings" if inn_count > 9 else ", one-run game"
        board["best_finish"] = {
            "label": "Best Finish",
            "summary": f"{best_finish.get('away_abbr')} {aR} – "
                       f"{best_finish.get('home_abbr')} {hR}{suffix}",
            "note": best_finish.get("summary", ""),
            "slug": build_game_slug(
                best_finish["away_abbr"],
                best_finish["home_abbr"],
                ""
            ),
            "away_abbr": best_finish["away_abbr"],
            "home_abbr": best_finish["home_abbr"],
        }

    # Biggest Offensive Performance — highest combined runs
    biggest_offense = max(games,
        key=lambda g: int(g.get("away_runs") or 0) + int(g.get("home_runs") or 0))
    if biggest_offense:
        aR = int(biggest_offense.get("away_runs") or 0)
        hR = int(biggest_offense.get("home_runs") or 0)
        board["biggest_offense"] = {
            "label": "Biggest Offensive Game",
            "summary": f"{biggest_offense.get('away_abbr')} {aR} – "
                       f"{biggest_offense.get('home_abbr')} {hR} "
                       f"({aR + hR} combined runs)",
            "note": biggest_offense.get("summary", ""),
            "slug": build_game_slug(
                biggest_offense["away_abbr"],
                biggest_offense["home_abbr"],
                ""
            ),
            "away_abbr": biggest_offense["away_abbr"],
            "home_abbr": biggest_offense["home_abbr"],
        }

    # Pitching Gem — starter with 6+ IP, <= 2 ER, 6+ K
    pitching_gem = None
    gem_pitcher = None
    gem_team = None
    for g in games:
        away = g.get("away_abbr", "")
        home = g.get("home_abbr", "")
        for p, t in ([(p, away) for p in g.get("away_pitching", [])] +
                     [(p, home) for p in g.get("home_pitching", [])]):
            try:
                ip = float(str(p.get("ip","0")).replace(".1",".33")
                           .replace(".2",".67"))
                er = int(p.get("er", 99))
                k  = int(p.get("k", 0))
                if ip >= 6.0 and er <= 2 and k >= 6:
                    pitching_gem = g
                    gem_pitcher = p
                    gem_team = t
                    break
            except (ValueError, TypeError):
                pass
        if pitching_gem:
            break
    if pitching_gem and gem_pitcher:
        board["pitching_gem"] = {
            "label": "Pitching Gem",
            "summary": f"{gem_pitcher['name']} ({gem_team}): "
                       f"{gem_pitcher['ip']} IP, "
                       f"{gem_pitcher['k']} K, {gem_pitcher['er']} ER",
            "note": pitching_gem.get("summary", ""),
            "slug": build_game_slug(
                pitching_gem["away_abbr"],
                pitching_gem["home_abbr"],
                ""
            ),
            "away_abbr": pitching_gem["away_abbr"],
            "home_abbr": pitching_gem["home_abbr"],
        }

    # Oddity — shutout or blowout (7+ run margin)
    shutouts = [g for g in games
                if int(g.get("away_runs") or 0) == 0 or int(g.get("home_runs") or 0) == 0]
    if shutouts:
        oddity = shutouts[0]
        aR = int(oddity.get("away_runs") or 0)
        hR = int(oddity.get("home_runs") or 0)
        winner = oddity.get("away_abbr") if aR > hR else oddity.get("home_abbr")
        loser  = oddity.get("home_abbr") if aR > hR else oddity.get("away_abbr")
        board["oddity"] = {
            "label": "Shutout",
            "summary": f"{winner} blanked {loser}, {max(aR,hR)}–0",
            "note": oddity.get("summary", ""),
            "slug": build_game_slug(
                oddity["away_abbr"],
                oddity["home_abbr"],
                ""
            ),
            "away_abbr": oddity["away_abbr"],
            "home_abbr": oddity["home_abbr"],
        }
    else:
        blowouts = [g for g in games
                    if abs(int(g.get("away_runs") or 0) - int(g.get("home_runs") or 0)) >= 7]
        if blowouts:
            oddity = blowouts[0]
            aR = int(oddity.get("away_runs") or 0)
            hR = int(oddity.get("home_runs") or 0)
            winner = oddity.get("away_abbr") if aR > hR \
                else oddity.get("home_abbr")
            loser  = oddity.get("home_abbr") if aR > hR \
                else oddity.get("away_abbr")
            board["oddity"] = {
                "label": "Blowout",
                "summary": f"{winner} routed {loser}, "
                           f"{max(aR,hR)}–{min(aR,hR)}",
                "note": oddity.get("summary", ""),
                "slug": build_game_slug(
                    oddity["away_abbr"],
                    oddity["home_abbr"],
                    ""
                ),
                "away_abbr": oddity["away_abbr"],
                "home_abbr": oddity["home_abbr"],
            }

    return board


def get_lead_image(edition_date: str):
    jpg  = MEDIA_DIR / f"{edition_date}_lead.jpg"
    webp = MEDIA_DIR / f"{edition_date}_lead.webp"
    if jpg.exists():
        filename = jpg.name
    elif webp.exists():
        filename = webp.name
    else:
        return None
    captions_path = MEDIA_DIR / "captions.json"
    try:
        captions = json.loads(captions_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    meta        = captions.get(edition_date, {})
    caption     = meta.get("caption", "").strip()
    credit      = meta.get("credit", "").strip()
    source_type = meta.get("source_type", "").strip()
    if not caption or not credit or source_type not in VALID_SOURCE_TYPES:
        return None
    return {
        "filename":    filename,
        "url":         f"/media/lead-images/{filename}",
        "caption":     caption,
        "credit":      credit,
        "source_type": source_type,
    }

def get_dope_sheet_data():
    data = load_json("dope-sheet-data.json", fallback={})
    return (
        data.get("games", []),
        data.get("date_display", ""),
        data.get("date_banner", ""),
        data.get("updated", ""),
    )

@app.route("/dope-sheet")
@app.route("/dope-sheet.html")
def dope_sheet():
    ds_games, date_display, date_banner, ds_updated = get_dope_sheet_data()
    odds_games, odds_updated = get_odds()

    TEAM_ALIASES = {
        "Athletics":               "Oakland Athletics",
        "D-backs":                 "Arizona Diamondbacks",
        "Diamondbacks":            "Arizona Diamondbacks",
        "White Sox":               "Chicago White Sox",
        "Cubs":                    "Chicago Cubs",
        "Reds":                    "Cincinnati Reds",
        "Guardians":               "Cleveland Guardians",
        "Rockies":                 "Colorado Rockies",
        "Tigers":                  "Detroit Tigers",
        "Astros":                  "Houston Astros",
        "Royals":                  "Kansas City Royals",
        "Angels":                  "Los Angeles Angels",
        "Dodgers":                 "Los Angeles Dodgers",
        "Marlins":                 "Miami Marlins",
        "Brewers":                 "Milwaukee Brewers",
        "Twins":                   "Minnesota Twins",
        "Mets":                    "New York Mets",
        "Yankees":                 "New York Yankees",
        "Phillies":                "Philadelphia Phillies",
        "Pirates":                 "Pittsburgh Pirates",
        "Padres":                  "San Diego Padres",
        "Giants":                  "San Francisco Giants",
        "Mariners":                "Seattle Mariners",
        "Cardinals":               "St. Louis Cardinals",
        "Rays":                    "Tampa Bay Rays",
        "Rangers":                 "Texas Rangers",
        "Blue Jays":               "Toronto Blue Jays",
        "Nationals":               "Washington Nationals",
        "Braves":                  "Atlanta Braves",
        "Orioles":                 "Baltimore Orioles",
        "Red Sox":                 "Boston Red Sox",
    }

    def normalize(name):
        return TEAM_ALIASES.get(name, name)

    odds_lookup = {}
    for og in odds_games:
        key = (normalize(og["away_team"]), normalize(og["home_team"]))
        odds_lookup[key] = og.get("markets", {})

    def fmt_odds(n):
        if n is None:
            return "N/A"
        return f"+{n}" if n > 0 else str(n)

    def implied_pct(american):
        if american is None:
            return "—"
        if american < 0:
            pct = (-american) / (-american + 100) * 100
        else:
            pct = 100 / (american + 100) * 100
        return f"{pct:.0f}%"

    for g in ds_games:
        away_full = g.get("awayFull", "")
        home_full = g.get("homeFull", "")
        key = (away_full, home_full)
        markets = odds_lookup.get(key, {})

        ml = markets.get("moneyline", [])
        away_ml = next((m["odds_american"] for m in ml if m["team_side"] == "away"), None)
        home_ml = next((m["odds_american"] for m in ml if m["team_side"] == "home"), None)
        g["awayML"]      = fmt_odds(away_ml)
        g["homeML"]      = fmt_odds(home_ml)
        g["awayImplied"] = implied_pct(away_ml)
        g["homeImplied"] = implied_pct(home_ml)
        g["oddsLive"]    = any(m.get("is_live") for m in ml)

        rl = markets.get("run_line", [])
        away_rl = next((m for m in rl if m["team_side"] == "away"), {})
        home_rl = next((m for m in rl if m["team_side"] == "home"), {})
        away_line = away_rl.get("line")
        home_line = home_rl.get("line")
        away_rl_odds = away_rl.get("odds_american")
        home_rl_odds = home_rl.get("odds_american")
        g["awaySpread"]     = fmt_odds(int(away_line)) if away_line is not None else "—"
        g["homeSpread"]     = fmt_odds(int(home_line)) if home_line is not None else "—"
        g["awaySpreadOdds"] = fmt_odds(away_rl_odds) if away_rl_odds is not None else "—"
        g["homeSpreadOdds"] = fmt_odds(home_rl_odds) if home_rl_odds is not None else "—"

        tot = markets.get("total_runs", [])
        over_tot  = next((m for m in tot if m.get("selection_type") == "over"), {})
        under_tot = next((m for m in tot if m.get("selection_type") == "under"), {})
        g["ou"]        = over_tot.get("line", "—")
        g["overOdds"]  = fmt_odds(over_tot.get("odds_american"))  if over_tot.get("odds_american")  is not None else "—"
        g["underOdds"] = fmt_odds(under_tot.get("odds_american")) if under_tot.get("odds_american") is not None else "—"

        g["oddsAvailable"] = bool(markets)

    return render_template(
        "dope-sheet.html",
        games=ds_games,
        date_display=date_display,
        date_banner=date_banner,
        ds_updated=ds_updated,
        odds_updated=odds_updated,
    )


@app.route("/scoreboard")
@app.route("/scoreboard/")
def scoreboard():
    data     = get_scoreboard_data()
    games    = data["games"]
    date_str = data["date"]
    al_games, nl_games = group_games_by_league(games)
    summary  = build_day_summary(games)
    for g in games:
        g["key_note"] = build_key_note(g)
        g["slug"] = build_game_slug(g["away_abbr"], g["home_abbr"], date_str)
    todays_board = build_todays_board(games)
    # Fix slugs in todays_board to include date
    for key, item in todays_board.items():
        if item.get("away_abbr") and item.get("home_abbr"):
            item["slug"] = build_game_slug(
                item["away_abbr"], item["home_abbr"], date_str)
    all_slugs = []
    for g in games:
        try:
            if g.get("away_abbr") and g.get("home_abbr"):
                all_slugs.append({
                    "slug":      g["slug"],
                    "away_abbr": g["away_abbr"],
                    "home_abbr": g["home_abbr"],
                    "away_runs": int(g.get("away_runs") or 0),
                    "home_runs": int(g.get("home_runs") or 0),
                    "innings":   len(g.get("innings", [])),
                    "active":    False,
                })
        except Exception as e:
            print(f"  ⚠ Skipping malformed game in scoreboard slugs: {e}")
    return render_template(
        "scoreboard.html",
        al_games=al_games,
        nl_games=nl_games,
        all_games=games,
        summary=summary,
        todays_board=todays_board,
        all_slugs=all_slugs,
        display_date=data["display_date"],
        date=date_str,
        updated=data["updated"],
    )

@app.route("/scoreboard/<game_slug>")
def scoreboard_game(game_slug):
    from flask import abort
    data  = get_scoreboard_data()
    games = data["games"]
    date_str = data["date"]

    game = find_game_by_slug(game_slug, games, date_str)
    if not game:
        abort(404)

    # Attach key note
    game["key_note"] = build_key_note(game)

    # Build supporting data
    stars    = build_star_performers(game)
    turning  = build_turning_point(game)

    # Build slug list for game nav strip
    all_slugs = [
        {
            "slug":       build_game_slug(g["away_abbr"], g["home_abbr"], date_str),
            "away_abbr":  g["away_abbr"],
            "home_abbr":  g["home_abbr"],
            "away_runs":  g["away_runs"],
            "home_runs":  g["home_runs"],
            "winner":     g.get("winner", ""),
            "innings":    len(g.get("innings", [])),
            "active":     (g["away_abbr"] == game["away_abbr"] and
                          g["home_abbr"] == game["home_abbr"]),
        }
        for g in games
    ]

    return render_template(
        "scoreboard_game.html",
        game=game,
        game_slug=game_slug,
        stars=stars,
        turning=turning,
        all_slugs=all_slugs,
        display_date=data["display_date"],
        date=date_str,
        updated=data["updated"],
    )

# Aliases
@app.route("/box-scores")
@app.route("/box-scores/")
@app.route("/boxscores")
@app.route("/boxscores/")
def scoreboard_alias():
    from flask import redirect, url_for
    return redirect(url_for("scoreboard"), 301)

@app.route("/ledger")
@app.route("/ledger/")
def ledger_redirect():
    from flask import redirect, url_for
    return redirect(url_for("scoreboard"), 301)


@app.route("/")
@app.route("/index.html")
@app.route("/barrel-proof-home.html")
def homepage():
    standings, standings_updated = get_standings()
    today_slate, rail_date, games_date, schedule_updated = get_schedule()
    games, display_date, game_count = get_game_cards()
    odds_games, odds_updated = get_odds()
    gotd = get_game_of_day()
    atl = get_around_the_league()
    gtw = get_game_to_watch()
    pb = get_press_box()

    banner_date = display_date or games_date

    lead_image = None
    if gotd:
        gotd_date = gotd.get("date", "")
        gc_data   = load_json("game_cards.json", fallback={})
        gc_date   = gc_data.get("date", "")
        if gotd_date and gc_date and gotd_date == gc_date:
            lead_image = get_lead_image(gotd_date)
        elif gotd_date and gc_date and gotd_date != gc_date:
            print(f"  ⚠ MEDIA-001: lead image suppressed — gotd.date ({gotd_date}) != game_cards.date ({gc_date})")

    # Find GOTD game in game_cards for box score display
    gotd_game = None
    if gotd:
        gotd_away = gotd.get("game", {}).get("away", "")
        gotd_home = gotd.get("game", {}).get("home", "")
        for g in games:
            if g.get("away_abbr") == gotd_away and g.get("home_abbr") == gotd_home:
                gotd_game = g
                break

    from datetime import date
    edition_date = date.today().strftime("%B %-d, %Y").upper() + " EDITION"

    team_nicknames = get_team_nicknames()

    return render_template(
        "home.html",
        standings=standings,
        standings_updated=standings_updated,
        today_slate=today_slate,
        rail_date=rail_date,
        games_date=banner_date,
        game_count=game_count,
        games=games,
        odds_games=odds_games,
        odds_updated=odds_updated,
        schedule_updated=schedule_updated,
        gotd=gotd,
        atl=atl,
        gtw=gtw,
        pb=pb,
        lead_image=lead_image,
        gotd_game=gotd_game,
        edition_date=edition_date,
        team_nicknames=team_nicknames,
    )


@app.route("/archive")
@app.route("/archive/")
def archive_index():
    index_path = DATA_DIR / "archive" / "archive_index.json"
    try:
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        index_data = {}
    return render_template("archive_index.html", index=index_data)

@app.route("/advance-scout")
@app.route("/advance-scout/")
@app.route("/advanced-scout")
@app.route("/advanced-scout/")
def advance_scout():
    from datetime import datetime
    edition_date = datetime.now().strftime("%-B %-d, %Y EDITION").upper()
    return render_template("advance_scout.html",
        edition_date=edition_date,
        scout_notes=[],
    )

@app.route("/al-nl")
@app.route("/al-nl/")
def al_nl():
    standings, standings_updated = get_standings()
    enriched = []
    for league in standings:
        league_code = league.get("league", "")
        enriched_divs = []
        for div in league.get("divisions", []):
            enriched_teams = []
            for team in div.get("teams", []):
                city = team.get("city", "")
                key = (city, league_code)
                if key in CITY_LEAGUE_TO_TEAM:
                    full_name = CITY_LEAGUE_TO_TEAM[key]
                else:
                    full_name = CITY_TO_TEAM.get(city, city)
                roster = load_roster_md(full_name)
                enriched_teams.append({
                    "city": city,
                    "full_name": full_name,
                    "w": team.get("w", "—"),
                    "l": team.get("l", "—"),
                    "gb": team.get("gb", "—"),
                    "roster": roster,
                })
            enriched_divs.append({
                "name": div.get("name", ""),
                "teams": enriched_teams,
            })
        enriched.append({
            "league": league_code,
            "divisions": enriched_divs,
        })
    return render_template(
        "al_nl.html",
        leagues=enriched,
        standings_updated=standings_updated,
    )

@app.route("/archive/<year>/<month>/<day>")
def archive_edition(year, month, day):
    snap_path = BASE_DIR / "Site Data" / "archive" / year / "snapshots" / f"{year}-{month}-{day}.json"
    if not snap_path.exists():
        abort(404)
    try:
        snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    except Exception as e:
        app.logger.error(f"archive snapshot malformed: {snap_path}: {e}")
        abort(500)

    edition      = snapshot.get("edition") or {}
    completeness = snapshot.get("completeness", "historical")
    facts        = snapshot.get("facts") or {}
    facts_games  = facts.get("games") or []

    gotd = edition.get("game_of_day")
    gtw  = edition.get("game_to_watch")
    atl  = edition.get("around_the_league")
    pb   = edition.get("press_box")

    if pb and not pb.get("passed_validation"):
        pb = None

    gc_edition = edition.get("game_cards")
    if gc_edition and gc_edition.get("games"):
        games = gc_edition["games"]
    else:
        games = facts_games

    return render_template(
        "archive-edition.html",
        snapshot=snapshot,
        display_date=snapshot.get("display_date", ""),
        day_of_week=snapshot.get("day_of_week", ""),
        completeness=completeness,
        facts_games=facts_games,
        games=games,
        gotd=gotd,
        gtw=gtw,
        atl=atl,
        pb=pb,
    )


@app.route("/media/lead-images/<path:filename>")
def serve_lead_image(filename):
    return send_from_directory(str(MEDIA_DIR), filename)


@app.route("/teams")
@app.route("/teams/")
def teams_index():
    teams = get_all_teams()
    return render_template(
        "teams_index.html",
        teams=teams,
        page_title="MLB Teams — Barrel Proof",
        meta_description="Browse MLB team pages for scores, schedules, standings and recent results from Barrel Proof."
    )

@app.route("/team/<team_slug>")
def team_detail(team_slug):
    team = get_team_by_slug(team_slug)
    if not team:
        abort(404)

    abbr = team.get("abbr")
    record = get_team_record(abbr)
    recent_games = get_team_recent_games(abbr)
    upcoming_games = get_team_upcoming_games(abbr)
    latest_box_score = get_latest_team_box_score(abbr)

    return render_template(
        "team_detail.html",
        team=team,
        record=record,
        recent_games=recent_games,
        upcoming_games=upcoming_games,
        latest_box_score=latest_box_score,
        page_title=f"{team.get('name')} Scores, Schedule & Standings — Barrel Proof",
        meta_description=f"{team.get('name')} scores, recent results, standings and upcoming schedule from Barrel Proof."
    )


@app.route("/barrel-proof-american-league.html")
def american_league():
    return render_template("american-league.html")


@app.route("/barrel-proof-national-league.html")
def national_league():
    return render_template("national-league.html")


if __name__ == "__main__":
    print(f"BASE_DIR : {BASE_DIR}")
    print(f"DATA_DIR : {DATA_DIR}")
    print(f"standings  : {(DATA_DIR / 'standings.json').exists()}")
    print(f"schedule   : {(DATA_DIR / 'schedule.json').exists()}")
    print(f"game_cards : {(DATA_DIR / 'game_cards.json').exists()}")
    print(f"odds       : {(DATA_DIR / 'odds.json').exists()}")
    print(f"template   : {(BASE_DIR / 'templates' / 'home.html').exists()}")
    app.run(debug=True, port=5000)
