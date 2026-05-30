#!/usr/bin/env python3
"""
MLB Active Roster Updater — Barrel Proof Vault
────────────────────────────────────────────────
Pulls current 26-man active rosters from the MLB Stats API
and saves them as Obsidian markdown files, organized by league/division.

Usage:
    python update_rosters.py           # update all 30 teams
    python update_rosters.py NYY       # update one team by abbreviation

Schedule with cron (9:10 AM daily):
    10 9 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 "/Users/allanturner/BARREL PROOF/update_rosters.py" >> "/Users/allanturner/BARREL PROOF/roster.log" 2>&1
"""

import requests
import sys
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

VAULT      = Path("/Users/allanturner/BARREL PROOF")
OUTPUT_DIR = VAULT / "Rosters"
BASE_URL   = "https://statsapi.mlb.com"
SEASON     = datetime.today().year

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.mlb.com",
    "Referer": "https://www.mlb.com/",
}

# Position sort order — position players first, pitchers last
POS_ORDER = {
    "C": 1, "1B": 2, "2B": 3, "3B": 4, "SS": 5,
    "LF": 6, "CF": 7, "RF": 8, "OF": 9, "DH": 10,
    "P": 11,
}

def get(endpoint, params=None):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2: raise
            time.sleep(2 ** attempt)


# ── Fetch all 30 MLB teams with league/division info ──────────────────────────
def get_teams():
    data  = get("/api/v1/teams", params={"sportId": 1, "season": SEASON})
    teams = {}
    for team in data.get("teams", []):
        league   = team.get("league",   {}).get("name", "")
        division = team.get("division", {}).get("name", "")
        if not league or not division:
            continue
        teams[team["id"]] = {
            "name":         team["name"],
            "abbreviation": team.get("abbreviation", ""),
            "league":       league,
            "division":     division,
        }
    return teams


# ── Fetch active roster for one team ─────────────────────────────────────────
def get_roster(team_id):
    data = get(f"/api/v1/teams/{team_id}/roster/active", params={
        "season":  SEASON,
        "hydrate": "person",
    })
    return data.get("roster", [])


# ── Build markdown for one team ───────────────────────────────────────────────
def team_markdown(team_info, roster):
    name     = team_info["name"]
    league   = team_info["league"]
    division = team_info["division"]
    updated  = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    def sort_key(p):
        pos = p.get("person", {}).get("primaryPosition", {}).get("abbreviation", "")
        num = p.get("jerseyNumber", "99")
        try:   num = int(num)
        except: num = 99
        return (POS_ORDER.get(pos, 10), num)

    roster_sorted = sorted(roster, key=sort_key)

    rows = []
    for p in roster_sorted:
        person = p.get("person", {})
        num    = p.get("jerseyNumber", "—")
        pname  = person.get("fullName", "—")
        pos    = person.get("primaryPosition", {}).get("abbreviation", "—")
        bats   = person.get("batSide",   {}).get("code", "—")
        throws = person.get("pitchHand", {}).get("code", "—")
        age    = person.get("currentAge", "—")
        height = person.get("height", "—")
        weight = person.get("weight", "—")
        if weight and weight != "—":
            weight = f"{weight} lbs"
        rows.append(f"| #{num} | {pname} | {pos} | {bats} | {throws} | {age} | {height} | {weight} |")

    table = (
        "| # | Name | Pos | Bats | Throws | Age | Height | Weight |\n"
        "|---|------|-----|------|--------|-----|--------|--------|\n"
        + "\n".join(rows)
    )

    return f"""---
team: {name}
league: {league}
division: {division}
updated: {updated}
tags: [baseball, mlb, roster]
---

# {name} — Active Roster

**League:** {league}  ·  **Division:** {division}
*Last updated: {updated}*

{table}
"""


# ── Update one team ───────────────────────────────────────────────────────────
def update_team(team_id, team_info):
    try:
        roster   = get_roster(team_id)
        md       = team_markdown(team_info, roster)
        out_dir  = OUTPUT_DIR / team_info["league"] / team_info["division"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{team_info['name']}.md"
        out_path.write_text(md, encoding="utf-8")
        return team_info["name"], len(roster), None
    except Exception as e:
        return team_info["name"], 0, str(e)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    filter_abbr = sys.argv[1].upper() if len(sys.argv) > 1 else None

    print("Fetching team list...", flush=True)
    teams = get_teams()

    if filter_abbr:
        teams = {tid: t for tid, t in teams.items() if t["abbreviation"] == filter_abbr}
        if not teams:
            print(f"No team found with abbreviation: {filter_abbr}")
            sys.exit(1)

    print(f"Updating rosters for {len(teams)} team(s)...", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(update_team, tid, tinfo): tinfo for tid, tinfo in teams.items()}
        for f in as_completed(futs):
            results.append(f.result())

    results.sort(key=lambda x: x[0])
    errors = []
    for name, count, err in results:
        if err:
            print(f"  ✗ {name}: {err}")
            errors.append((name, err))
        else:
            print(f"  ✓ {name}: {count} players")

    print(f"\n✓ Done. {len(results) - len(errors)}/{len(results)} teams updated.")
    print(f"  Files saved → {OUTPUT_DIR}")
    if errors:
        print(f"\n⚠ {len(errors)} team(s) had errors:")
        for name, err in errors:
            print(f"  {name}: {err}")

if __name__ == "__main__":
    main()
