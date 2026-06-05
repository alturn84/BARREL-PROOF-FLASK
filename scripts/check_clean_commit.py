#!/usr/bin/env python3
"""
check_clean_commit.py — Barrel Proof Baseball
──────────────────────────────────────────────
Checks whether any cron-generated Site Data files are staged for commit.
Use before git commit to catch accidental data file staging.

Usage:
    python3 scripts/check_clean_commit.py
    python3 scripts/check_clean_commit.py --allow-site-data

Exit codes:
    0  — safe to commit
    1  — blocked: generated data files are staged
"""

import subprocess
import sys
from pathlib import Path

# Files that should never be committed locally (cron owns them)
BLOCKED_PREFIXES = ["Site Data/"]
BLOCKED_EXCEPTIONS = [
    "Site Data/teams.json",       # manually maintained schema
    "Site Data/archive/",         # intentional historical snapshots
]

def is_blocked(path: str) -> bool:
    """Return True if the path is a cron-generated file that should not be staged."""
    for exc in BLOCKED_EXCEPTIONS:
        if path == exc or path.startswith(exc):
            return False
    for prefix in BLOCKED_PREFIXES:
        if path.startswith(prefix):
            return True
    return False

def find_repo_root() -> Path:
    """Walk up from script location to find the git repo root."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("No git repository found in parent directories.")

def main():
    allow = "--allow-site-data" in sys.argv

    if allow:
        print("SAFE: Site Data changes explicitly allowed")
        sys.exit(0)

    repo_root = find_repo_root()

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: git diff failed: {result.stderr.strip()}")
        sys.exit(1)

    staged = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    blocked = [f for f in staged if is_blocked(f)]

    if blocked:
        print("BLOCKED: staged generated data files detected")
        print()
        for f in blocked:
            print(f"  {f}")
        print()
        print("These files are cron-owned and should not be committed locally.")
        print("To unstage them:")
        for f in blocked:
            print(f'  git restore --staged "{f}"')
        print()
        print("To commit anyway (e.g. manual edition recovery):")
        print("  python3 scripts/check_clean_commit.py --allow-site-data")
        sys.exit(1)

    print("SAFE: no generated data files staged")
    sys.exit(0)

if __name__ == "__main__":
    main()
