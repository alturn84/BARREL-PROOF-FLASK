#!/usr/bin/env python3
"""Validate PLAYER-002 generated card/page data."""

from __future__ import annotations

import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"
PAGES_DIR = PLAYERS_DIR / "player_pages"


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path.relative_to(BASE_DIR)} is missing or invalid JSON: {exc}") from exc


def main() -> int:
    errors = []
    hitter_path = PLAYERS_DIR / "hitter_cards.json"
    pitcher_path = PLAYERS_DIR / "pitcher_cards.json"

    for path in (hitter_path, pitcher_path):
        if not path.exists():
            errors.append(f"Missing {path.relative_to(BASE_DIR)}")
        else:
            try:
                data = load_json(path)
                if not isinstance(data, list):
                    errors.append(f"{path.relative_to(BASE_DIR)} must be a list")
                if path == pitcher_path and isinstance(data, list):
                    for card in data:
                        has_season_like = any(card.get(field) not in (None, "", "—") for field in ("era", "whip", "wins", "losses"))
                        has_only_unknown_count = card.get("games") == 0 and card.get("games_started") == 0
                        has_no_box_score_counting = all(card.get(field) in (None, "", "—") for field in ("so", "bb"))
                        if has_season_like and has_only_unknown_count and has_no_box_score_counting:
                            errors.append(
                                "False-zero pitcher count risk: "
                                f"{card.get('slug') or card.get('full_name')} has season-like fields but G/GS are forced to 0"
                            )
            except ValueError as exc:
                errors.append(str(exc))

    if not PAGES_DIR.exists() or not PAGES_DIR.is_dir():
        errors.append("Missing Site Data/players/player_pages directory")
        page_paths = []
    else:
        page_paths = sorted(PAGES_DIR.glob("*.json"))

    if not page_paths:
        errors.append("No player page JSON files found")

    slugs = []
    for path in page_paths:
        try:
            page = load_json(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        slug = page.get("slug")
        name = page.get("full_name") or page.get("display_name")
        if not slug:
            errors.append(f"{path.relative_to(BASE_DIR)} missing slug")
        else:
            slugs.append(slug)
        if not name:
            errors.append(f"{path.relative_to(BASE_DIR)} missing player name")

    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        errors.append("Duplicate player page slugs: " + ", ".join(duplicates))

    if errors:
        print("PLAYER CARDS BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PLAYER CARDS SAFE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
