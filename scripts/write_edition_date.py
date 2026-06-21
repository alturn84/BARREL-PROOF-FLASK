"""
Phase 1 foundation script: writes the single source-of-truth edition date.

Calls the unmodified edition-date calculation (see edition_date_lib.py,
extracted verbatim from app.py's homepage route) and writes the result to
Site Data/edition.json. Intended to run as the very first step of the
morning pipeline, before any other script. Not yet wired into cron.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from edition_date_lib import get_edition_date_str

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "Site Data" / "edition.json"


def main():
    edition_date = get_edition_date_str()
    payload = {
        "edition_date": edition_date,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"edition_date: {edition_date}")
    print(f"wrote: {OUT_PATH}")


if __name__ == "__main__":
    main()
