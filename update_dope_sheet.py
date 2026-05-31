#!/usr/bin/env python3
"""
Barrel Proof — Dope Sheet Daily Updater
"""

import json
import sys
import requests
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent
DATA_DIR  = BASE_DIR / "Site Data"
OUT_FILE  = DATA_DIR / "dope-sheet-data.json"
MLB_BASE  = "https://statsapi.mlb.com/api/v1"

TEAM_ABB = {
    "Arizona Diamondbacks":  "AZ",  "Atlanta Braves":        "ATL",
    "Baltimore Orioles":     "BAL", "Boston Red Sox":        "BOS",
    "Chicago Cubs":          "CHC", "Chicago White Sox":     "CWS",
    "Cincinnati Reds":       "CIN", "Cleveland Guardians":   "CLE",
    "Colorado Rockies":      "COL", "Detroit Tigers":        "DET",
    "Houston Astros":        "HOU", "Kansas City Royals":    "KC",
    "Los Angeles Angels":    "LAA", "Los Angeles Dodgers":   "LAD",
    "Miami Marlins":         "MIA", "Milwaukee Brewers":     "MIL",
    "Minnesota Twins":       "MIN", "New York Mets":         "NYM",
    "New York Yankees":      "NYY", "Oakland Athletics":     "ATH",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates":    "PIT",
    "San Diego Padres":      "SD",  "San Francisco Giants":  "SF",
    "Seattle Mariners":      "SEA", "St. Louis Cardinals":   "STL",
    "Tampa Bay Rays":        "TB",  "Texas Rangers":         "TEX",
    "Toronto Blue Jays":     "TOR", "Washington Nationals":  "WSH",
}

DOME_PARKS = {
    "American Family Field", "Rogers Centre", "Tropicana Field",
    "loanDepot park", "Minute Maid Park", "Globe Life Field",
    "Chase Field", "T-Mobile Park",
}

def fetch(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def get_lineup_players(game, side):
    key = "awayPlayers" if side == "away" else "homePlayers"
    players = game.get("lineups", {}).get(key, [])

    return [
        {
            "name": p.get("fullName", ""),
            "pos": p.get("primaryPosition", {}).get("abbreviation", "")
        }
        for p in players
    ]

def get_probable_pitcher(game, side):
    try:
        pid = game.get("teams", {}).get(side, {}).get("probablePitcher", {}).get("id")
        if not pid:
            return empty_pitcher()

        data = fetch(f"{MLB_BASE}/people/{pid}?hydrate=stats(group=pitching,type=season)")
        p = data["people"][0]
        name = p.get("fullName", "TBD")
        hand = p.get("pitchHand", {}).get("code", "R")

        stats = {}
        for sg in p.get("stats", []):
            if sg.get("type", {}).get("displayName") == "season":
                stats = sg.get("splits", [{}])[0].get("stat", {})
                break

        return {
            "name": name,
            "hand": hand,
            "era": stats.get("era", "—"),
            "whip": stats.get("whip", "—"),
            "k9": stats.get("strikeoutsPer9Inn", "—"),
            "bb9": stats.get("walksPer9Inn", "—"),
            "ip": stats.get("inningsPitched", "—"),
            "lastStart": "—",
        }

    except Exception as e:
        print(f"  ⚠ Pitcher fetch error: {e}")
        return empty_pitcher()

def empty_pitcher():
    return {
        "name": "TBD",
        "hand": "R",
        "era": "—",
        "whip": "—",
        "k9": "—",
        "bb9": "—",
        "ip": "—",
        "lastStart": "—",
    }

def build_game(game):
    away_name = game["teams"]["away"]["team"]["name"]
    home_name = game["teams"]["home"]["team"]["name"]
    venue = game.get("venue", {}).get("name", "—")
    game_time = game.get("gameDate", "")

    try:
        dt = datetime.fromisoformat(game_time.replace("Z", "+00:00"))
        et_offset = -4
        et_hour = (dt.hour + et_offset) % 24
        ampm = "AM" if et_hour < 12 else "PM"
        disp_hour = et_hour if et_hour <= 12 else et_hour - 12
        if disp_hour == 0:
            disp_hour = 12
        time_str = f"{disp_hour}:{dt.minute:02d} {ampm} ET"
    except Exception:
        time_str = "TBD"

    roof = "Closed" if venue in DOME_PARKS else "Open"

    print(f"  Fetching pitchers for {away_name} @ {home_name}...")
    away_p = get_probable_pitcher(game, "away")
    home_p = get_probable_pitcher(game, "home")

    away_lineup = get_lineup_players(game, "away")
    home_lineup = get_lineup_players(game, "home")

    return {
        "away": TEAM_ABB.get(away_name, away_name[:3].upper()),
        "home": TEAM_ABB.get(home_name, home_name[:3].upper()),
        "awayFull": away_name,
        "homeFull": home_name,
        "time": time_str,
        "venue": venue,
        "roof": roof,
        "pitchers": {
            "away": away_p,
            "home": home_p,
        },
        "weather": {
            "temp": "—",
            "sky": "—",
            "wind": "—",
            "humidity": "—",
            "precip": "—",
            "roof": roof,
        },
        "umpire": {
            "name": "TBD",
            "calledKpct": "—",
            "rpg": "—",
            "note": "—",
        },
        "lineups": {
            "away": away_lineup,
            "home": home_lineup,
        },
        "bullpen": {
            "away": [],
            "home": [],
        },
        "injuries": {
            "away": [],
            "home": [],
        },
        "props": {
            "note": "",
            "pitchers": [],
            "batters": [],
        },
    }

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    print(f"\n🗓  Fetching MLB schedule for {date_str}...")

    sched = fetch(
        f"{MLB_BASE}/schedule?sportId=1&date={date_str}&hydrate=lineups,probablePitcher,teams,venue"
    )

    dates = sched.get("dates", [])
    if not dates:
        print("  ✗ No games found.")
        return

    raw_games = dates[0].get("games", [])
    print(f"  ✓ {len(raw_games)} games found\n")

    games = [g for g in raw_games if g.get("gameType") in ("R", "F", "D", "L", "W")]

    built = []
    for i, g in enumerate(games, 1):
        print(f"  [{i}/{len(games)}] Building game data...")
        built.append(build_game(g))

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        display = dt.strftime("%A, %B %-d, %Y")
        banner = dt.strftime("%B %-d, %Y").upper()
    except Exception:
        display = date_str
        banner = date_str.upper()

    output = {
        "date_display": display,
        "date_banner": banner,
        "updated": datetime.now(timezone.utc).isoformat(),
        "games": built,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lineup_count = sum(
        len(g.get("lineups", {}).get("away", [])) + len(g.get("lineups", {}).get("home", []))
        for g in built
    )

    print(f"\n✅  dope-sheet-data.json written → {OUT_FILE}")
    print(f"    {len(built)} games · {display}")
    print(f"    {lineup_count} lineup players found")

    print("\n📋  Still needed manually or by future scripts:")
    print("    • Weather per park")
    print("    • Umpire assignments")
    print("    • Bullpen availability")
    print("    • Player props")

if __name__ == "__main__":
    main()