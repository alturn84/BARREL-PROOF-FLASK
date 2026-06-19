# Cron Documentation
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** Barrel Proof scheduled automation jobs

---

## Active Cron Jobs

### Cron Job 1 — Data Pipeline

| Field | Value |
|-------|-------|
| ID | `98de609020e4` |
| Schedule | 6:00 AM ET daily |
| Purpose | MLB data collection, game card generation, data updates |
| Workspace | `/workspace/barrel-proof` |
| Status | Active |

**Responsibilities:**
- Fetch MLB data from data API for today's games
- Parse and validate raw API responses
- Generate game cards for today's scheduled games
- Run data update scripts for standings, stats, schedules
- Output validated JSON files for Cron Job 2 consumption
- Log completion timestamp and file manifest

**Expected outputs:**
- Game data JSON files (one per game or consolidated)
- Standings JSON
- Schedule JSON for today
- Player stats JSON (as applicable)

**Success condition:** All expected JSON files present, validated, no errors in log.

---

### Cron Job 2 — Content Generation

| Field | Value |
|-------|-------|
| ID | `e1af79acae93` |
| Schedule | 6:15 AM ET daily |
| Purpose | AI content generation via Gemini API |
| Workspace | `/workspace/barrel-proof` |
| Depends On | Cron Job 1 output |
| Status | Active |

**Responsibilities:**
- Read all Cron Job 1 output files
- Send data to Gemini API with appropriate prompts (see `02-PROMPTS/`)
- Generate: game summaries, Press Box, Around the League, Game of the Day, Game to Watch, Advanced Scout
- Validate all generated content
- Write content output to appropriate directories
- Log completion timestamp and content manifest

**Expected outputs:**
- Game summary files
- Press Box content
- Around the League content
- Game of the Day copy
- Game to Watch copy
- Advanced Scout preview (when applicable)

**Success condition:** All content types generated, validated, no null fields, no placeholder text.

---

## Cron Job Sequencing Rules

1. Cron Job 2 must not execute before Cron Job 1 has completed successfully
2. If Cron Job 1 is delayed, Cron Job 2 should wait for confirmed output availability
3. Both jobs must complete by 6:30 AM ET hard deadline
4. Recovery attempts for Cron Job 1 must not push Cron Job 2 start past 6:20 AM ET without Allan notification

---

## Monitoring

Daily verification of both cron jobs is required per `01-SOPs/Daily Verification SOP.md`.

Check after each scheduled run:
- Exit code of each job
- Presence and validity of output files
- Log timestamp confirms completion
- No error messages in job logs

---

## Recommended Additional Cron Job — Dope Sheet Afternoon Refresh (DOPE-PLAYER-001H, not yet active)

| Field | Value |
|-------|-------|
| Purpose | Refresh `Site Data/dope-sheet-data.json` and `Site Data/dope_player_matchups.json` after MLB lineups are typically posted |
| Reason | The 6:00 AM ET morning run is too early — most MLB lineups have not posted yet, so projected/confirmed lineups and confirmed-lineup-filtered Matchup Intelligence cannot populate |
| Script | `/opt/data/workspace/barrel-proof/run_dope_sheet_refresh_with_venv.sh` |
| Recommended command | `/bin/bash /opt/data/workspace/barrel-proof/run_dope_sheet_refresh_with_venv.sh` |
| Recommended schedule | 3:30 PM ET daily (primary); optional second run at 5:30 PM ET |
| Status | Not active — script exists in repo, but the cron entry itself must be installed by Hermes/Hostinger automation outside this repo |

**Steps run by this script (in order):**
1. `update_dope_sheet.py` — refreshes Dope Sheet game cards, including lineups
2. `update_odds.py` — if already part of the server wrapper, refreshes odds before matchup regeneration
3. `scripts/update_dope_player_matchups.py` — regenerates Matchup Intelligence from the refreshed Dope Sheet data
4. `scripts/check_dope_player_matchups_ready.py` — validates the regenerated player matchup file
5. `scripts/update_dope_pitcher_matchups.py` — regenerates Pitcher Matchup Intelligence (Starter Edge, Lineup Pressure, Fantasy/DFS Watch) from the refreshed Dope Sheet and lineup data
6. `scripts/check_dope_pitcher_matchups_ready.py` — validates the regenerated pitcher matchup file
7. `scripts/update_pitch_type_intelligence.py` — pulls 2026 Statcast pitch-by-pitch data for probable starters and key lineup hitters; generates pitch arsenal profiles (pitch family mix, usage, whiff rate, primary shape) and hitter pitch-family splits (damage/contact/risk by Fastball/Breaking/Offspeed family); outputs `Site Data/pitch_type_intelligence.json`
8. `scripts/check_pitch_type_intelligence_ready.py` — validates the pitch type intelligence file
9. `scripts/update_dope_game_intelligence.py` — regenerates unified Game Intelligence (game read, lineup read, pitching path, pitch-type matchup, bullpen read, environment read, players who tilt the game, fantasy/DFS watch, betting/props watch) from the refreshed Dope Sheet, matchup, pitch-type, and odds data
10. `scripts/check_dope_game_intelligence_ready.py` — validates the regenerated game intelligence file

This is a focused refresh only — it does not run the full morning pipeline (no MLB fetch, standings, odds, player stats, content generation, etc.).

