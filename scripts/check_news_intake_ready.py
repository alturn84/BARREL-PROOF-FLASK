"""
Readiness checker for Site Data/news_intake.json.

Validates schema, source attribution, and content safety.
PASSES on a valid limited fallback (data_quality=limited).
FAILS only on missing file, invalid JSON, or schema-breaking missing fields.
"""
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PATH = BASE_DIR / "Site Data" / "news_intake.json"

VALID_QUALITIES = {"available", "partial", "limited"}
VALID_STATUSES = {"ok", "failed", "limited"}
VALID_CONFIDENCES = {"high", "medium", "low"}
REQUIRED_META_KEYS = {"date", "generated_at", "data_quality", "item_count",
                      "source_count", "failure_count", "failure_notes"}
REQUIRED_SOURCE_KEYS = {"source_name", "source_url", "status"}
REQUIRED_ITEM_KEYS = {"source_name", "source_url", "summary", "confidence"}
SUMMARY_WORD_WARN = 30    # warn if summary exceeds this
SUMMARY_WORD_FAIL = 80    # fail if summary exceeds this (likely copied excerpt)
BAD_VALUES = {"nan", "inf", "-inf", "undefined", "none", "null"}


def fail(msg):
    print(f"FAIL: {msg}")
    print("NEWS INTAKE BLOCKED")
    raise SystemExit(1)


def warn(msg):
    print(f"WARN: {msg}")


def is_bad(v):
    if isinstance(v, str) and v.strip().lower() in BAD_VALUES:
        return True
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return True
    return False


def word_count(s):
    return len(s.split()) if s else 0


def check_items(items, list_name, extra_keys=None):
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            fail(f"{list_name}[{i}] is not a dict")
        missing = REQUIRED_ITEM_KEYS - set(item.keys())
        if missing:
            fail(f"{list_name}[{i}] missing required keys: {missing}")
        for key in REQUIRED_ITEM_KEYS:
            val = item.get(key)
            if val is None or val == "":
                # confidence and source_url must be non-empty
                if key in ("confidence", "source_url", "source_name"):
                    fail(f"{list_name}[{i}].{key} is empty or None")
            if isinstance(val, str) and is_bad(val):
                fail(f"{list_name}[{i}].{key} has bad value {val!r}")
        conf = item.get("confidence", "")
        if conf and conf not in VALID_CONFIDENCES:
            fail(f"{list_name}[{i}].confidence is invalid: {conf!r}")
        summary = item.get("summary") or ""
        wc = word_count(summary)
        if wc > SUMMARY_WORD_FAIL:
            fail(
                f"{list_name}[{i}].summary has {wc} words — exceeds {SUMMARY_WORD_FAIL} "
                f"word cap; possible copied excerpt"
            )
        if wc > SUMMARY_WORD_WARN:
            warn(f"{list_name}[{i}].summary has {wc} words — consider trimming")
        if extra_keys:
            for ek in extra_keys:
                if ek not in item:
                    fail(f"{list_name}[{i}] missing optional-but-expected key: {ek}")


def main():
    if not PATH.exists():
        fail(f"{PATH} does not exist")

    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"invalid JSON: {e}")

    # --- meta ---
    if "meta" not in data:
        fail("missing top-level 'meta' key")
    meta = data["meta"]
    missing_meta = REQUIRED_META_KEYS - set(meta.keys())
    if missing_meta:
        fail(f"meta missing required keys: {missing_meta}")

    date = meta.get("date")
    if not date or not isinstance(date, str):
        fail("meta.date is missing or not a string")

    dq = meta.get("data_quality")
    if dq not in VALID_QUALITIES:
        fail(f"meta.data_quality must be one of {VALID_QUALITIES}, got {dq!r}")

    if not isinstance(meta.get("failure_notes"), list):
        fail("meta.failure_notes must be a list")

    if dq == "limited":
        if not meta["failure_notes"]:
            fail("meta.data_quality=limited but meta.failure_notes is empty — must explain why")

    for key in ("item_count", "source_count", "failure_count"):
        if not isinstance(meta.get(key), int):
            fail(f"meta.{key} must be an integer")

    # --- top-level list keys ---
    for list_key in ("sources", "transactions", "injuries", "pitcher_notes",
                     "lineup_notes", "team_notes"):
        if list_key not in data:
            fail(f"missing top-level '{list_key}' key")
        if not isinstance(data[list_key], list):
            fail(f"'{list_key}' must be a list")

    # --- sources ---
    for i, src in enumerate(data["sources"]):
        if not isinstance(src, dict):
            fail(f"sources[{i}] is not a dict")
        missing = REQUIRED_SOURCE_KEYS - set(src.keys())
        if missing:
            fail(f"sources[{i}] missing keys: {missing}")
        status = src.get("status")
        if status not in VALID_STATUSES:
            fail(f"sources[{i}].status must be one of {VALID_STATUSES}, got {status!r}")
        for k in ("source_name", "source_url"):
            if not src.get(k):
                fail(f"sources[{i}].{k} is empty")

    # --- item lists ---
    check_items(data["transactions"], "transactions")
    check_items(data["injuries"], "injuries")
    check_items(data["pitcher_notes"], "pitcher_notes")
    check_items(data["lineup_notes"], "lineup_notes")
    check_items(data["team_notes"], "team_notes")

    # --- item_count consistency ---
    actual_count = (len(data["transactions"]) + len(data["injuries"])
                    + len(data["pitcher_notes"]) + len(data["lineup_notes"])
                    + len(data["team_notes"]))
    if meta["item_count"] != actual_count:
        fail(f"meta.item_count ({meta['item_count']}) != actual item total ({actual_count})")

    # --- summary
    total_items = actual_count
    quality_label = f"data_quality={dq}"
    if dq == "limited":
        reasons = "; ".join(meta["failure_notes"][:3])
        print(f"INFO: limited fallback — {reasons}")

    print(f"PASS: {len(data['sources'])} sources, {total_items} items, "
          f"date={date}, {quality_label}")
    print("NEWS INTAKE READY")


if __name__ == "__main__":
    main()
