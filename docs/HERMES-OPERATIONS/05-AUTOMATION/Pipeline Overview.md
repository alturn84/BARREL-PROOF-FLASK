# Pipeline Overview
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** Barrel Proof morning publication pipeline

---

## Overview

The Barrel Proof morning pipeline runs two sequential cron jobs every day to collect MLB data and generate editorial content for publication. The entire pipeline must complete by 6:30 AM ET.

---

## Pipeline Sequence

```
6:00 AM ET
└── Cron Job 1 (ID: 98de609020e4)
    ├── MLB data collection (API fetch)
    ├── Game card generation
    ├── Data validation
    └── JSON output to /workspace/barrel-proof/[data directory]
           │
           ▼
6:15 AM ET
└── Cron Job 2 (ID: e1af79acae93)
    ├── Read Cron Job 1 output (JSON files)
    ├── AI content generation (Gemini API)
    │   ├── Game summaries
    │   ├── Press Box
    │   ├── Around the League
    │   ├── Game of the Day
    │   ├── Game to Watch
    │   └── Advanced Scout previews
    ├── Content validation
    └── Output to /workspace/barrel-proof/[content directory]
           │
           ▼
Post-pipeline
├── Commit staged files
├── Push to GitHub
├── Render deployment
└── Live site updated
```

---

## Data Flow

| Stage | Input | Output | Destination |
|-------|-------|--------|-------------|
| MLB Data Collection | MLB API | Game data JSON | `/workspace/barrel-proof/` |
| Game Card Generation | Game data JSON | Game card JSON | `/workspace/barrel-proof/` |
| Content Generation | All JSON files | Markdown/HTML content | `/workspace/barrel-proof/` |
| Commit & Deploy | All validated files | GitHub commit | Render → Production |

---

## Dependencies

| Dependency | Used By | Failure Runbook |
|-----------|---------|----------------|
| MLB Data API | Cron Job 1 | `03-RUNBOOKS/Cron Failure Recovery.md` |
| Gemini API | Cron Job 2 | `03-RUNBOOKS/Gemini API Quota Failure.md` |
| GitHub | Post-pipeline | `03-RUNBOOKS/Git Conflict Recovery.md` |
| Render | Post-pipeline | `03-RUNBOOKS/Render Deployment Failure.md` |

---

## Critical Path

Cron Job 2 cannot run until Cron Job 1 has completed and produced valid output. If Cron Job 1 fails, Cron Job 2 must be held until data is available.

The 15-minute gap between jobs (6:00 → 6:15) provides a recovery window for Cron Job 1 failures. If Cron Job 1 is delayed but completes by 6:10, Cron Job 2 can still meet the 6:30 deadline.

If Cron Job 1 has not completed by 6:10 AM: begin escalation procedures.

---

## Workspace

All pipeline activity is confined to:
```
/workspace/barrel-proof
```

Hermes must never write pipeline output outside this directory.

---

## Related Documents
- `01-SOPs/Morning Update SOP.md`
- `05-AUTOMATION/Cron Documentation.md`
- `05-AUTOMATION/Script Inventory.md`
- `05-AUTOMATION/API Inventory.md`
