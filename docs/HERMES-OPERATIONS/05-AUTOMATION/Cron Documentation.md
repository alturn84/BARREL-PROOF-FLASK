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

This is a focused refresh only — it does not run the full morning pipeline (no MLB fetch, standings, odds, player stats, content generation, etc.).

> **Server wrapper note:** The active Hostinger cron wrapper (`/opt/data/scripts/run_dope_sheet_refresh.sh`, outside this repo) must be kept in sync with `run_dope_sheet_refresh_with_venv.sh`. If/when that external wrapper is updated, it must also run `scripts/update_dope_pitcher_matchups.py` followed by `scripts/check_dope_pitcher_matchups_ready.py` immediately after `scripts/check_dope_player_matchups_ready.py`. This repo cannot modify that external wrapper directly — confirm with Hermes/Hostinger automation that it has been updated to match.

---

## Failure Handling

See `03-RUNBOOKS/Cron Failure Recovery.md` for step-by-step recovery procedures.

Escalate to Allan Turner if either job cannot be recovered by the following thresholds:
- Cron Job 1: unresolved by 6:10 AM ET
- Cron Job 2: unresolved by 6:25 AM ET
