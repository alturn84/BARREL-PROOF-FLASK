import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time
from scipy.stats import poisson

class AdvancedMLBBetFinder:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        # Park Factors (2025-2026 approximate run multipliers; 1.00 = neutral)
        # Higher = more runs (hitter-friendly). Source: Typical Fangraphs-style values
        self.park_factors = {
            "Dodger Stadium": 0.92,      # Pitcher-friendly
            "Oracle Park": 0.88,         # Very pitcher-friendly (Giants)
            "Yankee Stadium": 1.10,      # Hitter-friendly
            "Coors Field": 1.25,         # Extremely hitter-friendly
            "Great American Ball Park": 1.15,
            "Chase Field": 1.08,
            "Fenway Park": 1.05,
            "Wrigley Field": 1.02,
            # Add more parks as needed
            "Default": 1.00
        }

    def american_to_implied_prob(self, odds):
        if odds > 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)

    def get_mlb_games(self):
        """TODO: Replace with actual Hard Rock Bet scraping/API logic."""
        # Placeholder structure - replace with real data
        sample_games = [
            {
                "game_id": 1,
                "away_team": "Dodgers", "home_team": "Giants",
                "away_pitcher": "Yamamoto", "home_pitcher": "Webb",
                "home_park": "Oracle Park",
                "moneyline_away": -140, "moneyline_home": +120,
                "total_line": 7.0, "total_odds_over": -110
            },
            # Add more...
        ]
        return pd.DataFrame(sample_games)

    def get_pitcher_rating(self, pitcher_name):
        """Lower = better (fewer runs allowed). Replace with live data."""
        ratings = {"Yamamoto": 3.10, "Webb": 3.40, "Burnes": 3.00, "Skenes": 2.80}
        return ratings.get(pitcher_name, 4.20)

    def get_team_offense(self, team):
        """Runs/game multiplier (1.0 = average)."""
        offense = {"Dodgers": 1.12, "Giants": 0.95, "Braves": 1.08, "Yankees": 1.10}
        return offense.get(team, 1.0)

    def pitcher_adjusted_lambdas(self, away_pitcher, home_pitcher, away_team, home_team, home_park):
        """Calculate expected runs with park adjustment."""
        away_pitcher_era = self.get_pitcher_rating(away_pitcher)
        home_pitcher_era = self.get_pitcher_rating(home_pitcher)
        
        away_off = self.get_team_offense(away_team)
        home_off = self.get_team_offense(home_team)
        park_factor = self.park_factors.get(home_park, self.park_factors["Default"])
        
        # Base expected runs, adjusted for pitcher, offense, and park
        away_lambda = (home_pitcher_era * away_off * park_factor) * 0.98   # Slight home/away tweak
        home_lambda = (away_pitcher_era * home_off * park_factor) * 1.02
        
        return away_lambda, home_lambda

    def find_value_bets(self, df, min_edge=0.045):
        value_bets = []
        
        for _, game in df.iterrows():
            away_l, home_l = self.pitcher_adjusted_lambdas(
                game['away_pitcher'], game['home_pitcher'],
                game['away_team'], game['home_team'], game.get('home_park', 'Default')
            )
            total_lambda = away_l + home_l
            
            # Moneyline (home win probability rough estimate)
            if 'moneyline_home' in game and pd.notna(game['moneyline_home']):
                implied_home = self.american_to_implied_prob(game['moneyline_home'])
                model_home_prob = home_l / (home_l + away_l + 0.1)  # Simple ratio + home advantage
                edge_ml = model_home_prob - implied_home
                if edge_ml > min_edge:
                    value_bets.append({
                        "Game": f"{game['away_team']} @ {game['home_team']}",
                        "Market": "ML Home",
                        "Odds": game['moneyline_home'],
                        "Model Prob": round(model_home_prob, 3),
                        "Implied": round(implied_home, 3),
                        "Edge%": round(edge_ml * 100, 2),
                        "Total Lambda": round(total_lambda, 2),
                        "Park": game.get('home_park', 'N/A')
                    })
            
            # Totals (Over)
            if 'total_line' in game and pd.notna(game['total_line']):
                over_prob = 1 - poisson.cdf(game['total_line'], total_lambda)
                implied_over = 0.5  # Adjust for vig in real use
                edge_over = over_prob - implied_over
                if edge_over > min_edge:
                    value_bets.append({
                        "Game": f"{game['away_team']} @ {game['home_team']}",
                        "Market": f"Over {game['total_line']}",
                        "Edge%": round(edge_over * 100, 2),
                        "Expected Runs": round(total_lambda, 2),
                        "Park Factor": round(self.park_factors.get(game.get('home_park'), 1.0), 2),
                        "Park": game.get('home_park', 'N/A')
                    })
        
        return pd.DataFrame(value_bets)

    def run_scanner(self, interval=180):
        print("🚀 Advanced MLB Bet Finder with Pitcher + Park Adjustments Started")
        print("Manual placement on Hard Rock Bet only.\n")
        while True:
            print(f"[{datetime.now()}] Scanning MLB markets...")
            df = self.get_mlb_games()
            if not df.empty:
                value = self.find_value_bets(df)
                if not value.empty:
                    print("\n=== VALUE BETS FOUND ===\n")
                    print(value.to_string(index=False))
                else:
                    print("No strong value bets detected at this time.")
            else:
                print("No game data available.")
            time.sleep(interval)

if __name__ == "__main__":
    bot = AdvancedMLBBetFinder()
    bot.run_scanner()
