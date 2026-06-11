#!/usr/bin/env python3
"""Build PLAYER-005A isolated hitter Power Signal data from local player layers."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"
OUT_FILE = PLAYERS_DIR / "hitter_power_signal.json"

CORE_INPUTS = {
    "barrel_pct": 0.30,
    "hard_hit_pct": 0.25,
    "avg_exit_velocity": 0.20,
    "xslg": 0.15,
    "max_exit_velocity": 0.10,
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


def percentile_rank(value, population):
    if value is None or not population:
        return None
    lower = sum(1 for item in population if item < value)
    equal = sum(1 for item in population if item == value)
    return ((lower + (0.5 * equal)) / len(population)) * 100


def confidence_for(input_count):
    if input_count >= 4:
        return "HIGH"
    if input_count == 3:
        return "MEDIUM"
    return "LOW"


def label_for(power_signal):
    if power_signal is None:
        return "Limited power signal"
    if power_signal >= 90:
        return "Elite power foundation"
    if power_signal >= 75:
        return "Strong power indicators"
    if power_signal >= 60:
        return "Usable power profile"
    if power_signal >= 40:
        return "Ordinary power profile"
    return "Limited power signal"


def main() -> int:
    statcast_data = load_json(PLAYERS_DIR / "statcast_hitter_cards.json", {})
    season_data = load_json(PLAYERS_DIR / "season_hitter_stats.json", {})
    statcast_players = statcast_data.get("players", {}) if isinstance(statcast_data, dict) else {}
    season_players = season_data.get("players", {}) if isinstance(season_data, dict) else {}
    season = (
        statcast_data.get("meta", {}).get("season")
        if isinstance(statcast_data.get("meta"), dict)
        else datetime.now().year
    )

    output = {
        "meta": {
            "generated_at": now_iso(),
            "season": season,
            "source": "Barrel Proof Statcast + season hitter stats",
            "status": "success",
            "calculated_count": 0,
            "low_confidence_count": 0,
        },
        "players": {},
    }

    if not isinstance(statcast_players, dict) or not isinstance(season_players, dict):
        output["meta"]["status"] = "failed"
        output["meta"]["error"] = "Statcast hitter cards or season hitter stats are unavailable."
        write_json(output)
        print("PLAYER POWER SIGNAL FAILED: source player objects unavailable")
        return 0

    rows = {}
    populations = {field: [] for field in CORE_INPUTS}
    for slug, statcast_card in statcast_players.items():
        if not isinstance(statcast_card, dict):
            continue
        season_card = season_players.get(slug, {})
        if not isinstance(season_card, dict):
            season_card = {}

        inputs = {
            "barrel_pct": clean_number(statcast_card.get("barrel_pct")),
            "hard_hit_pct": clean_number(statcast_card.get("hard_hit_pct")),
            "avg_exit_velocity": clean_number(statcast_card.get("avg_exit_velocity")),
            "max_exit_velocity": clean_number(statcast_card.get("max_exit_velocity")),
            "xslg": clean_number(statcast_card.get("xslg")),
            "slg": clean_number(season_card.get("slg")),
            "hr": clean_number(season_card.get("hr")),
        }
        rows[slug] = {
            "slug": slug,
            "full_name": statcast_card.get("full_name") or season_card.get("full_name"),
            "team_abbr": statcast_card.get("team_abbr") or season_card.get("team_abbr"),
            "inputs": inputs,
        }
        for field in CORE_INPUTS:
            value = inputs.get(field)
            if value is not None:
                populations[field].append(value)

    for slug, row in rows.items():
        weighted_total = 0.0
        available_weight = 0.0
        available_inputs = 0
        for field, weight in CORE_INPUTS.items():
            value = row["inputs"].get(field)
            rank = percentile_rank(value, populations[field])
            if rank is None:
                continue
            weighted_total += rank * weight
            available_weight += weight
            available_inputs += 1

        confidence = confidence_for(available_inputs)
        power_signal = None
        if available_inputs >= 3 and available_weight:
            power_signal = int(round(weighted_total / available_weight))
            power_signal = max(0, min(100, power_signal))

        output["players"][slug] = {
            "slug": row["slug"],
            "full_name": row["full_name"],
            "team_abbr": row["team_abbr"],
            "power_signal": power_signal,
            "label": label_for(power_signal),
            "confidence": confidence,
            "inputs": row["inputs"],
        }

    output["players"] = dict(sorted(output["players"].items()))
    output["meta"]["calculated_count"] = sum(
        1 for record in output["players"].values() if record.get("power_signal") is not None
    )
    output["meta"]["low_confidence_count"] = sum(
        1 for record in output["players"].values() if record.get("confidence") == "LOW"
    )
    write_json(output)
    print(
        "Wrote Power Signal layer: "
        f"{output['meta']['calculated_count']} calculated, "
        f"{output['meta']['low_confidence_count']} low confidence."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
