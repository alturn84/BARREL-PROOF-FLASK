#!/usr/bin/env python3
"""
Barrel Proof — Dope Sheet Daily Updater  v2
Fetches: schedule, probable pitchers, lineups, weather (NWS),
         bullpen availability, team form (last 10), team batting/pitching snapshots.

Usage:
    python update_dope_sheet.py              # today
    python update_dope_sheet.py 2026-06-08   # specific date
"""

import json, sys, time, math
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    import urllib.request, urllib.error
    class _Req:
        def get(self, url, timeout=20, headers=None):
            req = urllib.request.Request(url, headers=headers or {})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    class R:
                        status_code = r.status
                        def raise_for_status(self): pass
                        def json(self_): return json.loads(r.read())
                    return R()
            except Exception as e:
                class E:
                    status_code = 0
                    def raise_for_status(self): raise Exception(str(e))
                    def json(self_): return {}
                return E()
    requests = _Req()

BASE_DIR  = Path(__file__).resolve().parent
DATA_DIR  = BASE_DIR / "Site Data"
OUT_FILE  = DATA_DIR / "dope-sheet-data.json"
MLB_BASE  = "https://statsapi.mlb.com/api/v1"
NWS_BASE  = "https://api.weather.gov"

HEADERS = {
    "User-Agent": "BarrelProofBaseball/2.0 (barrel-proof-baseball.com)",
    "Accept": "application/json",
}

# ── TEAM LOOKUPS ──────────────────────────────────────────────────────────
TEAM_ABB = {
    "Arizona Diamondbacks":"AZ","Atlanta Braves":"ATL","Baltimore Orioles":"BAL",
    "Boston Red Sox":"BOS","Chicago Cubs":"CHC","Chicago White Sox":"CWS",
    "Cincinnati Reds":"CIN","Cleveland Guardians":"CLE","Colorado Rockies":"COL",
    "Detroit Tigers":"DET","Houston Astros":"HOU","Kansas City Royals":"KC",
    "Los Angeles Angels":"LAA","Los Angeles Dodgers":"LAD","Miami Marlins":"MIA",
    "Milwaukee Brewers":"MIL","Minnesota Twins":"MIN","New York Mets":"NYM",
    "New York Yankees":"NYY","Oakland Athletics":"ATH","Philadelphia Phillies":"PHI",
    "Pittsburgh Pirates":"PIT","San Diego Padres":"SD","San Francisco Giants":"SF",
    "Seattle Mariners":"SEA","St. Louis Cardinals":"STL","Tampa Bay Rays":"TB",
    "Texas Rangers":"TEX","Toronto Blue Jays":"TOR","Washington Nationals":"WSH",
}

DOME_PARKS = {
    "American Family Field","Rogers Centre","Tropicana Field",
    "loanDepot park","Minute Maid Park","Globe Life Field","Chase Field",
}

# NWS station per home venue (closest reliable station)
VENUE_STATION = {
    "PNC Park":                  "KPIT",
    "Wrigley Field":             "KMDW",
    "Guaranteed Rate Field":     "KMDW",
    "American Family Field":     "KMKE",
    "Comerica Park":             "KDTW",
    "Progressive Field":         "KCLE",
    "Target Field":              "KMSP",
    "Kauffman Stadium":          "KMCI",
    "Busch Stadium":             "KSTL",
    "Great American Ball Park":  "KCVG",
    "Great American":            "KCVG",
    "Citizens Bank Park":        "KPHL",
    "Camden Yards":              "KBWI",
    "Oriole Park at Camden Yards":"KBWI",
    "Fenway Park":               "KBOS",
    "Yankee Stadium":            "KLGA",
    "Citi Field":                "KLGA",
    "Truist Park":               "KFTY",
    "Globe Life Field":          "KDAL",
    "Minute Maid Park":          "KHOU",
    "Coors Field":               "KDEN",
    "Chase Field":               "KPHX",
    "Dodger Stadium":            "KLAX",
    "Angel Stadium":             "KSNA",
    "Petco Park":                "KSAN",
    "Oracle Park":               "KSFO",
    "T-Mobile Park":             "KSEA",
    "Sutter Health Park":        "KSAC",
    "loanDepot park":            "KMIA",
    "Tropicana Field":           "KTPA",
    "Rogers Centre":             "CYTZ",
}

# ── UTILITIES ─────────────────────────────────────────────────────────────
def fetch(url, headers=None, silent=False):
    try:
        r = requests.get(url, timeout=20, headers=headers or HEADERS)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        if not silent:
            print(f"    ⚠ fetch error {url[:60]}: {e}")
        return {}

