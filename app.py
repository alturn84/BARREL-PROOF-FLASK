#!/usr/bin/env python3
"""
Barrel Proof Baseball — Flask Web Server
"""

import json
import os
import re
import unicodedata
from pathlib import Path
from flask import Flask, render_template, abort, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "Site Data")))
PLAYER_DATA_DIR = DATA_DIR / "players"
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

# Maps teams.json abbr → game data abbr (for game_cards.json / schedule.json matching)
# Only entries that differ are listed.
ABBR_GAME_MAP = {
    "ARI": "AZ",   # Arizona: teams.json="ARI", game data="AZ"
    "WSH": "WSH",  # Washington: both use WSH (WAS also remapped in update scripts)
}

# standings.json uses "Athletics" as city for team 133,
# but teams.json has city="Oakland". This map normalizes the mismatch.
CITY_IN_STANDINGS_MAP = {
    "Oakland": "Athletics",
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

def player_lookup_key(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

def load_player_index():
    data = load_json("players/player_index.json", fallback=[])
    return data if isinstance(data, list) else []

def load_player_aliases():
    data = load_json("players/player_aliases.json", fallback={})
    return data if isinstance(data, dict) else {}

def get_player_by_slug(slug):
    wanted = str(slug or "").strip().lower()
    if not wanted:
        return None
    for player in load_player_index():
        if str(player.get("slug", "")).lower() == wanted:
            return player
    return None

def get_player_page_by_slug(slug):
    wanted = str(slug or "").strip().lower()
    if not wanted:
        return None
    page_path = PLAYER_DATA_DIR / "player_pages" / f"{wanted}.json"
    if not page_path.exists():
        return None
    data = load_json(f"players/player_pages/{wanted}.json", fallback=None)
    return data if isinstance(data, dict) else None

def load_hitter_luck_gap_cards():
    data = load_json("players/hitter_luck_gap.json", fallback={})
    players = data.get("players") if isinstance(data, dict) else {}
    return players if isinstance(players, dict) else {}

def load_hitter_power_signal_cards():
    data = load_json("players/hitter_power_signal.json", fallback={})
    players = data.get("players") if isinstance(data, dict) else {}
    return players if isinstance(players, dict) else {}

def resolve_player_name(name):
    if not name:
        return None
    query = str(name).strip()
    if not query:
        return None

    players = load_player_index()
    by_slug = {p.get("slug"): p for p in players if p.get("slug")}

    aliases = load_player_aliases()
    normalized_query = player_lookup_key(query)
    exact_matches = [
        player for player in players
        if normalized_query in {
            player_lookup_key(player.get("full_name")),
            player_lookup_key(player.get("display_name")),
        }
    ]
    if len({player.get("slug") for player in exact_matches if player.get("slug")}) > 1:
        return None
    if len(exact_matches) == 1:
        return exact_matches[0]

    alias_target = aliases.get(query)
    if alias_target:
        return by_slug.get(alias_target) or get_player_by_slug(alias_target)

    for alias, target in aliases.items():
        if player_lookup_key(alias) == normalized_query:
            return by_slug.get(target) or get_player_by_slug(target)

    fallback_matches = []
    for player in players:
        if normalized_query in {
            player_lookup_key(player.get("full_name")),
            player_lookup_key(player.get("display_name")),
            player_lookup_key(player.get("slug")),
        }:
            fallback_matches.append(player)

    if len({player.get("slug") for player in fallback_matches if player.get("slug")}) == 1:
        return fallback_matches[0]

    return None

def player_url(player):
    if not player or not player.get("slug"):
        return None
    return f"/player/{player['slug']}"

@app.context_processor
def inject_player_helpers():
    def stat_value(value):
        if value is None or value == "" or value is False:
            return "—"
        return value
    def signed_stat_value(value):
        if value is None or value == "" or value is False:
            return "—"
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return f"+{value}"
        return value
    return dict(player_url=player_url, stat_value=stat_value, signed_stat_value=signed_stat_value)

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
    raw_city = meta.get("city", "")
    expected_city = CITY_IN_STANDINGS_MAP.get(raw_city, raw_city)
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
    # Build a set of abbreviations to check — include any game-data alias
    check_abbrs = {team_abbr}
    if team_abbr in ABBR_GAME_MAP:
        check_abbrs.add(ABBR_GAME_MAP[team_abbr])
    return bool(
        check_abbrs & {
            game.get("away_abbr", ""),
            game.get("home_abbr", ""),
        }
    )

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


def get_team_form():
    """Returns dict keyed by team_abbr with last-10 form data."""
    data = load_json("team_form.json", fallback={})
    return data.get("teams", {})


def get_schedule_lookahead():
    """Returns dict keyed by team_abbr with next_games arrays."""
    data = load_json("schedule_lookahead.json", fallback={})
    return data.get("teams", {})


def get_team_stats():
    """Returns dict keyed by team_abbr with batting/pitching dicts."""
    data = load_json("team_stats.json", fallback={})
    return data.get("teams", {})


def get_team_il():
    """Returns dict keyed by team_abbr with list of IL player dicts."""
    data = load_json("team_il.json", fallback={})
    return data.get("teams", {})

def get_scoreboard_stats():
    data = load_json("scoreboard.json", fallback={})
    return {
        "games":     data.get("games", "—"),
        "home_runs": data.get("home_runs", "—"),
        "extras":    data.get("extras", "—"),
        "shutouts":  data.get("shutouts", "—"),
        "edition":   data.get("edition", ""),
        "updated":   data.get("updated", ""),
    }

@app.route("/dope-sheet")
@app.route("/dope-sheet.html")
def dope_sheet():
    sched_data = load_json("schedule.json", fallback={})
    today_slate = sched_data.get("today", {})
    sched_date = today_slate.get("date", "")
    
    from datetime import datetime
    try:
        dt = datetime.strptime(sched_date, "%Y-%m-%d")
    except Exception:
        dt = datetime.now()
    
    expected_display = dt.strftime("%A, %B %-d, %Y")
    expected_banner  = dt.strftime("%B %-d, %Y").upper()

    ds_games, date_display, date_banner, ds_updated = get_dope_sheet_data()
    odds_games, odds_updated = get_odds()

    if date_display != expected_display:
        import sys
        print(f"  ⚠ Dope Sheet date mismatch! Stale: {date_display} vs Expected: {expected_display}. Regenerating...")
        try:
            import subprocess
            cmd = [str(Path(sys.executable)), "update_dope_sheet.py", sched_date]
            subprocess.run(cmd, cwd=str(BASE_DIR), timeout=45, check=True)
            ds_games, date_display, date_banner, ds_updated = get_dope_sheet_data()
        except Exception as e:
            print(f"  ✗ Failed to regenerate Dope Sheet: {e}")
            ds_games = []
            for sg in today_slate.get("games", []):
                ds_games.append({
                    "away": sg.get("away_abbr", ""),
                    "home": sg.get("home_abbr", ""),
                    "awayFull": sg.get("away", "") + " " + sg.get("away_abbr", ""),
                    "homeFull": sg.get("home", "") + " " + sg.get("home_abbr", ""),
                    "time": sg.get("time", ""),
                    "venue": "TBD",
                    "pitchers": {
                        "away": {"name": sg.get("away_prob", "TBD"), "hand": "R", "era": "—", "whip": "—", "k9": "—", "bb9": "—", "ip": "—", "lastStart": "—"},
                        "home": {"name": sg.get("home_prob", "TBD"), "hand": "R", "era": "—", "whip": "—", "k9": "—", "bb9": "—", "ip": "—", "lastStart": "—"}
                    },
                    "weather": {"temp": "—", "sky": "—", "wind": "—", "humidity": "—", "precip": "—", "roof": "Open"},
                    "umpire": {"name": "TBD", "calledKpct": "—", "rpg": "—", "note": "—"},
                    "lineups": {"away": [], "home": []},
                    "bullpen": {"away": [], "home": []},
                    "injuries": {"away": [], "home": []},
                    "props": {"note": "", "pitchers": [], "batters": []}
                })
            date_display = expected_display
            date_banner = expected_banner

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
        away_team = og.get("away_team", "")
        home_team = og.get("home_team", "")
        key = (normalize(away_team), normalize(home_team))
        
        sb_dict = og.get("sportsbooks", {})
        sb_data = sb_dict.get("fanduel") or sb_dict.get("draftkings") or {}
        
        mapped_markets = {}
        if sb_data:
            # 1. Moneyline
            mapped_ml = []
            for item in sb_data.get("moneyline", []):
                item_name = item.get("name", "")
                side = "away" if item_name == away_team else "home" if item_name == home_team else None
                if side:
                    mapped_ml.append({
                        "team_side": side,
                        "odds_american": item.get("price")
                    })
            mapped_markets["moneyline"] = mapped_ml
            
            # 2. Run Line (Spread)
            mapped_rl = []
            for item in sb_data.get("run_line", []):
                item_name = item.get("name", "")
                side = "away" if item_name == away_team else "home" if item_name == home_team else None
                if side:
                    mapped_rl.append({
                        "team_side": side,
                        "line": item.get("point"),
                        "odds_american": item.get("price")
                    })
            mapped_markets["run_line"] = mapped_rl
            
            # 3. Total
            mapped_tot = []
            for item in sb_data.get("total", []):
                sel_type = item.get("name", "").lower()
                if sel_type in ["over", "under"]:
                    mapped_tot.append({
                        "selection_type": sel_type,
                        "line": item.get("point"),
                        "odds_american": item.get("price")
                    })
            mapped_markets["total_runs"] = mapped_tot
            
        odds_lookup[key] = mapped_markets

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
        g["awaySpread"]     = fmt_odds(away_line) if away_line is not None else "—"
        g["homeSpread"]     = fmt_odds(home_line) if home_line is not None else "—"
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

@app.route("/scoreboard-image")
@app.route("/scoreboard-image/")
def scoreboard_image():
    stats = get_scoreboard_stats()
    return render_template("scoreboard_image.html", **stats)

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

    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        _today_et = datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        from datetime import timezone, timedelta
        _today_et = (datetime.now(timezone.utc) - timedelta(hours=4)).date()
    edition_date = _today_et.strftime("%B %-d, %Y").upper() + " EDITION"

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

    months = []
    for year_entry in index_data.get("years", []):
        year = year_entry.get("year")
        year_index_path = DATA_DIR / "archive" / str(year) / "index.json"
        try:
            year_index = json.loads(year_index_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for month_entry in year_index.get("months", []):
            month_num = month_entry.get("month")
            month_file = DATA_DIR / "archive" / str(year) / month_entry.get("index_path", "")
            first_day = "01"
            try:
                month_data = json.loads(month_file.read_text(encoding="utf-8"))
                dates = month_data.get("dates", [])
                if dates:
                    first_day = dates[0].get("date", "")[-2:] or "01"
            except Exception:
                pass
            months.append({
                "year": year,
                "month_num": f"{month_num:02d}",
                "month_label": month_entry.get("month_name"),
                "count": month_entry.get("date_count"),
                "first_day": first_day,
            })

    months.sort(key=lambda m: (m["year"], m["month_num"]), reverse=True)
    return render_template("archive_index.html", index=index_data, months=months)

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
    teams_raw  = load_json("teams.json", fallback={}).get("teams", [])
    form_data  = get_team_form()

    # Build (standings_city, league) -> team metadata from teams.json
    # Uses CITY_IN_STANDINGS_MAP for cities that differ between the two sources
    city_league_to_meta = {}
    for t in teams_raw:
        raw_city       = t.get("city", "")
        standings_city = CITY_IN_STANDINGS_MAP.get(raw_city, raw_city)
        league         = t.get("league", "")
        city_league_to_meta[(standings_city, league)] = t

    enriched = []
    for league in standings:
        league_code = league.get("league", "")
        enriched_divs = []
        for div in league.get("divisions", []):
            enriched_teams = []
            for idx, team in enumerate(div.get("teams", []), start=1):
                city = team.get("city", "")
                meta = city_league_to_meta.get((city, league_code))
                abbr     = meta.get("abbr", "")     if meta else ""
                slug     = meta.get("slug", "")     if meta else ""
                nickname = meta.get("nickname", city) if meta else city
                form     = form_data.get(abbr, {})  if abbr else {}
                enriched_teams.append({
                    "city":        city,
                    "nickname":    nickname,
                    "full_name":   meta.get("name", city) if meta else city,
                    "abbr":        abbr,
                    "slug":        slug,
                    "w":           team.get("w", "—"),
                    "l":           team.get("l", "—"),
                    "gb":          team.get("gb", "—"),
                    "position":    idx,
                    "last_10":     form.get("last_10_record", ""),
                    "streak":      form.get("current_streak", ""),
                    "streak_type": form.get("streak_type", ""),
                })
            enriched_divs.append({
                "name":  div.get("name", ""),
                "teams": enriched_teams,
            })
        enriched.append({
            "league":      league_code,
            "league_full": "American League" if league_code == "AL" else "National League",
            "divisions":   enriched_divs,
        })

    # Hot teams: 7+ wins in last 10. Cold: 3 or fewer.
    hot_teams, cold_teams = [], []
    for abbr, form in form_data.items():
        wins = form.get("last_10_wins", 0) or 0
        meta = next((t for t in teams_raw if t.get("abbr") == abbr), None)
        if not meta:
            continue
        entry = {
            "nickname":    meta.get("nickname", abbr),
            "abbr":        abbr,
            "slug":        meta.get("slug", ""),
            "last_10":     form.get("last_10_record", ""),
            "streak":      form.get("current_streak", ""),
            "streak_type": form.get("streak_type", ""),
        }
        if wins >= 7:
            hot_teams.append(entry)
        elif wins <= 3:
            cold_teams.append(entry)

    hot_teams  = sorted(hot_teams,  key=lambda x: -(form_data.get(x["abbr"], {}).get("last_10_wins", 0) or 0))[:5]
    cold_teams = sorted(cold_teams, key=lambda x:  (form_data.get(x["abbr"], {}).get("last_10_wins", 99) or 99))[:5]

    # Closest races: divisions where 1st-to-2nd GB <= 2.5
    closest_races = []
    for league in enriched:
        for div in league["divisions"]:
            div_teams = div["teams"]
            if len(div_teams) >= 2:
                try:
                    gb_str = div_teams[1].get("gb", "—")
                    gb_val = float(gb_str) if gb_str not in ("—", "-", "") else 99.0
                    if gb_val <= 2.5:
                        closest_races.append({
                            "label":    f"{league['league']} {div['name']}",
                            "gb":       gb_str,
                            "teams":    div_teams[:3],
                        })
                except (ValueError, TypeError):
                    pass

    return render_template(
        "al_nl.html",
        leagues=enriched,
        standings_updated=standings_updated,
        hot_teams=hot_teams,
        cold_teams=cold_teams,
        closest_races=closest_races,
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
    from flask import redirect
    return redirect("/al-nl#team-directory", 302)

@app.route("/players")
@app.route("/players/")
def players_index():
    players = [p for p in load_player_index() if p.get("active", True)]
    team_order = {team.get("abbr"): idx for idx, team in enumerate(get_all_teams())}
    grouped = []
    by_team = {}

    for player in players:
        abbr = player.get("team_abbr") or "FA"
        by_team.setdefault(abbr, {
            "abbr": abbr,
            "name": player.get("team_name") or ("Free Agents" if abbr == "FA" else abbr),
            "players": [],
        })["players"].append(player)

    for group in by_team.values():
        group["players"].sort(key=lambda p: (p.get("position_group") or "", p.get("full_name") or ""))
        grouped.append(group)

    grouped.sort(key=lambda g: (team_order.get(g["abbr"], 999), g["name"]))

    return render_template(
        "players_index.html",
        grouped_players=grouped,
        player_count=len(players),
    )

@app.route("/player/<slug>")
def player_detail(slug):
    player = get_player_page_by_slug(slug) or get_player_by_slug(slug)
    if not player:
        abort(404)
    normalized_slug = str(slug or "").strip().lower()
    luck_gap_card = load_hitter_luck_gap_cards().get(normalized_slug)
    power_signal_card = load_hitter_power_signal_cards().get(normalized_slug)
    return render_template(
        "player_detail.html",
        player=player,
        hitter_card=player.get("hitter_card") if isinstance(player, dict) else None,
        pitcher_card=player.get("pitcher_card") if isinstance(player, dict) else None,
        luck_gap_card=luck_gap_card,
        power_signal_card=power_signal_card,
        page_title=f"{player.get('display_name') or player.get('full_name')} — Barrel Proof Player Ledger",
        meta_description=f"{player.get('display_name') or player.get('full_name')} player ledger — Barrel Proof Baseball.",
    )

@app.route("/leaderboards/luck-gap")
@app.route("/leaderboards/luck-gap/")
def luck_gap_leaderboard():
    cards = load_hitter_luck_gap_cards()
    players = [card for card in cards.values() if isinstance(card, dict)]
    players.sort(key=lambda card: (card.get("luck_gap_points") is None, -(card.get("luck_gap_points") or 0), card.get("full_name") or ""))
    positive_players = [card for card in players if isinstance(card.get("luck_gap_points"), (int, float)) and card.get("luck_gap_points") > 0]
    negative_players = sorted(
        [card for card in players if isinstance(card.get("luck_gap_points"), (int, float)) and card.get("luck_gap_points") < 0],
        key=lambda card: (card.get("luck_gap_points") or 0, card.get("full_name") or ""),
    )
    return render_template(
        "luck_gap_leaderboard.html",
        players=players,
        positive_players=positive_players,
        negative_players=negative_players,
        page_title="Luck Gap Leaderboard — Barrel Proof",
        meta_description="Barrel Proof Luck Gap leaderboard comparing xwOBA against calculated wOBA.",
    )

@app.route("/leaderboards/power-signal")
@app.route("/leaderboards/power-signal/")
def power_signal_leaderboard():
    cards = load_hitter_power_signal_cards()
    players = [card for card in cards.values() if isinstance(card, dict)]
    players.sort(key=lambda card: (card.get("power_signal") is None, -(card.get("power_signal") or 0), card.get("full_name") or ""))
    return render_template(
        "power_signal_leaderboard.html",
        players=players,
        page_title="Power Signal Leaderboard — Barrel Proof",
        meta_description="Barrel Proof Power Signal leaderboard showing hitter power supported by contact quality.",
    )

def build_team_context_note(team, record, form):
    """
    Build a deterministic one-sentence context note from available data.
    Returns empty string if insufficient data.
    """
    name   = team.get("nickname", team.get("name", ""))
    league = team.get("league", "")
    div    = ""
    parts  = []

    if record:
        w   = record.get("wins", "—")
        l   = record.get("losses", "—")
        pos = record.get("position", 0)
        gb  = record.get("games_back", "—")
        div = record.get("division", "")
        ordinals = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
        pos_word = ordinals.get(pos, f"{pos}th")

        if pos == 1:
            parts.append(f"The {name} lead the {league} {div} at {w}-{l}")
        else:
            gb_str = f", {gb} GB" if gb and gb not in ("—", "-") else ""
            parts.append(f"The {name} sit {pos_word} in the {league} {div} at {w}-{l}{gb_str}")

    if form:
        streak_type  = form.get("streak_type", "")
        streak_count = form.get("streak_count", 0)
        l10 = form.get("last_10_record", "")
        if streak_count >= 3:
            direction = "winning" if streak_type == "W" else "dropping"
            parts.append(f"currently on a {streak_count}-game {direction} streak")
        elif l10:
            parts.append(f"going {l10} over their last ten games")

    if not parts:
        return ""

    note = ", ".join(parts)
    return note[0].upper() + note[1:] + "."


def classify_pitchers(all_pitchers, abbr, lookahead_data):
    """
    Split a list of P-position players into starters and bullpen.

    Strategy:
      1. Cross-reference probable pitcher names from schedule_lookahead.
         Any pitcher whose name matches a upcoming probable starter → Rotation.
      2. If no lookahead matches (all TBD or no data), take the first 5
         pitchers in roster order as Rotation, rest as Bullpen.
      3. If 5 or fewer pitchers total, all go to Rotation.

    Returns (starters, bullpen) — two lists.
    """
    if not all_pitchers:
        return [], []

    if len(all_pitchers) <= 5:
        return all_pitchers, []

    # Build set of confirmed starter names from schedule lookahead
    probable_names = set()
    team_games = lookahead_data.get(abbr, {}).get("next_games", [])
    for game in team_games:
        name = game.get("prob_pitcher_team", "").strip()
        if name and name.upper() != "TBD":
            probable_names.add(name.lower())

    def is_probable_starter(player_name):
        pn = player_name.lower().strip()
        for sn in probable_names:
            if pn == sn:
                return True
            # Last-name fallback: avoids false negatives on name format diffs
            pn_last = pn.split()[-1] if pn.split() else ""
            sn_last = sn.split()[-1] if sn.split() else ""
            if len(pn_last) > 3 and pn_last == sn_last:
                return True
        return False

    if probable_names:
        starters = [p for p in all_pitchers if is_probable_starter(p["name"])]
        bullpen  = [p for p in all_pitchers if not is_probable_starter(p["name"])]
        # If schedule data returned fewer than 4 starters, backfill
        # from the front of the unmatched list to reach 5
        if len(starters) < 4:
            remaining = [p for p in all_pitchers if p not in starters]
            needed    = min(5 - len(starters), len(remaining))
            starters  = starters + remaining[:needed]
            bullpen   = remaining[needed:]
        return starters, bullpen

    # No lookahead data — heuristic fallback
    return all_pitchers[:5], all_pitchers[5:]


@app.route("/team/<team_slug>")
def team_detail(team_slug):
    team = get_team_by_slug(team_slug)
    if not team:
        abort(404)

    abbr = team.get("abbr")

    record          = get_team_record(abbr)
    recent_games    = get_team_recent_games(abbr)
    upcoming_games  = get_team_upcoming_games(abbr)

    # Team form (last 10)
    all_form = get_team_form()
    form     = all_form.get(abbr)

    # Schedule lookahead (next 5 games)
    all_lookahead = get_schedule_lookahead()
    lookahead     = all_lookahead.get(abbr, {}).get("next_games", [])

    # Team stats (batting + pitching)
    all_stats     = get_team_stats()
    team_batting  = all_stats.get(abbr, {}).get("batting", {})
    team_pitching = all_stats.get(abbr, {}).get("pitching", {})

    # Roster (grouped by role)
    full_name    = team.get("name", "")
    roster       = load_roster_md(full_name)
    # All pitchers use Pos="P" in the markdown files — no SP/RP distinction exists.
    # classify_pitchers() uses schedule_lookahead probable names to identify starters,
    # then falls back to a first-5 heuristic.
    all_pitchers = [p for p in roster if p.get("pos", "").upper() == "P"]
    lineup       = [p for p in roster if p.get("pos", "").upper() != "P"]
    starters, bullpen = classify_pitchers(all_pitchers, abbr, all_lookahead)

    # Injured list
    all_il  = get_team_il()
    team_il = all_il.get(abbr, [])

    # Context note
    context_note = build_team_context_note(team, record, form)

    # Recent game slugs for linking to scoreboard pages
    sc_data  = load_json("game_cards.json", fallback={})
    sc_date  = sc_data.get("date", "")

    def game_link(g):
        return build_game_slug(g.get("away_abbr", ""), g.get("home_abbr", ""), sc_date)

    return render_template(
        "team_detail.html",
        team=team,
        record=record,
        form=form,
        lookahead=lookahead,
        recent_games=recent_games,
        sc_date=sc_date,
        game_link=game_link,
        team_batting=team_batting,
        team_pitching=team_pitching,
        starters=starters,
        bullpen=bullpen,
        lineup=lineup,
        team_il=team_il,
        context_note=context_note,
        page_title=f"{team.get('name')} — Barrel Proof",
        meta_description=f"{team.get('name')} scores, schedule, standings and roster — Barrel Proof Baseball.",
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
