#!/usr/bin/env python3
"""
update_game_of_day.py — Barrel Proof Baseball
──────────────────────────────────────────────
Reads the daily MLB box score markdown (written by mlb_fetch.py),
scores every game, selects the Game of the Day, and writes:

    Site Data/game_of_day.json

The homepage template reads that file and renders the lead story block.

Usage:
    python update_game_of_day.py              # yesterday
    python update_game_of_day.py 2026-05-22  # specific date

Pipeline position:
    mlb_fetch.py  →  update_game_of_day.py  →  game_of_day.json  →  home.html

Cron (runs after mlb_fetch.py and update_game_cards.py):
    20 8 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
        "/Users/allanturner/BARREL PROOF/update_game_of_day.py"
"""

import json
import re
import sys
import time
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

VAULT    = Path("/Users/allanturner/BARREL PROOF")
DAILY    = VAULT / "Daily"
OUT_FILE = VAULT / "Site Data" / "game_of_day.json"
BASE_URL = "https://statsapi.mlb.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.mlb.com",
    "Referer": "https://www.mlb.com/",
}

# ── Team display names ────────────────────────────────────────────────────────
TEAM_NAMES = {
    "ARI": "Arizona Diamondbacks", "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",    "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs",         "CWS": "Chicago White Sox",
    "CIN": "Cincinnati Reds",      "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",     "DET": "Detroit Tigers",
    "HOU": "Houston Astros",       "KC":  "Kansas City Royals",
    "LAA": "Los Angeles Angels",   "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",        "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",      "NYM": "New York Mets",
    "NYY": "New York Yankees",     "ATH": "Oakland Athletics",
    "PHI": "Philadelphia Phillies","PIT": "Pittsburgh Pirates",
    "SD":  "San Diego Padres",     "SF":  "San Francisco Giants",
    "SEA": "Seattle Mariners",     "STL": "St. Louis Cardinals",
    "TB":  "Tampa Bay Rays",       "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",    "WSH": "Washington Nationals",
}

# ── Scoring weights ───────────────────────────────────────────────────────────
WEIGHTS = {
    "perfect_game":      130,
    "no_hitter":         100,
    "cycle":              60,
    "milestone":          45,
    "walk_off":           40,
    "comeback_7plus":     35,
    "extra_innings":      30,   # base; scaled by extra innings (capped)
    "comeback_5_6":       22,
    "playoff_spot_game":  22,
    "first_place_clash":  28,
    "one_run_game":       15,
    "comeback_3_4":       12,
    "division_rivalry":   18,
    "pennant_race_sept":  15,
    "rivalry_bonus":      20,
    "pitcher_k_record":   25,
    "multi_hr_game":      20,
    "dominant_start":     18,
    "large_market_home":  12,
    "rbi_explosion":      14,
    "high_run_game":      10,
    "stolen_base_spree":   8,
    "doubleheader_g2":     5,
}

LARGE_MARKET = {"NYY", "LAD", "BOS", "CHC", "ATL", "HOU", "SF", "NYM", "PHI"}

RIVALRIES = {
    frozenset({"NYY", "BOS"}), frozenset({"LAD", "SF"}),
    frozenset({"CHC", "STL"}), frozenset({"NYY", "NYM"}),
    frozenset({"ATL", "NYM"}), frozenset({"LAD", "SD"}),
    frozenset({"TEX", "HOU"}), frozenset({"OAK", "SF"}),
}


# ── Data class ────────────────────────────────────────────────────────────────
@dataclass
class GameScore:
    game_pk:    int
    away:       str
    home:       str
    away_runs:  int
    home_runs:  int
    innings:    int
    raw_score:  float = 0.0
    flags:      list  = field(default_factory=list)
    breakdown:  dict  = field(default_factory=dict)

    @property
    def margin(self):      return abs(self.home_runs - self.away_runs)
    @property
    def total_runs(self):  return self.home_runs + self.away_runs
    @property
    def winner(self):      return self.home if self.home_runs > self.away_runs else self.away
    @property
    def loser(self):       return self.away if self.home_runs > self.away_runs else self.home

    def add(self, key, pts, label=""):
        self.breakdown[key] = pts
        self.raw_score += pts
        if label:
            self.flags.append(label)


