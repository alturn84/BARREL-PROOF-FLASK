"""
Build Site Data/dope_game_intelligence.json — a unified per-game intelligence
layer for the Dope Sheet. Combines dope_player_matchups.json,
dope_pitcher_matchups.json, dope-sheet-data.json (bullpen/weather), and
odds.json into one readable "Game Intelligence" read per game.

Pure data layer — no rendering.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_date_lib import read_edition_date

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Site Data"

DOPE_SHEET_DATA_PATH = DATA_DIR / "dope-sheet-data.json"
PLAYER_MATCHUPS_PATH = DATA_DIR / "dope_player_matchups.json"
PITCHER_MATCHUPS_PATH = DATA_DIR / "dope_pitcher_matchups.json"
ODDS_PATH = DATA_DIR / "odds.json"
TEAM_IL_PATH = DATA_DIR / "team_il.json"
SCHEDULE_PATH = DATA_DIR / "schedule.json"

OUTPUT_PATH = DATA_DIR / "dope_game_intelligence.json"
PITCH_INTEL_PATH = DATA_DIR / "pitch_type_intelligence.json"
HITTER_CARDS_PATH = DATA_DIR / "players" / "statcast_hitter_cards.json"
PLAYER_INDEX_PATH = DATA_DIR / "players" / "player_index.json"

FASTBALL_EDGE_LABELS = {"Fastball Damage", "Handles Fastballs", "Contact Path"}

TEAM_ABBR_ALIASES = {"AZ": "ARI"}

TEAM_FULL_NAME_TO_ABBR_HINTS = {}

# Short, readable prose names — used in generated sentences only. Internal
# team codes and JSON keys are unaffected by this map.
TEAM_SHORT_NAME = {
    "ATH": "Athletics", "ATL": "Atlanta", "AZ": "Arizona", "BAL": "Baltimore",
    "BOS": "Boston", "CHC": "Chicago", "CWS": "Chicago", "CIN": "Cincinnati",
    "CLE": "Cleveland", "COL": "Colorado", "DET": "Detroit", "HOU": "Houston",
    "KC": "Kansas City", "LAA": "Los Angeles", "LAD": "Los Angeles", "MIA": "Miami",
    "MIL": "Milwaukee", "MIN": "Minnesota", "NYM": "New York", "NYY": "New York",
    "PHI": "Philadelphia", "PIT": "Pittsburgh", "SD": "San Diego", "SEA": "Seattle",
    "SF": "San Francisco", "STL": "St. Louis", "TB": "Tampa Bay", "TEX": "Texas",
    "TOR": "Toronto", "WSH": "Washington",
}

# Nickname fallback — only used when a short city name would be ambiguous
# against the specific opponent in the same game (e.g. Cubs vs. White Sox).
TEAM_NICKNAME = {
    "ATH": "Athletics", "CHC": "Cubs", "CWS": "White Sox", "LAA": "Angels",
    "LAD": "Dodgers", "NYM": "Mets", "NYY": "Yankees",
}


def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def normalize_team_abbr(abbr):
    return TEAM_ABBR_ALIASES.get(abbr, abbr)


def team_display_name(team_abbr, full_name=None, opponent_abbr=None):
    """Short, readable team name for generated prose (not for JSON keys/matching).

    Defaults to a plain city name (e.g. "Texas", "Miami"). Falls back to a
    team nickname only when the opponent in this game shares the same city
    short name (e.g. Cubs vs. White Sox, Yankees vs. Mets, Angels vs. Dodgers).
    """
    short = TEAM_SHORT_NAME.get(team_abbr or "")
    if short is None:
        return full_name or team_abbr or ""
    if opponent_abbr and TEAM_SHORT_NAME.get(opponent_abbr) == short and team_abbr in TEAM_NICKNAME:
        return TEAM_NICKNAME[team_abbr]
    return short


def format_player_list(names):
    """Join player names into readable prose: 'A', 'A and B', or 'A, B, and C'."""
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def il_names_for_team(team_abbr, il_data):
    abbr = normalize_team_abbr(team_abbr)
    entries = il_data.get(abbr) or []
    return {e.get("name") for e in entries if isinstance(e, dict) and e.get("name")}


def v(x):
    """Truthy display value, filtering bad placeholders."""
    if x is None:
        return None
    if isinstance(x, str) and x.strip().lower() in ("", "none", "null", "nan", "—", "-"):
        return None
    if isinstance(x, float) and (x != x):
        return None
    return x


# ---------------------------------------------------------------------------
# Lineup read
# ---------------------------------------------------------------------------

def bat_role_tags(bat):
    tags = bat.get("tags") or []
    out = []
    if "Power Watch" in tags:
        out.append("Power Threat")
    if "Contact Edge" in tags:
        out.append("Gets On Base")
    if "Buy-Low Bat" in tags:
        out.append("Buy-Low Signal")
    if "DFS Watch" in tags and not out:
        out.append("DFS Watch")
    return out or ["Lineup Watch"]


def lineup_side_read(team_label, bats, pressure, lineup_source):
    if not bats:
        return {
            "summary": f"{team_label}'s lineup does not have a standout name today.",
            "power_pressure": "No clear data yet.",
            "contact_pressure": "No clear data yet.",
            "traffic_path": "No clear data yet.",
            "risk": "No clear data yet.",
            "key_bats": [],
        }

    power_bats = [b for b in bats if "Power Watch" in (b.get("tags") or [])]
    contact_bats = [b for b in bats if "Contact Edge" in (b.get("tags") or [])]
    buy_low = [b for b in bats if "Buy-Low Bat" in (b.get("tags") or [])]

    if power_bats:
        names = format_player_list([b["full_name"] for b in power_bats[:2]])
        power_pressure = f"{names} can change the game with one swing."
    else:
        power_pressure = f"{team_label} does not have a standout power threat today."

    if contact_bats:
        names = format_player_list([b["full_name"] for b in contact_bats[:2]])
        contact_pressure = f"{names} get on base and can set up the middle of the order."
    else:
        contact_pressure = f"{team_label} does not have a clear on-base threat today."

    if contact_bats:
        traffic_path = f"{team_label} is more likely to score by putting runners on base than by hitting home runs."
    elif power_bats:
        traffic_path = f"{team_label} leans on the long ball more than putting runners on base."
    else:
        traffic_path = f"{team_label}'s best path to scoring is not clear today."

    risk_bits = []
    for b in bats:
        if b.get("hitter_profile_type") == "Regression Risk":
            risk_bits.append(f"{b['full_name']} is due for a cool-down")
    risk = (", ".join(risk_bits) + "." if risk_bits else "No real red flags in this lineup right now.")

    if power_bats and contact_bats:
        summary = f"{team_label} has both power and on-base threats — a lineup that can win this game more than one way."
    elif power_bats:
        summary = f"{team_label} leans on power — one swing can change this game."
    elif contact_bats:
        summary = f"{team_label} leans on getting on base rather than the long ball."
    else:
        summary = f"{team_label}'s lineup is hard to read today."

    if buy_low:
        summary += f" {buy_low[0]['full_name']} is worth watching — he's been better than his results show."

    key_bats = []
    for b in bats[:3]:
        key_bats.append({"name": b["full_name"], "slug": b.get("slug"), "tags": bat_role_tags(b)})

    return {
        "summary": summary,
        "power_pressure": power_pressure,
        "contact_pressure": contact_pressure,
        "traffic_path": traffic_path,
        "risk": risk,
        "key_bats": key_bats,
    }


def matchup_shape(away_pressure, home_pressure, away_starter, home_starter):
    profiles = {away_pressure.get("profile"), home_pressure.get("profile")}
    if "Heavy lineup pressure" in profiles or "Power-heavy pressure" in profiles:
        return "Power Game"
    if "Contact-heavy pressure" in profiles:
        return "Contact Game"
    starters_volatile = (
        (away_starter or {}).get("stability") == "Volatile Arm"
        and (home_starter or {}).get("stability") == "Volatile Arm"
    )
    if starters_volatile and not profiles & {"Heavy lineup pressure", "Power-heavy pressure", "Contact-heavy pressure"}:
        return "Unpredictable Game"
    if profiles <= {"Insufficient data", "Limited signal pressure"}:
        return "Pitching-Controlled"
    return "Balanced Lineup Game"


# ---------------------------------------------------------------------------
# Pitching read
# ---------------------------------------------------------------------------

def starter_read(team_label, opp_label, starter_block, opp_pressure_on_this_starter):
    if not starter_block or not v(starter_block.get("name")):
        return {
            "summary": "No confirmed starter yet.",
            "stability": "Starter TBD — lineup and bullpen matter more until it's confirmed.",
            "risk": "Starter TBD — lineup and bullpen matter more until it's confirmed.",
            "matchup_fit": "Starter TBD — lineup and bullpen matter more until it's confirmed.",
            "watch": "Starter TBD — lineup and bullpen matter more until it's confirmed.",
        }

    name = starter_block["name"]
    slug = starter_block.get("slug")

    if not slug:
        return {
            "summary": f"{name} ({team_label}) is probable, but there is not much data on him yet.",
            "stability": "Not enough innings yet to get a clean read.",
            "risk": "Not enough data yet for a risk read.",
            "matchup_fit": "Not enough data yet for a matchup read.",
            "watch": "Worth waiting for the lineup to be confirmed before drawing conclusions.",
        }

    stability_map = {
        "Stable Arm": "Reliable — likely to give innings and keep the game under control.",
        "Volatile Arm": "Inconsistent — this start can get away from him early.",
        "Limited Sample": "Not enough innings yet to get a clean read.",
    }
    stability = stability_map.get(starter_block.get("stability"), "Not enough innings yet to get a clean read.")

    risk_bits = []
    if starter_block.get("power_risk") == "Power Risk":
        risk_bits.append("can give up home runs if he leaves a pitch up")
    elif starter_block.get("power_risk") == "Suppresses Power":
        risk_bits.append("keeps the ball in the park well")
    if starter_block.get("contact_risk") == "Contact Pressure Risk":
        risk_bits.append("tends to let hitters put the ball in play and get on base")
    elif starter_block.get("contact_risk") == "Contact Suppression":
        risk_bits.append("limits hard contact")
    if starter_block.get("strikeout_read") == "Strikeout Edge":
        risk_bits.append("can rack up strikeouts to bail himself out of trouble")
    risk = (f"{name} " + ", and ".join(risk_bits) + ".") if risk_bits else f"{name} does not have enough of a track record yet for a clear risk read."

    pressure_read = (opp_pressure_on_this_starter or {}).get("pressure_read")
    danger_bats = (opp_pressure_on_this_starter or {}).get("danger_bats") or []
    if pressure_read in ("Power Pressure", "Balanced Pressure", "Contact Pressure") and danger_bats:
        names = format_player_list([b["name"] for b in danger_bats[:2]])
        verb = "are the hitters" if len(danger_bats[:2]) > 1 else "is the hitter"
        matchup_fit = f"{opp_label} is a tough matchup for {name} — {names} {verb} to watch."
    elif pressure_read == "Limited Read":
        matchup_fit = f"{opp_label}'s lineup is hard to read today, so the matchup against {name} is still developing."
    else:
        matchup_fit = f"{opp_label} does not have a standout threat against {name} today."

    if danger_bats:
        watch = f"Watch {danger_bats[0]['name']} early — if {name} falls behind in the count, that's the spot."
    elif starter_block.get("stability") == "Volatile Arm":
        watch = f"Watch {name}'s pitch count — a rough start could put pressure on the bullpen by the fifth."
    else:
        watch = f"Watch whether {name} can go deep into the game; that's the key to the middle innings."

    return {
        "summary": starter_block.get("summary") or f"{name} is a small-sample read today.",
        "stability": stability,
        "risk": risk,
        "matchup_fit": matchup_fit,
        "watch": watch,
    }


def pitching_shape_and_edge(away_team, home_team, away_block, home_block, away_pm_pitcher, home_pm_pitcher):
    away_ok = away_block and v(away_block.get("name")) and away_block.get("slug")
    home_ok = home_block and v(home_block.get("name")) and home_block.get("slug")

    if not away_ok or not home_ok:
        return "TBD Pitching Matchup", "Starters are not confirmed yet, so the pitching matchup is still developing."

    away_sig = (away_pm_pitcher or {}).get("pitcher_foundation_signal")
    home_sig = (home_pm_pitcher or {}).get("pitcher_foundation_signal")

    if away_block.get("stability") == "Volatile Arm" and home_block.get("stability") == "Volatile Arm":
        return "Volatile Starters", "Both starters have been inconsistent — this game can come down to whichever bullpen holds up better in the middle innings."

    if isinstance(away_sig, (int, float)) and isinstance(home_sig, (int, float)):
        if away_sig >= 65 and home_sig >= 65:
            return "Strong Pitching Matchup", "Both starters have been steady — a mistake pitch is the most likely way this game gets decided."
        if abs(away_sig - home_sig) >= 12:
            leader = away_team if away_sig > home_sig else home_team
            leader_name = away_block["name"] if away_sig > home_sig else home_block["name"]
            return "Starter Edge", f"{leader_name} gives {leader} the stronger starting-pitching edge tonight."

    return "Bullpen Game Risk", "Neither starter has a clear edge, so bullpen usage matters more in this one."


# ---------------------------------------------------------------------------
# Bullpen read
# ---------------------------------------------------------------------------

def bullpen_side_status(team_label, arms):
    if not arms:
        return f"Limited current bullpen data for {team_label}.", 0, 0
    used = sum(1 for a in arms if a.get("usage") == "used")
    light = sum(1 for a in arms if a.get("usage") == "light")
    if used and light:
        status = f"{team_label} has {used} arm(s) already used and {light} arm(s) on lighter usage — some depth, but the freshest options are limited."
    elif light:
        status = f"{team_label}'s bullpen is largely fresh — {light} arm(s) on lighter usage."
    elif used:
        status = f"{team_label} has leaned on {used} arm(s) already — bullpen freshness is a question if the starter exits early."
    else:
        status = f"{team_label} bullpen usage data is limited."
    return status, used, light


def bullpen_read(away_team_name, home_team_name, away_arms, home_arms):
    if not away_arms and not home_arms:
        return {
            "summary": "Limited current bullpen data; watch early starter length.",
            "away_status": "Limited current bullpen data; watch early starter length.",
            "home_status": "Limited current bullpen data; watch early starter length.",
            "leverage_note": "Limited current bullpen data; watch early starter length.",
            "risk": "Limited current bullpen data; watch early starter length.",
            "data_quality": "unavailable",
        }

    away_status, away_used, away_light = bullpen_side_status(away_team_name, away_arms)
    home_status, home_used, home_light = bullpen_side_status(home_team_name, home_arms)

    if away_used > home_used:
        leverage_note = f"{home_team_name} has the fresher bullpen. {away_team_name} is more exposed in the middle innings if its starter does not go deep."
        risk = f"Bullpen stress risk leans toward {away_team_name} if the game gets into traffic early."
    elif home_used > away_used:
        leverage_note = f"{away_team_name} has the fresher bullpen. {home_team_name} is more exposed in the middle innings if its starter does not go deep."
        risk = f"Bullpen stress risk leans toward {home_team_name} if the game gets into traffic early."
    else:
        leverage_note = "Both bullpens carry a similar usage profile — no clear middle-innings edge from bullpen freshness alone."
        risk = "Bullpen risk is balanced; starter length is the bigger lever for both sides."

    data_quality = "fresh" if (away_arms and home_arms) else "limited"

    return {
        "summary": f"{away_status} {home_status}",
        "away_status": away_status,
        "home_status": home_status,
        "leverage_note": leverage_note,
        "risk": risk,
        "data_quality": data_quality,
    }


# ---------------------------------------------------------------------------
# Environment read
# ---------------------------------------------------------------------------

def environment_read(venue, weather, total_line):
    roof = (weather or {}).get("roof") or ""
    sky = v((weather or {}).get("sky"))
    wind = v((weather or {}).get("wind"))
    temp = v((weather or {}).get("temp"))

    park_note = f"{venue} is tonight's park." if v(venue) else "Park data unavailable."

    if roof and roof not in ("No Roof", "Open"):
        run_environment = "Dome/Controlled"
        weather_note = f"Roof status: {roof} — the run environment is controlled regardless of outside conditions."
    elif sky or wind or temp:
        bits = [b for b in (temp, sky, wind) if b]
        weather_note = f"Conditions: {', '.join(bits)}." if bits else "Weather data unavailable."
        if isinstance(total_line, (int, float)):
            if total_line >= 9.5:
                run_environment = "Hitter Lean"
            elif total_line <= 8.0:
                run_environment = "Pitcher Lean"
            else:
                run_environment = "Neutral"
        else:
            run_environment = "Neutral"
    else:
        weather_note = "Weather data unavailable."
        run_environment = "Neutral"

    if isinstance(total_line, (int, float)):
        odds_note = f"Posted run total is {total_line}."
    else:
        odds_note = "Odds unavailable for run total."

    if run_environment == "Dome/Controlled":
        summary = f"{park_note} {weather_note}"
    else:
        summary = f"{park_note} {weather_note} {odds_note}"

    return {
        "summary": summary,
        "run_environment": run_environment,
        "weather_note": weather_note,
        "park_note": park_note,
        "odds_note": odds_note,
    }


# ---------------------------------------------------------------------------
# Players who tilt game
# ---------------------------------------------------------------------------

def players_who_tilt_game(away_team_name, home_team_name, away_team_abbr, home_team_abbr,
                           away_bats, home_bats, away_starter, home_starter,
                           away_pm_pitcher, home_pm_pitcher, il_data):
    seen = set()
    out = []
    display_for = {away_team_abbr: away_team_name, home_team_abbr: home_team_name}

    def add(name, slug, team, tag, reason):
        if not v(name) or name in seen:
            return False
        seen.add(name)
        out.append({"name": name, "slug": slug, "team": team, "tag": tag, "reason": reason})
        return True

    for bats, team_abbr in ((away_bats, away_team_abbr), (home_bats, home_team_abbr)):
        il_names = il_names_for_team(team_abbr, il_data)
        for b in bats:
            if b["full_name"] in il_names:
                continue
            tags = bat_role_tags(b)
            tag = tags[0]
            if tag == "Power Threat":
                reason = f"{b['full_name']} has enough power to change the game with one swing."
            elif tag == "Gets On Base":
                reason = f"{b['full_name']} gets on base and can set up the middle of the order."
            elif tag == "Buy-Low Signal":
                reason = f"{b['full_name']} has been better than his results show — worth watching."
            else:
                reason = f"{b['full_name']} is worth watching in today's lineup."
            add(b["full_name"], b.get("slug"), team_abbr, tag, reason)
            break  # one bat per team per pass; second pass below adds more

    for bats, team_abbr in ((away_bats, away_team_abbr), (home_bats, home_team_abbr)):
        il_names = il_names_for_team(team_abbr, il_data)
        for b in bats:
            if b["full_name"] in il_names or b["full_name"] in seen:
                continue
            tags = bat_role_tags(b)
            tag = "Middle-Order Power" if "Power Threat" not in [t for t in tags] else tags[0]
            team_display = display_for.get(team_abbr, team_abbr)
            if tag == "Power Threat":
                reason = f"{b['full_name']} adds a second power threat to {team_display}'s lineup."
            else:
                reason = f"{b['full_name']} adds another bat who can drive in runs for {team_display}."
            add(b["full_name"], b.get("slug"), team_abbr, tag, reason)
            break

    for starter, team_abbr, pm_pitcher in ((away_starter, away_team_abbr, away_pm_pitcher), (home_starter, home_team_abbr, home_pm_pitcher)):
        if not starter or not v(starter.get("name")) or not starter.get("slug"):
            continue
        name = starter["name"]
        team_display = display_for.get(team_abbr, team_abbr)
        if starter.get("stability") == "Volatile Arm":
            add(name, starter.get("slug"), team_abbr, "Volatile Starter", f"{name} has been inconsistent — this start can get away from him early.")
        else:
            sig = (pm_pitcher or {}).get("pitcher_foundation_signal")
            if isinstance(sig, (int, float)) and sig >= 60:
                add(name, starter.get("slug"), team_abbr, "Starting-Pitching Edge", f"{name} gives {team_display} the stronger starting-pitching edge tonight.")
            elif starter.get("strikeout_read") == "Strikeout Edge":
                add(name, starter.get("slug"), team_abbr, "Strikeout Starter", f"{name} has strikeout upside and can work around trouble.")

    return out[:8]


# ---------------------------------------------------------------------------
# Fantasy / DFS and betting/props
# ---------------------------------------------------------------------------

def fantasy_dfs_watch(tilt_players, bullpen, environment, away_lineup_source, home_lineup_source):
    notes = []
    for p in tilt_players:
        if p["tag"] in ("Power Threat", "Middle-Order Power"):
            notes.append(f"Power Watch: {p['name']} ({p['team']}) is a home run threat worth tracking for DFS.")
        elif p["tag"] == "Gets On Base":
            notes.append(f"DFS On-Base Value: {p['name']} ({p['team']}) gets on base enough to help a DFS stack.")
        elif p["tag"] == "Buy-Low Signal":
            notes.append(f"Buy-Low Watch: {p['name']} ({p['team']}) has been better than his results show — worth watching.")
        elif p["tag"] == "Starting-Pitching Edge":
            notes.append(f"Pitcher Stability: {p['name']} ({p['team']}) is worth watching in DFS lineups — a clean starting-pitching edge tonight.")
        elif p["tag"] == "Volatile Starter":
            notes.append(f"Pitcher Risk: {p['name']} ({p['team']}) has been inconsistent — worth checking before finalizing pitching picks.")
        elif p["tag"] == "Strikeout Starter":
            notes.append(f"Strikeout Watch: {p['name']} ({p['team']}) has strikeout upside in this game.")

    if bullpen.get("data_quality") not in ("unavailable",) and "fresher bullpen" in bullpen.get("leverage_note", ""):
        notes.append(f"Bullpen Exposure: {bullpen['leverage_note']}")

    if environment.get("run_environment") == "Hitter Lean":
        notes.append("Run Environment: Posted total leans hitter-friendly — worth tracking for DFS stacks.")
    elif environment.get("run_environment") == "Pitcher Lean":
        notes.append("Run Environment: Posted total leans pitcher-friendly — worth tracking for pitching picks.")
    elif environment.get("run_environment") == "Dome/Controlled":
        notes.append("Run Environment: Controlled environment removes weather as a factor for DFS planning.")

    if "roster_signals" in (away_lineup_source, home_lineup_source):
        notes.append("Lineup Note: At least one lineup is not confirmed yet — check before locking in DFS picks.")

    deduped = []
    seen = set()
    for n in notes:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped[:8]


def betting_props_watch(away_starter, home_starter, environment, away_team, home_team):
    notes = []
    for starter, team in ((away_starter, away_team), (home_starter, home_team)):
        if not starter or not v(starter.get("name")) or not starter.get("slug"):
            continue
        if starter.get("strikeout_read") == "Strikeout Edge":
            notes.append(f"Strikeout Watch: {starter['name']} has strikeout upside — worth comparing to the posted strikeout prop once lineups are confirmed.")
        if starter.get("power_risk") == "Power Risk":
            opp = home_team if team == away_team else away_team
            notes.append(f"Power Watch: {starter['name']} can give up home runs — {opp}'s home run props are worth watching.")

    if environment.get("run_environment") == "Hitter Lean":
        notes.append("Run Environment: This game's posted total leans hitter-friendly — worth checking against the live line.")
    elif environment.get("run_environment") == "Pitcher Lean":
        notes.append("Run Environment: This game's posted total leans pitcher-friendly — worth watching.")
    elif environment.get("run_environment") == "Unpredictable Game":
        notes.append("Run Environment: Both starters have been inconsistent — the total is worth watching if bullpens get exposed early.")

    deduped = []
    seen = set()
    for n in notes:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped[:5]


# ---------------------------------------------------------------------------
# Game read
# ---------------------------------------------------------------------------

def build_game_read(away_team_name, home_team_name, away_team_abbr, home_team_abbr,
                     shape, pitching_shape, pitching_note, tilt_players, bullpen):
    parts = []
    display_for = {away_team_abbr: away_team_name, home_team_abbr: home_team_name}

    if shape == "Power Game":
        parts.append(f"{away_team_name} at {home_team_name} is a good power matchup — one mistake pitch can leave the yard.")
    elif shape == "Contact Game":
        parts.append(f"{away_team_name} at {home_team_name} is more likely to be decided by rallies than solo home runs.")
    elif shape == "Pitching-Controlled":
        parts.append(f"{away_team_name} at {home_team_name} looks like a pitching-controlled game — neither lineup stands out today.")
    elif shape == "Unpredictable Game":
        parts.append(f"{away_team_name} at {home_team_name} is hard to predict — both starters have been inconsistent, so this can tilt quickly.")
    else:
        parts.append(f"{away_team_name} at {home_team_name} is a balanced matchup — both sides can win this more than one way.")

    parts.append(pitching_note)

    power_tilt = next((p for p in tilt_players if p["tag"] in ("Power Threat", "Middle-Order Power")), None)
    anchor = next((p for p in tilt_players if p["tag"] == "Starting-Pitching Edge"), None)
    if power_tilt:
        team_display = display_for.get(power_tilt["team"], power_tilt["team"])
        parts.append(f"If {team_display} gets into the middle innings with a lead, {power_tilt['name']} is one of the bats that can add on.")
    elif anchor:
        anchor_display = display_for.get(anchor["team"], anchor["team"])
        parts.append(f"{anchor['name']} gives {anchor_display} the stronger starting-pitching edge — the other side needs to apply pressure early.")
    elif bullpen.get("data_quality") == "fresh" and "fresher bullpen" in bullpen.get("leverage_note", ""):
        parts.append(bullpen["leverage_note"])

    return " ".join(parts[:4])


# ---------------------------------------------------------------------------
# Pitch-type matchup (reads from pitch_type_intelligence.json)
# ---------------------------------------------------------------------------

def _ptm_edge_for_bat(hitter_profile, pitcher_profile, hitter_slug, hitter_cards):
    """Return (edge_tag, reason) or (None, None). Nuanced labels — fastball edge is earned."""
    if not hitter_profile or not pitcher_profile:
        return None, None
    best = hitter_profile.get("best_family", "Limited Data")
    primary = pitcher_profile.get("primary_shape", "Limited Data")
    if best == "Limited Data" or primary == "Limited Data":
        return None, None

    fam_profile = (hitter_profile.get("pitch_family_profile") or {}).get(best, {})
    damage = fam_profile.get("damage", "neutral")
    contact = fam_profile.get("contact", "neutral")
    family_mix = pitcher_profile.get("family_mix", {})
    name = hitter_profile.get("name", "")

    if best == "Fastball":
        fb_pct = family_mix.get("Fastball", 0)
        # Only meaningful when pitcher actually relies on fastball family
        if fb_pct < 35 or "Fastball" not in primary:
            return None, None
        card = hitter_cards.get(hitter_slug, {})
        barrel_pct = card.get("barrel_pct") or 0
        if damage == "strong" and barrel_pct >= 12:
            reason = (
                f"{name} can drive the ball against fastballs — {barrel_pct:.1f}% barrel rate, "
                f"a good power matchup against {primary.lower()} pitching."
            )
            return "Fastball Damage", reason
        if damage == "strong" and barrel_pct >= 6:
            reason = (
                f"{name} handles fastballs well — a solid contact matchup against {primary.lower()} pitching."
            )
            return "Handles Fastballs", reason
        if contact == "strong" and damage != "strong":
            reason = (
                f"{name} makes consistent contact against fastballs — "
                f"a good matchup for contact, not necessarily power."
            )
            return "Contact Path", reason
        return None, None

    if best == "Breaking":
        br_pct = family_mix.get("Breaking", 0)
        if br_pct < 20 and "Breaking" not in primary:
            return None, None
        if damage == "strong" or contact == "strong":
            reason = (
                f"{name} handles breaking balls well — "
                f"a workable matchup against {primary.lower()} pitching."
            )
            return "Breaking-Ball Discipline", reason
        return None, None

    if best == "Offspeed":
        os_pct = family_mix.get("Offspeed", 0)
        if os_pct < 15 and "Offspeed" not in primary:
            return None, None
        if damage == "strong" or contact == "strong":
            reason = (
                f"{name} reads offspeed pitches well and can do damage when pitchers lean on them."
            )
            return "Offspeed Recognition", reason
        return None, None

    return None, None


def _ptm_risk_for_bat(hitter_profile, pitcher_profile):
    """Return (risk_tag, reason) or (None, None) if no meaningful signal."""
    if not hitter_profile or not pitcher_profile:
        return None, None
    risk = hitter_profile.get("risk_family", "Limited Data")
    primary = pitcher_profile.get("primary_shape", "Limited Data")
    if risk == "Limited Data" or primary == "Limited Data":
        return None, None

    family_to_shape_keywords = {
        "Fastball": ("Fastball", "Fastball/Breaking", "Fastball/Offspeed"),
        "Breaking": ("Breaking", "Fastball/Breaking", "Breaking-Heavy"),
        "Offspeed": ("Offspeed", "Fastball/Offspeed"),
    }
    keywords = family_to_shape_keywords.get(risk, ())
    if any(k in primary for k in keywords):
        risk_map = {
            "Fastball": "Fastball Risk",
            "Breaking": "Breaking-Ball Risk",
            "Offspeed": "Offspeed Risk",
        }
        risk_tag = risk_map.get(risk, "Limited Data Risk")
        reason = (
            f"{hitter_profile['name']} tends to chase {risk.lower()} pitches — "
            f"a risky spot against {primary.lower()} pitching."
        )
        return risk_tag, reason
    return None, None


def build_pitch_type_matchup(
    away_team_name, home_team_name,
    away_bats, home_bats,
    away_pitcher_slug, home_pitcher_slug,
    pitch_intel,
    hitter_cards,
):
    """Build the pitch_type_matchup block for a game."""
    pitchers = pitch_intel.get("pitchers", {})
    hitters_intel = pitch_intel.get("hitters", {})

    away_p = pitchers.get(away_pitcher_slug) if away_pitcher_slug else None
    home_p = pitchers.get(home_pitcher_slug) if home_pitcher_slug else None

    dq_flags = []
    if not away_p or away_p.get("primary_shape") == "Limited Data":
        dq_flags.append("away_starter_limited")
    if not home_p or home_p.get("primary_shape") == "Limited Data":
        dq_flags.append("home_starter_limited")

    # Pitcher arsenal notes
    away_arsenal_note = (
        away_p.get("summary") if away_p and away_p.get("primary_shape") != "Limited Data"
        else f"Pitch-type data is limited for the {away_team_name} starter."
    )
    home_arsenal_note = (
        home_p.get("summary") if home_p and home_p.get("primary_shape") != "Limited Data"
        else f"Pitch-type data is limited for the {home_team_name} starter."
    )

    # Lineup fit: how does each lineup match against the opposing starter?
    def lineup_fit_note(lineup_bats, opp_pitcher, opp_team_name, batting_team_name):
        if not opp_pitcher or opp_pitcher.get("primary_shape") == "Limited Data":
            return f"Pitch-type lineup fit is limited — {opp_team_name} starter profile unavailable."
        primary = opp_pitcher.get("primary_shape", "")
        best_fits = []
        for bat in lineup_bats[:5]:
            h = hitters_intel.get(bat.get("slug", ""))
            if h and h.get("best_family") != "Limited Data":
                best = h["best_family"]
                if any(k in primary for k in (best, best.split()[0])):
                    best_fits.append(h["name"])
        if best_fits:
            names = format_player_list(best_fits[:3])
            return (
                f"{batting_team_name}'s best matchups against this {primary.lower()} pitcher: "
                f"{names}."
            )
        return (
            f"{batting_team_name} faces a {primary.lower()} pitcher — "
            f"staying patient and waiting for a fastball to drive is the best approach."
        )

    away_lineup_fit = lineup_fit_note(away_bats, home_p, home_team_name, away_team_name)
    home_lineup_fit = lineup_fit_note(home_bats, away_p, away_team_name, home_team_name)

    # Hitters with edge and at risk — fastball-family edges capped at 3 per game
    edge_players = []
    risk_players = []
    seen_edge = set()
    seen_risk = set()
    fastball_edge_count = 0

    for bat in away_bats + home_bats:
        slug = bat.get("slug", "")
        name = bat.get("full_name", bat.get("name", ""))
        if not slug or not name:
            continue
        h = hitters_intel.get(slug)
        if not h:
            continue

        is_away = bat in away_bats
        opp_pitcher = home_p if is_away else away_p
        team_name = away_team_name if is_away else home_team_name

        if slug not in seen_edge:
            edge_tag, edge_reason = _ptm_edge_for_bat(h, opp_pitcher, slug, hitter_cards)
            if edge_tag and edge_reason and len(edge_players) < 4:
                is_fb_edge = edge_tag in FASTBALL_EDGE_LABELS
                if is_fb_edge and fastball_edge_count >= 3:
                    pass  # cap reached — skip this fastball-family label
                else:
                    edge_players.append({
                        "name": name,
                        "slug": slug,
                        "team": team_name,
                        "edge": edge_tag,
                        "reason": edge_reason,
                    })
                    seen_edge.add(slug)
                    if is_fb_edge:
                        fastball_edge_count += 1

        if slug not in seen_risk:
            risk_tag, risk_reason = _ptm_risk_for_bat(h, opp_pitcher)
            if risk_tag and risk_reason and len(risk_players) < 4:
                risk_players.append({
                    "name": name,
                    "slug": slug,
                    "team": team_name,
                    "risk": risk_tag,
                    "reason": risk_reason,
                })
                seen_risk.add(slug)

    # Overall summary
    def matchup_summary(away_p, home_p, edge_players, risk_players, away_team_name, home_team_name):
        if not away_p and not home_p:
            return "Pitch-type data is limited for this matchup — pitcher arsenal profiles are unavailable."
        parts = []
        if away_p and away_p.get("primary_shape") != "Limited Data":
            ap_shape = away_p["primary_shape"]
            parts.append(
                f"{away_team_name}'s starter leans on a {ap_shape.lower()} approach — "
                f"{home_team_name} needs to stay patient and pick the right pitch to drive."
            )
        if home_p and home_p.get("primary_shape") != "Limited Data":
            hp_shape = home_p["primary_shape"]
            parts.append(
                f"{home_team_name}'s starter leans on a {hp_shape.lower()} approach — "
                f"{away_team_name} needs to find the right pitch to do damage."
            )
        if edge_players:
            lead_edge = edge_players[0]
            parts.append(
                f"{lead_edge['name']} is the best matchup among the likely lineup contributors."
            )
        return " ".join(parts[:3]) if parts else "Pitch-type matchup data is limited for this game."

    summary = matchup_summary(away_p, home_p, edge_players, risk_players, away_team_name, home_team_name)

    data_quality = "limited" if len(dq_flags) >= 2 else ("partial" if dq_flags else "available")

    return {
        "summary": summary,
        "pitcher_arsenal_notes": {
            "away_starter": away_arsenal_note,
            "home_starter": home_arsenal_note,
        },
        "lineup_fit": {
            "away_vs_home_starter": away_lineup_fit,
            "home_vs_away_starter": home_lineup_fit,
        },
        "hitters_with_edge": edge_players,
        "hitters_at_risk": risk_players,
        "data_quality": data_quality,
    }


# ---------------------------------------------------------------------------
# Game report (flowing scouting narrative)
# ---------------------------------------------------------------------------

def _format_pitcher_arsenal_prose(pitcher_profile):
    """Convert arsenal data into a specific, number-driven prose sentence."""
    if not pitcher_profile or pitcher_profile.get("primary_shape") == "Limited Data":
        return None
    name = pitcher_profile.get("name", "")
    arsenal = pitcher_profile.get("arsenal") or []
    if not arsenal:
        return pitcher_profile.get("summary")

    primary = arsenal[0]
    primary_str = f"{primary['label']} ({int(round(primary['usage_pct']))}%, {primary['avg_velocity']:.1f}mph)"

    secondary_parts = []
    for p in arsenal[1:4]:
        if p["usage_pct"] >= 8:
            if p.get("whiff_pct") is not None and p["whiff_pct"] >= 28:
                secondary_parts.append(
                    f"{p['label']} ({int(round(p['usage_pct']))}%, {int(round(p['whiff_pct']))}% whiff)"
                )
            else:
                secondary_parts.append(f"{p['label']} ({int(round(p['usage_pct']))}%)")

    if secondary_parts:
        return f"{name}: {primary_str}, {', '.join(secondary_parts)}."
    return f"{name}: {primary_str}."


def _lineup_path_prose(team_name, bats, opp_pitcher_profile, hitters_intel, hitter_cards):
    """Prose describing a team's lineup approach and pitch-type fit against the opposing starter."""
    if not bats:
        return f"{team_name} does not have a standout name in today's lineup."

    power_bats = [b for b in bats if "Power Watch" in (b.get("tags") or [])]
    contact_bats = [b for b in bats if "Contact Edge" in (b.get("tags") or [])]
    buy_low = [b for b in bats if "Buy-Low Bat" in (b.get("tags") or [])]
    opp_shape = (opp_pitcher_profile or {}).get("primary_shape", "")

    parts = []

    power_names = {b["full_name"] for b in power_bats}
    if power_bats:
        damage_names = []
        handle_names = []
        for b in power_bats[:2]:
            slug = b.get("slug", "")
            h = hitters_intel.get(slug, {})
            card = hitter_cards.get(slug, {})
            fb = (h.get("pitch_family_profile") or {}).get("Fastball", {})
            barrel = card.get("barrel_pct") or 0
            if fb.get("damage") == "strong" and barrel >= 12:
                damage_names.append(b["full_name"])
            elif fb.get("damage") == "strong" or fb.get("contact") == "strong":
                handle_names.append(b["full_name"])
        if damage_names:
            n = format_player_list(damage_names)
            verb = "have" if len(damage_names) > 1 else "has"
            parts.append(
                f"{n} {verb} real home run threat — "
                f"{'bats' if len(damage_names) > 1 else 'a bat'} that can punish a mistake fastball."
            )
        elif handle_names:
            n = format_player_list(handle_names[:2])
            verb = "give" if len(handle_names[:2]) > 1 else "gives"
            parts.append(f"{n} {verb} {team_name} a good power matchup — solid contact, though not elite raw power.")
        else:
            names_list = [b["full_name"] for b in power_bats[:2]]
            n = format_player_list(names_list)
            if len(names_list) > 1:
                parts.append(f"{n} are {team_name}'s main power threats.")
            else:
                parts.append(f"{n} is {team_name}'s main power threat.")
    else:
        parts.append(f"{team_name} does not have a clear home run threat today.")

    # Exclude bats already mentioned as power from the contact/traffic line
    contact_only = [b for b in contact_bats if b["full_name"] not in power_names]
    if contact_only:
        names = format_player_list([b["full_name"] for b in contact_only[:2]])
        verb = "give" if len(contact_only[:2]) > 1 else "gives"
        parts.append(f"{names} {verb} {team_name} a good chance to put runners on base ahead of the middle of the order.")

    if opp_shape and opp_shape != "Limited Data":
        best_fits = []
        for b in bats[:6]:
            slug = b.get("slug", "")
            h = hitters_intel.get(slug, {})
            if not h or h.get("best_family") == "Limited Data":
                continue
            best = h["best_family"]
            fam_p = (h.get("pitch_family_profile") or {}).get(best, {})
            if fam_p.get("damage") == "strong" or fam_p.get("contact") == "strong":
                if any(k in opp_shape for k in (best, best.split()[0])):
                    best_fits.append(b["full_name"])
        if best_fits:
            parts.append(f"Good matchups against this {opp_shape.lower()} pitcher: {format_player_list(best_fits[:2])}.")

    if buy_low:
        parts.append(
            f"{buy_low[0]['full_name']} has been better than his results show — worth watching."
        )

    return " ".join(parts[:4])


