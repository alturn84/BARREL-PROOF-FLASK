#!/usr/bin/env python3
"""
Readiness checker for Site Data/pitch_type_intelligence.json.
Exits 0 on PASS, 1 on FAIL.
"""

import json
import math
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "Site Data" / "pitch_type_intelligence.json"

BAD_STRINGS = {"nan", "inf", "-inf", "undefined", "none", "null"}

BANNED_PHRASES = [
    "poised to", "set to", "showcase", "battle", "clash",
    "will look to", "only time will tell", "it remains to be seen",
    "both teams are looking to", "intriguing matchup",
    "exciting contest", "highly anticipated",
]
BANNED_BET = [
    "lock", "guaranteed", "free money", "must bet", "bet this",
    "smash spot", "can't miss", "easy money", "automatic",
    "hammer", "wager",
]


def fail(msg):
    print(f"FAIL: {msg}", flush=True)
    print("PITCH TYPE INTELLIGENCE BLOCKED", flush=True)
    sys.exit(1)


def is_bad_value(v):
    if v is None:
        return False
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return True
    if isinstance(v, str) and v.strip().lower() in BAD_STRINGS:
        return True
    return False


def walk(obj, path="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{path}[{i}]")
    elif is_bad_value(obj):
        fail(f"Bad value at {path}: {obj!r}")


def check_text(text):
    lower = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lower:
            fail(f"Banned phrase found: '{phrase}'")
    for word in BANNED_BET:
        if word in lower:
            fail(f"Banned betting word found: '{word}'")


def main():
    if not DATA_FILE.exists():
        fail(f"{DATA_FILE} not found")

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"JSON parse error: {e}")

    meta = data.get("meta")
    if not meta:
        fail("Missing 'meta'")
    if not meta.get("date"):
        fail("meta.date missing")
    if not meta.get("generated_at"):
        fail("meta.generated_at missing")
    if meta.get("data_quality") not in ("available", "partial", "limited"):
        fail(f"meta.data_quality invalid: {meta.get('data_quality')!r}")

    pitchers = data.get("pitchers", {})
    hitters = data.get("hitters", {})

    dq = meta.get("data_quality")
    if dq == "limited":
        # Still must have the keys present even if empty
        if not isinstance(pitchers, dict):
            fail("'pitchers' must be a dict")
        if not isinstance(hitters, dict):
            fail("'hitters' must be a dict")
        print("PASS: data_quality=limited — minimal validation only", flush=True)
        walk(data, "pitch_type_intelligence")
        check_text(json.dumps(data))
        print("PITCH TYPE INTELLIGENCE READY", flush=True)
        return

    # Validate pitcher profiles
    for slug, p in pitchers.items():
        if not isinstance(p, dict):
            fail(f"pitcher {slug!r} is not a dict")
        if not p.get("name"):
            fail(f"pitcher {slug!r} missing name")
        if "primary_shape" not in p:
            fail(f"pitcher {slug!r} missing primary_shape")
        if p.get("primary_shape") != "Limited Data":
            if not isinstance(p.get("arsenal"), list):
                fail(f"pitcher {slug!r} missing arsenal list")
            if not isinstance(p.get("family_mix"), dict):
                fail(f"pitcher {slug!r} missing family_mix dict")
        if not p.get("summary"):
            fail(f"pitcher {slug!r} missing summary")

    # Validate hitter profiles
    for slug, h in hitters.items():
        if not isinstance(h, dict):
            fail(f"hitter {slug!r} is not a dict")
        if not h.get("name"):
            fail(f"hitter {slug!r} missing name")
        if "best_family" not in h:
            fail(f"hitter {slug!r} missing best_family")
        if h.get("best_family") != "Limited Data":
            if not isinstance(h.get("pitch_family_profile"), dict):
                fail(f"hitter {slug!r} missing pitch_family_profile dict")
        if not h.get("summary"):
            fail(f"hitter {slug!r} missing summary")

    walk(data, "pitch_type_intelligence")
    check_text(json.dumps(data))

    p_avail = meta.get("pitcher_available", 0)
    h_avail = meta.get("hitter_available", 0)
    print(
        f"PASS: {len(pitchers)} pitchers ({p_avail} with data), "
        f"{len(hitters)} hitters ({h_avail} with data), "
        f"quality={dq}",
        flush=True,
    )
    print("PITCH TYPE INTELLIGENCE READY", flush=True)


if __name__ == "__main__":
    main()