# ── API helpers ───────────────────────────────────────────────────────────────
def api_get(endpoint, params=None):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params=params,
                             headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2: raise
            time.sleep(2 ** attempt)


def fetch_standings(date_str):
    data = api_get("/api/v1/standings", params={
        "leagueId": "103,104", "date": date_str,
        "season": date_str[:4], "standingsTypes": "regularSeason",
        "hydrate": "team,division",
    })
    result = {}
    for record in data.get("records", []):
        div_id = record.get("division", {}).get("id")
        for tr in record.get("teamRecords", []):
            abbr = tr["team"].get("abbreviation", "")
            gb_raw = tr.get("gamesBack", "0")
            try:
                gb = 0.0 if gb_raw in ("-", "") else float(gb_raw)
            except ValueError:
                gb = 99.0
            result[abbr] = {
                "div_rank":    tr.get("divisionRank", "99"),
                "gb":          gb,
                "division_id": div_id,
            }
    return result


def fetch_live_feed(game_pk):
    return api_get(f"/api/v1.1/game/{game_pk}/feed/live")


def fetch_schedule(date_str):
    data = api_get("/api/v1/schedule", params={
        "sportId": 1, "date": date_str,
        "gameType": "R,F,D,L,W", "hydrate": "team,linescore,decisions",
    })
    dates = data.get("dates", [])
    if not dates:
        return []
    return [g for g in dates[0]["games"]
            if g["status"]["abstractGameState"] == "Final"]


# ── Markdown parser (mirrors update_game_cards.py pattern) ───────────────────
def parse_md_for_games(date_str):
    """
    Read the vault markdown file and return a lightweight list of game dicts.
    Used as a fast fallback if the live feed call fails for a game.
    Returns: [{away, home, away_runs, home_runs, innings_count, notes}, ...]
    """
    md_file = DAILY / f"{date_str}-mlb-box-scores.md"
    if not md_file.exists():
        return []

    text = md_file.read_text(encoding="utf-8")
    text = re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL)
    result = []
    for block in re.split(r"\n(?=### )", text):
        block = block.strip()
        if not block.startswith("###"):
            continue
        hm = re.match(r"### (\w+) @ (\w+)[^—\-]*[—\-]\s*(.*)", block.split("\n")[0])
        if not hm:
            continue
        away, home = hm.group(1), hm.group(2)
        sm = re.findall(r"\*?(\d+)\*?", hm.group(3))
        try:
            away_r, home_r = int(sm[0]), int(sm[1])
        except (IndexError, ValueError):
            away_r, home_r = 0, 0
        # count innings from linescore table header
        inn_m = re.search(r"\|\s*Team\s*\|(.+?)\|\s*R\s*\|", block)
        innings = 9
        if inn_m:
            inn_cols = [c.strip() for c in inn_m.group(1).split("|")
                        if c.strip().isdigit()]
            innings = max(len(inn_cols), 9)
        # pull flags from notes lines
        raw_notes = [l.strip() for l in block.split("\n")
                     if re.match(r"^\*\*(HR|2B|3B|SB|WP|Balk):", l.strip())]
        result.append({
            "away": away, "home": home,
            "away_runs": away_r, "home_runs": home_r,
            "innings": innings, "raw_notes": raw_notes,
        })
    return result


# ── Scoring helpers ───────────────────────────────────────────────────────────
def _team_stat(bs, side, group, stat):
    try:
        return bs["teams"][side]["teamStats"][group].get(stat, 0) or 0
    except (KeyError, TypeError):
        return 0


def _find_cycles(bs):
    names = []
    for side in ("away", "home"):
        for _, p in bs["teams"][side]["players"].items():
            s = p.get("stats", {}).get("batting", {})
            if not s:
                continue
            h, d, t, hr = s.get("hits",0), s.get("doubles",0), s.get("triples",0), s.get("homeRuns",0)
            if (h - d - t - hr) >= 1 and d >= 1 and t >= 1 and hr >= 1:
                names.append(p["person"]["fullName"])
    return names


