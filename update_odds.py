#!/usr/bin/env python3

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Site Data"
OUTPUT_FILE = DATA_DIR / "odds.json"

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("SHARP_API_KEY")
BASE_URL = "https://api.sharpapi.io/api/v1/odds"

SPORTSBOOK = "fanduel"
LEAGUE = "MLB"

MARKETS_TO_KEEP = {
    "moneyline",
    "run_line",
    "total_runs",
}


def fetch_odds():
    if not API_KEY:
        raise RuntimeError("Missing SHARP_API_KEY")

    headers = {"X-API-Key": API_KEY}
    params = {"league": "mlb",
              "sportsbook": "draftkings, fanduel",
              "market": "moneyline, run_line, total_runs",
              "limit": 200,
}

    response = requests.get(BASE_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()

    return response.json().get("data", [])


def normalize_market_name(market_type):
    market_type = (market_type or "").lower()

    if market_type == "moneyline":
        return "moneyline"

    if market_type in {"spread", "run_line", "runline"}:
        return "run_line"

    if market_type in {"total", "totals"}:
        return "total"

    return market_type


def main():
    raw_odds = fetch_odds()

    games = {}

    for item in raw_odds:
        sportsbook = (item.get("sportsbook") or "").lower()
        league = (item.get("league") or "").lower()
        market_type = normalize_market_name(item.get("market_type"))

        if sportsbook != SPORTSBOOK:
            continue

        if league != "mlb":
            continue

        if market_type not in {"moneyline", "run_line", "total"}:
            continue

        if item.get("is_alternate_line"):
            continue

        if not item.get("is_main_line", True):
            continue

        event_id = item.get("event_id")
        if not event_id:
            continue

        if event_id not in games:
            games[event_id] = {
                "event_id": event_id,
                "event_uuid": item.get("event_uuid"),
                "home_team": item.get("home_team"),
                "away_team": item.get("away_team"),
                "event_start_time": item.get("event_start_time"),
                "is_live": item.get("is_live"),
                "sportsbook": SPORTSBOOK,
                "markets": {
                    "moneyline": [],
                    "run_line": [],
                    "total": [],
                },
            }

        games[event_id]["markets"][market_type].append({
            "selection": item.get("selection"),
            "selection_type": item.get("selection_type"),
            "team_side": item.get("team_side"),
            "odds_american": item.get("odds_american"),
            "line": item.get("line"),
            "last_seen_at": item.get("last_seen_at"),
            "odds_changed_at": item.get("odds_changed_at"),
            "is_live": item.get("is_live"),
        })

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "SharpAPI",
        "sportsbook": SPORTSBOOK,
        "league": "MLB",
        "game_count": len(games),
        "games": list(games.values()),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_FILE}")
    print(f"Games with odds: {len(games)}")


if __name__ == "__main__":
    main()
