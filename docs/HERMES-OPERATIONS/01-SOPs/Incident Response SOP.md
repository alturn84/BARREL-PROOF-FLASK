# SOP: Incident Response
**Version:** 1.0
**Last Modified:** 2025-06-06
**Owner:** Hermes
**Category:** Incident Management

---

## Purpose

This SOP governs how Hermes responds to failures, errors, and unexpected events. It defines the response protocol, escalation thresholds, and documentation requirements for all incidents.

---

## Incident Severity Levels

| Level | Description | Response Time | Escalate to Allan |
|-------|-------------|--------------|-------------------|
| P1 — Critical | Site is down, pipeline completely failed, data is corrupted on production | Immediate | Yes — immediately |
| P2 — High | One cron job failed, content missing from live site, deployment blocked | Within 5 min | Yes — if not resolved in 2 attempts |
| P3 — Medium | Partial content missing, API degraded but functional, non-blocking errors | Within 15 min | Yes — if not resolved in 2 attempts |
| P4 — Low | Minor anomaly, cosmetic issue, non-impacting warning in logs | Same day | Only if unresolved |

---

## Response Protocol

For all incidents:

### Step 1 — Identify
- Note the exact time the incident was detected
- Identify what failed (which job, which script, which API)
- Capture the error message or symptom exactly as it appears

### Step 2 — Classify
- Assign a severity level (P1–P4)
- Determine the relevant runbook

### Step 3 — Respond
- Follow the relevant runbook from `03-RUNBOOKS/`
- Attempt recovery once
- If recovery fails — attempt a second time
- If recovery fails twice — escalate to Allan

### Step 4 — Document
- Create an incident entry in `00-INBOX/`
- Log all actions taken, timestamps, and outcomes
- If resolved: document resolution in log
- If escalated: document escalation and await Allan's direction

---

## Runbook Reference

| Failure Type | Runbook |
|-------------|---------|
| Cron job fails | `03-RUNBOOKS/Cron Failure Recovery.md` |
| Git conflict or push failure | `03-RUNBOOKS/Git Conflict Recovery.md` |
| Render deployment fails | `03-RUNBOOKS/Render Deployment Failure.md` |
| Gemini API quota exhausted | `03-RUNBOOKS/Gemini API Quota Failure.md` |
| JSON file missing or corrupt | `03-RUNBOOKS/Missing JSON Recovery.md` |
| Data validation fails | `03-RUNBOOKS/Data Validation Failure.md` |

---

## Escalation to Allan Turner

Escalate immediately when:
- Any P1 incident is detected
- Any P2 or P3 incident cannot be resolved in two recovery attempts
- Any situation arises not covered by an existing runbook
- Content has been published that may be inaccurate or incomplete

When escalating, provide:
1. **What failed** — specific job, script, or service
2. **When it failed** — exact timestamp
3. **What was attempted** — recovery steps taken
4. **Current state** — what is broken right now
5. **Impact** — what is affected on the live site

Do not guess at root cause. Report facts and observable symptoms.

---

## Post-Incident Requirements

After every P1 or P2 incident, complete a postmortem within 24 hours using:
`08-TEMPLATES/Postmortem Template.md`

The postmortem should include:
- Root cause analysis
- What worked in the response
- What can be improved
- Whether a new or updated runbook is needed

---

## Related Documents
- `03-RUNBOOKS/` — all runbooks
- `00-INBOX/` — active incident staging
- `06-LOGS/` — operational logs
- `08-TEMPLATES/Incident Report Template.md`
- `08-TEMPLATES/Postmortem Template.md`
