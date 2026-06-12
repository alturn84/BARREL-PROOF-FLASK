#!/usr/bin/env python3
"""Validate PLAYER-008A hitter profile summary data."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PROFILE_PATH = BASE_DIR / "Site Data" / "players" / "hitter_profile_summary.json"
ALLOWED_PROFILE_TYPES = {
    "Real Power Bat",
    "Buy-Low Bat",
    "Regression Risk",
    "Volatile Slugger",
    "Contact-First Bat",
    "Balanced Producer",
    "Watch List",
    "Insufficient Data",
}
CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW"}
BAD_STRINGS = {"nan", "inf", "infinity", "-inf", "-infinity", "none", "undefined"}


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path.relative_to(BASE_DIR)} is missing or invalid JSON: {exc}") from exc


def bad_scalar(value):
    return isinstance(value, str) and value.strip().lower() in BAD_STRINGS


def valid_number_or_null(value):
    return value is None or (
        isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isnan(value) and not math.isinf(value)
    )


def main() -> int:
    errors = []
    if not PROFILE_PATH.exists():
        errors.append("Missing Site Data/players/hitter_profile_summary.json")
        data = {}
    else:
        try:
            data = load_json(PROFILE_PATH)
        except ValueError as exc:
            errors.append(str(exc))
            data = {}

    if not isinstance(data, dict):
        errors.append("Site Data/players/hitter_profile_summary.json must be an object")
        data = {}

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("hitter_profile_summary.json missing meta")
    else:
        for field in ("generated_at", "season", "source", "status", "profile_count", "insufficient_data_count"):
            if field not in meta:
                errors.append(f"hitter_profile_summary.json meta missing {field}")

    players = data.get("players")
    if not isinstance(players, dict):
        errors.append("hitter_profile_summary.json players must be an object")
        players = {}

    slugs = []
    insufficient_count = 0
    for slug, record in players.items():
        if not isinstance(record, dict):
            errors.append(f"hitter_profile_summary.json player {slug} must be an object")
            continue

        record_slug = record.get("slug")
        full_name = record.get("full_name")
        if not record_slug:
            errors.append(f"hitter_profile_summary.json player {slug} missing slug")
        else:
            slugs.append(record_slug)
        if not full_name:
            errors.append(f"hitter_profile_summary.json player {slug} missing full_name")

        profile_type = record.get("profile_type")
        if profile_type not in ALLOWED_PROFILE_TYPES:
            errors.append(f"hitter_profile_summary.json player {slug}.profile_type is invalid")
        elif profile_type == "Insufficient Data":
            insufficient_count += 1

        confidence = record.get("confidence")
        if confidence not in CONFIDENCE_VALUES:
            errors.append(f"hitter_profile_summary.json player {slug}.confidence must be HIGH, MEDIUM, or LOW")

        for field in ("power_signal", "contact_signal"):
            value = record.get(field)
            if bad_scalar(value) or not valid_number_or_null(value):
                errors.append(f"hitter_profile_summary.json player {slug}.{field} must be numeric 0-100 or null")
            elif value is not None and (value < 0 or value > 100):
                errors.append(f"hitter_profile_summary.json player {slug}.{field} outside 0-100")

        luck_gap_points = record.get("luck_gap_points")
        if bad_scalar(luck_gap_points) or not valid_number_or_null(luck_gap_points):
            errors.append(f"hitter_profile_summary.json player {slug}.luck_gap_points must be integer or null")
        elif luck_gap_points is not None and not isinstance(luck_gap_points, int):
            errors.append(f"hitter_profile_summary.json player {slug}.luck_gap_points must be integer or null")

        notes = record.get("supporting_notes")
        if not isinstance(notes, list):
            errors.append(f"hitter_profile_summary.json player {slug}.supporting_notes must be a list")
        else:
            for note in notes:
                if bad_scalar(note):
                    errors.append(f"hitter_profile_summary.json player {slug}.supporting_notes contains invalid text")

        for field in ("summary_label", "team_abbr"):
            if bad_scalar(record.get(field)):
                errors.append(f"hitter_profile_summary.json player {slug}.{field} is invalid")

    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        errors.append("Duplicate Hitter Profile slugs: " + ", ".join(duplicates))

    if isinstance(meta, dict) and meta.get("status") != "failed":
        if meta.get("profile_count") != len(players):
            errors.append("profile_count does not match players count")
        if meta.get("insufficient_data_count") != insufficient_count:
            errors.append("insufficient_data_count does not match profile type count")

    if errors:
        print("PLAYER HITTER PROFILE BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PLAYER HITTER PROFILE SAFE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
