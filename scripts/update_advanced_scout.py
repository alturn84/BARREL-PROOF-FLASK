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

TEAM_ABBR_TO_CITY = {
    "ARI": "Arizona", "ATL": "Atlanta", "BAL": "Baltimore", "BOS": "Boston",
    "CHC": "Chicago", "CWS": "Chicago", "CIN": "Cincinnati", "CLE": "Cleveland",
    "COL": "Colorado", "DET": "Detroit", "HOU": "Houston", "KC": "Kansas City",
    "LAA": "Los Angeles", "LAD": "Los Angeles", "MIA": "Miami", "MIL": "Milwaukee",
    "MIN": "Minnesota", "NYM": "New York", "NYY": "New York", "ATH": "Athletics",
    "PHI": "Philadelphia", "PIT": "Pittsburgh", "SD": "San Diego", "SF": "San Francisco",
    "SEA": "Seattle", "STL": "St. Louis", "TB": "Tampa Bay", "TEX": "Texas",
    "TOR": "Toronto", "WSH": "Washington",
}

TEAM_ABBR_TO_LEAGUE = {
    "BAL": "AL", "BOS": "AL", "NYY": "AL", "TB": "AL", "TOR": "AL",
    "CWS": "AL", "CLE": "AL", "DET": "AL", "KC": "AL", "MIN": "AL",
    "ATH": "AL", "HOU": "AL", "LAA": "AL", "SEA": "AL", "TEX": "AL",
    "ATL": "NL", "MIA": "NL", "NYM": "NL", "PHI": "NL", "WSH": "NL",
    "CHC": "NL", "CIN": "NL", "MIL": "NL", "PIT": "NL", "STL": "NL",
    "ARI": "NL", "COL": "NL", "LAD": "NL", "SD": "NL", "SF": "NL",
}

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
    """Returns (city, league) -> {display, w, l, gb} where gb is a float (0.0 = first place)."""
    data = load_json_safe(DATA_DIR / "standings.json", {})
    out = {}
    for league_block in data.get("leagues", []):
        league = league_block.get("league")
        for div in league_block.get("divisions", []):
            for t in div.get("teams", []):
                city = t.get("city")
                w, l, gb = t.get("w"), t.get("l"), t.get("gb")
                if city is None or w is None or l is None:
                    continue
                gb_num = 0.0 if gb in (None, "-", "0.0", "0") else float(gb)
                gb_str = "1st place" if gb_num == 0.0 else f"{gb} GB"
                out[(city, league)] = {"display": f"{w}-{l}, {gb_str}", "w": w, "l": l, "gb": gb_num}
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
    luck_gap = load_json_safe(PLAYER_DIR / "hitter_luck_gap.json", {}).get("players", {})
    il_data = load_json_safe(DATA_DIR / "team_il.json", {}).get("teams", {})

    return {
        "name_to_slug": name_to_slug,
        "team_to_players": team_to_players,
        "power": power,
        "contact": contact,
        "foundation": foundation,
        "profile": profile,
        "luck_gap": luck_gap,
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


def top_pitcher_signal(team_abbr, lookups):
    """Best pitcher_foundation_signal entry for a team, or None."""
    il_names = il_names_for_team(team_abbr, lookups)
    candidates = []
    for p in lookups["team_to_players"].get(team_abbr, []):
        if p.get("position_group") != "Pitcher":
            continue
        if p.get("full_name") in il_names:
            continue
        slug = p.get("slug")
        sig = lookups["foundation"].get(slug)
        if not sig:
            continue
        candidates.append(sig)
    candidates.sort(key=lambda s: s.get("pitcher_foundation_signal", 0) or 0, reverse=True)
    return candidates[0] if candidates else None


def luck_gap_standout(team_abbr, lookups):
    """Hitter with the largest |luck_gap_points| on a team, excluding IL."""
    il_names = il_names_for_team(team_abbr, lookups)
    candidates = []
    for p in lookups["team_to_players"].get(team_abbr, []):
        if p.get("position_group") == "Pitcher":
            continue
        if p.get("full_name") in il_names:
            continue
        slug = p.get("slug")
        lg = lookups["luck_gap"].get(slug)
        if not lg or lg.get("luck_gap_points") is None:
            continue
        candidates.append(lg)
    candidates.sort(key=lambda s: abs(s.get("luck_gap_points", 0)), reverse=True)
    return candidates[0] if candidates else None


def build_series_entry(away, home, games, away_name, home_name, lookups, standings):
    start_date = games[0]["date"]
    end_date = games[-1]["date"]
    game_count = len(games)
    is_four_game = game_count == 4
    is_thursday_start = start_date == "2026-06-18"

    series_id = f"{away.lower()}-{home.lower()}-{start_date}"

    # ── Series pressure ──────────────────────────────────────────────
    away_rec = standings.get((TEAM_ABBR_TO_CITY.get(away), TEAM_ABBR_TO_LEAGUE.get(away)))
    home_rec = standings.get((TEAM_ABBR_TO_CITY.get(home), TEAM_ABBR_TO_LEAGUE.get(home)))
    if away_rec and home_rec:
        away_gb, home_gb = away_rec["gb"], home_rec["gb"]
        hi_gb, lo_gb = max(away_gb, home_gb), min(away_gb, home_gb)
        if hi_gb <= 4.0:
            pressure_label = "Division Pressure"
            pressure_summary = (f"{away_name} ({away_rec['display']}) and {home_name} ({home_rec['display']}) "
                                 f"are both within range of the top of their division, so every game here carries standings weight.")
        elif hi_gb <= 8.0 and lo_gb <= 4.0:
            pressure_label = "Wildcard Pressure"
            pressure_summary = (f"{away_name} ({away_rec['display']}) and {home_name} ({home_rec['display']}) "
                                 f"sit close enough to the wildcard picture that this series adds to the margin either way.")
        elif lo_gb <= 2.0 and hi_gb >= 10.0:
            pressure_label = "Trap Series"
            leader_name = away_name if away_gb < home_gb else home_name
            leader_rec = away_rec if away_gb < home_gb else home_rec
            pressure_summary = (f"{leader_name} ({leader_rec['display']}) is fighting for position while the other side has more breathing room — "
                                 f"the kind of series that can quietly slip away from the favorite.")
        elif lo_gb >= 10.0:
            pressure_label = "Development Series"
            pressure_summary = (f"Both {away_name} and {home_name} sit well off the lead ({away_rec['display']} / {home_rec['display']}), "
                                 f"so the series is more about individual performance and roles than the standings.")
        else:
            pressure_label = "Limited Standings Pressure"
            pressure_summary = f"{away_name} ({away_rec['display']}) at {home_name} ({home_rec['display']}) — neither club is in immediate standings pressure this weekend."
    else:
        pressure_label = "Limited Standings Pressure"
        pressure_summary = "Current standings context is limited for this series."

    series_pressure = {"label": pressure_label, "summary": pressure_summary}

    # ── Series context ──────────────────────────────────────────────
    standings_angle = (f"{away_name} ({away_rec['display']}) at {home_name} ({home_rec['display']})."
                        if away_rec and home_rec else "Limited current form data")

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
    away_sigs, home_sigs = [], []
    for g in games:
        ap, hp = g["probable_away_pitcher"], g["probable_home_pitcher"]
        away_probables.append(ap if ap else "Probable starter TBD")
        home_probables.append(hp if hp else "Probable starter TBD")
        if ap and ap != "TBD":
            sig = pitcher_signal(ap, lookups)
            if sig and sig[0]:
                away_sigs.append((sig[0], ap, sig[2]))
        if hp and hp != "TBD":
            sig = pitcher_signal(hp, lookups)
            if sig and sig[0]:
                home_sigs.append((sig[0], hp, sig[2]))

    all_sigs = [(s, n, side, slug) for (s, n, slug) in away_sigs for side in (away_name,)] + \
               [(s, n, side, slug) for (s, n, slug) in home_sigs for side in (home_name,)]
    all_sigs.sort(key=lambda t: t[0].get("pitcher_foundation_signal", 0) or 0, reverse=True)

    pitcher_watchlist = []
    for sig, name, side, slug in all_sigs[:3]:
        score = sig.get("pitcher_foundation_signal", 0)
        if score >= 65:
            tag = "Stable Starter"
        elif score <= 40:
            tag = "Volatile Starter"
        else:
            tag = "Mid-Profile Starter"
        pitcher_watchlist.append({
            "name": name, "team": side, "slug": slug, "tag": tag,
            "label": sig.get("label", ""),
        })

    away_avg = sum(s[0].get("pitcher_foundation_signal", 0) for s in away_sigs) / len(away_sigs) if away_sigs else None
    home_avg = sum(s[0].get("pitcher_foundation_signal", 0) for s in home_sigs) / len(home_sigs) if home_sigs else None

    if away_avg is not None and home_avg is not None:
        if away_avg > home_avg + 5:
            rotation_edge = f"{away_name} carries the cleaner pitching path into this series, with its probable starters reading more stable than {home_name}'s."
        elif home_avg > away_avg + 5:
            rotation_edge = f"{home_name} carries the cleaner pitching path into this series, with its probable starters reading more stable than {away_name}'s."
        else:
            rotation_edge = f"{away_name} and {home_name} bring comparable starter profiles, so the pitching path looks close to even on paper."
    elif all_sigs:
        sig, name, side, slug = all_sigs[0]
        rotation_edge = f"{name} gives {side} the steadier arm on paper, but the rest of the rotation picture is still filling in."
    else:
        rotation_edge = "Probable starter signals are limited for this series, so the pitching path is still developing."

    tbd_count = sum(1 for g in games if g["probable_away_pitcher"] == "TBD" or g["probable_home_pitcher"] == "TBD")
    if tbd_count == 0:
        probable_confidence = "Confirmed"
        volatility_note = "All probable starters are listed for this series as of the edition date."
    elif tbd_count < game_count * 2:
        probable_confidence = "Partial"
        volatility_note = f"{tbd_count} of {game_count * 2} starting assignments are still TBD, so the back half of the series can swing the pitching path."
    else:
        probable_confidence = "TBD"
        volatility_note = "Probable starters are not yet posted for this series; the pitching path will sharpen closer to first pitch."

    pitching_path = {
        "away_probables": away_probables,
        "home_probables": home_probables,
        "rotation_edge": rotation_edge,
        "volatility_note": volatility_note,
        "probable_confidence": probable_confidence,
        "pitcher_watchlist": pitcher_watchlist,
    }

    # ── Lineup matchup ───────────────────────────────────────────────
    away_power = top_signal_bats(away, lookups["power"], lookups, n=2)
    home_power = top_signal_bats(home, lookups["power"], lookups, n=2)
    away_contact = top_signal_bats(away, lookups["contact"], lookups, n=2)
    home_contact = top_signal_bats(home, lookups["contact"], lookups, n=2)

    away_pressure = (f"{away_power[0]['full_name']} is the power-pocket bat for {away_name} — {away_power[0]['label'].lower()}."
                      if away_power else "Limited current form data")
    home_pressure = (f"{home_power[0]['full_name']} is the power-pocket bat for {home_name} — {home_power[0]['label'].lower()}."
                      if home_power else "Limited current form data")

    power_bats = [s["full_name"] for s in (away_power[:1] + home_power[:1])]
    contact_bats = [s["full_name"] for s in (away_contact[:1] + home_contact[:1])]

    avg_power = sum(s.get("power_signal", 0) or 0 for s in (away_power + home_power)) / len(away_power + home_power) if (away_power + home_power) else 0
    avg_contact = sum(s.get("contact_signal", 0) or 0 for s in (away_contact + home_contact)) / len(away_contact + home_contact) if (away_contact + home_contact) else 0

    if not (away_power or home_power or away_contact or home_contact):
        matchup_shape = "Pitching-Controlled Series"
        shape_summary = "Hitter signal data is limited for this series, so the read leans on the pitching path instead of the lineups."
    elif avg_power >= avg_contact + 8:
        matchup_shape = "Power Series"
        shape_summary = f"Both lineups carry more thump than traffic here — {away_name} and {home_name} project as a series where one mistake to a power pocket can be the separator."
    elif avg_contact >= avg_power + 8:
        matchup_shape = "Contact Pressure Series"
        shape_summary = f"This leans on traffic over thunder — {away_name} and {home_name} both project to work counts and string at-bats together rather than rely on one swing."
    else:
        matchup_shape = "Balanced Offensive Series"
        shape_summary = f"{away_name} and {home_name} both bring a mix of power and contact pressure, so the series can tilt on either kind of mistake."

    def dedupe_bats(power_list, contact_list):
        names = [s["full_name"] for s in power_list[:1]]
        for s in contact_list:
            if s["full_name"] not in names:
                names.append(s["full_name"])
                break
        return names

    key_bats_by_team = {
        away: dedupe_bats(away_power, away_contact),
        home: dedupe_bats(home_power, home_contact),
    }

    lineup_matchup = {
        "away_pressure": away_pressure,
        "home_pressure": home_pressure,
        "matchup_shape": matchup_shape,
        "key_bats_by_team": key_bats_by_team,
        "summary": shape_summary,
        "power_bats": power_bats,
        "contact_bats": contact_bats,
    }

    # ── Bullpen leverage ─────────────────────────────────────────────
    bullpen_leverage = {
        "away_read": "Limited current bullpen data; watch early starter length.",
        "home_read": "Limited current bullpen data; watch early starter length.",
        "edge": "Limited current form data",
        "data_quality": "limited",
    }

    # ── Players who tilt series ──────────────────────────────────────
    tilt = []
    seen_names = set()

    def add_tilt(name, team, slug, tag, reason):
        if name in seen_names:
            return
        seen_names.add(name)
        tilt.append({"name": name, "team": team, "slug": slug, "tag": tag, "reason": reason})

    # Top power bat from each side
    for s, team, side_name in ((away_power[:1], away, away_name), (home_power[:1], home, home_name)):
        for sig in s:
            add_tilt(sig["full_name"], team, sig.get("slug"), "Power Pressure",
                     f"{sig['full_name']} is the clearest power-pocket bat for {side_name} — {sig['label'].lower()}.")

    # Top contact bat from each side
    for s, team, side_name in ((away_contact[:1], away, away_name), (home_contact[:1], home, home_name)):
        for sig in s:
            add_tilt(sig["full_name"], team, sig.get("slug"), "Contact Table-Setter",
                     f"{sig['full_name']} sets the table for {side_name} with a contact profile that keeps traffic on the bases.")

    # Best pitcher signal overall
    if all_sigs:
        sig, name, side, slug = all_sigs[0]
        score = sig.get("pitcher_foundation_signal", 0)
        if score >= 65:
            tag, reason = "Run Prevention Anchor", f"{name} gives {side} a run-prevention anchor — {sig.get('label','').lower()}."
        elif score <= 40:
            tag, reason = "Volatile Starter", f"{name} brings volatility to {side}'s pitching path — {sig.get('label','').lower()}."
        else:
            tag, reason = "Run Prevention Anchor", f"{name} is the steadiest probable arm in this series for {side}."
        add_tilt(name, away if side == away_name else home, slug, tag, reason)

    # Luck-gap / breakout signal from each side
    for team, side_name in ((away, away_name), (home, home_name)):
        lg = luck_gap_standout(team, lookups)
        if lg and abs(lg.get("luck_gap_points", 0)) >= 15:
            tag = "Buy-Low Signal" if lg["luck_gap_points"] > 0 else "Series Swing Bat"
            reason = (f"{lg['full_name']} has been {'unlucky' if lg['luck_gap_points'] > 0 else 'running hot'} relative to expected production "
                      f"({lg['label'].lower()}), making {side_name} a buy-low watch this series." if lg["luck_gap_points"] > 0 else
                      f"{lg['full_name']} is outperforming the underlying numbers for {side_name} ({lg['label'].lower()}), a swing factor if it continues.")
            add_tilt(lg["full_name"], team, lg.get("slug"), tag, reason)

    tilt = tilt[:5]
    if len(tilt) < 3:
        # backfill from remaining power/contact pool to reach a useful minimum
        for s, team, side_name in ((away_power[1:], away, away_name), (home_power[1:], home, home_name),
                                    (away_contact[1:], away, away_name), (home_contact[1:], home, home_name)):
            for sig in s:
                if len(tilt) >= 3:
                    break
                add_tilt(sig["full_name"], team, sig.get("slug"), "DFS Watch",
                         f"{sig['full_name']} adds depth to the {side_name} lineup pressure picture.")

    # ── Fantasy/DFS watch ──────────────────────────────────────────────
    fantasy_dfs_watch = []
    for t in tilt:
        if t["tag"] == "Power Pressure":
            fantasy_dfs_watch.append(f"Power Watch: {t['name']} ({t['team']}) is a power-pressure angle worth tracking for DFS builds in this series.")
        elif t["tag"] == "Contact Table-Setter":
            fantasy_dfs_watch.append(f"Contact/OBP Watch: {t['name']} ({t['team']}) profiles as a table-setter lean if confirmed near the top of the order.")
        elif t["tag"] in ("Run Prevention Anchor", "Volatile Starter"):
            fantasy_dfs_watch.append(f"Pitcher {'Stability' if t['tag']=='Run Prevention Anchor' else 'Risk'}: {t['name']} ({t['team']}) is worth a profile check before finalizing pitching builds.")
        elif t["tag"] in ("Buy-Low Signal", "Series Swing Bat"):
            fantasy_dfs_watch.append(f"Value Angle: {t['name']} ({t['team']}) is a {'buy-low' if t['tag']=='Buy-Low Signal' else 'form'} lean based on recent luck-gap signals.")
        else:
            fantasy_dfs_watch.append(f"DFS Pool: {t['name']} ({t['team']}) is worth tracking as the series develops.")

    if tbd_count:
        fantasy_dfs_watch.append("Lineup Confirmation: Several probable starters are still TBD — confirm lineups and pitching matchups before finalizing builds.")

    fantasy_dfs_watch = fantasy_dfs_watch[:5]
    if not fantasy_dfs_watch:
        fantasy_dfs_watch = ["Limited current form data for DFS watch."]

    # ── Betting / props series watch (analysis framing only) ──────────
    betting_props_watch = []
    if all_sigs:
        sig, name, side, slug = all_sigs[0]
        if sig.get("k9", 0) and sig["k9"] >= 9:
            betting_props_watch.append(f"Strikeout Angle: {name}'s profile ({sig.get('k9')} K/9) makes the strikeout market worth checking once lineups are confirmed.")
        elif sig.get("pitcher_foundation_signal", 0) <= 40:
            betting_props_watch.append(f"Run Environment: {side}'s probable starter profile reads volatile, so the run environment here is worth checking once lineups are confirmed.")
    if away_power or home_power:
        bat = (away_power + home_power)[0]
        betting_props_watch.append(f"Power Risk: {bat['full_name']}'s power profile is worth watching against this series' probable starters.")
    if tbd_count >= game_count:
        betting_props_watch.append("Starter Risk: With probable pitchers still unsettled, props tied to specific starters carry more uncertainty until lineups firm up.")

    # ── Data transparency ───────────────────────────────────────────────
    data_basis = {
        "lineup_basis": "player signal pool" if (away_power or home_power or away_contact or home_contact) else "limited",
        "probable_pitcher_basis": probable_confidence.lower(),
        "bullpen_basis": "limited",
    }

    # ── Barrel proof read ───────────────────────────────────────────────
    read_parts = []
    if matchup_shape == "Power Series":
        read_parts.append(f"{away_name} at {home_name} reads as a power series — both lineups carry pockets that can turn one mistake into the separator.")
    elif matchup_shape == "Contact Pressure Series":
        read_parts.append(f"{away_name} at {home_name} leans on contact pressure over power — traffic and at-bat quality matter more than one swing here.")
    elif matchup_shape == "Pitching-Controlled Series":
        read_parts.append(f"{away_name} at {home_name} looks like a series the pitching path controls, with the lineups offering a more limited read.")
    else:
        read_parts.append(f"{away_name} at {home_name} is a balanced series — neither lineup has a clean power or contact edge over the other.")

    if away_avg is not None and home_avg is not None and abs(away_avg - home_avg) > 5:
        leader = away_name if away_avg > home_avg else home_name
        trailer = home_name if away_avg > home_avg else away_name
        read_parts.append(f"{leader} has the cleaner pitching path, and {trailer} needs its lineup to create traffic early rather than wait on one swing to even things out.")
    elif all_sigs:
        sig, name, side, slug = all_sigs[0]
        read_parts.append(f"{name} gives {side} the steadier arm on paper, which puts pressure on the opposing lineup to find traffic in the middle innings.")
    else:
        read_parts.append("Probable starters are still unsettled, so the pitching path is the swing factor to track as the week develops.")

    if tilt:
        top = tilt[0]
        if top["tag"] == "Power Pressure":
            read_parts.append(f"If {top['team']} gets into the middle innings with a lead, {top['name']} turns this into a bullpen-stress series for the other side.")
        elif top["tag"] in ("Run Prevention Anchor",):
            read_parts.append(f"Watch {top['name']}'s start as the early signal for which way the series tilts.")

    barrel_proof_read = " ".join(read_parts[:4])

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
        "series_pressure": series_pressure,
        "series_context": series_context,
        "pitching_path": pitching_path,
        "lineup_matchup": lineup_matchup,
        "bullpen_leverage": bullpen_leverage,
        "players_who_tilt_series": tilt,
        "fantasy_dfs_watch": fantasy_dfs_watch,
        "betting_props_watch": betting_props_watch,
        "data_basis": data_basis,
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
