"""
Build Site Data/dfs_board.json — DFS projections/prices from
DailyFantasyFuel (DraftKings + FanDuel), via Firecrawl.

Pure data layer — no Game Intelligence/Dope Sheet wiring in this phase.

Edition date is read exclusively from Site Data/edition.json via
scripts/edition_date_lib.read_edition_date(). This script never
calculates its own date. If edition.json is missing, it fails clearly
and writes nothing — no fallback date, no misleading output.

Failure behavior:
  - Missing FIRECRAWL_API_KEY      -> log to audit, exit 1, no board written.
  - Both platform scrapes fail     -> log to audit, exit 1, no board written.
  - One platform scrape fails      -> board is still written with the
                                       successful platform's records; the
                                       failure is logged to the audit file.
  - Never crashes unrelated systems. Game Intelligence treats a missing
    dfs_board.json as optional (wired up in a later phase, not this one).

Usage:
    python3 scripts/update_dfs_board.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edition_date_lib import read_edition_date
from dfs_props_lib import (
    DATA_DIR,
    write_json,
    load_firecrawl_api_key,
    firecrawl_scrape,
    build_team_alias_map,
    normalize_team_abbr,
    build_game_id_lookup,
    find_game_id,
    load_audit,
    save_audit,
    parse_markdown_tables,
    to_number,
)

OUTPUT_PATH = DATA_DIR / "dfs_board.json"

DFF_SOURCES = [
    {"platform": "DraftKings", "url": "https://www.dailyfantasyfuel.com/mlb/projections/draftkings/"},
    {"platform": "FanDuel", "url": "https://www.dailyfantasyfuel.com/mlb/projections/fanduel/"},
]

# Column-name variants -> canonical field, matched case-insensitively
# against markdown table headers. DailyFantasyFuel's exact header wording
# was not verifiable from this local Mac (no Firecrawl credentials) —
# Phase 1 proved extraction works on Hermes/VPS, so these aliases should be
# confirmed/extended there against real scraped markdown.
COLUMN_ALIASES = {
    "player": "player_name", "name": "player_name", "player_name": "player_name",
    "pos": "position", "position": "position",
    "team": "team",
    "opp": "opponent", "opponent": "opponent", "vs": "opponent",
    "salary": "salary",
    "proj": "projection", "proj.": "projection", "proj fpts": "projection",
    "projection": "projection", "fpts": "projection",
    "value": "value_score", "val": "value_score", "value_score": "value_score",
    "slate": "slate",
    "status": "status",
}

def parse_dff_markdown(markdown, platform):
    """Parse a DailyFantasyFuel projections page (markdown) into raw DFS
    rows for one platform. Returns a list of dicts with whatever fields
    could be extracted — never fabricates missing fields."""
    raw_rows = parse_markdown_tables(markdown)
    records = []
    for row in raw_rows:
        mapped = {}
        for raw_key, value in row.items():
            field = COLUMN_ALIASES.get(raw_key.strip().lower())
            if field:
                mapped[field] = value
        if not mapped.get("player_name"):
            continue

        records.append({
            "player_name": mapped.get("player_name"),
            "team": mapped.get("team"),
            "opponent": mapped.get("opponent"),
            "platform": platform,
            "position": mapped.get("position"),
            "salary": to_number(mapped.get("salary")),
            "projection": to_number(mapped.get("projection")),
            "value_score": to_number(mapped.get("value_score")),
            "slate": mapped.get("slate"),
            "status": mapped.get("status"),
        })
    return records


def main():
    try:
        edition_date = read_edition_date()
    except Exception as e:
        print(f"  ✗ {e}")
        sys.exit(1)

    audit = load_audit(edition_date)

    api_key = load_firecrawl_api_key()
    if not api_key:
        msg = "FIRECRAWL_API_KEY not set — cannot scrape DailyFantasyFuel"
        print(f"  ✗ {msg}")
        audit["errors"].append(f"[dfs_board] {msg}")
        save_audit(audit)
        sys.exit(1)

    all_rows = []
    failures = []
    for src in DFF_SOURCES:
        print(f"  Fetching {src['platform']} projections via Firecrawl...")
        markdown, error = firecrawl_scrape(api_key, src["url"])
        if error:
            print(f"  ✗ {src['platform']} scrape failed: {error}")
            failures.append(f"[dfs_board] {src['platform']}: {error}")
            continue
        rows = parse_dff_markdown(markdown, src["platform"])
        print(f"  ✓ {src['platform']}: {len(rows)} player rows parsed")
        all_rows.extend(rows)

    if failures:
        audit["errors"].extend(failures)

    if not all_rows:
        msg = "No DFS rows parsed from any platform — not writing dfs_board.json"
        print(f"  ✗ {msg}")
        audit["errors"].append(f"[dfs_board] {msg}")
        save_audit(audit)
        sys.exit(1)

    alias_map = build_team_alias_map()
    game_id_lookup = build_game_id_lookup()

    team_issues = []
    matched = 0
    unmatched = 0
    players = []
    for row in all_rows:
        team_abbr = normalize_team_abbr(row.get("team"), alias_map)
        opp_abbr = normalize_team_abbr(row.get("opponent"), alias_map)

        if row.get("team") and not team_abbr:
            team_issues.append(f"[dfs_board] unrecognized team '{row.get('team')}' for {row.get('player_name')}")
        if row.get("opponent") and not opp_abbr:
            team_issues.append(f"[dfs_board] unrecognized opponent '{row.get('opponent')}' for {row.get('player_name')}")

        game_id = find_game_id(team_abbr, opp_abbr, game_id_lookup) if team_abbr and opp_abbr else None
        match_status = "matched" if game_id else "unmatched"
        if match_status == "matched":
            matched += 1
        else:
            unmatched += 1

        players.append({
            "player_name": row.get("player_name"),
            "team": team_abbr or row.get("team"),
            "opponent": opp_abbr or row.get("opponent"),
            "game_id": game_id,
            "platform": row.get("platform"),
            "position": row.get("position"),
            "salary": row.get("salary"),
            "projection": row.get("projection"),
            "value_score": row.get("value_score"),
            "slate": row.get("slate"),
            "status": row.get("status"),
            "match_status": match_status,
        })

    output = {
        "date": edition_date,
        "source": "dailyfantasyfuel",
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "players": players,
    }
    write_json(OUTPUT_PATH, output)
    print(f"  ✓ Wrote {OUTPUT_PATH} ({len(players)} records, {matched} matched, {unmatched} unmatched)")

    audit["dfs_records"] = len(players)
    audit["dfs_matched"] = matched
    audit["dfs_unmatched"] = unmatched
    audit["team_issues"].extend(team_issues)
    save_audit(audit)


if __name__ == "__main__":
    main()
