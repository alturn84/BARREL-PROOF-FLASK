# Runbook: Data Validation Failure
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** Data validation checks in Cron Job 1 and Cron Job 2

---

## Symptoms

- Validation script returns errors after Cron Job 1
- Required fields are null, missing, or incorrectly typed
- Unexpected data values (negative scores, future dates, missing team names)
- Content generation produces output with `null`, `undefined`, or empty fields
- Schema validation fails on one or more output files

---

## Diagnosis

### Step 1 — Identify which validation failed

Review the validation output or error log. Identify:
- Which file failed validation
- Which specific field(s) are invalid
- What the actual value is vs. what was expected

### Step 2 — Classify the failure

| Failure Type | Description |
|-------------|-------------|
| Missing field | Required field is absent from the JSON |
| Null value | Field exists but contains null or empty string |
| Type mismatch | Field contains wrong data type (string where number expected) |
| Out-of-range value | Value is implausible (negative attendance, score > 30, etc.) |
| Schema change | API response structure changed, parser produced unexpected output |

### Step 3 — Assess scope

- Is it one file or multiple files?
- Is it one field or systemic across the dataset?
- Is the error in raw API data or in the parser's output?

---

## Recovery Steps

### Recovery Attempt 1 — Re-fetch and reprocess

If the failure is limited to one file and may be a transient data issue:

1. Delete the invalid output file
2. Re-run the data collection and processing for the affected data type
3. Re-validate
4. If validation passes: continue pipeline
5. Log the retry

### Recovery Attempt 2 — Partial pipeline

If re-fetch fails or produces the same invalid data:

1. Identify which content types depend on the invalid data
2. Determine whether content generation can proceed for other data types
3. Generate what can be generated cleanly
4. Flag affected content types as unavailable
5. Alert Allan — do not publish incomplete or null-containing content without authorization

---

## Hard Rules

- **Never commit files that fail validation**
- **Never manually edit data files to fix validation failures**
- **Never publish content with null, empty, or placeholder field values**
- **Never modify the validation scripts without authorization**

---

## Escalation Criteria

Escalate to Allan if:
- Re-fetch produces the same invalid data
- Validation failure is systemic across multiple files
- The failure pattern suggests an API schema change
- It is past 6:20 AM ET and validation is still failing

When escalating:
- Name the specific file and field that failed
- Paste the actual value vs. expected value
- Confirm whether partial content can be published

---

## Post-Recovery

- [ ] Confirm all published files passed validation
- [ ] Log which data types were affected
- [ ] Log whether full or partial pipeline ran
- [ ] Create incident entry in `00-INBOX/` if Allan was alerted
- [ ] Note field names and failure type for pattern tracking — repeated failures on the same field may indicate an API change requiring code update

---

## Related Documents
- `03-RUNBOOKS/Missing JSON Recovery.md`
- `03-RUNBOOKS/Cron Failure Recovery.md`
- `05-AUTOMATION/Pipeline Overview.md`
- `05-AUTOMATION/Script Inventory.md`