def safe(val, fallback="—"):
    if val is None or val == "" or val != val:
        return fallback
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return fallback
    except (TypeError, ValueError):
        pass
    return val

def fmt_stat(val, decimals=2, fallback="—"):
    v = safe(val, None)
    if v is None:
        return fallback
    try:
        return f"{float(v):.{decimals}f}"
    except Exception:
        return str(v)

def fmt_time_et(game_time_str):
    try:
        dt = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
        et = dt - timedelta(hours=4)
        h = et.hour % 12 or 12
        ampm = "AM" if et.hour < 12 else "PM"
        return f"{h}:{et.minute:02d} {ampm} ET"
    except Exception:
        return "TBD"

# ── WEATHER (NWS) ─────────────────────────────────────────────────────────
def get_weather(venue, roof):
    if roof == "Closed":
        return {"temp":"—","sky":"Dome","wind":"—","humidity":"—","precip":"0%","roof":"Closed","source":"dome"}

    station = VENUE_STATION.get(venue)
    if not station:
        return {"temp":"—","sky":"—","wind":"—","humidity":"—","precip":"—","roof":"Open","source":"unavailable"}

    try:
        obs = fetch(f"{NWS_BASE}/stations/{station}/observations/latest", silent=True)
        props = obs.get("properties", {})

        temp_c = props.get("temperature", {}).get("value")
        temp_f = f"{round(temp_c * 9/5 + 32)}°F" if temp_c is not None else "—"

        wind_ms = props.get("windSpeed", {}).get("value")
        wind_dir = props.get("windDirection", {}).get("value")
        if wind_ms is not None:
            wind_mph = round(wind_ms * 2.237)
            if wind_dir is not None:
                dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
                compass = dirs[round(wind_dir / 22.5) % 16]
                wind_str = f"{wind_mph} mph {compass}"
            else:
                wind_str = f"{wind_mph} mph"
        else:
            wind_str = "—"

        humidity = props.get("relativeHumidity", {}).get("value")
        hum_str = f"{round(humidity)}%" if humidity is not None else "—"

        sky_raw = props.get("textDescription") or ""
        sky = sky_raw[:40] if isinstance(sky_raw, str) and sky_raw else "—"

        return {
            "temp": temp_f,
            "sky": sky,
            "wind": wind_str,
            "humidity": hum_str,
            "precip": "—",
            "roof": "Open",
            "source": "NWS",
        }
    except Exception as e:
        print(f"    ⚠ Weather error for {venue}: {e}")
        return {"temp":"—","sky":"—","wind":"—","humidity":"—","precip":"—","roof":"Open","source":"error"}

# ── PROBABLE PITCHERS ─────────────────────────────────────────────────────
def get_probable_pitcher(game, side):
    try:
        pid = game.get("teams", {}).get(side, {}).get("probablePitcher", {}).get("id")
        if not pid:
            return empty_pitcher()
        data = fetch(f"{MLB_BASE}/people/{pid}?hydrate=stats(group=pitching,type=season)")
        p = data.get("people", [{}])[0]
        name = p.get("fullName", "TBD")
        hand = p.get("pitchHand", {}).get("code", "R")
        stats = {}
        for sg in p.get("stats", []):
            if sg.get("type", {}).get("displayName") == "season":
                stats = sg.get("splits", [{}])[0].get("stat", {})
                break
        wins   = stats.get("wins", "—")
        losses = stats.get("losses", "—")
        record = f"{wins}-{losses}" if wins != "—" else "—"
        return {
            "name": name, "hand": hand,
            "era":  fmt_stat(stats.get("era"), 2),
            "whip": fmt_stat(stats.get("whip"), 2),
            "k9":   fmt_stat(stats.get("strikeoutsPer9Inn"), 1),
            "bb9":  fmt_stat(stats.get("walksPer9Inn"), 1),
            "ip":   fmt_stat(stats.get("inningsPitched"), 1),
            "record": record,
            "lastStart": "—",
        }
    except Exception as e:
        print(f"    ⚠ Pitcher error: {e}")
        return empty_pitcher()

def empty_pitcher():
    return {"name":"TBD","hand":"R","era":"—","whip":"—","k9":"—","bb9":"—","ip":"—","record":"—","lastStart":"—"}

# ── LINEUPS ───────────────────────────────────────────────────────────────
def get_lineup_players(game, side):
    key = "awayPlayers" if side == "away" else "homePlayers"
    players = game.get("lineups", {}).get(key, [])
    return [
        {"name": p.get("fullName",""), "pos": p.get("primaryPosition",{}).get("abbreviation","")}
        for p in players
    ]

