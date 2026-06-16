#!/usr/bin/env python3
"""
Pitch Type Intelligence Data Layer
────────────────────────────────────
Pulls 2026 Statcast pitch-by-pitch data for probable starters (Dope Sheet
+ Advanced Scout named probables) and key lineup hitters (bats_to_watch
from dope_player_matchups.json).

Outputs: Site Data/pitch_type_intelligence.json

Usage:
    python3 scripts/update_pitch_type_intelligence.py
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pybaseball

pybaseball.cache.enable()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Site Data"
PLAYER_DIR = DATA_DIR / "players"

DOPE_SHEET_PATH = DATA_DIR / "dope-sheet-data.json"
PLAYER_MATCHUPS_PATH = DATA_DIR / "dope_player_matchups.json"
PITCHER_MATCHUPS_PATH = DATA_DIR / "dope_pitcher_matchups.json"
ADVANCED_SCOUT_PATH = DATA_DIR / "advanced_scout.json"
PLAYER_INDEX_PATH = PLAYER_DIR / "player_index.json"
OUTPUT_PATH = DATA_DIR / "pitch_type_intelligence.json"

SEASON_START = "2026-03-27"
SEASON_END = datetime.now(timezone.utc).strftime("%Y-%m-%d")

PITCH_FAMILIES = {
    "FF": "Fastball", "FA": "Fastball", "SI": "Fastball",
    "FT": "Fastball", "FC": "Fastball",
    "SL": "Breaking", "CU": "Breaking", "KC": "Breaking",
    "ST": "Breaking", "SV": "Breaking", "CS": "Breaking", "GY": "Breaking",
    "CH": "Offspeed", "FS": "Offspeed", "FO": "Offspeed",
    "SC": "Offspeed", "KN": "Offspeed", "EP": "Offspeed",
}

PITCH_LABELS = {
    "FF": "Four-Seam Fastball", "SI": "Sinker", "FC": "Cutter",
    "FA": "Fastball", "FT": "Two-Seam Fastball",
    "SL": "Slider", "CU": "Curveball", "KC": "Knuckle-Curve",
    "ST": "Sweeper", "SV": "Slurve", "CS": "Slow Curve", "GY": "Gyroball",
    "CH": "Changeup", "FS": "Split-Finger", "FO": "Forkball",
    "SC": "Screwball", "KN": "Knuckleball", "EP": "Eephus",
}

SWING_EVENTS = {
    "swinging_strike", "swinging_strike_blocked",
    "foul", "foul_tip",
    "hit_into_play", "hit_into_play_score", "hit_into_play_no_out",
}
WHIFF_EVENTS = {"swinging_strike", "swinging_strike_blocked"}

MIN_PITCHES = 20
MIN_SWINGS = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path, fallback=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return fallback if fallback is not None else {}


def name_to_slug(name):
    """Convert 'First Last' to 'first-last' slug."""
    s = name.lower().strip()
    s = re.sub(r"['’\.]", "", s)
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s


def parse_name(full_name):
    """Split 'First Last' into (last, first) for playerid_lookup."""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    # Handle suffixes
    suffixes = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv"}
    if parts[-1].lower() in suffixes:
        parts = parts[:-1]
    return " ".join(parts[1:]), parts[0]


_id_cache = {}


def resolve_mlbam(full_name):
    """Return (mlbam_id, canonical_slug) for a player name. None on failure."""
    if full_name in _id_cache:
        return _id_cache[full_name]
    last, first = parse_name(full_name)
    try:
        result = pybaseball.playerid_lookup(last, first, fuzzy=True)
        if result is None or result.empty:
            _id_cache[full_name] = (None, name_to_slug(full_name))
            return _id_cache[full_name]
        row = result.iloc[0]
        mlbam = int(row["key_mlbam"]) if not (row["key_mlbam"] != row["key_mlbam"]) else None
        slug = name_to_slug(full_name)
        _id_cache[full_name] = (mlbam, slug)
        return _id_cache[full_name]
    except Exception as e:
        print(f"  ID lookup failed for {full_name}: {e}", flush=True)
        _id_cache[full_name] = (None, name_to_slug(full_name))
        return _id_cache[full_name]


# ---------------------------------------------------------------------------
# Pitcher profile
# ---------------------------------------------------------------------------

def pitcher_arsenal_summary(arsenal, family_mix, primary_shape, name):
    """Build readable pitcher arsenal summary."""
    if primary_shape == "Limited Data":
        return f"{name}'s pitch-type data is limited for this sample."

    top = arsenal[:1]
    second = arsenal[1:2]

    top_label = top[0]["label"] if top else ""
    top_usage = top[0]["usage_pct"] if top else 0
    top_vel = top[0].get("avg_velocity")

    vel_str = f"sitting {top_vel:.1f} mph" if isinstance(top_vel, float) else ""

    fb_pct = family_mix.get("Fastball", 0)
    br_pct = family_mix.get("Breaking", 0)
    os_pct = family_mix.get("Offspeed", 0)

    if primary_shape == "Breaking-Heavy":
        lead = f"{name} leans heavily on breaking ball shape — {br_pct:.0f}% breaking-ball usage."
    elif primary_shape == "Fastball/Breaking":
        lead = f"{name} works primarily from a fastball/breaking-ball mix."
    elif primary_shape == "Fastball/Offspeed":
        lead = f"{name} pairs fastball velocity with offspeed timing."
    elif primary_shape == "Balanced Arsenal":
        lead = f"{name} commands a balanced arsenal across pitch families."
    else:
        lead = f"{name}'s primary shape is {primary_shape.lower()}."

    parts = [lead]
    if top_label and top_usage:
        vel_note = f", {vel_str}" if vel_str else ""
        parts.append(f"The {top_label} is the primary weapon at {top_usage:.0f}% usage{vel_note}.")

    if second:
        sl = second[0]["label"]
        su = second[0]["usage_pct"]
        parts.append(f"The {sl} ({su:.0f}%) is the key secondary.")

    return " ".join(parts)


def build_pitcher_profile(full_name, slug, team, throws, mlbam_id):
    """Pull Statcast data for a pitcher and build their profile."""
    if not mlbam_id:
        return {
            "name": full_name,
            "slug": slug,
            "team": team,
            "throws": throws,
            "sample": {"pitches": 0, "date_range": "unavailable"},
            "arsenal": [],
            "family_mix": {},
            "primary_shape": "Limited Data",
            "summary": f"{full_name}'s pitch-type data is limited for this sample.",
        }

    try:
        df = pybaseball.statcast_pitcher(SEASON_START, SEASON_END, mlbam_id)
    except Exception as e:
        print(f"    Statcast fetch failed for {full_name}: {e}", flush=True)
        return {
            "name": full_name, "slug": slug, "team": team, "throws": throws,
            "sample": {"pitches": 0, "date_range": "unavailable"},
            "arsenal": [], "family_mix": {}, "primary_shape": "Limited Data",
            "summary": f"{full_name}'s pitch-type data is limited for this sample.",
        }

    df = df[df["pitch_type"].notna() & (df["pitch_type"] != "")]
    total = len(df)

    if total < MIN_PITCHES:
        return {
            "name": full_name, "slug": slug, "team": team, "throws": throws,
            "sample": {"pitches": total, "date_range": "insufficient"},
            "arsenal": [], "family_mix": {}, "primary_shape": "Limited Data",
            "summary": f"{full_name} has limited pitch-type data this season ({total} pitches tracked).",
        }

    # Date range
    dates = df["game_date"].dropna()
    date_range = f"{dates.min()} to {dates.max()}" if not dates.empty else "2026 season"

    # Per-pitch-type aggregation
    arsenal = []
    family_counts = {}

    for pt, grp in df.groupby("pitch_type"):
        label = PITCH_LABELS.get(pt, pt)
        family = PITCH_FAMILIES.get(pt, "Other")
        count = len(grp)
        usage_pct = count / total * 100

        speeds = grp["release_speed"].dropna()
        avg_vel = round(float(speeds.mean()), 1) if not speeds.empty else None

        swing_mask = grp["description"].isin(SWING_EVENTS)
        whiff_mask = grp["description"].isin(WHIFF_EVENTS)
        swing_count = swing_mask.sum()
        whiff_count = whiff_mask.sum()
        whiff_pct = round(whiff_count / swing_count * 100, 1) if swing_count >= 5 else None

        arsenal.append({
            "pitch": pt,
            "label": label,
            "family": family,
            "usage_pct": round(usage_pct, 1),
            "whiff_pct": whiff_pct,
            "avg_velocity": avg_vel,
        })

        family_counts[family] = family_counts.get(family, 0) + count

    arsenal.sort(key=lambda x: x["usage_pct"], reverse=True)

    # Family mix
    family_mix = {
        fam: round(cnt / total * 100, 1)
        for fam, cnt in family_counts.items()
        if fam != "Other"
    }

    # Primary shape
    fb = family_mix.get("Fastball", 0)
    br = family_mix.get("Breaking", 0)
    os = family_mix.get("Offspeed", 0)

    if br >= 45:
        primary_shape = "Breaking-Heavy"
    elif fb >= 50 and br >= 25:
        primary_shape = "Fastball/Breaking"
    elif fb >= 50 and os >= 20:
        primary_shape = "Fastball/Offspeed"
    elif max(fb, br, os) < 45:
        primary_shape = "Balanced Arsenal"
    elif fb >= 60:
        primary_shape = "Fastball/Breaking"
    else:
        primary_shape = "Balanced Arsenal"

    summary = pitcher_arsenal_summary(arsenal, family_mix, primary_shape, full_name)

    return {
        "name": full_name,
        "slug": slug,
        "team": team,
        "throws": throws,
        "sample": {"pitches": total, "date_range": date_range},
        "arsenal": arsenal,
        "family_mix": family_mix,
        "primary_shape": primary_shape,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Hitter profile
# ---------------------------------------------------------------------------

def family_damage_label(pitches, swings, whiffs, whiff_threshold_high=0.33, whiff_threshold_low=0.18):
    """Return (damage, contact) labels for a pitch family."""
    if pitches < MIN_PITCHES:
        return "limited", "limited"
    whiff_rate = whiffs / swings if swings >= MIN_SWINGS else None
    if whiff_rate is None:
        return "neutral", "neutral"
    if whiff_rate >= whiff_threshold_high:
        damage = "risk"
        contact = "risk"
    elif whiff_rate <= whiff_threshold_low:
        damage = "strong"
        contact = "strong"
    else:
        damage = "neutral"
        contact = "neutral"
    return damage, contact


def hitter_family_summary(name, family, damage, contact, pitches):
    """One-sentence readable note for a hitter's pitch family profile."""
    if damage == "limited":
        return f"Limited {family.lower()} data for {name} this season."
    if damage == "strong" and contact == "strong":
        return f"{name} makes consistent contact and finds damage lanes against {family.lower()} pitching."
    if damage == "risk" and contact == "risk":
        return f"{name} carries swing-and-miss risk against {family.lower()} pitching — chase vulnerability is elevated."
    if damage == "strong":
        return f"{name} generates contact against {family.lower()} pitching with solid run-production upside."
    if contact == "risk":
        return f"{name} has some whiff exposure against {family.lower()} shape — chase risk below the zone."
    return f"{name} profiles as a neutral bat against {family.lower()} pitching."


