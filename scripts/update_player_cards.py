#!/usr/bin/env python3
"""Build basic PLAYER-002 traditional stat cards from existing site data."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "Site Data"
PLAYERS_DIR = DATA_DIR / "players"
PLAYER_PAGES_DIR = PLAYERS_DIR / "player_pages"

HITTER_FIELDS = [
    "player_id", "slug", "full_name", "team_abbr", "position",
    "games", "avg", "obp", "slg", "ops", "hr", "rbi", "runs", "sb", "bb", "so",
]
PITCHER_FIELDS = [
    "player_id", "slug", "full_name", "team_abbr", "position",
    "games", "games_started", "wins", "losses", "saves", "era", "ip", "so", "bb", "whip",
]


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


def clean(value):
    if value in ("", "—", None):
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def to_int(value):
    value = clean(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def add_number(current, value):
    value = to_int(value)
    if value is None:
        return current
    return (current or 0) + value


def ip_to_outs(value):
    value = clean(value)
    if value is None:
        return None
    text = str(value)
    if "." in text:
        whole, frac = text.split(".", 1)
        try:
            return int(whole) * 3 + int(frac[:1] or 0)
        except ValueError:
            return None
    try:
        return int(text) * 3
    except ValueError:
        return None


def outs_to_ip(outs):
    if outs is None:
        return None
    whole, rem = divmod(int(outs), 3)
    return f"{whole}.{rem}" if rem else f"{whole}.0"


def parse_record(value):
    if not value or "-" not in str(value):
        return None, None
    left, right = str(value).split("-", 1)
    return to_int(left), to_int(right)


def build_resolver(players, aliases):
    by_slug = {p.get("slug"): p for p in players if p.get("slug")}
    by_exact = {}
    by_normalized = {}
    for player in players:
        for name in (player.get("full_name"), player.get("display_name")):
            if name:
                by_exact[name] = player
                by_normalized.setdefault(lookup_key(name), player)
        if player.get("slug"):
            by_normalized.setdefault(lookup_key(player["slug"]), player)

    normalized_aliases = {lookup_key(alias): target for alias, target in aliases.items()}

    def resolve(name):
        if not name:
            return None
        if name in by_exact:
            return by_exact[name]
        target = aliases.get(name)
        if target:
            return by_slug.get(target)
        key = lookup_key(name)
        target = normalized_aliases.get(key)
        if target:
            return by_slug.get(target)
        return by_normalized.get(key)

    return resolve


def blank_hitter(player, position=None):
    return {
        "player_id": player.get("player_id"),
        "slug": player.get("slug"),
        "full_name": player.get("full_name") or player.get("display_name"),
        "team_abbr": player.get("team_abbr"),
        "position": position or player.get("position"),
        "games": None,
        "avg": None,
        "obp": None,
        "slg": None,
        "ops": None,
        "hr": None,
        "rbi": None,
        "runs": None,
        "sb": None,
        "bb": None,
        "so": None,
    }


def blank_pitcher(player, position=None):
    return {
        "player_id": player.get("player_id"),
        "slug": player.get("slug"),
        "full_name": player.get("full_name") or player.get("display_name"),
        "team_abbr": player.get("team_abbr"),
        "position": position or player.get("position"),
        "games": None,
        "games_started": None,
        "wins": None,
        "losses": None,
        "saves": None,
        "era": None,
        "ip": None,
        "so": None,
        "bb": None,
        "whip": None,
        "_outs": None,
        "_observed_games": False,
    }


def add_hitter_row(cards, player, row):
    slug = player.get("slug")
    if not slug:
        return
    card = cards.setdefault(slug, blank_hitter(player, row.get("pos")))
    card["games"] = (card.get("games") or 0) + 1
    card["position"] = card.get("position") or row.get("pos") or player.get("position")
    card["hr"] = add_number(card.get("hr"), row.get("hr"))
    card["rbi"] = add_number(card.get("rbi"), row.get("rbi"))
    card["runs"] = add_number(card.get("runs"), row.get("r"))
    for optional in ("sb", "bb", "so"):
        if optional in row:
            card[optional] = add_number(card.get(optional), row.get(optional))


def add_pitcher_row(cards, player, row, *, started=False, decision=None):
    slug = player.get("slug")
    if not slug:
        return
    card = cards.setdefault(slug, blank_pitcher(player, row.get("pos") or "P"))
    card["games"] = (card.get("games") or 0) + 1
    card["_observed_games"] = True
    if started:
        card["games_started"] = (card.get("games_started") or 0) + 1
    elif card.get("games_started") is None:
        card["games_started"] = 0
    if decision == "W":
        card["wins"] = (card.get("wins") or 0) + 1
    elif decision == "L":
        card["losses"] = (card.get("losses") or 0) + 1
    elif decision == "SV":
        card["saves"] = (card.get("saves") or 0) + 1
    card["so"] = add_number(card.get("so"), row.get("k") if "k" in row else row.get("so"))
    card["bb"] = add_number(card.get("bb"), row.get("bb"))
    outs = ip_to_outs(row.get("ip"))
    if outs is not None:
        card["_outs"] = (card.get("_outs") or 0) + outs
        card["ip"] = outs_to_ip(card["_outs"])


def apply_dope_pitchers(cards, resolve):
    data = load_json(DATA_DIR / "dope-sheet-data.json", {})
    for game in data.get("games", []):
        for side in ("away", "home"):
            pitcher = game.get("pitchers", {}).get(side, {})
            player = resolve(pitcher.get("name"))
            if not player:
                continue
            slug = player.get("slug")
            card = cards.setdefault(slug, blank_pitcher(player, "P"))
            card["era"] = clean(pitcher.get("era")) or card.get("era")
            card["whip"] = clean(pitcher.get("whip")) or card.get("whip")
            card["ip"] = clean(pitcher.get("ip")) or card.get("ip")
            wins, losses = parse_record(pitcher.get("record"))
            if wins is not None:
                card["wins"] = wins
            if losses is not None:
                card["losses"] = losses


def strip_internal(card, fields):
    cleaned = {field: clean(card.get(field)) for field in fields}
    return cleaned


def main():
    players = load_json(PLAYERS_DIR / "player_index.json", [])
    aliases = load_json(PLAYERS_DIR / "player_aliases.json", {})
    resolve = build_resolver(players, aliases)
    hitter_cards = {}
    pitcher_cards = {}

    game_cards = load_json(DATA_DIR / "game_cards.json", {})
    for game in game_cards.get("games", []):
        for side in ("away", "home"):
            abbr = game.get(f"{side}_abbr")
            for row in game.get(f"{side}_batting", []):
                player = resolve(row.get("name"))
                if player:
                    add_hitter_row(hitter_cards, player, row)

            pitchers = game.get(f"{side}_pitching", [])
            for index, row in enumerate(pitchers):
                player = resolve(row.get("name"))
                if not player:
                    continue
                decision = None
                decisions = game.get("decisions", {})
                for marker in ("W", "L", "SV"):
                    if row.get("name") and row.get("name") == decisions.get(marker):
                        decision = marker
                add_pitcher_row(pitcher_cards, player, row, started=(index == 0), decision=decision)

    apply_dope_pitchers(pitcher_cards, resolve)

    hitter_output = [
        strip_internal(card, HITTER_FIELDS)
        for card in sorted(hitter_cards.values(), key=lambda c: (c.get("team_abbr") or "", c.get("full_name") or ""))
    ]
    pitcher_output = [
        strip_internal(card, PITCHER_FIELDS)
        for card in sorted(pitcher_cards.values(), key=lambda c: (c.get("team_abbr") or "", c.get("full_name") or ""))
    ]

    hitter_by_slug = {card["slug"]: card for card in hitter_output if card.get("slug")}
    pitcher_by_slug = {card["slug"]: card for card in pitcher_output if card.get("slug")}
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    PLAYER_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    for player in players:
        slug = player.get("slug")
        if not slug:
            continue
        page = dict(player)
        page["hitter_card"] = hitter_by_slug.get(slug)
        page["pitcher_card"] = pitcher_by_slug.get(slug)
        page["generated_at"] = generated_at
        page["metadata"] = {
            "player_cards_version": "PLAYER-002",
            "sources": ["Site Data/game_cards.json", "Site Data/dope-sheet-data.json"],
        }
        write_json(PLAYER_PAGES_DIR / f"{slug}.json", page)

    write_json(PLAYERS_DIR / "hitter_cards.json", hitter_output)
    write_json(PLAYERS_DIR / "pitcher_cards.json", pitcher_output)
    print(
        f"Wrote {len(hitter_output)} hitter cards, "
        f"{len(pitcher_output)} pitcher cards, {len(players)} player pages."
    )


if __name__ == "__main__":
    main()
