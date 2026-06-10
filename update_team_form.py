#!/usr/bin/env python3
"""
Team Form Updater — Barrel Proof
──────────────────────────────────
Writes Site Data/team_form.json with last-10 record, current streak,
and runs scored/allowed over last 10 games per team.

Sources:
  - MLB Stats API standings (streak, lastTen W-L)
  - MLB Stats API schedule (last 14 days, completed games, for runs)

Usage:
    python update_team_form.py
    python update_team_form.py --dry-run
"""

import json
import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

BASE_DIR = Path(__file__).resolve().parent
OUT_FILE = BASE_DIR / "Site Data" / "team_form.json"
BASE_URL = "https://statsapi.mlb.com"
SEASON   = datetime.today().year

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept":     "application/json",
    "Origin":     "https://www.mlb.com",
    "Referer":    "https://www.mlb.com/",
}

# Maps MLB team ID → teams.json abbr (canonical for this site)
MLB_ID_TO_ABBR = {
    108: "LAA", 109: "ARI", 110: "BAL", 111: "BOS",
    112: "CHC", 113: "CIN", 114: "CLE", 115: "COL",
    116: "DET", 117: "HOU", 118: "KC",  119: "LAD",
    120: "WSH", 121: "NYM", 133: "ATH", 134: "PIT",
    135: "SD",  136: "SEA", 137: "SF",  138: "STL",
    139: "TB",  140: "TEX", 141: "TOR", 142: "MIN",
    143: "PHI", 144: "ATL", 145: "CWS", 146: "MIA",
    147: "NYY", 158: "MIL",
}

# Maps teams.json abbr → slug (from teams.json)
ABBR_TO_SLUG = {
    "LAA": "los-angeles-angels", "ARI": "arizona-diamondbacks",
    "BAL": "baltimore-orioles",  "BOS": "boston-red-sox",
    "CHC": "chicago-cubs",       "CIN": "cincinnati-reds",
    "CLE": "cleveland-guardians","COL": "colorado-rockies",
    "DET": "detroit-tigers",     "HOU": "houston-astros",
    "KC":  "kansas-city-royals", "LAD": "los-angeles-dodgers",
    "WSH": "washington-nationals","NYM": "new-york-mets",
    "ATH": "oakland-athletics",  "PIT": "pittsburgh-pirates",
    "SD":  "san-diego-padres",   "SEA": "seattle-mariners",
    "SF":  "san-francisco-giants","STL":"st-louis-cardinals",
    "TB":  "tampa-bay-rays",     "TEX": "texas-rangers",
    "TOR": "toronto-blue-jays",  "MIN": "minnesota-twins",
    "PHI": "philadelphia-phillies","ATL":"atlanta-braves",
    "CWS": "chicago-white-sox",  "MIA": "miami-marlins",
    "NYY": "new-york-yankees",   "MIL": "milwaukee-brewers",
}

# MLB API abbreviations that differ from teams.json abbr
# Maps MLB-API-abbr → teams.json-abbr
API_ABBR_REMAP = {
    "AZ":  "ARI",
    "ATH": "ATH",
    "WSH": "WSH",
    "WAS": "WSH",
}


