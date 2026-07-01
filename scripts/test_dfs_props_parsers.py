"""
Unit tests for dfs_props_lib and the DFS/props parser scripts.

Uses inline sample strings — no Firecrawl credentials needed,
no production JSON files written.

Run:
    python3 scripts/test_dfs_props_parsers.py
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dfs_props_lib import (
    clean_dff_player_name,
    parse_salary,
    parse_markdown_table_rows,
    to_number,
    normalize_market,
)
from update_dfs_board import parse_dff_markdown, _looks_like_dff_player_row
from update_player_props import (
    parse_bettingpros_markdown,
    _is_page_not_found,
    _clean_bp_player_name,
)

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(label, got, expected):
    ok = got == expected
    status = PASS if ok else FAIL
    results.append((status, label, got, expected))
    if not ok:
        print(f"  {FAIL}: {label}")
        print(f"         got={got!r}")
        print(f"    expected={expected!r}")
    return ok


# ---------------------------------------------------------------------------
# clean_dff_player_name
# ---------------------------------------------------------------------------

def test_name_cleaner():
    cases = [
        (
            "![](https://dff-images.s3.amazonaws.com/logos/mlb/DET.svg)Tarik Skubal  • (L)",
            "Tarik Skubal",
        ),
        (
            "![](https://dff-images.s3.amazonaws.com/logos/mlb/NYY.svg)Cam Schlittler  • (R)",
            "Cam Schlittler",
        ),
        (
            "![](https://dff-images.s3.amazonaws.com/logos/mlb/BOS.svg)Rafael Devers • (S)",
            "Rafael Devers",
        ),
        # Jr. preserved
        (
            "![](https://dff-images.s3.amazonaws.com/logos/mlb/LAD.svg)Fernando Tatis Jr.  • (R)",
            "Fernando Tatis Jr.",
        ),
        # Hyphenated name preserved
        (
            "![](https://dff-images.s3.amazonaws.com/logos/mlb/NYM.svg)Josh Walker-Harris  • (L)",
            "Josh Walker-Harris",
        ),
        # No image prefix (plain name still cleaned of suffix)
        ("Aaron Judge  • (R)", "Aaron Judge"),
        # Extra whitespace collapsed
        ("![](url)  Shohei   Ohtani   • (L)  ", "Shohei Ohtani"),
        # Already clean — passthrough
        ("Tarik Skubal", "Tarik Skubal"),
    ]
    for raw, expected in cases:
        check(f"clean_dff_player_name", clean_dff_player_name(raw), expected)


# ---------------------------------------------------------------------------
# parse_salary
# ---------------------------------------------------------------------------

def test_salary_parser():
    cases = [
        ("$10.0k",  10000),
        ("$10.5k",  10500),
        ("$9.7k",   9700),
        ("$7.0k",   7000),
        ("$4,200",  4200),
        ("4200",    4200),
        ("$3,500",  3500),
        ("$12.5k",  12500),
        ("9700",    9700),
        ("10.0K",   10000),   # uppercase K
        (None,      None),
        ("N/A",     None),
        # Guard: "10.0" (old to_number bug output) → rejected (< 500)
        ("10.0",    None),
        # Guard: bare "10" → rejected (< 500)
        ("10",      None),
    ]
    for raw, expected in cases:
        check(f"parse_salary({raw!r})", parse_salary(raw), expected)


# ---------------------------------------------------------------------------
# DFF markdown column-position parser integration
# Confirms clean_dff_player_name and parse_salary are wired correctly.
# Uses the confirmed DFF column layout (DFF_COL_PLAYER_NAME=2, SALARY=3).
# ---------------------------------------------------------------------------

# Minimal DFF-style markdown table: 10+ columns, image prefix in col 2,
# k-format salary in col 3, numeric projection in col 8, value in col 9.
# Col 0 = rank, col 1 = position, col 2 = player, col 3 = salary,
# col 4 = ?, col 5 = team, col 6 = opp, col 7 = ?, col 8 = proj, col 9 = value.
DFF_DK_SAMPLE = (
    "| # | Pos | Player | Salary | - | Team | Opp | - | Proj | Val |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    "| 1 | SP | ![](https://dff-images.s3.amazonaws.com/logos/mlb/DET.svg)"
    "Tarik Skubal  • (L) | $10.0k | - | DET | @ NYY | - | 32.4 | 3.2 |\n"
    "| 2 | SP | ![](https://dff-images.s3.amazonaws.com/logos/mlb/NYY.svg)"
    "Cam Schlittler  • (R) | $9.7k | - | NYY | vs DET | - | 28.1 | 2.9 |\n"
    "| 3 | OF | ![](https://dff-images.s3.amazonaws.com/logos/mlb/LAD.svg)"
    "Shohei Ohtani  • (L) | $7.0k | - | LAD | vs SD | - | 14.2 | 2.0 |\n"
    "| 4 | 3B | ![](https://dff-images.s3.amazonaws.com/logos/mlb/BOS.svg)"
    "Rafael Devers • (L) | $4,200 | - | BOS | vs TOR | - | 9.5 | 2.3 |\n"
)


def test_dff_player_row_filter():
    """_looks_like_dff_player_row should accept real rows, reject short ones."""
    rows = parse_markdown_table_rows(DFF_DK_SAMPLE)
    # Header row is also parsed — filter to data rows via _looks_like_dff_player_row
    player_rows = [r for r in rows if _looks_like_dff_player_row(r)]
    check("DFF row filter: 4 player rows", len(player_rows), 4)


def test_dff_dk_parser():
    rows = parse_dff_markdown(DFF_DK_SAMPLE, "DraftKings")
    check("DFF DK: row count", len(rows), 4)

    r = rows[0]
    check("DFF DK row0: player_name clean", r["player_name"], "Tarik Skubal")
    check("DFF DK row0: salary $10.0k→10000", r["salary"], 10000)
    check("DFF DK row0: position", r["position"], "SP")
    check("DFF DK row0: team", r["team"], "DET")
    check("DFF DK row0: projection", r["projection"], 32.4)
    check("DFF DK row0: platform", r["platform"], "DraftKings")

    r1 = rows[1]
    check("DFF DK row1: salary $9.7k→9700", r1["salary"], 9700)
    check("DFF DK row1: player_name clean", r1["player_name"], "Cam Schlittler")

    r2 = rows[2]
    check("DFF DK row2: salary $7.0k→7000", r2["salary"], 7000)

    r3 = rows[3]
    check("DFF DK row3: salary $4,200→4200", r3["salary"], 4200)
    check("DFF DK row3: player_name clean", r3["player_name"], "Rafael Devers")


def test_dff_fd_parser():
    """FanDuel uses the same column layout — smaller slate is fine."""
    fd_sample = (
        "| # | Pos | Player | Salary | - | Team | Opp | - | Proj | Val |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 1 | P | ![](url)Tarik Skubal  • (L) | $10.5k | - | DET | @ NYY | - | 40.2 | 3.8 |\n"
        "| 2 | OF | ![](url)Shohei Ohtani  • (L) | $4,800 | - | LAD | @ SD | - | 15.0 | 3.1 |\n"
    )
    rows = parse_dff_markdown(fd_sample, "FanDuel")
    check("DFF FD: row count", len(rows), 2)
    check("DFF FD row0: salary $10.5k→10500", rows[0]["salary"], 10500)
    check("DFF FD row0: platform", rows[0]["platform"], "FanDuel")
    check("DFF FD row1: salary $4,800→4800", rows[1]["salary"], 4800)


# ---------------------------------------------------------------------------
# Jr. / II / III / IV suffix preservation (via clean_dff_player_name)
# ---------------------------------------------------------------------------

def test_name_suffix_preservation():
    cases = [
        ("![](url)Fernando Tatis Jr.  • (R)", "Fernando Tatis Jr."),
        ("![](url)Ken Griffey Jr.  • (L)", "Ken Griffey Jr."),
        ("![](url)Cal Ripken II  • (R)", "Cal Ripken II"),
        ("![](url)Some Player III  • (L)", "Some Player III"),
    ]
    for raw, expected in cases:
        check(f"suffix preserved: {expected}", clean_dff_player_name(raw), expected)


# ---------------------------------------------------------------------------
# _is_page_not_found (from update_player_props)
# ---------------------------------------------------------------------------

def test_page_not_found():
    check("not_found: None", _is_page_not_found(None), True)
    check("not_found: empty", _is_page_not_found(""), True)
    check("not_found: short (<500)", _is_page_not_found("hi"), True)
    check(
        "not_found: 404 text",
        _is_page_not_found(
            "Page Not Found\n\nSorry, this page doesn't exist.\n" + "x" * 600
        ),
        True,
    )
    check("not_found: real content", _is_page_not_found("x" * 600), False)


# ---------------------------------------------------------------------------
# BettingPros _clean_bp_player_name (from update_player_props)
# ---------------------------------------------------------------------------

def test_bp_name_cleaner():
    check("BP: glued 1B suffix", _clean_bp_player_name("A. Burleson1B,LF,RF,DH"), "A. Burleson")
    check("BP: glued P suffix", _clean_bp_player_name("B. WoodruffP"), "B. Woodruff")
    check("BP: clean name unchanged", _clean_bp_player_name("B. Woodruff"), "B. Woodruff")
    check("BP: Jr. not stripped", _clean_bp_player_name("F. Tatis Jr."), "F. Tatis Jr.")


# ---------------------------------------------------------------------------
# BettingPros markdown parser — Page Not Found → 0 rows
# ---------------------------------------------------------------------------

BP_NOT_FOUND = (
    "Page Not Found\n\nSorry, this page doesn't exist. Please check the URL.\n"
    + "x" * 600
)


def test_bp_not_found_returns_zero():
    rows = parse_bettingpros_markdown(BP_NOT_FOUND, "hits")
    check("BP parser: Page Not Found → 0 rows", len(rows), 0)


# ---------------------------------------------------------------------------
# BettingPros markdown parser — card-style snippet
# ---------------------------------------------------------------------------

# BettingPros card pages use abbreviated names: "B. Woodruff"
# The _NAME_RE in update_player_props expects "F. Lastname" style.
BP_CARD_SAMPLE = """\
## MLB Player Props

