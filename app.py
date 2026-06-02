#!/usr/bin/env python3
"""
Barrel Proof Baseball — Flask Web Server
"""

import json
import os
from pathlib import Path
from flask import Flask, render_template, abort, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "Site Data")))
VALID_SOURCE_TYPES = {"ap", "getty", "mlb", "team", "manual", "illustrated"}
MEDIA_DIR = BASE_DIR / "media" / "lead-images"

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))


def load_json(filename, fallback=None):
    path = DATA_DIR / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ Could not load {filename}: {e}")
        return fallback if fallback is not None else {}


def get_standings():
    data = load_json("standings.json")
    return data.get("leagues", []), data.get("updated", "")


def get_schedule():
    data = load_json("schedule.json")
    return (
        data.get("today", {}),
        data.get("rail_date", "Today"),
        data.get("games_date_full", ""),
        data.get("updated", ""),
    )


def get_game_cards():
    data = load_json("game_cards.json")
    return data.get("games", []), data.get("display_date", ""), data.get("game_count", 0)


def get_odds():
    data = load_json("odds.json", fallback={})
    return data.get("games", []), data.get("updated", "")

def get_game_of_day():
    data = load_json("game_of_day.json", fallback={})
    return data if data else None

def get_around_the_league():
    data = load_json("around_the_league.json", fallback={})
    return data if data else None

def get_game_to_watch():
    data = load_json("game_to_watch.json", fallback={})
    return data if data else None

def get_press_box():
    data = load_json("press_box.json", fallback={})
    if not data or not data.get("passed_validation"):
        return None
    # Date guard: compare ISO date in press_box.json against
    # ISO date in game_cards.json — both are YYYY-MM-DD format
    gc = load_json("game_cards.json", fallback={})
    gc_date = gc.get("date", "")
    pb_date = data.get("date", "")
    if gc_date and pb_date and pb_date != gc_date:
        print(f"  press_box date {pb_date} != game_cards date {gc_date} — suppressing")
        return None
    return data

def get_lead_image(edition_date: str):
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
        "url":         f"/media/lead-images/{filename}",
        "caption":     caption,
        "credit":      credit,
        "source_type": source_type,
    }

# ── ADD THIS ROUTE TO app.py ──────────────────────────────────────────────
# Place after the get_odds() function and before the @app.route("/") block

def get_dope_sheet_data():
    data = load_json("dope-sheet-data.json", fallback={})
    return (
        data.get("games", []),
        data.get("date_display", ""),
        data.get("date_banner", ""),
        data.get("updated", ""),
    )

@app.route("/dope-sheet")
@app.route("/dope-sheet.html")
def dope_sheet():
    ds_games, date_display, date_banner, ds_updated = get_dope_sheet_data()
    odds_games, odds_updated = get_odds()

    # ── Merge odds into dope sheet games by team name ─────────────────────
    # Build a lookup from odds: (away_team, home_team) → markets
    TEAM_ALIASES = {
        "Athletics":               "Oakland Athletics",
        "D-backs":                 "Arizona Diamondbacks",
        "Diamondbacks":            "Arizona Diamondbacks",
        "White Sox":               "Chicago White Sox",
        "Cubs":                    "Chicago Cubs",
        "Reds":                    "Cincinnati Reds",
        "Guardians":               "Cleveland Guardians",
        "Rockies":                 "Colorado Rockies",
        "Tigers":                  "Detroit Tigers",
        "Astros":                  "Houston Astros",
        "Royals":                  "Kansas City Royals",
        "Angels":                  "Los Angeles Angels",
        "Dodgers":                 "Los Angeles Dodgers",
        "Marlins":                 "Miami Marlins",
        "Brewers":                 "Milwaukee Brewers",
        "Twins":                   "Minnesota Twins",
        "Mets":                    "New York Mets",
        "Yankees":                 "New York Yankees",
        "Phillies":                "Philadelphia Phillies",
        "Pirates":                 "Pittsburgh Pirates",
        "Padres":                  "San Diego Padres",
        "Giants":                  "San Francisco Giants",
        "Mariners":                "Seattle Mariners",
        "Cardinals":               "St. Louis Cardinals",
        "Rays":                    "Tampa Bay Rays",
        "Rangers":                 "Texas Rangers",
        "Blue Jays":               "Toronto Blue Jays",
        "Nationals":               "Washington Nationals",
        "Braves":                  "Atlanta Braves",
        "Orioles":                 "Baltimore Orioles",
        "Red Sox":                 "Boston Red Sox",
    }

    def normalize(name):
        return TEAM_ALIASES.get(name, name)

    odds_lookup = {}
    for og in odds_games:
        key = (normalize(og["away_team"]), normalize(og["home_team"]))
        odds_lookup[key] = og["markets"]

    def fmt_odds(n):
        if n is None:
            return "N/A"
        return f"+{n}" if n > 0 else str(n)

    def implied_pct(american):
        if american is None:
            return "—"
        if american < 0:
            pct = (-american) / (-american + 100) * 100
        else:
            pct = 100 / (american + 100) * 100
        return f"{pct:.0f}%"

    for g in ds_games:
        away_full = g.get("awayFull", "")
        home_full = g.get("homeFull", "")
        key = (away_full, home_full)
        markets = odds_lookup.get(key, {})

        # Moneyline
        ml = markets.get("moneyline", [])
        away_ml = next((m["odds_american"] for m in ml if m["team_side"] == "away"), None)
        home_ml = next((m["odds_american"] for m in ml if m["team_side"] == "home"), None)
        g["awayML"]      = fmt_odds(away_ml)
        g["homeML"]      = fmt_odds(home_ml)
        g["awayImplied"] = implied_pct(away_ml)
        g["homeImplied"] = implied_pct(home_ml)
        g["oddsLive"]    = any(m.get("is_live") for m in ml)

        # Run line / spread
        rl = markets.get("run_line", [])
        away_rl = next((m for m in rl if m["team_side"] == "away"), {})
        home_rl = next((m for m in rl if m["team_side"] == "home"), {})
        away_line = away_rl.get("line")
        home_line = home_rl.get("line")
        away_rl_odds = away_rl.get("odds_american")
        home_rl_odds = home_rl.get("odds_american")
        g["awaySpread"]     = fmt_odds(int(away_line)) if away_line is not None else "—"
        g["homeSpread"]     = fmt_odds(int(home_line)) if home_line is not None else "—"
        g["awaySpreadOdds"] = fmt_odds(away_rl_odds) if away_rl_odds is not None else "—"
        g["homeSpreadOdds"] = fmt_odds(home_rl_odds) if home_rl_odds is not None else "—"

        # Total / O/U
        tot = markets.get("total_runs", [])
        over_tot  = next((m for m in tot if m.get("selection_type") == "over"), {})
        under_tot = next((m for m in tot if m.get("selection_type") == "under"), {})
        g["ou"]        = over_tot.get("line", "—")
        g["overOdds"]  = fmt_odds(over_tot.get("odds_american"))  if over_tot.get("odds_american")  is not None else "—"
        g["underOdds"] = fmt_odds(under_tot.get("odds_american")) if under_tot.get("odds_american") is not None else "—"

        # No odds found flag
        g["oddsAvailable"] = bool(markets)

    return render_template(
        "dope-sheet.html",
        games=ds_games,
        date_display=date_display,
        date_banner=date_banner,
        ds_updated=ds_updated,
        odds_updated=odds_updated,
    )