def build_game_report(
    away_team_name, home_team_name,
    away_team_abbr, home_team_abbr,
    away_bats, home_bats,
    shape, pitching_note,
    pitch_intel, away_pitcher_slug, home_pitcher_slug,
    bp_read, env_read,
    tilt_players,
    hitters_intel, hitter_cards,
):
    """Build the flowing game_report block."""
    pitchers = pitch_intel.get("pitchers", {})

    away_p = pitchers.get(away_pitcher_slug) if away_pitcher_slug else None
    home_p = pitchers.get(home_pitcher_slug) if home_pitcher_slug else None
    display_for = {away_team_abbr: away_team_name, home_team_abbr: home_team_name}

    # ── game_shape ────────────────────────────────────────────────────────
    shape_openers = {
        "Power Game": (
            f"{away_team_name} at {home_team_name} is a good power matchup — "
            f"one mistake pitch from either starter can leave the yard."
        ),
        "Contact Game": (
            f"{away_team_name} and {home_team_name} are more likely to score by "
            f"extending innings than by relying on solo home runs."
        ),
        "Pitching-Controlled": (
            f"{away_team_name} at {home_team_name} looks like a pitching-controlled game — "
            f"neither lineup stands out today."
        ),
        "Unpredictable Game": (
            f"{away_team_name} at {home_team_name} is hard to predict — "
            f"both starters have been inconsistent and this can tilt quickly."
        ),
    }
    opener = shape_openers.get(
        shape,
        f"{away_team_name} at {home_team_name} is a balanced matchup — both sides have multiple ways to score.",
    )

    power_tilt = next((p for p in tilt_players if p["tag"] in ("Power Threat", "Middle-Order Power")), None)
    anchor = next((p for p in tilt_players if p["tag"] == "Starting-Pitching Edge"), None)
    driver = ""
    if power_tilt:
        driver = (
            f"The swing factor: if {power_tilt['name']} gets a fastball to drive, "
            f"the inning changes."
        )
    elif anchor:
        anchor_display = display_for.get(anchor["team"], anchor["team"])
        driver = (
            f"{anchor['name']} gives {anchor_display} the stronger starting-pitching edge — "
            f"the other side needs to apply pressure early."
        )
    elif bp_read.get("data_quality") == "fresh" and "fresher bullpen" in bp_read.get("leverage_note", ""):
        driver = bp_read["leverage_note"]

    env_note = ""
    run_env = env_read.get("run_environment", "")
    if run_env == "Hitter Lean":
        env_note = "The posted total leans hitter-friendly."
    elif run_env == "Dome/Controlled":
        park = env_read.get("park_note", "").replace(" is tonight's park.", "")
        env_note = f"Controlled environment{' at ' + park if park else ''} — no weather to plan around."

    game_shape_parts = [opener, pitching_note]
    if driver:
        game_shape_parts.append(driver)
    if env_note:
        game_shape_parts.append(env_note)
    game_shape = " ".join(game_shape_parts[:4])

    # ── pitching_arsenal_read ─────────────────────────────────────────────
    away_prose = _format_pitcher_arsenal_prose(away_p)
    home_prose = _format_pitcher_arsenal_prose(home_p)
    if away_prose and home_prose:
        pitching_arsenal_read = f"{away_prose} {home_prose}"
    elif away_prose:
        pitching_arsenal_read = f"{away_prose} {home_team_name} starter arsenal data is limited."
    elif home_prose:
        pitching_arsenal_read = f"{away_team_name} starter arsenal data is limited. {home_prose}"
    else:
        pitching_arsenal_read = "Pitch arsenal data is limited for this matchup."

    # ── lineup paths ──────────────────────────────────────────────────────
    away_lineup_path = _lineup_path_prose(away_team_name, away_bats, home_p, hitters_intel, hitter_cards)
    home_lineup_path = _lineup_path_prose(home_team_name, home_bats, away_p, hitters_intel, hitter_cards)

    # ── bullpen + environment ─────────────────────────────────────────────
    bp_parts = []
    lev = bp_read.get("leverage_note", "")
    if lev and "Limited current" not in lev and "balanced" not in lev:
        bp_parts.append(lev)
    else:
        away_st = bp_read.get("away_status", "")
        home_st = bp_read.get("home_status", "")
        if away_st and "Limited current" not in away_st:
            bp_parts.append(away_st)
        elif home_st and "Limited current" not in home_st:
            bp_parts.append(home_st)

    w_note = env_read.get("weather_note", "")
    o_note = env_read.get("odds_note", "")
    if w_note and "unavailable" not in w_note.lower():
        bp_parts.append(w_note)
    if o_note and "unavailable" not in o_note.lower():
        bp_parts.append(o_note)

    bullpen_environment_read = (
        " ".join(bp_parts[:3]) if bp_parts
        else "Bullpen and environment data are limited for this game."
    )

    # ── fantasy / DFS / props ─────────────────────────────────────────────
    fdw = []
    for p in tilt_players:
        slug = p.get("slug", "")
        tag = p["tag"]
        name = p["name"]
        team = p["team"]
        team_display = display_for.get(team, team)
        card = hitter_cards.get(slug, {})
        barrel = card.get("barrel_pct")
        if tag in ("Power Threat", "Middle-Order Power"):
            if barrel and barrel >= 12:
                fdw.append(f"DFS Power: {name} ({team}) — {barrel:.1f}% barrel rate, genuine home run threat.")
            else:
                fdw.append(f"DFS Power: {name} ({team}) — power threat worth tracking for DFS stacks.")
        elif tag == "Gets On Base":
            fdw.append(f"DFS On-Base Value: {name} ({team}) — gives {team_display} a good chance to put runners on base.")
        elif tag == "Buy-Low Signal":
            fdw.append(f"Buy-Low: {name} ({team}) — has been better than his results show.")
        elif tag == "Starting-Pitching Edge":
            fdw.append(f"Pitcher Pick: {name} ({team}) — clean starting-pitching edge, worth watching in DFS lineups.")
        elif tag == "Volatile Starter":
            fdw.append(f"Pitcher Risk: {name} ({team}) — inconsistent, check before finalizing pitching picks.")
        elif tag == "Strikeout Starter":
            fdw.append(f"Strikeout Watch: {name} ({team}) — strikeout upside worth a look.")

    if run_env == "Dome/Controlled":
        fdw.append("Environment: Controlled venue removes weather as a factor for DFS planning.")
    elif run_env == "Hitter Lean":
        fdw.append("Environment: Hitter-friendly total — worth tracking for DFS stacks.")
    elif run_env == "Pitcher Lean":
        fdw.append("Environment: Pitcher-friendly total — worth tracking for pitching picks.")

    return {
        "game_shape": game_shape,
        "pitching_arsenal_read": pitching_arsenal_read,
        "away_lineup_path": away_lineup_path,
        "home_lineup_path": home_lineup_path,
        "bullpen_environment_read": bullpen_environment_read,
        "fantasy_dfs_props_watch": fdw[:6],
    }


