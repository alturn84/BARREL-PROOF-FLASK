#!/usr/bin/env python3
"""
MLB Box Score Fetcher — Barrel Proof Vault
───────────────────────────────────────────
Pulls complete box scores with BR-style stats from the free MLB Stats API.

Usage:
    python mlb_fetch.py                         # yesterday's games
    python mlb_fetch.py 2026-05-22              # one specific date
    python mlb_fetch.py 2026-03-29 2026-05-17   # full date range
    python mlb_fetch.py 2026-03-29 2026-05-17 --overwrite

Schedule with cron (8 AM daily):
    0 8 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 "/Users/allanturner/Documents/BARREL PROOF/mlb_fetch.py"
"""

import pandas as pd
import requests
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

print(f"SCRIPT STARTED: {datetime.now()}", flush=True)

VAULT      = Path(".")
OUTPUT_DIR = VAULT / "Daily"
BASE_URL   = "https://statsapi.mlb.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.mlb.com",
    "Referer": "https://www.mlb.com/",
}

def get(endpoint, params=None):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2: raise
            time.sleep(2 ** attempt)


# ── Season stats ──────────────────────────────────────────────────────────────
def fetch_season_stats(player_ids, season):
    if not player_ids: return {}
    ids_str = ",".join(str(pid) for pid in player_ids)
    try:
        data = get("/api/v1/people", params={
            "personIds": ids_str,
            "hydrate": f"stats(group=[hitting,pitching],type=season,season={season})",
        })
    except Exception:
        return {}

    result = {}
    for person in data.get("people", []):
        pid = person["id"]
        for sg in person.get("stats", []):
            splits = sg.get("splits", [])
            if not splits: continue
            s     = splits[0].get("stat", {})
            group = sg.get("group", {}).get("displayName", "")
            if group == "hitting":
                result.setdefault(pid, {}).update({
                    "avg":  s.get("avg",  ".---"),
                    "obp":  s.get("obp",  ".---"),
                    "slg":  s.get("slg",  ".---"),
                    "ops":  s.get("ops",  ".---"),
                })
            elif group == "pitching":
                result.setdefault(pid, {}).update({
                    "era":  s.get("era",  ""),
                    "whip": s.get("whip", ""),
                })
    return result

# ── Linescore ─────────────────────────────────────────────────────────────────
def fmt_inn(val):
    if val is None: return " "
    if str(val) == "X": return "—"
    return str(val)

def linescore_table(innings, away_abbr, home_abbr, totals):
    num_inn = max(9, len(innings))
    cols    = [str(i + 1) for i in range(num_inn)]
    header  = "| Team | " + " | ".join(cols) + " | R | H | E |"
    sep     = "|------|" + "|".join(["---"] * num_inn) + "|---|---|---|"

    def row(abbr, key, tk):
        vals = []
        for i in range(num_inn):
            if i < len(innings):
                v = innings[i].get(key, {}).get("runs")
                vals.append(fmt_inn(v))
            else:
                vals.append(" ")
        t = totals[tk]
        return (
            f"| **{abbr}** | "
            + " | ".join(vals)
            + f" | **{t.get('runs', 0)}** | {t.get('hits', 0)} | {t.get('errors', 0)} |"
        )

    return "\n".join([header, sep, row(away_abbr, "away", "away"), row(home_abbr, "home", "home")])


