#!/usr/bin/env python3
"""Validate PLAYER-005A hitter Power Signal data."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
POWER_SIGNAL_PATH = BASE_DIR / "Site Data" / "players" / "hitter_power_signal.json"
NUMERIC_INPUT_FIELDS = {
    "barrel_pct",
    "hard_hit_pct",
    "avg_exit_velocity",
    "max_exit_velocity",
    "xslg",
    "slg",
    "hr",
}
BAD_STRINGS = {"nan", "inf", "infinity", "-inf", "-infinity", "none", "undefined"}
CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW"}


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
    if not POWER_SIGNAL_PATH.exists():
        errors.append("Missing Site Data/players/hitter_power_signal.json")
        data = {}
    else:
        try:
            data = load_json(POWER_SIGNAL_PATH)
        except ValueError as exc:
            errors.append(str(exc))
            data = {}

    if not isinstance(data, dict):
        errors.append("Site Data/players/hitter_power_signal.json must be an object")
        data = {}

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("hitter_power_signal.json missing meta")
    else:
        for field in ("generated_at", "season", "source", "status", "calculated_count", "low_confidence_count"):
            if field not in meta:
                errors.append(f"hitter_power_signal.json meta missing {field}")

    players = data.get("players")
    if not isinstance(players, dict):
        errors.append("hitter_power_signal.json players must be an object")
        players = {}

    slugs = []
    calculated_count = 0
    low_confidence_count = 0
    for slug, record in players.items():
        if not isinstance(record, dict):
            errors.append(f"hitter_power_signal.json player {slug} must be an object")
            continue

        record_slug = record.get("slug")
        full_name = record.get("full_name")
        if not record_slug:
            errors.append(f"hitter_power_signal.json player {slug} missing slug")
        else:
            slugs.append(record_slug)
        if not full_name:
            errors.append(f"hitter_power_signal.json player {slug} missing full_name")

        power_signal = record.get("power_signal")
        if bad_scalar(power_signal) or not valid_number_or_null(power_signal):
            errors.append(f"hitter_power_signal.json player {slug}.power_signal must be numeric 0-100 or null")
        elif power_signal is not None:
            calculated_count += 1
            if power_signal < 0 or power_signal > 100:
                errors.append(f"hitter_power_signal.json player {slug}.power_signal outside 0-100")

        confidence = record.get("confidence")
        if confidence not in CONFIDENCE_VALUES:
            errors.append(f"hitter_power_signal.json player {slug}.confidence must be HIGH, MEDIUM, or LOW")
        elif confidence == "LOW":
            low_confidence_count += 1

        for field in ("label", "team_abbr"):
            if bad_scalar(record.get(field)):
                errors.append(f"hitter_power_signal.json player {slug}.{field} is invalid")

        inputs = record.get("inputs")
        if not isinstance(inputs, dict):
            errors.append(f"hitter_power_signal.json player {slug}.inputs must be an object")
            continue
        for field in NUMERIC_INPUT_FIELDS:
            value = inputs.get(field)
            if bad_scalar(value) or not valid_number_or_null(value):
                errors.append(f"hitter_power_signal.json player {slug}.inputs.{field} must be numeric or null")

    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        errors.append("Duplicate Power Signal slugs: " + ", ".join(duplicates))

    if isinstance(meta, dict) and meta.get("status") != "failed":
        if meta.get("calculated_count") != calculated_count:
            errors.append("calculated_count does not match calculated player count")
        if meta.get("low_confidence_count") != low_confidence_count:
            errors.append("low_confidence_count does not match low confidence player count")

    if errors:
        print("PLAYER POWER SIGNAL BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PLAYER POWER SIGNAL SAFE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
