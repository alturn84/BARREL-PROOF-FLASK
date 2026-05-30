# =============================================
# SIMPLE MLB VALUE BET SCANNER (Copy-Paste Version)
# Pitcher + Park Adjusted
# =============================================

import time
from datetime import datetime

# ================== SETTINGS ==================
CHECK_INTERVAL = 180  # seconds (3 minutes)

# Park Factors (higher = more runs)
PARK_FACTORS = {
    "Coors Field": 1.25,
    "Yankee Stadium": 1.10,
    "Great American Ball Park": 1.15,
    "Chase Field": 1.08,
    "Fenway Park": 1.05,
    "Oracle Park": 0.88,
    "Dodger Stadium": 0.92,
    "Default": 1.00
}

# Example Pitcher Ratings (lower = better)
PITCHER_RATINGS = {
    "Yamamoto": 3.10, "Webb": 3.40, "Burnes": 3.00,
    "Skenes": 2.80, "Ohtani": 2.90, "Default": 4.20
}

# Example Team Offense (1.0 = average)
TEAM_OFFENSE = {
    "Dodgers": 1.12, "Yankees": 1.10, "Braves": 1.08,
    "Giants": 0.95, "Default": 1.00
}

# ================== SAMPLE GAMES ==================
# Replace these with real upcoming games + probable pitchers
games = [
    {
        "away": "Dodgers", "home": "Giants",
        "away_pitcher": "Yamamoto", "home_pitcher": "Webb",
        "park": "Oracle Park",
        "ml_home": 120, "total": 7.0
    },
    {
        "away": "Yankees", "home": "Red Sox",
        "away_pitcher": "Burnes", "home_pitcher": "Default",
        "park": "Fenway Park",
        "ml_home": -110, "total": 8.5
    },
    # Add more games here...
]

def get_pitcher_rating(name):
    return PITCHER_RATINGS.get(name, PITCHER_RATINGS["Default"])

def get_team_offense(team):
    return TEAM_OFFENSE.get(team, TEAM_OFFENSE["Default"])

def get_park_factor(park):
    return PARK_FACTORS.get(park, PARK_FACTORS["Default"])

print("🚀 Simple MLB Bet Scanner Started (Pitcher + Park Adjusted)")
print("Update the 'games' list with real matchups.\n")

while True:
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scanning MLB...")
    
    for game in games:
        # Calculate expected runs
        away_l = (get_pitcher_rating(game["home_pitcher"]) * get_team_offense(game["away"])) * get_park_factor(game["park"]) * 0.98
        home_l = (get_pitcher_rating(game["away_pitcher"]) * get_team_offense(game["home"])) * get_park_factor(game["park"]) * 1.02
        total_expected = away_l + home_l
        
        # Simple Over value check
        if total_expected > game["total"] + 0.8:   # Clear edge on Over
            edge = (total_expected - game["total"]) / game["total"] * 100
            print(f"✅ VALUE: Over {game['total']} in {game['away']} @ {game['home']}")
            print(f"   Expected Runs: {total_expected:.1f} | Edge: +{edge:.1f}% | Park: {game['park']}")
    
    print("No more value bets right now." if all((away_l + home_l) <= g["total"] + 0.8 for g in games) else "")
    time.sleep(CHECK_INTERVAL)