#!/usr/bin/env python3
"""
Pitch Type Intelligence Data Layer — cron-safe
────────────────────────────────────────────────
Pulls 2026 Statcast pitch-by-pitch data for probable starters (Dope Sheet
+ Advanced Scout named probables) and key lineup hitters (bats_to_watch
from dope_player_matchups.json).

Failure handling:
  - Individual player failures are caught and logged; one bad fetch
    cannot crash the script.
  - If fresh generation produces usable data (≥50% of each group),
    the file is written with cache_status="fresh".
  - If fresh data is partially usable (some data but below threshold),
    the file is written with data_quality="partial", cache_status="fresh".
  - If fresh generation produces no usable data AND a valid cache file
    exists that is ≤3 days old, the old file is reused (meta updated).
  - If fresh generation produces no usable data AND no valid cache exists,
    a minimal fallback JSON is written so downstream scripts never break.

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
OUTPUT_PATH = DATA_DIR / "pitch_type_intelligence.json"

SEASON_START = "2026-03-27"
SEASON_END = datetime.now(timezone.utc).strftime("%Y-%m-%d")

CACHE_MAX_AGE_DAYS = 3

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
MIN_BIP = 15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path, fallback=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return fallback if fallback is not None else {}


def name_to_slug(name):
    s = name.lower().strip()
    s = re.sub(r"[''\.]", "", s)
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s


def parse_name(full_name):
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    suffixes = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv"}
    if parts[-1].lower() in suffixes:
        parts = parts[:-1]
    return " ".join(parts[1:]), parts[0]


_id_cache = {}


def resolve_mlbam(full_name):
    """Return (mlbam_id, slug). mlbam_id is None if lookup fails."""
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
        _id_cache[full_name] = (mlbam, name_to_slug(full_name))
        return _id_cache[full_name]
    except Exception as e:
        print(f"  ID lookup failed for {full_name}: {e}", flush=True)
        _id_cache[full_name] = (None, name_to_slug(full_name))
        return _id_cache[full_name]


def load_existing_cache():
    """Return existing output JSON if it exists, is valid, and is ≤3 days old."""
    if not OUTPUT_PATH.exists():
        return None
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    meta = data.get("meta", {})
    if not meta.get("generated_at") or not meta.get("data_quality"):
        return None
    try:
        gen_dt = datetime.fromisoformat(meta["generated_at"].replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - gen_dt).total_seconds() / 86400
        if age_days > CACHE_MAX_AGE_DAYS:
            return None
    except Exception:
        return None
    if not isinstance(data.get("pitchers"), dict) or not isinstance(data.get("hitters"), dict):
        return None
    return data


# ---------------------------------------------------------------------------
# Pitcher profile
# ---------------------------------------------------------------------------

def pitcher_arsenal_summary(arsenal, family_mix, primary_shape, name):
    if primary_shape == "Limited Data":
        return f"{name}'s pitch-type data is limited for this sample."

    top = arsenal[:1]
    second = arsenal[1:2]
    top_label = top[0]["label"] if top else ""
    top_usage = top[0]["usage_pct"] if top else 0
    top_vel = top[0].get("avg_velocity")
    vel_str = f"sitting {top_vel:.1f} mph" if isinstance(top_vel, float) else ""

    br_pct = family_mix.get("Breaking", 0)

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
        parts.append(f"The {second[0]['label']} ({second[0]['usage_pct']:.0f}%) is the key secondary.")
    return " ".join(parts)


def build_pitcher_profile(full_name, slug, team, throws, mlbam_id):
    """Build pitcher profile. Returns a profile dict; never raises."""
    limited_base = {
        "name": full_name, "slug": slug, "team": team, "throws": throws,
        "sample": {"pitches": 0, "date_range": "unavailable"},
        "arsenal": [], "family_mix": {}, "primary_shape": "Limited Data",
        "summary": f"{full_name}'s pitch-type data is limited for this sample.",
    }

    if not mlbam_id:
        return limited_base

    try:
        df = pybaseball.statcast_pitcher(SEASON_START, SEASON_END, mlbam_id)
    except Exception as e:
        err = str(e)[:120]
        print(f"    Statcast fetch failed for {full_name}: {err}", flush=True)
        return {**limited_base, "data_quality": "limited", "failure_reason": err}

    try:
        df = df[df["pitch_type"].notna() & (df["pitch_type"] != "")]
        total = len(df)

        if total < MIN_PITCHES:
            return {
                **limited_base,
                "sample": {"pitches": total, "date_range": "insufficient"},
                "summary": f"{full_name} has limited pitch-type data this season ({total} pitches tracked).",
            }

        dates = df["game_date"].dropna()
        date_range = f"{dates.min()} to {dates.max()}" if not dates.empty else "2026 season"

        arsenal = []
        family_counts = {}

        for pt, grp in df.groupby("pitch_type"):
            label = PITCH_LABELS.get(pt, pt)
            family = PITCH_FAMILIES.get(pt, "Other")
            count = len(grp)
            usage_pct = count / total * 100
            speeds = grp["release_speed"].dropna()
            avg_vel = round(float(speeds.mean()), 1) if not speeds.empty else None
            swing_count = grp["description"].isin(SWING_EVENTS).sum()
            whiff_count = grp["description"].isin(WHIFF_EVENTS).sum()
            whiff_pct = round(whiff_count / swing_count * 100, 1) if swing_count >= 5 else None
            bip_grp = grp[grp["type"] == "X"]
            bip_count = len(bip_grp)
            if bip_count >= MIN_BIP:
                hard_hit_count = (bip_grp["launch_speed"].dropna() >= 95).sum()
                hard_hit_pct = round(hard_hit_count / bip_count * 100, 1)
                barrel_mask = (
                    (bip_grp["launch_speed"] >= 98) &
                    (bip_grp["launch_angle"] >= 8) &
                    (bip_grp["launch_angle"] <= 50)
                )
                barrel_pct = round(barrel_mask.sum() / bip_count * 100, 1)
            else:
                hard_hit_pct = None
                barrel_pct = None
            arsenal.append({
                "pitch": pt, "label": label, "family": family,
                "usage_pct": round(usage_pct, 1), "whiff_pct": whiff_pct,
                "avg_velocity": avg_vel,
                "bip_count": bip_count,
                "hard_hit_pct": hard_hit_pct,
                "barrel_pct": barrel_pct,
            })
            family_counts[family] = family_counts.get(family, 0) + count

        arsenal.sort(key=lambda x: x["usage_pct"], reverse=True)
        family_mix = {
            fam: round(cnt / total * 100, 1)
            for fam, cnt in family_counts.items() if fam != "Other"
        }

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
            "name": full_name, "slug": slug, "team": team, "throws": throws,
            "sample": {"pitches": total, "date_range": date_range},
            "arsenal": arsenal, "family_mix": family_mix,
            "primary_shape": primary_shape, "summary": summary,
        }

    except Exception as e:
        err = str(e)[:120]
        print(f"    Profile build failed for {full_name}: {err}", flush=True)
        return {**limited_base, "data_quality": "limited", "failure_reason": err}


# ---------------------------------------------------------------------------
# Hitter profile
# ---------------------------------------------------------------------------

def family_damage_label(pitches, swings, whiffs):
    if pitches < MIN_PITCHES:
        return "limited", "limited"
    whiff_rate = whiffs / swings if swings >= MIN_SWINGS else None
    if whiff_rate is None:
        return "neutral", "neutral"
    if whiff_rate >= 0.33:
        return "risk", "risk"
    if whiff_rate <= 0.18:
        return "strong", "strong"
    return "neutral", "neutral"


def hitter_family_summary(name, family, damage, contact, pitches):
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
    if best_family == "Limited Data":
        return f"{name}'s pitch-type split data is limited for this sample."
    parts = []
    p = family_profile.get(best_family, {})
    if p.get("damage") == "strong":
        parts.append(f"{name} finds the damage lane against {best_family.lower()} pitching.")
    else:
        parts.append(f"{name} fits best in {best_family.lower()}-heavy matchups.")
    if risk_family and risk_family != best_family:
        parts.append(f"The risk spot is {risk_family.lower()} — chase vulnerability goes up when pitchers work that family.")
    return " ".join(parts) if parts else f"{name} shows a balanced pitch-type profile."


def build_hitter_profile(full_name, slug, team, bats, mlbam_id):
    """Build hitter profile. Returns a profile dict; never raises."""
    limited_base = {
        "name": full_name, "slug": slug, "team": team, "bats": bats,
        "sample": {"pitches": 0, "date_range": "unavailable"},
        "pitch_family_profile": {},
        "best_family": "Limited Data", "risk_family": "Limited Data",
        "summary": f"{full_name}'s pitch-type data is unavailable.",
    }

    if not mlbam_id:
        return limited_base

    try:
        df = pybaseball.statcast_batter(SEASON_START, SEASON_END, mlbam_id)
    except Exception as e:
        err = str(e)[:120]
        print(f"    Statcast batter fetch failed for {full_name}: {err}", flush=True)
        return {
            **limited_base,
            "summary": f"{full_name}'s pitch-type data is limited for this sample.",
            "data_quality": "limited",
            "failure_reason": err,
        }

    try:
        df = df[df["pitch_type"].notna() & (df["pitch_type"] != "")]
        total = len(df)

        if total < MIN_PITCHES:
            return {
                **limited_base,
                "sample": {"pitches": total, "date_range": "insufficient"},
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
            fam_summary = hitter_family_summary(full_name, fam, damage, contact, n_pitches)
            family_profile[fam] = {
                "damage": damage, "contact": contact,
                "pitches": n_pitches, "summary": fam_summary,
            }
            family_scores[fam] = 2 if damage == "strong" else (1 if damage == "neutral" else (0 if damage == "limited" else -1))

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
            "name": full_name, "slug": slug, "team": team, "bats": bats,
            "sample": {"pitches": total, "date_range": date_range},
            "pitch_family_profile": family_profile,
            "best_family": best_family, "risk_family": risk_family,
            "summary": summary,
        }

    except Exception as e:
        err = str(e)[:120]
        print(f"    Hitter profile build failed for {full_name}: {err}", flush=True)
        return {
            **limited_base,
            "summary": f"{full_name}'s pitch-type data is limited for this sample.",
            "data_quality": "limited",
            "failure_reason": err,
        }


# ---------------------------------------------------------------------------
# Collect targets
# ---------------------------------------------------------------------------

def collect_pitcher_targets():
    dope = load_json(DOPE_SHEET_PATH, {})
    games = dope.get("games") or (dope if isinstance(dope, list) else [])
    ptm = load_json(PITCHER_MATCHUPS_PATH, {})
    ptm_games = ptm.get("games") or []

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
        if not name or name in ("TBD", "Probable starter TBD") or name in seen:
            return
        slug = slug or ptm_lookup.get(name, {}).get("slug") or name_to_slug(name)
        team = team or ptm_lookup.get(name, {}).get("team", "")
        throws = throws or ptm_lookup.get(name, {}).get("throws", "")
        seen[name] = {"name": name, "slug": slug, "team": team, "throws": throws}

    for g in games:
        for side in ("away", "home"):
            pname = g.get("pitchers", {}).get(side, {}).get("name", "")
            if pname:
                add_pitcher(pname)

    adv = load_json(ADVANCED_SCOUT_PATH, {})
    for s in adv.get("series", []):
        pp = s.get("pitching_path", {})
        for pname in pp.get("away_probables", []) + pp.get("home_probables", []):
            if pname and pname not in ("TBD", "Probable starter TBD"):
                add_pitcher(pname)

    return list(seen.values())


def collect_hitter_targets():
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
                    "name": name, "slug": slug,
                    "team": b.get("team_abbr", ""), "bats": b.get("bats", ""),
                }
    return list(seen.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("=== Pitch Type Intelligence ===", flush=True)
    print(f"Season window: {SEASON_START} to {SEASON_END}", flush=True)

    pitchers = collect_pitcher_targets()
    hitters = collect_hitter_targets()
    print(f"Targets: {len(pitchers)} pitchers, {len(hitters)} hitters", flush=True)

    # ── Pitcher profiles ──────────────────────────────────────────────
    pitcher_profiles = {}
    failure_notes = []

    print("\nBuilding pitcher profiles...", flush=True)
    for i, p in enumerate(pitchers, 1):
        print(f"  [{i}/{len(pitchers)}] {p['name']}...", flush=True)
        try:
            mlbam, slug = resolve_mlbam(p["name"])
            profile = build_pitcher_profile(
                p["name"], p["slug"] or slug, p["team"], p["throws"], mlbam
            )
        except Exception as e:
            err = str(e)[:120]
            print(f"    UNEXPECTED error for {p['name']}: {err}", flush=True)
            slug = p.get("slug") or name_to_slug(p["name"])
            profile = {
                "name": p["name"], "slug": slug, "team": p["team"], "throws": p["throws"],
                "sample": {"pitches": 0, "date_range": "unavailable"},
                "arsenal": [], "family_mix": {}, "primary_shape": "Limited Data",
                "summary": f"{p['name']}'s pitch-type data is limited for this sample.",
                "data_quality": "limited", "failure_reason": err,
            }

        key = p["slug"] or slug
        pitcher_profiles[key] = profile
        shape = profile["primary_shape"]
        pitches = profile["sample"]["pitches"]
        print(f"    → {shape} ({pitches} pitches)", flush=True)
        if "failure_reason" in profile and len(failure_notes) < 5:
            failure_notes.append(f"Pitcher {p['name']}: {profile['failure_reason']}")

    # ── Hitter profiles ───────────────────────────────────────────────
    hitter_profiles = {}

    print("\nBuilding hitter profiles...", flush=True)
    for i, h in enumerate(hitters, 1):
        print(f"  [{i}/{len(hitters)}] {h['name']}...", flush=True)
        try:
            mlbam, slug = resolve_mlbam(h["name"])
            profile = build_hitter_profile(
                h["name"], h["slug"] or slug, h["team"], h["bats"], mlbam
            )
        except Exception as e:
            err = str(e)[:120]
            print(f"    UNEXPECTED error for {h['name']}: {err}", flush=True)
            slug = h.get("slug") or name_to_slug(h["name"])
            profile = {
                "name": h["name"], "slug": slug, "team": h["team"], "bats": h["bats"],
                "sample": {"pitches": 0, "date_range": "unavailable"},
                "pitch_family_profile": {},
                "best_family": "Limited Data", "risk_family": "Limited Data",
                "summary": f"{h['name']}'s pitch-type data is limited for this sample.",
                "data_quality": "limited", "failure_reason": err,
            }

        key = h["slug"] or slug
        hitter_profiles[key] = profile
        best = profile["best_family"]
        pitches = profile["sample"]["pitches"]
        print(f"    → best: {best} ({pitches} pitches)", flush=True)
        if "failure_reason" in profile and len(failure_notes) < 5:
            failure_notes.append(f"Hitter {h['name']}: {profile['failure_reason']}")

    # ── Assess quality ────────────────────────────────────────────────
    pitcher_available = sum(
        1 for p in pitcher_profiles.values() if p.get("primary_shape") not in (None, "Limited Data")
    )
    hitter_available = sum(
        1 for h in hitter_profiles.values() if h.get("best_family") not in (None, "Limited Data")
    )
    failed_pitcher_count = sum(1 for p in pitcher_profiles.values() if "failure_reason" in p)
    failed_hitter_count = sum(1 for h in hitter_profiles.values() if "failure_reason" in h)

    n_pitchers = max(len(pitcher_profiles), 1)
    n_hitters = max(len(hitter_profiles), 1)
    pitcher_rate = pitcher_available / n_pitchers
    hitter_rate = hitter_available / n_hitters

    # "Failed badly" = no usable data at all from either group
    failed_badly = pitcher_available == 0 and hitter_available == 0

    # Data quality label for fresh writes
    if pitcher_rate >= 0.5 and hitter_rate >= 0.5:
        dq = "available"
    elif pitcher_available > 0 or hitter_available > 0:
        dq = "partial"
    else:
        dq = "limited"

    base_meta = {
        "date": SEASON_END,
        "season": 2026,
        "source": "pybaseball/statcast",
        "pitcher_count": len(pitcher_profiles),
        "hitter_count": len(hitter_profiles),
        "pitcher_available": pitcher_available,
        "hitter_available": hitter_available,
        "failed_pitcher_count": failed_pitcher_count,
        "failed_hitter_count": failed_hitter_count,
        "failure_notes": failure_notes,
    }

    # ── Write decision ────────────────────────────────────────────────
    if not failed_badly:
        # Fresh write (available or partial)
        out = {
            "meta": {
                **base_meta,
                "generated_at": now_str,
                "data_quality": dq,
                "cache_status": "fresh",
            },
            "pitchers": pitcher_profiles,
            "hitters": hitter_profiles,
        }
        OUTPUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(
            f"\nWrote {OUTPUT_PATH} — "
            f"{len(pitcher_profiles)} pitchers ({pitcher_available} with data), "
            f"{len(hitter_profiles)} hitters ({hitter_available} with data), "
            f"quality={dq}, cache_status=fresh",
            flush=True,
        )
        return

    # Fresh generation produced no usable data — try existing cache
    print("\n⚠ Fresh generation produced no usable data.", flush=True)
    cached = load_existing_cache()

    if cached:
        cached_meta = cached.get("meta", {})
        cached_meta["generated_at"] = now_str
        cached_meta["cache_status"] = "reused_previous"
        cached_meta["failed_pitcher_count"] = failed_pitcher_count
        cached_meta["failed_hitter_count"] = failed_hitter_count
        cached_meta["failure_notes"] = failure_notes
        cached["meta"] = cached_meta
        OUTPUT_PATH.write_text(json.dumps(cached, indent=2), encoding="utf-8")
        print(
            f"⚠ Reused previous cache (original date: {cached_meta.get('date', 'unknown')}). "
            f"cache_status=reused_previous",
            flush=True,
        )
        return

    # No valid cache — write minimal fallback
    print("⚠ No valid cache available. Writing fallback.", flush=True)
    fallback = {
        "meta": {
            **base_meta,
            "generated_at": now_str,
            "data_quality": "limited",
            "cache_status": "fallback_limited",
        },
        "pitchers": {},
        "hitters": {},
    }
    OUTPUT_PATH.write_text(json.dumps(fallback, indent=2), encoding="utf-8")
    print("⚠ Wrote fallback_limited — downstream scripts will use limited pitch-type data.", flush=True)


if __name__ == "__main__":
    main()
