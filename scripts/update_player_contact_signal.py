#!/usr/bin/env python3
"""Build PLAYER-006A isolated hitter Contact Signal data from local player layers."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"
OUT_FILE = PLAYERS_DIR / "hitter_contact_signal.json"

CORE_INPUTS = {
    "xba": 0.30,
    "obp": 0.20,
    "k_avoidance": 0.20,
    "bb_pct": 0.15,
    "calculated_woba": 0.15,
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


def rate(numerator, denominator):
    numerator = clean_number(numerator)
    denominator = clean_number(denominator)
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator, 3)


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


def label_for(contact_signal):
    if contact_signal is None:
        return "Contact risk"
    if contact_signal >= 90:
        return "Elite contact foundation"
    if contact_signal >= 75:
        return "Strong contact indicators"
    if contact_signal >= 60:
        return "Stable contact profile"
    if contact_signal >= 40:
        return "Volatile contact profile"
    return "Contact risk"


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
        print("PLAYER CONTACT SIGNAL FAILED: source player objects unavailable")
        return 0

    rows = {}
    populations = {field: [] for field in CORE_INPUTS}
    for slug, statcast_card in statcast_players.items():
        if not isinstance(statcast_card, dict):
            continue
        season_card = season_players.get(slug, {})
        if not isinstance(season_card, dict):
            season_card = {}

        pa = clean_number(season_card.get("pa"))
        bb = clean_number(season_card.get("bb"))
        so = clean_number(season_card.get("so"))
        k_pct = rate(so, pa)
        bb_pct = rate(bb, pa)
        k_avoidance = None if k_pct is None else round(1 - k_pct, 3)

        inputs = {
            "xba": clean_number(statcast_card.get("xba")),
            "xwoba": clean_number(statcast_card.get("xwoba")),
            "avg": clean_number(season_card.get("avg")),
            "obp": clean_number(season_card.get("obp")),
            "calculated_woba": clean_number(season_card.get("calculated_woba")),
            "pa": pa,
            "bb": bb,
            "so": so,
            "bb_pct": bb_pct,
            "k_pct": k_pct,
            "k_avoidance": k_avoidance,
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
        contact_signal = None
        if available_inputs >= 3 and available_weight:
            contact_signal = int(round(weighted_total / available_weight))
            contact_signal = max(0, min(100, contact_signal))

        output["players"][slug] = {
            "slug": row["slug"],
            "full_name": row["full_name"],
            "team_abbr": row["team_abbr"],
            "contact_signal": contact_signal,
            "label": label_for(contact_signal),
            "confidence": confidence,
            "inputs": row["inputs"],
        }

    output["players"] = dict(sorted(output["players"].items()))
    output["meta"]["calculated_count"] = sum(
        1 for record in output["players"].values() if record.get("contact_signal") is not None
    )
    output["meta"]["low_confidence_count"] = sum(
        1 for record in output["players"].values() if record.get("confidence") == "LOW"
    )
    write_json(output)
    print(
        "Wrote Contact Signal layer: "
        f"{output['meta']['calculated_count']} calculated, "
        f"{output['meta']['low_confidence_count']} low confidence."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