# ── Batting table (BR-style) ──────────────────────────────────────────────────
def batting_table(players, team_abbr, season_stats):
    rows = []
    hr_notes = []
    double_notes = []
    triple_notes = []
    sb_notes = []
    cs_notes = []
    hbp_notes = []

    for pid_str, p in players.items():
        s = p.get("stats", {}).get("batting", {})
        if not s: continue
        ab  = s.get("atBats", 0)
        bb  = s.get("baseOnBalls", 0)
        hbp = s.get("hitByPitch", 0)
        sf  = s.get("sacFlies", 0)
        sh  = s.get("sacBunts", 0)
        pa  = ab + bb + hbp + sf + sh
        if pa == 0: continue

        pid   = p["person"]["id"]
        name  = p["person"]["fullName"]
        pos   = p.get("allPositions", [{}])[0].get("abbreviation", "")
        h     = s.get("hits", 0)
        r     = s.get("runs", 0)
        d     = s.get("doubles", 0)
        t     = s.get("triples", 0)
        hr    = s.get("homeRuns", 0)
        rbi   = s.get("rbi", 0)
        so    = s.get("strikeOuts", 0)
        sb    = s.get("stolenBases", 0)
        cs    = s.get("caughtStealing", 0)
        gidp  = s.get("groundIntoDoublePlay", 0)
        avg   = season_stats.get(pid, {}).get("avg",  ".---")
        obp   = season_stats.get(pid, {}).get("obp",  ".---")
        slg   = season_stats.get(pid, {}).get("slg",  ".---")
        ops   = season_stats.get(pid, {}).get("ops",  ".---")
        order = p.get("battingOrder", "9990")
        try: order_num = int(str(order))
        except: order_num = 9990

        # Collect play notes
        if hr:   hr_notes.append(f"{name} ({hr} HR)")
        if d:    double_notes.append(f"{name} ({d})")
        if t:    triple_notes.append(f"{name} ({t})")
        if sb:   sb_notes.append(f"{name} ({sb})")
        if cs:   cs_notes.append(f"{name} ({cs})")
        if hbp:  hbp_notes.append(name)

        rows.append((order_num, f"| {name} ({pos}) | {pa} | {ab} | {r} | {h} | {d} | {t} | {hr} | {rbi} | {bb} | {so} | {avg} | {obp} | {slg} | {ops} |"))

    if not rows:
        return f"*No batting data for {team_abbr}*\n", ""

    rows.sort(key=lambda x: x[0])
    header = (
        f"**{team_abbr} Batting**\n\n"
        "| Batter | PA | AB | R | H | 2B | 3B | HR | RBI | BB | SO | AVG | OBP | SLG | OPS |\n"
        "|--------|----|----|---|---|----|----|----|----|----|----|-----|-----|-----|-----|"
    )
    table = header + "\n" + "\n".join(r[1] for r in rows) + "\n"

    # Build notes
    notes_parts = []
    if hr_notes:     notes_parts.append("**HR:** " + ", ".join(hr_notes))
    if double_notes: notes_parts.append("**2B:** " + ", ".join(double_notes))
    if triple_notes: notes_parts.append("**3B:** " + ", ".join(triple_notes))
    if sb_notes:     notes_parts.append("**SB:** " + ", ".join(sb_notes))
    if cs_notes:     notes_parts.append("**CS:** " + ", ".join(cs_notes))
    if hbp_notes:    notes_parts.append("**HBP:** " + ", ".join(hbp_notes))
    notes = "  ".join(notes_parts) if notes_parts else ""

    return table, notes


