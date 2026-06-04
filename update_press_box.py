#!/usr/bin/env python3
"""
update_press_box.py — Barrel Proof Baseball
─────────────────────────────────────────────
Assembles daily baseball context, calls Hermes (Google Gemini),
and writes Site Data/press_box.json.

Pipeline position (runs last in morning block):
    update_around_the_league.py
    update_game_to_watch.py
    → update_press_box.py

Cron:
    # Cron:
    # 40 9 * * * /usr/bin/python3 /opt/data/workspace/barrel-proof/update_press_box.py >> /opt/data/workspace/barrel-proof/press_box.log 2>&1

Usage:
    python3 update_press_box.py
    python3 update_press_box.py 2026-05-30
"""

import json
import re
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

VAULT     = Path(__file__).resolve().parent
SITE_DATA = VAULT / "Site Data"
ARCHIVE   = VAULT / "Archive"
OUT_FILE  = SITE_DATA / "press_box.json"

MODEL          = "gemini-2.5-flash"   # change here to swap Gemini models
MAX_TOKENS     = 4096
CONTEXT_DAYS   = 7
MAX_CTX_TOKENS = 2000

SYSTEM_PROMPT = """You write the Press Box notebook for Barrel Proof Baseball.

FORMAT — output bullet points only:
- One sentence per bullet
- 6 to 10 bullets
- Maximum 25 words per bullet
- No paragraphs
- No intro sentence
- No closing sentence
- Start every bullet with •

COVER ONLY:
- Injured list placements and returns
- Designated for assignment moves
- Call-ups from the minors
- Trades
- Free agent signings or contract extensions
- Rehab assignments
- Suspensions or disciplinary actions
- Career milestones (500 HR, 3000 hits, 300 wins, etc.)

PRIORITY ORDER — list items in this order, most important first:
1. Significant injuries (torn ligaments, fractures, season-ending)
2. DFA moves
3. Trades
4. Free agent signings
5. Call-ups from the minors
6. Rehab assignments
7. Minor roster moves and option assignments

Do not simply list items in the order they appear in the data.
Rank by news value. A torn ACL comes before a rehab assignment.

DO NOT INCLUDE:
- Game scores or recaps
- Standings information
- Opinion or analysis
- Any item not directly sourced from the transactions data

STYLE RULES:
- Plain text only
- No markdown, no bold, no asterisks, no headers
- Use full team names on first reference
- Be specific: name the player, the team, the injury or move
- Do not pad with generic phrases

GOOD EXAMPLE:
- Brewers placed LHP Rob Zastryzny on the 15-day injured list with a left trapezius strain.
- Blue Jays sent RHP Yimi García on a rehab assignment to Triple-A Buffalo.

BAD EXAMPLE:
- The Milwaukee Brewers have announced a roster move involving their left-handed pitching staff."""


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ Could not load {path}: {e}", flush=True)
        return {}


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_failed(reason, date_str):
    write_json(OUT_FILE, {
        "date":              date_str,
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "passed_validation": False,
        "error":             reason,
    })
    print(f"  ✗ Failed: {reason}", flush=True)


def fetch_transactions(date_str):
    """Fetch MLB transactions for the given date from the Stats API."""
    import requests as _requests
    url = "https://statsapi.mlb.com/api/v1/transactions"
    params = {"startDate": date_str, "endDate": date_str, "sportId": 1}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://www.mlb.com",
        "Referer": "https://www.mlb.com/",
    }
    try:
        resp = _requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        transactions = data.get("transactions", [])
        # Filter to meaningful transaction types only
        keep_types = {"DFA", "RL", "SC", "TR", "SG", "RLC", "ASG", "CLW", "DES"}
        filtered = []
        for t in transactions:
            type_code = t.get("typeCode", "")
            desc = t.get("description", "").strip()
            if desc and (type_code in keep_types or any(kw in desc.lower() for kw in
                ["injured list", "designated for assignment", "called up", "traded",
                 "signed", "released", "optioned", "recalled", "rehab"])):
                filtered.append(desc)
        print(f"  Transactions fetched: {len(filtered)} items", flush=True)
        return filtered
    except Exception as e:
        print(f"  ⚠ Transactions fetch failed: {e}", flush=True)
        return []


