#!/usr/bin/env python3
"""
update_archive.py — Barrel Proof Baseball
──────────────────────────────────────────
Builds and maintains daily snapshot archive.

Pipeline position (runs after all daily updates):
    update_game_cards.py
    update_game_of_day.py
    update_around_the_league.py
    update_game_to_watch.py
    update_press_box.py
    → update_archive.py

Directory layout:
    Site Data/archive/
      archive_index.json
      2026/
        index.json
        2026-03.json
        2026-04.json
        2026-05.json
        snapshots/
          2026-03-25.json
          ...

Usage:
    python3 update_archive.py                  # yesterday
    python3 update_archive.py 2026-05-31       # specific date
    python3 update_archive.py --full           # all available dates
    python3 update_archive.py --facts-only     # skip edition capture
    python3 update_archive.py --dry-run        # preview, no writes
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

VAULT       = Path("/Users/allanturner/BARREL PROOF")
DAILY       = VAULT / "Daily"
SITE_DATA   = VAULT / "Site Data"
ARCHIVE_DIR = VAULT / "Site Data" / "archive"

VALID_SOURCE_TYPES = {"ap", "getty", "mlb", "team", "manual", "illustrated"}
MEDIA_DIR = Path(__file__).resolve().parent / "media" / "lead-images"

COMPLETENESS_RANK = {"historical": 0, "partial": 1, "full": 2}


# ── Team abbreviation → full city name ───────────────────────────────────────
# Copied exactly from update_game_cards.py
TEAM_CITIES = {
    "SD": "San Diego", "WSH": "Washington", "KC": "Kansas City",
    "TEX": "Texas", "LAA": "Los Angeles", "TB": "Tampa Bay",
    "CHC": "Chicago", "STL": "St. Louis", "AZ": "Arizona",
    "SEA": "Seattle", "MIN": "Minnesota", "PIT": "Pittsburgh",
    "MIA": "Miami", "NYM": "New York", "PHI": "Philadelphia",
    "LAD": "Los Angeles", "MIL": "Milwaukee", "HOU": "Houston",
    "SF": "San Francisco", "COL": "Colorado", "BOS": "Boston",
    "CLE": "Cleveland", "ATL": "Atlanta", "CIN": "Cincinnati",
    "DET": "Detroit", "CWS": "Chicago", "TOR": "Toronto",
    "BAL": "Baltimore", "NYY": "New York", "ATH": "Athletics",
    "WAS": "Washington",
}


# ── Parse one game block from the markdown ────────────────────────────────────
# Copied exactly from update_game_cards.py
def parse_game(block):
    lines = block.strip().split('\n')
    game  = {}

    header = lines[0] if lines else ''
    m = re.match(r'### (\w+) @ (\w+) — (.+)', header)
    if not m:
        return None
    away_abbr = m.group(1)
    home_abbr = m.group(2)
    score_str = m.group(3)

    score_m   = re.findall(r'\*\*(\w+)\s+(\d+)\*\*|(\w+)\s+(\d+)', score_str)
    away_runs = home_runs = 0
    for sm in score_m:
        if sm[0]:
            r = int(sm[1])
            if sm[0] == away_abbr: away_runs = r
            else: home_runs = r
        else:
            r = int(sm[3])
            if sm[2] == away_abbr: away_runs = r
            elif sm[2] == home_abbr: home_runs = r

    game['away_abbr'] = away_abbr
    game['home_abbr'] = home_abbr
    game['away_city'] = TEAM_CITIES.get(away_abbr, away_abbr)
    game['home_city'] = TEAM_CITIES.get(home_abbr, home_abbr)
    game['away_runs'] = away_runs
    game['home_runs'] = home_runs
    game['winner']    = 'away' if away_runs > home_runs else 'home'

    venue_m = re.search(r'\*\*Venue:\*\* ([^·]+)', block)
    game['venue'] = venue_m.group(1).strip() if venue_m else ''

    dur_m = re.search(r'\*\*Duration:\*\* ([^\s·]+)', block)
    game['duration'] = dur_m.group(1).strip() if dur_m else ''

    att_m = re.search(r'\*\*Attendance:\*\* ([\d,]+)', block)
    game['attendance'] = att_m.group(1).strip() if att_m else ''

    dec_m     = re.search(r'\*\*Decisions:\*\* (.+)', block)
    decisions = {'W': '', 'L': '', 'SV': ''}
    if dec_m:
        dec_str = dec_m.group(1)
        for key in ('W', 'L', 'SV'):
            km = re.search(rf'{key}: ([^·\n]+?)(?:\s*·|\s*$)', dec_str)
            if km:
                decisions[key] = km.group(1).strip()
    game['decisions'] = decisions

    ls_m = re.search(
        r'\| Team \|(.+?)\n\|[-|]+\|\n\| \*\*' + re.escape(away_abbr) + r'\*\* \|(.+?)\n\| \*\*' + re.escape(home_abbr) + r'\*\* \|(.+?)(?:\n|$)',
        block
    )
    if not ls_m:
        ls_m = re.search(
            r'\| Team \|(.+?)\n\|[-|]+\|\n\|[^|]*' + re.escape(away_abbr) + r'[^|]* \|(.+?)\n\|[^|]*' + re.escape(home_abbr) + r'[^|]* \|(.+?)(?:\n|$)',
            block
        )

    innings = away_line = home_line = []
    away_rhe = [str(away_runs), '', '']
    home_rhe = [str(home_runs), '', '']

    if ls_m:
        def parse_row(row):
            cells = [c.strip().strip('*') for c in row.split('|')]
            return [c for c in cells if c]

        hdr   = parse_row(ls_m.group(1))
        arow  = parse_row(ls_m.group(2))
        hrow  = parse_row(ls_m.group(3))
        n_inn = len(arow) - 3
        innings   = hdr[:n_inn]
        away_line = arow[:n_inn]
        home_line = hrow[:n_inn]
        away_rhe  = arow[-3:]
        home_rhe  = hrow[-3:]

    game['innings']   = innings
    game['away_line'] = away_line
    game['home_line'] = home_line
    game['away_rhe']  = away_rhe
    game['home_rhe']  = home_rhe

    def parse_batting(team_abbr):
        pattern = rf'\*\*{re.escape(team_abbr)} Batting\*\*\n\n\|[^\n]+\|\n\|[-|]+\|\n((?:\|[^\n]+\|\n?)+)'
        m = re.search(pattern, block)
        if not m:
            return []
        rows = []
        for row in m.group(1).strip().split('\n'):
            cells = [c.strip() for c in row.split('|')]
            cells = [c for c in cells if c]
            if len(cells) < 9:
                continue
            batter_pos = cells[0]
            bm = re.match(r'(.+?)\s*\((\w+)\)', batter_pos)
            name = bm.group(1).strip() if bm else batter_pos
            pos  = bm.group(2).strip() if bm else ''
            parts = name.split()
            short = f"{parts[0][0]}.{parts[-1]}" if len(parts) > 1 else name
            try:
                ab  = int(cells[2])
                r   = int(cells[3])
                h   = int(cells[4])
                dbl = int(cells[5])
                trp = int(cells[6])
                hr  = int(cells[7])
                rbi = int(cells[8])
            except (ValueError, IndexError):
                continue
            rows.append({
                'name': short, 'pos': pos,
                'ab': ab, 'r': r, 'h': h,
                '2b': dbl, '3b': trp, 'hr': hr, 'rbi': rbi,
            })
        return rows

    game['away_batting'] = parse_batting(away_abbr)
    game['home_batting'] = parse_batting(home_abbr)

    def parse_pitching(team_abbr):
        pattern = rf'\*\*{re.escape(team_abbr)} Pitching\*\*\n\n\|[^\n]+\|\n\|[-|]+\|\n((?:\|[^\n]+\|\n?)+)'
        m = re.search(pattern, block)
        if not m:
            return []
        rows = []
        for row in m.group(1).strip().split('\n'):
            cells = [c.strip() for c in row.split('|')]
            cells = [c for c in cells if c]
            if len(cells) < 4:
                continue
            name  = cells[0].strip()
            parts = name.split()
            short = f"{parts[0][0]}.{parts[-1]}" if len(parts) > 1 else name
            try:
                ip = cells[1]
                h  = cells[2]
                r  = cells[3]
                er = cells[4] if len(cells) > 4 else ''
                bb = cells[5] if len(cells) > 5 else ''
                k  = cells[6] if len(cells) > 6 else ''
            except IndexError:
                continue
            rows.append({
                'name': short, 'ip': ip,
                'h': h, 'r': r, 'er': er, 'bb': bb, 'k': k,
            })
        return rows

    game['away_pitching'] = parse_pitching(away_abbr)
    game['home_pitching'] = parse_pitching(home_abbr)

    return game


# ── Lead image ───────────────────────────────────────────────────────────────
def get_lead_image_for_archive(edition_date: str):
    jpg  = MEDIA_DIR / f"{edition_date}_lead.jpg"
    webp = MEDIA_DIR / f"{edition_date}_lead.webp"
    if jpg.exists():
        filename = jpg.name
    elif webp.exists():
        filename = webp.name
    else:
        return None
    captions_path = MEDIA_DIR / "captions.json"
    try:
        captions = json.loads(captions_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    meta        = captions.get(edition_date, {})
    caption     = meta.get("caption", "").strip()
    credit      = meta.get("credit", "").strip()
    source_type = meta.get("source_type", "").strip()
    if not caption or not credit or source_type not in VALID_SOURCE_TYPES:
        return None
    return {
        "filename":    filename,
        "caption":     caption,
        "credit":      credit,
        "source_type": source_type,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────
def atomic_write(path: Path, data: dict):
    """Write JSON atomically via .tmp then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.rename(path)