# ── BULLPEN AVAILABILITY ──────────────────────────────────────────────────
def get_bullpen(team_id, date_str):
    try:
        roster_data = fetch(f"{MLB_BASE}/teams/{team_id}/roster?rosterType=active")
        relievers = [
            p for p in roster_data.get("roster", [])
            if p.get("position", {}).get("type") == "Pitcher"
            and p.get("position", {}).get("abbreviation") != "SP"
        ]

        date_dt = datetime.strptime(date_str, "%Y-%m-%d")
        cutoff  = (date_dt - timedelta(days=5)).strftime("%Y-%m-%d")
        result  = []

        for r in relievers[:12]:
            pid   = r.get("person", {}).get("id")
            pname = r.get("person", {}).get("fullName", "Unknown")
            if not pid:
                continue
            try:
                log = fetch(
                    f"{MLB_BASE}/people/{pid}/stats?stats=gameLog&group=pitching"
                    f"&season={date_dt.year}&startDate={cutoff}&endDate={date_str}",
                    silent=True,
                )
                splits = log.get("stats", [{}])[0].get("splits", []) if log else []

                if splits:
                    last_date_str = splits[-1].get("date", "")
                    try:
                        last_dt   = datetime.strptime(last_date_str, "%Y-%m-%d")
                        days_rest = (date_dt - last_dt).days
                    except Exception:
                        days_rest = 99
                    two_day_ips = sum(
                        float(s.get("stat",{}).get("inningsPitched",0) or 0)
                        for s in splits[-2:]
                    )
                else:
                    days_rest = 99
                    two_day_ips = 0.0

                if days_rest == 0:
                    usage = "used"
                elif days_rest == 1 and two_day_ips >= 1.0:
                    usage = "light"
                elif days_rest <= 2 and two_day_ips >= 2.0:
                    usage = "used"
                else:
                    usage = "fresh"

                result.append({
                    "name": pname,
                    "role": "",
                    "usage": usage,
                    "rest": str(days_rest) if days_rest < 99 else "—",
                })
            except Exception:
                result.append({"name": pname, "role": "", "usage": "fresh", "rest": "—"})

        usage_order = {"used": 0, "light": 1, "fresh": 2}
        result.sort(key=lambda x: usage_order.get(x["usage"], 3))
        return result[:8]

    except Exception as e:
        print(f"    ⚠ Bullpen error team {team_id}: {e}")
        return []

# ── TEAM FORM (last 10) ───────────────────────────────────────────────────
def get_team_form(team_id, date_str):
    try:
        date_dt  = datetime.strptime(date_str, "%Y-%m-%d")
        start_dt = date_dt - timedelta(days=20)
        start    = start_dt.strftime("%Y-%m-%d")

        sched = fetch(
            f"{MLB_BASE}/schedule?sportId=1&teamId={team_id}"
            f"&startDate={start}&endDate={date_str}"
            f"&hydrate=decisions&gameType=R",
            silent=True,
        )
        games = []
        for d in sched.get("dates", []):
            for g in d.get("games", []):
                if g.get("status", {}).get("abstractGameState") == "Final":
                    games.append(g)

        games = games[-10:]
        if not games:
            return {"w":0,"l":0,"last10":"—","streak":"—","rs":0,"ra":0,"form_pct":0.0}

        wins = losses = 0
        rs = ra = 0
        streak_char = ""
        streak_count = 0

        for g in reversed(games):
            home_id = g.get("teams",{}).get("home",{}).get("team",{}).get("id")
            is_home = (home_id == team_id)
            home_score = g.get("teams",{}).get("home",{}).get("score",0) or 0
            away_score = g.get("teams",{}).get("away",{}).get("score",0) or 0
            team_score = home_score if is_home else away_score
            opp_score  = away_score if is_home else home_score
            won = team_score > opp_score
            rs += team_score
            ra += opp_score
            if won:
                wins += 1
                if streak_char != "W":
                    streak_char = "W"
                    streak_count = 1
                else:
                    streak_count += 1
            else:
                losses += 1
                if streak_char != "L":
                    streak_char = "L"
                    streak_count = 1
                else:
                    streak_count += 1

        form_pct = wins / len(games) if games else 0.0
        return {
            "w": wins, "l": losses,
            "last10": f"{wins}-{losses}",
            "streak": f"{streak_char}{streak_count}" if streak_char else "—",
            "rs": rs, "ra": ra,
            "form_pct": round(form_pct, 3),
        }
    except Exception as e:
        print(f"    ⚠ Form error team {team_id}: {e}")
        return {"w":0,"l":0,"last10":"—","streak":"—","rs":0,"ra":0,"form_pct":0.0}

