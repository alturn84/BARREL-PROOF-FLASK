#!/usr/bin/env python3
"""Build PLAYER-002B season batting/pitching stat JSON from pybaseball."""

from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYERS_DIR = BASE_DIR / "Site Data" / "players"
SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().year

HITTER_OUT = PLAYERS_DIR / "season_hitter_stats.json"
PITCHER_OUT = PLAYERS_DIR / "season_pitcher_stats.json"
WOBA_CONSTANTS_PATH = PLAYERS_DIR / "woba_constants.json"

TEAM_ABBR_OVERRIDES = {
    "CHW": "CWS",
    "KCR": "KC",
    "OAK": "ATH",
    "SDP": "SD",
    "SFG": "SF",
    "TBR": "TB",
    "WSN": "WSH",
}

TEAM_NAME_TO_ABBR = {
    "arizona": "ARI",
    "arizona diamondbacks": "ARI",
    "athletics": "ATH",
    "oakland": "ATH",
    "oakland athletics": "ATH",
    "atlanta": "ATL",
    "atlanta braves": "ATL",
    "baltimore": "BAL",
    "baltimore orioles": "BAL",
    "boston": "BOS",
    "boston red sox": "BOS",
    "chicago cubs": "CHC",
    "cubs": "CHC",
    "chicago white sox": "CWS",
    "white sox": "CWS",
    "cincinnati": "CIN",
    "cincinnati reds": "CIN",
    "cleveland": "CLE",
    "cleveland guardians": "CLE",
    "colorado": "COL",
    "colorado rockies": "COL",
    "detroit": "DET",
    "detroit tigers": "DET",
    "houston": "HOU",
    "houston astros": "HOU",
    "kansas city": "KC",
    "kansas city royals": "KC",
    "los angeles angels": "LAA",
    "angels": "LAA",
    "los angeles dodgers": "LAD",
    "dodgers": "LAD",
    "miami": "MIA",
    "miami marlins": "MIA",
    "milwaukee": "MIL",
    "milwaukee brewers": "MIL",
    "minnesota": "MIN",
    "minnesota twins": "MIN",
    "new york mets": "NYM",
    "mets": "NYM",
    "new york yankees": "NYY",
    "yankees": "NYY",
    "philadelphia": "PHI",
    "philadelphia phillies": "PHI",
    "pittsburgh": "PIT",
    "pittsburgh pirates": "PIT",
    "san diego": "SD",
    "san diego padres": "SD",
    "san francisco": "SF",
    "san francisco giants": "SF",
    "seattle": "SEA",
    "seattle mariners": "SEA",
    "st louis": "STL",
    "st louis cardinals": "STL",
    "st. louis": "STL",
    "st. louis cardinals": "STL",
    "tampa bay": "TB",
    "tampa bay rays": "TB",
    "texas": "TEX",
    "texas rangers": "TEX",
    "toronto": "TOR",
    "toronto blue jays": "TOR",
    "washington": "WSH",
    "washington nationals": "WSH",
}

DEFAULT_WOBA_WEIGHTS = {
    "wBB": 0.69,
    "wHBP": 0.72,
    "w1B": 0.89,
    "w2B": 1.27,
    "w3B": 1.62,
    "wHR": 2.10,
}

