#!/usr/bin/env python3
"""Validate PLAYER-003A isolated Statcast hitter card data."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
STATCAST_PATH = BASE_DIR / "Site Data" / "players" / "statcast_hitter_cards.json"
NUMERIC_FIELDS = {
    "avg_exit_velocity",
    "max_exit_velocity",
    "hard_hit_pct",
    "barrel_pct",
    "sweet_spot_pct",
    "xba",
    "xslg",
    "xwoba",
}


def blocked(errors):
    print("PLAYER STATCAST BLOCKED")
    for error in errors:
        print(f"- {error}")
    return 1


def has_bad_scalar(value):
    if isinstance(value, str) and value.strip().lower() in {"nan", "inf", "infinity", "none", "undefined"}:
        return True
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return True
    return False


def walk_bad_values(value):
    if has_bad_scalar(value):
        return True
    if isinstance(value, dict):
        return any(walk_bad_values(v) for v in value.values())
    if isinstance(value, list):
        return any(walk_bad_values(v) for v in value)
    return False


def main():
    errors = []
    if not STATCAST_PATH.exists():
        return blocked([f"Missing {STATCAST_PATH.relative_to(BASE_DIR)}"])

    try:
        data = json.loads(STATCAST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return blocked([f"Invalid JSON: {exc}"])

    if walk_bad_values(data):
        errors.append("JSON contains NaN, inf, undefined, or string None values")

    meta = data.get("meta")
    players = data.get("players")
    unmatched = data.get("unmatched")

    if not isinstance(meta, dict):
        errors.append("meta object is missing")
        meta = {}
    if not meta.get("fetch_status"):
        errors.append("meta.fetch_status is missing")
    if "unmatched_count" not in meta:
        errors.append("meta.unmatched_count is missing")
    if not isinstance(players, dict):
        errors.append("players object is missing")
        players = {}
    if unmatched is not None and not isinstance(unmatched, list):
        errors.append("unmatched must be a list")

    slugs = []
    for slug, card in players.items():
        if not isinstance(card, dict):
            errors.append(f"{slug} card is not an object")
            continue
        if not card.get("slug"):
            errors.append(f"{slug} missing slug")
        else:
            slugs.append(card["slug"])
        if card.get("slug") != slug:
            errors.append(f"{slug} key does not match card slug")
        if not card.get("full_name"):
            errors.append(f"{slug} missing full_name")
        for field in NUMERIC_FIELDS:
            value = card.get(field)
            if value is not None and not isinstance(value, (int, float)):
                errors.append(f"{slug}.{field} must be a number or null")
            elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                errors.append(f"{slug}.{field} is not finite")

    duplicate_slugs = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicate_slugs:
        errors.append("Duplicate slugs: " + ", ".join(duplicate_slugs))

    if errors:
        return blocked(errors)

    print("PLAYER STATCAST SAFE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