# ── TEAM BATTING SNAPSHOT ─────────────────────────────────────────────────
def get_team_batting(team_id, season):
    try:
        data = fetch(
            f"{MLB_BASE}/teams/{team_id}/stats?stats=season&group=hitting&season={season}",
            silent=True,
        )
        splits = data.get("stats", [{}])[0].get("splits", [{}])
        s = splits[0].get("stat", {}) if splits else {}
        g = int(s.get("gamesPlayed") or 1) or 1
        return {
            "avg":  fmt_stat(s.get("avg"), 3),
            "obp":  fmt_stat(s.get("obp"), 3),
            "slg":  fmt_stat(s.get("slg"), 3),
            "ops":  fmt_stat(s.get("ops"), 3),
            "rpg":  fmt_stat((s.get("runs") or 0) / g, 2),
            "hrpg": fmt_stat((s.get("homeRuns") or 0) / g, 2),
            "hr":   safe(s.get("homeRuns"), "—"),
        }
    except Exception as e:
        print(f"    ⚠ Batting snapshot error team {team_id}: {e}")
        return {"avg":"—","obp":"—","slg":"—","ops":"—","rpg":"—","hrpg":"—","hr":"—"}

# ── TEAM PITCHING SNAPSHOT ────────────────────────────────────────────────
def get_team_pitching(team_id, season):
    try:
        data = fetch(
            f"{MLB_BASE}/teams/{team_id}/stats?stats=season&group=pitching&season={season}",
            silent=True,
        )
        splits = data.get("stats", [{}])[0].get("splits", [{}])
        s = splits[0].get("stat", {}) if splits else {}
        bp_data = fetch(
            f"{MLB_BASE}/teams/{team_id}/stats?stats=season&group=pitching"
            f"&season={season}&pitchingType=relievers",
            silent=True,
        )
        bp_splits = bp_data.get("stats", [{}])[0].get("splits", [{}]) if bp_data else []
        bp_s = bp_splits[0].get("stat", {}) if bp_splits else {}
        return {
            "era":    fmt_stat(s.get("era"), 2),
            "whip":   fmt_stat(s.get("whip"), 2),
            "k9":     fmt_stat(s.get("strikeoutsPer9Inn"), 1),
            "bb9":    fmt_stat(s.get("walksPer9Inn"), 1),
            "savepct":"—",
            "bp_era": fmt_stat(bp_s.get("era"), 2),
        }
    except Exception as e:
        print(f"    ⚠ Pitching snapshot error team {team_id}: {e}")
        return {"era":"—","whip":"—","k9":"—","bb9":"—","savepct":"—","bp_era":"—"}

