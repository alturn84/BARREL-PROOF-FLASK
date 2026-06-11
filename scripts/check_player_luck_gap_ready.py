#!/usr/bin/env python3
"""Validate PLAYER-004A Luck Gap data."""

from __future__ import annotations

import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
LUCK_GAP_PATH = BASE_DIR / "Site Data" / "players" / "hitter_luck_gap.json"
NUMERIC_FIELDS = {"calculated_woba", "xwoba", "luck_gap", "luck_gap_points"}
BAD_STRINGS = {"nan", "inf", "infinity", "-inf", "-infinity", "none", "undefined"}


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path.relative_to(BASE_DIR)} is missing or invalid JSON: {exc}") from exc


def bad_scalar(value):
    return isinstance(value, str) and value.strip().lower() in BAD_STRINGS


def valid_number_or_null(value):
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def main() -> int:
    errors = []
    if not LUCK_GAP_PATH.exists():
        errors.append("Missing Site Data/players/hitter_luck_gap.json")
        data = {}
    else:
        try:
            data = load_json(LUCK_GAP_PATH)
        except ValueError as exc:
            errors.append(str(exc))
            data = {}

    if not isinstance(data, dict):
        errors.append("Site Data/players/hitter_luck_gap.json must be an object")
        data = {}

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("hitter_luck_gap.json missing meta")
    else:
        for field in ("fetch_status", "matched_count", "unmatched_count", "ambiguous_count", "calculated_count"):
            if field not in meta:
                errors.append(f"hitter_luck_gap.json meta missing {field}")

    players = data.get("players")
    if not isinstance(players, dict):
        errors.append("hitter_luck_gap.json players must be an object")
        players = {}

    slugs = []
    calculated_count = 0
    for slug, record in players.items():
        if not isinstance(record, dict):
            errors.append(f"hitter_luck_gap.json player {slug} must be an object")
            continue
        record_slug = record.get("slug")
        full_name = record.get("full_name")
        if not record_slug:
            errors.append(f"hitter_luck_gap.json player {slug} missing slug")
        else:
            slugs.append(record_slug)
        if not full_name:
            errors.append(f"hitter_luck_gap.json player {slug} missing full_name")

        for field in NUMERIC_FIELDS:
            value = record.get(field)
            if bad_scalar(value):
                errors.append(f"hitter_luck_gap.json player {slug}.{field} is invalid")
            elif not valid_number_or_null(value):
                errors.append(f"hitter_luck_gap.json player {slug}.{field} must be numeric or null")

        calculated_woba = record.get("calculated_woba")
        xwoba = record.get("xwoba")
        luck_gap = record.get("luck_gap")
        points = record.get("luck_gap_points")
        if luck_gap is not None:
            calculated_count += 1
            if calculated_woba is None or xwoba is None:
                errors.append(f"hitter_luck_gap.json player {slug} has luck_gap without both calculated_woba and xwoba")
            elif round(xwoba - calculated_woba, 3) != round(luck_gap, 3):
                errors.append(f"hitter_luck_gap.json player {slug} luck_gap does not equal xwoba - calculated_woba")
        if points is not None and luck_gap is None:
            errors.append(f"hitter_luck_gap.json player {slug} has luck_gap_points without luck_gap")

    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        errors.append("Duplicate Luck Gap slugs: " + ", ".join(duplicates))

    if isinstance(meta, dict) and meta.get("fetch_status") != "failed":
        if meta.get("matched_count") != len(players):
            errors.append("matched_count does not match players count")
        if meta.get("calculated_count") != calculated_count:
            errors.append("calculated_count does not match calculated player count")

    if errors:
        print("PLAYER LUCK GAP BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PLAYER LUCK GAP SAFE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
