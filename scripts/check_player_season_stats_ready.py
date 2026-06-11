#!/usr/bin/env python3
"""Validate PLAYER-002B season stat JSON files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"
SEASON_FILES = [
    PLAYERS_DIR / "season_hitter_stats.json",
    PLAYERS_DIR / "season_pitcher_stats.json",
]

HITTER_STRING_FIELDS = {"avg", "obp", "slg", "ops"}
PITCHER_STRING_FIELDS = {"ip"}
COUNT_FIELDS = {
    "games", "pa", "ab", "h", "singles", "doubles", "triples", "hr",
    "rbi", "runs", "sb", "bb", "ibb", "hbp", "sf", "so",
    "games_started", "wins", "losses", "saves",
}
FLOAT_FIELDS = {"era", "whip", "calculated_woba"}
BAD_STRINGS = {"nan", "inf", "infinity", "-inf", "-infinity", "none", "undefined"}
RATE_RE = re.compile(r"^(?:\d+)?\.\d{1,3}$")
IP_RE = re.compile(r"^\d+(?:\.[012])?$")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path.relative_to(BASE_DIR)} is missing or invalid JSON: {exc}") from exc


def bad_scalar(value):
    return isinstance(value, str) and value.strip().lower() in BAD_STRINGS


def valid_number_or_null(value):
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def valid_rate(value):
    if value is None:
        return True
    if bad_scalar(value):
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    return isinstance(value, str) and bool(RATE_RE.match(value.strip()))


def valid_ip(value):
    if value is None:
        return True
    if bad_scalar(value):
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    return isinstance(value, str) and bool(IP_RE.match(value.strip()))


def validate_file(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"Missing {path.relative_to(BASE_DIR)}")
        return

    try:
        data = load_json(path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(data, dict):
        errors.append(f"{path.relative_to(BASE_DIR)} must be an object")
        return

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append(f"{path.relative_to(BASE_DIR)} missing meta")
    else:
        for field in ("matched_count", "unmatched_count", "ambiguous_count", "fetch_status"):
            if field not in meta:
                errors.append(f"{path.relative_to(BASE_DIR)} meta missing {field}")

    players = data.get("players")
    if not isinstance(players, dict):
        errors.append(f"{path.relative_to(BASE_DIR)} players must be an object")
        return

    slugs = []
    string_fields = HITTER_STRING_FIELDS if "hitter" in path.name else PITCHER_STRING_FIELDS
    for slug, record in players.items():
        if not isinstance(record, dict):
            errors.append(f"{path.relative_to(BASE_DIR)} player {slug} must be an object")
            continue
        record_slug = record.get("slug")
        full_name = record.get("full_name")
        if not record_slug:
            errors.append(f"{path.relative_to(BASE_DIR)} player {slug} missing slug")
        else:
            slugs.append(record_slug)
        if not full_name:
            errors.append(f"{path.relative_to(BASE_DIR)} player {slug} missing full_name")

        for field, value in record.items():
            if bad_scalar(value):
                errors.append(f"{path.relative_to(BASE_DIR)} player {slug}.{field} is invalid")
            elif field in string_fields:
                if field == "ip" and not valid_ip(value):
                    errors.append(f"{path.relative_to(BASE_DIR)} player {slug}.{field} must be IP string/number or null")
                elif field != "ip" and not valid_rate(value):
                    errors.append(f"{path.relative_to(BASE_DIR)} player {slug}.{field} must be rate string/number or null")
            elif field in COUNT_FIELDS | FLOAT_FIELDS and not valid_number_or_null(value):
                errors.append(f"{path.relative_to(BASE_DIR)} player {slug}.{field} must be number or null")

        singles = record.get("singles")
        if singles is not None and isinstance(singles, (int, float)) and singles < 0:
            errors.append(f"{path.relative_to(BASE_DIR)} player {slug}.singles must not be negative")

    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        errors.append(f"{path.relative_to(BASE_DIR)} duplicate slugs: " + ", ".join(duplicates))

    if isinstance(meta, dict) and meta.get("fetch_status") != "failed":
        if meta.get("matched_count") != len(players):
            errors.append(f"{path.relative_to(BASE_DIR)} matched_count does not match players count")


def main() -> int:
    errors = []
    for path in SEASON_FILES:
        validate_file(path, errors)

    if errors:
        print("PLAYER SEASON STATS BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PLAYER SEASON STATS SAFE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
