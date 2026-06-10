#!/usr/bin/env python3
"""
Team Stats Updater — Barrel Proof
───────────────────────────────────
Fetches season-level team batting and pitching aggregates from the
MLB Stats API and writes Site Data/team_stats.json.

Fields per team:
  batting:  avg, obp, slg, ops, runs_per_game, home_runs
  pitching: era, whip, k9, bb9

Usage:
    python update_team_stats.py
    python update_team_stats.py --dry-run
"""

import json
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

BASE_DIR = Path(__file__).resolve().parent
OUT_FILE = BASE_DIR / "Site Data" / "team_stats.json"
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


def fmt_rate(val, decimals=3):
    """Format a rate stat (avg, era, etc.) to a clean string."""
    if val is None:
        return None
    try:
        f = float(val)
        if decimals == 3:
            s = f"{f:.3f}"
            # Remove leading zero for avg/obp/slg/ops: .273 not 0.273
            return s.lstrip("0") if s.startswith("0.") else s
        else:
            return f"{f:.2f}"
    except (ValueError, TypeError):
        return str(val)


def fetch_batting():
    data = get("/api/v1/teams/stats", params={
        "stats":   "season",
        "group":   "hitting",
        "season":  SEASON,
        "sportId": 1,
    })
    result = {}
    for stat_obj in data.get("stats", []):
        for split in stat_obj.get("splits", []):
            team    = split.get("team", {})
            team_id = team.get("id")
            abbr    = MLB_ID_TO_ABBR.get(team_id)
            if not abbr:
                continue
            s = split.get("stat", {})
            gp = int(s.get("gamesPlayed", 1) or 1)
            runs = int(s.get("runs", 0) or 0)
            result[abbr] = {
                "avg":           fmt_rate(s.get("avg"), 3),
                "obp":           fmt_rate(s.get("obp"), 3),
                "slg":           fmt_rate(s.get("slg"), 3),
                "ops":           fmt_rate(s.get("ops"), 3),
                "home_runs":     int(s.get("homeRuns", 0) or 0),
                "runs_per_game": round(runs / gp, 2) if gp > 0 else None,
            }
    return result


def fetch_pitching():
    data = get("/api/v1/teams/stats", params={
        "stats":   "season",
        "group":   "pitching",
        "season":  SEASON,
        "sportId": 1,
    })
    result = {}
    for stat_obj in data.get("stats", []):
        for split in stat_obj.get("splits", []):
            team    = split.get("team", {})
            team_id = team.get("id")
            abbr    = MLB_ID_TO_ABBR.get(team_id)
            if not abbr:
                continue
            s = split.get("stat", {})
            result[abbr] = {
                "era":  fmt_rate(s.get("era"), 2),
                "whip": fmt_rate(s.get("whip"), 3),
                "k9":   fmt_rate(s.get("strikeoutsPer9Inn"), 2),
                "bb9":  fmt_rate(s.get("walksPer9Inn"), 2),
            }
    return result


def main():
    dry_run = "--dry-run" in sys.argv

    print("  Fetching team batting stats...", flush=True)
    batting = fetch_batting()
    print(f"  ✓ {len(batting)} teams", flush=True)

    print("  Fetching team pitching stats...", flush=True)
    pitching = fetch_pitching()
    print(f"  ✓ {len(pitching)} teams", flush=True)

    # Merge batting + pitching per team
    all_abbrs = set(list(batting.keys()) + list(pitching.keys()))
    teams_out = {}
    for abbr in sorted(all_abbrs):
        teams_out[abbr] = {
            "batting":  batting.get(abbr, {}),
            "pitching": pitching.get(abbr, {}),
        }

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "season":  SEASON,
        "teams":   teams_out,
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
