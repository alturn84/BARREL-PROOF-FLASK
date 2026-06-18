"""
Build Site Data/dope_player_matchups.json from the Player V1 signal stack
and today's schedule. Pure data layer — no rendering.

This is NOT batter-vs-pitcher historical matchup data. It is Barrel Proof
player-signal matchup intelligence: hitter profile vs. opposing pitcher
profile, lineup power/contact pressure, and deterministic fantasy notes.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Site Data"
PLAYER_DIR = DATA_DIR / "players"

SCHEDULE_PATH = DATA_DIR / "schedule.json"
DOPE_SHEET_DATA_PATH = DATA_DIR / "dope-sheet-data.json"
TEAMS_PATH = DATA_DIR / "teams.json"
PLAYER_INDEX_PATH = PLAYER_DIR / "player_index.json"
POWER_SIGNAL_PATH = PLAYER_DIR / "hitter_power_signal.json"
CONTACT_SIGNAL_PATH = PLAYER_DIR / "hitter_contact_signal.json"
LUCK_GAP_PATH = PLAYER_DIR / "hitter_luck_gap.json"
HITTER_PROFILE_PATH = PLAYER_DIR / "hitter_profile_summary.json"
PITCHER_FOUNDATION_PATH = PLAYER_DIR / "pitcher_foundation_signal.json"
PITCHER_PROFILE_PATH = PLAYER_DIR / "pitcher_profile_summary.json"

OUTPUT_PATH = DATA_DIR / "dope_player_matchups.json"

# Schedule abbreviations that differ from player-data team abbreviations.
TEAM_ABBR_ALIASES = {
    "AZ": "ARI",
}

GOOD_HITTER_PROFILES = [
    "Real Power Bat",
    "Buy-Low Bat",
    "Contact-First Bat",
    "Balanced Producer",
]

MAX_BATS_PER_TEAM = 5


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


def normalize_team_abbr(abbr):
    if not abbr:
        return abbr
    return TEAM_ABBR_ALIASES.get(abbr, abbr)


def build_team_name_lookup():
    data = load_json(TEAMS_PATH, fallback={})
    lookup = {}
    for team in data.get("teams", []):
        abbr = team.get("abbr")
        if abbr:
            lookup[abbr] = team.get("name")
    return lookup


def build_player_index_lookups(player_index):
    by_slug = {}
    by_name_team = {}
    for p in player_index:
        slug = p.get("slug")
        if not slug:
            continue
        by_slug[slug] = p
        name_key = (str(p.get("full_name") or "").strip().lower(), p.get("team_abbr"))
        by_name_team.setdefault(name_key, []).append(p)
    return by_slug, by_name_team


def find_pitcher_record(name, team_abbr, pitcher_foundation, by_name_team):
    """Resolve a probable-pitcher name + team to a pitcher_foundation_signal record."""
    name_key = (str(name or "").strip().lower(), team_abbr)
    candidates = by_name_team.get(name_key, [])
    for candidate in candidates:
        slug = candidate.get("slug")
        record = pitcher_foundation.get(slug)
        if record:
            return slug, record
    # Fall back to direct scan of pitcher_foundation by name + team.
    for slug, record in pitcher_foundation.items():
        if (
            str(record.get("full_name") or "").strip().lower() == str(name or "").strip().lower()
            and record.get("team_abbr") == team_abbr
        ):
            return slug, record
    return None, None


def build_probable_pitcher_block(slug, foundation, profiles):
    if not foundation:
        return None
    profile = profiles.get(slug) if slug else None
    return {
        "slug": slug,
        "full_name": foundation.get("full_name"),
        "team_abbr": foundation.get("team_abbr"),
        "throws": None,
        "pitcher_foundation_signal": foundation.get("pitcher_foundation_signal"),
        "profile_type": profile.get("profile_type") if isinstance(profile, dict) else None,
        "confidence": foundation.get("confidence"),
        "k9": foundation.get("k9"),
        "bb9": foundation.get("bb9"),
        "era": foundation.get("era"),
        "whip": foundation.get("whip"),
    }


def lineup_name_key(name):
    return str(name or "").strip().lower()


def build_bats_to_watch(team_abbr, players_by_team, power_signal, contact_signal, luck_gap, hitter_profile, confirmed_names=None):
    if not team_abbr:
        return []

    confirmed_keys = None
    if confirmed_names:
        confirmed_keys = {lineup_name_key(n) for n in confirmed_names}

    candidates = []
    for p in players_by_team.get(team_abbr, []):
        if p.get("position_group") == "Pitcher":
            continue
        slug = p.get("slug")
        if not slug:
            continue
        if confirmed_keys is not None:
            full_name = lineup_name_key(p.get("full_name"))
            display_name = lineup_name_key(p.get("display_name"))
            if full_name not in confirmed_keys and display_name not in confirmed_keys:
                continue

        power = power_signal.get(slug)
        contact = contact_signal.get(slug)
        luck = luck_gap.get(slug)
        profile = hitter_profile.get(slug)

        power_score = power.get("power_signal") if isinstance(power, dict) else None
        contact_score = contact.get("contact_signal") if isinstance(contact, dict) else None
        luck_points = luck.get("luck_gap_points") if isinstance(luck, dict) else None
        profile_type = profile.get("profile_type") if isinstance(profile, dict) else None

        qualifies = (
            (isinstance(power_score, (int, float)) and power_score >= 75)
            or (isinstance(contact_score, (int, float)) and contact_score >= 75)
            or (profile_type in GOOD_HITTER_PROFILES)
            or (isinstance(luck_points, (int, float)) and luck_points >= 35)
        )
        if not qualifies:
            continue

        composite = 0.0
        composite += 0.35 * (power_score or 0)
        composite += 0.30 * (contact_score or 0)
        composite += 0.15 * min(max(luck_points or 0, 0), 100)
        if profile_type in GOOD_HITTER_PROFILES:
            composite += 20

        tags = []
        if isinstance(power_score, (int, float)) and power_score >= 75:
            tags.append("Power Watch")
        if isinstance(contact_score, (int, float)) and contact_score >= 75:
            tags.append("Contact Edge")
        if profile_type == "Buy-Low Bat":
            tags.append("Buy-Low Bat")
        if profile_type == "Balanced Producer":
            tags.append("Balanced Producer")
        if profile_type == "Regression Risk":
            tags.append("Regression Risk")
        if (
            (isinstance(power_score, (int, float)) and power_score >= 85)
            or (isinstance(contact_score, (int, float)) and contact_score >= 85)
            or (isinstance(luck_points, (int, float)) and luck_points >= 35)
        ):
            tags.append("DFS Watch")

        note_parts = []
        if isinstance(power_score, (int, float)) and power_score >= 75:
            note_parts.append("brings strong power indicators")
        if isinstance(contact_score, (int, float)) and contact_score >= 75:
            note_parts.append("backed by a stable contact profile")
        if isinstance(luck_points, (int, float)) and luck_points >= 35:
            note_parts.append("expected production is running ahead of current results")
        if not note_parts:
            note_parts.append("profile flagged for today's matchup")
        note = f"{p.get('full_name')} {', and '.join(note_parts)}."

        candidates.append({
            "slug": slug,
            "full_name": p.get("full_name"),
            "team_abbr": team_abbr,
            "position": p.get("position"),
            "bats": p.get("bats"),
            "power_signal": power_score,
            "contact_signal": contact_score,
            "luck_gap_points": luck_points,
            "hitter_profile_type": profile_type,
            "confidence": profile.get("confidence") if isinstance(profile, dict) else None,
            "tags": tags,
            "note": note,
            "_composite": composite,
        })

    candidates.sort(key=lambda c: (-c["_composite"], c["full_name"] or ""))
    top = candidates[:MAX_BATS_PER_TEAM]
    for c in top:
        del c["_composite"]
    return top


def build_lineup_pressure(bats_to_watch):
    if not bats_to_watch:
        return {
            "power_score": None,
            "contact_score": None,
            "profile": "Insufficient data",
            "notes": [],
        }

    power_values = [b["power_signal"] for b in bats_to_watch if isinstance(b["power_signal"], (int, float))]
    contact_values = [b["contact_signal"] for b in bats_to_watch if isinstance(b["contact_signal"], (int, float))]

    if not power_values and not contact_values:
        return {
            "power_score": None,
            "contact_score": None,
            "profile": "Insufficient data",
            "notes": [],
        }

    power_score = round(sum(power_values) / len(power_values)) if power_values else None
    contact_score = round(sum(contact_values) / len(contact_values)) if contact_values else None

    p = power_score or 0
    c = contact_score or 0
    if p >= 75 and c >= 65:
        profile = "Heavy lineup pressure"
    elif p >= 75:
        profile = "Power-heavy pressure"
    elif c >= 75:
        profile = "Contact-heavy pressure"
    elif p >= 60 or c >= 60:
        profile = "Moderate lineup pressure"
    else:
        profile = "Limited signal pressure"

    notes = []
    high_signal_names = [b["full_name"] for b in bats_to_watch if "DFS Watch" in b["tags"]]
    if len(high_signal_names) >= 2:
        notes.append(f"Multiple high-signal bats are clustered in this lineup: {', '.join(high_signal_names[:3])}.")

    return {
        "power_score": power_score,
        "contact_score": contact_score,
        "profile": profile,
        "notes": notes,
    }


def build_pitcher_edges(pitcher_block, opponent_team):
    if not pitcher_block:
        return []

    signal = pitcher_block.get("pitcher_foundation_signal")
    k9 = pitcher_block.get("k9")
    confidence = pitcher_block.get("confidence")
    edges = []

    if isinstance(signal, (int, float)) and signal >= 75 and isinstance(k9, (int, float)) and k9 >= 9:
        edges.append("Strikeout Upside")
    if isinstance(signal, (int, float)) and signal >= 75:
        edges.append("Run Prevention Edge")
    if isinstance(signal, (int, float)) and signal < 40:
        edges.append("Pitcher Risk")
    if confidence == "LOW":
        edges.append("Small Sample")

    results = []
    for edge_type in edges:
        if edge_type == "Strikeout Upside":
            note = f"{pitcher_block.get('full_name')} owns a strong foundation with a double-digit K/9 against {opponent_team}."
        elif edge_type == "Run Prevention Edge":
            note = f"{pitcher_block.get('full_name')} carries a strong run-prevention foundation into this matchup."
        elif edge_type == "Pitcher Risk":
            note = f"{pitcher_block.get('full_name')}'s foundation signal points to significant risk against {opponent_team}."
        elif edge_type == "Small Sample":
            note = f"{pitcher_block.get('full_name')}'s read carries a small-sample confidence flag."
        else:
            note = f"{pitcher_block.get('full_name')} flagged for {edge_type}."

        results.append({
            "pitcher_slug": pitcher_block.get("slug"),
            "pitcher_name": pitcher_block.get("full_name"),
            "team_abbr": pitcher_block.get("team_abbr"),
            "opponent_team": opponent_team,
            "edge_type": edge_type,
            "confidence": confidence,
            "pitcher_foundation_signal": signal,
            "pitcher_profile_type": pitcher_block.get("profile_type"),
            "k9": k9,
            "bb9": pitcher_block.get("bb9"),
            "note": note,
        })
    return results


def build_fantasy_watch(away_bats, home_bats, away_pressure, home_pressure, pitcher_edges, away_team, home_team):
    notes = []

    for bats, team in ((away_bats, away_team), (home_bats, home_team)):
        for bat in bats:
            if "Power Watch" in bat["tags"]:
                notes.append(f"Power Watch: {bat['full_name']} brings elite power indicators into today's matchup.")
                break

    for edge in pitcher_edges:
        if edge["edge_type"] == "Strikeout Upside":
            notes.append(f"Strikeout Upside: {edge['pitcher_name']} owns a strong foundation with a double-digit K/9.")
        elif edge["edge_type"] == "Pitcher Risk":
            notes.append(f"Risk Spot: {edge['pitcher_name']}'s foundation signal points to risk against {edge['opponent_team']}.")

    for bats, team in ((away_bats, away_team), (home_bats, home_team)):
        for bat in bats:
            if "Buy-Low Bat" in bat["tags"]:
                notes.append(f"Buy-Low Bat: {bat['full_name']}'s expected production is running ahead of current results.")
                break

    if away_pressure.get("profile") == "Heavy lineup pressure" and away_pressure.get("notes"):
        notes.append(f"Stack Watch: {away_pressure['notes'][0]}")
    if home_pressure.get("profile") == "Heavy lineup pressure" and home_pressure.get("notes"):
        notes.append(f"Stack Watch: {home_pressure['notes'][0]}")

    for edge in pitcher_edges:
        if edge["edge_type"] == "Run Prevention Edge":
            opp_pressure = home_pressure if edge["team_abbr"] == away_team else away_pressure
            if opp_pressure.get("profile") in ("Heavy lineup pressure", "Power-heavy pressure"):
                notes.append(f"Risk Spot: {opp_pressure.get('profile')} lineup faces a {edge['pitcher_profile_type'] or 'strong foundation'} arm in {edge['pitcher_name']}.")

    deduped = []
    seen = set()
    for note in notes:
        if note not in seen:
            seen.add(note)
            deduped.append(note)

    return deduped[:6]


def main():
    schedule = load_json(SCHEDULE_PATH, fallback={})
    today = schedule.get("today") if isinstance(schedule, dict) else {}
    game_date = today.get("date") if isinstance(today, dict) else None
    games_raw = today.get("games") if isinstance(today, dict) else []
    if not isinstance(games_raw, list):
        games_raw = []

    team_names = build_team_name_lookup()

    dope_sheet_data = load_json(DOPE_SHEET_DATA_PATH, fallback={})
    lineups_by_matchup = {}
    for g in (dope_sheet_data.get("games") or []):
        away_lineup = (g.get("lineups") or {}).get("away") or []
        home_lineup = (g.get("lineups") or {}).get("home") or []
        lineup_sources = g.get("lineup_sources") or {}
        lineups_by_matchup[(g.get("away"), g.get("home"))] = {
            "away": [p.get("name") for p in away_lineup if p.get("name")],
            "home": [p.get("name") for p in home_lineup if p.get("name")],
            "away_source": lineup_sources.get("away", "roster_signals"),
            "home_source": lineup_sources.get("home", "roster_signals"),
        }

    player_index_data = load_json(PLAYER_INDEX_PATH, fallback=[])
    player_index = player_index_data if isinstance(player_index_data, list) else []
    by_slug, by_name_team = build_player_index_lookups(player_index)

    players_by_team = {}
    for p in player_index:
        abbr = p.get("team_abbr")
        if abbr:
            players_by_team.setdefault(abbr, []).append(p)

    power_signal = players_by_key(load_json(POWER_SIGNAL_PATH, fallback={}))
    contact_signal = players_by_key(load_json(CONTACT_SIGNAL_PATH, fallback={}))
    luck_gap = players_by_key(load_json(LUCK_GAP_PATH, fallback={}))
    hitter_profile = players_by_key(load_json(HITTER_PROFILE_PATH, fallback={}))
    pitcher_foundation = players_by_key(load_json(PITCHER_FOUNDATION_PATH, fallback={}))
    pitcher_profile = players_by_key(load_json(PITCHER_PROFILE_PATH, fallback={}))

    games_out = []
    pitchers_matched = 0
    games_with_bats = 0

    for game in games_raw:
        away_abbr_raw = game.get("away_abbr")
        home_abbr_raw = game.get("home_abbr")
        away_abbr = normalize_team_abbr(away_abbr_raw)
        home_abbr = normalize_team_abbr(home_abbr_raw)

        away_slug, away_foundation = find_pitcher_record(game.get("away_prob"), away_abbr, pitcher_foundation, by_name_team)
        home_slug, home_foundation = find_pitcher_record(game.get("home_prob"), home_abbr, pitcher_foundation, by_name_team)

        away_pitcher_block = build_probable_pitcher_block(away_slug, away_foundation, pitcher_profile)
        home_pitcher_block = build_probable_pitcher_block(home_slug, home_foundation, pitcher_profile)
        if away_pitcher_block:
            pitchers_matched += 1
        if home_pitcher_block:
            pitchers_matched += 1

        lineups = lineups_by_matchup.get((away_abbr_raw, home_abbr_raw), {})
        away_names = lineups.get("away") or None
        home_names = lineups.get("home") or None
        away_raw_source = lineups.get("away_source", "roster_signals")
        home_raw_source = lineups.get("home_source", "roster_signals")

        if away_names and away_raw_source in ("confirmed_lineup", "projected_lineup", "roster_projection"):
            away_confirmed = away_names
            away_lineup_source = away_raw_source
        else:
            away_confirmed = None
            away_lineup_source = "roster_signals"

        if home_names and home_raw_source in ("confirmed_lineup", "projected_lineup", "roster_projection"):
            home_confirmed = home_names
            home_lineup_source = home_raw_source
        else:
            home_confirmed = None
            home_lineup_source = "roster_signals"

        away_bats = build_bats_to_watch(away_abbr, players_by_team, power_signal, contact_signal, luck_gap, hitter_profile, confirmed_names=away_confirmed)
        home_bats = build_bats_to_watch(home_abbr, players_by_team, power_signal, contact_signal, luck_gap, hitter_profile, confirmed_names=home_confirmed)
        if away_bats or home_bats:
            games_with_bats += 1

        away_pressure = build_lineup_pressure(away_bats)
        home_pressure = build_lineup_pressure(home_bats)

        pitcher_edges = []
        pitcher_edges.extend(build_pitcher_edges(away_pitcher_block, home_abbr_raw))
        pitcher_edges.extend(build_pitcher_edges(home_pitcher_block, away_abbr_raw))

        fantasy_watch = build_fantasy_watch(away_bats, home_bats, away_pressure, home_pressure, pitcher_edges, away_abbr_raw, home_abbr_raw)

        matchup_notes = []
        if away_pitcher_block and home_pitcher_block:
            matchup_notes.append(
                f"{away_pitcher_block.get('full_name')} ({away_pitcher_block.get('profile_type') or 'No profile'}) "
                f"faces {home_pitcher_block.get('full_name')} ({home_pitcher_block.get('profile_type') or 'No profile'})."
            )

        games_out.append({
            "game_id": str(game.get("game_pk")) if game.get("game_pk") is not None else None,
            "game_date": game_date,
            "away_team": away_abbr_raw,
            "home_team": home_abbr_raw,
            "away_team_name": team_names.get(away_abbr),
            "home_team_name": team_names.get(home_abbr),
            "venue": game.get("venue"),
            "lineup_source": away_lineup_source if away_lineup_source == home_lineup_source else "mixed",
            "away_lineup_source": away_lineup_source,
            "home_lineup_source": home_lineup_source,
            "probable_pitchers": {
                "away": away_pitcher_block,
                "home": home_pitcher_block,
            },
            "away_bats_to_watch": away_bats,
            "home_bats_to_watch": home_bats,
            "away_lineup_pressure": away_pressure,
            "home_lineup_pressure": home_pressure,
            "pitcher_edges": pitcher_edges,
            "fantasy_watch": fantasy_watch,
            "matchup_notes": matchup_notes,
        })

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": game_date,
        "season": 2026,
        "source": "Barrel Proof player signal stack",
        "status": "success",
        "game_count": len(games_out),
    }

    output = {"meta": meta, "games": games_out}
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH} with {len(games_out)} games")
    print(f"Probable pitchers matched: {pitchers_matched}")
    print(f"Games with bats_to_watch: {games_with_bats}")


if __name__ == "__main__":
    main()
