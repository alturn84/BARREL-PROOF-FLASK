#!/usr/bin/env python3
"""Build PLAYER-009A isolated pitcher Foundation Signal data."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"
SEASON_PITCHER_PATH = PLAYERS_DIR / "season_pitcher_stats.json"
PLAYER_INDEX_PATH = PLAYERS_DIR / "player_index.json"
OUT_FILE = PLAYERS_DIR / "pitcher_foundation_signal.json"

CORE_INPUTS = {
    "era": {"weight": 0.30, "lower_is_better": True},
    "whip": {"weight": 0.25, "lower_is_better": True},
    "k9": {"weight": 0.20, "lower_is_better": False},
    "bb9": {"weight": 0.15, "lower_is_better": True},
    "kbb_strength": {"weight": 0.10, "lower_is_better": False},
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
    return number


def round_number(value, places=3):
    value = clean_number(value)
    if value is None:
        return None
    return round(value, places)


def true_innings(value):
    if value in (None, "", "—"):
        return None
    text = str(value).strip()
    if not text:
        return None

    if "." in text:
        whole_text, fraction_text = text.split(".", 1)
        try:
            whole = int(whole_text or "0")
        except ValueError:
            return None
        if fraction_text in {"0", "00"}:
            outs = 0
        elif fraction_text in {"1", "10"}:
            outs = 1
        elif fraction_text in {"2", "20"}:
            outs = 2
        else:
            number = clean_number(value)
            return None if number is None else round(number, 4)
        return round(whole + (outs / 3), 4)

    number = clean_number(value)
    return None if number is None else round(number, 4)


def rate_per_nine(numerator, innings):
    numerator = clean_number(numerator)
    innings = clean_number(innings)
    if numerator is None or innings is None or innings <= 0:
        return None
    return round((numerator / innings) * 9, 2)


def percentile_score(value, population, lower_is_better=False):
    if value is None or not population:
        return None
    if lower_is_better:
        better = sum(1 for item in population if item > value)
    else:
        better = sum(1 for item in population if item < value)
    equal = sum(1 for item in population if item == value)
    return ((better + (0.5 * equal)) / len(population)) * 100


def confidence_for(ip):
    if ip is None or ip < 10:
        return "INSUFFICIENT"
    if ip >= 50:
        return "HIGH"
    if ip >= 25:
        return "MEDIUM"
    return "LOW"


def label_for(signal):
    if signal is None:
        return "Insufficient Data"
    if signal >= 90:
        return "Elite run-prevention foundation"
    if signal >= 75:
        return "Strong pitching foundation"
    if signal >= 60:
        return "Stable pitching profile"
    if signal >= 40:
        return "Volatile pitching profile"
    return "Pitching risk"


def player_index_by_slug():
    index = load_json(PLAYER_INDEX_PATH, [])
    if not isinstance(index, list):
        return {}
    return {
        player.get("slug"): player
        for player in index
        if isinstance(player, dict) and player.get("slug")
    }


def build_failed_output(message):
    return {
        "meta": {
            "generated_at": now_iso(),
            "season": datetime.now().year,
            "source": "Barrel Proof pitcher season stats",
            "status": "failed",
            "pitcher_count": 0,
            "calculated_count": 0,
            "insufficient_data_count": 0,
            "error": message,
        },
        "players": {},
    }


def main() -> int:
    season_data = load_json(SEASON_PITCHER_PATH, {})
    season_players = season_data.get("players", {}) if isinstance(season_data, dict) else {}
    season = (
        season_data.get("meta", {}).get("season")
        if isinstance(season_data.get("meta"), dict)
        else datetime.now().year
    )

    if not isinstance(season_players, dict):
        output = build_failed_output("Season pitcher stats are unavailable.")
        write_json(output)
        print("PLAYER PITCHER FOUNDATION FAILED: season pitcher players object unavailable")
        return 0

    identities = player_index_by_slug()
    rows = {}
    populations = {field: [] for field in CORE_INPUTS}

    for slug, pitcher in season_players.items():
        if not isinstance(pitcher, dict):
            continue
        identity = identities.get(slug, {})
        ip = true_innings(pitcher.get("ip"))
        so = clean_number(pitcher.get("so"))
        bb = clean_number(pitcher.get("bb"))
        k9 = rate_per_nine(so, ip)
        bb9 = rate_per_nine(bb, ip)
        kbb_strength = None if k9 is None or bb9 is None else round(k9 - bb9, 2)

        row = {
            "slug": slug,
            "full_name": pitcher.get("full_name") or identity.get("full_name") or identity.get("display_name"),
            "team_abbr": pitcher.get("team_abbr") or identity.get("team_abbr"),
            "ip": ip,
            "era": round_number(pitcher.get("era"), 3),
            "whip": round_number(pitcher.get("whip"), 3),
            "k9": k9,
            "bb9": bb9,
            "kbb_strength": kbb_strength,
        }
        rows[slug] = row

        if ip is None or ip < 10:
            continue
        for field in CORE_INPUTS:
            value = row.get(field)
            if value is not None:
                populations[field].append(value)

    output = {
        "meta": {
            "generated_at": now_iso(),
            "season": season,
            "source": "Barrel Proof pitcher season stats",
            "status": "success",
            "pitcher_count": 0,
            "calculated_count": 0,
            "insufficient_data_count": 0,
        },
        "players": {},
    }

    for slug, row in rows.items():
        ip = row.get("ip")
        confidence = confidence_for(ip)
        components = {
            "era_score": None,
            "whip_score": None,
            "k9_score": None,
            "bb9_score": None,
            "kbb_score": None,
        }
        signal = None

        if confidence != "INSUFFICIENT":
            weighted_total = 0.0
            available_weight = 0.0
            for field, config in CORE_INPUTS.items():
                score = percentile_score(
                    row.get(field),
                    populations[field],
                    lower_is_better=config["lower_is_better"],
                )
                component_name = "kbb_score" if field == "kbb_strength" else f"{field}_score"
                components[component_name] = None if score is None else int(round(score))
                if score is None:
                    continue
                weighted_total += score * config["weight"]
                available_weight += config["weight"]

            if available_weight:
                signal = int(round(weighted_total / available_weight))
                signal = max(0, min(100, signal))
            else:
                confidence = "INSUFFICIENT"

        output["players"][slug] = {
            "slug": row["slug"],
            "full_name": row["full_name"],
            "team_abbr": row["team_abbr"],
            "pitcher_foundation_signal": signal,
            "label": label_for(signal),
            "confidence": confidence,
            "ip": row["ip"],
            "era": row["era"],
            "whip": row["whip"],
            "k9": row["k9"],
            "bb9": row["bb9"],
            "kbb_strength": row["kbb_strength"],
            "components": components,
        }

    output["players"] = dict(sorted(output["players"].items()))
    output["meta"]["pitcher_count"] = len(output["players"])
    output["meta"]["calculated_count"] = sum(
        1 for record in output["players"].values() if record.get("pitcher_foundation_signal") is not None
    )
    output["meta"]["insufficient_data_count"] = sum(
        1 for record in output["players"].values() if record.get("confidence") == "INSUFFICIENT"
    )

    write_json(output)
    print(
        "Wrote Pitcher Foundation Signal layer: "
        f"{output['meta']['calculated_count']} calculated, "
        f"{output['meta']['insufficient_data_count']} insufficient data."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