# ---------------------------------------------------------------------------
# Matchup board (DOPE-CARD-001A)
# ---------------------------------------------------------------------------

def _pitch_damage_grade(pitch):
    """Green=tough to square up; Red=getting barreled; Yellow=middling; Gray=no data."""
    whiff = pitch.get("whiff_pct")
    hard_hit = pitch.get("hard_hit_pct")
    barrel = pitch.get("barrel_pct")
    bip = pitch.get("bip_count") or 0
    has_contact = bip >= 15 and hard_hit is not None

    if whiff is None and not has_contact:
        return "gray"
    if has_contact and (hard_hit >= 40 or (barrel is not None and barrel >= 10)):
        return "red"
    if whiff is not None and whiff >= 28:
        if not has_contact or (hard_hit < 32 and (barrel is None or barrel < 6)):
            return "green"
    if whiff is not None and whiff < 14 and has_contact and hard_hit >= 35:
        return "red"
    return "yellow"


FAMILY_SHAPE_KEYWORDS = {
    "Fastball": ("Fastball", "Fastball/Breaking", "Fastball/Offspeed"),
    "Breaking": ("Breaking", "Fastball/Breaking", "Breaking-Heavy"),
    "Offspeed": ("Offspeed", "Fastball/Offspeed"),
}


def _hitter_grade_from_card(hitter_card, pitcher_profile):
    """Fallback grade from statcast hitter card when no pitch-type split is available."""
    card = hitter_card or {}
    barrel = card.get("barrel_pct") or 0
    hard_hit = card.get("hard_hit_pct") or 0
    xslg = card.get("xslg") or 0
    has_card = barrel > 0 or hard_hit > 0 or xslg > 0

    if not pitcher_profile or pitcher_profile.get("primary_shape") == "Limited Data":
        if has_card:
            return "gray", "Limited Data", "Not enough pitch-type data yet for this matchup."
        return "gray", "Limited Data", "Not enough data yet for this matchup."

    # Have pitcher shape but no pitch-type split for this hitter
    if barrel >= 12 or hard_hit >= 50:
        return "yellow", "Power Threat", (
            "Limited pitch-type data, but he's a home run threat based on exit velocity."
        )
    if barrel >= 6 or hard_hit >= 40:
        return "yellow", "Hard Contact", (
            "Limited pitch-type data, but he hits the ball hard consistently."
        )
    if xslg >= 0.450:
        return "yellow", "Above-Average Hitter", (
            "Limited pitch-type data, but he's an above-average hitter overall."
        )
    if has_card:
        return "gray", "Limited Data", (
            "Limited pitch-type data; contact profile is average or still developing."
        )
    return "gray", "Limited Data", "Not enough data yet for this matchup."


