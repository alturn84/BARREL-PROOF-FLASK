# Template: Runbook

> Copy to `03-RUNBOOKS/` and rename to `[Failure Type] Recovery.md`

---

# Runbook: {{FAILURE TYPE}}
**Version:** 1.0
**Last Modified:** {{DATE}}
**Applies To:** [What system, job, or service this runbook covers]

---

## Symptoms
> Observable signs that this failure has occurred.

-
-

---

## Diagnosis

### Step 1 — [Identify the failure]


### Step 2 — [Classify the failure]


---

## Recovery Steps

### Recovery Attempt 1 — [Name]
> First recovery approach.

1. 
2. 
3. 

### Recovery Attempt 2 — [Name]
> Second recovery approach if Attempt 1 fails.

1. 
2. 
3. 

---

## Hard Rules
> Things that must never be done during this recovery.

- **Never**
- **Never**

---

## Escalation Criteria
> Conditions that require immediate escalation to Allan Turner.

Escalate to Allan if:
- 
- 

When escalating, provide:
1. What failed
2. When it failed
3. What was attempted
4. Current state

---

## Post-Recovery
- [ ] Confirm issue is resolved
- [ ] Log incident in `06-LOGS/`
- [ ] Create incident entry in `00-INBOX/` if escalation occurred

---

## Related Documents
- 