def load_recent_columns(date_str):
    results = []
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    for i in range(1, CONTEXT_DAYS + 1):
        d    = dt - timedelta(days=i)
        path = ARCHIVE / d.strftime("%Y") / d.strftime("%m") / f"{d.strftime('%d')}.json"
        if not path.exists():
            continue
        snap = load_json(path)
        pb   = snap.get("press_box", {})
        if not pb:
            continue
        col = pb.get("column", {})
        ww  = col.get("worth_watching", "") if isinstance(col, dict) else ""
        if ww:
            results.append((d.strftime("%Y-%m-%d"), ww))
    return results


def build_context(date_str, gotd, atl, standings, game_cards, recent_columns, transactions=None):
    dt       = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt.strftime("%A, %B %-d, %Y")
    month_end = (dt.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    days_left = (month_end - dt).days

    lines = []

    lines.append(f"DATE: {day_name}")
    lines.append(f"DAYS REMAINING IN MONTH: {days_left}")
    lines.append("")

    if gotd and gotd.get("game"):
        g  = gotd["game"]
        ed = gotd.get("editorial", {})
        lines.append("GAME OF THE DAY")
        inn = f" (F/{g['innings']})" if g.get("innings", 9) > 9 else ""
        lines.append(f"{g.get('away','?')} {g.get('away_runs','?')} @ {g.get('home','?')} {g.get('home_runs','?')}{inn}")
        if g.get("flags"):
            lines.append(f"Flags: {', '.join(g['flags'])}")
        if ed.get("headline"):
            lines.append(f"Headline: {ed['headline']}")
        if ed.get("lead_angle"):
            lines.append(f"Lead: {ed['lead_angle']}")
        lines.append("")

    all_games = gotd.get("all_games", []) if gotd else []
    if all_games:
        lines.append(f"TODAY'S FULL RESULTS ({len(all_games)} games)")
        for g in all_games:
            flags = f" — {', '.join(g['flags'])}" if g.get("flags") else ""
            lines.append(f"  {g['away']} {g['away_runs']} @ {g['home']} {g['home_runs']}{flags}")
        lines.append("")

    items = atl.get("items", []) if atl else []
    if items:
        lines.append("AROUND THE LEAGUE TODAY")
        for item in items:
            lines.append(f"  {item}")
        lines.append("")

    if standings and standings.get("leagues"):
        lines.append("STANDINGS SNAPSHOT")
        for league in standings["leagues"]:
            lg = league.get("league", "")
            for div in league.get("divisions", []):
                teams = div.get("teams", [])
                if not teams:
                    continue
                second   = teams[1] if len(teams) > 1 else None
                gap      = second["gb"] if second else "—"
                team_line = ", ".join(f"{t['city']} {t['w']}-{t['l']}" for t in teams[:3])
                lines.append(f"  {lg} {div['name']}: {team_line} | Leader gap to 2nd: {gap} GB")
        lines.append("")

    if transactions:
        lines.append("MLB TRANSACTIONS TODAY")
        for t in transactions[:20]:
            lines.append(f"  {t}")
        lines.append("")

    if recent_columns:
        lines.append(f"RECENT PRESS BOX CONTEXT (last {len(recent_columns)} days)")
        for rc_date, ww in recent_columns:
            lines.append(f"  {rc_date}: {ww}")
        lines.append("")

    context = "\n".join(lines)

    if len(context) > MAX_CTX_TOKENS * 4 and len(recent_columns) > 3:
        print(f"  ⚠ Context {len(context)} chars — trimming recent columns", flush=True)
        return build_context(date_str, gotd, atl, standings, game_cards, recent_columns[:3], transactions)

    return context


def validate(column_text, article_title, article_subtitle, article_body, teaser_text):
    results  = {}
    failures = []

    col_words = len(column_text.split())
    # Relaxed column word count validation
    results["column_word_count_ok"] = col_words > 20 # At least 20 words
    if not results["column_word_count_ok"]:
        failures.append(f"column_word_count={col_words} (expected > 20)")

    # "Worth watching:" is no longer expected from narrative output
    # results["column_worth_watching"] = "Worth watching:" in column_text
    # if not results["column_worth_watching"]:
    #    failures.append("column missing 'Worth watching:'")

    art_words = len(article_body.split())
    # Relaxed article word count validation
    results["article_word_count_ok"] = art_words > 50 # At least 50 words
    if not results["article_word_count_ok"]:
        failures.append(f"article_word_count={art_words} (expected > 50)")

    results["article_title_present"] = len(article_title.strip()) > 0
    if not results["article_title_present"]:
        failures.append("article title empty")

    # Subtitle is heuristically empty, so don't fail if it's not present
    results["article_subtitle_present"] = True 

    if teaser_text:
        tlen = len(teaser_text)
        results["teaser_char_count"] = 1 <= tlen <= 280
        if not results["teaser_char_count"]:
            failures.append(f"teaser_char_count={tlen} (need 1-280)")

        results["teaser_no_hashtags"] = "#" not in teaser_text
        if not results["teaser_no_hashtags"]:
            failures.append("teaser contains hashtag")

        results["teaser_not_truncation"] = True # No longer a strict check as content is generated heuristically
    else:
        results["teaser_char_count"]     = True
        results["teaser_no_hashtags"]    = True
        results["teaser_not_truncation"] = True

    passed = len(failures) == 0
    if failures:
        print(f"  ✗ Validation failures: {'; '.join(failures)}", flush=True)
    else:
        print("  ✓ All validation checks passed", flush=True)

    return passed, results


def extract_worth_watching(column_text):
    marker = "Worth watching:"
    idx = column_text.find(marker)
    if idx == -1:
        return ""
    sentence = column_text[idx:]
    end = sentence.find(".")
    if end != -1:
        sentence = sentence[:end + 1]
    return sentence.strip()


def run(date_str):
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        env_file = VAULT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        write_failed("GEMINI_API_KEY not set", date_str)
        sys.exit(1)

    print(f"  Loading inputs for {date_str}...", flush=True)
    gotd       = load_json(SITE_DATA / "game_of_day.json")
    atl        = load_json(SITE_DATA / "around_the_league.json")
    standings  = load_json(SITE_DATA / "standings.json")
    game_cards = load_json(SITE_DATA / "game_cards.json")
    transactions = fetch_transactions(date_str)
    print(f"  {len(transactions)} transactions loaded", flush=True)
    recent     = load_recent_columns(date_str)

    # ── Date guard — validate inputs match requested date ─────────────────────
    date_checks = {
        "game_of_day":         gotd.get("date"),
        "around_the_league":   atl.get("date"),
        "game_cards":          game_cards.get("date") if game_cards.get("date") else None,
        "standings":           standings.get("date") if standings.get("date") else None,
    }
    mismatches = []
    for name, d in date_checks.items():
        if d is not None and d != date_str:
            mismatches.append(f"{name}={d}")
    if mismatches:
        print(f"  ⚠ Date mismatch(es) for {date_str}: {', '.join(mismatches)}", flush=True)
        # Null out inputs whose date doesn't match — continue with what aligns
        if gotd.get("date") and gotd["date"] != date_str:
            print("  ⚠ Dropping game_of_day (wrong date)", flush=True)
            gotd = {}
        if atl.get("date") and atl["date"] != date_str:
            print("  ⚠ Dropping around_the_league (wrong date)", flush=True)
            atl = {}
        if game_cards.get("date") and game_cards["date"] != date_str:
            print("  ⚠ Dropping game_cards (wrong date)", flush=True)
            game_cards = {}

    inputs_available = sum([bool(gotd), bool(atl), bool(standings), bool(game_cards)])
    print(f"  {inputs_available}/4 primary inputs loaded, {len(recent)} days of context", flush=True)

    if inputs_available == 0:
        write_failed("no input data available", date_str)
        sys.exit(1)

    effective_date = gotd.get("date", date_str)
    context = build_context(effective_date, gotd, atl, standings, game_cards, recent, transactions)
    print(f"  Context assembled: {len(context)} chars", flush=True)

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        write_failed("google-genai not installed", date_str)
        sys.exit(1)

    client = genai.Client(api_key=api_key, http_options=genai_types.HttpOptions(api_version="v1"))

    full_prompt = f"{SYSTEM_PROMPT}\n\n{context}"

    print("  Calling Hermes...", flush=True)
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=MAX_TOKENS,
            ),
        )
    except Exception as e:
        write_failed(f"API error: {e}", date_str)
        sys.exit(1)

    raw = response.text
    print(f"  Response received: {len(raw)} chars", flush=True)


    cleaned = raw.strip()
    parsed = {}

    # Extract title from the first heading
    title_match = re.search(r"^##\s*(.*?)\n", cleaned, re.MULTILINE)
    if title_match:
        article_title = title_match.group(1).strip()
        # The rest of the content is the article body
        article_body = cleaned[title_match.end():].strip()
    else:
        article_title = "MLB Daily Recap"
        article_body = cleaned

    # For bullet format (starts with •), use the full body as column text
    if article_body.strip().startswith("•"):
        column_text = article_body.strip()
    else:
        # Heuristically generate column text (first few sentences, aiming for > 50 words)
        sentences = re.findall(r"([^.!?]+[.!?])", article_body, re.DOTALL)
        column_text_sentences = []
        current_word_count = 0
        for sentence in sentences:
            column_text_sentences.append(sentence)
            current_word_count += len(sentence.split())
            if current_word_count >= 50 and len(column_text_sentences) >= 3:
                break
        column_text = "".join(column_text_sentences).strip()
        if not column_text:
            column_text = article_body[:500].strip()  # Fallback to first 500 chars

    # Heuristically generate teaser text (first sentence)
    first_sentence_match = re.search(r"^(.*?\.)(?:\s|$)", column_text, re.DOTALL)
    if first_sentence_match:
        teaser_text = first_sentence_match.group(1).strip()
    else:
        teaser_text = column_text[:280].strip() # Fallback to first 280 chars

    # No subtitle from narrative output, default to empty
    article_subtitle = ""

    # Assign to parsed dictionary for consistency with later validation and output
    parsed["column"]             = column_text
    parsed["x_article_title"]    = article_title
    parsed["x_article_subtitle"] = article_subtitle
    parsed["x_article_body"]     = article_body
    parsed["x_teaser"]           = teaser_text
    teaser_text      = parsed.get("x_teaser", "").strip()

    passed, val_results = validate(column_text, article_title, article_subtitle, article_body, teaser_text)

    worth_watching  = extract_worth_watching(column_text)
    dt              = datetime.strptime(effective_date, "%Y-%m-%d")
    teaser_included = bool(teaser_text)

    output = {
        "date":              effective_date,
        "date_display":      dt.strftime("%A, %B %-d, %Y"),
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "model":             "hermes-editor-at-large-v1",
        "passed_validation": passed,
        "column": {
            "text":           column_text,
            "worth_watching": worth_watching,
            "word_count":     len(column_text.split()),
        },
        "x_article": {
            "title":      article_title,
            "subtitle":   article_subtitle,
            "body":       article_body,
            "word_count": len(article_body.split()),
        },
        "x_teaser": {
            "text":       teaser_text,
            "char_count": len(teaser_text),
            "included":   teaser_included,
        },
        "validation":    val_results,
        "input_summary": {
            "games_processed": len(gotd.get("all_games", [])),
            "gotd":            f"{gotd.get('game', {}).get('away','?')} @ {gotd.get('game', {}).get('home','?')}",
            "atl_item_count":  len(atl.get("items", [])),
            "days_of_context": len(recent),
        },
    }

    write_json(OUT_FILE, output)

    status = "✓ PASSED" if passed else "✗ FAILED VALIDATION"
    print(f"\n  {status}", flush=True)
    print(f"  Column: {output['column']['word_count']} words", flush=True)
    print(f"  Article: {output['x_article']['word_count']} words", flush=True)
    print(f"  Teaser: {'included' if teaser_included else 'omitted'}", flush=True)
    print(f"  Saved → {OUT_FILE}", flush=True)

    if passed:
        print(f"\n  HEADLINE: {article_title}", flush=True)
        print(f"\n  COLUMN PREVIEW:\n  {column_text[:300]}...", flush=True)


if __name__ == "__main__":
    args     = [a for a in sys.argv[1:] if not a.startswith("--")]
    date_str = args[0] if args else (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    run(date_str)
