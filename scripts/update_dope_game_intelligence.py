"""
Build Site Data/dope_game_intelligence.json — a unified per-game intelligence
layer for the Dope Sheet. Combines dope_player_matchups.json,
dope_pitcher_matchups.json, dope-sheet-data.json (bullpen/weather), and
odds.json into one readable "Game Intelligence" read per game.

Pure data layer — no rendering.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

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

TEAM_ABBR_ALIASES = {"AZ": "ARI"}

TEAM_FULL_NAME_TO_ABBR_HINTS = {}


def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def normalize_team_abbr(abbr):
    return TEAM_ABBR_ALIASES.get(abbr, abbr)


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
        out.append("Power Pressure")
    if "Contact Edge" in tags:
        out.append("Contact Table-Setter")
    if "Buy-Low Bat" in tags:
        out.append("Buy-Low Signal")
    if "DFS Watch" in tags and not out:
        out.append("DFS Watch")
    return out or ["Lineup Watch"]


def lineup_side_read(team_label, bats, pressure, lineup_source):
    if not bats:
        return {
            "summary": f"{team_label} lineup signal is limited today — no standout profiles cleared the bar yet.",
            "power_pressure": "Limited current signal data.",
            "contact_pressure": "Limited current signal data.",
            "traffic_path": "Limited current signal data.",
            "risk": "Limited current signal data.",
            "key_bats": [],
        }

    power_bats = [b for b in bats if "Power Watch" in (b.get("tags") or [])]
    contact_bats = [b for b in bats if "Contact Edge" in (b.get("tags") or [])]
    buy_low = [b for b in bats if "Buy-Low Bat" in (b.get("tags") or [])]

    if power_bats:
        names = ", ".join(b["full_name"] for b in power_bats[:2])
        power_pressure = f"{names} give {team_label} a power pocket that can turn one mistake into a separator."
    else:
        power_pressure = f"{team_label} doesn't carry a standout power-pocket bat in today's signal pool."

    if contact_bats:
        names = ", ".join(b["full_name"] for b in contact_bats[:2])
        contact_pressure = f"{names} create contact pressure and traffic if they get on ahead of the middle of the order."
    else:
        contact_pressure = f"{team_label} lacks a clear contact-pressure profile today."

    if contact_bats:
        traffic_path = f"{team_label}'s path to scoring runs through traffic — putting the ball in play and forcing the defense to make plays with runners on."
    elif power_bats:
        traffic_path = f"{team_label}'s path leans on the power pocket rather than traffic — fewer baserunners, but louder mistake punishment."
    else:
        traffic_path = f"{team_label}'s scoring path is unclear from today's signal pool."

    risk_bits = []
    for b in bats:
        if b.get("hitter_profile_type") == "Regression Risk":
            risk_bits.append(f"{b['full_name']} carries a regression-risk profile")
    risk = (", ".join(risk_bits) + "." if risk_bits else "No major volatility flags in today's lineup signal.")

    if power_bats and contact_bats:
        summary = f"{team_label} brings both a power pocket and contact pressure — a balanced lineup that can win this game more than one way."
    elif power_bats:
        summary = f"{team_label} leans on power pressure — one swing can change the separator."
    elif contact_bats:
        summary = f"{team_label} leans on contact pressure and traffic rather than the power pocket."
    else:
        summary = f"{team_label}'s lineup read is limited today; {pressure.get('profile', 'signal pressure').lower()}."

    if buy_low:
        summary += f" {buy_low[0]['full_name']} is a buy-low signal worth tracking — expected production is running ahead of results."

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
        return "Power Pressure"
    if "Contact-heavy pressure" in profiles:
        return "Traffic Game"
    starters_volatile = (
        (away_starter or {}).get("stability") == "Volatile Arm"
        and (home_starter or {}).get("stability") == "Volatile Arm"
    )
    if starters_volatile and not profiles & {"Heavy lineup pressure", "Power-heavy pressure", "Contact-heavy pressure"}:
        return "Volatile Run Environment"
    if profiles <= {"Insufficient data", "Limited signal pressure"}:
        return "Pitching-Controlled"
    return "Balanced Lineup Game"


# ---------------------------------------------------------------------------
# Pitching read
# ---------------------------------------------------------------------------

def starter_read(team_label, opp_label, starter_block, opp_pressure_on_this_starter):
    if not starter_block or not v(starter_block.get("name")):
        return {
            "summary": "Pitching path still developing.",
            "stability": "Probables TBD; lineup and bullpen angles carry more weight until starters are confirmed.",
            "risk": "Probables TBD; lineup and bullpen angles carry more weight until starters are confirmed.",
            "matchup_fit": "Probables TBD; lineup and bullpen angles carry more weight until starters are confirmed.",
            "watch": "Probables TBD; lineup and bullpen angles carry more weight until starters are confirmed.",
        }

    name = starter_block["name"]
    slug = starter_block.get("slug")

    if not slug:
        return {
            "summary": f"{name} ({team_label}) is probable, but signal data is limited — pitching path still developing.",
            "stability": "Limited sample; stability read still developing.",
            "risk": "Limited current sample for a risk read.",
            "matchup_fit": "Limited current sample for a matchup-fit read.",
            "watch": "Limited current sample — watch for confirmed lineup before drawing conclusions.",
        }

    stability_map = {
        "Stable Arm": "Stable arm — likely to give length and shape the middle innings.",
        "Volatile Arm": "Volatile arm — this outing can swing early if traffic builds against them.",
        "Limited Sample": "Limited sample; stability read still developing.",
    }
    stability = stability_map.get(starter_block.get("stability"), "Limited sample; stability read still developing.")

    risk_bits = []
    if starter_block.get("power_risk") == "Power Risk":
        risk_bits.append("carries power risk if they leave pitches in the damage lane")
    elif starter_block.get("power_risk") == "Suppresses Power":
        risk_bits.append("suppresses the power pocket")
    if starter_block.get("contact_risk") == "Contact Pressure Risk":
        risk_bits.append("is vulnerable to contact pressure and traffic")
    elif starter_block.get("contact_risk") == "Contact Suppression":
        risk_bits.append("limits contact quality")
    if starter_block.get("strikeout_read") == "Strikeout Edge":
        risk_bits.append("has a swing-and-miss path to work around traffic")
    risk = (f"{name} " + ", and ".join(risk_bits) + ".") if risk_bits else f"{name} is a small-sample read today — risk profile still developing."

    pressure_read = (opp_pressure_on_this_starter or {}).get("pressure_read")
    danger_bats = (opp_pressure_on_this_starter or {}).get("danger_bats") or []
    if pressure_read in ("Power Pressure", "Balanced Pressure", "Contact Pressure") and danger_bats:
        names = ", ".join(b["name"] for b in danger_bats[:2])
        matchup_fit = f"{opp_label}'s lineup grades as {pressure_read.lower()} against {name} — {names} is the matchup fit to track."
    elif pressure_read == "Limited Read":
        matchup_fit = f"{opp_label}'s lineup signal is limited, so the matchup fit against {name} is still developing."
    else:
        matchup_fit = f"{opp_label}'s lineup doesn't carry a standout threat profile against {name} in today's signal."

    if danger_bats:
        watch = f"Watch {danger_bats[0]['name']} early — if {name} falls behind in counts, that's the leverage point."
    elif starter_block.get("stability") == "Volatile Arm":
        watch = f"Watch {name}'s pitch count — a volatile start can put pressure on the bullpen by the fifth."
    else:
        watch = f"Watch whether {name} gets length; that's the swing factor for the middle innings."

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
        return "TBD Pitching Path", "Probable starter signals are limited for this game, so the pitching path is still developing."

    away_sig = (away_pm_pitcher or {}).get("pitcher_foundation_signal")
    home_sig = (home_pm_pitcher or {}).get("pitcher_foundation_signal")

    if away_block.get("stability") == "Volatile Arm" and home_block.get("stability") == "Volatile Arm":
        return "Volatile Starters", "Both starters carry volatile-arm profiles — this game can tilt on whichever bullpen absorbs the middle innings better."

    if isinstance(away_sig, (int, float)) and isinstance(home_sig, (int, float)):
        if away_sig >= 65 and home_sig >= 65:
            return "Run Prevention Game", "Both starters carry stable run-prevention profiles — mistake punishment is the most likely separator."
        if abs(away_sig - home_sig) >= 12:
            leader = away_team if away_sig > home_sig else home_team
            leader_name = away_block["name"] if away_sig > home_sig else home_block["name"]
            return "Starter Edge", f"{leader_name} gives {leader} the cleaner path with the stronger foundation read in this matchup."

    return "Bullpen Game Risk", "Neither starter holds a clear foundation edge, so middle-innings bullpen usage carries extra weight."


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
        leverage_note = f"{home_team_name} has the fresher bullpen path — {away_team_name} is more exposed in the middle innings if their starter doesn't go deep."
        risk = f"Bullpen stress risk leans toward {away_team_name} if the game gets into traffic early."
    elif home_used > away_used:
        leverage_note = f"{away_team_name} has the fresher bullpen path — {home_team_name} is more exposed in the middle innings if their starter doesn't go deep."
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
            if tag == "Power Pressure":
                reason = f"{b['full_name']} carries a power-pocket profile that can turn one swing into the separator."
            elif tag == "Contact Table-Setter":
                reason = f"{b['full_name']}'s contact profile creates traffic ahead of the middle of the order."
            elif tag == "Buy-Low Signal":
                reason = f"{b['full_name']}'s expected production is running ahead of current results — a buy-low signal."
            else:
                reason = f"{b['full_name']} is a DFS-relevant profile in today's signal pool."
            add(b["full_name"], b.get("slug"), team_abbr, tag, reason)
            break  # one bat per team per pass; second pass below adds more

    for bats, team_abbr in ((away_bats, away_team_abbr), (home_bats, home_team_abbr)):
        il_names = il_names_for_team(team_abbr, il_data)
        for b in bats:
            if b["full_name"] in il_names or b["full_name"] in seen:
                continue
            tags = bat_role_tags(b)
            tag = "Middle-Order Damage" if "Power Pressure" not in [t for t in tags] else tags[0]
            if tag == "Power Pressure":
                reason = f"{b['full_name']} adds a second power-pocket bat to {team_abbr}'s lineup pressure."
            else:
                reason = f"{b['full_name']} adds middle-order damage to {team_abbr}'s lineup."
            add(b["full_name"], b.get("slug"), team_abbr, tag, reason)
            break

    for starter, team_abbr, pm_pitcher in ((away_starter, away_team_abbr, away_pm_pitcher), (home_starter, home_team_abbr, home_pm_pitcher)):
        if not starter or not v(starter.get("name")) or not starter.get("slug"):
            continue
        name = starter["name"]
        if starter.get("stability") == "Volatile Arm":
            add(name, starter.get("slug"), team_abbr, "Volatile Starter", f"{name}'s volatile-arm profile means this start can swing early if traffic builds.")
        else:
            sig = (pm_pitcher or {}).get("pitcher_foundation_signal")
            if isinstance(sig, (int, float)) and sig >= 60:
                add(name, starter.get("slug"), team_abbr, "Run Prevention Anchor", f"{name}'s foundation read gives {team_abbr} the cleaner run-prevention path tonight.")
            elif starter.get("strikeout_read") == "Strikeout Edge":
                add(name, starter.get("slug"), team_abbr, "Traffic Starter", f"{name}'s strikeout edge gives {team_abbr} a swing-and-miss path through traffic.")

    return out[:8]


# ---------------------------------------------------------------------------
# Fantasy / DFS and betting/props
# ---------------------------------------------------------------------------

def fantasy_dfs_watch(tilt_players, bullpen, environment, away_lineup_source, home_lineup_source):
    notes = []
    for p in tilt_players:
        if p["tag"] in ("Power Pressure", "Middle-Order Damage"):
            notes.append(f"Power Watch: {p['name']} ({p['team']}) is a power-pressure angle worth tracking for DFS builds.")
        elif p["tag"] == "Contact Table-Setter":
            notes.append(f"Contact/OBP Watch: {p['name']} ({p['team']})'s table-setter profile is worth tracking for stack consideration.")
        elif p["tag"] == "Buy-Low Signal":
            notes.append(f"Buy-Low Watch: {p['name']} ({p['team']}) is a one-off profile worth tracking — expected production is running ahead of results.")
        elif p["tag"] == "Run Prevention Anchor":
            notes.append(f"Pitcher Stability: {p['name']} ({p['team']}) is worth a profile check for pitching builds — run-prevention path looks clean.")
        elif p["tag"] == "Volatile Starter":
            notes.append(f"Pitcher Risk: {p['name']} ({p['team']})'s volatile profile is worth tracking before finalizing pitching builds.")
        elif p["tag"] == "Traffic Starter":
            notes.append(f"Strikeout Watch: {p['name']} ({p['team']})'s swing-and-miss path is a build consideration in this game.")

    if bullpen.get("data_quality") not in ("unavailable",) and "fresher bullpen path" in bullpen.get("leverage_note", ""):
        notes.append(f"Bullpen Exposure: {bullpen['leverage_note']}")

    if environment.get("run_environment") == "Hitter Lean":
        notes.append("Run Environment: Posted total leans toward a hitter-friendly environment — worth tracking for stack consideration.")
    elif environment.get("run_environment") == "Pitcher Lean":
        notes.append("Run Environment: Posted total leans toward a pitcher-friendly environment — worth tracking for pitching builds.")
    elif environment.get("run_environment") == "Dome/Controlled":
        notes.append("Run Environment: Controlled environment removes weather variance from DFS planning.")

    if "roster_signals" in (away_lineup_source, home_lineup_source):
        notes.append("Lineup-Confirmation Note: At least one lineup is still roster-signal based — confirm before locking builds.")

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
            notes.append(f"Strikeout Watch: {starter['name']}'s swing-and-miss path is worth comparing against the posted K number once lineups are confirmed.")
        if starter.get("power_risk") == "Power Risk":
            opp = home_team if team == away_team else away_team
            notes.append(f"Power Watch: {starter['name']}'s power-risk profile makes {opp} home-run markets worth monitoring.")

    if environment.get("run_environment") == "Hitter Lean":
        notes.append("Run Environment: This game's posted total leans toward a hitter-friendly number — worth checking against the live line.")
    elif environment.get("run_environment") == "Pitcher Lean":
        notes.append("Run Environment: This game's posted total leans toward a pitcher-friendly number — a market to monitor.")
    elif environment.get("run_environment") == "Volatile Run Environment":
        notes.append("Run Environment: Both starters carry volatile profiles — the total is a market to monitor if bullpens get exposed early.")

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

def build_game_read(away_team_name, home_team_name, shape, pitching_shape, pitching_note, tilt_players, bullpen):
    parts = []

    if shape == "Power Pressure":
        parts.append(f"{away_team_name} at {home_team_name} reads as a power-pressure game — one mistake against either power pocket can become the separator.")
    elif shape == "Traffic Game":
        parts.append(f"{away_team_name} at {home_team_name} is a traffic game — the path to runs is contact and baserunners rather than the long ball.")
    elif shape == "Pitching-Controlled":
        parts.append(f"{away_team_name} at {home_team_name} reads as pitching-controlled — neither lineup carries a standout pressure profile today.")
    elif shape == "Volatile Run Environment":
        parts.append(f"{away_team_name} at {home_team_name} is a volatile-run-environment game — both starters carry volatile profiles, so this can tilt quickly.")
    else:
        parts.append(f"{away_team_name} at {home_team_name} is a balanced lineup game — both sides can win this more than one way.")

    parts.append(pitching_note)

    power_tilt = next((p for p in tilt_players if p["tag"] in ("Power Pressure", "Middle-Order Damage")), None)
    anchor = next((p for p in tilt_players if p["tag"] == "Run Prevention Anchor"), None)
    if power_tilt:
        team_full = away_team_name if power_tilt["team"] not in (None,) and power_tilt["team"] == away_team_name else None
        parts.append(f"If {power_tilt['team']} gets into the middle innings with a lead, {power_tilt['name']} turns this into a bullpen-stress game for the other side.")
    elif anchor:
        parts.append(f"{anchor['name']} gives {anchor['team']} the cleaner run-prevention path — the other side's best route is pressure before the middle innings settle.")
    elif bullpen.get("data_quality") == "fresh" and "fresher bullpen path" in bullpen.get("leverage_note", ""):
        parts.append(bullpen["leverage_note"])

    return " ".join(parts[:4])


# ---------------------------------------------------------------------------
# Pitch-type matchup (reads from pitch_type_intelligence.json)
# ---------------------------------------------------------------------------

def _ptm_edge_for_bat(hitter_profile, pitcher_profile):
    """Return (edge_tag, reason) or (None, None) if no meaningful signal."""
    if not hitter_profile or not pitcher_profile:
        return None, None
    best = hitter_profile.get("best_family", "Limited Data")
    primary = pitcher_profile.get("primary_shape", "Limited Data")
    if best == "Limited Data" or primary == "Limited Data":
        return None, None

    family_to_shape_keywords = {
        "Fastball": ("Fastball", "Fastball/Breaking", "Fastball/Offspeed"),
        "Breaking": ("Breaking", "Fastball/Breaking", "Breaking-Heavy"),
        "Offspeed": ("Offspeed", "Fastball/Offspeed"),
    }
    keywords = family_to_shape_keywords.get(best, ())
    if any(k in primary for k in keywords):
        edge_tag = f"{best} Fit"
        reason = (
            f"{hitter_profile['name']} profiles well against {primary.lower()} pitching — "
            f"the {best.lower()} family is a stronger damage lane for this bat."
        )
        return edge_tag, reason
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
            "Fastball": "Fastball Velocity",
            "Breaking": "Breaking Ball Chase",
            "Offspeed": "Offspeed Timing",
        }
        risk_tag = risk_map.get(risk, "Limited Data Risk")
        reason = (
            f"{hitter_profile['name']} carries chase risk against {risk.lower()} pitching — "
            f"the {primary.lower()} shape puts pressure on this bat's expansion tendency."
        )
        return risk_tag, reason
    return None, None


def build_pitch_type_matchup(
    away_team_name, home_team_name,
    away_bats, home_bats,
    away_pitcher_slug, home_pitcher_slug,
    pitch_intel,
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
            names = ", ".join(best_fits[:3])
            return (
                f"{batting_team_name}'s best-fit bats against this {primary.lower()} shape: "
                f"{names}. The pitch-type matchup favors patience and working the primary offering."
            )
        return (
            f"{batting_team_name} faces a {primary.lower()} pitcher — "
            f"the key path is discipline against the primary shape and damage in the fastball window."
        )

    away_lineup_fit = lineup_fit_note(away_bats, home_p, home_team_name, away_team_name)
    home_lineup_fit = lineup_fit_note(home_bats, away_p, away_team_name, home_team_name)

    # Hitters with edge and at risk
    edge_players = []
    risk_players = []
    seen_edge = set()
    seen_risk = set()

    for bat in away_bats + home_bats:
        slug = bat.get("slug", "")
        name = bat.get("full_name", bat.get("name", ""))
        if not slug or not name:
            continue
        h = hitters_intel.get(slug)
        if not h:
            continue

        # Edge: this batter vs opposing starter
        is_away = bat in away_bats
        opp_pitcher = home_p if is_away else away_p
        team_name = away_team_name if is_away else home_team_name

        if slug not in seen_edge:
            edge_tag, edge_reason = _ptm_edge_for_bat(h, opp_pitcher)
            if edge_tag and edge_reason and len(edge_players) < 4:
                edge_players.append({
                    "name": name,
                    "slug": slug,
                    "team": team_name,
                    "edge": edge_tag,
                    "reason": edge_reason,
                })
                seen_edge.add(slug)

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
                f"{away_team_name}'s starter brings a {ap_shape.lower()} approach — "
                f"the {home_team_name} lineup's path runs through pitch discipline and damage timing."
            )
        if home_p and home_p.get("primary_shape") != "Limited Data":
            hp_shape = home_p["primary_shape"]
            parts.append(
                f"{home_team_name}'s starter works from {hp_shape.lower()} shape — "
                f"the {away_team_name} offense needs to find the right window to do damage."
            )
        if edge_players:
            lead_edge = edge_players[0]
            parts.append(
                f"{lead_edge['name']} stands out as the best pitch-type fit among the likely lineup contributors."
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
# Main
# ---------------------------------------------------------------------------

def main():
    dope_sheet_data = load_json(DOPE_SHEET_DATA_PATH, fallback={})
    schedule = load_json(SCHEDULE_PATH, fallback={})
    game_date = (schedule.get("today") or {}).get("date") or dope_sheet_data.get("date")

    games_raw = dope_sheet_data.get("games") or []

    player_matchups = load_json(PLAYER_MATCHUPS_PATH, fallback={})
    pitcher_matchups = load_json(PITCHER_MATCHUPS_PATH, fallback={})
    odds_data = load_json(ODDS_PATH, fallback={})
    il_data = (load_json(TEAM_IL_PATH, fallback={}) or {}).get("teams", {})
    pitch_intel = load_json(PITCH_INTEL_PATH, fallback={"pitchers": {}, "hitters": {}})

    pm_by_teams = {}
    for g in (player_matchups.get("games") or []):
        pm_by_teams[(g.get("away_team"), g.get("home_team"))] = g

    ptm_by_teams = {}
    for g in (pitcher_matchups.get("games") or []):
        ptm_by_teams[(g.get("away_team"), g.get("home_team"))] = g

    odds_by_teams = {}
    for og in (odds_data.get("games") or []):
        odds_by_teams[(og.get("away_team"), og.get("home_team"))] = og

    games_out = {}

    for g in games_raw:
        away_abbr = g.get("away")
        home_abbr = g.get("home")
        away_team_name = g.get("awayFull") or away_abbr
        home_team_name = g.get("homeFull") or home_abbr

        pm = pm_by_teams.get((away_abbr, home_abbr), {})
        ptm = ptm_by_teams.get((away_abbr, home_abbr), {})
        odds_game = odds_by_teams.get((away_team_name, home_team_name), {})

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

        # --- Pitch-type matchup ---
        away_pitcher_slug = (away_pm_pitcher or {}).get("slug") or (away_starter or {}).get("slug")
        home_pitcher_slug = (home_pm_pitcher or {}).get("slug") or (home_starter or {}).get("slug")
        pitch_type_matchup = build_pitch_type_matchup(
            away_team_name, home_team_name,
            away_bats, home_bats,
            away_pitcher_slug, home_pitcher_slug,
            pitch_intel,
        )

        # --- Game read ---
        game_read = build_game_read(away_team_name, home_team_name, shape, pitching_shape, pitching_note, tilt_players, bp_read)

        key = f"{away_abbr}-{home_abbr}-{game_date}"
        games_out[key] = {
            "away_team": away_abbr,
            "home_team": home_abbr,
            "game_read": game_read,
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

    output = {"meta": meta, "games": games_out}
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH} with {len(games_out)} games")


if __name__ == "__main__":
    main()