def _find_milestones(ld):
    hits = []
    kws = ["500th home run","3,000th hit","300th save","3000 career","500 career","milestone"]
    for play in ld.get("plays", {}).get("allPlays", []):
        desc = play.get("result", {}).get("description", "").lower()
        if any(kw in desc for kw in kws):
            name = play.get("matchup", {}).get("batter", {}).get("fullName", "")
            hits.append(name or desc[:60])
    return hits


def _is_walk_off(ld):
    plays = ld.get("plays", {}).get("allPlays", [])
    return bool(plays) and "walk-off" in plays[-1].get("result", {}).get("description", "").lower()


def _max_deficit(ld, home_wins):
    innings = ld.get("linescore", {}).get("innings", [])
    wk = "home" if home_wins else "away"
    lk = "away" if home_wins else "home"
    ws = ls = max_d = 0
    for inn in innings:
        ws += inn.get(wk, {}).get("runs") or 0
        ls += inn.get(lk, {}).get("runs") or 0
        if ls - ws > max_d:
            max_d = ls - ws
    return max_d


def _find_multi_hr(bs):
    out = []
    for side in ("away", "home"):
        for _, p in bs["teams"][side]["players"].items():
            hr = p.get("stats", {}).get("batting", {}).get("homeRuns", 0)
            if hr >= 2:
                out.append(f"{p['person']['fullName']} ({hr} HR)")
    return out


def _find_dominant_start(bs):
    out = []
    for side in ("away", "home"):
        for _, p in bs["teams"][side]["players"].items():
            s = p.get("stats", {}).get("pitching", {})
            if not s:
                continue
            ip_raw = s.get("inningsPitched", "0")
            try:
                ip = float(ip_raw.replace(".1", ".33").replace(".2", ".67"))
            except ValueError:
                ip = 0.0
            if ip >= 7.0 and s.get("earnedRuns", 0) <= 1 and s.get("strikeOuts", 0) >= 8:
                out.append(f"{p['person']['fullName']} ({ip_raw} IP, {s.get('earnedRuns',0)} ER, {s.get('strikeOuts',0)} K)")
    return out


def _find_k_record(bs, threshold=15):
    out = []
    for side in ("away", "home"):
        for _, p in bs["teams"][side]["players"].items():
            s = p.get("stats", {}).get("pitching", {})
            if not s:
                continue
            ip_raw = s.get("inningsPitched", "0")
            try:
                ip = float(ip_raw.replace(".1", ".33").replace(".2", ".67"))
            except ValueError:
                ip = 0.0
            k = s.get("strikeOuts", 0)
            if k >= threshold and ip >= 6.0:
                out.append(f"{p['person']['fullName']} ({k} K)")
    return out


def _find_rbi_heroes(bs, threshold=5):
    out = []
    for side in ("away", "home"):
        for _, p in bs["teams"][side]["players"].items():
            rbi = p.get("stats", {}).get("batting", {}).get("rbi", 0)
            if rbi >= threshold:
                out.append(f"{p['person']['fullName']} ({rbi} RBI)")
    return out


