#!/usr/bin/env python3
"""
Barrel Proof Baseball — Flask Web Server
"""

import json
import os
from pathlib import Path
from flask import Flask, render_template

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "Site Data")))

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

    banner_date = display_date or games_date

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
    )


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
