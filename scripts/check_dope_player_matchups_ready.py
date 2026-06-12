"""
Readiness checker for Site Data/dope_player_matchups.json
"""
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PATH = BASE_DIR / "Site Data" / "dope_player_matchups.json"
PLAYER_INDEX_PATH = BASE_DIR / "Site Data" / "players" / "player_index.json"

BAD_STRINGS = {"nan", "inf", "-inf", "undefined", "none"}


def fail(msg):
    print(f"FAIL: {msg}")
    print("DOPE PLAYER MATCHUPS BLOCKED")
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

    player_index_data = json.loads(PLAYER_INDEX_PATH.read_text(encoding="utf-8")) if PLAYER_INDEX_PATH.exists() else []
    player_index = player_index_data if isinstance(player_index_data, list) else []
    slugs = {p.get("slug") for p in player_index if p.get("slug")}

    muncy_slugs = {p.get("slug") for p in player_index if p.get("full_name") == "Max Muncy"}
    if "max-muncy" not in muncy_slugs or "max-muncy-ath" not in muncy_slugs:
        fail("Max Muncy LAD/ATH slugs not both present in player_index")

    for i, game in enumerate(games):
        for field in ("away_team", "home_team"):
            if field not in game:
                fail(f"games[{i}]: missing {field}")

        for side in ("away", "home"):
            key = f"{side}_bats_to_watch"
            if key not in game or not isinstance(game[key], list):
                fail(f"games[{i}]: missing or invalid {key}")
            for bat in game[key]:
                slug = bat.get("slug")
                if slug and slug not in slugs:
                    fail(f"games[{i}]: bat slug {slug!r} not found in player_index")

            pressure_key = f"{side}_lineup_pressure"
            if pressure_key not in game or not isinstance(game[pressure_key], dict):
                fail(f"games[{i}]: missing or invalid {pressure_key}")

            pitcher = game.get("probable_pitchers", {}).get(side)
            if pitcher:
                pslug = pitcher.get("slug")
                if pslug and pslug not in slugs:
                    fail(f"games[{i}]: pitcher slug {pslug!r} not found in player_index")

        if "pitcher_edges" not in game or not isinstance(game["pitcher_edges"], list):
            fail(f"games[{i}]: missing or invalid pitcher_edges")

        if "fantasy_watch" not in game or not isinstance(game["fantasy_watch"], list):
            fail(f"games[{i}]: missing or invalid fantasy_watch")

        walk(game, f"games[{i}]")

    print(f"OK: {len(games)} games validated")
    print("DOPE PLAYER MATCHUPS SAFE")


if __name__ == "__main__":
    main()