# ── Pitching table (BR-style) ─────────────────────────────────────────────────
def pitching_table(players, team_abbr, season_stats):
    rows = []
    wp_notes = []
    hbp_notes = []
    balk_notes = []

    for pid_str, p in players.items():
        s = p.get("stats", {}).get("pitching", {})
        if not s: continue
        ip_raw = s.get("inningsPitched", "0")
        try: ip_val = float(ip_raw.replace(".1",".33").replace(".2",".67"))
        except: ip_val = 0.0
        if ip_val == 0: continue

        pid  = p["person"]["id"]
        name = p["person"]["fullName"]
        ip   = s.get("inningsPitched", "0.0")
        h    = s.get("hits", 0)
        r    = s.get("runs", 0)
        er   = s.get("earnedRuns", 0)
        bb   = s.get("baseOnBalls", 0)
        k    = s.get("strikeOuts", 0)
        hr   = s.get("homeRuns", 0)
        bf   = s.get("battersFaced", "")
        pc   = s.get("pitchesThrown", "")
        st   = s.get("strikes", "")
        wp   = s.get("wildPitches", 0)
        hbp  = s.get("hitByPitch", 0)
        blk  = s.get("balks", 0)
        era  = season_stats.get(pid, {}).get("era",  "")
        whip = season_stats.get(pid, {}).get("whip", "")
        pc_st = f"{pc}-{st}" if pc and st else (str(pc) if pc else "—")

        if wp:  wp_notes.append(name)
        if hbp: hbp_notes.append(name)
        if blk: balk_notes.append(name)

        rows.append((ip_val, f"| {name} | {ip} | {h} | {r} | {er} | {bb} | {k} | {hr} | {bf} | {pc_st} | {era} | {whip} |"))

    if not rows:
        return f"*No pitching data for {team_abbr}*\n", ""

    rows.sort(key=lambda x: x[0], reverse=True)
    header = (
        f"**{team_abbr} Pitching**\n\n"
        "| Pitcher | IP | H | R | ER | BB | K | HR | BF | P-S | ERA | WHIP |\n"
        "|---------|----|----|----|----|----|----|----|----|-----|-----|------|"
    )
    table = header + "\n" + "\n".join(r[1] for r in rows) + "\n"

    notes_parts = []
    if wp_notes:   notes_parts.append("**WP:** " + ", ".join(wp_notes))
    if hbp_notes:  notes_parts.append("**HBP:** " + ", ".join(hbp_notes))
    if balk_notes: notes_parts.append("**Balk:** " + ", ".join(balk_notes))
    notes = "  ".join(notes_parts) if notes_parts else ""

    return table, notes


