"""
Shared helpers for the DFS board and player props generators
(scripts/update_dfs_board.py, scripts/update_player_props.py).

Reuses existing Barrel Proof conventions rather than inventing new ones:
  - Firecrawl client pattern: same as scripts/update_news_intake.py
    (plain requests.post to the /v1/scrape endpoint — no new dependency).
  - Team abbreviation normalization: built from Site Data/teams.json plus
    Site Data/players/player_manual_overrides.json's "team_abbr" map
    (the same override file scripts/update_player_index.py already uses
    for the OAK -> ATH fix). No second, conflicting team map is created.
  - Player name resolution: Site Data/players/player_aliases.json
    (built by scripts/update_player_index.py's initial_alias()/
    build_aliases(), which already produces "F. Lastname" -> slug style
    keys — the exact shape BettingPros uses) plus a same-team last-name
    fallback against Site Data/players/player_index.json.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Site Data"
PLAYER_DIR = DATA_DIR / "players"

SCHEDULE_PATH = DATA_DIR / "schedule.json"
TEAMS_PATH = DATA_DIR / "teams.json"
PLAYER_ALIASES_PATH = PLAYER_DIR / "player_aliases.json"
PLAYER_INDEX_PATH = PLAYER_DIR / "player_index.json"
MANUAL_OVERRIDES_PATH = PLAYER_DIR / "player_manual_overrides.json"
AUDIT_PATH = DATA_DIR / "dfs_props_audit.json"

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
REQUEST_TIMEOUT = 25

# Extra raw-name team variants seen on DFS/odds sites that aren't covered
# by teams.json's own name/nickname fields or the manual-overrides abbr map.
EXTRA_TEAM_ALIASES = {
    "OAKLAND ATHLETICS": "ATH",
    "OAKLAND": "ATH",
    "ATHLETICS": "ATH",
    "A'S": "ATH",
    "AS": "ATH",
    "OAK": "ATH",
    # DailyFantasyFuel uses WAS for Washington; Barrel Proof's canonical
    # abbreviation (teams.json) is WSH. Confirmed via Hermes/VPS live test.
    "WAS": "WSH",
}


# ---------------------------------------------------------------------------
# Generic JSON helpers
# ---------------------------------------------------------------------------

def load_json(path, fallback=None):
    if fallback is None:
        fallback = {}
    p = Path(path)
    if not p.exists():
        return fallback
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Firecrawl client — same pattern as scripts/update_news_intake.py
# ---------------------------------------------------------------------------

def load_firecrawl_api_key():
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not key:
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("FIRECRAWL_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    return key or None


def firecrawl_scrape(api_key, url):
    """Call Firecrawl /v1/scrape. Returns (markdown_str, error_msg)."""
    try:
        resp = requests.post(
            FIRECRAWL_SCRAPE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return None, f"Firecrawl success=false for {url}: {data.get('error', 'unknown')}"
        content = (data.get("data") or {}).get("markdown") or ""
        if not content:
            return None, f"Firecrawl returned empty markdown for {url}"
        return content, None
    except Exception as e:
        return None, str(e)[:200]


# ---------------------------------------------------------------------------
# Team normalization — built from teams.json + existing manual overrides,
# not a new conflicting map.
# ---------------------------------------------------------------------------

def build_team_alias_map():
    """Map every known raw team string (abbr, full name, nickname, plus the
    extra OAK/Oakland/A's variants DFS/odds sites use) to the canonical
    Barrel Proof abbreviation. ATH is canonical for the Athletics — never
    OAK."""
    teams_data = load_json(TEAMS_PATH, fallback={})
    overrides = load_json(MANUAL_OVERRIDES_PATH, fallback={})
    override_abbr = overrides.get("team_abbr", {}) if isinstance(overrides, dict) else {}

    alias_map = {}

    def add(raw, abbr):
        if raw:
            alias_map[raw.strip().upper()] = abbr

    for team in teams_data.get("teams", []) if isinstance(teams_data, dict) else []:
        abbr = team.get("abbr")
        if not abbr:
            continue
        abbr = override_abbr.get(abbr, abbr)
        add(team.get("abbr"), abbr)
        add(team.get("name"), abbr)
        add(team.get("nickname"), abbr)
        add(team.get("city"), abbr)

    for raw_abbr, canonical in override_abbr.items():
        add(raw_abbr, canonical)

    for raw, canonical in EXTRA_TEAM_ALIASES.items():
        alias_map[raw] = canonical

    return alias_map


def normalize_team_abbr(raw, alias_map):
    """Normalize any raw team string to the canonical Barrel Proof
    abbreviation. Returns None if unrecognized (caller should treat that as
    a team_issue, never invent one)."""
    if not raw:
        return None
    key = str(raw).strip().upper()
    return alias_map.get(key)


# ---------------------------------------------------------------------------
# game_id lookup — built from Site Data/schedule.json's today.games, which
# uses game_pk (e.g. 823531) as the canonical Barrel Proof game identifier,
# stored elsewhere (dope_player_matchups.json etc.) as str(game_pk).
# ---------------------------------------------------------------------------

def build_game_id_lookup():
    """Returns dict keyed by (away_abbr, home_abbr) -> str(game_pk)."""
    schedule = load_json(SCHEDULE_PATH, fallback={})
    games = (schedule.get("today") or {}).get("games") or []
    lookup = {}
    for g in games:
        pk = g.get("game_pk")
        away = g.get("away_abbr")
        home = g.get("home_abbr")
        if pk is not None and away and home:
            lookup[(away, home)] = str(pk)
    return lookup


def find_game_id(team_abbr, opponent_abbr, game_id_lookup):
    """team_abbr may be either the home or away side; try both orderings."""
    if not team_abbr or not opponent_abbr:
        return None
    return (
        game_id_lookup.get((team_abbr, opponent_abbr))
        or game_id_lookup.get((opponent_abbr, team_abbr))
    )


# ---------------------------------------------------------------------------
# Player name resolution
# ---------------------------------------------------------------------------

def load_player_resolution_data():
    aliases = load_json(PLAYER_ALIASES_PATH, fallback={})
    index_list = load_json(PLAYER_INDEX_PATH, fallback=[])
    if not isinstance(index_list, list):
        index_list = []
    by_slug = {p.get("slug"): p for p in index_list if isinstance(p, dict) and p.get("slug")}
    teams_data = load_json(TEAMS_PATH, fallback={})
    team_by_abbr = {t.get("abbr"): t for t in teams_data.get("teams", []) if isinstance(t, dict)}
    return aliases, by_slug, index_list, team_by_abbr


def _team_qualifiers(team_abbr, team_by_abbr):
    """Mirror scripts/update_player_index.py's team_alias_parts() —
    qualifies an ambiguous short alias with team abbr/name/nickname."""
    parts = {team_abbr}
    team = team_by_abbr.get(team_abbr) or {}
    if team.get("name"):
        parts.add(team["name"])
        bits = team["name"].split()
        if bits:
            parts.add(bits[-1])
    if team.get("nickname"):
        parts.add(team["nickname"])
    if team_abbr == "ATH":
        parts.update({"Athletics", "Oakland Athletics"})
    return {p for p in parts if p}


def resolve_abbreviated_name(raw_name, team_abbr, aliases, by_slug, index_list):
    """
    Resolve a BettingPros-style abbreviated name ("B. Woodruff") to a full
    public player name, using (in order):
      1. Direct player_aliases.json lookup.
      2. Team-qualified player_aliases.json lookup (handles names that were
         ambiguous at alias-build time and got team-qualified).
      3. Same-team last-name fallback against player_index.json.

    Returns (full_name, match_status, method, issue) where issue is None or
    a short string describing an ambiguity/no-match condition for
    player_name_issues.
    """
    raw_name = (raw_name or "").strip()
    if not raw_name:
        return raw_name, "unmatched", None, "empty raw name"

    slug = aliases.get(raw_name)
    if slug:
        rec = by_slug.get(slug)
        if rec:
            if team_abbr and rec.get("team_abbr") and rec.get("team_abbr") != team_abbr:
                issue = (
                    f"{raw_name}: alias resolved to {rec.get('full_name')} "
                    f"({rec.get('team_abbr')}) but prop team was {team_abbr}"
                )
                return raw_name, "unmatched", None, issue
            return rec.get("full_name") or raw_name, "matched", "alias_direct", None

    if team_abbr:
        teams_data = load_json(TEAMS_PATH, fallback={})
        team_by_abbr = {t.get("abbr"): t for t in teams_data.get("teams", []) if isinstance(t, dict)}
        for qualifier in _team_qualifiers(team_abbr, team_by_abbr):
            qualified_key = f"{raw_name} {qualifier}"
            slug = aliases.get(qualified_key)
            if slug:
                rec = by_slug.get(slug)
                if rec:
                    return rec.get("full_name") or raw_name, "matched", "alias_team_qualified", None

    # Fallback: same-team last-name match against player_index.
    parts = raw_name.split(".", 1)
    last_name = (parts[1] if len(parts) > 1 else raw_name).strip().lower()
    if not last_name:
        return raw_name, "unmatched", None, f"{raw_name}: could not parse last name"

    if not team_abbr:
        return raw_name, "unmatched", None, f"{raw_name}: no team to disambiguate against"

    candidates = [
        p for p in index_list
        if isinstance(p, dict)
        and p.get("team_abbr") == team_abbr
        and last_name in (p.get("full_name") or "").lower()
    ]
    if len(candidates) == 1:
        return candidates[0].get("full_name") or raw_name, "matched", "team_last_name", None
    if len(candidates) > 1:
        names = ", ".join(c.get("full_name", "?") for c in candidates)
        issue = f"{raw_name} ({team_abbr}): ambiguous last-name match — candidates: {names}"
        return raw_name, "unmatched", None, issue

    return raw_name, "unmatched", None, f"{raw_name} ({team_abbr}): no roster match found"


# ---------------------------------------------------------------------------
# Generic markdown-table parsing — shared by both scrapers. Not site-
# specific, so it tolerates header re-ordering/renaming across DFF and
# BettingPros pages.
# ---------------------------------------------------------------------------

MONEY_RE = re.compile(r"[^0-9.\-]")


def clean_cell(cell):
    cell = re.sub(r"[*_`]", "", cell or "")
    return cell.strip()


def to_number(raw):
    if raw is None:
        return None
    cleaned = MONEY_RE.sub("", str(raw))
    if not cleaned or cleaned in ("-", "."):
        return None
    try:
        return int(cleaned)
    except ValueError:
        try:
            return float(cleaned)
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# DFF player name and salary cleaners
# ---------------------------------------------------------------------------

_DFF_IMAGE_RE = re.compile(r'!\[.*?\]\(.*?\)', re.DOTALL)
_DFF_HAND_RE = re.compile(r'\s*[•·]\s*\([LRS]\)\s*$')


def clean_dff_player_name(raw):
    """Strip DFF markdown image prefix and hand-indicator suffix from a raw
    player cell value.

    Input:  "![](https://dff-images.s3.amazonaws.com/logos/mlb/DET.svg)Tarik Skubal  • (L)"
    Output: "Tarik Skubal"

    Preserves Jr., II, III, IV, hyphens, and accented characters.
    Never mutates projection/value cells — only call this on the player-name
    column."""
    s = _DFF_IMAGE_RE.sub('', raw or '')
    s = _DFF_HAND_RE.sub('', s)
    return ' '.join(s.split()).strip()


def parse_salary(raw):
    """Parse a DFF salary string into an integer dollar amount.

    "$10.0k" → 10000   "$9.7k" → 9700   "$4,200" → 4200   "4200" → 4200

    Returns None if unparseable. Never returns a float — the old bug where
    to_number("$10.0k") produced 10.0 (stripping 'k' but not multiplying)
    is avoided by handling the 'k' suffix explicitly here.
    Only use this for the salary column; to_number() remains correct for
    projection and value_score columns."""
    if raw is None:
        return None
    s = str(raw).strip().replace(',', '').replace('$', '').lower()
    if s.endswith('k'):
        try:
            return int(round(float(s[:-1]) * 1000))
        except (ValueError, TypeError):
            return None
    try:
        val = float(s)
        if val < 500:  # no valid DFS salary is below $500
            return None
        return int(val)
    except (ValueError, TypeError):
        return None


def parse_markdown_tables(markdown):
    """Parse every markdown pipe-table found in a page into a list of dict
    rows keyed by lower-cased header text."""
    lines = markdown.splitlines()
    rows = []
    i = 0
    while i < len(lines) - 1:
        line = lines[i].strip()
        next_line = lines[i + 1].strip()
        if line.startswith("|") and re.match(r"^\|?[\s:|\-]+\|?$", next_line):
            header = [clean_cell(c).lower() for c in line.strip("|").split("|")]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [clean_cell(c) for c in lines[i].strip("|").split("|")]
                if len(cells) == len(header):
                    rows.append(dict(zip(header, cells)))
                i += 1
            continue
        i += 1
    return rows


def parse_markdown_table_rows(markdown):
    """Parse every markdown pipe-table row in a page into raw cell-list
    rows, by position rather than by header-name matching.

    Unlike parse_markdown_tables(), this does not require a row's column
    count to match a preceding header row — needed because DailyFantasyFuel
    mixes in narrower group-header rows (e.g. a 5-column section divider)
    among the wider per-player rows. Callers that know a fixed column
    layout (like DFF's column-indexed player rows) should filter/validate
    rows themselves rather than relying on a single shared header."""
    lines = markdown.splitlines()
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|?[\s:|\-]+\|?$", stripped):
            continue  # separator row
        cells = [clean_cell(c) for c in stripped.strip("|").split("|")]
        rows.append(cells)
    return rows


# ---------------------------------------------------------------------------
# Market name normalization (player props)
# ---------------------------------------------------------------------------

MARKET_NORMALIZE = {
    "HITS": "hits",
    "TOTAL BASES": "total_bases",
    "HOME RUNS": "home_runs",
    "HOME RUN": "home_runs",
    "RBIS": "rbis",
    "RBI": "rbis",
    "RUNS": "runs",
    "HITS + RUNS + RBIS": "hits_runs_rbis",
    "HITS+RUNS+RBIS": "hits_runs_rbis",
    "H+R+RBI": "hits_runs_rbis",
    "STOLEN BASES": "stolen_bases",
    "PITCHER STRIKEOUTS": "pitcher_strikeouts",
    "STRIKEOUTS": "pitcher_strikeouts",
    "OUTS RECORDED": "outs_recorded",
    "EARNED RUNS": "earned_runs",
    "WALKS": "walks",
}


def normalize_market(raw_market):
    """Normalize a raw BettingPros market label to snake_case. Returns None
    (caller should skip/flag, never invent) if unrecognized."""
    if not raw_market:
        return None
    key = str(raw_market).strip().upper()
    if key in MARKET_NORMALIZE:
        return MARKET_NORMALIZE[key]
    # Already-normalized snake_case input (idempotent).
    snake = str(raw_market).strip().lower().replace(" ", "_").replace("+", "_")
    snake = "_".join(part for part in snake.split("_") if part)
    if snake in MARKET_NORMALIZE.values():
        return snake
    return None


# ---------------------------------------------------------------------------
# Audit file — read-modify-write, shared between both generator scripts.
# update_dfs_board.py owns dfs_* fields; update_player_props.py owns
# prop_* fields. Neither script overwrites the other's fields.
# team_issues / player_name_issues / errors are cumulative lists.
# ---------------------------------------------------------------------------

def _empty_audit(edition_date):
    return {
        "date": edition_date,
        "last_updated": None,
        "dfs_records": 0,
        "dfs_matched": 0,
        "dfs_unmatched": 0,
        "prop_records": 0,
        "prop_matched": 0,
        "prop_unmatched": 0,
        "team_issues": [],
        "player_name_issues": [],
        "errors": [],
    }


def load_audit(edition_date):
    """Load the audit file, resetting it if it's missing or stamped for a
    different edition date (a new day starts a fresh audit)."""
    existing = load_json(AUDIT_PATH, fallback=None)
    if not isinstance(existing, dict) or existing.get("date") != edition_date:
        return _empty_audit(edition_date)
    # Backfill any fields missing from an older-shaped audit file.
    fresh = _empty_audit(edition_date)
    fresh.update({k: v for k, v in existing.items() if k in fresh})
    return fresh


def save_audit(audit):
    audit["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_json(AUDIT_PATH, audit)


def start_run(edition_date, tag):
    """Load the audit for this edition date, then drop this script's own
    previously-logged entries (identified by their "[tag]" prefix) from
    team_issues/player_name_issues/errors before the new run repopulates
    them.

    This keeps each script's section reflecting only its current run —
    a fixed parser bug's old error doesn't linger forever after a later
    clean run — while never touching the other script's "[other_tag]"
    entries (per-edition-date cumulative behavior across scripts is
    preserved; only same-script re-runs are deduplicated)."""
    audit = load_audit(edition_date)
    prefix = f"[{tag}]"
    for field in ("team_issues", "player_name_issues", "errors"):
        audit[field] = [item for item in audit.get(field, []) if not str(item).startswith(prefix)]
    return audit