# ── Score one game ────────────────────────────────────────────────────────────
def score_game(game, feed, standings, date_str):
    gd = feed.get("gameData", {})
    ld = feed.get("liveData", {})
    ls = ld.get("linescore", {})
    bs = ld.get("boxscore", {})

    away = game["teams"]["away"]["team"]["abbreviation"]
    home = game["teams"]["home"]["team"]["abbreviation"]
    game_pk = game["gamePk"]

    at = ls.get("teams", {}).get("away", {})
    ht = ls.get("teams", {}).get("home", {})
    away_r = at.get("runs", 0)
    home_r = ht.get("runs", 0)
    inn = len(ls.get("innings", []))
    game_num = gd.get("game", {}).get("gameNumber", 1)
    month = datetime.strptime(date_str, "%Y-%m-%d").month
    home_wins = home_r > away_r

    gs = GameScore(game_pk=game_pk, away=away, home=home,
                   away_runs=away_r, home_runs=home_r, innings=max(inn, 9))

    # ── Historic events ───────────────────────────────────────────────────────
    away_hits = at.get("hits", 0)
    home_hits = ht.get("hits", 0)

    if home_hits == 0 and inn >= 9:
        bb  = _team_stat(bs, "away", "batting", "baseOnBalls")
        hbp = _team_stat(bs, "away", "batting", "hitByPitch")
        if bb == 0 and hbp == 0:
            gs.add("perfect_game", WEIGHTS["perfect_game"], "PERFECT GAME")
        else:
            gs.add("no_hitter", WEIGHTS["no_hitter"], "NO-HITTER")
    elif away_hits == 0 and inn >= 9:
        bb  = _team_stat(bs, "home", "batting", "baseOnBalls")
        hbp = _team_stat(bs, "home", "batting", "hitByPitch")
        if bb == 0 and hbp == 0:
            gs.add("perfect_game", WEIGHTS["perfect_game"], "PERFECT GAME")
        else:
            gs.add("no_hitter", WEIGHTS["no_hitter"], "NO-HITTER")

    cycles = _find_cycles(bs)
    if cycles:
        gs.add("cycle", WEIGHTS["cycle"], f"CYCLE: {', '.join(cycles)}")

    milestones = _find_milestones(ld)
    if milestones:
        gs.add("milestone", WEIGHTS["milestone"], f"MILESTONE: {milestones[0]}")

    # ── Dramatic finish ───────────────────────────────────────────────────────
    if home_wins:
        last = ls.get("innings", [{}])[-1]
        last_home = last.get("home", {}).get("runs", 0) or 0
        if last_home > 0 and (inn > 9 or _is_walk_off(ld)):
            gs.add("walk_off", WEIGHTS["walk_off"], "WALK-OFF WIN")
        elif inn == 9 and last_home > 0:
            gs.add("walk_off", int(WEIGHTS["walk_off"] * 0.75), "WALK-OFF WIN")

    if inn > 9:
        extra = min(inn - 9, 5)
        gs.add("extra_innings", int(WEIGHTS["extra_innings"] * extra / 5),
               f"EXTRA INNINGS ({inn})")

    deficit = _max_deficit(ld, home_wins)
    if deficit >= 7:
        gs.add("comeback_7plus", WEIGHTS["comeback_7plus"],
               f"COMEBACK (trailed {deficit})")
    elif deficit >= 5:
        gs.add("comeback_5_6", WEIGHTS["comeback_5_6"],
               f"COMEBACK (trailed {deficit})")
    elif deficit >= 3:
        gs.add("comeback_3_4", WEIGHTS["comeback_3_4"],
               f"COMEBACK (trailed {deficit})")

    if gs.margin == 1:
        gs.add("one_run_game", WEIGHTS["one_run_game"], "ONE-RUN GAME")

    # ── Standings context ─────────────────────────────────────────────────────
    as_ = standings.get(away, {})
    hs_ = standings.get(home, {})
    same_div = (as_.get("division_id") == hs_.get("division_id")
                and as_.get("division_id") is not None)

    if as_.get("div_rank") == "1" and hs_.get("div_rank") == "1":
        gs.add("first_place_clash", WEIGHTS["first_place_clash"], "FIRST-PLACE CLASH")

    if as_.get("gb", 99) <= 2.0 or hs_.get("gb", 99) <= 2.0:
        gs.add("playoff_spot_game", WEIGHTS["playoff_spot_game"], "PLAYOFF IMPLICATIONS")

    if same_div:
        gs.add("division_rivalry", WEIGHTS["division_rivalry"], "DIVISION MATCHUP")

    if month == 9 and (as_.get("gb", 99) <= 5.0 or hs_.get("gb", 99) <= 5.0):
        gs.add("pennant_race_sept", WEIGHTS["pennant_race_sept"], "PENNANT RACE")

    # ── Star performances ─────────────────────────────────────────────────────
    multi_hr = _find_multi_hr(bs)
    if multi_hr:
        gs.add("multi_hr_game", WEIGHTS["multi_hr_game"],
               f"MULTI-HR: {multi_hr[0]}")

    dom = _find_dominant_start(bs)
    if dom:
        gs.add("dominant_start", WEIGHTS["dominant_start"],
               f"DOMINANT START: {dom[0]}")

    rbi = _find_rbi_heroes(bs)
    if rbi:
        gs.add("rbi_explosion", WEIGHTS["rbi_explosion"],
               f"BIG RBI GAME: {rbi[0]}")

    sb = _team_stat(bs, "away", "batting", "stolenBases") + \
         _team_stat(bs, "home", "batting", "stolenBases")
    if sb >= 3:
        gs.add("stolen_base_spree", WEIGHTS["stolen_base_spree"],
               f"SB SPREE ({sb})")

    k_stars = _find_k_record(bs)
    if k_stars:
        gs.add("pitcher_k_record", WEIGHTS["pitcher_k_record"],
               f"15+ K: {k_stars[0]}")

    # ── Fan interest ──────────────────────────────────────────────────────────
    if home in LARGE_MARKET:
        gs.add("large_market_home", WEIGHTS["large_market_home"],
               f"{home} HOME GAME")

    if frozenset({away, home}) in RIVALRIES:
        gs.add("rivalry_bonus", WEIGHTS["rivalry_bonus"],
               f"RIVALRY GAME")

    if gs.total_runs >= 16:
        gs.add("high_run_game", WEIGHTS["high_run_game"],
               f"HIGH-SCORING ({gs.total_runs} runs)")

    if game_num == 2:
        gs.add("doubleheader_g2", WEIGHTS["doubleheader_g2"], "DH GAME 2")

    return gs


