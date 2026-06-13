#!/usr/bin/env python3
"""
Build Barrel Proof's canonical player identity files.

This is intentionally source-agnostic: it reads today's local roster data, keeps
optional fields nullable, and leaves future stat feeds to attach later by ID.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "Site Data"
PLAYERS_DIR = DATA_DIR / "players"
ROSTERS_DIR = BASE_DIR / "Rosters"

DEFAULT_OVERRIDES = {
    "team_abbr": {"OAK": "ATH"},
    "names": {
        "M. Harris II": "Michael Harris II",
        "Jazz Chisolm Jr": "Jazz Chisholm Jr.",
        "J.Jr": "Jazz Chisholm Jr.",
    },
    "player_ids": {},
    "slug_overrides": {},
    "aliases": {},
    "manual_players": [],
}

POSITION_GROUPS = {
    "P": "Pitcher",
    "SP": "Pitcher",
    "RP": "Pitcher",
    "C": "Catcher",
    "1B": "Infielder",
    "2B": "Infielder",
    "3B": "Infielder",
    "SS": "Infielder",
    "IF": "Infielder",
    "LF": "Outfielder",
    "CF": "Outfielder",
    "RF": "Outfielder",
    "OF": "Outfielder",
    "DH": "Designated Hitter",
}


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact_ws(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def ascii_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def slugify(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.replace(".", "")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", folded.lower()).strip("-")
    return slug or "player"


def initial_alias(name: str) -> str | None:
    parts = name.split()
    if len(parts) < 2:
        return None
    suffixes = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv", "v"}
    suffix = ""
    core = parts[:]
    if core[-1].lower() in suffixes:
        suffix = " " + core.pop()
    if len(core) < 2 or len(core[0]) < 1:
        return None
    return f"{core[0][0]}. {' '.join(core[1:])}{suffix}"


def normalize_team_abbr(value, overrides) -> str | None:
    abbr = compact_ws(value).upper()
    if not abbr:
        return None
    return overrides.get("team_abbr", {}).get(abbr, abbr)


def normalize_name(value, overrides) -> str:
    name = compact_ws(value)
    return compact_ws(overrides.get("names", {}).get(name, name))


def load_teams(overrides):
    data = load_json(DATA_DIR / "teams.json", {"teams": []})
    by_name = {}
    by_abbr = {}
    for team in data.get("teams", []):
        abbr = normalize_team_abbr(team.get("abbr"), overrides)
        if not abbr:
            continue
        normalized = dict(team)
        normalized["abbr"] = abbr
        by_abbr[abbr] = normalized
        for key in (team.get("name"), team.get("nickname"), team.get("city")):
            if key:
                by_name[ascii_key(key)] = normalized
    by_name["athletics"] = by_abbr.get("ATH", {"abbr": "ATH", "name": "Athletics"})
    by_name["oakland athletics"] = by_abbr.get("ATH", {"abbr": "ATH", "name": "Athletics"})
    return by_abbr, by_name


def roster_rows_from_markdown(path: Path):
    text = path.read_text(encoding="utf-8")
    team_name = ""
    for line in text.splitlines():
        if line.startswith("team:"):
            team_name = compact_ws(line.split(":", 1)[1])
            break
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped or "Name" in stripped:
            continue
        cells = [compact_ws(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        yield {
            "source": str(path.relative_to(BASE_DIR)),
            "team_name": team_name or path.stem,
            "number": cells[0].lstrip("#"),
            "full_name": cells[1],
            "position": cells[2],
            "bats": cells[3] if len(cells) > 3 else None,
            "throws": cells[4] if len(cells) > 4 else None,
            "status": "Active",
            "active": True,
        }


def walk_for_players(value, inherited=None):
    inherited = dict(inherited or {})
    if isinstance(value, dict):
        local = dict(inherited)
        for team_key in ("team", "team_name", "team_abbr", "abbr"):
            if value.get(team_key):
                local[team_key] = value.get(team_key)
        name = (
            value.get("full_name")
            or value.get("fullName")
            or value.get("display_name")
            or value.get("name")
            or value.get("player_name")
        )
        position = value.get("position") or value.get("pos") or value.get("primary_position")
        if name and position:
            row = dict(value)
            row.update(local)
            row["full_name"] = name
            row["position"] = position
            yield row
        for child in value.values():
            yield from walk_for_players(child, local)
    elif isinstance(value, list):
        for child in value:
            yield from walk_for_players(child, inherited)


def team_il_rows():
    data = load_json(DATA_DIR / "team_il.json", None)
    if not data:
        return
    for team_abbr, players in (data.get("teams") or {}).items():
        if not isinstance(players, list):
            continue
        for player in players:
            if not isinstance(player, dict):
                continue
            name = player.get("name") or player.get("full_name")
            position = player.get("position")
            if not name or not position:
                continue
            row = dict(player)
            row["full_name"] = name
            row["position"] = position
            row["team_abbr"] = team_abbr
            row["source"] = "Site Data/team_il.json"
            yield row


def json_roster_rows():
    for rel in ("mlb_rosters.json", "team_stats.json"):
        path = DATA_DIR / rel
        data = load_json(path, None)
        if data is None:
            continue
        for row in walk_for_players(data):
            row.setdefault("source", f"Site Data/{rel}")
            yield row
    yield from team_il_rows()


def source_rows():
    for path in sorted(ROSTERS_DIR.glob("*/*/*.md")):
        yield from roster_rows_from_markdown(path)
    yield from json_roster_rows()


def manual_rows(overrides):
    for row in overrides.get("manual_players", []):
        if isinstance(row, dict):
            manual = dict(row)
            manual.setdefault("source", "Site Data/players/player_manual_overrides.json")
            manual.setdefault("status", "Active")
            manual.setdefault("active", True)
            yield manual


def find_team(row, teams_by_abbr, teams_by_name, overrides):
    abbr = normalize_team_abbr(row.get("team_abbr") or row.get("abbr"), overrides)
    if abbr and abbr in teams_by_abbr:
        return teams_by_abbr[abbr]
    name = row.get("team_name") or row.get("team") or row.get("team_full") or row.get("team_full_name")
    if name:
        return teams_by_name.get(ascii_key(str(name)), {"abbr": abbr, "name": compact_ws(name)})
    return {"abbr": abbr, "name": None}


def canonical_record(row, teams_by_abbr, teams_by_name, overrides):
    full_name = normalize_name(row.get("full_name") or row.get("display_name") or row.get("name"), overrides)
    if not full_name:
        return None
    team = find_team(row, teams_by_abbr, teams_by_name, overrides)
    position = compact_ws(row.get("position") or row.get("pos") or "") or None
    mlbam_id = row.get("mlbam_id") or row.get("mlb_id") or row.get("id") or row.get("player_id")
    mlbam_id = str(mlbam_id) if mlbam_id not in (None, "") else None
    base_slug = compact_ws(row.get("slug")) or overrides.get("slug_overrides", {}).get(full_name) or slugify(full_name)
    player_id = overrides.get("player_ids", {}).get(full_name) or (f"mlbam-{mlbam_id}" if mlbam_id else base_slug)
    return {
        "player_id": player_id,
        "mlbam_id": mlbam_id,
        "full_name": full_name,
        "display_name": normalize_name(row.get("display_name") or full_name, overrides),
        "slug": base_slug,
        "team_abbr": normalize_team_abbr(team.get("abbr"), overrides),
        "team_name": team.get("name"),
        "position": position,
        "position_group": compact_ws(row.get("position_group")) or POSITION_GROUPS.get((position or "").upper()),
        "status": compact_ws(row.get("status")) or ("Active" if row.get("active", True) else None),
        "bats": compact_ws(row.get("bats")) or None,
        "throws": compact_ws(row.get("throws")) or None,
        "active": bool(row.get("active", True)),
        "_manual": "player_manual_overrides.json" in str(row.get("source") or ""),
    }


def merge_records(records):
    merged = {}
    name_team_keys = {}
    player_id_keys = {}
    for rec in records:
        if not rec:
            continue
        name_team_key = f"{ascii_key(rec.get('full_name', ''))}|{rec.get('team_abbr') or ''}"
        player_id = rec.get("player_id")
        key = rec.get("mlbam_id") or player_id or name_team_key
        if player_id and player_id in player_id_keys:
            key = player_id_keys[player_id]
        if rec.get("mlbam_id") and name_team_key in name_team_keys:
            key = name_team_keys[name_team_key]
        existing = merged.get(key)
        if not existing:
            merged[key] = rec
            name_team_keys[name_team_key] = key
            if player_id:
                player_id_keys[player_id] = key
            continue
        is_manual = bool(rec.get("_manual"))
        for field, value in rec.items():
            if value in (None, ""):
                continue
            if is_manual and field in {"mlbam_id", "player_id", "slug", "team_name", "position", "position_group", "bats", "throws", "active", "status"}:
                existing[field] = value
            elif existing.get(field) in (None, ""):
                existing[field] = value
    return list(merged.values())


def ensure_unique_slugs(records, overrides):
    by_base = defaultdict(list)
    for rec in records:
        by_base[rec["slug"]].append(rec)

    for base, group in by_base.items():
        if len(group) > 1:
            keep_base = None
            if base == "max-muncy":
                keep_base = next((rec for rec in group if rec.get("team_abbr") == "LAD"), None)
            keep_base = keep_base or sorted(group, key=lambda r: (r.get("team_abbr") or "", r.get("full_name") or ""))[0]
            for rec in group:
                if rec is keep_base:
                    continue
                suffix = rec.get("team_abbr") or rec.get("mlbam_id") or str(group.index(rec) + 1)
                rec["slug"] = f"{base}-{str(suffix).lower()}"

    for rec in records:
        rec.pop("_manual", None)
        override = overrides.get("slug_overrides", {}).get(rec.get("full_name", ""))
        if override:
            rec["slug"] = override
        if rec.get("slug") == "max-muncy-ath" and rec.get("mlbam_id"):
            rec["player_id"] = f"mlbam-{rec['mlbam_id']}"
        elif not rec.get("player_id") or rec["player_id"] == rec.get("slug"):
            rec["player_id"] = rec["slug"]
    return records


def build_aliases(records, overrides):
    aliases = {}
    normalized_lookup = {}
    by_name = defaultdict(list)
    by_short_alias = defaultdict(list)
    for rec in records:
        key = ascii_key(rec.get("full_name") or rec.get("display_name") or "")
        if key:
            by_name[key].append(rec)
        short = initial_alias(rec.get("full_name") or "")
        if short:
            by_short_alias[ascii_key(short)].append(rec)

    def team_alias_parts(rec):
        parts = {rec.get("team_abbr"), rec.get("team_name")}
        team_name = rec.get("team_name") or ""
        if team_name:
            bits = team_name.split()
            if bits:
                parts.add(bits[-1])
        if rec.get("team_abbr") == "ATH":
            parts.update({"Athletics", "Oakland Athletics"})
        return {compact_ws(part) for part in parts if compact_ws(part)}

    for rec in records:
        slug = rec["slug"]
        duplicate_name = len(by_name.get(ascii_key(rec.get("full_name") or ""), [])) > 1
        names = {rec.get("full_name"), rec.get("display_name")}
        short = initial_alias(rec.get("full_name") or "")
        if short:
            short_matches = by_short_alias.get(ascii_key(short), [])
            duplicate_short = len({match.get("slug") for match in short_matches if match.get("slug")}) > 1
            if duplicate_short:
                for team_part in team_alias_parts(rec):
                    qualified = f"{short} {team_part}"
                    aliases[qualified] = slug
                    normalized_lookup.setdefault(ascii_key(qualified), slug)
            else:
                names.add(short)
        for name in names:
            if name and not duplicate_name:
                aliases[name] = slug
                normalized_lookup.setdefault(ascii_key(name), slug)
            elif name:
                for team_part in team_alias_parts(rec):
                    qualified = f"{name} {team_part}"
                    aliases[qualified] = slug
                    normalized_lookup.setdefault(ascii_key(qualified), slug)
    for alias, target in overrides.get("aliases", {}).items():
        target_slug = aliases.get(target, target)
        aliases[alias] = target_slug
    for alias, canonical_name in overrides.get("names", {}).items():
        target = aliases.get(canonical_name) or normalized_lookup.get(ascii_key(canonical_name))
        if target:
            aliases[alias] = target
    return dict(sorted(aliases.items(), key=lambda item: item[0].lower()))


def main():
    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    overrides_path = PLAYERS_DIR / "player_manual_overrides.json"
    overrides = DEFAULT_OVERRIDES
    if overrides_path.exists():
        loaded = load_json(overrides_path, {})
        overrides = {**DEFAULT_OVERRIDES, **loaded}
        for key, value in DEFAULT_OVERRIDES.items():
            if isinstance(value, dict):
                overrides[key] = {**value, **loaded.get(key, {})}
    else:
        write_json(overrides_path, DEFAULT_OVERRIDES)

    teams_by_abbr, teams_by_name = load_teams(overrides)
    records = [canonical_record(row, teams_by_abbr, teams_by_name, overrides) for row in list(source_rows()) + list(manual_rows(overrides))]
    records = ensure_unique_slugs(merge_records(records), overrides)
    records = sorted(records, key=lambda r: (r.get("team_abbr") or "ZZZ", r.get("full_name") or ""))
    aliases = build_aliases(records, overrides)

    write_json(PLAYERS_DIR / "player_index.json", records)
    write_json(PLAYERS_DIR / "player_aliases.json", aliases)
    print(f"Wrote {len(records)} players and {len(aliases)} aliases.")


if __name__ == "__main__":
    main()