B. Woodruff MIL vs CHC

Over 6.5 -115
Under 6.5 -105

Best Bet: Over

A. Nola PHI @ NYM

Over 5.5 +105
Under 5.5 -125
"""


def test_bp_card_parser():
    rows = parse_bettingpros_markdown(BP_CARD_SAMPLE, "pitcher_strikeouts")
    check("BP card: at least 1 row", len(rows) >= 1, True)
    if rows:
        r = rows[0]
        check("BP card row0: market set", r.get("market"), "pitcher_strikeouts")
        check("BP card row0: best_book is null", r.get("best_book"), None)
        check("BP card row0: projection is null", r.get("projection"), None)
        check("BP card row0: edge_label is null", r.get("edge_label"), None)


# ---------------------------------------------------------------------------
# normalize_market (from dfs_props_lib)
# ---------------------------------------------------------------------------

def test_normalize_market():
    cases = [
        ("PITCHER STRIKEOUTS", "pitcher_strikeouts"),
        ("STRIKEOUTS", "pitcher_strikeouts"),
        ("pitcher_strikeouts", "pitcher_strikeouts"),  # idempotent
        ("HITS", "hits"),
        ("TOTAL BASES", "total_bases"),
        ("HOME RUNS", "home_runs"),
        ("RBIS", "rbis"),
        ("OUTS RECORDED", "outs_recorded"),
        (None, None),
        ("NONSENSE MARKET XYZ", None),
    ]
    for raw, expected in cases:
        check(f"normalize_market({raw!r})", normalize_market(raw), expected)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def main():
    suites = [
        ("DFF name cleaner", test_name_cleaner),
        ("DFF suffix preservation", test_name_suffix_preservation),
        ("Salary parser", test_salary_parser),
        ("DFF row filter", test_dff_player_row_filter),
        ("DFF DraftKings parser", test_dff_dk_parser),
        ("DFF FanDuel parser", test_dff_fd_parser),
        ("Page Not Found detection", test_page_not_found),
        ("BP position-code cleaner", test_bp_name_cleaner),
        ("BP not-found → 0 rows", test_bp_not_found_returns_zero),
        ("BP card-style parser", test_bp_card_parser),
        ("normalize_market", test_normalize_market),
    ]

    for suite_name, fn in suites:
        print(f"\n--- {suite_name} ---")
        try:
            fn()
        except Exception:
            traceback.print_exc()
            results.append((FAIL, suite_name, "exception", "no exception"))

    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    total = passed + failed

    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed:
        print("\nFailing checks:")
        for status, label, got, expected in results:
            if status == FAIL:
                print(f"  FAIL  {label}")
                print(f"        got={got!r}")
                print(f"        expected={expected!r}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