# ── Game markdown ─────────────────────────────────────────────────────────────
def game_markdown(game_pk, away_abbr, home_abbr, season):
    data = get(f"/api/v1.1/game/{game_pk}/feed/live")
    ls   = data["liveData"]["linescore"]
    bs   = data["liveData"]["boxscore"]
    gd   = data.get("gameData", {})

    innings = ls.get("innings", [])             
    totals  = {"away": ls["teams"]["away"], "home": ls["teams"]["home"]}

    a_runs = totals["away"].get("runs", 0)
    h_runs = totals["home"].get("runs", 0)

    score_line = (
        f"**{away_abbr} {a_runs}**, {home_abbr} {h_runs}"
        if a_runs > h_runs else
        f"{away_abbr} {a_runs}, **{home_abbr} {h_runs}**"
    )

    # Decisions
    decisions = data["liveData"].get("decisions", {})
    dec_parts = []
    if "winner" in decisions: dec_parts.append(f"W: {decisions['winner']['fullName']}")
    if "loser"  in decisions: dec_parts.append(f"L: {decisions['loser']['fullName']}")
    if "save"   in decisions: dec_parts.append(f"SV: {decisions['save']['fullName']}")
    dec_line = " · ".join(dec_parts) if dec_parts else "—"

    # Venue
    venue = gd.get("venue", {}).get("name", "")

    # Team records
    away_rec = gd.get("teams", {}).get("away", {}).get("record", {})
    home_rec = gd.get("teams", {}).get("home", {}).get("record", {})
    away_wins = away_rec.get("wins", "")
    away_loss = away_rec.get("losses", "")
    home_wins = home_rec.get("wins", "")
    home_loss = home_rec.get("losses", "")
    away_record = f"{away_wins}-{away_loss}" if away_wins != "" else ""
    home_record = f"{home_wins}-{home_loss}" if home_wins != "" else ""

    # Attendance & duration
    game_info   = gd.get("gameInfo", {})
    attendance  = game_info.get("attendance", "")
    duration    = game_info.get("gameDurationMinutes", "")
    dur_fmt     = f"{duration//60}:{duration%60:02d}" if isinstance(duration, int) else str(duration)

    # Weather
    weather = gd.get("weather", {})
    temp    = weather.get("temp", "")
    wind    = weather.get("wind", "")
    cond    = weather.get("condition", "")
    weather_line = ", ".join(filter(None, [
        f"{temp}°F" if temp else "",
        f"Wind {wind}" if wind else "",
        cond
    ]))

    # Umpires
    officials = gd.get("officials", [])
    ump_parts = []
    for o in officials:
        role    = o.get("officialType", "")
        ump_name = o.get("official", {}).get("fullName", "")
        if role and ump_name:
            ump_parts.append(f"{role}: {ump_name}")
    umpires_line = " · ".join(ump_parts) if ump_parts else ""

    # Datetime
    game_date_str = gd.get("datetime", {}).get("originalDate", "")
    start_time    = gd.get("datetime", {}).get("time", "")
    ampm          = gd.get("datetime", {}).get("ampm", "")
    start_fmt     = f"{start_time} {ampm}".strip() if start_time else ""
    day_night     = gd.get("datetime", {}).get("dayNight", "").capitalize()

    # Team LOB
    away_lob = bs["teams"]["away"].get("teamStats", {}).get("batting", {}).get("leftOnBase", "")
    home_lob = bs["teams"]["home"].get("teamStats", {}).get("batting", {}).get("leftOnBase", "")

    # Players
    ap = bs["teams"]["away"]["players"]
    hp = bs["teams"]["home"]["players"]

    all_pids = [p["person"]["id"] for p in list(ap.values()) + list(hp.values())]
    season_stats = fetch_season_stats(all_pids, season)

    ls_table           = linescore_table(innings, away_abbr, home_abbr, totals)
    away_bat, away_bat_notes = batting_table(ap, away_abbr, season_stats)
    home_bat, home_bat_notes = batting_table(hp, home_abbr, season_stats)
    away_pit, away_pit_notes = pitching_table(ap, away_abbr, season_stats)
    home_pit, home_pit_notes = pitching_table(hp, home_abbr, season_stats)

    game_num = gd.get("game", {}).get("gameNumber", 1)
    dh_note  = " (Game 2)" if game_num == 2 else ""

    # Build info block
    info_parts = []
    if venue:        info_parts.append(f"**Venue:** {venue}")
    if start_fmt:    info_parts.append(f"**Start:** {start_fmt} {day_night}".strip())
    if attendance:   info_parts.append(f"**Attendance:** {attendance:,}" if isinstance(attendance, int) else f"**Attendance:** {attendance}")
    if dur_fmt:      info_parts.append(f"**Duration:** {dur_fmt}")
    if weather_line: info_parts.append(f"**Weather:** {weather_line}")
    info_line = "  ·  ".join(info_parts)

    # LOB notes
    lob_parts = []
    if away_lob != "": lob_parts.append(f"{away_abbr}: {away_lob}")
    if home_lob != "": lob_parts.append(f"{home_abbr}: {home_lob}")
    lob_line  = "**LOB:** " + ", ".join(lob_parts) if lob_parts else ""

    # Build batting notes blocks
    def notes_block(bat_notes, lob, pit_notes):
        parts = [x for x in [bat_notes, lob, pit_notes] if x]
        return "\n".join(parts) if parts else ""

    away_notes = notes_block(away_bat_notes, lob_line if lob_parts else "", away_pit_notes)
    home_notes = notes_block(home_bat_notes, "", home_pit_notes)

    ump_str = f"\n**Umpires:** {umpires_line}" if umpires_line else ""

    return f"""### {away_abbr} @ {home_abbr}{dh_note} — {score_line}

{info_line}

**Decisions:** {dec_line}

{ls_table}

#### Batting

{away_bat}
{away_bat_notes}

{home_bat}
{home_bat_notes}

{lob_line}

#### Pitching

{away_pit}
{away_pit_notes}

{home_pit}
{home_pit_notes}
{ump_str}

---
"""


