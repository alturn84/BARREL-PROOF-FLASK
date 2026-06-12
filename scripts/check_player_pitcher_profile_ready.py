"""
Readiness checker for Site Data/players/pitcher_profile_summary.json
"""
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PATH = BASE_DIR / "Site Data" / "players" / "pitcher_profile_summary.json"

VALID_PROFILE_TYPES = {
    "Insufficient Data",
    "Ace Foundation",
    "Strong Foundation",
    "Small-Sample Standout",
    "Stable Arm",
    "Volatile Arm",
    "Pitching Risk",
}

VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"}

NUMERIC_FIELDS = ["ip", "era", "whip", "k9", "bb9", "kbb_strength"]


def fail(msg):
    print(f"FAIL: {msg}")
    print("PLAYER PITCHER PROFILE BLOCKED")
    raise SystemExit(1)


def is_bad_value(v):
    if isinstance(v, str) and v.strip().lower() in ("nan", "inf", "-inf", "undefined", "none"):
        return True
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return True
    return False


def main():
    if not PATH.exists():
        fail(f"{PATH} does not exist")

    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"invalid JSON: {e}")

    if "meta" not in data or "players" not in data:
        fail("missing meta or players key")

    players = data["players"]
    if not isinstance(players, dict):
        fail("players is not an object")

    seen_slugs = set()

    for slug, p in players.items():
        if slug in seen_slugs:
            fail(f"duplicate slug: {slug}")
        seen_slugs.add(slug)

        if not p.get("slug"):
            fail(f"{slug}: missing slug")
        if not p.get("full_name"):
            fail(f"{slug}: missing full_name")

        if p.get("profile_type") not in VALID_PROFILE_TYPES:
            fail(f"{slug}: invalid profile_type {p.get('profile_type')!r}")

        if p.get("confidence") not in VALID_CONFIDENCE:
            fail(f"{slug}: invalid confidence {p.get('confidence')!r}")

        signal = p.get("pitcher_foundation_signal")
        if signal is not None:
            if not isinstance(signal, (int, float)) or isinstance(signal, bool):
                fail(f"{slug}: pitcher_foundation_signal not numeric")
            if not (0 <= signal <= 100):
                fail(f"{slug}: pitcher_foundation_signal out of range: {signal}")

        foundation_label = p.get("foundation_label")
        if foundation_label is not None and not isinstance(foundation_label, str):
            fail(f"{slug}: foundation_label not string or null")

        for field in NUMERIC_FIELDS:
            v = p.get(field)
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool)):
                fail(f"{slug}: {field} not numeric or null")
            if is_bad_value(v):
                fail(f"{slug}: {field} has bad value {v!r}")

        notes = p.get("supporting_notes")
        if not isinstance(notes, list):
            fail(f"{slug}: supporting_notes is not a list")

        for k, v in p.items():
            if is_bad_value(v):
                fail(f"{slug}: field {k} has bad value {v!r}")

    meta = data["meta"]
    if meta.get("profile_count") != len(players):
        fail(f"meta.profile_count ({meta.get('profile_count')}) != players count ({len(players)})")

    print(f"OK: {len(players)} players validated")
    print("PLAYER PITCHER PROFILE SAFE")


if __name__ == "__main__":
    main()