def _hitter_grade(hitter_profile, pitcher_profile, hitter_card):
    """Return (grade, label, reason) for a hitter vs opposing pitcher arsenal."""
    # No pitch-type profile — fall back to hitter card
    if not hitter_profile:
        return _hitter_grade_from_card(hitter_card, pitcher_profile)

    best = hitter_profile.get("best_family", "Limited Data")
    risk = hitter_profile.get("risk_family", "Limited Data")
    primary_shape = (pitcher_profile or {}).get("primary_shape", "Limited Data")
    family_mix = (pitcher_profile or {}).get("family_mix", {})

    if not pitcher_profile:
        return "gray", "Limited Data", "Not enough pitch-type data yet for this matchup."
    if best == "Limited Data" and risk == "Limited Data":
        return _hitter_grade_from_card(hitter_card, pitcher_profile)
    if primary_shape == "Limited Data":
        return "gray", "Limited Data", "Not enough pitch-type data yet on this pitcher."

    best_pct = family_mix.get(best, 0) if best != "Limited Data" else 0
    risk_pct = family_mix.get(risk, 0) if risk != "Limited Data" else 0
    best_shape_match = best != "Limited Data" and any(k in primary_shape for k in FAMILY_SHAPE_KEYWORDS.get(best, ()))
    risk_shape_match = risk != "Limited Data" and any(k in primary_shape for k in FAMILY_SHAPE_KEYWORDS.get(risk, ()))

    pfp = hitter_profile.get("pitch_family_profile", {})
    best_fam = pfp.get(best, {}) if best != "Limited Data" else {}
    best_damage = best_fam.get("damage", "neutral")
    best_contact = best_fam.get("contact", "neutral")

    card = hitter_card or {}
    barrel_pct = card.get("barrel_pct") or 0
    hard_hit = card.get("hard_hit_pct") or 0

    # ── Green: genuine damage threat — pitch-type split + real barrel production ──
    # "damage=strong" alone means low whiff rate (fastball competence), not power.
    # Green requires BOTH: strong pitch-type fit AND verifiable barrel/power output.
    if best_shape_match and best_pct >= 35:
        if best_damage == "strong" and (barrel_pct >= 10 or hard_hit >= 45):
            label = f"{best} Power"
            if barrel_pct >= 10:
                reason = f"{barrel_pct:.0f}% barrel rate — a good power matchup against {best.lower()} pitching."
            else:
                reason = f"{hard_hit:.0f}% hard-hit rate — a home run threat against {best.lower()} pitching."
            return "green", label, reason

    # ── Yellow: contact fit or partial power signal ──
    if best_shape_match and best_pct >= 25:
        if best_damage == "strong":
            label = f"Handles {best}"
            reason = (
                f"Low whiff rate against {best.lower()} pitching — a strong contact matchup "
                f"against this pitcher, though not a power edge."
            )
            return "yellow", label, reason
        if best_contact == "strong":
            label = f"{best} Contact"
            reason = f"Consistent contact against {best.lower()} pitching — a strong contact matchup, not a power one."
            return "yellow", label, reason

    # ── Red: risk family aligns with pitcher's primary ──
    if risk_shape_match and risk_pct >= 20:
        risk_type_labels = {
            "Fastball": "Fastball Risk",
            "Breaking": "Breaking-Ball Risk",
            "Offspeed": "Offspeed Risk",
        }
        label = risk_type_labels.get(risk, "Risky Spot")
        reason = f"Tends to chase {risk.lower()} pitches — a risky spot against this pitcher."
        return "red", label, reason

    # ── Yellow: weaker signal ──
    if best != "Limited Data" and (best_damage == "strong" or best_contact == "strong"):
        label = "Some Matchup Fit"
        reason = f"Decent {best.lower()} contact, but this pitcher does not throw it enough to call it a real edge."
        return "yellow", label, reason

    if risk != "Limited Data" or best != "Limited Data":
        label = "Neutral Matchup"
        reason = "No clear edge or risk either way — a neutral matchup."
        return "yellow", label, reason

    return _hitter_grade_from_card(hitter_card, pitcher_profile)


