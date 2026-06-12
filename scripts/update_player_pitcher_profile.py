"""
Build Site Data/players/pitcher_profile_summary.json from
pitcher_foundation_signal.json. Pure data layer — no rendering.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Site Data" / "players"

FOUNDATION_PATH = DATA_DIR / "pitcher_foundation_signal.json"
OUTPUT_PATH = DATA_DIR / "pitcher_profile_summary.json"

VALID_PROFILE_TYPES = [
    "Insufficient Data",
    "Ace Foundation",
    "Strong Foundation",
    "Small-Sample Standout",
    "Stable Arm",
    "Volatile Arm",
    "Pitching Risk",
]

SUMMARY_LABELS = {
    "Insufficient Data": "Not enough tracking data to establish a pitching foundation yet.",
    "Ace Foundation": "Top-end pitching foundation with enough workload to trust.",
    "Strong Foundation": "Strong pitching foundation backed by solid sample size.",
    "Small-Sample Standout": "Strong early signal, but sample size is still small.",
    "Stable Arm": "Solid, dependable pitching foundation.",
    "Volatile Arm": "Mixed indicators point to an inconsistent foundation.",
    "Pitching Risk": "Underlying indicators point to significant risk.",
}


def classify(signal, confidence):
    if signal is None or confidence == "INSUFFICIENT":
        return "Insufficient Data"
    if signal >= 85 and confidence == "HIGH":
        return "Ace Foundation"
    if signal >= 75 and confidence in ("HIGH", "MEDIUM"):
        return "Strong Foundation"
    if signal >= 75 and confidence == "LOW":
        return "Small-Sample Standout"
    if signal >= 60 and confidence in ("HIGH", "MEDIUM"):
        return "Stable Arm"
    if 40 <= signal < 60:
        return "Volatile Arm"
    return "Pitching Risk"


def build_notes(profile_type, signal, confidence, era, whip, k9, bb9, kbb_strength):
    notes = []

    if profile_type == "Insufficient Data":
        notes.append("Sample size is limited.")
        notes.append("Additional tracking data is needed to establish a foundation.")
        return notes

    # Run prevention (ERA)
    if era is not None and era <= 3.50:
        notes.append("Run prevention foundation is strong.")
    elif era is not None and era >= 4.75:
        notes.append("Run prevention indicators are weak.")

    # Baserunner prevention (WHIP)
    if whip is not None and whip <= 1.20:
        notes.append("Baserunner prevention is a strength.")
    elif whip is not None and whip >= 1.45:
        notes.append("Baserunners are reaching too often.")

    # Strikeout rate (K/9)
    if k9 is not None and k9 >= 9.0:
        notes.append("Strikeout rate supports the profile.")
    elif k9 is not None and k9 < 6.5:
        notes.append("Strikeout rate is below average.")

    # Walk rate (BB/9)
    if bb9 is not None and bb9 <= 3.0:
        notes.append("Walk rate is under control.")
    elif bb9 is not None and bb9 >= 4.5:
        notes.append("Walk rate is a concern.")

    # K/BB strength
    if kbb_strength is not None and kbb_strength >= 3.0:
        notes.append("Strikeout-to-walk ratio is a strength.")

    if profile_type in ("Volatile Arm", "Pitching Risk"):
        notes.append("Current foundation is volatile.")

    if profile_type == "Small-Sample Standout":
        notes.append("Sample size is limited.")

    # Deduplicate while preserving order, cap at 4
    seen = set()
    deduped = []
    for n in notes:
        if n not in seen:
            seen.add(n)
            deduped.append(n)

    if not deduped:
        deduped.append("Foundation indicators are mixed.")

    return deduped[:4]


def main():
    foundation = json.loads(FOUNDATION_PATH.read_text(encoding="utf-8"))
    source_players = foundation.get("players", {})

    out_players = {}
    type_counts = {t: 0 for t in VALID_PROFILE_TYPES}

    for slug, p in source_players.items():
        signal = p.get("pitcher_foundation_signal")
        confidence = p.get("confidence")
        era = p.get("era")
        whip = p.get("whip")
        k9 = p.get("k9")
        bb9 = p.get("bb9")
        kbb_strength = p.get("kbb_strength")
        ip = p.get("ip")

        profile_type = classify(signal, confidence)
        type_counts[profile_type] += 1

        notes = build_notes(profile_type, signal, confidence, era, whip, k9, bb9, kbb_strength)

        out_players[slug] = {
            "slug": slug,
            "full_name": p.get("full_name"),
            "team_abbr": p.get("team_abbr"),
            "profile_type": profile_type,
            "summary_label": SUMMARY_LABELS[profile_type],
            "confidence": confidence,
            "pitcher_foundation_signal": signal,
            "foundation_label": p.get("label"),
            "ip": ip,
            "era": era,
            "whip": whip,
            "k9": k9,
            "bb9": bb9,
            "kbb_strength": kbb_strength,
            "supporting_notes": notes,
        }

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": foundation.get("meta", {}).get("season", 2026),
        "source": "Barrel Proof pitcher foundation signal",
        "status": "success",
        "profile_count": len(out_players),
        "insufficient_data_count": type_counts["Insufficient Data"],
    }

    output = {"meta": meta, "players": out_players}
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH} with {len(out_players)} players")
    for t in VALID_PROFILE_TYPES:
        print(f"  {t}: {type_counts[t]}")


if __name__ == "__main__":
    main()
