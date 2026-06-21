"""
Build Site Data/dope_pitcher_matchups.json from today's Dope Sheet probable
pitchers and the Player V1 pitcher/hitter signal stack.

This is a readable "pitcher matchup intelligence" data layer:
- Starter strikeout / power-risk / contact-risk / stability reads
- Opposing projected/confirmed lineup pressure reads

Pure data layer — no rendering. V1 keeps thresholds simple and documented
inline so they can be tuned later without redesigning the schema.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_date_lib import read_edition_date

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Site Data"
PLAYER_DIR = DATA_DIR / "players"

DOPE_SHEET_DATA_PATH = DATA_DIR / "dope-sheet-data.json"
SCHEDULE_PATH = DATA_DIR / "schedule.json"
PLAYER_INDEX_PATH = PLAYER_DIR / "player_index.json"
PLAYER_ALIASES_PATH = PLAYER_DIR / "player_aliases.json"
PITCHER_FOUNDATION_PATH = PLAYER_DIR / "pitcher_foundation_signal.json"
PITCHER_PROFILE_PATH = PLAYER_DIR / "pitcher_profile_summary.json"
POWER_SIGNAL_PATH = PLAYER_DIR / "hitter_power_signal.json"
CONTACT_SIGNAL_PATH = PLAYER_DIR / "hitter_contact_signal.json"

OUTPUT_PATH = DATA_DIR / "dope_pitcher_matchups.json"

LINEUP_SOURCES_WITH_PLAYERS = ("confirmed_lineup", "projected_lineup", "roster_projection")

# Lineup pressure thresholds, mirrored from update_dope_player_matchups.py
DANGER_BAT_POWER_THRESHOLD = 75
DANGER_BAT_CONTACT_THRESHOLD = 75
MAX_DANGER_BATS = 3


def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def players_by_key(data, key="players"):
    players = data.get(key) if isinstance(data, dict) else None
    return players if isinstance(players, dict) else {}


def resolve_pitcher_slug(name, aliases, foundation_players):
    """Resolve a probable-pitcher full name to a player slug.

    Probable pitchers in dope-sheet-data.json are stored as full names
    (e.g. "Ryan Gusto"). player_aliases.json maps both abbreviated and
    full names to slugs, so try a direct lookup first, then fall back to
    a case-insensitive full_name scan of the pitcher foundation signal.
    """
    if not name:
        return None
    slug = aliases.get(name)
    if slug:
        return slug
    name_lower = str(name).strip().lower()
    for slug, record in foundation_players.items():
        if str(record.get("full_name") or "").strip().lower() == name_lower:
            return slug
    return None


def strikeout_read(foundation):
    """Strikeout read from pitcher_foundation_signal k9 / confidence."""
    if not foundation:
        return "Small Sample"
    k9 = foundation.get("k9")
    confidence = foundation.get("confidence")
    if confidence == "LOW" or not isinstance(k9, (int, float)):
        return "Small Sample"
    if k9 >= 9.5:
        return "Strikeout Edge"
    if k9 <= 6.5:
        return "Low K Ceiling"
    return "Neutral K Profile"


def power_risk_read(foundation):
    """Power risk read from kbb_strength / bb9 as a proxy for command-driven
    home run risk (no batted-ball data available on pitcher foundation)."""
    if not foundation:
        return "Small Sample"
    signal = foundation.get("pitcher_foundation_signal")
    confidence = foundation.get("confidence")
    if confidence == "LOW" or not isinstance(signal, (int, float)):
        return "Small Sample"
    if signal < 40:
        return "Power Risk"
    if signal >= 70:
        return "Suppresses Power"
    return "Neutral Power Risk"


def contact_risk_read(foundation):
    """Contact risk read from whip / k9 — high WHIP + low K9 implies
    hitters are putting the ball in play with regularity."""
    if not foundation:
        return "Small Sample"
    whip = foundation.get("whip")
    k9 = foundation.get("k9")
    confidence = foundation.get("confidence")
    if confidence == "LOW" or not isinstance(whip, (int, float)):
        return "Small Sample"
    if whip >= 1.40 and isinstance(k9, (int, float)) and k9 < 8:
        return "Contact Pressure Risk"
    if whip <= 1.10:
        return "Contact Suppression"
    return "Neutral Contact Profile"


def stability_read(profile, foundation):
    """Stability read from pitcher_profile_summary.profile_type, falling
    back to foundation confidence/sample size."""
    if profile and profile.get("profile_type"):
        ptype = profile["profile_type"]
        if ptype == "Stable Arm":
            return "Stable Arm"
        if ptype == "Volatile Arm":
            return "Volatile Arm"
        return "Limited Sample"
    if not foundation or foundation.get("confidence") == "LOW":
        return "Limited Sample"
    ip = foundation.get("ip")
    if isinstance(ip, (int, float)) and ip < 15:
        return "Limited Sample"
    return "Stable Arm" if (foundation.get("pitcher_foundation_signal") or 0) >= 55 else "Volatile Arm"


def build_pitcher_summary(name, team, k_read, power_read, contact_read, stable_read, slug):
    if not slug:
        return f"{name} signal data unavailable — limited sample."
    parts = []
    if k_read == "Strikeout Edge":
        parts.append("misses bats")
    elif k_read == "Low K Ceiling":
        parts.append("low strikeout ceiling")
    if power_read == "Power Risk":
        parts.append("carries power risk")
    elif power_read == "Suppresses Power":
        parts.append("suppresses power")
    if contact_read == "Contact Pressure Risk":
        parts.append("vulnerable to contact pressure")
    elif contact_read == "Contact Suppression":
        parts.append("limits contact quality")
    if stable_read == "Volatile Arm":
        parts.append("has been volatile")
    if not parts:
        return f"{name} is a small-sample read today."
    return f"{name} " + ", ".join(parts) + "."


def build_starter_block(name, hand, team_abbr, aliases, foundation_players, profile_players):
    if not name:
        return None, {
            "name": None,
            "slug": None,
            "team": team_abbr,
            "throws": None,
            "role": "probable_starter",
            "strikeout_read": "Small Sample",
            "power_risk": "Small Sample",
            "contact_risk": "Small Sample",
            "stability": "Limited Sample",
            "summary": "Probable starter unavailable.",
        }

    slug = resolve_pitcher_slug(name, aliases, foundation_players)
    foundation = foundation_players.get(slug) if slug else None
    profile = profile_players.get(slug) if slug else None

    k_read = strikeout_read(foundation)
    power_read = power_risk_read(foundation)
    contact_read = contact_risk_read(foundation)
    stable_read = stability_read(profile, foundation)

    block = {
        "name": name,
        "slug": slug,
        "team": team_abbr,
        "throws": hand,
        "role": "probable_starter",
        "strikeout_read": k_read,
        "power_risk": power_read,
        "contact_risk": contact_read,
        "stability": stable_read,
        "summary": build_pitcher_summary(name, team_abbr, k_read, power_read, contact_read, stable_read, slug),
    }
    return slug, block


def build_lineup_pressure(lineup_players, lineup_source, player_index_by_name, power_signal, contact_signal):
    """Build a lineup-pressure read for the hitters facing the opposing
    starter. Only uses the confirmed/projected lineup players passed in —
    never falls back to broad roster candidates, preserving DOPE-LINEUPS-001.
    """
    if not lineup_players:
        return {
            "lineup_source": lineup_source,
            "pressure_read": "Limited Read",
            "danger_bats": [],
            "summary": "Lineup not yet available for this game.",
        }

    danger_bats = []
    power_values = []
    contact_values = []

    for p in lineup_players:
        slug = p.get("slug")
        name = p.get("name")
        if not slug:
            continue
        power = power_signal.get(slug)
        contact = contact_signal.get(slug)
        power_score = power.get("power_signal") if isinstance(power, dict) else None
        contact_score = contact.get("contact_signal") if isinstance(contact, dict) else None

        if isinstance(power_score, (int, float)):
            power_values.append(power_score)
        if isinstance(contact_score, (int, float)):
            contact_values.append(contact_score)

        if isinstance(power_score, (int, float)) and power_score >= DANGER_BAT_POWER_THRESHOLD:
            danger_bats.append({"name": name, "slug": slug, "tag": "Power Threat"})
        elif isinstance(contact_score, (int, float)) and contact_score >= DANGER_BAT_CONTACT_THRESHOLD:
            danger_bats.append({"name": name, "slug": slug, "tag": "Contact Threat"})

    danger_bats = danger_bats[:MAX_DANGER_BATS]

    avg_power = sum(power_values) / len(power_values) if power_values else None
    avg_contact = sum(contact_values) / len(contact_values) if contact_values else None

    if avg_power is None and avg_contact is None:
        pressure_read = "Limited Read"
    else:
        p = avg_power or 0
        c = avg_contact or 0
        if p >= 70 and c >= 65:
            pressure_read = "Balanced Pressure"
        elif p >= 70:
            pressure_read = "Power Pressure"
        elif c >= 70:
            pressure_read = "Contact Pressure"
        else:
            pressure_read = "Balanced Pressure"

    if danger_bats:
        names = ", ".join(b["name"] for b in danger_bats)
        summary = f"{pressure_read} — watch for {names}."
    elif pressure_read == "Limited Read":
        summary = "Insufficient hitter signal data for this lineup."
    else:
        summary = f"{pressure_read} lineup with no standout individual threats."

    return {
        "lineup_source": lineup_source,
        "pressure_read": pressure_read,
        "danger_bats": danger_bats,
        "summary": summary,
    }


def build_game_pitching_read(away_team, home_team, away_pitcher, home_pitcher, away_pressure, home_pressure):
    notes = []

    for team, pitcher, opp_pressure in (
        (away_team, away_pitcher, home_pressure),
        (home_team, home_pitcher, away_pressure),
    ):
        if not pitcher.get("slug"):
            continue
        traits = []
        if pitcher["strikeout_read"] == "Strikeout Edge":
            traits.append("strikeout upside")
        if pitcher["power_risk"] == "Power Risk":
            traits.append("power risk")
        if pitcher["contact_risk"] == "Contact Pressure Risk":
            traits.append("contact risk")
        if traits:
            notes.append(f"{team} starter has {' but '.join(traits)}.")

        if opp_pressure["pressure_read"] in ("Power Pressure", "Balanced Pressure", "Contact Pressure") and opp_pressure["danger_bats"]:
            opp_team = home_team if team == away_team else away_team
            notes.append(f"{opp_team} {opp_pressure['lineup_source'].replace('_', ' ')} creates {opp_pressure['pressure_read'].lower()}.")

    return notes


def main():
    try:
        edition_date = read_edition_date()
    except Exception as e:
        print(f"✗ {e}")
        raise SystemExit(1)

    dope_sheet_data = load_json(DOPE_SHEET_DATA_PATH, fallback={})
    schedule = load_json(SCHEDULE_PATH, fallback={})
    schedule_date = (schedule.get("today") or {}).get("date") if isinstance(schedule, dict) else None
    game_date = schedule_date or dope_sheet_data.get("date")

    games_raw = dope_sheet_data.get("games") or []

    aliases = load_json(PLAYER_ALIASES_PATH, fallback={})
    foundation_players = players_by_key(load_json(PITCHER_FOUNDATION_PATH, fallback={}))
    profile_players = players_by_key(load_json(PITCHER_PROFILE_PATH, fallback={}))
    power_signal = players_by_key(load_json(POWER_SIGNAL_PATH, fallback={}))
    contact_signal = players_by_key(load_json(CONTACT_SIGNAL_PATH, fallback={}))
    player_index = load_json(PLAYER_INDEX_PATH, fallback=[])
    player_index_by_name = {
        str(p.get("full_name") or "").strip().lower(): p for p in player_index if isinstance(p, dict)
    }

    games_out = []
    missing_pitcher_count = 0
    limited_sample_count = 0
    lineup_source_counts = {}

    for game in games_raw:
        away_team = game.get("away")
        home_team = game.get("home")
        pitchers = game.get("pitchers") or {}
        away_p = pitchers.get("away") or {}
        home_p = pitchers.get("home") or {}

        away_slug, away_block = build_starter_block(
            away_p.get("name"), away_p.get("hand"), away_team, aliases, foundation_players, profile_players
        )
        home_slug, home_block = build_starter_block(
            home_p.get("name"), home_p.get("hand"), home_team, aliases, foundation_players, profile_players
        )

        for slug, block in ((away_slug, away_block), (home_slug, home_block)):
            if not block.get("name"):
                missing_pitcher_count += 1
            elif not slug or block["stability"] == "Limited Sample":
                limited_sample_count += 1

        lineups = game.get("lineups") or {}
        lineup_sources = game.get("lineup_sources") or {}
        away_lineup = lineups.get("away") or []
        home_lineup = lineups.get("home") or []
        away_source = lineup_sources.get("away", "roster_signals")
        home_source = lineup_sources.get("home", "roster_signals")

        if away_source not in LINEUP_SOURCES_WITH_PLAYERS:
            away_lineup = []
            away_source = "roster_signals"
        if home_source not in LINEUP_SOURCES_WITH_PLAYERS:
            home_lineup = []
            home_source = "roster_signals"

        lineup_source_counts[away_source] = lineup_source_counts.get(away_source, 0) + 1
        lineup_source_counts[home_source] = lineup_source_counts.get(home_source, 0) + 1

        # away_lineup_vs_home_pitcher = pressure the AWAY lineup puts on the HOME pitcher
        away_lineup_pressure = build_lineup_pressure(away_lineup, away_source, player_index_by_name, power_signal, contact_signal)
        home_lineup_pressure = build_lineup_pressure(home_lineup, home_source, player_index_by_name, power_signal, contact_signal)

        game_pitching_read = build_game_pitching_read(
            away_team, home_team, away_block, home_block, away_lineup_pressure, home_lineup_pressure
        )

        games_out.append({
            "game_date": game_date,
            "away_team": away_team,
            "home_team": home_team,
            "away_pitcher": away_block,
            "home_pitcher": home_block,
            "away_lineup_vs_home_pitcher": away_lineup_pressure,
            "home_lineup_vs_away_pitcher": home_lineup_pressure,
            "game_pitching_read": game_pitching_read,
        })

    meta = {
        "date": game_date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Barrel Proof pitcher/player signals",
        "game_count": len(games_out),
    }

    output = {"date": edition_date, "meta": meta, "games": games_out}
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH} with {len(games_out)} games")
    print(f"Missing probable pitchers: {missing_pitcher_count}")
    print(f"Limited-sample pitcher reads: {limited_sample_count}")
    print(f"Lineup source counts: {lineup_source_counts}")


if __name__ == "__main__":
    main()
