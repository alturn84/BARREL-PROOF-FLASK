# Runbook: Render Deployment Failure
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** Render deployments for Barrel Proof

---

## Symptoms

- Render build did not trigger after push to GitHub
- Render build triggered but failed mid-build
- Build succeeded but live site is returning errors
- Live site is down or unreachable after deployment

---

## Diagnosis

### Step 1 — Check build status

Log into Render dashboard and check the deployment status for the Barrel Proof service.

Identify:
- Did the build trigger? (If not: GitHub webhook issue)
- Did the build fail? (If yes: review build logs)
- Did the build succeed but deploy fail? (Runtime issue)

### Step 2 — Review build logs

In the Render dashboard, open the failed deployment and review:
- Where did the build process stop?
- What error message appears at the point of failure?
- Is it a dependency error, a build command failure, or a runtime startup failure?

### Step 3 — Confirm the push was clean

Verify the GitHub commit that triggered the build:
- Was the push successful?
- Are the expected files present in the commit?
- Was there a partial or malformed file in the commit?

---

## Recovery Steps

### Recovery Attempt 1 — Trigger manual redeploy

If the build failure appears transient (network issue, timeout, infrastructure):

1. In the Render dashboard, select the failed deployment
2. Click "Manual Deploy" or "Redeploy"
3. Monitor the new build in real time
4. If it succeeds: verify the live site
5. Log the incident

### Recovery Attempt 2 — Review and re-push

If the manual redeploy fails:

1. Review the build log error in detail
2. If the error is caused by a specific file in the last commit:
   - Do not modify code
   - If the file is data or content: assess whether it can be regenerated
   - If the file is code: escalate to Allan — do not touch production code
3. If the error is a missing environment variable or configuration: escalate to Allan

---

## Hard Rules

- **Do not modify build configuration without Allan's authorization**
- **Do not roll back to a previous deployment without Allan's authorization**
- **Do not modify application code to fix a deployment failure**

---

## Escalation Criteria

Escalate to Allan if:
- Manual redeploy fails
- Build logs show a code or configuration error
- The live site is down and cannot be restored by redeploy
- It is past 6:30 AM ET and site is still not live

When escalating:
- Link to the failed deployment in Render
- Paste the relevant error from the build log
- Confirm whether the previous deployment is still serving (if rollback is possible)

---

## Post-Recovery

- [ ] Confirm live site is accessible
- [ ] Spot check content on live site
- [ ] Log incident in `06-LOGS/`
- [ ] Note in `00-INBOX/` if escalation was required

---

## Related Documents
- `01-SOPs/Deployment SOP.md`
- `03-RUNBOOKS/Git Conflict Recovery.md`
- `05-AUTOMATION/Render Flow.md`
