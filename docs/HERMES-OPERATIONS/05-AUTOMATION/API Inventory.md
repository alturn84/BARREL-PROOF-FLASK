# API Inventory
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** All external APIs used by the Barrel Proof pipeline

---

## Active APIs

### MLB Data API
| Field | Value |
|-------|-------|
| Purpose | Game data, scores, schedules, standings, player stats |
| Used By | Cron Job 1 |
| Failure Runbook | `03-RUNBOOKS/Cron Failure Recovery.md` |
| Rate Limits | [Document when known] |
| Authentication | [Document API key storage location] |
| Notes | Primary data source for all game and player data |

---

### Gemini API
| Field | Value |
|-------|-------|
| Purpose | AI content generation — all editorial content types |
| Used By | Cron Job 2 |
| Failure Runbook | `03-RUNBOOKS/Gemini API Quota Failure.md` |
| Daily Quota | [Document current quota limit] |
| Per-Minute Limit | [Document rate limit] |
| Authentication | [Document API key storage location] |
| Notes | Required for all content generation. Quota exhaustion = partial or no content. |

---

## API Key Security

All API keys must be stored as environment variables. Keys must never be:
- Hard-coded in scripts
- Committed to GitHub in any file
- Stored in plain text in any note or document in this vault

Reference: See `05-AUTOMATION/Environment Variables.md` for the approved key storage approach.

---

## Adding New APIs

When a new API is integrated into the pipeline:
1. Add it to this inventory with all fields completed
2. Document its failure mode and create a runbook entry if needed
3. Confirm key storage follows security standards
4. Update `05-AUTOMATION/Pipeline Overview.md` if it affects the pipeline sequence

---

## Deprecated / Inactive APIs

Document removed APIs here to maintain history of what was used and why it was removed.

| API | Removed Date | Reason |
|-----|-------------|--------|
| — | — | — |