# ── STANDINGS CONTEXT ─────────────────────────────────────────────────────
def load_standings():
    standings_file = DATA_DIR / "standings.json"
    if standings_file.exists():
        try:
            return json.loads(standings_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def get_standings_context(away_full, home_full, standings_data):
    context = {}
    leagues = standings_data.get("leagues", [])
    for league in leagues:
        for div in league.get("divisions", []):
            for team in div.get("teams", []):
                name = team.get("name", "")
                if name in (away_full, home_full):
                    key = "away" if name == away_full else "home"
                    context[key] = {
                        "w":    team.get("w", "—"),
                        "l":    team.get("l", "—"),
                        "pct":  team.get("pct", "—"),
                        "gb":   team.get("gb", "—"),
                        "rank": team.get("divRank", "—"),
                        "div":  div.get("name", ""),
                        "wc":   team.get("wildCardRank", "—"),
                        "elim": team.get("eliminationNumber", "—"),
                    }
    return context

# ── BUILD GAME ────────────────────────────────────────────────────────────
def build_game(game, date_str, standings_data, season):
    away_name = game["teams"]["away"]["team"]["name"]
    home_name = game["teams"]["home"]["team"]["name"]
    away_id   = game["teams"]["away"]["team"]["id"]
    home_id   = game["teams"]["home"]["team"]["id"]
    venue     = game.get("venue", {}).get("name", "—")
    roof      = "Closed" if venue in DOME_PARKS else "Open"

    print(f"  ├ {away_name} @ {home_name}")

    print(f"  │  pitchers...", end=" ", flush=True)
    away_p = get_probable_pitcher(game, "away")
    home_p = get_probable_pitcher(game, "home")
    print("✓")

    away_lu = get_lineup_players(game, "away")
    home_lu = get_lineup_players(game, "home")

    print(f"  │  weather...", end=" ", flush=True)
    weather = get_weather(venue, roof)
    print(f"✓ ({weather.get('source','?')})")

    print(f"  │  bullpen...", end=" ", flush=True)
    away_bp = get_bullpen(away_id, date_str)
    home_bp = get_bullpen(home_id, date_str)
    print(f"✓ ({len(away_bp)}+{len(home_bp)})")

    print(f"  │  form...", end=" ", flush=True)
    away_form = get_team_form(away_id, date_str)
    home_form = get_team_form(home_id, date_str)
    print("✓")

    print(f"  │  snapshots...", end=" ", flush=True)
    away_bat  = get_team_batting(away_id, season)
    home_bat  = get_team_batting(home_id, season)
    away_pit  = get_team_pitching(away_id, season)
    home_pit  = get_team_pitching(home_id, season)
    print("✓")

    std_ctx = get_standings_context(away_name, home_name, standings_data)

    return {
        "away":     TEAM_ABB.get(away_name, away_name[:3].upper()),
        "home":     TEAM_ABB.get(home_name, home_name[:3].upper()),
        "awayFull": away_name,
        "homeFull": home_name,
        "awayId":   away_id,
        "homeId":   home_id,
        "time":     fmt_time_et(game.get("gameDate", "")),
        "venue":    venue,
        "roof":     roof,
        "pitchers": {"away": away_p, "home": home_p},
        "weather":  weather,
        "umpire":   {"name":"TBD","calledKpct":"—","rpg":"—","note":""},
        "lineups":  {"away": away_lu, "home": home_lu},
        "bullpen":  {"away": away_bp, "home": home_bp},
        "injuries": {"away": [], "home": []},
        "form":     {"away": away_form, "home": home_form},
        "batting":  {"away": away_bat,  "home": home_bat},
        "pitching": {"away": away_pit,  "home": home_pit},
        "standings": std_ctx,
        "props":    {"note":"","pitchers":[],"batters":[]},
        "why_matters": "",
        "scouts_edge": "",
    }

# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    season   = date_str[:4]

    print(f"\n🗓  Barrel Proof Dope Sheet v2 — {date_str}")
    print(f"   Fetching MLB schedule...")

    sched = fetch(
        f"{MLB_BASE}/schedule?sportId=1&date={date_str}"
        f"&hydrate=lineups,probablePitcher,teams,venue"
    )
    dates = sched.get("dates", [])
    if not dates:
        print("  ✗ No games found.")
        return

    raw_games = dates[0].get("games", [])
    games = [g for g in raw_games if g.get("gameType") in ("R","F","D","L","W")]
    print(f"   ✓ {len(games)} games\n")

    standings_data = load_standings()
    if standings_data:
        print(f"   ✓ standings.json loaded\n")

    built = []
    for i, g in enumerate(games, 1):
        print(f"  [{i}/{len(games)}]")
        built.append(build_game(g, date_str, standings_data, season))
        time.sleep(0.3)

    try:
        dt      = datetime.strptime(date_str, "%Y-%m-%d")
        display = dt.strftime("%A, %B %-d, %Y")
        banner  = dt.strftime("%B %-d, %Y").upper()
    except Exception:
        display = date_str
        banner  = date_str.upper()

    output = {
        "date_display": display,
        "date_banner":  banner,
        "updated":      datetime.now(timezone.utc).isoformat(),
        "games":        built,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    lineup_total = sum(
        len(g.get("lineups",{}).get("away",[])) + len(g.get("lineups",{}).get("home",[]))
        for g in built
    )
    weather_live = sum(1 for g in built if g.get("weather",{}).get("source") == "NWS")
    bullpen_total = sum(
        len(g.get("bullpen",{}).get("away",[])) + len(g.get("bullpen",{}).get("home",[]))
        for g in built
    )

    print(f"\n✅  dope-sheet-data.json written → {OUT_FILE}")
    print(f"    {len(built)} games · {display}")
    print(f"    {lineup_total} lineup players")
    print(f"    {weather_live}/{len(built)} games with live NWS weather")
    print(f"    {bullpen_total} bullpen entries")
    print(f"\n📋  Manual fills:")
    print(f"    • Umpire (add to each game's umpire object)")
    print(f"    • Props (add to each game's props object)")
    print(f"    • why_matters / scouts_edge overrides (optional)")

if __name__ == "__main__":
    main()