def load_json_safe(path: Path):
    """Load JSON, returning None on any error."""
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"  ⚠ Could not load {path.name}: {e}", flush=True)
        return None


def snapshot_path(date_str: str) -> Path:
    year = date_str[:4]
    return ARCHIVE_DIR / year / "snapshots" / f"{date_str}.json"


def get_all_daily_dates() -> list:
    """Return sorted list of all dates with available markdown files."""
    pattern = re.compile(r'(\d{4}-\d{2}-\d{2})-mlb-box-scores\.md')
    dates = []
    for f in DAILY.glob("*-mlb-box-scores.md"):
        m = pattern.match(f.name)
        if m:
            dates.append(m.group(1))
    return sorted(dates)


def parse_games_from_md(md_path: Path) -> list:
    """Parse all game blocks from a daily markdown file."""
    text = md_path.read_text(encoding='utf-8')
    raw_blocks = re.split(r'\n(?=### )', text)
    raw_blocks = [b for b in raw_blocks if b.strip().startswith('###')]
    games = []
    for block in raw_blocks:
        g = parse_game(block)
        if g:
            games.append(g)
    return games


# ── Edition capture ───────────────────────────────────────────────────────────
def capture_edition(target_date: str) -> dict:
    """
    Attempt to capture edition fields from Site Data JSONs.
    Returns dict with captured timestamp and six edition fields (or null).
    Edition capture is best-effort and non-fatal.
    """
    captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    edition = {"captured": captured_at}

    # Files with internal date fields
    internal_date_sources = [
        ("standings",        "standings.json",        "updated"),   # date portion of "updated"
        ("game_cards",       "game_cards.json",        "date"),
        ("press_box",        "press_box.json",         "date"),
    ]
    for key, filename, date_field in internal_date_sources:
        path = SITE_DATA / filename
        try:
            if not path.exists():
                edition[key] = None
                continue
            data = load_json_safe(path)
            if data is None:
                edition[key] = None
                continue
            raw = data.get(date_field, "")
            file_date = raw[:10] if raw else ""   # handles "2026-05-31 08:05" → "2026-05-31"
            if file_date == target_date:
                edition[key] = data
            else:
                if file_date:
                    print(f"  ⚠ {filename}: date {file_date!r} != {target_date} — null", flush=True)
                edition[key] = None
        except Exception as e:
            print(f"  ⚠ {filename}: {e}", flush=True)
            edition[key] = None

    # Files matched by mtime (no internal date)
    mtime_sources = [
        ("game_of_day",        "game_of_day.json"),
        ("game_to_watch",      "game_to_watch.json"),
        ("around_the_league",  "around_the_league.json"),
    ]
    for key, filename in mtime_sources:
        path = SITE_DATA / filename
        try:
            if not path.exists():
                edition[key] = None
                continue
            mtime_date = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
            if mtime_date == target_date:
                data = load_json_safe(path)
                edition[key] = data  # may be None if malformed — that's fine
            else:
                print(f"  ⚠ {filename}: mtime {mtime_date} != {target_date} — null", flush=True)
                edition[key] = None
        except Exception as e:
            print(f"  ⚠ {filename}: {e}", flush=True)
            edition[key] = None

    return edition


