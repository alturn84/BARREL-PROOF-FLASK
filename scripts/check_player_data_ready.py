#!/usr/bin/env python3
"""Validate PLAYER-001 identity files before routing depends on them."""

from __future__ import annotations

import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path} is missing or invalid JSON: {exc}") from exc


def main() -> int:
    errors = []
    index_path = PLAYERS_DIR / "player_index.json"
    aliases_path = PLAYERS_DIR / "player_aliases.json"
    overrides_path = PLAYERS_DIR / "player_manual_overrides.json"

    for path in (index_path, aliases_path, overrides_path):
        if not path.exists():
            errors.append(f"Missing {path.relative_to(BASE_DIR)}")

    players = []
    if index_path.exists():
        try:
            players = load_json(index_path)
        except ValueError as exc:
            errors.append(str(exc))

    if not isinstance(players, list) or not players:
        errors.append("player_index has no players")
        players = []

    if aliases_path.exists():
        try:
            aliases = load_json(aliases_path)
            if not isinstance(aliases, dict):
                errors.append("player_aliases.json must be an object")
        except ValueError as exc:
            errors.append(str(exc))

    slugs = []
    for player in players:
        name = player.get("full_name") or player.get("display_name")
        slug = player.get("slug")
        if not name:
            errors.append(f"Player missing name: {player}")
        if not slug:
            errors.append(f"Player missing slug: {name or player}")
        else:
            slugs.append(slug)
        if (
            player.get("active")
            and player.get("team_abbr") == "OAK"
            and (player.get("team_name") or player.get("team_abbr"))
        ):
            errors.append(f"Active Athletics player still uses OAK: {name}")

    duplicate_slugs = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicate_slugs:
        errors.append("Duplicate slugs: " + ", ".join(duplicate_slugs))

    if errors:
        print("PLAYER DATA BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PLAYER DATA SAFE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
