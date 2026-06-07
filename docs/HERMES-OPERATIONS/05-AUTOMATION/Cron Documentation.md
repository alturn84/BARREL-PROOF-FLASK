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

## Failure Handling

See `03-RUNBOOKS/Cron Failure Recovery.md` for step-by-step recovery procedures.

Escalate to Allan Turner if either job cannot be recovered by the following thresholds:
- Cron Job 1: unresolved by 6:10 AM ET
- Cron Job 2: unresolved by 6:25 AM ET
