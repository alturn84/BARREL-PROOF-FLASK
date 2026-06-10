#!/usr/bin/env python3
"""
Schedule Lookahead — Barrel Proof
───────────────────────────────────
Writes Site Data/schedule_lookahead.json with the next 5 games per team,
including opponent, date/time, home/away, probable pitchers, and venue.

Source: MLB Stats API schedule endpoint (7-day window)

Usage:
    python update_schedule_lookahead.py
    python update_schedule_lookahead.py --dry-run
"""

import json
import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

BASE_DIR = Path(__file__).resolve().parent
OUT_FILE = BASE_DIR / "Site Data" / "schedule_lookahead.json"
BASE_URL = "https://statsapi.mlb.com"
SEASON   = datetime.today().year

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept":     "application/json",
    "Origin":     "https://www.mlb.com",
    "Referer":    "https://www.mlb.com/",
}

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

MLB_ID_TO_CITY = {
    108: "Los Angeles",   109: "Arizona",      110: "Baltimore",
    111: "Boston",        112: "Chicago",       113: "Cincinnati",
    114: "Cleveland",     115: "Colorado",      116: "Detroit",
    117: "Houston",       118: "Kansas City",   119: "Los Angeles",
    120: "Washington",    121: "New York",       133: "Athletics",
    134: "Pittsburgh",    135: "San Diego",     136: "Seattle",
    137: "San Francisco", 138: "St. Louis",     139: "Tampa Bay",
    140: "Texas",         141: "Toronto",       142: "Minnesota",
    143: "Philadelphia",  144: "Atlanta",       145: "Chicago",
    146: "Miami",         147: "New York",      158: "Milwaukee",
}

API_ABBR_REMAP = {"AZ": "ARI", "WAS": "WSH"}


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


def main():
    dry_run   = "--dry-run" in sys.argv
    today     = datetime.today()
    end_date  = today + timedelta(days=7)
    start_str = today.strftime("%Y-%m-%d")
    end_str   = end_date.strftime("%Y-%m-%d")

    print(f"  Fetching schedule {start_str} → {end_str}...", flush=True)
    data = get("/api/v1/schedule", params={
        "sportId":   1,
        "startDate": start_str,
        "endDate":   end_str,
        "gameType":  "R",
        "hydrate":   "team,probablePitcher,venue",
    })

    # Per-team: list of next games (up to 5), in date order
    teams_games = {abbr: [] for abbr in MLB_ID_TO_ABBR.values()}

    for date_entry in data.get("dates", []):
        date_str = date_entry.get("date", "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_display = dt.strftime("%a, %b %-d")
        except Exception:
            date_display = date_str

        for g in date_entry.get("games", []):
            status = g.get("status", {}).get("abstractGameState", "")
            # Skip already-final games (if today has finished games)
            if status == "Final":
                continue

            away_team = g["teams"]["away"]["team"]
            home_team = g["teams"]["home"]["team"]
            away_id = away_team.get("id")
            home_id = home_team.get("id")

            away_abbr = MLB_ID_TO_ABBR.get(away_id)
            home_abbr = MLB_ID_TO_ABBR.get(home_id)
            if not away_abbr or not home_abbr:
                continue

            away_city = MLB_ID_TO_CITY.get(away_id, away_team.get("locationName", ""))
            home_city = MLB_ID_TO_CITY.get(home_id, home_team.get("locationName", ""))

            away_prob = g["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD")
            home_prob = g["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD")
            venue     = g.get("venue", {}).get("name", "")

            game_time_utc = g.get("gameDate", "")
            time_disp = "TBD"
            if game_time_utc:
                try:
                    utc_dt    = datetime.fromisoformat(game_time_utc.replace("Z", "+00:00"))
                    et_dt     = utc_dt - timedelta(hours=4)
                    time_disp = et_dt.strftime("%-I:%M %p ET")
                except Exception:
                    pass

            game_entry_away = {
                "date":                  date_str,
                "date_display":          date_display,
                "opponent_abbr":         home_abbr,
                "opponent_city":         home_city,
                "home_away":             "away",
                "game_time":             time_disp,
                "prob_pitcher_team":     away_prob,
                "prob_pitcher_opponent": home_prob,
                "venue":                 venue,
            }
            game_entry_home = {
                "date":                  date_str,
                "date_display":          date_display,
                "opponent_abbr":         away_abbr,
                "opponent_city":         away_city,
                "home_away":             "home",
                "game_time":             time_disp,
                "prob_pitcher_team":     home_prob,
                "prob_pitcher_opponent": away_prob,
                "venue":                 venue,
            }

            if len(teams_games.get(away_abbr, [])) < 5:
                teams_games.setdefault(away_abbr, []).append(game_entry_away)
            if len(teams_games.get(home_abbr, [])) < 5:
                teams_games.setdefault(home_abbr, []).append(game_entry_home)

    # Wrap into team dict keyed by abbr
    output_teams = {}
    for abbr, games in teams_games.items():
        output_teams[abbr] = {
            "team_abbr": abbr,
            "next_games": games,
        }

    output = {
        "updated":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "from_date": start_str,
        "thru_date": end_str,
        "teams":     output_teams,
    }

    total_games = sum(len(v["next_games"]) for v in output_teams.values())
    print(f"  ✓ {total_games} upcoming game slots across {len(output_teams)} teams", flush=True)

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
