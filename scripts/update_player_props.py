"""
Build Site Data/player_props.json — MLB player prop lines from BettingPros,
via Firecrawl.

Pure data layer — no Game Intelligence/Dope Sheet wiring in this phase.

Edition date is read exclusively from Site Data/edition.json via
scripts/edition_date_lib.read_edition_date(). This script never
calculates its own date. If edition.json is missing, it fails clearly
and writes nothing — no fallback date, no misleading output.

BettingPros uses abbreviated names ("B. Woodruff"). Name resolution uses
the existing Barrel Proof player_aliases.json / player_index.json (see
scripts/dfs_props_lib.resolve_abbreviated_name) — no new isolated name
normalizer. If a name can't be confidently resolved (no match, or an
ambiguous same-team last-name collision), player_name stays the raw
abbreviated form and match_status is "unmatched"; the ambiguity is logged
to dfs_props_audit.json's player_name_issues, never guessed.

best_book, projection, and edge_label are not available from BettingPros'
working picks pages per the Phase 1 POC — they are always written as null,
never fabricated.

Failure behavior:
  - Missing FIRECRAWL_API_KEY      -> log to audit, exit 1, nothing written.
  - All market-page scrapes fail   -> log to audit, exit 1, nothing written.
  - Some market pages fail         -> props.json still written with the
                                       successful markets' records; failures
                                       logged to the audit file.
  - Never crashes unrelated systems. Game Intelligence treats a missing
    player_props.json as optional (wired up in a later phase, not this one).

Usage:
    python3 scripts/update_player_props.py
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
    load_player_resolution_data,
    resolve_abbreviated_name,
    normalize_market,
    load_audit,
    save_audit,
    parse_markdown_tables,
)

OUTPUT_PATH = DATA_DIR / "player_props.json"

# Per Phase 1 POC: hits / total_bases / outs_recorded were proven working;
# home_runs / rbis / pitcher_strikeouts are additional markets BettingPros
# exposes but weren't exercised in the capped POC run. URL slugs are a
# best-effort guess at BettingPros' picks-page convention and must be
# confirmed/corrected by Hermes/VPS against the pages Phase 1 actually used.
PROP_MARKET_PAGES = [
    {"market": "hits", "url": "https://www.bettingpros.com/mlb/picks/prop-bets/hits/"},
    {"market": "total_bases", "url": "https://www.bettingpros.com/mlb/picks/prop-bets/total-bases/"},
    {"market": "outs_recorded", "url": "https://www.bettingpros.com/mlb/picks/prop-bets/outs-recorded/"},
    {"market": "home_runs", "url": "https://www.bettingpros.com/mlb/picks/prop-bets/home-runs/"},
    {"market": "rbis", "url": "https://www.bettingpros.com/mlb/picks/prop-bets/rbis/"},
    {"market": "pitcher_strikeouts", "url": "https://www.bettingpros.com/mlb/picks/prop-bets/strikeouts/"},
]

COLUMN_ALIASES = {
    "player": "raw_player_name", "name": "raw_player_name", "player_name": "raw_player_name",
    "team": "team",
    "opp": "opponent", "opponent": "opponent", "vs": "opponent",
    "line": "line", "prop": "line",
    "over": "over_odds", "over_odds": "over_odds", "o": "over_odds",
    "under": "under_odds", "under_odds": "under_odds", "u": "under_odds",
    "pick": "recommendation", "recommendation": "recommendation", "best bet": "recommendation",
}


def parse_bettingpros_markdown(markdown, market):
    """Parse a BettingPros picks page (markdown) into raw prop rows for one
    market. Returns a list of dicts with whatever fields could be
    extracted — never fabricates missing fields (best_book, projection,
    edge_label are not present on these pages per the Phase 1 POC)."""
    raw_rows = parse_markdown_tables(markdown)
    records = []
    for row in raw_rows:
        mapped = {}
        for raw_key, value in row.items():
            field = COLUMN_ALIASES.get(raw_key.strip().lower())
            if field:
                mapped[field] = value
        if not mapped.get("raw_player_name"):
            continue

        line_raw = mapped.get("line")
        line_val = None
        if line_raw:
            try:
                line_val = float("".join(c for c in line_raw if c.isdigit() or c in ".-"))
            except ValueError:
                line_val = None

        records.append({
            "raw_player_name": mapped.get("raw_player_name"),
            "team": mapped.get("team"),
            "opponent": mapped.get("opponent"),
            "market": market,
            "line": line_val,
            "over_odds": mapped.get("over_odds"),
            "under_odds": mapped.get("under_odds"),
            "best_book": None,
            "projection": None,
            "recommendation": mapped.get("recommendation"),
            "edge_label": None,
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
        msg = "FIRECRAWL_API_KEY not set — cannot scrape BettingPros"
        print(f"  ✗ {msg}")
        audit["errors"].append(f"[player_props] {msg}")
        save_audit(audit)
        sys.exit(1)

    all_rows = []
    failures = []
    for src in PROP_MARKET_PAGES:
        print(f"  Fetching {src['market']} props via Firecrawl...")
        markdown, error = firecrawl_scrape(api_key, src["url"])
        if error:
            print(f"  ✗ {src['market']} scrape failed: {error}")
            failures.append(f"[player_props] {src['market']}: {error}")
            continue
        rows = parse_bettingpros_markdown(markdown, src["market"])
        print(f"  ✓ {src['market']}: {len(rows)} prop rows parsed")
        all_rows.extend(rows)

    if failures:
        audit["errors"].extend(failures)

    if not all_rows:
        msg = "No prop rows parsed from any market — not writing player_props.json"
        print(f"  ✗ {msg}")
        audit["errors"].append(f"[player_props] {msg}")
        save_audit(audit)
        sys.exit(1)

    alias_map = build_team_alias_map()
    game_id_lookup = build_game_id_lookup()
    aliases, by_slug, index_list, _ = load_player_resolution_data()

    team_issues = []
    player_name_issues = []
    matched = 0
    unmatched = 0
    props = []
    for row in all_rows:
        market = normalize_market(row.get("market"))
        if not market:
            team_issues.append(f"[player_props] unrecognized market '{row.get('market')}'")
            continue

        team_abbr = normalize_team_abbr(row.get("team"), alias_map)
        opp_abbr = normalize_team_abbr(row.get("opponent"), alias_map)
        if row.get("team") and not team_abbr:
            team_issues.append(f"[player_props] unrecognized team '{row.get('team')}' for {row.get('raw_player_name')}")
        if row.get("opponent") and not opp_abbr:
            team_issues.append(f"[player_props] unrecognized opponent '{row.get('opponent')}' for {row.get('raw_player_name')}")

        full_name, name_status, method, issue = resolve_abbreviated_name(
            row.get("raw_player_name"), team_abbr, aliases, by_slug, index_list
        )
        if issue:
            player_name_issues.append(f"[player_props] {issue}")

        game_id = find_game_id(team_abbr, opp_abbr, game_id_lookup) if team_abbr and opp_abbr else None
        match_status = "matched" if (name_status == "matched" and game_id) else "unmatched"
        if name_status == "matched" and not game_id:
            # Name resolved, but no schedule game_id — still record the
            # resolved name; just flag the overall record as unmatched.
            pass
        if match_status == "matched":
            matched += 1
        else:
            unmatched += 1

        props.append({
            "player_name": full_name,
            "raw_player_name": row.get("raw_player_name"),
            "team": team_abbr or row.get("team"),
            "opponent": opp_abbr or row.get("opponent"),
            "game_id": game_id,
            "market": market,
            "line": row.get("line"),
            "over_odds": row.get("over_odds"),
            "under_odds": row.get("under_odds"),
            "best_book": row.get("best_book"),
            "projection": row.get("projection"),
            "recommendation": row.get("recommendation"),
            "edge_label": row.get("edge_label"),
            "match_status": match_status,
            "name_match_method": method,
        })

    output = {
        "date": edition_date,
        "source": "bettingpros",
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "props": props,
    }
    write_json(OUTPUT_PATH, output)
    print(f"  ✓ Wrote {OUTPUT_PATH} ({len(props)} records, {matched} matched, {unmatched} unmatched)")

    audit["prop_records"] = len(props)
    audit["prop_matched"] = matched
    audit["prop_unmatched"] = unmatched
    audit["team_issues"].extend(team_issues)
    audit["player_name_issues"].extend(player_name_issues)
    save_audit(audit)


if __name__ == "__main__":
    main()
