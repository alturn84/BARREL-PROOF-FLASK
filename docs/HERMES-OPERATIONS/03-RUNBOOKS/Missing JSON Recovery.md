# Runbook: Missing JSON Recovery
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** Missing or inaccessible JSON output files from Cron Job 1

---

## Symptoms

- Cron Job 2 fails because expected JSON input files are absent
- Game card generation produced no output files
- Data files exist but are empty (0 bytes)
- Pipeline references a file path that does not exist

---

## Diagnosis

### Step 1 — Confirm what is missing

List the expected output directory:
```
ls -la /workspace/barrel-proof/[data-output-directory]
```

Identify:
- Which files are missing
- Which files exist but are empty
- Whether any partial files exist (could indicate an interrupted write)

### Step 2 — Check Cron Job 1 logs

Review Cron Job 1 logs for the current run:
- Did the job complete successfully?
- Were there write errors?
- Did the MLB data API return data?
- Were there disk space or permissions issues?

### Step 3 — Confirm upstream data availability

Test MLB data API reachability:
- Did the API return data for today's date?
- Are today's games on the schedule? (Some off days produce minimal data)
- Is the response format what the parser expects?

---

## Recovery Steps

### Recovery Attempt 1 — Re-run Cron Job 1

1. Confirm Cron Job 1 is not currently running (avoid double execution)
2. Manually trigger Cron Job 1
3. Monitor output in real time
4. Confirm JSON files are created in expected locations
5. Verify files are not empty and contain valid JSON
6. If successful: trigger Cron Job 2

### Recovery Attempt 2 — Isolated script run

If Cron Job 1 re-run produces no output:

1. Run the data collection script directly to capture full output:
   ```
   [data collection script command]
   ```
2. Review output for specific errors:
   - API connection failure → see `03-RUNBOOKS/Cron Failure Recovery.md`
   - Parse error → API response format may have changed
   - Permission error → workspace permissions issue
3. If the issue is clearly identifiable and within scope: resolve and retry
4. If the issue requires code investigation: **escalate to Allan — do not modify scripts**

---

## Special Case — MLB Off Day

If today is an MLB off day or a day with very few games:
- Minimal or no game card data is expected
- Verify the pipeline handles zero-game days gracefully
- Content generation (Cron Job 2) should still run with available data
- Document the off-day handling in the daily log

---

## Hard Rules

- **Never fabricate or manually create JSON data files to fill a gap**
- **Never modify data parsing scripts without authorization**
- **If data is genuinely unavailable: publish what can be published; alert Allan about gaps**

---

## Escalation Criteria

Escalate to Allan if:
- Cron Job 1 re-run fails to produce output
- Isolated script run reveals a code or API format issue
- It is past 6:15 AM ET and data files are still missing
- Data exists but appears corrupted or malformed

---

## Post-Recovery

- [ ] Confirm all expected JSON files exist and are valid
- [ ] Validate file contents are not empty or malformed
- [ ] Proceed with Cron Job 2 if data is complete
- [ ] Log incident in `06-LOGS/`
- [ ] Note file path and issue type for pattern tracking

---

## Related Documents
- `03-RUNBOOKS/Cron Failure Recovery.md`
- `03-RUNBOOKS/Data Validation Failure.md`
- `05-AUTOMATION/Pipeline Overview.md`
- `05-AUTOMATION/Script Inventory.md`