> **Server wrapper note:** The active Hostinger cron wrapper (`/opt/data/scripts/run_dope_sheet_refresh.sh`, outside this repo) must be kept in sync with `run_dope_sheet_refresh_with_venv.sh`. If/when that external wrapper is updated, it must also run `scripts/update_dope_pitcher_matchups.py` → `scripts/check_dope_pitcher_matchups_ready.py` → `scripts/update_pitch_type_intelligence.py` → `scripts/check_pitch_type_intelligence_ready.py` → `scripts/update_dope_game_intelligence.py` → `scripts/check_dope_game_intelligence_ready.py`, in that order after `scripts/check_dope_player_matchups_ready.py`. Note: `update_pitch_type_intelligence.py` pulls live Statcast data via pybaseball and may take 5–10 minutes on first run (subsequent runs benefit from pybaseball's local cache). This repo cannot modify that external wrapper directly — confirm with Hermes/Hostinger automation that it has been updated to match.

---

## Firecrawl News Intake (FIRECRAWL-001)

### Purpose

`scripts/update_news_intake.py` gathers source-backed facts from official MLB sources before editorial generation runs. It is **not a writing replacement** — it provides factual context that Press Box can optionally use when generating the morning edition.

### Environment Variable

| Variable | Purpose | Required By | Storage |
|---|---|---|---|
| `FIRECRAWL_API_KEY` | Firecrawl API authentication | `scripts/update_news_intake.py` | Server environment / `.env` |

> **Never commit this key.** It must be set in the Render dashboard (Production) or server `.env` (Hostinger). See `05-AUTOMATION/Environment Variables.md`.

### Behavior

- If `FIRECRAWL_API_KEY` is **missing**: writes a valid `limited` fallback JSON, exits 0. No morning disruption.
- If any source **fails** (network error, Firecrawl error, blocked page): logs the failure in `meta.failure_notes`, marks source `status=failed`, continues remaining sources, exits 0.
- If **all sources fail**: writes valid `limited` fallback, exits 0.
- **Never fatal** to the morning update.

### Sources attempted (V1)

1. **MLB Stats API Transactions** — direct REST call (`https://statsapi.mlb.com/api/v1/transactions`), no Firecrawl needed. Fetches today's significant transactions (trades, IL placements, call-ups, DFAs).
2. **MLB.com Probable Pitchers** — Firecrawl scrape of `https://www.mlb.com/probable-pitchers`. Requires API key.
3. **MLB.com Injuries** — Firecrawl scrape of `https://www.mlb.com/injuries`. Requires API key.

### Copyright / editorial rules

- Fact intake only. No article rewriting.
- Max 25 words per summary item. Paraphrased factual summaries preferred.
- Every item retains `source_name` + `source_url`.
- No long excerpts. No full article text.

### Output file

`Site Data/news_intake.json` — schema: `meta`, `sources`, `transactions`, `injuries`, `pitcher_notes`, `lineup_notes`, `team_notes`.

### Pipeline placement

In `run_morning_update_with_venv.sh`, news intake runs **after** game intelligence and **before** editorial generation:

```
scripts/check_dope_game_intelligence_ready.py
scripts/update_news_intake.py          ← gather facts
scripts/check_news_intake_ready.py     ← validate (passes on limited)
update_game_of_day.py                  ← editorial start
update_around_the_league.py
update_game_to_watch.py
update_press_box.py                    ← optionally reads news_intake.json
```

### Press Box integration

`update_press_box.py` optionally reads `news_intake.json`. When `data_quality` is `available` or `partial`, it appends a `NEWS INTAKE` section to the Gemini context with brief tagged facts (`[TXN]`, `[INJ]`, `[PITCHER]`). When `limited`, the section is omitted silently. Press Box does not fail if news_intake is missing or limited.

### Server wrapper note

The Hostinger cron wrapper (`/opt/data/scripts/run_morning_update.sh`, outside this repo) must be updated to include `scripts/update_news_intake.py` → `scripts/check_news_intake_ready.py` before `update_game_of_day.py`. This repo cannot modify that wrapper directly. Confirm with Hermes/Hostinger automation that it has been updated. See also `05-AUTOMATION/Render Flow.md` for Render environment variable setup.

---

## Failure Handling

See `03-RUNBOOKS/Cron Failure Recovery.md` for step-by-step recovery procedures.

For Firecrawl-specific operating rules (what it can/cannot be used for, source handling, editorial boundary): see `05-AUTOMATION/FIRECRAWL-002 - Hermes News Intake Operating Rules.md`.

For failure alert categories, message formats, and the future Telegram helper plan: see `05-AUTOMATION/ALERTS-001 - Hermes Telegram Failure Alerts.md`.

For Render deploy hook setup and live wiring: see `05-AUTOMATION/RENDER-AUTO-001 - Render Auto Deploy Setup.md` (RENDER-HOOK-003 section). Part 1, Part 2, and Dope Sheet refresh now trigger Render deploy via `/opt/data/scripts/trigger_render_deploy.sh` after each successful `git push origin main`. This helper lives outside the repo, reads `RENDER_DEPLOY_HOOK` from `/opt/data/.env`, and is non-blocking — deploy trigger failure produces a Telegram WARNING alert but does not abort the pipeline.

Escalate to Allan Turner if either job cannot be recovered by the following thresholds:
- Cron Job 1: unresolved by 6:10 AM ET
- Cron Job 2: unresolved by 6:25 AM ET
