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
    40 9 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
        "/Users/allanturner/BARREL PROOF/update_press_box.py" >> \
        "/Users/allanturner/BARREL PROOF/press_box.log" 2>&1

Usage:
    python3 update_press_box.py
    python3 update_press_box.py 2026-05-30
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

VAULT     = Path("/Users/allanturner/BARREL PROOF")
SITE_DATA = VAULT / "Site Data"
ARCHIVE   = VAULT / "Archive"
OUT_FILE  = SITE_DATA / "press_box.json"

MODEL          = "gemini-2.5-flash"   # change here to swap Gemini models
MAX_TOKENS     = 8192
CONTEXT_DAYS   = 7
MAX_CTX_TOKENS = 2000

SYSTEM_PROMPT = """You are the Editor-at-Large for Barrel Proof Baseball, a vintage newspaper-style baseball publication. Your column is called "From the Press Box."

Today you will produce three things from a single editorial observation — something meaningful in today's baseball results that a casual fan might have overlooked.

You are looking for one of the following:
- A trend becoming visible across multiple days
- A team quietly doing something the standings don't yet reflect
- A pitcher or hitter whose recent results suggest a turn
- A division race developing in an unexpected direction
- A result today that connects to something from earlier this week

Do not summarize the day's results. The reader already has the box scores. Give them the thing worth noticing underneath.

Voice: thoughtful, observant, restrained. Veteran baseball columnist. No hyperbole. No hot takes. No gambling references. No fantasy baseball. No fan bias. No predictions framed as facts.

────────────────────────────────────────────
ITEM 1: HOMEPAGE COLUMN
────────────────────────────────────────────
100 to 175 words. This is the thesis — tight and complete on its own. A reader who only reads this should finish thinking: "I hadn't noticed that, but that's interesting."

End with exactly one sentence that begins: "Worth watching:"
That sentence tells the reader what to look for in the next few days.

────────────────────────────────────────────
ITEM 2: X ARTICLE
────────────────────────────────────────────
400 to 800 words. This expands the same observation from the homepage column. Do not introduce a different take. Add:
- historical context if relevant
- specific game moments from today's data that support the thesis
- what the numbers say about where this trend goes
- one counterargument, briefly acknowledged and addressed

Write in the same newspaper column voice. Sections are allowed but not required. No subheadings needed.

Also produce:
- A title: direct, specific, not a question, not clickbait
- A subtitle: one sentence that adds context to the title

────────────────────────────────────────────
ITEM 3: SOCIAL TEASER (optional)
────────────────────────────────────────────
280 characters or less. This promotes the X Article — it is not a summary of the column. It is the hook that earns the click. Write it as something a baseball writer would post, not a promotional announcement. No hashtags. No emojis.

If you cannot produce a teaser that meets these standards, omit it entirely rather than produce a weak one.

────────────────────────────────────────────
RETURN FORMAT
────────────────────────────────────────────
Return only valid JSON with exactly these keys:
{
  "column": "...",
  "x_article_title": "...",
  "x_article_subtitle": "...",
  "x_article_body": "...",
  "x_teaser": "..."
}

x_teaser may be an empty string if omitted.
No markdown. No preamble. No explanation. Raw JSON only."""


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


def build_context(date_str, gotd, atl, standings, game_cards, recent_columns):
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

    if recent_columns:
        lines.append(f"RECENT PRESS BOX CONTEXT (last {len(recent_columns)} days)")
        for rc_date, ww in recent_columns:
            lines.append(f"  {rc_date}: {ww}")
        lines.append("")

    context = "\n".join(lines)

    if len(context) > MAX_CTX_TOKENS * 4 and len(recent_columns) > 3:
        print(f"  ⚠ Context {len(context)} chars — trimming recent columns", flush=True)
        return build_context(date_str, gotd, atl, standings, game_cards, recent_columns[:3])

    return context


def validate(column_text, article_title, article_subtitle, article_body, teaser_text):
    results  = {}
    failures = []

    col_words = len(column_text.split())
    results["column_word_count"] = 100 <= col_words <= 175
    if not results["column_word_count"]:
        failures.append(f"column_word_count={col_words} (need 100-175)")

    results["column_worth_watching"] = "Worth watching:" in column_text
    if not results["column_worth_watching"]:
        failures.append("column missing 'Worth watching:'")

    art_words = len(article_body.split())
    results["article_word_count"] = 400 <= art_words <= 800
    if not results["article_word_count"]:
        failures.append(f"article_word_count={art_words} (need 400-800)")

    results["article_title_present"] = len(article_title.strip()) > 0
    if not results["article_title_present"]:
        failures.append("article title empty")

    results["article_subtitle_present"] = len(article_subtitle.strip()) > 0
    if not results["article_subtitle_present"]:
        failures.append("article subtitle empty")

    if teaser_text:
        tlen = len(teaser_text)
        results["teaser_char_count"] = 1 <= tlen <= 280
        if not results["teaser_char_count"]:
            failures.append(f"teaser_char_count={tlen} (need 1-280)")

        results["teaser_no_hashtags"] = "#" not in teaser_text
        if not results["teaser_no_hashtags"]:
            failures.append("teaser contains hashtag")

        results["teaser_not_truncation"] = teaser_text != column_text[:280]
        if not results["teaser_not_truncation"]:
            failures.append("teaser is truncated column")
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
    context = build_context(effective_date, gotd, atl, standings, game_cards, recent)
    print(f"  Context assembled: {len(context)} chars", flush=True)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        write_failed("google-genai not installed — run: pip install google-genai --break-system-packages", date_str)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print("  Calling Hermes...", flush=True)
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=context,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=MAX_TOKENS,
            ),
        )
    except Exception as e:
        write_failed(f"API error: {e}", date_str)
        sys.exit(1)

    raw = response.text
    print(f"  Response received: {len(raw)} chars", flush=True)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines   = cleaned.split("\n")
        cleaned = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        write_failed(f"json_parse_failed — raw: {raw[:500]}", date_str)
        sys.exit(1)

    required_keys = {"column", "x_article_title", "x_article_subtitle", "x_article_body", "x_teaser"}
    missing = required_keys - set(parsed.keys())
    if missing:
        write_failed(f"missing keys: {missing}", date_str)
        sys.exit(1)

    column_text      = parsed["column"].strip()
    article_title    = parsed["x_article_title"].strip()
    article_subtitle = parsed["x_article_subtitle"].strip()
    article_body     = parsed["x_article_body"].strip()
    teaser_text      = parsed["x_teaser"].strip()

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