# ── Tie-breaking ──────────────────────────────────────────────────────────────
TIE_BREAK = [
    lambda gs: gs.breakdown.get("perfect_game", 0) + gs.breakdown.get("no_hitter", 0),
    lambda gs: gs.breakdown.get("walk_off", 0)      + gs.breakdown.get("extra_innings", 0),
    lambda gs: gs.breakdown.get("first_place_clash", 0) + gs.breakdown.get("playoff_spot_game", 0),
    lambda gs: gs.total_runs,
    lambda gs: len(gs.breakdown),
    lambda gs: -gs.game_pk,
]


def pick_winner(scored):
    if len(scored) == 1:
        return scored[0]
    best = max(gs.raw_score for gs in scored)
    candidates = [gs for gs in scored if gs.raw_score == best]
    for fn in TIE_BREAK:
        if len(candidates) == 1:
            break
        top = max(fn(gs) for gs in candidates)
        candidates = [gs for gs in candidates if fn(gs) == top]
    return candidates[0]


# ── Editorial copy generation ─────────────────────────────────────────────────
def editorial(gs, date_str):
    """
    Build plain-English headline, subheadline, lead angle, and reason
    from the game's flags. Ordered by flag priority.
    """
    away_name = TEAM_NAMES.get(gs.away, gs.away)
    home_name = TEAM_NAMES.get(gs.home, gs.home)
    winner_name = TEAM_NAMES.get(gs.winner, gs.winner)
    loser_name  = TEAM_NAMES.get(gs.loser,  gs.loser)
    score_str = f"{gs.away} {gs.away_runs}, {gs.home} {gs.home_runs}"
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    flags = [f.upper() for f in gs.flags]

    # ── Perfect game ──────────────────────────────────────────────────────────
    if any("PERFECT GAME" in f for f in flags):
        return {
            "headline":    f"Perfect.",
            "subheadline": f"{winner_name} throws a perfect game against {loser_name}.",
            "lead_angle":  (
                f"In one of the rarest achievements in baseball, {gs.winner} hurled a perfect game, "
                f"retiring all 27 batters in a {score_str} victory. "
                f"It's the kind of night that makes you stop everything and watch."
            ),
            "reason": "A perfect game is the Mount Everest of pitching. Nothing else comes close.",
        }

    # ── No-hitter ─────────────────────────────────────────────────────────────
    if any("NO-HITTER" in f for f in flags):
        return {
            "headline":    f"History on the mound.",
            "subheadline": f"{winner_name} no-hits {loser_name}, {score_str}.",
            "lead_angle":  (
                f"{gs.winner} pitching combined for a no-hitter in a {score_str} win. "
                f"The no-no is the defining story of the baseball day — everything else is secondary."
            ),
            "reason": "No-hitters are historic. Full stop.",
        }

    # ── Cycle ─────────────────────────────────────────────────────────────────
    cycle_flag = next((f for f in gs.flags if f.upper().startswith("CYCLE:")), None)
    if cycle_flag:
        player = cycle_flag.split(":", 1)[1].strip()
        return {
            "headline":    f"{player} hits for the cycle.",
            "subheadline": f"{winner_name} wins as {player} goes single, double, triple, homer.",
            "lead_angle":  (
                f"You don't see it often. {player} completed the cycle for {gs.winner} "
                f"in a {score_str} victory over {gs.loser}. "
                f"Single, double, triple, home run — the full tour of the bases."
            ),
            "reason": "Hitting for the cycle happens fewer than a dozen times a season league-wide.",
        }

    # ── Walk-off + Extra innings ──────────────────────────────────────────────
    if any("WALK-OFF" in f for f in flags) and any("EXTRA INNINGS" in f for f in flags):
        inn_flag = next((f for f in gs.flags if "EXTRA INNINGS" in f.upper()), "")
        inn_str  = inn_flag.split("(")[-1].rstrip(")") if "(" in inn_flag else str(gs.innings)
        return {
            "headline":    f"Walk-off in extras. {gs.winner} wins it in the {inn_str}th.",
            "subheadline": f"{score_str} — {gs.innings} innings of baseball finally settle it.",
            "lead_angle":  (
                f"They played deep into the night and {winner_name} ended it the right way. "
                f"A walk-off in the {inn_str}th inning gave {gs.winner} a {score_str} victory "
                f"over {gs.loser} in a game that refused to end. The best kind."
            ),
            "reason": f"Extra-inning walk-off — the purest combination of tension and resolution the sport offers.",
        }

    # ── Walk-off ──────────────────────────────────────────────────────────────
    if any("WALK-OFF" in f for f in flags):
        comeback = next((f for f in gs.flags if "COMEBACK" in f.upper()), None)
        if comeback:
            deficit = comeback.split("trailed")[-1].strip().rstrip(")")
            return {
                "headline":    f"Down {deficit}, {gs.winner} walks it off.",
                "subheadline": f"{score_str}. {winner_name} completes the comeback.",
                "lead_angle":  (
                    f"They were staring at a {deficit}-run deficit and they came all the way back. "
                    f"{winner_name} finished it with a walk-off, beating {loser_name} {score_str}. "
                    f"The kind of game you remember."
                ),
                "reason": f"Walk-off comeback from {deficit} runs — drama stacked on drama.",
            }
        return {
            "headline":    f"{gs.winner} walks it off.",
            "subheadline": f"{winner_name} {gs.home_runs if gs.winner == gs.home else gs.away_runs}, "
                           f"{loser_name} {gs.home_runs if gs.loser == gs.home else gs.away_runs}.",
            "lead_angle":  (
                f"{winner_name} didn't need extra time — they needed one last swing. "
                f"A walk-off finish gave them a {score_str} win over {loser_name}."
            ),
            "reason": "Walk-offs are baseball's signature drama. The season's best finish this day.",
        }

    # ── Extra innings (no walk-off) ───────────────────────────────────────────
    if any("EXTRA INNINGS" in f for f in flags):
        inn_flag = next((f for f in gs.flags if "EXTRA INNINGS" in f.upper()), "")
        inn_str  = inn_flag.split("(")[-1].rstrip(")") if "(" in inn_flag else str(gs.innings)
        return {
            "headline":    f"{gs.innings} innings. {gs.winner} finally puts it away.",
            "subheadline": f"{score_str} in a marathon that went to the {inn_str}th.",
            "lead_angle":  (
                f"Neither side would yield. {winner_name} and {loser_name} played through "
                f"{gs.innings} innings before {gs.winner} walked away with a {score_str} win. "
                f"The bullpens are empty; the story is full."
            ),
            "reason": f"Marathon ball. {gs.innings} innings of sustained tension makes this the day's standout.",
        }

    # ── Comeback ──────────────────────────────────────────────────────────────
    comeback = next((f for f in gs.flags if "COMEBACK" in f.upper()), None)
    if comeback:
        deficit = comeback.split("trailed")[-1].strip().rstrip(")")
        return {
            "headline":    f"{gs.winner} erases a {deficit}-run hole.",
            "subheadline": f"{winner_name} rallies past {loser_name}, {score_str}.",
            "lead_angle":  (
                f"Write it off? They never did. {winner_name} trailed by {deficit} runs "
                f"and still found a way, beating {loser_name} {score_str}. "
                f"The biggest comeback of the day."
            ),
            "reason": f"A {deficit}-run comeback is the day's best storyline — resilience over résumé.",
        }

    # ── Milestone ─────────────────────────────────────────────────────────────
    milestone_flag = next((f for f in gs.flags if "MILESTONE" in f.upper()), None)
    if milestone_flag:
        detail = milestone_flag.split(":", 1)[1].strip() if ":" in milestone_flag else "a career milestone"
        return {
            "headline":    f"A milestone night.",
            "subheadline": f"{winner_name} wins as history is made.",
            "lead_angle":  (
                f"The box score almost doesn't matter. {detail} — the kind of moment "
                f"that marks careers and eras. {gs.winner} also handled business on the field, {score_str}."
            ),
            "reason": "Career milestones are rare, televised, remembered. This game carries that weight.",
        }

    # ── First-place clash ─────────────────────────────────────────────────────
    if any("FIRST-PLACE" in f for f in flags):
        return {
            "headline":    f"First place on the line. {gs.winner} takes it.",
            "subheadline": f"{score_str}. Top of the division changes hands — or firms up.",
            "lead_angle":  (
                f"When two first-place teams meet, somebody goes home with a better ledger. "
                f"{winner_name} handled {loser_name} {score_str} to tighten their grip at the top. "
                f"The division race just got sharper."
            ),
            "reason": "Two division leaders, one winner — the standings implications make this the marquee matchup.",
        }

    # ── Dominant pitching ─────────────────────────────────────────────────────
    dom_flag = next((f for f in gs.flags if "DOMINANT START" in f.upper()), None)
    if dom_flag:
        detail = dom_flag.split(":", 1)[1].strip() if ":" in dom_flag else "a dominant line"
        return {
            "headline":    f"Locked in.",
            "subheadline": f"{gs.winner} wins behind a gem — {detail}.",
            "lead_angle":  (
                f"The game was never really in question. {detail} — a masterclass "
                f"that gave {winner_name} total control of the contest. "
                f"Final: {score_str}."
            ),
            "reason": "A dominant pitching performance — the rarest resource in the sport — anchors this game.",
        }

    # ── 15+ K game ───────────────────────────────────────────────────────────
    k_flag = next((f for f in gs.flags if "15+ K" in f.upper()), None)
    if k_flag:
        pitcher = k_flag.split(":", 1)[1].strip() if ":" in k_flag else "a starter"
        return {
            "headline":    f"{pitcher.split('(')[0].strip()} is untouchable.",
            "subheadline": f"{gs.winner} wins {score_str} behind a historic strikeout effort.",
            "lead_angle":  (
                f"When a pitcher fans 15 or more batters, you save the clip. "
                f"{pitcher} did it tonight, carrying {winner_name} past {loser_name} {score_str}. "
                f"That's a scoreboard, and it's also a statement."
            ),
            "reason": "15+ strikeouts by a single pitcher is a top-5 individual performance on any given day.",
        }

    # ── Multi-HR ──────────────────────────────────────────────────────────────
    hr_flag = next((f for f in gs.flags if "MULTI-HR" in f.upper()), None)
    if hr_flag:
        player = hr_flag.split(":", 1)[1].strip() if ":" in hr_flag else "a slugger"
        return {
            "headline":    f"{player.split('(')[0].strip()} goes deep — twice.",
            "subheadline": f"{score_str}. The long ball carries {gs.winner}.",
            "lead_angle":  (
                f"When one guy goes yard twice in a game, the lineup card becomes a footnote. "
                f"{player} powered {winner_name} past {loser_name} {score_str}. "
                f"Circle the at-bats."
            ),
            "reason": "A multi-home-run game by a single player gives the day a clear protagonist.",
        }

    # ── One-run game / rivalry / playoff ─────────────────────────────────────
    if any("ONE-RUN" in f for f in flags):
        rivalry = any("RIVALRY" in f for f in flags)
        playoff = any("PLAYOFF" in f for f in flags)
        ctx = " in a rivalry game" if rivalry else (" with playoff stakes" if playoff else "")
        return {
            "headline":    f"One run{ctx}. {gs.winner} survives.",
            "subheadline": f"{score_str}. Every pitch mattered.",
            "lead_angle":  (
                f"No margin for error, and {winner_name} didn't leave one. "
                f"A one-run {score_str} win over {loser_name}{ctx}. "
                f"The standings will remember it even if the score looks tidy."
            ),
            "reason": "One-run games — especially with standings implications — carry the most cumulative tension.",
        }

    # ── Default: best available remaining flags ───────────────────────────────
    lead_flag = gs.flags[0] if gs.flags else "Best game of the slate"
    return {
        "headline":    f"{gs.winner} {gs.home_runs if gs.winner == gs.home else gs.away_runs}, "
                       f"{gs.loser} {gs.home_runs if gs.loser == gs.home else gs.away_runs}.",
        "subheadline": f"{winner_name} takes the day's marquee matchup.",
        "lead_angle":  (
            f"{winner_name} beat {loser_name} {score_str} in the game that stood out most "
            f"from a full slate. {lead_flag.capitalize()}."
        ),
        "reason": f"Highest composite score on today's slate. Flags: {', '.join(gs.flags) or 'None'}.",
    }