def null_edition() -> dict:
    """Return an edition block with all fields null (for --facts-only or backfill)."""
    return {
        "captured":          None,
        "standings":         None,
        "game_cards":        None,
        "game_of_day":       None,
        "game_to_watch":     None,
        "around_the_league": None,
        "press_box":         None,
    }


def compute_completeness(edition: dict) -> str:
    edition_keys = ["standings", "game_cards", "game_of_day",
                    "game_to_watch", "around_the_league", "press_box"]
    populated = sum(1 for k in edition_keys if edition.get(k) is not None)
    if populated == 0:
        return "historical"
    elif populated == len(edition_keys):
        return "full"
    else:
        return "partial"


# ── Snapshot processing ───────────────────────────────────────────────────────
def process_date(date_str: str, dry_run: bool, full_flag: bool, facts_only: bool) -> str:
    """
    Build or upgrade a snapshot for date_str.
    Returns: "written", "skipped", or "no_md"
    """
    snap_path_file = snapshot_path(date_str)

    # Load existing snapshot if present
    existing_rank = -1
    if snap_path_file.exists():
        existing = load_json_safe(snap_path_file)
        if existing:
            existing_rank = COMPLETENESS_RANK.get(
                existing.get("completeness", "historical"), 0
            )
            # Skip full snapshots unless --full flag
            if existing_rank == 2 and not full_flag:
                print(f"  {date_str}: already full — skipping", flush=True)
                return "skipped"

    # Require markdown source
    md_path = DAILY / f"{date_str}-mlb-box-scores.md"
    if not md_path.exists():
        print(f"  {date_str}: no markdown file — skipping", flush=True)
        return "no_md"

    # Parse facts
    games = parse_games_from_md(md_path)

    # Capture edition
    if facts_only:
        edition = null_edition()
    else:
        edition = capture_edition(date_str)

    completeness = compute_completeness(edition)
    new_rank = COMPLETENESS_RANK[completeness]

    # Overwrite guard: only proceed if new rank is strictly greater
    if existing_rank >= 0 and new_rank <= existing_rank:
        from_label = ["historical", "partial", "full"][existing_rank]
        print(f"  {date_str}: existing {from_label} (rank {existing_rank})"
              f" >= new {completeness} (rank {new_rank}) — skipping", flush=True)
        return "skipped"

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    snapshot = {
        "date":         date_str,
        "display_date": dt.strftime("%A, %B %-d, %Y"),
        "day_of_week":  dt.strftime("%A"),
        "generated":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "completeness": completeness,
        "facts": {
            "game_count": len(games),
            "games":      games,
        },
        "edition": edition,
    }

    # Attach lead image if one exists for this date (omit key entirely if absent)
    lead_img = get_lead_image_for_archive(date_str)
    if lead_img:
        snapshot["lead_image"] = lead_img

    if dry_run:
        li_note = f", lead_image={lead_img['filename']}" if lead_img else ""
        print(f"  [DRY RUN] {date_str}: {completeness}, {len(games)} games{li_note}", flush=True)
        return "skipped"

    atomic_write(snap_path_file, snapshot)
    print(f"  ✓ {date_str}: {completeness}, {len(games)} games → {snap_path_file.name}", flush=True)
    return "written"