def build_matchup_board(
    away_team_name, home_team_name,
    away_starter_block, home_starter_block,
    away_pitcher_slug, home_pitcher_slug,
    away_lineup, home_lineup,
    pitch_intel, hitter_cards, player_index_by_slug,
):
    """Build the matchup_board dict for a game."""
    pitchers = pitch_intel.get("pitchers", {})
    hitters_intel = pitch_intel.get("hitters", {})
    away_p = pitchers.get(away_pitcher_slug) if away_pitcher_slug else None
    home_p = pitchers.get(home_pitcher_slug) if home_pitcher_slug else None

    # Build a lookup from name to slug
    name_to_slug_map = {}
    for p_slug, p_idx in (player_index_by_slug or {}).items():
        if p_idx.get("full_name"):
            name_to_slug_map[p_idx["full_name"].lower()] = p_slug
        if p_idx.get("display_name"):
            name_to_slug_map[p_idx["display_name"].lower()] = p_slug

    def build_pitcher_board(pitcher_profile, starter_block):
        if not pitcher_profile or pitcher_profile.get("primary_shape") == "Limited Data":
            name = (starter_block or {}).get("name", "Unknown")
            hand = (starter_block or {}).get("hand", "")
            return {
                "name": name, "hand": hand, "pitches": [],
                "summary": f"{name}'s pitch-type data is limited.",
                "data_quality": "limited",
            }
        arsenal = pitcher_profile.get("arsenal", [])
        pitches = []
        for pitch in arsenal[:5]:
            pitches.append({
                "pitch": pitch["pitch"],
                "label": pitch["label"],
                "family": pitch["family"],
                "usage_pct": pitch["usage_pct"],
                "whiff_pct": pitch.get("whiff_pct"),
                "avg_velocity": pitch.get("avg_velocity"),
                "hard_hit_pct": pitch.get("hard_hit_pct"),
                "barrel_pct": pitch.get("barrel_pct"),
                "bip_count": pitch.get("bip_count") or 0,
                "damage_grade": _pitch_damage_grade(pitch),
            })
        return {
            "name": pitcher_profile["name"],
            "slug": pitcher_profile.get("slug"),
            "hand": (starter_block or {}).get("hand", pitcher_profile.get("throws", "")),
            "pitches": pitches,
            "primary_shape": pitcher_profile["primary_shape"],
            "summary": pitcher_profile.get("summary", ""),
            "data_quality": "available",
        }

    def build_lineup_board(lineup, opp_pitcher_profile):
        rows = []
        for hitter in sorted(lineup or [], key=lambda h: h.get("batting_order") or 99):
            slug = hitter.get("slug", "")
            name = hitter.get("name", "")
            if not slug and name:
                slug = name_to_slug_map.get(name.lower(), "")
            pos = hitter.get("pos", "")
            order = hitter.get("batting_order")
            h_profile = hitters_intel.get(slug)
            card = hitter_cards.get(slug, {})
            idx_entry = player_index_by_slug.get(slug, {})
            bats = idx_entry.get("bats", "")
            grade, label, reason = _hitter_grade(h_profile, opp_pitcher_profile, card)
            rows.append({
                "name": name, "slug": slug, "pos": pos,
                "batting_order": order, "bats": bats,
                "grade": grade, "label": label, "reason": reason,
            })
        return rows

    away_board = build_pitcher_board(away_p, away_starter_block)
    home_board = build_pitcher_board(home_p, home_starter_block)
    away_lineup_grades = build_lineup_board(away_lineup, home_p)
    home_lineup_grades = build_lineup_board(home_lineup, away_p)

    away_greens = sum(1 for h in away_lineup_grades if h["grade"] == "green")
    home_greens = sum(1 for h in home_lineup_grades if h["grade"] == "green")

    if away_greens > home_greens:
        board_summary = (
            f"{away_team_name}'s lineup has more favorable pitch-type matchups "
            f"({away_greens} green grades vs {home_greens})."
        )
    elif home_greens > away_greens:
        board_summary = (
            f"{home_team_name}'s lineup has more favorable pitch-type matchups "
            f"({home_greens} green grades vs {away_greens})."
        )
    else:
        board_summary = "Both lineups show similar pitch-type matchup grades against today's starters."

    return {
        "away_starter": away_board,
        "home_starter": home_board,
        "away_lineup_vs_home_starter": away_lineup_grades,
        "home_lineup_vs_away_starter": home_lineup_grades,
        "board_summary": board_summary,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        edition_date = read_edition_date()
    except Exception as e:
        print(f"✗ {e}")
        raise SystemExit(1)

    dope_sheet_data = load_json(DOPE_SHEET_DATA_PATH, fallback={})
    schedule = load_json(SCHEDULE_PATH, fallback={})
    game_date = (schedule.get("today") or {}).get("date") or dope_sheet_data.get("date")

    games_raw = dope_sheet_data.get("games") or []

    player_matchups = load_json(PLAYER_MATCHUPS_PATH, fallback={})
    pitcher_matchups = load_json(PITCHER_MATCHUPS_PATH, fallback={})
    odds_data = load_json(ODDS_PATH, fallback={})
    il_data = (load_json(TEAM_IL_PATH, fallback={}) or {}).get("teams", {})
    pitch_intel = load_json(PITCH_INTEL_PATH, fallback={"pitchers": {}, "hitters": {}})
    hitter_cards = (load_json(HITTER_CARDS_PATH, fallback={}) or {}).get("players", {})
    player_index_list = load_json(PLAYER_INDEX_PATH, fallback=[])
    player_index_by_slug = {p["slug"]: p for p in player_index_list if isinstance(p, dict) and p.get("slug")}

    pm_games_list = player_matchups.get("games") or []
    ptm_games_list = pitcher_matchups.get("games") or []

    # Team-pair lists for fallback when positional match fails (e.g. count mismatch)
    pm_by_teams_list: dict = {}
    for _g in pm_games_list:
        pm_by_teams_list.setdefault((_g.get("away_team"), _g.get("home_team")), []).append(_g)

    ptm_by_teams_list: dict = {}
    for _g in ptm_games_list:
        ptm_by_teams_list.setdefault((_g.get("away_team"), _g.get("home_team")), []).append(_g)

    pm_consumed: dict = {}   # (away, home) -> count consumed, for fallback path
    ptm_consumed: dict = {}

    odds_by_teams = {}
    for og in (odds_data.get("games") or []):
        odds_by_teams[(og.get("away_team"), og.get("home_team"))] = og

    games_out = {}

    for ds_idx, g in enumerate(games_raw):
        away_abbr = g.get("away")
        home_abbr = g.get("home")
        away_team_full = g.get("awayFull") or away_abbr
        home_team_full = g.get("homeFull") or home_abbr
        # Short, readable names for generated prose; full names are kept for
        # matching against odds data below.
        away_team_name = team_display_name(away_abbr, away_team_full, home_abbr)
        home_team_name = team_display_name(home_abbr, home_team_full, away_abbr)
        pair = (away_abbr, home_abbr)

        # Positional match (primary): same index in player-matchup list → same game
        if ds_idx < len(pm_games_list) and (pm_games_list[ds_idx].get("away_team"), pm_games_list[ds_idx].get("home_team")) == pair:
            pm = pm_games_list[ds_idx]
        else:
            _candidates = pm_by_teams_list.get(pair, [])
            _idx = pm_consumed.get(pair, 0)
            pm = _candidates[_idx] if _idx < len(_candidates) else {}
        pm_consumed[pair] = pm_consumed.get(pair, 0) + 1

        if ds_idx < len(ptm_games_list) and (ptm_games_list[ds_idx].get("away_team"), ptm_games_list[ds_idx].get("home_team")) == pair:
            ptm = ptm_games_list[ds_idx]
        else:
            _candidates = ptm_by_teams_list.get(pair, [])
            _idx = ptm_consumed.get(pair, 0)
            ptm = _candidates[_idx] if _idx < len(_candidates) else {}
        ptm_consumed[pair] = ptm_consumed.get(pair, 0) + 1
        odds_game = odds_by_teams.get((away_team_full, home_team_full), {})

        away_bats = pm.get("away_bats_to_watch") or []
        home_bats = pm.get("home_bats_to_watch") or []
        away_pressure = pm.get("away_lineup_pressure") or {"profile": "Insufficient data"}
        home_pressure = pm.get("home_lineup_pressure") or {"profile": "Insufficient data"}
        away_lineup_source = pm.get("away_lineup_source", "roster_signals")
        home_lineup_source = pm.get("home_lineup_source", "roster_signals")

        away_starter = ptm.get("away_pitcher")
        home_starter = ptm.get("home_pitcher")
        away_pm_pitcher = (pm.get("probable_pitchers") or {}).get("away")
        home_pm_pitcher = (pm.get("probable_pitchers") or {}).get("home")

        # --- Lineup read ---
        away_lineup_read = lineup_side_read(away_team_name, away_bats, away_pressure, away_lineup_source)
        home_lineup_read = lineup_side_read(home_team_name, home_bats, home_pressure, home_lineup_source)
        shape = matchup_shape(away_pressure, home_pressure, away_starter, home_starter)

        lineup_read = {
            "away": away_lineup_read,
            "home": home_lineup_read,
            "matchup_shape": shape,
        }

        # --- Pitching read ---
        away_starter_read = starter_read(away_team_name, home_team_name, away_starter, ptm.get("home_lineup_vs_away_pitcher"))
        home_starter_read = starter_read(home_team_name, away_team_name, home_starter, ptm.get("away_lineup_vs_home_pitcher"))
        pitching_shape, pitching_note = pitching_shape_and_edge(away_team_name, home_team_name, away_starter, home_starter, away_pm_pitcher, home_pm_pitcher)

        pitching_read = {
            "away_starter": away_starter_read,
            "home_starter": home_starter_read,
            "starter_edge": pitching_note,
            "game_pitching_shape": pitching_shape,
        }

        # --- Bullpen read ---
        bullpen = g.get("bullpen") or {}
        bp_read = bullpen_read(away_team_name, home_team_name, bullpen.get("away") or [], bullpen.get("home") or [])

        # --- Environment read ---
        weather = g.get("weather") or {}
        total_line = None
        fd = (odds_game.get("sportsbooks") or {}).get("fanduel") or (odds_game.get("sportsbooks") or {}).get("draftkings") or {}
        for t in (fd.get("total") or []):
            if isinstance(t.get("point"), (int, float)):
                total_line = t["point"]
                break
        env_read = environment_read(g.get("venue"), weather, total_line)

        # --- Players who tilt game ---
        tilt_players = players_who_tilt_game(
            away_team_name, home_team_name, away_abbr, home_abbr,
            away_bats, home_bats, away_starter, home_starter,
            away_pm_pitcher, home_pm_pitcher, il_data,
        )

        # --- Fantasy/DFS + betting/props ---
        dfs_watch = fantasy_dfs_watch(tilt_players, bp_read, env_read, away_lineup_source, home_lineup_source)
        props_watch = betting_props_watch(away_starter, home_starter, env_read, away_team_name, home_team_name)

        # --- Data basis ---
        data_basis = []
        lineup_labels = {"confirmed_lineup": "Confirmed lineup", "projected_lineup": "Projected lineup", "roster_projection": "Roster projection", "roster_signals": "Roster signal pool"}
        data_basis.append(f"Away: {lineup_labels.get(away_lineup_source, 'Roster signal pool')}")
        data_basis.append(f"Home: {lineup_labels.get(home_lineup_source, 'Roster signal pool')}")
        if away_starter and v(away_starter.get("name")) and away_starter.get("slug") and home_starter and v(home_starter.get("name")) and home_starter.get("slug"):
            data_basis.append("Confirmed probables")
        else:
            data_basis.append("TBD probables")
        data_basis.append("Bullpen usage available" if (bullpen.get("away") or bullpen.get("home")) else "Bullpen data limited")
        weather_present = bool(v((weather or {}).get("sky")) or v((weather or {}).get("temp")) or (weather.get("roof") not in (None, "", "No Roof")))
        data_basis.append("Weather available" if weather_present else "Weather unavailable")
        data_basis.append("Odds available" if total_line is not None else "Odds unavailable")

        # --- Matchup board ---
        away_pitcher_slug = (away_pm_pitcher or {}).get("slug") or (away_starter or {}).get("slug")
        home_pitcher_slug = (home_pm_pitcher or {}).get("slug") or (home_starter or {}).get("slug")
        raw_lineups = g.get("lineups") or {}
        away_lineup_raw = raw_lineups.get("away") or []
        home_lineup_raw = raw_lineups.get("home") or []
        matchup_board = build_matchup_board(
            away_team_name, home_team_name,
            away_starter, home_starter,
            away_pitcher_slug, home_pitcher_slug,
            away_lineup_raw, home_lineup_raw,
            pitch_intel, hitter_cards, player_index_by_slug,
        )

        # --- Pitch-type matchup ---
        pitch_type_matchup = build_pitch_type_matchup(
            away_team_name, home_team_name,
            away_bats, home_bats,
            away_pitcher_slug, home_pitcher_slug,
            pitch_intel,
            hitter_cards,
        )

        # --- Game read ---
        game_read = build_game_read(away_team_name, home_team_name, away_abbr, home_abbr, shape, pitching_shape, pitching_note, tilt_players, bp_read)

        # --- Game report (flowing scouting narrative) ---
        hitters_intel = pitch_intel.get("hitters", {})
        game_report = build_game_report(
            away_team_name, home_team_name,
            away_abbr, home_abbr,
            away_bats, home_bats,
            shape, pitching_note,
            pitch_intel, away_pitcher_slug, home_pitcher_slug,
            bp_read, env_read,
            tilt_players,
            hitters_intel, hitter_cards,
        )

        game_id = pm.get("game_id")
        if game_id is not None:
            key = str(game_id)
        else:
            # Fallback: include time slug to keep doubleheaders distinct
            _time_slug = (g.get("time") or "").replace(" ", "").replace(":", "")
            key = f"{away_abbr}-{home_abbr}-{game_date}-{_time_slug}" if _time_slug else f"{away_abbr}-{home_abbr}-{game_date}"

        games_out[key] = {
            "away_team": away_abbr,
            "home_team": home_abbr,
            "game_id": game_id,
            "game_read": game_read,
            "game_report": game_report,
            "matchup_board": matchup_board,
            "lineup_read": lineup_read,
            "pitching_read": pitching_read,
            "pitch_type_matchup": pitch_type_matchup,
            "bullpen_read": bp_read,
            "environment_read": env_read,
            "players_who_tilt_game": tilt_players,
            "fantasy_dfs_watch": dfs_watch,
            "betting_props_watch": props_watch,
            "data_basis": data_basis,
        }

    meta = {
        "date": game_date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Barrel Proof unified game intelligence",
        "game_count": len(games_out),
    }

    output = {"date": edition_date, "meta": meta, "games": games_out}
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH} with {len(games_out)} games")


if __name__ == "__main__":
    main()
