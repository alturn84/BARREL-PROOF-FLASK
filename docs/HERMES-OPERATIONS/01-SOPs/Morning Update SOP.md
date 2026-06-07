# SOP: Morning Update
**Version:** 1.0
**Last Modified:** 2025-06-06
**Owner:** Hermes
**Category:** Daily Operations

---

## Purpose

This SOP governs the daily morning publication pipeline for Barrel Proof. It covers the pre-run checklist, both cron job sequences, verification steps, and post-run confirmation.

**Hard deadline:** All morning automation must be complete and verified by **6:30 AM ET**.

---

## Schedule

| Cron Job | ID | Time (ET) | Scope |
|----------|----|-----------|-------|
| Cron Job 1 | `98de609020e4` | 6:00 AM | Data pipeline, MLB data collection, game card generation, data updates |
| Cron Job 2 | `e1af79acae93` | 6:15 AM | AI content generation, summaries, headlines, lead angles, editorial content |

---

## Pre-Run Checklist (Before 6:00 AM)

- [ ] Confirm API access is active (MLB data, Gemini)
- [ ] Confirm `/workspace/barrel-proof` is accessible
- [ ] Confirm GitHub connection is live
- [ ] Confirm Render is reachable
- [ ] Review any known issues from previous day's log (`06-LOGS/`)
- [ ] Check for any pending incidents from `00-INBOX/`

---

## Cron Job 1 — Data Pipeline (6:00 AM ET)

### Steps
1. Trigger pipeline for MLB data collection
2. Validate raw data ingestion — confirm expected record counts
3. Generate game cards for the day's scheduled games
4. Run data update scripts
5. Validate all output files against expected schema
6. Log completion with timestamp

### Verification
- All expected game cards generated
- No null or malformed fields in output JSON
- Data validation passes without errors
- No API errors in logs

### If Cron Job 1 Fails
→ Follow `03-RUNBOOKS/Cron Failure Recovery.md`
→ Attempt recovery twice
→ If unresolved by 6:10 AM ET — alert Allan

---

## Cron Job 2 — Content Generation (6:15 AM ET)

### Steps
1. Confirm Cron Job 1 output is present and valid
2. Trigger AI content generation pipeline
3. Generate game summaries
4. Generate Press Box content
5. Generate Around the League items
6. Generate Game of the Day copy
7. Generate Game to Watch copy
8. Generate Advanced Scout previews (if applicable)
9. Validate all content output
10. Log completion with timestamp

### Verification
- All content types generated for the day
- Content passes editorial standards check (see `04-EDITORIAL/Editorial Rules.md`)
- No placeholder text or incomplete sections
- Gemini API returned valid responses for all prompts

### If Cron Job 2 Fails
→ Follow `03-RUNBOOKS/Cron Failure Recovery.md`
→ Attempt recovery twice
→ If unresolved by 6:25 AM ET — alert Allan

---

## Post-Run Checklist (By 6:30 AM ET)

- [ ] Both cron jobs completed successfully
- [ ] All data validated
- [ ] All content generated and validated
- [ ] Commit staged with verified files only
- [ ] Commit pushed to GitHub
- [ ] Render deployment triggered and confirmed
- [ ] Daily log entry created in `06-LOGS/`
- [ ] Any anomalies flagged in `00-INBOX/`

---

## Commit Standards

Every morning commit must include:
- Descriptive message referencing the date and content type
- Only verified, validated files
- No partial or broken content

Example commit message:
```
morning update 2025-06-06 — game cards, summaries, press box
```

---

## Escalation

If any step cannot be completed by **6:30 AM ET**, alert Allan Turner immediately with:
- What failed
- When it failed
- What was attempted
- Current state of the pipeline

Do not attempt improvised fixes outside the runbooks without Allan's authorization.

---

## Related Documents
- `03-RUNBOOKS/Cron Failure Recovery.md`
- `03-RUNBOOKS/Git Conflict Recovery.md`
- `03-RUNBOOKS/Render Deployment Failure.md`
- `03-RUNBOOKS/Gemini API Quota Failure.md`
- `03-RUNBOOKS/Missing JSON Recovery.md`
- `05-AUTOMATION/Pipeline Overview.md`
- `06-LOGS/Daily Log Template.md`