def get(endpoint, params=None):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params=params,
                             headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def fetch_standings_form():
    """Fetch streak and last-10 W-L from standings endpoint."""
    data = get("/api/v1/standings", params={
        "leagueId":       "103,104",
        "season":         SEASON,
        "standingsTypes": "regularSeason",
        "hydrate":        "team,division,league,streak,records",
    })
    result = {}
    for record in data.get("records", []):
        for tr in record.get("teamRecords", []):
            team_id = tr["team"]["id"]
            abbr = MLB_ID_TO_ABBR.get(team_id)
            if not abbr:
                continue
            # Streak: streakCode = "W3" or "L2"
            streak_code = tr.get("streak", {}).get("streakCode", "")
            streak_type  = streak_code[0] if streak_code else ""
            streak_count = int(streak_code[1:]) if len(streak_code) > 1 and streak_code[1:].isdigit() else 0
            # Last-10 record from splitRecords
            last10_w = last10_l = 0
            for split in tr.get("records", {}).get("splitRecords", []):
                if split.get("type") == "lastTen":
                    last10_w = split.get("wins", 0)
                    last10_l = split.get("losses", 0)
                    break
            result[abbr] = {
                "team_abbr":    abbr,
                "team_slug":    ABBR_TO_SLUG.get(abbr, ""),
                "last_10_wins": last10_w,
                "last_10_losses": last10_l,
                "last_10_record": f"{last10_w}-{last10_l}",
                "current_streak": streak_code,
                "streak_type":  streak_type,
                "streak_count": streak_count,
                # Runs fields added by fetch_game_runs() below
                "runs_scored_last_10":  None,
                "runs_allowed_last_10": None,
                "run_diff_last_10":     None,
            }
    return result


def fetch_game_runs(form_data):
    """
    Fetch completed games for last 14 days. For each team, take the last 10
    completed games and sum runs scored and allowed.
    """
    today     = datetime.today()
    start_str = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    end_str   = today.strftime("%Y-%m-%d")

    data = get("/api/v1/schedule", params={
        "sportId":   1,
        "startDate": start_str,
        "endDate":   end_str,
        "gameType":  "R",
        "hydrate":   "linescore,team",
    })

    # Per team: list of (runs_for, runs_against) from completed games, newest first
    team_games = {abbr: [] for abbr in form_data}

    for date_entry in reversed(data.get("dates", [])):   # newest first
        for g in date_entry.get("games", []):
            if g.get("status", {}).get("abstractGameState") != "Final":
                continue
            linescore = g.get("linescore", {})
            away_runs = linescore.get("teams", {}).get("away", {}).get("runs")
            home_runs = linescore.get("teams", {}).get("home", {}).get("runs")
            if away_runs is None or home_runs is None:
                continue

            away_id = g["teams"]["away"]["team"]["id"]
            home_id = g["teams"]["home"]["team"]["id"]
            away_abbr_raw = g["teams"]["away"]["team"].get("abbreviation", "")
            home_abbr_raw = g["teams"]["home"]["team"].get("abbreviation", "")

            away_abbr = MLB_ID_TO_ABBR.get(away_id) or API_ABBR_REMAP.get(away_abbr_raw, away_abbr_raw)
            home_abbr = MLB_ID_TO_ABBR.get(home_id) or API_ABBR_REMAP.get(home_abbr_raw, home_abbr_raw)

            if away_abbr in team_games and len(team_games[away_abbr]) < 10:
                team_games[away_abbr].append((int(away_runs), int(home_runs)))
            if home_abbr in team_games and len(team_games[home_abbr]) < 10:
                team_games[home_abbr].append((int(home_runs), int(away_runs)))

    for abbr, games in team_games.items():
        if games and abbr in form_data:
            rs = sum(g[0] for g in games)
            ra = sum(g[1] for g in games)
            form_data[abbr]["runs_scored_last_10"]  = rs
            form_data[abbr]["runs_allowed_last_10"] = ra
            form_data[abbr]["run_diff_last_10"]     = rs - ra

    return form_data


def main():
    dry_run = "--dry-run" in sys.argv

    print("  Fetching standings (streak + last-10)...", flush=True)
    form_data = fetch_standings_form()
    print(f"  ✓ {len(form_data)} teams", flush=True)

    print("  Fetching game results (last 14 days) for run totals...", flush=True)
    form_data = fetch_game_runs(form_data)

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "season":  SEASON,
        "teams":   form_data,
    }

    if dry_run:
        print(json.dumps(output, indent=2))
        print("  (dry run — file not written)")
    else:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  ✓ Written → {OUT_FILE}", flush=True)

    print(f"\n✓  Done. {datetime.now()}", flush=True)


if __name__ == "__main__":
    main()
