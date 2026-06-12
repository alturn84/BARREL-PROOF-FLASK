#!/usr/bin/env python3
"""Validate PLAYER-009A pitcher Foundation Signal data."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SIGNAL_PATH = BASE_DIR / "Site Data" / "players" / "pitcher_foundation_signal.json"
BAD_STRINGS = {"nan", "inf", "infinity", "-inf", "-infinity", "none", "undefined"}
CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"}
LABEL_VALUES = {
    "Elite run-prevention foundation",
    "Strong pitching foundation",
    "Stable pitching profile",
    "Volatile pitching profile",
    "Pitching risk",
    "Insufficient Data",
}
NUMERIC_FIELDS = {
    "ip",
    "era",
    "whip",
    "k9",
    "bb9",
    "kbb_strength",
}
COMPONENT_FIELDS = {
    "era_score",
    "whip_score",
    "k9_score",
    "bb9_score",
    "kbb_score",
}


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


def valid_signal(value):
    if value is None:
        return True
    return valid_number_or_null(value) and 0 <= value <= 100


def main() -> int:
    errors = []
    if not SIGNAL_PATH.exists():
        errors.append("Missing Site Data/players/pitcher_foundation_signal.json")
        data = {}
    else:
        try:
            data = load_json(SIGNAL_PATH)
        except ValueError as exc:
            errors.append(str(exc))
            data = {}

    if not isinstance(data, dict):
        errors.append("Site Data/players/pitcher_foundation_signal.json must be an object")
        data = {}

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("pitcher_foundation_signal.json missing meta")
    else:
        for field in (
            "generated_at",
            "season",
            "source",
            "status",
            "pitcher_count",
            "calculated_count",
            "insufficient_data_count",
        ):
            if field not in meta:
                errors.append(f"pitcher_foundation_signal.json meta missing {field}")

    players = data.get("players")
    if not isinstance(players, dict):
        errors.append("pitcher_foundation_signal.json players must be an object")
        players = {}

    slugs = []
    calculated_count = 0
    insufficient_data_count = 0

    for slug, record in players.items():
        if not isinstance(record, dict):
            errors.append(f"pitcher_foundation_signal.json player {slug} must be an object")
            continue

        record_slug = record.get("slug")
        full_name = record.get("full_name")
        if not record_slug:
            errors.append(f"pitcher_foundation_signal.json player {slug} missing slug")
        else:
            slugs.append(record_slug)
        if not full_name:
            errors.append(f"pitcher_foundation_signal.json player {slug} missing full_name")

        signal = record.get("pitcher_foundation_signal")
        if bad_scalar(signal) or not valid_signal(signal):
            errors.append(f"pitcher_foundation_signal.json player {slug}.pitcher_foundation_signal must be numeric 0-100 or null")
        elif signal is not None:
            calculated_count += 1

        confidence = record.get("confidence")
        if confidence not in CONFIDENCE_VALUES:
            errors.append(f"pitcher_foundation_signal.json player {slug}.confidence is invalid")
        elif confidence == "INSUFFICIENT":
            insufficient_data_count += 1

        label = record.get("label")
        if label not in LABEL_VALUES:
            errors.append(f"pitcher_foundation_signal.json player {slug}.label is invalid")

        if confidence == "INSUFFICIENT" and signal is not None:
            errors.append(f"pitcher_foundation_signal.json player {slug} has signal despite INSUFFICIENT confidence")
        if signal is None and label != "Insufficient Data":
            errors.append(f"pitcher_foundation_signal.json player {slug} with null signal must use Insufficient Data label")

        for field in ("team_abbr",):
            if bad_scalar(record.get(field)):
                errors.append(f"pitcher_foundation_signal.json player {slug}.{field} is invalid")
        for field in NUMERIC_FIELDS:
            value = record.get(field)
            if bad_scalar(value) or not valid_number_or_null(value):
                errors.append(f"pitcher_foundation_signal.json player {slug}.{field} must be numeric or null")

        components = record.get("components")
        if not isinstance(components, dict):
            errors.append(f"pitcher_foundation_signal.json player {slug}.components must be an object")
            continue
        for field in COMPONENT_FIELDS:
            value = components.get(field)
            if bad_scalar(value) or not valid_signal(value):
                errors.append(f"pitcher_foundation_signal.json player {slug}.components.{field} must be numeric 0-100 or null")

    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        errors.append("Duplicate Pitcher Foundation slugs: " + ", ".join(duplicates))

    if isinstance(meta, dict) and meta.get("status") != "failed":
        if meta.get("pitcher_count") != len(players):
            errors.append("pitcher_count does not match players count")
        if meta.get("calculated_count") != calculated_count:
            errors.append("calculated_count does not match calculated player count")
        if meta.get("insufficient_data_count") != insufficient_data_count:
            errors.append("insufficient_data_count does not match insufficient player count")

    if errors:
        print("PLAYER PITCHER FOUNDATION BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PLAYER PITCHER FOUNDATION SAFE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
