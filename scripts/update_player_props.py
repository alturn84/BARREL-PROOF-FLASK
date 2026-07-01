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
  - Page Not Found or markdown < 500 chars -> mark source failed, try next URL.
  - Never crashes unrelated systems. Game Intelligence treats a missing
    player_props.json as optional (wired up in a later phase, not this one).

Debug mode:
    python3 scripts/update_player_props.py --debug-sources
    Prints each configured URL, markdown length, and row count. No JSON written.

Usage:
    python3 scripts/update_player_props.py
    python3 scripts/update_player_props.py --debug-sources
"""

import re
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
    start_run,
    save_audit,
)

OUTPUT_PATH = DATA_DIR / "player_props.json"

# VPS validation 2026-06-30: the old /mlb/player-props/{market}/ paths all
# returned Page Not Found. Each market now has an ordered list of candidate
# URLs; the scraper tries them in order and uses the first that returns
# parseable content (>= 500 chars and no 404 indicator text).
# Responses are cached within a run so the all-markets pages are only
# fetched once even when listed under multiple markets.
PROP_MARKET_PAGES = [
    {
        "market": "pitcher_strikeouts",
        "urls": [
            "https://www.bettingpros.com/mlb/odds/player-props/strikeouts/",
            "https://www.bettingpros.com/mlb/picks/prop-bets/bet/strikeouts/",
            "https://www.bettingpros.com/mlb/picks/prop-bets/",
        ],
    },
    {
        "market": "total_bases",
        "urls": [
            "https://www.bettingpros.com/mlb/odds/player-props/total-bases/",
            "https://www.bettingpros.com/mlb/picks/prop-bets/",
        ],
    },
    {
        "market": "home_runs",
        "urls": [
            "https://www.bettingpros.com/mlb/odds/player-props/homeruns/",
            "https://www.bettingpros.com/mlb/picks/prop-bets/",
        ],
    },
    {
        "market": "hits",
        "urls": [
            "https://www.bettingpros.com/mlb/picks/prop-bets/",
            "https://www.bettingpros.com/mlb/odds/player-props/",
        ],
    },
    {
        "market": "rbis",
        "urls": [
            "https://www.bettingpros.com/mlb/picks/prop-bets/",
            "https://www.bettingpros.com/mlb/odds/player-props/",
        ],
    },
    {
        "market": "outs_recorded",
        "urls": [
            "https://www.bettingpros.com/mlb/odds/player-props/",
            "https://www.bettingpros.com/mlb/picks/prop-bets/",
        ],
    },
]

_NOT_FOUND_PHRASES = (
    "page not found", "404 not found", "404 error",
    "this page doesn't exist", "we couldn't find that page",
    "nothing to see here",
)


def _is_page_not_found(markdown):
    """True if markdown looks like a 404 page or is too short to be real content."""
    if not markdown or len(markdown) < 500:
        return True
    lower = markdown.lower()
    return any(phrase in lower for phrase in _NOT_FOUND_PHRASES)


def _fetch_cached(api_key, url, cache):
    """Fetch url via Firecrawl, caching the result so identical URLs within
    one run are not re-fetched."""
    if url not in cache:
        cache[url] = firecrawl_scrape(api_key, url)
    return cache[url]


def _debug_sources(api_key):
    """Print URL, markdown length, and row count for every configured URL.
    Does not write any JSON."""
    print("=== --debug-sources ===")
    seen = {}
    for src in PROP_MARKET_PAGES:
        market = src["market"]
        for url in src["urls"]:
            if url in seen:
                print(f"  [{market}] {url} — cached, skipping re-fetch")
                continue
            markdown, error = firecrawl_scrape(api_key, url)
            seen[url] = True
            if error:
                print(f"  [{market}] {url}")
                print(f"    status: ERROR — {error[:100]}")
                continue
            if _is_page_not_found(markdown):
                print(f"  [{market}] {url}")
                print(f"    status: NOT FOUND / too short (len={len(markdown or '')})")
                continue
            rows = parse_bettingpros_markdown(markdown, market)
            print(f"  [{market}] {url}")
            print(f"    status: OK  len={len(markdown)}  rows={len(rows)}")
    print("=== end debug-sources ===")

# Position codes BettingPros sometimes glues directly onto the end of a
# player's abbreviated name with no separating space, e.g.
# "A. Burleson1B,LF,RF,DH" or "B. WoodruffP". Order matters only in that
# two-letter codes must be tried before the bare single-letter ones so the
# alternation doesn't short-circuit on a partial match.
_POSITION_CODE = r"(?:1B|2B|3B|SS|LF|CF|RF|OF|DH|C|P)"
_GLUED_POSITION_SUFFIX_RE = re.compile(
    rf"(?<![A-Za-z]\.)((?:{_POSITION_CODE})(?:,{_POSITION_CODE})*)$"
)


def _clean_bp_player_name(raw):
    """Strip BettingPros' glued-on position-code suffix (e.g. the
    "1B,LF,RF,DH" in "A. Burleson1B,LF,RF,DH") from a raw abbreviated name.

    Matches only an exact, case-sensitive run of known position codes at
    the very end of the string with no preceding space (the scraping
    artifact is always glued directly onto the last name). Legitimate
    suffixes like "Jr." or "II" are not position codes, so they never
    match and are left untouched."""
    raw = (raw or "").strip()
    match = _GLUED_POSITION_SUFFIX_RE.search(raw)
    if not match:
        return raw
    prefix = raw[: match.start()]
    # Only strip if there's a real name left and it wasn't already
    # separated by whitespace (a legitimately-spaced position column
    # value, not a glued artifact).
    if prefix and not prefix.endswith(" "):
        return prefix
    return raw


# A bare "Over -159" / "Under +119" line is just labeled odds, not the
# pick itself — only a qualifier word (Bet/Lean/Pick/Take/Best Bet) makes
# Over/Under an actual recommendation. Without real BettingPros card
# markdown to confirm against, both regexes are necessarily best-effort.
_ODDS_LABEL_RE = re.compile(r"\b(Over|Under)\b\s*([+-]\d{2,4})\b", re.IGNORECASE)
_RECOMMENDATION_RE = re.compile(r"\b(?:Bet|Lean|Pick|Take|Best\s+Bet)[:\s]+(Over|Under)\b", re.IGNORECASE)
_ODDS_RE = re.compile(r"[+-]\d{2,4}\b")
_LINE_RE = re.compile(r"\b\d+\.\d\b")
_TEAM_OPP_RE = re.compile(r"\b([A-Z]{2,4})\s*(?:@|vs\.?|VS)\s*([A-Z]{2,4})\b")
# A BettingPros abbreviated name: "B. Woodruff", optionally with a glued
# position-code suffix that _clean_bp_player_name() strips afterward.
_NAME_RE = re.compile(r"\b([A-Z]\.\s?[A-Za-z'\.\-]+(?:" + _POSITION_CODE + r"(?:,(?:" + _POSITION_CODE + r"))*)?)\b")


def parse_bettingpros_markdown(markdown, market):
    """Parse a BettingPros player-props page (markdown) into raw prop rows
    for one market.

    Confirmed via Hermes/VPS live test: these pages render as card-style
    blocks, not markdown tables, so this scans line-by-line instead of
    looking for pipe-delimited rows. Each card is expected to contain a
    player name, a team/opponent pair, a numeric line, an over/under odds
    pair, and a recommendation — fields that aren't found are left null,
    never fabricated (best_book, projection, edge_label are never present
    on these pages and are always null)."""
    records = []
    current = None

    def flush():
        if current and current.get("raw_player_name"):
            records.append({
                "raw_player_name": _clean_bp_player_name(current.get("raw_player_name")),
                "team": current.get("team"),
                "opponent": current.get("opponent"),
                "market": market,
                "line": current.get("line"),
                "over_odds": current.get("over_odds"),
                "under_odds": current.get("under_odds"),
                "best_book": None,
                "projection": None,
                "recommendation": current.get("recommendation"),
                "edge_label": None,
            })

    for raw_line in markdown.splitlines():
        line = re.sub(r"[*_`#>]", " ", raw_line).strip()
        if not line:
            continue

        name_match = _NAME_RE.search(line)
        # A fresh name line starts a new card; flush the previous one first.
        if name_match:
            if current is not None:
                flush()
            current = {"raw_player_name": name_match.group(1)}
            continue

        if current is None:
            continue

        team_opp = _TEAM_OPP_RE.search(line)
        if team_opp:
            current.setdefault("team", team_opp.group(1))
            current.setdefault("opponent", team_opp.group(2))

        line_match = _LINE_RE.search(line)
        if line_match and "line" not in current:
            current["line"] = float(line_match.group(0))

        odds_label = _ODDS_LABEL_RE.search(line)
        if odds_label:
            side, price = odds_label.group(1).lower(), odds_label.group(2)
            current.setdefault("over_odds" if side == "over" else "under_odds", price)
            continue

        rec_match = _RECOMMENDATION_RE.search(line)
        if rec_match:
            current.setdefault("recommendation", rec_match.group(1).title())
            continue

        # Fallback: a bare odds number with no Over/Under label nearby —
        # assign to whichever side hasn't been filled yet.
        odds = _ODDS_RE.findall(line)
        if odds:
            if "over_odds" not in current:
                current["over_odds"] = odds[0]
            elif "under_odds" not in current:
                current["under_odds"] = odds[0]

    flush()
    return records


def main():
    try:
        edition_date = read_edition_date()
    except Exception as e:
        print(f"  ✗ {e}")
        sys.exit(1)

    api_key = load_firecrawl_api_key()
    if not api_key:
        audit = start_run(edition_date, "player_props")
        msg = "FIRECRAWL_API_KEY not set — cannot scrape BettingPros"
        print(f"  ✗ {msg}")
        audit["errors"].append(f"[player_props] {msg}")
        save_audit(audit)
        sys.exit(1)

    if "--debug-sources" in sys.argv:
        _debug_sources(api_key)
        return

    audit = start_run(edition_date, "player_props")

    all_rows = []
    failures = []
    url_cache = {}
    for src in PROP_MARKET_PAGES:
        market = src["market"]
        fetched = False
        for url in src["urls"]:
            markdown, error = _fetch_cached(api_key, url, url_cache)
            if error:
                note = f"scrape error: {error[:80]}"
                print(f"    ✗ {market} @ {url}: {note}")
                failures.append(f"[player_props] {market} @ {url}: {note}")
                continue
            if _is_page_not_found(markdown):
                note = f"Page Not Found / too short (len={len(markdown or '')})"
                print(f"    ✗ {market} @ {url}: {note}")
                failures.append(f"[player_props] {market} @ {url}: {note}")
                continue
            rows = parse_bettingpros_markdown(markdown, market)
            print(f"  ✓ {market}: {len(rows)} prop rows from {url}")
            all_rows.extend(rows)
            fetched = True
            break  # success — don't try remaining URLs for this market
        if not fetched:
            print(f"  ✗ {market}: all URLs failed")

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
