#!/usr/bin/env python3
"""Build PLAYER-003A isolated Statcast hitter contact-quality cards."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "Site Data"
PLAYERS_DIR = DATA_DIR / "players"
OUT_FILE = PLAYERS_DIR / "statcast_hitter_cards.json"
SEASON = datetime.now().year

STAT_FIELDS = [
    "avg_exit_velocity",
    "max_exit_velocity",
    "hard_hit_pct",
    "barrel_pct",
    "sweet_spot_pct",
    "xba",
    "xslg",
    "xwoba",
]

EXITVELO_COLUMNS = {
    "avg_exit_velocity": ["avg_hit_speed", "avg_exit_velocity", "avg_ev", "ev"],
    "max_exit_velocity": ["max_hit_speed", "max_exit_velocity", "max_ev"],
    "hard_hit_pct": ["ev95percent", "hard_hit_percent", "hard_hit_pct", "hardhit_percent", "hardhit_pct"],
    "barrel_pct": ["brl_percent", "barrel_pct", "barrel_percent"],
    "sweet_spot_pct": ["anglesweetspotpercent", "sweet_spot_percent", "sweet_spot_pct"],
}

EXPECTED_COLUMNS = {
    "xba": ["xba", "est_ba", "xBA"],
    "xslg": ["xslg", "est_slg", "xSLG"],
    "xwoba": ["xwoba", "est_woba", "xwOBA"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(data) -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lookup_key(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def clean_number(value):
    if value in (None, "", "—"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, 3)


def first_value(row, candidates):
    for column in candidates:
        if column in row:
            value = clean_number(row.get(column))
            if value is not None:
                return value
    return None


def row_name(row) -> str | None:
    for key in ("last_name, first_name", "name", "player_name", "Name"):
        value = row.get(key)
        if not value:
            continue
        text = str(value).strip()
        if key == "last_name, first_name" and "," in text:
            last, first = [part.strip() for part in text.split(",", 1)]
            return f"{first} {last}".strip()
        return text
    return None


def row_player_id(row):
    for key in ("player_id", "playerid", "mlbam_id", "batter"):
        value = row.get(key)
        if value not in (None, "", "—"):
            return str(value)
    return None


def row_team(row):
    for key in ("team", "team_abbr", "Team", "player_team"):
        value = row.get(key)
        if value not in (None, "", "—"):
            team = str(value).upper()
            return "ATH" if team == "OAK" else team
    return None


def build_resolver(players, aliases):
    by_mlbam = {
        str(player.get("mlbam_id")): player
        for player in players
        if player.get("mlbam_id") not in (None, "")
    }
    by_slug = {player.get("slug"): player for player in players if player.get("slug")}
    by_name_team = {}
    by_name = {}
    for player in players:
        team = player.get("team_abbr")
        for name in (player.get("full_name"), player.get("display_name")):
            key = lookup_key(name)
            if not key:
                continue
            by_name_team[(key, team)] = player
            by_name.setdefault(key, []).append(player)

    normalized_aliases = {lookup_key(alias): target for alias, target in aliases.items()}

    def resolve(row):
        source_id = row_player_id(row)
        if source_id and source_id in by_mlbam:
            return by_mlbam[source_id], "mlbam_id"

        name = row_name(row)
        team = row_team(row)
        name_key = lookup_key(name)
        if name_key and team:
            player = by_name_team.get((name_key, team))
            if player:
                return player, "name_team"

        target = normalized_aliases.get(name_key)
        if target and target in by_slug:
            return by_slug[target], "alias"

        candidates = by_name.get(name_key, [])
        if len(candidates) == 1:
            return candidates[0], "unique_name"

        return None, None

    return resolve


def import_pybaseball():
    from pybaseball import cache
    from pybaseball import statcast_batter_exitvelo_barrels
    from pybaseball import statcast_batter_expected_stats

    cache.enable()
    return statcast_batter_exitvelo_barrels, statcast_batter_expected_stats


def dataframe_records(df):
    if df is None:
        return []
    return df.to_dict(orient="records")


def failure_output(error_summary: str):
    return {
        "meta": {
            "generated_at": now_iso(),
            "season": SEASON,
            "source": "pybaseball/statcast",
            "fetch_status": "failed",
            "matched_count": 0,
            "unmatched_count": 0,
            "error": error_summary[:500],
        },
        "players": {},
        "unmatched": [],
    }


def merge_rows(rows, field_map, resolve, players_out, unmatched, seen_unmatched):
    matched = 0
    for row in rows:
        player, method = resolve(row)
        extracted = {
            field: first_value(row, candidates)
            for field, candidates in field_map.items()
        }
        extracted = {field: value for field, value in extracted.items() if value is not None}
        if not extracted:
            continue

        if not player:
            key = (row_name(row), row_team(row), row_player_id(row))
            if key not in seen_unmatched:
                seen_unmatched.add(key)
                unmatched.append({
                    "name": row_name(row),
                    "team_abbr": row_team(row),
                    "source_player_id": row_player_id(row),
                    "available_fields": sorted(extracted.keys()),
                })
            continue

        slug = player.get("slug")
        card = players_out.setdefault(slug, {
            "player_id": player.get("player_id"),
            "slug": slug,
            "full_name": player.get("full_name") or player.get("display_name"),
            "team_abbr": player.get("team_abbr"),
            **{field: None for field in STAT_FIELDS},
        })
        card.update(extracted)
        card["_match_method"] = method
        matched += 1
    return matched


def main():
    players = load_json(PLAYERS_DIR / "player_index.json", [])
    aliases = load_json(PLAYERS_DIR / "player_aliases.json", {})
    if not isinstance(players, list) or not isinstance(aliases, dict):
        write_json(failure_output("PLAYER-001 index or aliases are unavailable."))
        print("PLAYER STATCAST FETCH FAILED: player identity files unavailable")
        return

    try:
        exitvelo_func, expected_func = import_pybaseball()
    except Exception as exc:
        write_json(failure_output(f"pybaseball import failed: {type(exc).__name__}: {exc}"))
        print(f"PLAYER STATCAST FETCH FAILED: pybaseball import failed: {exc}")
        return

    resolve = build_resolver(players, aliases)
    players_out = {}
    unmatched = []
    seen_unmatched = set()
    errors = []

    try:
        exitvelo_rows = dataframe_records(exitvelo_func(SEASON))
        merge_rows(exitvelo_rows, EXITVELO_COLUMNS, resolve, players_out, unmatched, seen_unmatched)
    except Exception as exc:
        errors.append(f"statcast_batter_exitvelo_barrels failed: {type(exc).__name__}: {exc}")

    try:
        expected_rows = dataframe_records(expected_func(SEASON))
        merge_rows(expected_rows, EXPECTED_COLUMNS, resolve, players_out, unmatched, seen_unmatched)
    except Exception as exc:
        errors.append(f"statcast_batter_expected_stats failed: {type(exc).__name__}: {exc}")

    for card in players_out.values():
        card.pop("_match_method", None)

    fetch_status = "success" if players_out and not errors else "partial" if players_out else "failed"
    output = {
        "meta": {
            "generated_at": now_iso(),
            "season": SEASON,
            "source": "pybaseball/statcast",
            "fetch_status": fetch_status,
            "matched_count": len(players_out),
            "unmatched_count": len(unmatched),
        },
        "players": dict(sorted(players_out.items())),
        "unmatched": unmatched,
    }
    if errors:
        output["meta"]["errors"] = errors

    write_json(output)
    print(
        "PLAYER STATCAST "
        f"{fetch_status.upper()}: matched={len(players_out)} unmatched={len(unmatched)}"
    )


if __name__ == "__main__":
    main()