HITTER_FIELDS = [
    "games", "pa", "ab", "h", "singles", "doubles", "triples", "hr",
    "bb", "ibb", "hbp", "sf", "avg", "obp", "slg", "ops", "rbi", "runs", "sb", "so",
    "calculated_woba",
]
PITCHER_FIELDS = ["games", "games_started", "wins", "losses", "saves", "era", "ip", "so", "bb", "whip"]
RATE_FIELDS = {"avg", "obp", "slg", "ops"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lookup_key(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def fix_name(value):
    if value in (None, "", "—"):
        return None
    text = str(value)
    try:
        text = bytes(text, "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    text = unicodedata.normalize("NFC", text)
    return text.replace("*", "").replace("#", "").strip()


def clean_number(value):
    if value in (None, "", "—"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def clean_int(value):
    number = clean_number(value)
    if number is None:
        return None
    return int(number)


def clean_float(value, digits=3):
    number = clean_number(value)
    if number is None:
        return None
    return round(number, digits)


def clean_rate(value):
    number = clean_number(value)
    if number is None:
        return None
    text = f"{number:.3f}"
    return text[1:] if text.startswith("0") else text


def load_woba_weights():
    data = load_json(WOBA_CONSTANTS_PATH, {})
    weights = data.get("weights", {}) if isinstance(data, dict) else {}
    loaded = {}
    for key, fallback in DEFAULT_WOBA_WEIGHTS.items():
        value = clean_number(weights.get(key))
        loaded[key] = fallback if value is None else value
    return loaded


def calculate_woba(row, weights):
    ab = clean_int(row.get("AB"))
    h = clean_int(row.get("H"))
    doubles = clean_int(row.get("2B"))
    triples = clean_int(row.get("3B"))
    hr = clean_int(row.get("HR"))
    bb = clean_int(row.get("BB"))
    ibb = clean_int(row.get("IBB"))
    hbp = clean_int(row.get("HBP"))
    sf = clean_int(row.get("SF"))
    required = (ab, h, doubles, triples, hr, bb, hbp, sf)
    if any(value is None for value in required):
        return None, None
    ibb = ibb or 0
    singles = h - doubles - triples - hr
    if singles < 0:
        return singles, None
    ubb = bb - ibb
    denominator = ab + bb - ibb + sf + hbp
    if denominator <= 0:
        return singles, None
    numerator = (
        weights["wBB"] * ubb
        + weights["wHBP"] * hbp
        + weights["w1B"] * singles
        + weights["w2B"] * doubles
        + weights["w3B"] * triples
        + weights["wHR"] * hr
    )
    return singles, round(numerator / denominator, 3)


def clean_ip(value):
    number = clean_number(value)
    if number is None:
        return None
    text = str(value).strip()
    return text if text and text.lower() != "nan" else None


def normalize_team(value):
    if value in (None, "", "—"):
        return None
    text = str(value).strip()
    upper = text.upper()
    if upper in {"TOT", "2TM", "3TM", "4TM", "5TM", "MULTI", "MULTIPLE TEAMS"}:
        return None
    upper = TEAM_ABBR_OVERRIDES.get(upper, upper)
    if upper in {
        "ARI", "ATH", "ATL", "BAL", "BOS", "CHC", "CIN", "CLE", "COL", "CWS",
        "DET", "HOU", "KC", "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY",
        "PHI", "PIT", "SD", "SEA", "SF", "STL", "TB", "TEX", "TOR", "WSH",
    }:
        return upper
    return TEAM_NAME_TO_ABBR.get(lookup_key(text))


def row_team(row):
    for key in ("Tm", "Team", "team", "team_abbr"):
        team = normalize_team(row.get(key))
        if team:
            return team
    return None


def build_resolver(players, aliases):
    by_slug = {player.get("slug"): player for player in players if player.get("slug")}
    by_name_team = {}
    by_name = {}
    for player in players:
        team = player.get("team_abbr")
        for name in (player.get("full_name"), player.get("display_name")):
            key = lookup_key(name)
            if not key:
                continue
            by_name_team.setdefault((key, team), []).append(player)
            by_name.setdefault(key, []).append(player)

    normalized_aliases = {lookup_key(alias): target for alias, target in aliases.items()}

    def unique_candidates(candidates):
        unique = {}
        for candidate in candidates:
            slug = candidate.get("slug")
            if slug:
                unique[slug] = candidate
        return list(unique.values())

    def resolve(name, team):
        key = lookup_key(name)
        if not key:
            return None, "unmatched", []

        if team:
            candidates = unique_candidates(by_name_team.get((key, team), []))
            if len(candidates) == 1:
                return candidates[0], "name_team", []
            if len(candidates) > 1:
                return None, "ambiguous", candidates

        target = normalized_aliases.get(key)
        if target and target in by_slug:
            return by_slug[target], "alias", []

        candidates = unique_candidates(by_name.get(key, []))
        unique_slugs = {candidate.get("slug") for candidate in candidates if candidate.get("slug")}
        if len(unique_slugs) == 1 and len(candidates) == 1:
            return candidates[0], "unique_name", []
        if candidates:
            return None, "ambiguous", candidates

        return None, "unmatched", []

    return resolve


def base_output(status="success", error=None):
    meta = {
        "generated_at": now_iso(),
        "season": SEASON,
        "source": "pybaseball/bref",
        "fetch_status": status,
        "matched_count": 0,
        "unmatched_count": 0,
        "ambiguous_count": 0,
    }
    if error:
        meta["error"] = str(error)[:500]
    return {"meta": meta, "players": {}, "unmatched": [], "ambiguous": []}


def row_identity(row):
    return {
        "source_name": fix_name(row.get("Name") or row.get("name")),
        "source_team": row.get("Tm") or row.get("Team") or row.get("team"),
        "team_abbr": row_team(row),
    }


def add_problem(target, row, candidates=None):
    info = row_identity(row)
    if candidates:
        info["candidate_slugs"] = sorted(candidate.get("slug") for candidate in candidates if candidate.get("slug"))
    target.append(info)


def finish_output(output):
    output["players"] = dict(sorted(output["players"].items()))
    output["unmatched"] = sorted(output["unmatched"], key=lambda item: (item.get("source_name") or "", item.get("source_team") or ""))
    output["ambiguous"] = sorted(output["ambiguous"], key=lambda item: (item.get("source_name") or "", item.get("source_team") or ""))
    output["meta"]["matched_count"] = len(output["players"])
    output["meta"]["unmatched_count"] = len(output["unmatched"])
    output["meta"]["ambiguous_count"] = len(output["ambiguous"])
    return output


def hitter_card(player, row, weights=None):
    weights = weights or DEFAULT_WOBA_WEIGHTS
    singles, calculated_woba = calculate_woba(row, weights)
    return {
        "slug": player.get("slug"),
        "full_name": player.get("full_name") or player.get("display_name"),
        "team_abbr": player.get("team_abbr"),
        "games": clean_int(row.get("G")),
        "pa": clean_int(row.get("PA")),
        "ab": clean_int(row.get("AB")),
        "h": clean_int(row.get("H")),
        "singles": singles,
        "doubles": clean_int(row.get("2B")),
        "triples": clean_int(row.get("3B")),
        "avg": clean_rate(row.get("BA")),
        "obp": clean_rate(row.get("OBP")),
        "slg": clean_rate(row.get("SLG")),
        "ops": clean_rate(row.get("OPS")),
        "hr": clean_int(row.get("HR")),
        "rbi": clean_int(row.get("RBI")),
        "runs": clean_int(row.get("R")),
        "sb": clean_int(row.get("SB")),
        "bb": clean_int(row.get("BB")),
        "ibb": clean_int(row.get("IBB")),
        "hbp": clean_int(row.get("HBP")),
        "sf": clean_int(row.get("SF")),
        "so": clean_int(row.get("SO")),
        "calculated_woba": calculated_woba,
    }


def pitcher_card(player, row):
    return {
        "slug": player.get("slug"),
        "full_name": player.get("full_name") or player.get("display_name"),
        "team_abbr": player.get("team_abbr"),
        "games": clean_int(row.get("G")),
        "games_started": clean_int(row.get("GS")),
        "wins": clean_int(row.get("W")),
        "losses": clean_int(row.get("L")),
        "saves": clean_int(row.get("SV")),
        "era": clean_float(row.get("ERA"), 2),
        "ip": clean_ip(row.get("IP")),
        "so": clean_int(row.get("SO")),
        "bb": clean_int(row.get("BB")),
        "whip": clean_float(row.get("WHIP"), 3),
    }


def merge_rows(rows, players, aliases, make_card, *card_args):
    resolve = build_resolver(players, aliases)
    output = base_output()
    seen_unmatched = set()
    seen_ambiguous = set()
    for row in rows:
        name = fix_name(row.get("Name") or row.get("name"))
        team = row_team(row)
        player, method, candidates = resolve(name, team)
        if not player:
            problem_key = (lookup_key(name), str(row.get("Tm") or row.get("Team") or ""), team)
            if method == "ambiguous":
                if problem_key not in seen_ambiguous:
                    seen_ambiguous.add(problem_key)
                    add_problem(output["ambiguous"], row, candidates)
            elif problem_key not in seen_unmatched:
                seen_unmatched.add(problem_key)
                add_problem(output["unmatched"], row)
            continue
        slug = player.get("slug")
        if not slug:
            continue
        card = make_card(player, row, *card_args)
        output["players"][slug] = card
    return finish_output(output)


def dataframe_records(df):
    if df is None:
        return []
    return df.to_dict(orient="records")


def write_failed(error):
    failure = base_output("failed", error)
    write_json(HITTER_OUT, failure)
    write_json(PITCHER_OUT, failure)


def main() -> int:
    players = load_json(PLAYERS_DIR / "player_index.json", [])
    aliases = load_json(PLAYERS_DIR / "player_aliases.json", {})
    if not isinstance(players, list) or not isinstance(aliases, dict):
        write_failed("PLAYER-001 index or aliases are unavailable.")
        print("PLAYER SEASON STATS FETCH FAILED: player identity files unavailable")
        return 0

    try:
        from pybaseball import batting_stats_bref, cache, pitching_stats_bref

        cache.enable()
        batting_rows = dataframe_records(batting_stats_bref(SEASON))
        pitching_rows = dataframe_records(pitching_stats_bref(SEASON))
    except Exception as exc:
        write_failed(f"{type(exc).__name__}: {exc}")
        print(f"PLAYER SEASON STATS FETCH FAILED: {exc}")
        return 0

    woba_weights = load_woba_weights()
    hitter_output = merge_rows(batting_rows, players, aliases, hitter_card, woba_weights)
    pitcher_output = merge_rows(pitching_rows, players, aliases, pitcher_card)
    write_json(HITTER_OUT, hitter_output)
    write_json(PITCHER_OUT, pitcher_output)
    print(
        "Wrote season stats: "
        f"{hitter_output['meta']['matched_count']} hitters matched, "
        f"{pitcher_output['meta']['matched_count']} pitchers matched."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
