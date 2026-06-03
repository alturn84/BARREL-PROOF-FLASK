#!/usr/bin/env python3
"""
MLB Schedule Fetcher — Barrel Proof
─────────────────────────────────────
Fetches today's MLB schedule with probable pitchers and writes
Site Data/schedule.json for the homepage right rail.

The right rail shows TODAY'S games — what's on now or coming up.
The main body of the homepage shows YESTERDAY'S completed box scores.

Usage:
    python update_schedule.py               # writes schedule.json
    python update_schedule.py --dry-run     # prints JSON, does not write

Schedule with cron (7 AM daily):
    0 7 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 "update_schedule.py"
"""

import json
import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

# ── Config ────────────────────────────────────────────────────────────────────
VAULT    = Path(".")
OUT_FILE = VAULT / "Site Data" / "schedule.json"
BASE_URL = "https://statsapi.mlb.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept":     "application/json",
    "Origin":     "https://www.mlb.com",
    "Referer":    "https://www.mlb.com/",
}

# ── Team ID → clean display name (matches update_standings.py) ────────────────
TEAM_NAMES = {
    108: "Los Angeles",     # Angels
    109: "Arizona",
    110: "Baltimore",
    111: "Boston",
    112: "Chicago",         # Cubs
    113: "Cincinnati",
    114: "Cleveland",
    115: "Colorado",
    116: "Detroit",
    117: "Houston",
    118: "Kansas City",
    119: "Los Angeles",     # Dodgers
    120: "Washington",
    121: "New York",        # Mets
    133: "Athletics",
    134: "Pittsburgh",
    135: "San Diego",
    136: "Seattle",
    137: "San Francisco",
    138: "St. Louis",
    139: "Tampa Bay",
    140: "Texas",
    141: "Toronto",
    142: "Minnesota",
    143: "Philadelphia",
    144: "Atlanta",
    145: "Chicago",         # White Sox
    146: "Miami",
    147: "New York",        # Yankees
    158: "Milwaukee",
}

# ── HTTP helper ───────────────────────────────────────────────────────────────
def get(endpoint, params=None):
    for attempt in range(3):
        try:
            r = requests.get(
                f"{BASE_URL}{endpoint}",
                params=params,
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


# ── Fetch one date ────────────────────────────────────────────────────────────
def fetch_date(date_str):
    data = get("/api/v1/schedule", params={
        "sportId":  1,
        "date":     date_str,
        "gameType": "R,F,D,L,W",
        "hydrate":  "team,probablePitcher,linescore",
    })

    dates = data.get("dates", [])
    if not dates:
        return []

    games = []
    for g in dates[0].get("games", []):
        status    = g.get("status", {}).get("abstractGameState", "")
        away_team = g["teams"]["away"]["team"]
        home_team = g["teams"]["home"]["team"]
        away_prob = g["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD")
        home_prob = g["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD")

        # Use clean team name map
        away_id   = away_team.get("id")
        home_id   = home_team.get("id")
        away_city = TEAM_NAMES.get(away_id, away_team.get("locationName", away_team.get("name", "")))
        home_city = TEAM_NAMES.get(home_id, home_team.get("locationName", home_team.get("name", "")))

        # Convert UTC game time to ET
        game_time = g.get("gameDate", "")
        time_disp = "TBD"
        if game_time:
            try:
                utc_dt    = datetime.fromisoformat(game_time.replace("Z", "+00:00"))
                et_dt     = utc_dt - timedelta(hours=4)  # EDT
                time_disp = et_dt.strftime("%-I:%M %p ET")
            except Exception:
                pass

        games.append({
            "away":      away_city,
            "home":      home_city,
            "away_abbr": away_team.get("abbreviation", ""),
            "home_abbr": home_team.get("abbreviation", ""),
            "away_prob": away_prob,
            "home_prob": home_prob,
            "time":      time_disp,
            "status":    status,
            "game_pk":   g.get("gamePk"),
        })

    games.sort(key=lambda x: x.get("time", ""))
    return games


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    dry_run   = "--dry-run" in sys.argv
    today     = datetime.today()
    yesterday = today - timedelta(days=1)

    today_str = today.strftime("%Y-%m-%d")

    print(f"  Fetching today's schedule ({today_str})...", flush=True)

    try:
        today_games = fetch_date(today_str)
    except Exception as e:
        print(f"  ✗ API error: {e}", flush=True)
        sys.exit(1)

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rail_date":  today.strftime("%A, %B %-d"),
        "games_date": yesterday.strftime("%Y-%m-%d"),
        "games_date_full": yesterday.strftime("%A, %B %-d, %Y"),
        "today": {
            "date":  today.strftime("%Y-%m-%d"),
            "games": today_games,
        },
    }

    print(f"  ✓ Today: {len(today_games)} games", flush=True)

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
