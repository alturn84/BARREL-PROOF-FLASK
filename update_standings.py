#!/usr/bin/env python3
"""
MLB Standings Updater — Barrel Proof
─────────────────────────────────────
Fetches current AL/NL standings from the free MLB Stats API and writes
them to Site Data/standings.json. The Flask app reads this file at
request time to render the left rail on the homepage.

Usage:
    python update_standings.py              # writes standings.json
    python update_standings.py --dry-run    # prints JSON, does not write

Schedule with cron (8 AM daily):
    0 8 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 "/Users/allanturner/BARREL PROOF/update_standings.py"
"""

import json
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

# ── Config ────────────────────────────────────────────────────────────────────
VAULT     = Path("/opt/data/workspace/barrel-proof")
OUT_FILE  = VAULT / "Site Data" / "standings.json"
BASE_URL  = "https://statsapi.mlb.com"
SEASON    = datetime.today().year

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept":     "application/json",
    "Origin":     "https://www.mlb.com",
    "Referer":    "https://www.mlb.com/",
}

# ── Team ID → clean display name ──────────────────────────────────────────────
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

# Division structure for ordered output
AL_DIVISIONS = [(201, "East"), (202, "Central"), (200, "West")]
NL_DIVISIONS = [(204, "East"), (205, "Central"), (203, "West")]

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


# ── Fetch ─────────────────────────────────────────────────────────────────────
def fetch_standings(season):
    data = get("/api/v1/standings", params={
        "leagueId":       "103,104",
        "season":         season,
        "standingsTypes": "regularSeason",
        "hydrate":        "team,division,league",
    })

    raw = {}
    for record in data.get("records", []):
        div_id = record["division"]["id"]
        teams  = []
        for tr in record.get("teamRecords", []):
            team_id = tr["team"]["id"]
            teams.append({
                "city": TEAM_NAMES.get(team_id, tr["team"].get("locationName", "")),
                "w":    tr.get("wins", 0),
                "l":    tr.get("losses", 0),
                "gb":   tr.get("gamesBack", "-"),
            })
        raw[div_id] = teams
    return raw


# ── Build structured output ───────────────────────────────────────────────────
def build_output(raw):
    """
    Produces a list of league objects ready for the Flask template:
    [
      {
        "league": "AL",
        "divisions": [
          { "name": "East", "teams": [ {"city":..,"w":..,"l":..,"gb":..}, ... ] },
          ...
        ]
      },
      { "league": "NL", ... }
    ]
    """
    def build_league(label, div_list):
        divisions = []
        for div_id, div_name in div_list:
            teams = raw.get(div_id, [])
            divisions.append({"name": div_name, "teams": teams})
        return {"league": label, "divisions": divisions}

    return {
        "updated":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "season":   SEASON,
        "leagues":  [
            build_league("AL", AL_DIVISIONS),
            build_league("NL", NL_DIVISIONS),
        ],
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    dry_run = "--dry-run" in sys.argv

    print(f"  Fetching {SEASON} standings...", flush=True)
    try:
        raw = fetch_standings(SEASON)
    except Exception as e:
        print(f"  ✗ API error: {e}", flush=True)
        sys.exit(1)

    output = build_output(raw)
    total  = sum(len(d["teams"]) for lg in output["leagues"] for d in lg["divisions"])
    print(f"  ✓ {total} teams across 6 divisions", flush=True)

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
