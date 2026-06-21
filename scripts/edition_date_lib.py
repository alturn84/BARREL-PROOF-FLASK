"""
Shared edition-date calculation.

This is a verbatim extraction of the date logic found in app.py's
`/` (homepage) route (around line 1657-1664 at the time of writing), which
itself was a prior bug fix for UTC rollover on Render after 8pm ET. The
logic is copied unmodified — same ZoneInfo lookup, same try/except
fallback to UTC-4 when zoneinfo/tzdata is unavailable. app.py is left
untouched; this module exists only so other scripts can reuse the same
calculation without duplicating it again.
"""

import json
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EDITION_PATH = REPO_ROOT / "Site Data" / "edition.json"


def get_edition_date_et():
    """Return today's date (as a date object) in America/New_York,
    falling back to UTC-4 if zoneinfo is unavailable. Identical logic
    to the inline calculation in app.py's homepage route."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        from datetime import timezone, timedelta
        return (datetime.now(timezone.utc) - timedelta(hours=4)).date()


def get_edition_date_str():
    """Return today's edition date as YYYY-MM-DD (ET)."""
    return get_edition_date_et().strftime("%Y-%m-%d")


def read_edition_date():
    """Read edition_date from Site Data/edition.json — the single
    authoritative source for downstream generator scripts.

    Does not calculate a fallback date under any circumstance. Raises a
    clear exception if edition.json is missing or malformed, so callers
    fail safely instead of silently computing their own date."""
    if not EDITION_PATH.exists():
        raise RuntimeError(
            f"edition_date unavailable: {EDITION_PATH} does not exist. "
            "Run scripts/write_edition_date.py first."
        )
    try:
        data = json.loads(EDITION_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"edition_date unavailable: failed to parse {EDITION_PATH}: {e}")

    edition_date = data.get("edition_date")
    if not edition_date:
        raise RuntimeError(f"edition_date unavailable: {EDITION_PATH} has no 'edition_date' field")

    return edition_date