# ── Build JSON output ─────────────────────────────────────────────────────────
def build_output(winner, all_scored, date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    copy = editorial(winner, date_str)

    ranked = []
    for rank, gs in enumerate(
        sorted(all_scored, key=lambda x: x.raw_score, reverse=True), start=1
    ):
        ranked.append({
            "rank":       rank,
            "away":       gs.away,
            "home":       gs.home,
            "away_runs":  gs.away_runs,
            "home_runs":  gs.home_runs,
            "innings":    gs.innings,
            "raw_score":  round(gs.raw_score, 1),
            "flags":      gs.flags,
            "selected":   gs.game_pk == winner.game_pk,
        })

    return {
        "date":         date_str,
        "date_display": dt.strftime("%A, %B %-d, %Y"),
        "updated":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "game": {
            "away":       winner.away,
            "home":       winner.home,
            "away_runs":  winner.away_runs,
            "home_runs":  winner.home_runs,
            "innings":    winner.innings,
            "raw_score":  round(winner.raw_score, 1),
            "flags":      winner.flags,
            "winner":     winner.winner,
            "loser":      winner.loser,
            "margin":     winner.margin,
            "total_runs": winner.total_runs,
        },
        "editorial": {
            "headline":    copy["headline"],
            "subheadline": copy["subheadline"],
            "lead_angle":  copy["lead_angle"],
            "reason":      copy["reason"],
        },
        "all_games": ranked,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def run(date_str):
    print(f"  Fetching schedule for {date_str}...")
    games = fetch_schedule(date_str)
    if not games:
        print("  No final games found.")
        return

    print(f"  {len(games)} final game(s). Fetching standings...")
    standings = fetch_standings(date_str)

    all_scored = []
    for game in games:
        away = game["teams"]["away"]["team"]["abbreviation"]
        home = game["teams"]["home"]["team"]["abbreviation"]
        pk   = game["gamePk"]
        print(f"  Scoring {away} @ {home} (pk {pk})...", end=" ", flush=True)
        try:
            feed = fetch_live_feed(pk)
            gs   = score_game(game, feed, standings, date_str)
            all_scored.append(gs)
            print(f"{gs.raw_score:.1f} pts  [{', '.join(gs.flags) or '—'}]")
        except Exception as e:
            print(f"ERROR: {e}")

    if not all_scored:
        print("  No games could be scored.")
        return

    winner = pick_winner(all_scored)
    output = build_output(winner, all_scored, date_str)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  ✓  Game of the Day: {winner.away} @ {winner.home}  ({winner.raw_score:.1f} pts)")
    print(f"     Headline: {output['editorial']['headline']}")
    print(f"     Saved → {OUT_FILE}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    date_str = args[0] if args else (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    run(date_str)
