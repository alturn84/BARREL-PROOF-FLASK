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
HITTER_CARDS_PATH = DATA_DIR / "players" / "statcast_hitter_cards.json"
PLAYER_INDEX_PATH = DATA_DIR / "players" / "player_index.json"

FASTBALL_EDGE_LABELS = {"Fastball Damage", "Handles Fastballs", "Contact Path"}

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
                f"{name} punishes fastball pitching — {barrel_pct:.1f}% barrel rate with strong contact in the fastball family. "
                f"The {primary.lower()} shape fits this damage profile."
            )
            return "Fastball Damage", reason
        if damage == "strong" and barrel_pct >= 6:
            reason = (
                f"{name} handles fastball pitching and finds the damage lane — workable contact profile against the {primary.lower()} shape."
            )
            return "Handles Fastballs", reason
        if contact == "strong" and damage != "strong":
            reason = (
                f"{name} makes consistent contact against fastball pitching — "
                f"a contact-path profile against the {primary.lower()} shape, not a power advantage."
            )
            return "Contact Path", reason
        return None, None

    if best == "Breaking":
        br_pct = family_mix.get("Breaking", 0)
        if br_pct < 20 and "Breaking" not in primary:
            return None, None
        if damage == "strong" or contact == "strong":
            reason = (
                f"{name} handles breaking-ball pitching — "
                f"the {primary.lower()} shape is a workable lane for this bat."
            )
            return "Breaking-Ball Discipline", reason
        return None, None

    if best == "Offspeed":
        os_pct = family_mix.get("Offspeed", 0)
        if os_pct < 15 and "Offspeed" not in primary:
            return None, None
        if damage == "strong" or contact == "strong":
            reason = (
                f"{name} recognizes offspeed pitching — finds the contact and damage lane when pitchers lean on that family."
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
        return f"{team_name}'s lineup signal is limited — no standout profiles cleared the bar."

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
            n = ", ".join(damage_names)
            verb = "bring" if len(damage_names) > 1 else "brings"
            parts.append(
                f"{n} {verb} genuine power-damage upside — "
                f"{'bats' if len(damage_names) > 1 else 'a bat'} that {'punish' if len(damage_names) > 1 else 'punishes'} mistakes in the fastball window."
            )
        elif handle_names:
            n = ", ".join(handle_names[:2])
            parts.append(f"{n} give {team_name} a power pocket — workable contact profile, though not elite barrel production.")
        else:
            n = ", ".join(b["full_name"] for b in power_bats[:2])
            verb = "carry" if len(power_bats[:2]) > 1 else "carries"
            parts.append(f"{n} {verb} the power-pressure profile for {team_name}.")
    else:
        parts.append(f"{team_name} doesn't carry a clear power-pocket bat in today's signal pool.")

    # Exclude bats already mentioned as power from the contact/traffic line
    contact_only = [b for b in contact_bats if b["full_name"] not in power_names]
    if contact_only:
        names = ", ".join(b["full_name"] for b in contact_only[:2])
        verb = "run" if len(contact_only[:2]) > 1 else "runs"
        parts.append(f"{names} {verb} the traffic path — contact pressure and baserunners ahead of the middle of the order.")

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
            parts.append(f"Pitch-type fit vs the {opp_shape.lower()} shape: {', '.join(best_fits[:2])}.")

    if buy_low:
        parts.append(
            f"{buy_low[0]['full_name']} is a buy-low signal — expected production is running ahead of current results."
        )

    return " ".join(parts[:4])


def build_game_report(
    away_team_name, home_team_name,
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

    # ── game_shape ────────────────────────────────────────────────────────
    shape_openers = {
        "Power Pressure": (
            f"{away_team_name} at {home_team_name} is a power-pressure game — "
            f"one mistake from either starter can become the separator."
        ),
        "Traffic Game": (
            f"{away_team_name} at {home_team_name} runs on contact and baserunners — "
            f"the scoring path goes through traffic, not the big swing."
        ),
        "Pitching-Controlled": (
            f"{away_team_name} at {home_team_name} reads as a pitching-controlled game — "
            f"neither lineup carries a standout pressure profile today."
        ),
        "Volatile Run Environment": (
            f"{away_team_name} at {home_team_name} is an unpredictable run environment — "
            f"both starters carry volatile profiles and this can tilt quickly."
        ),
    }
    opener = shape_openers.get(
        shape,
        f"{away_team_name} at {home_team_name} is a balanced game — both sides have multiple paths to scoring.",
    )

    power_tilt = next((p for p in tilt_players if p["tag"] in ("Power Pressure", "Middle-Order Damage")), None)
    anchor = next((p for p in tilt_players if p["tag"] == "Run Prevention Anchor"), None)
    driver = ""
    if power_tilt:
        driver = (
            f"The swing factor: if {power_tilt['name']} sees a fastball in the damage zone, "
            f"the inning changes."
        )
    elif anchor:
        driver = (
            f"{anchor['name']} gives {anchor['team']} the cleaner run-prevention path — "
            f"the other side needs to apply pressure before the starter settles."
        )
    elif bp_read.get("data_quality") == "fresh" and "fresher bullpen path" in bp_read.get("leverage_note", ""):
        driver = bp_read["leverage_note"]

    env_note = ""
    run_env = env_read.get("run_environment", "")
    if run_env == "Hitter Lean":
        env_note = "The posted total reflects a hitter-friendly lean."
    elif run_env == "Dome/Controlled":
        park = env_read.get("park_note", "").replace(" is tonight's park.", "")
        env_note = f"Controlled environment{' at ' + park if park else ''} — no weather variable to plan around."

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
        card = hitter_cards.get(slug, {})
        barrel = card.get("barrel_pct")
        if tag in ("Power Pressure", "Middle-Order Damage"):
            if barrel and barrel >= 12:
                fdw.append(f"DFS Power: {name} ({team}) — {barrel:.1f}% barrel rate, genuine power-pocket threat.")
            else:
                fdw.append(f"DFS Power: {name} ({team}) — power-pressure profile worth tracking in stack builds.")
        elif tag == "Contact Table-Setter":
            fdw.append(f"OBP/Stack: {name} ({team}) — table-setter profile is a stack lead consideration.")
        elif tag == "Buy-Low Signal":
            fdw.append(f"Buy-Low: {name} ({team}) — expected production running ahead of current results.")
        elif tag == "Run Prevention Anchor":
            fdw.append(f"Pitcher Build: {name} ({team}) — clean run-prevention path, worth a profile check for pitching builds.")
        elif tag == "Volatile Starter":
            fdw.append(f"Pitcher Risk: {name} ({team}) — volatile profile, check before finalizing pitching builds.")
        elif tag == "Traffic Starter":
            fdw.append(f"Strikeout Watch: {name} ({team}) — swing-and-miss path is a build consideration.")

    if run_env == "Dome/Controlled":
        fdw.append("Environment: Controlled venue removes weather variance from DFS planning.")
    elif run_env == "Hitter Lean":
        fdw.append("Environment: Hitter-friendly total — worth tracking for stack consideration.")
    elif run_env == "Pitcher Lean":
        fdw.append("Environment: Pitcher-friendly total — worth tracking for pitching builds.")

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
            return "gray", "Split limited", "Limited pitch-type split; arsenal data developing."
        return "gray", "Split limited", "Limited pitch-type split; profile data developing."

    # Have pitcher shape but no pitch-type split for this hitter
    if barrel >= 12 or hard_hit >= 50:
        return "yellow", "Power Profile", (
            "Limited pitch-type split; strong power profile — graded from exit velocity data."
        )
    if barrel >= 6 or hard_hit >= 40:
        return "yellow", "Hard Contact", (
            "Limited pitch-type split; solid hard contact rate — graded from Statcast data."
        )
    if xslg >= 0.450:
        return "yellow", "Above-Avg xSLG", (
            "Limited pitch-type split; above-average expected production — graded from Statcast data."
        )
    if has_card:
        return "gray", "Split limited", (
            "Limited pitch-type split; contact profile is average or developing."
        )
    return "gray", "Split limited", "Pitch-type split unavailable; contact data limited."


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
        return "gray", "Split limited", "Limited pitch-type split; arsenal data developing."
    if best == "Limited Data" and risk == "Limited Data":
        return _hitter_grade_from_card(hitter_card, pitcher_profile)
    if primary_shape == "Limited Data":
        return "gray", "Split limited", "Limited pitch-type split; pitcher arsenal data developing."

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
            label = f"{best} Damage"
            if barrel_pct >= 10:
                reason = f"{barrel_pct:.0f}% barrel rate — genuine damage threat in the {best.lower()} family against this arsenal."
            else:
                reason = f"{hard_hit:.0f}% hard-hit rate — power threat in the {best.lower()} family against this arsenal."
            return "green", label, reason

    # ── Yellow: contact fit or partial power signal ──
    if best_shape_match and best_pct >= 25:
        if best_damage == "strong":
            label = f"Handles {best}"
            reason = (
                f"Low whiff rate against {best.lower()} pitching — consistent contact profile "
                f"against the {primary_shape.lower()} shape. Barrel rate does not reach damage threshold."
            )
            return "yellow", label, reason
        if best_contact == "strong":
            label = f"{best} Contact"
            reason = f"Consistent contact against {best.lower()} pitching — contact-path fit, not a power advantage."
            return "yellow", label, reason

    # ── Red: risk family aligns with pitcher's primary ──
    if risk_shape_match and risk_pct >= 20:
        risk_type_labels = {
            "Fastball": "Velocity Risk",
            "Breaking": "Breaking Chase",
            "Offspeed": "Offspeed Timing",
        }
        label = risk_type_labels.get(risk, "Pitch Risk")
        reason = f"Chase tendency against {risk.lower()} pitching — the {primary_shape.lower()} shape targets this bat."
        return "red", label, reason

    # ── Yellow: weaker signal ──
    if best != "Limited Data" and (best_damage == "strong" or best_contact == "strong"):
        label = "Partial Fit"
        reason = f"{best.lower().capitalize()} contact profile — some fit against this arsenal, pitcher usage below threshold."
        return "yellow", label, reason

    if risk != "Limited Data" or best != "Limited Data":
        label = "Neutral"
        reason = "No dominant edge or risk signal — neutral matchup read."
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
        game_read = build_game_read(away_team_name, home_team_name, shape, pitching_shape, pitching_note, tilt_players, bp_read)

        # --- Game report (flowing scouting narrative) ---
        hitters_intel = pitch_intel.get("hitters", {})
        game_report = build_game_report(
            away_team_name, home_team_name,
            away_bats, home_bats,
            shape, pitching_note,
            pitch_intel, away_pitcher_slug, home_pitcher_slug,
            bp_read, env_read,
            tilt_players,
            hitters_intel, hitter_cards,
        )

        key = f"{away_abbr}-{home_abbr}-{game_date}"
        games_out[key] = {
            "away_team": away_abbr,
            "home_team": home_abbr,
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

    output = {"meta": meta, "games": games_out}
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH} with {len(games_out)} games")


if __name__ == "__main__":
    main()
