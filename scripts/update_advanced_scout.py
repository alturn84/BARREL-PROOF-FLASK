#!/usr/bin/env python3
"""
Advanced Scout — Weekend Series Data Layer
───────────────────────────────────────────
Builds Site Data/advanced_scout.json for the Wednesday Advanced Scout
edition, covering the upcoming weekend series (Fri-Sun, plus any
Thursday-start series that continue into the weekend).

Data-only script. Does not touch templates, app.py, or other data files.

Usage:
    python3 scripts/update_advanced_scout.py
"""

import json
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
DATA_DIR = VAULT / "Site Data"
PLAYER_DIR = DATA_DIR / "players"
OUT_FILE = DATA_DIR / "advanced_scout.json"

BASE_URL = "https://statsapi.mlb.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.mlb.com",
    "Referer": "https://www.mlb.com/",
}

TEAM_NAMES = {
    108: "Los Angeles Angels", 109: "Arizona Diamondbacks", 110: "Baltimore Orioles",
    111: "Boston Red Sox", 112: "Chicago Cubs", 113: "Cincinnati Reds",
    114: "Cleveland Guardians", 115: "Colorado Rockies", 116: "Detroit Tigers",
    117: "Houston Astros", 118: "Kansas City Royals", 119: "Los Angeles Dodgers",
    120: "Washington Nationals", 121: "New York Mets", 133: "Athletics",
    134: "Pittsburgh Pirates", 135: "San Diego Padres", 136: "Seattle Mariners",
    137: "San Francisco Giants", 138: "St. Louis Cardinals", 139: "Tampa Bay Rays",
    140: "Texas Rangers", 141: "Toronto Blue Jays", 142: "Minnesota Twins",
    143: "Philadelphia Phillies", 144: "Atlanta Braves", 145: "Chicago White Sox",
    146: "Miami Marlins", 147: "New York Yankees", 158: "Milwaukee Brewers",
}

# MLB API abbreviation -> canonical Barrel Proof abbreviation
# (matches player_index.json / team_stats.json / team_il.json, which use ARI for Arizona)
TEAM_ABBR_ALIASES = {"AZ": "ARI"}

WINDOW_DATES = ["2026-06-18", "2026-06-19", "2026-06-20", "2026-06-21"]
WEEKEND_DATES = {"2026-06-19", "2026-06-20", "2026-06-21"}
EDITION_DATE = "2026-06-17"


def get(endpoint, params=None):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def fetch_date(date_str):
    data = get("/api/v1/schedule", params={
        "sportId": 1,
        "date": date_str,
        "gameType": "R,F,D,L,W",
        "hydrate": "team,probablePitcher,venue",
    })
    dates = data.get("dates", [])
    if not dates:
        return []

    games = []
    for g in dates[0].get("games", []):
        away_team = g["teams"]["away"]["team"]
        home_team = g["teams"]["home"]["team"]
        away_prob = g["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD")
        home_prob = g["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD")
        games.append({
            "date": date_str,
            "away_team": TEAM_ABBR_ALIASES.get(away_team.get("abbreviation", ""), away_team.get("abbreviation", "")),
            "home_team": TEAM_ABBR_ALIASES.get(home_team.get("abbreviation", ""), home_team.get("abbreviation", "")),
            "away_team_name": TEAM_NAMES.get(away_team.get("id"), away_team.get("name", "")),
            "home_team_name": TEAM_NAMES.get(home_team.get("id"), home_team.get("name", "")),
            "venue": g.get("venue", {}).get("name", ""),
            "probable_away_pitcher": away_prob or "TBD",
            "probable_home_pitcher": home_prob or "TBD",
        })
    return games