# ── Index rebuilds ────────────────────────────────────────────────────────────
def rebuild_indexes():
    """
    Rebuild month indexes, year indexes, and archive_index.json from scratch
    by scanning all snapshot files. Unconditional after any write.
    """
    print("  Rebuilding indexes...", flush=True)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Scan all snapshot files
    # Structure: ARCHIVE_DIR/<year>/snapshots/<date>.json
    all_entries = []   # list of dicts with date, year, month, game_count, completeness
    for snap_file in sorted(ARCHIVE_DIR.glob("*/snapshots/*.json")):
        data = load_json_safe(snap_file)
        if not data:
            continue
        date_str = data.get("date", "")
        if not re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            continue
        year  = int(date_str[:4])
        month = int(date_str[5:7])
        all_entries.append({
            "date":         date_str,
            "display_date": data.get("display_date", ""),
            "year":         year,
            "month":        month,
            "game_count":   data.get("facts", {}).get("game_count", 0),
            "completeness": data.get("completeness", "historical"),
        })

    if not all_entries:
        print("  No snapshots found — skipping index rebuild.", flush=True)
        return

    # Group by year → month
    from collections import defaultdict
    by_year_month = defaultdict(lambda: defaultdict(list))
    for e in all_entries:
        by_year_month[e["year"]][e["month"]].append(e)

    MONTH_NAMES = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December",
    }

    year_summaries = []

    for year in sorted(by_year_month.keys()):
        year_str  = str(year)
        year_dir  = ARCHIVE_DIR / year_str
        month_summaries = []

        for month in sorted(by_year_month[year].keys()):
            month_str    = f"{month:02d}"
            month_entries = sorted(by_year_month[year][month], key=lambda x: x["date"])
            month_name   = MONTH_NAMES.get(month, str(month))

            dates_list = []
            for e in month_entries:
                rel_snap = f"snapshots/{e['date']}.json"
                dates_list.append({
                    "date":          e["date"],
                    "display_date":  e["display_date"],
                    "game_count":    e["game_count"],
                    "completeness":  e["completeness"],
                    "snapshot_path": rel_snap,
                })

            total_games      = sum(e["game_count"] for e in month_entries)
            full_count       = sum(1 for e in month_entries if e["completeness"] == "full")
            historical_count = sum(1 for e in month_entries if e["completeness"] == "historical")

            month_index = {
                "year":             year,
                "month":            month,
                "month_name":       month_name,
                "dates":            dates_list,
                "total_games":      total_games,
                "full_count":       full_count,
                "historical_count": historical_count,
                "generated":        now_str,
            }
            month_index_path = year_dir / f"{year_str}-{month_str}.json"
            atomic_write(month_index_path, month_index)

            month_summaries.append({
                "month":            month,
                "month_name":       month_name,
                "game_count":       total_games,
                "date_count":       len(month_entries),
                "full_count":       full_count,
                "historical_count": historical_count,
                "index_path":       f"{year_str}-{month_str}.json",
            })

        # Year index
        year_entries = all_entries  # filter to this year
        year_entries_filtered = [e for e in all_entries if e["year"] == year]
        year_total_dates = len(year_entries_filtered)
        year_total_games = sum(e["game_count"] for e in year_entries_filtered)
        year_full        = sum(1 for e in year_entries_filtered if e["completeness"] == "full")
        year_historical  = sum(1 for e in year_entries_filtered if e["completeness"] == "historical")

        year_index = {
            "year":            year,
            "months":          month_summaries,
            "total_dates":     year_total_dates,
            "total_games":     year_total_games,
            "full_count":      year_full,
            "historical_count": year_historical,
            "generated":       now_str,
        }
        atomic_write(year_dir / "index.json", year_index)

        year_summaries.append({
            "year":            year,
            "date_count":      year_total_dates,
            "game_count":      year_total_games,
            "full_count":      year_full,
            "historical_count": year_historical,
            "index_path":      f"{year_str}/index.json",
        })

    # archive_index.json
    all_dates = sorted(e["date"] for e in all_entries)
    total_dates  = len(all_dates)
    total_games  = sum(e["game_count"] for e in all_entries)
    full_editions    = sum(1 for e in all_entries if e["completeness"] == "full")
    historical_count = sum(1 for e in all_entries if e["completeness"] == "historical")

    archive_index = {
        "updated":          now_str,
        "earliest_date":    all_dates[0],
        "latest_date":      all_dates[-1],
        "total_dates":      total_dates,
        "total_games":      total_games,
        "full_editions":    full_editions,
        "historical_count": historical_count,
        "years":            year_summaries,
    }
    atomic_write(ARCHIVE_DIR / "archive_index.json", archive_index)
    print(f"  ✓ Indexes rebuilt: {total_dates} dates, {total_games} games", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args       = sys.argv[1:]
    dry_run    = "--dry-run"    in args
    full_flag  = "--full"       in args
    facts_only = "--facts-only" in args
    date_args  = [a for a in args if not a.startswith("--")]

    if dry_run:
        print("  [DRY RUN MODE — no files will be written]", flush=True)

    # Determine dates to process
    if date_args:
        dates = [date_args[0]]
    elif full_flag:
        dates = get_all_daily_dates()
        print(f"  --full: processing {len(dates)} available dates", flush=True)
    else:
        yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        dates = [yesterday]

    written  = 0
    skipped  = 0
    no_md    = 0

    for date_str in dates:
        result = process_date(date_str, dry_run, full_flag, facts_only)
        if result == "written":
            written += 1
        elif result == "skipped":
            skipped += 1
        elif result == "no_md":
            no_md += 1

    print(f"\n  Summary: {written} written, {skipped} skipped, {no_md} no markdown", flush=True)

    if written > 0 and not dry_run:
        rebuild_indexes()

    print(f"\n✓  Done. {datetime.now()}", flush=True)


if __name__ == "__main__":
    main()
