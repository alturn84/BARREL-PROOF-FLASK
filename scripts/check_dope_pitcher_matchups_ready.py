"""
Readiness checker for Site Data/dope_pitcher_matchups.json
"""
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PATH = BASE_DIR / "Site Data" / "dope_pitcher_matchups.json"
DOPE_SHEET_DATA_PATH = BASE_DIR / "Site Data" / "dope-sheet-data.json"
SCHEDULE_PATH = BASE_DIR / "Site Data" / "schedule.json"
PLAYER_INDEX_PATH = BASE_DIR / "Site Data" / "players" / "player_index.json"

BAD_STRINGS = {"nan", "inf", "-inf", "undefined", "none"}

VALID_LINEUP_SOURCES = {
    "confirmed_lineup", "projected_lineup", "roster_projection", "roster_signals",
}
VALID_PRESSURE_READS = {
    "Power Pressure", "Contact Pressure", "Balanced Pressure", "Limited Read",
}


def fail(msg):
    print(f"FAIL: {msg}")
    print("DOPE PITCHER MATCHUPS BLOCKED")
    raise SystemExit(1)


def is_bad_value(v):
    if isinstance(v, str) and v.strip().lower() in BAD_STRINGS:
        return True
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return True
    return False


def walk(value, path):
    if isinstance(value, dict):
        for k, v in value.items():
            walk(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            walk(v, f"{path}[{i}]")
    else:
        if is_bad_value(value):
            fail(f"{path} has bad value {value!r}")


def main():
    if not PATH.exists():
        fail(f"{PATH} does not exist")

    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"invalid JSON: {e}")

    if "meta" not in data or "games" not in data:
        fail("missing meta or games key")

    games = data["games"]
    if not isinstance(games, list):
        fail("games is not a list")

    if data["meta"].get("game_count") != len(games):
        fail(f"meta.game_count ({data['meta'].get('game_count')}) != games count ({len(games)})")

    # Check meta.date matches schedule/dope-sheet date.
    schedule = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8")) if SCHEDULE_PATH.exists() else {}
    schedule_date = (schedule.get("today") or {}).get("date")
    if schedule_date and data["meta"].get("date") != schedule_date:
        fail(f"meta.date ({data['meta'].get('date')!r}) does not match schedule date ({schedule_date!r})")

    # Check game count matches Dope Sheet games where possible.
    if DOPE_SHEET_DATA_PATH.exists():
        dope_sheet_data = json.loads(DOPE_SHEET_DATA_PATH.read_text(encoding="utf-8"))
        dope_games = dope_sheet_data.get("games") or []
        if len(dope_games) != len(games):
            fail(f"game count ({len(games)}) does not match Dope Sheet games ({len(dope_games)})")

    player_index_data = json.loads(PLAYER_INDEX_PATH.read_text(encoding="utf-8")) if PLAYER_INDEX_PATH.exists() else []
    player_index = player_index_data if isinstance(player_index_data, list) else []
    slugs = {p.get("slug") for p in player_index if p.get("slug")}

    # Build expected pair counts from dope-sheet-data (doubleheaders produce 2 entries).
    expected_pair_counts: dict = {}
    if DOPE_SHEET_DATA_PATH.exists():
        dope_sheet_data = json.loads(DOPE_SHEET_DATA_PATH.read_text(encoding="utf-8"))
        for dg in (dope_sheet_data.get("games") or []):
            pair = (dg.get("away"), dg.get("home"))
            expected_pair_counts[pair] = expected_pair_counts.get(pair, 0) + 1

    seen_game_counts: dict = {}
    for i, game in enumerate(games):
        for field in ("away_team", "home_team", "game_date"):
            if field not in game or game[field] is None:
                fail(f"games[{i}]: missing {field}")

        game_key = (game["away_team"], game["home_team"])
        seen_game_counts[game_key] = seen_game_counts.get(game_key, 0) + 1
        allowed = expected_pair_counts.get(game_key, 1)
        if seen_game_counts[game_key] > allowed:
            fail(f"games[{i}]: duplicate game record for {game_key}")

        for side in ("away_pitcher", "home_pitcher"):
            pitcher = game.get(side)
            if not isinstance(pitcher, dict):
                fail(f"games[{i}]: missing or invalid {side}")
            for field in ("strikeout_read", "power_risk", "contact_risk", "stability", "summary", "role"):
                if field not in pitcher or pitcher[field] is None:
                    fail(f"games[{i}].{side}: missing {field}")
            slug = pitcher.get("slug")
            if slug and slug not in slugs:
                fail(f"games[{i}].{side}: slug {slug!r} not found in player_index")

        for side in ("away_lineup_vs_home_pitcher", "home_lineup_vs_away_pitcher"):
            pressure = game.get(side)
            if not isinstance(pressure, dict):
                fail(f"games[{i}]: missing or invalid {side}")
            source = pressure.get("lineup_source")
            if source not in VALID_LINEUP_SOURCES:
                fail(f"games[{i}].{side}: invalid lineup_source {source!r}")
            if pressure.get("pressure_read") not in VALID_PRESSURE_READS:
                fail(f"games[{i}].{side}: invalid pressure_read {pressure.get('pressure_read')!r}")
            if not isinstance(pressure.get("danger_bats"), list):
                fail(f"games[{i}].{side}: danger_bats must be a list")
            # If a lineup source has no players, danger_bats must be empty.
            if source == "roster_signals" and pressure["danger_bats"]:
                fail(f"games[{i}].{side}: roster_signals source should not have danger_bats")
            for bat in pressure["danger_bats"]:
                slug = bat.get("slug")
                if slug and slug not in slugs:
                    fail(f"games[{i}].{side}: danger bat slug {slug!r} not found in player_index")

        if "game_pitching_read" not in game or not isinstance(game["game_pitching_read"], list):
            fail(f"games[{i}]: missing or invalid game_pitching_read")

        walk(game, f"games[{i}]")

    print(f"OK: {len(games)} games validated")
    print("DOPE PITCHER MATCHUPS SAFE")


if __name__ == "__main__":
    main()
