#!/usr/bin/env python3
"""
Readiness checker for Site Data/pitch_type_intelligence.json.

PASS when:
  - JSON exists and is valid
  - meta present with required keys: data_quality, generated_at, cache_status
  - data_quality is "available" or "partial"
  - OR data_quality is "limited" AND cache_status is "reused_previous" or
    "fallback_limited" AND JSON is otherwise structurally valid
  - No raw None/NaN/undefined leaks in profile values
  - No banned phrases or betting language

FAIL only when:
  - JSON missing or unparseable
  - meta missing or required keys absent
  - data_quality missing or unrecognised
  - Structural keys required by downstream scripts are absent
  - Raw NaN / bad-value leaks present

Exits 0 on PASS, 1 on FAIL.
"""

import json
import math
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "Site Data" / "pitch_type_intelligence.json"

BAD_STRINGS = {"nan", "inf", "-inf", "undefined"}
# "none" and "null" are not flagged — they appear as literal strings in
# fallback summaries and are acceptable placeholder text.

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

REQUIRED_META_KEYS = {"data_quality", "generated_at", "cache_status"}
VALID_DATA_QUALITY = {"available", "partial", "limited"}
VALID_CACHE_STATUS = {"fresh", "reused_previous", "fallback_limited"}


def fail(msg):
    print(f"FAIL: {msg}", flush=True)
    print("PITCH TYPE INTELLIGENCE BLOCKED", flush=True)
    sys.exit(1)


def is_bad_value(v):
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


def validate_pitcher(slug, p):
    if not isinstance(p, dict):
        fail(f"pitcher {slug!r} is not a dict")
    if not p.get("name"):
        fail(f"pitcher {slug!r} missing name")
    if "primary_shape" not in p:
        fail(f"pitcher {slug!r} missing primary_shape")
    if p.get("primary_shape") not in (None, "Limited Data"):
        if not isinstance(p.get("arsenal"), list):
            fail(f"pitcher {slug!r} missing arsenal list")
        if not isinstance(p.get("family_mix"), dict):
            fail(f"pitcher {slug!r} missing family_mix dict")
    if not p.get("summary"):
        fail(f"pitcher {slug!r} missing summary")


def validate_hitter(slug, h):
    if not isinstance(h, dict):
        fail(f"hitter {slug!r} is not a dict")
    if not h.get("name"):
        fail(f"hitter {slug!r} missing name")
    if "best_family" not in h:
        fail(f"hitter {slug!r} missing best_family")
    if h.get("best_family") not in (None, "Limited Data"):
        if not isinstance(h.get("pitch_family_profile"), dict):
            fail(f"hitter {slug!r} missing pitch_family_profile dict")
    if not h.get("summary"):
        fail(f"hitter {slug!r} missing summary")


def main():
    if not DATA_FILE.exists():
        fail(f"{DATA_FILE} not found")

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"JSON parse error: {e}")

    # ── Meta checks ───────────────────────────────────────────────────
    meta = data.get("meta")
    if not isinstance(meta, dict):
        fail("Missing or invalid 'meta' block")

    for key in REQUIRED_META_KEYS:
        if key not in meta:
            fail(f"meta.{key} missing")

    dq = meta.get("data_quality")
    if dq not in VALID_DATA_QUALITY:
        fail(f"meta.data_quality invalid: {dq!r} (expected one of {VALID_DATA_QUALITY})")

    cache_status = meta.get("cache_status")
    if cache_status not in VALID_CACHE_STATUS:
        fail(f"meta.cache_status invalid: {cache_status!r} (expected one of {VALID_CACHE_STATUS})")

    if not meta.get("generated_at"):
        fail("meta.generated_at is empty")

    # ── Structural checks ─────────────────────────────────────────────
    pitchers = data.get("pitchers")
    hitters = data.get("hitters")

    if not isinstance(pitchers, dict):
        fail("'pitchers' must be a dict")
    if not isinstance(hitters, dict):
        fail("'hitters' must be a dict")

    # ── Fallback / reused-cache paths: minimal validation ─────────────
    if cache_status in ("fallback_limited", "reused_previous") or dq == "limited":
        walk(data, "pitch_type_intelligence")
        check_text(json.dumps(data))
        p_avail = meta.get("pitcher_available", 0)
        h_avail = meta.get("hitter_available", 0)
        print(
            f"PASS: data_quality={dq}, cache_status={cache_status} — "
            f"{len(pitchers)} pitchers ({p_avail} with data), "
            f"{len(hitters)} hitters ({h_avail} with data)",
            flush=True,
        )
        print("PITCH TYPE INTELLIGENCE READY", flush=True)
        return

    # ── Full profile validation for available/partial fresh data ──────
    for slug, p in pitchers.items():
        validate_pitcher(slug, p)

    for slug, h in hitters.items():
        validate_hitter(slug, h)

    walk(data, "pitch_type_intelligence")
    check_text(json.dumps(data))

    p_avail = meta.get("pitcher_available", 0)
    h_avail = meta.get("hitter_available", 0)
    failed_p = meta.get("failed_pitcher_count", 0)
    failed_h = meta.get("failed_hitter_count", 0)

    notes = []
    if failed_p:
        notes.append(f"{failed_p} pitcher fetch(es) failed")
    if failed_h:
        notes.append(f"{failed_h} hitter fetch(es) failed")

    print(
        f"PASS: {len(pitchers)} pitchers ({p_avail} with data), "
        f"{len(hitters)} hitters ({h_avail} with data), "
        f"quality={dq}, cache_status={cache_status}"
        + (f" [{', '.join(notes)}]" if notes else ""),
        flush=True,
    )
    print("PITCH TYPE INTELLIGENCE READY", flush=True)


if __name__ == "__main__":
    main()
