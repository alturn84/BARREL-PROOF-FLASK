# SOP: Daily Verification
**Version:** 1.0
**Last Modified:** 2025-06-06
**Owner:** Hermes
**Category:** Quality Assurance

---

## Purpose

This SOP defines the daily verification routine that confirms the Barrel Proof pipeline ran correctly, content is live, and no errors or anomalies exist that require attention.

---

## Verification Window

Daily verification should be complete by **6:30 AM ET** following the morning pipeline run.

---

## Pipeline Verification Checklist

### Data Layer (Post Cron Job 1)
- [ ] MLB data collection completed — expected game count matches actual
- [ ] All game cards generated — no missing games for today's schedule
- [ ] JSON output files exist and are valid (no null fields, no schema errors)
- [ ] No API errors in data collection logs
- [ ] No timeout or rate limit errors

### Content Layer (Post Cron Job 2)
- [ ] Game summaries generated for all eligible games
- [ ] Press Box content generated
- [ ] Around the League items generated
- [ ] Game of the Day copy present and complete
- [ ] Game to Watch copy present and complete
- [ ] Advanced Scout content generated (if applicable to today's schedule)
- [ ] Gemini API returned valid responses — no truncation or error responses
- [ ] No placeholder text in any content output

### Deployment Layer
- [ ] Commit pushed to GitHub successfully
- [ ] Render build triggered
- [ ] Render build completed without errors
- [ ] Live site is accessible
- [ ] Content is visible on live site
- [ ] No 500 errors or broken pages

---

## Spot Check Protocol

After deployment, perform a spot check of the live site:

1. Load the homepage — confirm today's content is present
2. Load one game summary — confirm it renders correctly
3. Load the Press Box — confirm it is populated
4. Confirm no broken images, missing data, or error states

---

## Anomaly Logging

Any anomaly found during verification — even minor — must be logged in `00-INBOX/` with:
- Date and time
- What was found
- Whether it was resolved or escalated

Minor anomalies that are resolved do not require Allan notification. Unresolved anomalies always require escalation.

---

## End-of-Day Review (Optional)

At the end of the day, optionally review:
- Did the day's game data update correctly for completed games?
- Are standings current?
- Any upcoming game data for tomorrow loaded correctly?

Log any issues found in `06-LOGS/` for the following morning's pre-run awareness.

---

## Related Documents
- `01-SOPs/Morning Update SOP.md`
- `03-RUNBOOKS/Data Validation Failure.md`
- `05-AUTOMATION/Pipeline Overview.md`
- `06-LOGS/Daily Log Template.md`