@app.route("/")
@app.route("/index.html")
@app.route("/barrel-proof-home.html")
def homepage():
    standings, standings_updated = get_standings()
    today_slate, rail_date, games_date, schedule_updated = get_schedule()
    games, display_date, game_count = get_game_cards()
    odds_games, odds_updated = get_odds()
    gotd = get_game_of_day()
    atl = get_around_the_league()
    gtw = get_game_to_watch()
    pb = get_press_box()

    banner_date = display_date or games_date

    lead_image = None
    if gotd:
        gotd_date = gotd.get("date", "")
        gc_data   = load_json("game_cards.json", fallback={})
        gc_date   = gc_data.get("date", "")
        if gotd_date and gc_date and gotd_date == gc_date:
            lead_image = get_lead_image(gotd_date)
        elif gotd_date and gc_date and gotd_date != gc_date:
            print(f"  ⚠ MEDIA-001: lead image suppressed — gotd.date ({gotd_date}) != game_cards.date ({gc_date})")

    return render_template(
        "home.html",
        standings=standings,
        standings_updated=standings_updated,
        today_slate=today_slate,
        rail_date=rail_date,
        games_date=banner_date,
        game_count=game_count,
        games=games,
        odds_games=odds_games,
        odds_updated=odds_updated,
        schedule_updated=schedule_updated,
        gotd=gotd,
        atl=atl,
        gtw=gtw,
        pb=pb,
        lead_image=lead_image,
    )


@app.route("/archive/<year>/<month>/<day>")
def archive_edition(year, month, day):
    snap_path = BASE_DIR / "Site Data" / "archive" / year / "snapshots" / f"{year}-{month}-{day}.json"
    if not snap_path.exists():
        abort(404)
    try:
        snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    except Exception as e:
        app.logger.error(f"archive snapshot malformed: {snap_path}: {e}")
        abort(500)

    edition      = snapshot.get("edition") or {}
    completeness = snapshot.get("completeness", "historical")
    facts        = snapshot.get("facts") or {}
    facts_games  = facts.get("games") or []

    # Edition sections — null if not captured for this date
    gotd = edition.get("game_of_day")
    gtw  = edition.get("game_to_watch")
    atl  = edition.get("around_the_league")
    pb   = edition.get("press_box")

    # Press box: only show if it passed validation
    if pb and not pb.get("passed_validation"):
        pb = None

    # Game Summaries: prefer game_cards edition (has summary/headline),
    # fall back to facts.games (has linescore + batting/pitching, no prose)
    gc_edition = edition.get("game_cards")
    if gc_edition and gc_edition.get("games"):
        games = gc_edition["games"]
    else:
        games = facts_games

    return render_template(
        "archive-edition.html",
        snapshot=snapshot,
        display_date=snapshot.get("display_date", ""),
        day_of_week=snapshot.get("day_of_week", ""),
        completeness=completeness,
        facts_games=facts_games,
        games=games,
        gotd=gotd,
        gtw=gtw,
        atl=atl,
        pb=pb,
    )


@app.route("/media/lead-images/<path:filename>")
def serve_lead_image(filename):
    return send_from_directory(str(MEDIA_DIR), filename)


@app.route("/barrel-proof-american-league.html")
def american_league():
    return render_template("american-league.html")


@app.route("/barrel-proof-national-league.html")
def national_league():
    return render_template("national-league.html")


if __name__ == "__main__":
    print(f"BASE_DIR : {BASE_DIR}")
    print(f"DATA_DIR : {DATA_DIR}")
    print(f"standings  : {(DATA_DIR / 'standings.json').exists()}")
    print(f"schedule   : {(DATA_DIR / 'schedule.json').exists()}")
    print(f"game_cards : {(DATA_DIR / 'game_cards.json').exists()}")
    print(f"odds       : {(DATA_DIR / 'odds.json').exists()}")
    print(f"template   : {(BASE_DIR / 'templates' / 'home.html').exists()}")
    app.run(debug=True, port=5000)
