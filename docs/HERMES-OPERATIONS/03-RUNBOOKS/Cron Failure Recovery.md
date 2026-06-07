# Runbook: Cron Failure Recovery
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** Cron Job 1 (`98de609020e4`) and Cron Job 2 (`e1af79acae93`)

---

## Symptoms

- Cron job did not trigger at scheduled time
- Cron job triggered but exited with non-zero status
- Expected output files are absent after the scheduled run time
- Pipeline logs show no activity at the expected time
- Morning content is missing from the site

---

## Diagnosis

### Step 1 — Confirm the failure

Check the cron job logs for the relevant job ID:
- Cron Job 1: `98de609020e4`
- Cron Job 2: `e1af79acae93`

Look for:
- Exit code (non-zero = failure)
- Error message in logs
- Timestamp of last successful run vs. today's expected run

### Step 2 — Identify failure type

| Symptom | Likely Cause |
|---------|-------------|
| Job did not run at all | Cron scheduler issue, environment problem |
| Job ran but exited immediately | Script error, missing dependency, permission issue |
| Job ran but produced no output | Data source unavailable, API failure |
| Job ran but output is malformed | Schema change, API response change, parsing error |

### Step 3 — Check dependencies

For Cron Job 1 failures:
- Is the MLB data API reachable?
- Are environment variables set correctly?
- Is `/workspace/barrel-proof` accessible with write permissions?

For Cron Job 2 failures:
- Did Cron Job 1 complete? (Check for Cron Job 1 output files)
- Is the Gemini API reachable and within quota?
- Are prompt files accessible?

---

## Recovery Steps

### Recovery Attempt 1 — Manual trigger

1. Confirm the workspace is accessible:
   ```
   ls /workspace/barrel-proof
   ```
2. Check for obvious environment issues (missing env vars, permissions)
3. Manually trigger the failed cron job
4. Monitor output in real time
5. If successful: verify output files and proceed to deployment
6. Log the manual trigger and outcome in `06-LOGS/`

### Recovery Attempt 2 — Isolated run

If Attempt 1 fails:

1. Isolate the specific failing script
2. Run the script directly (not via cron) to capture full error output
3. Review the error output for actionable cause
4. If the error is clearly a transient issue (network timeout, API rate limit): wait 5 minutes and retry
5. If the error is a code or data issue: **do not attempt further fixes — escalate**

---

## Escalation Criteria

Escalate to Allan Turner if:
- Both recovery attempts fail
- The failure cause is unclear after direct script execution
- It is 6:20 AM ET or later and pipeline is still incomplete
- Any production data appears corrupted

When escalating, provide:
- Which cron job failed (ID and scheduled time)
- Exact error message from logs
- What recovery was attempted
- Current state (what files exist, what is missing)

---

## Post-Recovery

After successful recovery:
- [ ] Verify all expected output files exist
- [ ] Validate data and content quality
- [ ] Complete deployment per `01-SOPs/Deployment SOP.md`
- [ ] Log incident and recovery in `06-LOGS/`
- [ ] Create incident entry in `00-INBOX/` if recovery took more than one attempt

---

## Related Documents
- `01-SOPs/Morning Update SOP.md`
- `03-RUNBOOKS/Gemini API Quota Failure.md`
- `03-RUNBOOKS/Missing JSON Recovery.md`
- `03-RUNBOOKS/Data Validation Failure.md`
- `05-AUTOMATION/Pipeline Overview.md`
- `05-AUTOMATION/Cron Documentation.md`
