"""
Readiness checker for Site Data/advanced_scout.json
"""
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PATH = BASE_DIR / "Site Data" / "advanced_scout.json"

BAD_STRINGS = {"nan", "inf", "-inf", "undefined", "none"}

REQUIRED_SERIES_KEYS = {
    "series_id", "away_team", "home_team", "start_date", "end_date",
    "game_count", "games", "barrel_proof_read",
}


def fail(msg):
    print(f"FAIL: {msg}")
    print("ADVANCED SCOUT BLOCKED")
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

    if "meta" not in data or "series" not in data:
        fail("missing meta or series key")

    meta = data["meta"]
    for key in ("edition_date", "covered_dates", "schedule_window", "generated_at", "series_count"):
        if key not in meta:
            fail(f"meta.{key} missing")

    series = data["series"]
    if not isinstance(series, list) or not series:
        fail("series is empty or not a list")

    if meta["series_count"] != len(series):
        fail(f"meta.series_count ({meta['series_count']}) != len(series) ({len(series)})")

    window_start, window_end = meta["schedule_window"]

    seen_series_ids = set()
    team_appearances = {}

    for s in series:
        missing = REQUIRED_SERIES_KEYS - set(s.keys())
        if missing:
            fail(f"series {s.get('series_id')} missing keys: {missing}")

        sid = s["series_id"]
        if sid in seen_series_ids:
            fail(f"duplicate series_id {sid}")
        seen_series_ids.add(sid)

        for team in (s["away_team"], s["home_team"]):
            team_appearances.setdefault(team, []).append(sid)

        if not s["barrel_proof_read"] or not isinstance(s["barrel_proof_read"], str):
            fail(f"series {sid} has empty/invalid barrel_proof_read")

        if not isinstance(s["is_four_game_series"], bool):
            fail(f"series {sid} is_four_game_series must be bool")
        if not isinstance(s["is_thursday_start"], bool):
            fail(f"series {sid} is_thursday_start must be bool")
        if s["is_four_game_series"] and s["game_count"] != 4:
            fail(f"series {sid} is_four_game_series true but game_count={s['game_count']}")
        if s["is_thursday_start"] and s["start_date"] != "2026-06-18":
            fail(f"series {sid} is_thursday_start true but start_date={s['start_date']}")

        if s["game_count"] != len(s["games"]):
            fail(f"series {sid} game_count ({s['game_count']}) != len(games) ({len(s['games'])})")

        for g in s["games"]:
            if not (window_start <= g["date"] <= window_end):
                fail(f"series {sid} game date {g['date']} outside schedule window {window_start}..{window_end}")

        dates_in_series = {gg["date"] for gg in s["games"]}
        if dates_in_series == {"2026-06-18"}:
            fail(f"series {sid} is Thursday-only and should have been excluded")

    # Duplicate teams across series — allowed only for genuine split/double cases
    for team, sids in team_appearances.items():
        if len(sids) > 1:
            fail(f"team {team} appears in multiple series: {sids}")

    walk(data, "advanced_scout")

    print(f"PASS: {len(series)} series, edition_date={meta['edition_date']}, covered_dates={meta['covered_dates']}")
    print("ADVANCED SCOUT READY")


if __name__ == "__main__":
    main()
