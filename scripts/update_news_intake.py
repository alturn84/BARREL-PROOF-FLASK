"""
Build Site Data/news_intake.json — Firecrawl-powered fact-gathering layer.

Gathers source-backed facts from official MLB sources before editorial
generation runs. This is NOT a writing replacement — it provides factual
context that Press Box / Around The League can optionally use.

Sources attempted:
  1. MLB Stats API transactions  — direct REST, no Firecrawl needed
  2. MLB.com probable pitchers   — Firecrawl
  3. MLB.com injuries            — Firecrawl

Copyright / editorial rules:
  - Fact intake only. No article rewriting.
  - No long excerpts. Max 25 words per factual summary item.
  - Every item retains source_name + source_url.
  - Paraphrased factual summaries preferred over verbatim text.

Failure behavior:
  - Missing FIRECRAWL_API_KEY → writes valid limited fallback, exits 0.
  - Any source failure → logs it, continues other sources, exits 0.
  - Total failure → writes valid limited fallback, exits 0.
  - Never fatal to the morning update.

Usage:
    python3 scripts/update_news_intake.py
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Site Data"
OUTPUT_PATH = DATA_DIR / "news_intake.json"
SCHEDULE_PATH = DATA_DIR / "schedule.json"

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
REQUEST_TIMEOUT = 25
MAX_SUMMARY_WORDS = 25
MAX_ITEMS_PER_SOURCE = 20

MLB_STATS_API_URL = "https://statsapi.mlb.com/api/v1/transactions"
MLB_STATS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.mlb.com",
    "Referer": "https://www.mlb.com/",
}

# Firecrawl-backed sources (requires FIRECRAWL_API_KEY)
FIRECRAWL_SOURCES = [
    {
        "source_name": "MLB.com Probable Pitchers",
        "source_url": "https://www.mlb.com/probable-pitchers",
        "source_type": "pitchers",
    },
    {
        "source_name": "MLB.com Injuries",
        "source_url": "https://www.mlb.com/injuries",
        "source_type": "injuries",
    },
]

# Transaction type codes considered significant
SIGNIFICANT_TYPE_CODES = {"DFA", "RL", "SC", "TR", "SG", "RLC", "ASG", "CLW", "DES", "A", "DA"}
SIGNIFICANT_KEYWORDS = [
    "injured list", "designated for assignment", "called up", "traded",
    "signed", "released", "optioned", "recalled", "rehab", "placed on",
    "activated from", "reinstated",
]

# MLB team names for Firecrawl content parsing
MLB_TEAMS = [
    "Yankees", "Red Sox", "Blue Jays", "Rays", "Orioles",
    "White Sox", "Guardians", "Tigers", "Royals", "Twins",
    "Astros", "Angels", "Athletics", "Mariners", "Rangers",
    "Braves", "Marlins", "Mets", "Phillies", "Nationals",
    "Cubs", "Reds", "Brewers", "Pirates", "Cardinals",
    "Diamondbacks", "Rockies", "Dodgers", "Giants", "Padres",
]

INJURY_KEYWORDS = [
    "injured list", " il ", "out ", "surgery", "placed on", "day il",
    "day disabled", "activated", "returned", "strained", "torn",
    "fractured", "sprain", "concussion",
]

PITCHER_KEYWORDS = [
    "probable", "tbd", "to be determined", "start", "pitcher",
    "starter", "rotation",
]


# ---------------------------------------------------------------------------
# Helpers
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


def get_slate_date():
    sched = load_json(SCHEDULE_PATH)
    return (sched.get("today") or {}).get("date") or datetime.now().strftime("%Y-%m-%d")


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


def truncate_to_words(text, max_words=MAX_SUMMARY_WORDS):
    """Truncate text to at most max_words words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def write_output(date_str, sources, transactions, injuries, pitcher_notes,
                 lineup_notes, team_notes, failure_notes, failure_count):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_items = (len(transactions) + len(injuries) + len(pitcher_notes)
                   + len(lineup_notes) + len(team_notes))

    if failure_count == 0 and total_items > 0:
        data_quality = "available"
    elif total_items > 0:
        data_quality = "partial"
    else:
        data_quality = "limited"

    output = {
        "meta": {
            "date": date_str,
            "generated_at": now_str,
            "source": "firecrawl",
            "data_quality": data_quality,
            "item_count": total_items,
            "source_count": len(sources),
            "failure_count": failure_count,
            "failure_notes": failure_notes,
        },
        "sources": sources,
        "transactions": transactions,
        "injuries": injuries,
        "pitcher_notes": pitcher_notes,
        "lineup_notes": lineup_notes,
        "team_notes": team_notes,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({total_items} items, quality={data_quality})")


def write_limited_fallback(date_str, failure_notes):
    write_output(date_str, [], [], [], [], [], [], failure_notes, len(failure_notes))


# ---------------------------------------------------------------------------
# Source 1: MLB Stats API transactions (direct REST, no Firecrawl)
# ---------------------------------------------------------------------------

def fetch_mlb_transactions(date_str):
    source = {
        "source_name": "MLB Stats API Transactions",
        "source_url": f"https://statsapi.mlb.com/api/v1/transactions?startDate={date_str}&endDate={date_str}",
        "source_type": "transactions",
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
    }
    items = []
    try:
        resp = requests.get(
            MLB_STATS_API_URL,
            params={"startDate": date_str, "endDate": date_str, "sportId": 1},
            headers=MLB_STATS_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        raw_txns = resp.json().get("transactions", [])

        seen = set()
        for t in raw_txns:
            type_code = t.get("typeCode", "")
            desc = (t.get("description") or "").strip()
            if not desc:
                continue
            lower_desc = desc.lower()
            is_significant = type_code in SIGNIFICANT_TYPE_CODES or any(
                kw in lower_desc for kw in SIGNIFICANT_KEYWORDS
            )
            if not is_significant:
                continue
            # Deduplicate by description
            key = desc[:60].lower()
            if key in seen:
                continue
            seen.add(key)

            player = (t.get("person") or {}).get("fullName") or ""
            team = (t.get("toTeam") or t.get("fromTeam") or {}).get("name") or ""
            t_type = (t.get("typeDesc") or t.get("typeCode") or "").strip()
            summary = truncate_to_words(desc)

            items.append({
                "team": team,
                "player": player,
                "transaction_type": t_type,
                "summary": summary,
                "source_name": "MLB Stats API",
                "source_url": "https://statsapi.mlb.com/api/v1/transactions",
                "published_at": date_str,
                "confidence": "high",
            })
            if len(items) >= MAX_ITEMS_PER_SOURCE:
                break

        print(f"  MLB transactions: {len(items)} significant items")
    except Exception as e:
        source["status"] = "failed"
        source["failure_note"] = str(e)[:120]
        print(f"  WARN: MLB transactions fetch failed: {e}")

    return source, items


# ---------------------------------------------------------------------------
# Firecrawl scraper
# ---------------------------------------------------------------------------

def firecrawl_scrape(api_key, url):
    """
    Call Firecrawl /v1/scrape. Returns (markdown_str, error_msg).
    On success: (content, None). On failure: (None, error).
    """
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
            return None, f"Firecrawl success=false for {url}: {data.get('error','unknown')}"
        content = (data.get("data") or {}).get("markdown") or ""
        if not content:
            return None, f"Firecrawl returned empty markdown for {url}"
        return content, None
    except Exception as e:
        return None, str(e)[:120]


# ---------------------------------------------------------------------------
# Firecrawl content parsers
# ---------------------------------------------------------------------------

def _clean_line(line):
    """Strip markdown formatting and whitespace."""
    line = re.sub(r"[#*_\[\]`>|]", " ", line)
    return re.sub(r"\s+", " ", line).strip()


def parse_pitcher_notes(markdown, source_url):
    """
    Extract brief pitcher probable notes from Firecrawl markdown.
    Looks for lines mentioning team names near pitcher/probable keywords.
    Returns list of pitcher_note dicts.
    """
    items = []
    seen = set()
    lines = markdown.splitlines()

    current_team = ""
    for line in lines[:300]:
        clean = _clean_line(line)
        if not clean or len(clean) < 5:
            continue

        # Detect team header
        for team in MLB_TEAMS:
            if team in clean and len(clean) < 80:
                current_team = team
                break

        lower = clean.lower()
        has_pitcher_kw = any(kw in lower for kw in PITCHER_KEYWORDS)
        if not has_pitcher_kw:
            continue

        summary = truncate_to_words(clean)
        dedup_key = summary[:40].lower()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        items.append({
            "team": current_team,
            "player": "",
            "note_type": "probable",
            "summary": summary,
            "source_name": "MLB.com Probable Pitchers",
            "source_url": source_url,
            "published_at": "",
            "confidence": "medium",
        })
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break

    return items


def parse_injury_notes(markdown, source_url):
    """
    Extract brief injury notes from Firecrawl markdown.
    Looks for lines containing injury-related keywords.
    Returns list of injury dicts.
    """
    items = []
    seen = set()
    lines = markdown.splitlines()

    current_team = ""
    for line in lines[:400]:
        clean = _clean_line(line)
        if not clean or len(clean) < 10:
            continue

        # Detect team header
        for team in MLB_TEAMS:
            if team in clean and len(clean) < 80:
                current_team = team
                break

        lower = clean.lower()
        has_injury_kw = any(kw in lower for kw in INJURY_KEYWORDS)
        if not has_injury_kw:
            continue

        summary = truncate_to_words(clean)
        dedup_key = summary[:40].lower()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        items.append({
            "team": current_team,
            "player": "",
            "status": "",
            "summary": summary,
            "source_name": "MLB.com Injuries",
            "source_url": source_url,
            "published_at": "",
            "confidence": "medium",
        })
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break

    return items


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    date_str = get_slate_date()
    print(f"update_news_intake: date={date_str}")

    api_key = load_firecrawl_api_key()
    if not api_key:
        print("  WARN: FIRECRAWL_API_KEY not set — writing limited fallback")
        write_limited_fallback(date_str, ["FIRECRAWL_API_KEY not set in environment or .env"])
        return

    all_sources = []
    all_transactions = []
    all_injuries = []
    all_pitcher_notes = []
    all_lineup_notes = []
    all_team_notes = []
    failure_notes = []
    failure_count = 0

    # --- Source 1: MLB Stats API transactions (no Firecrawl needed) ---
    print("  Fetching MLB transactions (Stats API)...")
    txn_source, txn_items = fetch_mlb_transactions(date_str)
    all_sources.append(txn_source)
    all_transactions.extend(txn_items)
    if txn_source["status"] == "failed":
        failure_count += 1
        failure_notes.append(
            f"MLB Stats API transactions: {txn_source.get('failure_note', 'fetch failed')}"
        )

    # --- Sources 2+: Firecrawl-backed pages ---
    for src_def in FIRECRAWL_SOURCES:
        src_name = src_def["source_name"]
        src_url = src_def["source_url"]
        src_type = src_def["source_type"]
        print(f"  Fetching {src_name} via Firecrawl...")

        source_record = {
            "source_name": src_name,
            "source_url": src_url,
            "source_type": src_type,
            "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "ok",
        }

        content, error = firecrawl_scrape(api_key, src_url)
        if error or not content:
            source_record["status"] = "failed"
            failure_count += 1
            msg = error or "empty response"
            failure_notes.append(f"{src_name}: {msg}")
            all_sources.append(source_record)
            print(f"    WARN: {src_name} failed: {msg}")
            continue

        print(f"    OK: {len(content)} chars extracted")
        all_sources.append(source_record)

        if src_type == "pitchers":
            notes = parse_pitcher_notes(content, src_url)
            all_pitcher_notes.extend(notes)
            print(f"    {len(notes)} pitcher notes extracted")
        elif src_type == "injuries":
            notes = parse_injury_notes(content, src_url)
            all_injuries.extend(notes)
            print(f"    {len(notes)} injury notes extracted")

    write_output(
        date_str,
        all_sources,
        all_transactions,
        all_injuries,
        all_pitcher_notes,
        all_lineup_notes,
        all_team_notes,
        failure_notes,
        failure_count,
    )


if __name__ == "__main__":
    main()
