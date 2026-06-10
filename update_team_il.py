#!/usr/bin/env python3
"""
Team Injured List Updater — Barrel Proof
─────────────────────────────────────────
Fetches the 40-man roster for all 30 teams from the MLB Stats API
and writes Site Data/team_il.json containing only players whose
roster status is not "Active" (IL, bereavement list, etc.).

The 40-man roster is the only MLB Stats API endpoint that reliably
includes IL players with their status codes. Injury reasons and
dates placed are not available from this endpoint and are not included.

Usage:
    python update_team_il.py
    python update_team_il.py --dry-run

Morning pipeline: run at 8:25 AM ET (after standings, before team_form)
"""

import json
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

BASE_DIR = Path(__file__).resolve().parent
OUT_FILE = BASE_DIR / "Site Data" / "team_il.json"
BASE_URL = "https://statsapi.mlb.com"
SEASON   = datetime.today().year

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept":     "application/json",
    "Origin":     "https://www.mlb.com",
    "Referer":    "https://www.mlb.com/",
}

# MLB team ID → teams.json abbr
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

# Status codes that indicate unavailability
IL_STATUS_CODES = {"D10", "D15", "D60", "BRV", "SUSP", "RST"}

# Human-readable labels for status codes
STATUS_LABELS = {
    "D10":  "10-Day IL",
    "D15":  "15-Day IL",
    "D60":  "60-Day IL",
    "BRV":  "Bereavement List",
    "SUSP": "Suspended",
    "RST":  "Restricted List",
}


def get(endpoint, params=None):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params=params,
                             headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def fetch_team_il(team_id):
    """Fetch 40-man roster for one team, return IL players only."""
    data = get(f"/api/v1/teams/{team_id}/roster", params={
        "rosterType": "40Man",
        "season":     SEASON,
    })
    il_players = []
    for entry in data.get("roster", []):
        status_code = entry.get("status", {}).get("code", "A")
        if status_code == "A" or not status_code:
            continue
        if status_code not in IL_STATUS_CODES:
            # Include any non-active status we haven't explicitly listed
            # but skip DFA, option, etc. that aren't injury-related
            if status_code in {"DFA", "OPT", "MIN", "NRI", "RM"}:
                continue
        name     = entry.get("person", {}).get("fullName", "")
        pos      = entry.get("position", {}).get("abbreviation", "")
        status_label = STATUS_LABELS.get(
            status_code,
            entry.get("status", {}).get("description", status_code)
        )
        if name:
            il_players.append({
                "name":         name,
                "position":     pos,
                "status_code":  status_code,
                "status":       status_label,
            })
    return il_players


def main():
    dry_run = "--dry-run" in sys.argv
    teams_out = {}
    total_il  = 0
    errors    = 0

    for team_id, abbr in sorted(MLB_ID_TO_ABBR.items(), key=lambda x: x[1]):
        try:
            il = fetch_team_il(team_id)
            teams_out[abbr] = il
            total_il += len(il)
            if il:
                print(f"  {abbr}: {len(il)} IL player(s)", flush=True)
            time.sleep(0.1)  # courteous pacing
        except Exception as e:
            print(f"  ✗ {abbr} (id={team_id}): {e}", flush=True)
            teams_out[abbr] = []
            errors += 1

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "season":  SEASON,
        "teams":   teams_out,
    }

    print(f"\n  ✓ {total_il} IL players across {len(teams_out)} teams", flush=True)
    if errors:
        print(f"  ⚠ {errors} team(s) failed", flush=True)

    if dry_run:
        print(json.dumps(output, indent=2))
        print("  (dry run — file not written)")
    else:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUT_FILE.write_text(
            json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  ✓ Written → {OUT_FILE}", flush=True)

    print(f"\n✓  Done. {datetime.now()}", flush=True)


if __name__ == "__main__":
    main()
