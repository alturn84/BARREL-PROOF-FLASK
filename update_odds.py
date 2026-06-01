import json
import os
from datetime import datetime, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Site Data"
OUTPUT_FILE = DATA_DIR / "odds.json"

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"

SPORTSBOOKS = ["fanduel", "draftkings"]

MARKETS = ["h2h", "spreads", "totals"]

MARKET_NAME_MAP = {
    "h2h": "moneyline",
    "spreads": "run_line",
    "totals": "total",
}


def fetch_odds():
    if not API_KEY:
        raise RuntimeError("Missing ODDS_API_KEY in .env")

    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": ",".join(MARKETS),
        "bookmakers": ",".join(SPORTSBOOKS),
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    # Log remaining requests for monitoring
    remaining = response.headers.get("x-requests-remaining", "unknown")
    used = response.headers.get("x-requests-used", "unknown")
    print(f"Odds API: {used} requests used, {remaining} remaining")

    return response.json()


def normalize(raw_games):
    games = []

    for game in raw_games:
        game_id = game.get("id")
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        commence_time = game.get("commence_time")

        structured_game = {
            "event_id": game_id,
            "home_team": home_team,
            "away_team": away_team,
            "event_start_time": commence_time,
            "sportsbooks": {},
        }

        for bookmaker in game.get("bookmakers", []):
            book_key = bookmaker.get("key")
            if book_key not in SPORTSBOOKS:
                continue

            markets = {}

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")
                market_name = MARKET_NAME_MAP.get(market_key, market_key)

                outcomes = []
                for outcome in market.get("outcomes", []):
                    outcomes.append({
                        "name": outcome.get("name"),
                        "price": outcome.get("price"),
                        "point": outcome.get("point"),
                    })

                markets[market_name] = outcomes

            structured_game["sportsbooks"][book_key] = markets

        games.append(structured_game)

    return games


def main():
    print(f"SCRIPT STARTED: {datetime.now()}")

    raw_games = fetch_odds()

    if not raw_games:
        print("No games returned from The Odds API")
        return

    games = normalize(raw_games)

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "TheOddsAPI",
        "sportsbooks": SPORTSBOOKS,
        "league": "MLB",
        "game_count": len(games),
        "games": games,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_FILE}")
    print(f"Games with odds: {len(games)}")
    print(f"SCRIPT COMPLETED: {datetime.now()}")


if __name__ == "__main__":
    main()
