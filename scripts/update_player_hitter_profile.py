#!/usr/bin/env python3
"""Build PLAYER-008A isolated hitter profile summaries from local signal layers."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"
OUT_FILE = PLAYERS_DIR / "hitter_profile_summary.json"

SUMMARY_LABELS = {
    "Real Power Bat": "Power is supported by the underlying contact profile.",
    "Buy-Low Bat": "Expected production is ahead of current results.",
    "Regression Risk": "Actual production is running ahead of expected contact quality.",
    "Volatile Slugger": "Power is loud, but contact risk is present.",
    "Contact-First Bat": "Contact foundation is stronger than the power indicators.",
    "Balanced Producer": "Power, contact, and production are mostly aligned.",
    "Watch List": "Multiple hitter signals are available, but no stronger profile is clear.",
    "Insufficient Data": "More hitter signal data is needed before assigning a stronger profile.",
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


def clean_signal(value):
    number = clean_number(value)
    if number is None:
        return None
    return int(round(number))


def identity_for(slug, index_by_slug, season_card, power_card, contact_card, luck_card):
    identity = index_by_slug.get(slug, {}) if isinstance(index_by_slug.get(slug), dict) else {}
    for card in (season_card, power_card, contact_card, luck_card):
        if not isinstance(card, dict):
            continue
        if card.get("full_name") or card.get("team_abbr"):
            return {
                "full_name": card.get("full_name") or identity.get("full_name") or identity.get("display_name"),
                "team_abbr": card.get("team_abbr") or identity.get("team_abbr"),
            }
    return {
        "full_name": identity.get("full_name") or identity.get("display_name"),
        "team_abbr": identity.get("team_abbr"),
    }


def confidence_for(power_signal, contact_signal, luck_gap_points, power_confidence, contact_confidence):
    available_count = sum(value is not None for value in (power_signal, contact_signal, luck_gap_points))
    if (
        available_count == 3
        and power_confidence in {"HIGH", "MEDIUM"}
        and contact_confidence in {"HIGH", "MEDIUM"}
    ):
        return "HIGH"
    if available_count >= 2:
        return "MEDIUM"
    return "LOW"


def profile_type_for(power_signal, contact_signal, luck_gap_points):
    available_count = sum(value is not None for value in (power_signal, contact_signal, luck_gap_points))
    if available_count < 2:
        return "Insufficient Data"
    if luck_gap_points is not None and luck_gap_points <= -35:
        return "Regression Risk"
    if (
        luck_gap_points is not None
        and luck_gap_points >= 35
        and (
            (power_signal is not None and power_signal >= 60)
            or (contact_signal is not None and contact_signal >= 60)
        )
    ):
        return "Buy-Low Bat"
    if (
        power_signal is not None
        and contact_signal is not None
        and power_signal >= 75
        and contact_signal < 55
    ):
        return "Volatile Slugger"
    if (
        power_signal is not None
        and contact_signal is not None
        and luck_gap_points is not None
        and power_signal >= 75
        and contact_signal >= 55
        and -30 <= luck_gap_points <= 60
    ):
        return "Real Power Bat"
    if (
        power_signal is not None
        and contact_signal is not None
        and contact_signal >= 75
        and power_signal < 60
    ):
        return "Contact-First Bat"
    if (
        power_signal is not None
        and contact_signal is not None
        and luck_gap_points is not None
        and power_signal >= 60
        and contact_signal >= 60
        and -20 <= luck_gap_points <= 20
    ):
        return "Balanced Producer"
    return "Watch List"


def supporting_notes(power_signal, contact_signal, luck_gap_points, profile_type):
    notes = []
    if power_signal is None:
        notes.append("Power signal is not available.")
    elif power_signal >= 90:
        notes.append("Power indicators are elite.")
    elif power_signal >= 75:
        notes.append("Power indicators are strong.")
    elif power_signal >= 60:
        notes.append("Power indicators are usable.")
    elif power_signal < 40:
        notes.append("Power indicators are limited.")

    if contact_signal is None:
        notes.append("Contact signal is not available.")
    elif contact_signal >= 75:
        notes.append("Contact profile is strong.")
    elif contact_signal >= 60:
        notes.append("Contact profile is stable.")
    elif contact_signal < 55:
        notes.append("Contact risk is present.")

    if luck_gap_points is None:
        notes.append("Luck Gap is not available.")
    elif luck_gap_points >= 40:
        notes.append("Expected production is well ahead of current results.")
    elif luck_gap_points >= 15:
        notes.append("Expected production is slightly ahead of current results.")
    elif luck_gap_points <= -40:
        notes.append("Actual production is running well ahead of expected contact quality.")
    elif luck_gap_points <= -15:
        notes.append("Actual production is running ahead of expected contact quality.")
    else:
        notes.append("Actual and expected production are mostly aligned.")

    if profile_type == "Volatile Slugger":
        notes.append("Power is strong, but contact risk is present.")
    elif profile_type == "Contact-First Bat":
        notes.append("Contact skill is carrying the profile.")
    elif profile_type == "Insufficient Data":
        notes.append("Fewer than two hitter signals are available.")

    return notes[:4]


def main() -> int:
    power_data = load_json(PLAYERS_DIR / "hitter_power_signal.json", {})
    contact_data = load_json(PLAYERS_DIR / "hitter_contact_signal.json", {})
    luck_data = load_json(PLAYERS_DIR / "hitter_luck_gap.json", {})
    season_data = load_json(PLAYERS_DIR / "season_hitter_stats.json", {})
    player_index = load_json(PLAYERS_DIR / "player_index.json", [])

    power_players = power_data.get("players", {}) if isinstance(power_data, dict) else {}
    contact_players = contact_data.get("players", {}) if isinstance(contact_data, dict) else {}
    luck_players = luck_data.get("players", {}) if isinstance(luck_data, dict) else {}
    season_players = season_data.get("players", {}) if isinstance(season_data, dict) else {}
    index_by_slug = {
        str(player.get("slug")): player
        for player in player_index
        if isinstance(player, dict) and player.get("slug")
    } if isinstance(player_index, list) else {}
    season = (
        season_data.get("meta", {}).get("season")
        if isinstance(season_data.get("meta"), dict)
        else datetime.now().year
    )

    output = {
        "meta": {
            "generated_at": now_iso(),
            "season": season,
            "source": "Barrel Proof hitter signal stack",
            "status": "success",
            "profile_count": 0,
            "insufficient_data_count": 0,
        },
        "players": {},
    }

    if not all(isinstance(layer, dict) for layer in (power_players, contact_players, luck_players, season_players)):
        output["meta"]["status"] = "failed"
        output["meta"]["error"] = "One or more hitter signal layers are unavailable."
        write_json(output)
        print("PLAYER HITTER PROFILE FAILED: source player objects unavailable")
        return 0

    slugs = sorted(set(season_players) | set(power_players) | set(contact_players) | set(luck_players))
    for slug in slugs:
        season_card = season_players.get(slug, {})
        power_card = power_players.get(slug, {})
        contact_card = contact_players.get(slug, {})
        luck_card = luck_players.get(slug, {})

        power_signal = clean_signal(power_card.get("power_signal")) if isinstance(power_card, dict) else None
        contact_signal = clean_signal(contact_card.get("contact_signal")) if isinstance(contact_card, dict) else None
        luck_gap_points = clean_signal(luck_card.get("luck_gap_points")) if isinstance(luck_card, dict) else None
        power_confidence = power_card.get("confidence") if isinstance(power_card, dict) else None
        contact_confidence = contact_card.get("confidence") if isinstance(contact_card, dict) else None
        identity = identity_for(slug, index_by_slug, season_card, power_card, contact_card, luck_card)
        profile_type = profile_type_for(power_signal, contact_signal, luck_gap_points)

        output["players"][slug] = {
            "slug": slug,
            "full_name": identity.get("full_name"),
            "team_abbr": identity.get("team_abbr"),
            "profile_type": profile_type,
            "summary_label": SUMMARY_LABELS[profile_type],
            "confidence": confidence_for(
                power_signal,
                contact_signal,
                luck_gap_points,
                power_confidence,
                contact_confidence,
            ),
            "power_signal": power_signal,
            "contact_signal": contact_signal,
            "luck_gap_points": luck_gap_points,
            "supporting_notes": supporting_notes(power_signal, contact_signal, luck_gap_points, profile_type),
        }

    output["meta"]["profile_count"] = len(output["players"])
    output["meta"]["insufficient_data_count"] = sum(
        1 for record in output["players"].values() if record.get("profile_type") == "Insufficient Data"
    )
    write_json(output)
    print(
        "Wrote Hitter Profile layer: "
        f"{output['meta']['profile_count']} profiles, "
        f"{output['meta']['insufficient_data_count']} insufficient data."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
