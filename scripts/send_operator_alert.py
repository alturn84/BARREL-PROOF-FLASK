"""
Non-blocking operator alert helper for Barrel Proof.

Sends a phone-readable Telegram alert using environment variables only.
Designed to be called from Hermes wrappers after key pipeline checkpoints.

Never breaks the pipeline — exits 0 on all non-operator-error conditions.

Environment variables (read from environment, never from disk):
  TELEGRAM_BOT_TOKEN          — Telegram bot token
  TELEGRAM_CHAT_ID            — Telegram chat/channel ID
  BARREL_PROOF_ALERTS_ENABLED — set to 0/false/off to disable silently

Usage:
  python3 scripts/send_operator_alert.py \\
      --severity WARNING \\
      --workflow "Dope Refresh" \\
      --problem "Game count mismatch" \\
      --expected "14 games" \\
      --actual "13 records in intelligence file" \\
      --next-action "Check dope_game_intelligence.json"

Dry-run (no Telegram call, no credentials required):
  python3 scripts/send_operator_alert.py --dry-run --severity INFO --workflow "Test" --problem "Test only"
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime


TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

_DISABLED_VALUES = {"0", "false", "off"}

# Operator alerts use Eastern Time — Barrel Proof publishing operations are Eastern Time.
try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    def _et_date_str() -> str:
        return datetime.now(_ZoneInfo("America/New_York")).strftime("%Y-%m-%d ET")
except ImportError:
    from datetime import timezone as _tz, timedelta as _td  # type: ignore[assignment]
    # Fixed UTC-5 (EST) fallback; DST not handled — close enough for alert display date only.
    def _et_date_str() -> str:
        return datetime.now(_tz(_td(hours=-5))).strftime("%Y-%m-%d ET")


def build_message(args) -> str:
    today = args.date or _et_date_str()
    lines = [
        "BARREL PROOF ALERT" if args.severity != "INFO" else "BARREL PROOF OK",
        f"Severity: {args.severity}",
        f"Workflow: {args.workflow}",
        f"Date: {today}",
        "",
        f"Problem:\n{args.problem}",
    ]
    if args.expected:
        lines += ["", f"Expected:\n{args.expected}"]
    if args.actual:
        lines += ["", f"Actual:\n{args.actual}"]
    if args.likely_cause:
        lines += ["", f"Likely cause:\n{args.likely_cause}"]
    if args.next_action:
        lines += ["", f"Next action:\n{args.next_action}"]
    if args.log_file:
        lines += ["", f"Log/file:\n{args.log_file}"]
    if args.notes:
        lines += ["", f"Notes:\n{args.notes}"]
    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    url = TELEGRAM_API.format(token=token)
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("ok", False)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        # Redact token from any error output
        print(f"ALERT DELIVERY FAILED: HTTP {e.code} — {body[:200]}")
        return False
    except Exception as e:
        print(f"ALERT DELIVERY FAILED: {type(e).__name__}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Send a non-blocking operator alert via Telegram."
    )
    parser.add_argument("--severity", required=True, choices=["INFO", "WARNING", "CRITICAL"])
    parser.add_argument("--workflow", required=True, help="Workflow name, e.g. 'Morning Update'")
    parser.add_argument("--problem", required=True, help="Short description of the problem")
    parser.add_argument("--expected", default="", help="Expected state")
    parser.add_argument("--actual", default="", help="Actual state observed")
    parser.add_argument("--likely-cause", dest="likely_cause", default="", help="Likely root cause")
    parser.add_argument("--next-action", dest="next_action", default="", help="Recommended next action")
    parser.add_argument("--log-file", dest="log_file", default="", help="Relevant log or file path")
    parser.add_argument("--date", default="", help="Date string YYYY-MM-DD (defaults to today)")
    parser.add_argument("--notes", default="", help="Optional extra notes")
    parser.add_argument("--dry-run", action="store_true", help="Print message only; do not call Telegram")

    args = parser.parse_args()

    # Check if alerts are explicitly disabled
    enabled_flag = os.environ.get("BARREL_PROOF_ALERTS_ENABLED", "").strip().lower()
    if enabled_flag in _DISABLED_VALUES:
        print("ALERTS: disabled via BARREL_PROOF_ALERTS_ENABLED — skipping.")
        sys.exit(0)

    message = build_message(args)

    if args.dry_run:
        print("--- DRY RUN: alert message (no Telegram call) ---")
        print(message)
        print("--- END DRY RUN ---")
        sys.exit(0)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        print("ALERTS: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping alert.")
        sys.exit(0)

    ok = send_telegram(token, chat_id, message)
    if ok:
        print(f"ALERT SENT: [{args.severity}] {args.workflow} — {args.problem[:60]}")
    # Failures already printed inside send_telegram; always exit 0
    sys.exit(0)


if __name__ == "__main__":
    main()
