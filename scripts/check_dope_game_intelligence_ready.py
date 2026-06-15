"""
Readiness checker for Site Data/dope_game_intelligence.json
"""
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PATH = BASE_DIR / "Site Data" / "dope_game_intelligence.json"

BAD_STRINGS = {"nan", "inf", "-inf", "undefined", "none"}

REQUIRED_GAME_KEYS = {
    "away_team", "home_team", "game_read", "lineup_read", "pitching_read",
    "bullpen_read", "environment_read", "players_who_tilt_game",
    "fantasy_dfs_watch", "betting_props_watch", "data_basis",
}


def fail(msg):
    print(f"FAIL: {msg}")
    print("DOPE GAME INTELLIGENCE BLOCKED")
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

    meta = data["meta"]
    for key in ("date", "generated_at", "game_count"):
        if key not in meta:
            fail(f"meta.{key} missing")

    games = data["games"]
    if not isinstance(games, dict) or not games:
        fail("games is empty or not a dict")

    if meta["game_count"] != len(games):
        fail(f"meta.game_count ({meta['game_count']}) != len(games) ({len(games)})")

    for game_id, g in games.items():
        missing = REQUIRED_GAME_KEYS - set(g.keys())
        if missing:
            fail(f"game {game_id} missing keys: {missing}")

        if not g["game_read"] or not isinstance(g["game_read"], str):
            fail(f"game {game_id} has empty/invalid game_read")

        for side in ("away", "home"):
            if side not in g["lineup_read"]:
                fail(f"game {game_id} lineup_read missing {side}")
        if "matchup_shape" not in g["lineup_read"]:
            fail(f"game {game_id} lineup_read missing matchup_shape")

        for side in ("away_starter", "home_starter"):
            if side not in g["pitching_read"]:
                fail(f"game {game_id} pitching_read missing {side}")
        for key in ("starter_edge", "game_pitching_shape"):
            if key not in g["pitching_read"]:
                fail(f"game {game_id} pitching_read missing {key}")

        if not isinstance(g["players_who_tilt_game"], list):
            fail(f"game {game_id} players_who_tilt_game must be a list")

        for p in g["players_who_tilt_game"]:
            for key in ("name", "team", "tag", "reason"):
                if key not in p or not p[key]:
                    fail(f"game {game_id} tilt player missing {key}")

        if not isinstance(g["fantasy_dfs_watch"], list):
            fail(f"game {game_id} fantasy_dfs_watch must be a list")
        if not isinstance(g["betting_props_watch"], list):
            fail(f"game {game_id} betting_props_watch must be a list")
        if not isinstance(g["data_basis"], list):
            fail(f"game {game_id} data_basis must be a list")

    walk(data, "dope_game_intelligence")

    print(f"PASS: {len(games)} games, date={meta['date']}")
    print("DOPE GAME INTELLIGENCE READY")


if __name__ == "__main__":
    main()
