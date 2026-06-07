# SOP: Deployment
**Version:** 1.0
**Last Modified:** 2025-06-06
**Owner:** Hermes
**Category:** Deployment

---

## Purpose

This SOP governs all deployment activity from the `/workspace/barrel-proof` repository to production via Render. It covers the pre-deployment checklist, deployment steps, verification, and rollback criteria.

---

## Deployment Types

| Type | Trigger | Frequency |
|------|---------|-----------|
| Morning Update | Post-pipeline completion | Daily |
| Feature Release | Claude Code implementation complete | As needed |
| Hotfix | Critical bug or data error | As needed |

Hermes handles **Morning Update** deployments autonomously per schedule.

Feature Releases and Hotfixes are authorized by Allan Turner and executed by Claude Code. Hermes supports but does not initiate these.

---

## Pre-Deployment Checklist

Before any commit is pushed:

- [ ] All files to be committed have been validated
- [ ] No broken or partial content exists in staged files
- [ ] Data validation passed without errors
- [ ] Content passed editorial review (automated or manual)
- [ ] No known active incidents in `00-INBOX/`
- [ ] Render is reachable and current deployment is stable

---

## Deployment Steps

### Step 1 — Stage Commit
```
git add [verified files only]
```
Never use `git add .` without explicit review of all changed files.

### Step 2 — Write Commit Message
Follow commit message standards:
```
[type] [date] — [brief description]
```
Examples:
```
morning update 2025-06-06 — game cards, summaries, press box
hotfix 2025-06-06 — corrected null field in game card JSON
```

### Step 3 — Push to GitHub
```
git push origin main
```
Confirm push succeeds without errors.

### Step 4 — Confirm Render Deployment
- Monitor Render dashboard or deployment logs
- Confirm build triggered automatically on push
- Confirm build completes without errors
- Confirm site is live and serving correctly

### Step 5 — Post-Deployment Verification
- Spot check live site for expected content
- Confirm no 500 errors or broken pages
- Log deployment completion in `06-LOGS/`

---

## Rollback Criteria

Initiate rollback if:
- Render build fails and cannot be resolved
- Live site returns errors after deployment
- Content is missing or malformed on live site
- Data appears corrupted on live pages

Rollback procedure:
1. Alert Allan Turner immediately
2. Document the failure in `00-INBOX/`
3. Do not attempt to fix a broken production deployment without authorization

---

## Escalation

Alert Allan Turner immediately if:
- Push to GitHub fails twice
- Render deployment fails twice
- Live site is down or serving errors post-deployment

---

## Related Documents
- `03-RUNBOOKS/Render Deployment Failure.md`
- `03-RUNBOOKS/Git Conflict Recovery.md`
- `05-AUTOMATION/GitHub Flow.md`
- `05-AUTOMATION/Render Flow.md`
