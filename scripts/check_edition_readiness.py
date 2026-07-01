"""
Phase 1 foundation script: report-only readiness checker.

Reads Site Data/edition.json for the edition_date (written by
write_edition_date.py) and classifies each content file's "date" field
against it. This script never calculates a fallback date itself — if
edition.json is missing, it reports that and exits cleanly. It must not
become a second hidden date calculator.

Report-only: does not block anything, does not modify cron, does not
modify any other script.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = REPO_ROOT / "Site Data"
EDITION_PATH = SITE_DATA / "edition.json"
REPORT_PATH = SITE_DATA / "edition_readiness_report.json"

CHECKED_FILES = [
    "schedule.json",
    "game_cards.json",
    "odds.json",
    "dfs_board.json",
    "dope-sheet-data.json",
    "dope_game_intelligence.json",
    "dope_player_matchups.json",
    "dope_pitcher_matchups.json",
    "game_of_day.json",
    "game_to_watch.json",
    "around_the_league.json",
    "press_box.json",
]

# Files intentionally paused/optional — reported as "paused" regardless of
# on-disk state. Absence is expected and not a readiness failure.
# player_props.json: BettingPros source unreliable via Firecrawl as of
# 2026-06-30 VPS validation; props paused until a better source is found.
PAUSED_FILES = [
    "player_props.json",
]


def classify(filename, edition_date):
    path = SITE_DATA / filename
    if not path.exists():
        return "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "missing"
    date_field = data.get("date") if isinstance(data, dict) else None
    if not date_field:
        return "no_date_field"
    return "current" if date_field == edition_date else "stale"


def main():
    if not EDITION_PATH.exists():
        report = {
            "mode": "report-only",
            "error": "edition.json missing",
        }
        print(json.dumps(report, indent=2))
        return

    try:
        edition_data = json.loads(EDITION_PATH.read_text(encoding="utf-8"))
        edition_date = edition_data.get("edition_date")
    except Exception:
        report = {
            "mode": "report-only",
            "error": "edition.json missing",
        }
        print(json.dumps(report, indent=2))
        return

    files = {f: classify(f, edition_date) for f in CHECKED_FILES}
    paused = {f: "paused" for f in PAUSED_FILES}

    report = {
        "edition_source": "Site Data/edition.json",
        "edition_date": edition_date,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report-only",
        "files": files,
        "paused": list(PAUSED_FILES),
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"edition_source: Site Data/edition.json")
    print(f"edition_date: {edition_date}")
    for f, status in files.items():
        print(f"{f}: {status}")
    for f, status in paused.items():
        print(f"{f}: {status}")
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