def hitter_overall_summary(name, best_family, risk_family, family_profile):
    """Readable overall summary for a hitter's pitch-type fit."""
    if best_family == "Limited Data":
        return f"{name}'s pitch-type split data is limited for this sample."

    parts = []
    if best_family:
        p = family_profile.get(best_family, {})
        if p.get("damage") == "strong":
            parts.append(f"{name} finds the damage lane against {best_family.lower()} pitching.")
        else:
            parts.append(f"{name} fits best in {best_family.lower()}-heavy matchups.")

    if risk_family and risk_family != best_family:
        parts.append(f"The risk spot is {risk_family.lower()} — chase vulnerability goes up when pitchers work that family.")

    return " ".join(parts) if parts else f"{name} shows a balanced pitch-type profile."


def build_hitter_profile(full_name, slug, team, bats, mlbam_id):
    """Pull Statcast batter data and build hitter pitch-family profile."""
    if not mlbam_id:
        return {
            "name": full_name, "slug": slug, "team": team, "bats": bats,
            "sample": {"pitches": 0, "date_range": "unavailable"},
            "pitch_family_profile": {},
            "best_family": "Limited Data", "risk_family": "Limited Data",
            "summary": f"{full_name}'s pitch-type data is unavailable.",
        }

    try:
        df = pybaseball.statcast_batter(SEASON_START, SEASON_END, mlbam_id)
    except Exception as e:
        print(f"    Statcast batter fetch failed for {full_name}: {e}", flush=True)
        return {
            "name": full_name, "slug": slug, "team": team, "bats": bats,
            "sample": {"pitches": 0, "date_range": "unavailable"},
            "pitch_family_profile": {},
            "best_family": "Limited Data", "risk_family": "Limited Data",
            "summary": f"{full_name}'s pitch-type data is limited for this sample.",
        }

    df = df[df["pitch_type"].notna() & (df["pitch_type"] != "")]
    total = len(df)

    if total < MIN_PITCHES:
        return {
            "name": full_name, "slug": slug, "team": team, "bats": bats,
            "sample": {"pitches": total, "date_range": "insufficient"},
            "pitch_family_profile": {},
            "best_family": "Limited Data", "risk_family": "Limited Data",
            "summary": f"{full_name} has limited pitch-type data this season ({total} pitches tracked).",
        }

    df = df.copy()
    df["family"] = df["pitch_type"].map(PITCH_FAMILIES).fillna("Other")

    dates = df["game_date"].dropna()
    date_range = f"{dates.min()} to {dates.max()}" if not dates.empty else "2026 season"

    family_profile = {}
    family_scores = {}

    for fam in ["Fastball", "Breaking", "Offspeed"]:
        sub = df[df["family"] == fam]
        n_pitches = len(sub)
        swings = sub["description"].isin(SWING_EVENTS).sum()
        whiffs = sub["description"].isin(WHIFF_EVENTS).sum()

        damage, contact = family_damage_label(n_pitches, swings, whiffs)
        summary = hitter_family_summary(full_name, fam, damage, contact, n_pitches)

        family_profile[fam] = {
            "damage": damage,
            "contact": contact,
            "pitches": n_pitches,
            "summary": summary,
        }

        # Score for best/risk ranking (lower whiff = better fit)
        if damage == "strong":
            family_scores[fam] = 2
        elif damage == "neutral":
            family_scores[fam] = 1
        elif damage == "limited":
            family_scores[fam] = 0
        else:  # risk
            family_scores[fam] = -1

    # Best and risk families (only from families with enough data)
    scored = [(fam, score) for fam, score in family_scores.items()
              if family_profile[fam]["damage"] != "limited"]

    if scored:
        scored.sort(key=lambda x: x[1], reverse=True)
        best_family = scored[0][0]
        risk_candidates = [f for f, s in scored if s < 0]
        risk_family = risk_candidates[0] if risk_candidates else (scored[-1][0] if len(scored) > 1 else "Limited Data")
    else:
        best_family = "Limited Data"
        risk_family = "Limited Data"

    summary = hitter_overall_summary(full_name, best_family, risk_family, family_profile)

    return {
        "name": full_name,
        "slug": slug,
        "team": team,
        "bats": bats,
        "sample": {"pitches": total, "date_range": date_range},
        "pitch_family_profile": family_profile,
        "best_family": best_family,
        "risk_family": risk_family,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Collect targets
# ---------------------------------------------------------------------------

def collect_pitcher_targets():
    """Return list of {name, slug, team, throws} dicts from Dope Sheet + Advanced Scout."""
    dope = load_json(DOPE_SHEET_PATH, {})
    games = dope.get("games") or (dope if isinstance(dope, list) else [])
    ptm = load_json(PITCHER_MATCHUPS_PATH, {})
    ptm_games = ptm.get("games") or []

    # Build slug/throws lookup from pitcher matchups
    ptm_lookup = {}
    for g in ptm_games:
        for side in ("away_pitcher", "home_pitcher"):
            p = g.get(side) or {}
            if p.get("name"):
                ptm_lookup[p["name"]] = {
                    "slug": p.get("slug") or name_to_slug(p["name"]),
                    "team": p.get("team") or "",
                    "throws": p.get("throws") or "",
                }

    seen = {}

    def add_pitcher(name, slug=None, team="", throws=""):
        if not name or name in ("TBD", "Probable starter TBD"):
            return
        if name in seen:
            return
        slug = slug or ptm_lookup.get(name, {}).get("slug") or name_to_slug(name)
        team = team or ptm_lookup.get(name, {}).get("team", "")
        throws = throws or ptm_lookup.get(name, {}).get("throws", "")
        seen[name] = {"name": name, "slug": slug, "team": team, "throws": throws}

    # From dope-sheet-data pitchers
    for g in games:
        for side in ("away", "home"):
            p = g.get("pitchers", {}).get(side, {})
            pname = p.get("name", "")
            if pname:
                add_pitcher(pname)

    # From advanced_scout named probables
    adv = load_json(ADVANCED_SCOUT_PATH, {})
    for s in adv.get("series", []):
        pp = s.get("pitching_path", {})
        for pname in pp.get("away_probables", []) + pp.get("home_probables", []):
            if pname and pname not in ("TBD", "Probable starter TBD"):
                add_pitcher(pname)

    return list(seen.values())


def collect_hitter_targets():
    """Return list of {name, slug, team, bats} dicts from dope_player_matchups bats_to_watch."""
    pm = load_json(PLAYER_MATCHUPS_PATH, {})
    games = pm.get("games") or []

    seen = {}
    for g in games:
        for side in ("away_bats_to_watch", "home_bats_to_watch"):
            for b in g.get(side, []):
                name = b.get("full_name", "")
                slug = b.get("slug", "") or name_to_slug(name)
                if not name or slug in seen:
                    continue
                seen[slug] = {
                    "name": name,
                    "slug": slug,
                    "team": b.get("team_abbr", ""),
                    "bats": b.get("bats", ""),
                }

    return list(seen.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Pitch Type Intelligence ===", flush=True)
    print(f"Season window: {SEASON_START} to {SEASON_END}", flush=True)

    pitchers = collect_pitcher_targets()
    hitters = collect_hitter_targets()
    print(f"Targets: {len(pitchers)} pitchers, {len(hitters)} hitters", flush=True)

    pitcher_profiles = {}
    print(f"\nBuilding pitcher profiles...", flush=True)
    for i, p in enumerate(pitchers, 1):
        print(f"  [{i}/{len(pitchers)}] {p['name']}...", flush=True)
        mlbam, slug = resolve_mlbam(p["name"])
        profile = build_pitcher_profile(
            p["name"],
            p["slug"] or slug,
            p["team"],
            p["throws"],
            mlbam,
        )
        pitcher_profiles[p["slug"] or slug] = profile
        shape = profile["primary_shape"]
        sample = profile["sample"]["pitches"]
        print(f"    → {shape} ({sample} pitches)", flush=True)

    hitter_profiles = {}
    print(f"\nBuilding hitter profiles...", flush=True)
    for i, h in enumerate(hitters, 1):
        print(f"  [{i}/{len(hitters)}] {h['name']}...", flush=True)
        mlbam, slug = resolve_mlbam(h["name"])
        profile = build_hitter_profile(
            h["name"],
            h["slug"] or slug,
            h["team"],
            h["bats"],
            mlbam,
        )
        hitter_profiles[h["slug"] or slug] = profile
        best = profile["best_family"]
        sample = profile["sample"]["pitches"]
        print(f"    → best: {best} ({sample} pitches)", flush=True)

    pitcher_available = sum(1 for p in pitcher_profiles.values() if p["primary_shape"] != "Limited Data")
    hitter_available = sum(1 for h in hitter_profiles.values() if h["best_family"] != "Limited Data")

    if pitcher_available + hitter_available == 0:
        dq = "limited"
    elif (pitcher_available + hitter_available) / max(len(pitcher_profiles) + len(hitter_profiles), 1) < 0.5:
        dq = "partial"
    else:
        dq = "available"

    out = {
        "meta": {
            "date": SEASON_END,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "season": 2026,
            "source": "pybaseball/statcast",
            "data_quality": dq,
            "pitcher_count": len(pitcher_profiles),
            "hitter_count": len(hitter_profiles),
            "pitcher_available": pitcher_available,
            "hitter_available": hitter_available,
        },
        "pitchers": pitcher_profiles,
        "hitters": hitter_profiles,
    }

    OUTPUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(
        f"\nWrote {OUTPUT_PATH} — "
        f"{len(pitcher_profiles)} pitchers ({pitcher_available} with data), "
        f"{len(hitter_profiles)} hitters ({hitter_available} with data), "
        f"quality={dq}",
        flush=True,
    )


if __name__ == "__main__":
    main()
