"""
Readiness checker for Site Data/dope_game_intelligence.json
"""
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PATH = BASE_DIR / "Site Data" / "dope_game_intelligence.json"
DOPE_SHEET_DATA_PATH = BASE_DIR / "Site Data" / "dope-sheet-data.json"

BAD_STRINGS = {"nan", "inf", "-inf", "undefined", "none"}

REQUIRED_GAME_KEYS = {
    "away_team", "home_team", "game_read", "game_report", "lineup_read", "pitching_read",
    "bullpen_read", "environment_read", "players_who_tilt_game",
    "fantasy_dfs_watch", "betting_props_watch", "data_basis",
}

REQUIRED_GAME_REPORT_KEYS = {
    "game_shape", "pitching_arsenal_read", "away_lineup_path",
    "home_lineup_path", "bullpen_environment_read", "fantasy_dfs_props_watch",
}

FASTBALL_EDGE_LABELS = {"Fastball Damage", "Handles Fastballs", "Contact Path"}
FASTBALL_EDGE_CAP = 3
VALID_GRADES = {"green", "yellow", "red", "gray"}
MATCHUP_BOARD_KEYS = {"away_starter", "home_starter", "away_lineup_vs_home_starter", "home_lineup_vs_away_starter", "board_summary"}
GREEN_FAIL = 6
GREEN_WARN = 5
GRAY_MISSING_FAIL_PCT = 45  # fail if >45% of hitter slots are gray due to missing profiles
GRAY_MISSING_WARN_PCT = 25
BANNED_HITTER_PHRASES = ["No pitch-type profile", "No profile", "Pitch-type profile unavailable for this hitter"]

BANNED_PHRASES = [
    "poised to", "set to", "showcase", "battle", "clash",
    "will look to", "only time will tell", "it remains to be seen",
    "both teams are looking to", "intriguing matchup",
    "exciting contest", "highly anticipated",
]
BANNED_BET = [
    "lock", "guaranteed", "free money", "must bet", "bet this",
    "smash spot", "can't miss", "easy money", "automatic", "hammer", "wager",
]


def fail(msg):
    print(f"FAIL: {msg}")
    print("DOPE GAME INTELLIGENCE BLOCKED")
    raise SystemExit(1)


def is_bad_value(v):
    if isinstance(v, str) and v.strip().lower() in BAD_STRINGS:
        return True
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return True
    return False


