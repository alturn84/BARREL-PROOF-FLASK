#!/usr/bin/env python3
"""
check_edition_ready.py — Barrel Proof Baseball
───────────────────────────────────────────────
Read-only pre-deploy edition integrity check.
Exits 0 (DEPLOY SAFE) or 1 (DEPLOY BLOCKED).

Usage:
    python3 scripts/check_edition_ready.py
"""

import json
import sys
from pathlib import Path

VAULT     = Path(__file__).resolve().parent.parent
SITE_DATA = VAULT / "Site Data"
MEDIA_DIR = VAULT / "media" / "lead-images"

VALID_SOURCE_TYPES = {"ap", "getty", "mlb", "team", "manual", "illustrated"}


def load(path):
    """Return parsed JSON or None on any error."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except Exception:
        return None


results = []   # list of (label, passed, reason)

def check(label, passed, reason):
    results.append((label, passed, reason))


# ── 1. game_cards.json ────────────────────────────────────────────────────────
gc_path = SITE_DATA / "game_cards.json"
gc = load(gc_path)

if gc is None:
    check("game_cards.json", False, "missing or unreadable")
    edition_date = None
elif not gc:
    check("game_cards.json", False, "empty")
    edition_date = None
else:
    edition_date = gc.get("date", "").strip()
    if not edition_date:
        check("game_cards.json", False, "date field missing or empty")
        edition_date = None
    else:
        check("game_cards.json", True, f"date={edition_date}")

# ── 2. game_of_day.json ───────────────────────────────────────────────────────
gotd_path = SITE_DATA / "game_of_day.json"
gotd = load(gotd_path)
if gotd is None:
    check("game_of_day.json", False, "missing or unreadable")
elif not gotd:
    check("game_of_day.json", False, "empty")
else:
    check("game_of_day.json", True, "present and non-empty")

# ── 3. game_to_watch.json ─────────────────────────────────────────────────────
gtw = load(SITE_DATA / "game_to_watch.json")
if gtw is None:
    check("game_to_watch.json", False, "missing or unreadable")
elif not gtw:
    check("game_to_watch.json", False, "empty")
else:
    check("game_to_watch.json", True, "present and non-empty")

# ── 4. around_the_league.json ─────────────────────────────────────────────────
atl = load(SITE_DATA / "around_the_league.json")
if atl is None:
    check("around_the_league.json", False, "missing or unreadable")
elif not atl:
    check("around_the_league.json", False, "empty")
else:
    check("around_the_league.json", True, "present and non-empty")

# ── 5. press_box.json ─────────────────────────────────────────────────────────
pb = load(SITE_DATA / "press_box.json")
if pb is None:
    check("press_box.json", False, "missing or unreadable")
elif not pb:
    check("press_box.json", False, "empty")
elif not pb.get("passed_validation"):
    check("press_box.json", False, f"passed_validation={pb.get('passed_validation')}")
else:
    check("press_box.json", True, "present, non-empty, passed_validation=True")

# ── 6. Cross-date guard: game_of_day.date == game_cards.date ──────────────────
if edition_date and gotd is not None:
    gotd_date = gotd.get("date", "").strip() if isinstance(gotd, dict) else ""
    if not gotd_date:
        check("date guard (gotd == gc)", False, "game_of_day.json has no date field")
    elif gotd_date != edition_date:
        check("date guard (gotd == gc)", False,
              f"gotd.date={gotd_date!r} != gc.date={edition_date!r}")
    else:
        check("date guard (gotd == gc)", True,
              f"both={edition_date}")
elif edition_date is None:
    check("date guard (gotd == gc)", False, "skipped — edition_date unavailable")
# if gotd is None, the earlier check already failed; skip duplicate

# ── 7. Lead image (skipped if no image file exists) ───────────────────────────
if edition_date:
    jpg  = MEDIA_DIR / f"{edition_date}_lead.jpg"
    webp = MEDIA_DIR / f"{edition_date}_lead.webp"
    img_exists = jpg.exists() or webp.exists()

    if not img_exists:
        check("lead image", True, "no image file for edition_date — skip")
    else:
        img_file = jpg.name if jpg.exists() else webp.name
        caps_path = MEDIA_DIR / "captions.json"
        caps = load(caps_path)
        if caps is None:
            check("lead image", False, "image present but captions.json missing/unreadable")
        else:
            entry = caps.get(edition_date, {})
            if not entry:
                check("lead image", False,
                      f"image present but no captions.json entry for {edition_date}")
            else:
                caption     = entry.get("caption", "").strip()
                credit      = entry.get("credit", "").strip()
                source_type = entry.get("source_type", "").strip()
                if not caption:
                    check("lead image", False, "caption is empty")
                elif not credit:
                    check("lead image", False, "credit is empty")
                elif source_type not in VALID_SOURCE_TYPES:
                    check("lead image", False,
                          f"source_type={source_type!r} not in {sorted(VALID_SOURCE_TYPES)}")
                else:
                    check("lead image", True,
                          f"file={img_file}, source_type={source_type}")
else:
    check("lead image", False, "skipped — edition_date unavailable")

# ── 8. Archive snapshot ───────────────────────────────────────────────────────
if edition_date:
    year = edition_date[:4]
    snap = SITE_DATA / "archive" / year / "snapshots" / f"{edition_date}.json"
    if snap.exists():
        snap_data = load(snap)
        completeness = snap_data.get("completeness", "unknown") if snap_data else "unreadable"
        check("archive snapshot", True,
              f"exists, completeness={completeness}")
    else:
        check("archive snapshot", False,
              f"not found at archive/{year}/snapshots/{edition_date}.json")
else:
    check("archive snapshot", False, "skipped — edition_date unavailable")


# ── Output ────────────────────────────────────────────────────────────────────
print(f"edition_date: {edition_date or '(unknown)'}")
print()

label_width = max(len(r[0]) for r in results)
for label, passed, reason in results:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}]  {label:<{label_width}}  {reason}")

all_passed = all(p for _, p, _ in results)
print()
print("DEPLOY SAFE" if all_passed else "DEPLOY BLOCKED")
sys.exit(0 if all_passed else 1)