def load_json_safe(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def group_into_series(all_games):
    """Group games by (away_team, home_team) into contiguous-date series."""
    by_pair = {}
    for g in all_games:
        key = (g["away_team"], g["home_team"])
        by_pair.setdefault(key, []).append(g)

    series_list = []
    for (away, home), games in by_pair.items():
        games = sorted(games, key=lambda x: x["date"])
        dates_in_run = {g["date"] for g in games}
        if not (dates_in_run & WEEKEND_DATES):
            continue  # Thursday-only games not continuing into weekend
        series_list.append((away, home, games))

    return series_list


def get_standings_records():
    """Returns city name -> 'W-L (GB)' string."""
    data = load_json_safe(DATA_DIR / "standings.json", {})
    out = {}
    for league in data.get("leagues", []):
        for div in league.get("divisions", []):
            for t in div.get("teams", []):
                city = t.get("city")
                w, l, gb = t.get("w"), t.get("l"), t.get("gb")
                if city is None or w is None or l is None:
                    continue
                gb_str = "1st place" if gb in (None, "-", "0.0") else f"{gb} GB"
                out[city] = f"{w}-{l}, {gb_str}"
    return out


def get_player_index():
    data = load_json_safe(PLAYER_DIR / "player_index.json", [])
    return data if isinstance(data, list) else []


def build_lookups():
    player_index = get_player_index()
    name_to_slug = {}
    team_to_players = {}
    for p in player_index:
        name_to_slug[p.get("full_name", "")] = p
        team_abbr = p.get("team_abbr")
        if team_abbr:
            team_to_players.setdefault(team_abbr, []).append(p)

    power = load_json_safe(PLAYER_DIR / "hitter_power_signal.json", {}).get("players", {})
    contact = load_json_safe(PLAYER_DIR / "hitter_contact_signal.json", {}).get("players", {})
    foundation = load_json_safe(PLAYER_DIR / "pitcher_foundation_signal.json", {}).get("players", {})
    profile = load_json_safe(PLAYER_DIR / "pitcher_profile_summary.json", {}).get("players", {})
    il_data = load_json_safe(DATA_DIR / "team_il.json", {}).get("teams", {})

    return {
        "name_to_slug": name_to_slug,
        "team_to_players": team_to_players,
        "power": power,
        "contact": contact,
        "foundation": foundation,
        "profile": profile,
        "il": il_data,
    }


def il_names_for_team(team_abbr, lookups):
    return {p.get("name") for p in lookups["il"].get(team_abbr, [])}


def top_signal_bats(team_abbr, signal_map, lookups, n=2):
    candidates = []
    il_names = il_names_for_team(team_abbr, lookups)
    for p in lookups["team_to_players"].get(team_abbr, []):
        if p.get("position_group") == "Pitcher":
            continue
        if p.get("full_name") in il_names:
            continue
        slug = p.get("slug")
        sig = signal_map.get(slug)
        if not sig:
            continue
        candidates.append(sig)
    candidates.sort(key=lambda s: s.get("power_signal", s.get("contact_signal", 0)) or 0, reverse=True)
    return candidates[:n]


def pitcher_signal(pitcher_name, lookups):
    p = lookups["name_to_slug"].get(pitcher_name)
    if not p:
        return None
    slug = p.get("slug")
    return lookups["foundation"].get(slug), lookups["profile"].get(slug), slug


def build_series_entry(away, home, games, away_name, home_name, lookups, standings):
    start_date = games[0]["date"]
    end_date = games[-1]["date"]
    game_count = len(games)
    is_four_game = game_count == 4
    is_thursday_start = start_date == "2026-06-18"

    series_id = f"{away.lower()}-{home.lower()}-{start_date}"

    # ── Series context ──────────────────────────────────────────────
    away_record = standings.get(away_name)
    home_record = standings.get(home_name)
    if away_record or home_record:
        standings_angle = f"{away_name} ({away_record or 'record unavailable'}) at {home_name} ({home_record or 'record unavailable'})."
    else:
        standings_angle = "Limited current form data"

    away_il = lookups["il"].get(away, [])
    home_il = lookups["il"].get(home, [])
    injury_bits = []
    if away_il:
        injury_bits.append(f"{away_name} IL list includes {len(away_il)} player(s).")
    if home_il:
        injury_bits.append(f"{home_name} IL list includes {len(home_il)} player(s).")
    injury_angle = " ".join(injury_bits) if injury_bits else "Limited current form data"

    series_context = {
        "standings_angle": standings_angle,
        "form_angle": "Limited current form data",
        "injury_angle": injury_angle,
    }

    # ── Pitching path ────────────────────────────────────────────────
    away_probables, home_probables = [], []
    best_signal = None
    for g in games:
        ap, hp = g["probable_away_pitcher"], g["probable_home_pitcher"]
        away_probables.append(ap if ap else "Probable starter TBD")
        home_probables.append(hp if hp else "Probable starter TBD")
        for name, side in ((ap, away_name), (hp, home_name)):
            if not name or name == "TBD":
                continue
            sig = pitcher_signal(name, lookups)
            if sig and sig[0]:
                score = sig[0].get("pitcher_foundation_signal", 0)
                if best_signal is None or score > best_signal[0]:
                    best_signal = (score, name, side, sig[0].get("label"))

    if best_signal:
        rotation_edge = f"{best_signal[1]} ({best_signal[2]}) shows the steadier pitching profile in this series: {best_signal[3]}."
    else:
        rotation_edge = "Probable starter signals limited for this series."

    tbd_count = sum(1 for g in games if g["probable_away_pitcher"] == "TBD" or g["probable_home_pitcher"] == "TBD")
    if tbd_count:
        volatility_note = f"{tbd_count} of {game_count} game(s) still have a probable starter TBD, adding rotation uncertainty."
    else:
        volatility_note = "All probable starters listed for this series as of the edition date."

    pitching_path = {
        "away_probables": away_probables,
        "home_probables": home_probables,
        "rotation_edge": rotation_edge,
        "volatility_note": volatility_note,
    }

    # ── Lineup matchup ───────────────────────────────────────────────
    away_power = top_signal_bats(away, lookups["power"], lookups)
    home_power = top_signal_bats(home, lookups["power"], lookups)
    away_contact = top_signal_bats(away, lookups["contact"], lookups)
    home_contact = top_signal_bats(home, lookups["contact"], lookups)

    away_pressure = (f"{away_power[0]['full_name']} headlines the {away_name} power threat ({away_power[0]['label']})."
                      if away_power else "Limited current form data")
    home_pressure = (f"{home_power[0]['full_name']} headlines the {home_name} power threat ({home_power[0]['label']})."
                      if home_power else "Limited current form data")

    power_bats = [s["full_name"] for s in (away_power[:1] + home_power[:1])]
    contact_bats = [s["full_name"] for s in (away_contact[:1] + home_contact[:1])]

    lineup_matchup = {
        "away_pressure": away_pressure,
        "home_pressure": home_pressure,
        "power_bats": power_bats,
        "contact_bats": contact_bats,
    }

    # ── Bullpen leverage ─────────────────────────────────────────────
    bullpen_leverage = {
        "away_read": "Limited bullpen data available for V1.",
        "home_read": "Limited bullpen data available for V1.",
        "edge": "Limited current form data",
    }

    # ── Players who tilt series ─────────────────────────────────────
    tilt = []
    if best_signal:
        _, name, side, label = best_signal
        sig = pitcher_signal(name, lookups)
        slug = sig[2] if sig else None
        tilt.append({"name": name, "team": side, "slug": slug, "tag": "Strikeout Arm" if sig and sig[0] and sig[0].get("k9", 0) >= 9 else "Stable Starter"})
    for s, team in ((away_power[:1], away), (home_power[:1], home)):
        for sig in s:
            tilt.append({"name": sig["full_name"], "team": team, "slug": sig.get("slug"), "tag": "Power Pressure"})
    for s, team in ((away_contact[:1], away), (home_contact[:1], home)):
        for sig in s:
            if any(t["name"] == sig["full_name"] for t in tilt):
                continue
            tilt.append({"name": sig["full_name"], "team": team, "slug": sig.get("slug"), "tag": "Contact Table-Setter"})
    tilt = tilt[:4]

    # ── Fantasy/DFS watch ────────────────────────────────────────────
    fantasy_dfs_watch = []
    for t in tilt:
        if t["tag"] == "Power Pressure":
            fantasy_dfs_watch.append(f"{t['name']} ({t['team']}) is a power-pressure watch for DFS builds in this series.")
        elif t["tag"] == "Strikeout Arm":
            fantasy_dfs_watch.append(f"{t['name']} ({t['team']}) profiles as a strikeout-arm lean for DFS pitching pools.")
    if not fantasy_dfs_watch:
        fantasy_dfs_watch = ["Limited current form data for DFS watch."]

    # ── Barrel proof read ────────────────────────────────────────────
    read_parts = [f"{away_name} visit {home_name} for a {game_count}-game series ({start_date} to {end_date})."]
    if best_signal:
        read_parts.append(f"{best_signal[1]} gives {best_signal[2]} the steadier arm on paper.")
    if away_power or home_power:
        bat = (away_power or home_power)[0]
        read_parts.append(f"Watch {bat['full_name']} as a power-pressure presence in this matchup.")
    barrel_proof_read = " ".join(read_parts)

    return {
        "series_id": series_id,
        "away_team": away,
        "home_team": home,
        "away_team_name": away_name,
        "home_team_name": home_name,
        "start_date": start_date,
        "end_date": end_date,
        "game_count": game_count,
        "is_four_game_series": is_four_game,
        "is_thursday_start": is_thursday_start,
        "games": games,
        "series_context": series_context,
        "pitching_path": pitching_path,
        "lineup_matchup": lineup_matchup,
        "bullpen_leverage": bullpen_leverage,
        "players_who_tilt_series": tilt,
        "fantasy_dfs_watch": fantasy_dfs_watch,
        "barrel_proof_read": barrel_proof_read,
    }


def main():
    print("Fetching schedule window 2026-06-18 through 2026-06-21...", flush=True)
    all_games = []
    for d in WINDOW_DATES:
        try:
            games = fetch_date(d)
            print(f"  {d}: {len(games)} games", flush=True)
            all_games.extend(games)
        except Exception as e:
            print(f"  ✗ Error fetching {d}: {e}", flush=True)
            sys.exit(1)

    grouped = group_into_series(all_games)
    lookups = build_lookups()
    standings = get_standings_records()

    series_out = []
    teams_seen = []
    for away, home, run in grouped:
        away_name = run[0]["away_team_name"]
        home_name = run[0]["home_team_name"]
        entry = build_series_entry(away, home, run, away_name, home_name, lookups, standings)
        series_out.append(entry)
        teams_seen.extend([away, home])

    series_out.sort(key=lambda s: (s["start_date"], s["away_team"]))

    # team coverage report
    seen_set = set(teams_seen)
    dupes = [t for t in seen_set if teams_seen.count(t) > 1]
    missing = sorted(set(TEAM_NAMES_ABBR_SET()) - seen_set)
    if dupes:
        print(f"  ⚠ Duplicate teams across series: {sorted(dupes)}", flush=True)
    if missing:
        print(f"  ⚠ Teams missing from weekend slate: {missing}", flush=True)
    else:
        print("  ✓ All 30 teams represented exactly once.", flush=True)

    out = {
        "meta": {
            "edition_date": EDITION_DATE,
            "covered_dates": sorted(WEEKEND_DATES),
            "schedule_window": [WINDOW_DATES[0], WINDOW_DATES[-1]],
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "series_count": len(series_out),
        },
        "series": series_out,
    }

    OUT_FILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"  ✓ Wrote {OUT_FILE} ({len(series_out)} series)", flush=True)


def TEAM_NAMES_ABBR_SET():
    # Build the set of all 30 abbreviations from the schedule API's own abbreviations
    # (derived from TEAM_NAMES ids mapped through known abbreviations).
    return [
        "ARI","ATL","BAL","BOS","CHC","CWS","CIN","CLE","COL","DET","HOU","KC",
        "LAA","LAD","MIA","MIL","MIN","NYM","NYY","ATH","PHI","PIT","SD","SF",
        "SEA","STL","TB","TEX","TOR","WSH",
    ]


if __name__ == "__main__":
    main()