def walk(value, path):
    if isinstance(value, dict):
        for k, v in value.items():
            walk(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            walk(v, f"{path}[{i}]")
    else:
        if is_bad_value(value):
            fail(f"{path} has bad value {value!r}")


def main():
    if not PATH.exists():
        fail(f"{PATH} does not exist")

    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"invalid JSON: {e}")

    if "meta" not in data or "games" not in data:
        fail("missing meta or games key")

    meta = data["meta"]
    for key in ("date", "generated_at", "game_count"):
        if key not in meta:
            fail(f"meta.{key} missing")

    games = data["games"]
    if not isinstance(games, dict) or not games:
        fail("games is empty or not a dict")

    if meta["game_count"] != len(games):
        fail(f"meta.game_count ({meta['game_count']}) != len(games) ({len(games)})")

    # Compare against dope-sheet-data active game count (doubleheaders must not be collapsed).
    if DOPE_SHEET_DATA_PATH.exists():
        dope_sheet_data = json.loads(DOPE_SHEET_DATA_PATH.read_text(encoding="utf-8"))
        dope_games = dope_sheet_data.get("games") or []
        if len(dope_games) != len(games):
            fail(
                f"intelligence game count ({len(games)}) != dope-sheet-data game count ({len(dope_games)}); "
                f"doubleheaders may have been collapsed"
            )
        # Build expected pair counts for duplicate-pair validation below
        expected_pair_counts: dict = {}
        for dg in dope_games:
            p = (dg.get("away"), dg.get("home"))
            expected_pair_counts[p] = expected_pair_counts.get(p, 0) + 1
    else:
        expected_pair_counts = {}

    # Validate that duplicate (away, home) pairs in intelligence match dope-sheet-data expectations
    seen_pair_counts: dict = {}
    for g in games.values():
        if not isinstance(g, dict):
            continue
        p = (g.get("away_team"), g.get("home_team"))
        seen_pair_counts[p] = seen_pair_counts.get(p, 0) + 1
    for p, count in seen_pair_counts.items():
        allowed = expected_pair_counts.get(p, 1)
        if count > allowed:
            fail(f"intelligence has {count} records for pair {p} but dope-sheet-data only has {allowed}")

    all_text = json.dumps(data)
    all_lower = all_text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in all_lower:
            fail(f"banned phrase found: '{phrase}'")
    for word in BANNED_BET:
        if word in all_lower:
            fail(f"banned betting word found: '{word}'")

    for game_id, g in games.items():
        missing = REQUIRED_GAME_KEYS - set(g.keys())
        if missing:
            fail(f"game {game_id} missing keys: {missing}")

        if not g["game_read"] or not isinstance(g["game_read"], str):
            fail(f"game {game_id} has empty/invalid game_read")

        # game_report validation
        gr = g.get("game_report")
        if not isinstance(gr, dict):
            fail(f"game {game_id} game_report must be a dict")
        gr_missing = REQUIRED_GAME_REPORT_KEYS - set(gr.keys())
        if gr_missing:
            fail(f"game {game_id} game_report missing keys: {gr_missing}")
        for key in ("game_shape", "pitching_arsenal_read", "away_lineup_path", "home_lineup_path", "bullpen_environment_read"):
            if not gr.get(key) or not isinstance(gr[key], str):
                fail(f"game {game_id} game_report.{key} is empty or invalid")
        if not isinstance(gr.get("fantasy_dfs_props_watch"), list):
            fail(f"game {game_id} game_report.fantasy_dfs_props_watch must be a list")

        # Fastball edge cap check
        ptm = g.get("pitch_type_matchup", {})
        edges = ptm.get("hitters_with_edge", [])
        fb_edge_count = sum(1 for e in edges if e.get("edge") in FASTBALL_EDGE_LABELS)
        if fb_edge_count > FASTBALL_EDGE_CAP:
            fail(
                f"game {game_id} has {fb_edge_count} fastball-family edge labels "
                f"(cap is {FASTBALL_EDGE_CAP})"
            )

        for side in ("away", "home"):
            if side not in g["lineup_read"]:
                fail(f"game {game_id} lineup_read missing {side}")
        if "matchup_shape" not in g["lineup_read"]:
            fail(f"game {game_id} lineup_read missing matchup_shape")

        for side in ("away_starter", "home_starter"):
            if side not in g["pitching_read"]:
                fail(f"game {game_id} pitching_read missing {side}")
        for key in ("starter_edge", "game_pitching_shape"):
            if key not in g["pitching_read"]:
                fail(f"game {game_id} pitching_read missing {key}")

        if not isinstance(g["players_who_tilt_game"], list):
            fail(f"game {game_id} players_who_tilt_game must be a list")

        for p in g["players_who_tilt_game"]:
            for key in ("name", "team", "tag", "reason"):
                if key not in p or not p[key]:
                    fail(f"game {game_id} tilt player missing {key}")

        if not isinstance(g["fantasy_dfs_watch"], list):
            fail(f"game {game_id} fantasy_dfs_watch must be a list")
        if not isinstance(g["betting_props_watch"], list):
            fail(f"game {game_id} betting_props_watch must be a list")
        if not isinstance(g["data_basis"], list):
            fail(f"game {game_id} data_basis must be a list")

    # matchup_board grade distribution and quality checks
    total_hitters = 0
    gray_hitters = 0
    for game_id, g in games.items():
        mb = g.get("matchup_board")
        if not mb:
            continue
        for side in ("away_lineup_vs_home_starter", "home_lineup_vs_away_starter"):
            for h in mb.get(side, []):
                total_hitters += 1
                if h.get("grade") == "gray":
                    gray_hitters += 1
                reason = h.get("reason", "")
                for phrase in BANNED_HITTER_PHRASES:
                    if phrase in reason:
                        fail(f"game {game_id} hitter {h.get('name')} reason contains banned phrase: '{phrase}'")

    if total_hitters > 0:
        gray_pct = gray_hitters / total_hitters * 100
        if gray_pct > GRAY_MISSING_FAIL_PCT:
            fail(f"matchup_board gray hitter rate {gray_pct:.1f}% exceeds {GRAY_MISSING_FAIL_PCT}% threshold ({gray_hitters}/{total_hitters})")
        if gray_pct > GRAY_MISSING_WARN_PCT:
            print(f"WARN: matchup_board gray hitter rate {gray_pct:.1f}% ({gray_hitters}/{total_hitters}) — above {GRAY_MISSING_WARN_PCT}% warning threshold")
        print(f"INFO: matchup_board grade coverage: {total_hitters} hitters, {gray_hitters} gray ({gray_pct:.1f}%)")

    # matchup_board validation (optional but structured when present)
    for game_id, g in games.items():
        mb = g.get("matchup_board")
        if mb is None:
            continue
        if not isinstance(mb, dict):
            fail(f"game {game_id} matchup_board must be a dict")
        missing_mb = MATCHUP_BOARD_KEYS - set(mb.keys())
        if missing_mb:
            fail(f"game {game_id} matchup_board missing keys: {missing_mb}")
        if not isinstance(mb.get("board_summary"), str) or not mb["board_summary"].strip():
            fail(f"game {game_id} matchup_board.board_summary must be a non-empty string")
        for side in ("away_lineup_vs_home_starter", "home_lineup_vs_away_starter"):
            lineup = mb.get(side, [])
            if not isinstance(lineup, list):
                fail(f"game {game_id} matchup_board.{side} must be a list")
            green_count = 0
            for hitter in lineup:
                grade = hitter.get("grade")
                if grade not in VALID_GRADES:
                    fail(f"game {game_id} matchup_board.{side} hitter {hitter.get('name')} has invalid grade: {grade!r}")
                if not hitter.get("reason") or not isinstance(hitter["reason"], str):
                    fail(f"game {game_id} matchup_board.{side} hitter {hitter.get('name')} has missing/invalid reason")
                if grade == "green":
                    green_count += 1
            if green_count >= GREEN_FAIL:
                fail(f"game {game_id} matchup_board.{side} has {green_count} green grades (cap is {GREEN_FAIL - 1})")
            if green_count >= GREEN_WARN:
                print(f"WARN: game {game_id} matchup_board.{side} has {green_count} green grades — verify grading is not too generous")

    walk(data, "dope_game_intelligence")

    print(f"PASS: {len(games)} games, date={meta['date']}")
    print("DOPE GAME INTELLIGENCE READY")


if __name__ == "__main__":
    main()
