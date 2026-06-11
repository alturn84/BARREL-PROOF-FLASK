#!/usr/bin/env python3
"""Build PLAYER-004A isolated hitter Luck Gap data from local player layers."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"
OUT_FILE = PLAYERS_DIR / "hitter_luck_gap.json"


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


def label_for(points):
    if points is None:
        return None
    if points >= 40:
        return "Production lagging contact quality"
    if points >= 15:
        return "Expected production ahead of actual production"
    if points >= -14:
        return "Actual and expected production aligned"
    if points >= -39:
        return "Actual production running ahead"
    return "Regression warning"


def main() -> int:
    season_data = load_json(PLAYERS_DIR / "season_hitter_stats.json", {})
    statcast_data = load_json(PLAYERS_DIR / "statcast_hitter_cards.json", {})
    season_players = season_data.get("players", {}) if isinstance(season_data, dict) else {}
    statcast_players = statcast_data.get("players", {}) if isinstance(statcast_data, dict) else {}
    season = (
        season_data.get("meta", {}).get("season")
        if isinstance(season_data.get("meta"), dict)
        else datetime.now().year
    )

    output = {
        "meta": {
            "generated_at": now_iso(),
            "season": season,
            "source": "season_hitter_stats calculated_woba + statcast_hitter_cards",
            "fetch_status": "success",
            "matched_count": 0,
            "unmatched_count": 0,
            "ambiguous_count": 0,
            "calculated_count": 0,
        },
        "players": {},
        "unmatched": [],
        "ambiguous": [],
    }

    if not isinstance(season_players, dict) or not isinstance(statcast_players, dict):
        output["meta"]["fetch_status"] = "failed"
        output["meta"]["error"] = "Season hitter stats or Statcast hitter cards are unavailable."
        write_json(output)
        print("PLAYER LUCK GAP FAILED: source player objects unavailable")
        return 0

    for slug, season_card in season_players.items():
        if not isinstance(season_card, dict):
            continue
        statcast_card = statcast_players.get(slug, {})
        if not isinstance(statcast_card, dict):
            continue

        calculated_woba = clean_number(season_card.get("calculated_woba"))
        xwoba = clean_number(statcast_card.get("xwoba"))
        if calculated_woba is None or xwoba is None:
            continue

        luck_gap = round(xwoba - calculated_woba, 3)
        luck_gap_points = int(round(luck_gap * 1000))
        output["players"][slug] = {
            "slug": slug,
            "full_name": season_card.get("full_name") or statcast_card.get("full_name"),
            "team_abbr": season_card.get("team_abbr") or statcast_card.get("team_abbr"),
            "calculated_woba": calculated_woba,
            "xwoba": xwoba,
            "luck_gap": luck_gap,
            "luck_gap_points": luck_gap_points,
            "label": label_for(luck_gap_points),
        }

    output["players"] = dict(sorted(output["players"].items()))
    output["meta"]["matched_count"] = len(output["players"])
    output["meta"]["calculated_count"] = len(output["players"])
    write_json(output)
    print(f"Wrote Luck Gap layer: {len(output['players'])} calculated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
