"""
check_live_site_smoke.py — Barrel Proof Baseball
─────────────────────────────────────────────────
Lightweight live-site smoke check after Render deploys.

Checks that key public routes return HTTP 200 and contain expected content
markers. Does not call Telegram or trigger any external actions — prints
results only.

Default base URL: https://barrel-proof-baseball.com
Override via --base-url or BARREL_PROOF_SITE_URL env var.

Exit codes:
  0  — PASS or WARN (no critical failures)
  1  — FAIL (at least one critical route failed)
  0  — always, when --soft-fail is set

Usage:
  python3 scripts/check_live_site_smoke.py
  python3 scripts/check_live_site_smoke.py --base-url https://barrel-proof-baseball.com
  python3 scripts/check_live_site_smoke.py --timeout 20 --retries 3
  python3 scripts/check_live_site_smoke.py --json
  python3 scripts/check_live_site_smoke.py --soft-fail
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://barrel-proof-baseball.com"
DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 2


# ---------------------------------------------------------------------------
# Route definitions
# ---------------------------------------------------------------------------

CRITICAL_ROUTES = [
    {
        "name": "Homepage",
        "path": "/",
        "required_markers": ["Page 1", "Game of the Day", "Around the League", "Barrel Proof"],
        "required_any": True,  # any one of required_markers is sufficient
        "warn_markers": [],
    },
    {
        "name": "Dope Sheet",
        "path": "/dope-sheet",
        "required_markers": ["Dope Sheet", "The Dope Sheet"],
        "required_any": True,
        "warn_markers": [
            "Game Intelligence",
            "Pitcher Arsenal",
            "Player Matchup",
            "Lineup Matchup",
            "Arsenal Board",
        ],
    },
    {
        "name": "Scoreboard",
        "path": "/scoreboard",
        "required_markers": ["Scoreboard", "Today's Board", "Final"],
        "required_any": True,
        "warn_markers": [],
    },
    {
        "name": "Advanced Scout",
        "path": "/advance-scout",
        "required_markers": ["Advanced Scout", "Series", "Scout"],
        "required_any": True,
        "warn_markers": [],
    },
]

OPTIONAL_ROUTES = [
    {"name": "Archive", "path": "/archive"},
    {"name": "Players", "path": "/players"},
    {"name": "Teams", "path": "/teams"},
]


# ---------------------------------------------------------------------------
# HTTP fetch with retry
# ---------------------------------------------------------------------------

def fetch(url: str, timeout: int, retries: int) -> tuple[int, str]:
    """Return (status_code, body_text). Raises on unrecoverable network error."""
    last_exc = None
    for attempt in range(retries + 1):
        if attempt > 0:
            time.sleep(2)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BarrelProofSmokeCheck/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception as e:
            last_exc = e
    raise last_exc


# ---------------------------------------------------------------------------
# Check runners
# ---------------------------------------------------------------------------

def check_critical(route: dict, base_url: str, timeout: int, retries: int) -> dict:
    url = base_url.rstrip("/") + route["path"]
    result = {
        "name": route["name"],
        "path": route["path"],
        "url": url,
        "status": None,
        "level": None,       # OK / WARN / FAIL
        "messages": [],
    }

    try:
        code, body = fetch(url, timeout, retries)
    except Exception as e:
        result["level"] = "FAIL"
        result["messages"].append(f"Request failed: {type(e).__name__}: {e}")
        return result

    result["status"] = code

    if code != 200:
        result["level"] = "FAIL"
        result["messages"].append(f"HTTP {code} (expected 200)")
        return result

    # Check required markers
    matched_required = [m for m in route["required_markers"] if m in body]
    if route["required_any"] and not matched_required:
        result["level"] = "FAIL"
        result["messages"].append(
            f"None of required markers found: {route['required_markers']}"
        )
        return result

    # Check warn markers for Dope Sheet
    if route["warn_markers"]:
        matched_warn = [m for m in route["warn_markers"] if m in body]
        if not matched_warn:
            result["level"] = "WARN"
            result["messages"].append(
                f"Page loaded but none of expected section markers found: {route['warn_markers']}"
            )
            return result

    result["level"] = "OK"
    if matched_required:
        result["messages"].append(f"Marker found: {matched_required[0]!r}")
    return result


def check_optional(route: dict, base_url: str, timeout: int, retries: int) -> dict:
    url = base_url.rstrip("/") + route["path"]
    result = {
        "name": route["name"],
        "path": route["path"],
        "url": url,
        "status": None,
        "level": None,
        "messages": [],
    }

    try:
        code, _ = fetch(url, timeout, retries)
    except Exception as e:
        result["level"] = "WARN"
        result["messages"].append(f"Request failed: {type(e).__name__}: {e}")
        return result

    result["status"] = code

    if code == 500:
        result["level"] = "FAIL"
        result["messages"].append("HTTP 500 — server error")
    elif code != 200:
        result["level"] = "WARN"
        result["messages"].append(f"HTTP {code}")
    else:
        result["level"] = "OK"
        result["messages"].append("HTTP 200")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Barrel Proof live-site smoke check.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BARREL_PROOF_SITE_URL", DEFAULT_BASE_URL),
        help=f"Base URL to check (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Retry count on network failure")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Print JSON summary to stdout")
    parser.add_argument("--soft-fail", action="store_true", help="Always exit 0 even on critical failure")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    results = []
    critical_failures = 0
    warnings = 0

    # Run critical checks
    for route in CRITICAL_ROUTES:
        r = check_critical(route, base_url, args.timeout, args.retries)
        results.append({"critical": True, **r})
        msg = f"{r['level']}: [{r['name']}] {r['path']}"
        if r["messages"]:
            msg += f" — {r['messages'][0]}"
        print(msg)
        if r["level"] == "FAIL":
            critical_failures += 1
        elif r["level"] == "WARN":
            warnings += 1

    # Run optional checks
    for route in OPTIONAL_ROUTES:
        r = check_optional(route, base_url, args.timeout, args.retries)
        results.append({"critical": False, **r})
        msg = f"{r['level']}: [{r['name']}] {r['path']}"
        if r["messages"]:
            msg += f" — {r['messages'][0]}"
        print(msg)
        if r["level"] == "FAIL":
            critical_failures += 1
        elif r["level"] == "WARN":
            warnings += 1

    # Summary
    if critical_failures > 0:
        overall = "FAIL"
    elif warnings > 0:
        overall = "WARN"
    else:
        overall = "PASS"

    summary = {
        "result": overall,
        "base_url": base_url,
        "critical_failures": critical_failures,
        "warnings": warnings,
        "checks": results,
    }

    print()
    print("LIVE SITE SMOKE CHECK")
    print(f"Base URL: {base_url}")
    print(f"Critical failures: {critical_failures}")
    print(f"Warnings: {warnings}")
    print(f"Result: {overall}")

    if args.json_output:
        print()
        print(json.dumps(summary, indent=2))

    if args.soft_fail:
        sys.exit(0)

    sys.exit(1 if critical_failures > 0 else 0)


if __name__ == "__main__":
    main()