# ── Fetch one game ────────────────────────────────────────────────────────────
def fetch_game(g, season):
    away = g["teams"]["away"]["team"]["abbreviation"]
    home = g["teams"]["home"]["team"]["abbreviation"]
    pk   = g["gamePk"]
    try:
        md = game_markdown(pk, away, home, season)
        return (pk, away, home, md, None)
    except Exception as e:
        return (pk, away, home, f"### {away} @ {home}\n\n*Data unavailable: {e}*\n\n---\n", str(e))

# ── Run one date ──────────────────────────────────────────────────────────────
def run_date(date_str, overwrite=False):
    out_path = OUTPUT_DIR / f"{date_str}-mlb-box-scores.md"
    if out_path.exists() and not overwrite:
        print(f"  {date_str}  — already exists (use --overwrite to replace)")
        return date_str, -1, []

    dt     = datetime.strptime(date_str, "%Y-%m-%d")
    season = dt.year

    schedule = get("/api/v1/schedule", params={
        "sportId":  1, "date": date_str,
        "gameType": "R,F,D,L,W", "hydrate": "team",
    })
    dates    = schedule.get("dates", [])
    if not dates: return date_str, 0, []
    games    = dates[0]["games"]
    finished = [g for g in games if g["status"]["abstractGameState"] == "Final"]
    if not finished: return date_str, 0, []

    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_game, g, season): g for g in finished}
        for f in as_completed(futs):
            results.append(f.result())
    results.sort(key=lambda x: x[0])

    date_display = dt.strftime("%A, %B %-d, %Y")
    blocks  = [r[3] for r in results]
    errors  = [(r[1], r[2], r[4]) for r in results if r[4]]
    content = (
        f"---\ndate: {date_str}\ntags: [baseball, mlb, box-scores]\n---\n\n"
        f"# MLB Box Scores — {date_display}\n\n"
        f"*{len(finished)} game(s) · MLB Stats API · statsapi.mlb.com*\n\n"
    ) + "\n".join(blocks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return date_str, len(finished), errors

# ── Main ──────────────────────────────────────────────────────────────────────
def parse_args():
    args      = sys.argv[1:]
    overwrite = "--overwrite" in args
    args      = [a for a in args if a != "--overwrite"]
    if len(args) == 0:
        d = datetime.today() - timedelta(days=1)
        return [d.strftime("%Y-%m-%d")], overwrite
    elif len(args) == 1:
        return [args[0]], overwrite
    elif len(args) == 2:
        start = datetime.strptime(args[0], "%Y-%m-%d")
        end   = datetime.strptime(args[1], "%Y-%m-%d")
        dates, d = [], start
        while d <= end:
            dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        return dates, overwrite
    else:
        print("Usage: python mlb_fetch.py [start_date [end_date]] [--overwrite]")
        sys.exit(1)

if __name__ == "__main__":
    dates, overwrite = parse_args()
    if len(dates) > 1:
        print(f"Fetching {len(dates)} dates: {dates[0]} → {dates[-1]}")
    else:
        print(f"Fetching MLB box scores for {dates[0]}...")

    total_days = total_games = 0
    all_errors = []
    for date_str in dates:
        try:
            ds, count, errs = run_date(date_str, overwrite=overwrite)
            if count == -1: pass
            elif count == 0: print(f"  {ds}  — no final games")
            else:
                err_note = f"  ⚠ {len(errs)} error(s)" if errs else ""
                print(f"  {ds}  — {count} game(s) ✓{err_note}")
                total_days += 1; total_games += count
                all_errors.extend(errs)
        except Exception as e:
            print(f"  {date_str}  — FAILED: {e}")
            all_errors.append(("—", "—", str(e)))

    print(f"\n✓  Done. {total_days} game day(s), {total_games} game(s) total.")
    print(f"   Files saved → {OUTPUT_DIR}")
    if all_errors:
        print(f"\n⚠  {len(all_errors)} game(s) had errors:")
        for away, home, err in all_errors:
            print(f"   {away} @ {home}: {err}")
