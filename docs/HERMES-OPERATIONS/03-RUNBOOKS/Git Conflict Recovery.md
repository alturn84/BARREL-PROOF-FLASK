# Runbook: Git Conflict Recovery
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** GitHub push failures and merge conflicts

---

## Symptoms

- `git push` returns a rejection or conflict error
- Push fails with "non-fast-forward" error
- Merge conflict markers appear in files
- GitHub remote is ahead of local branch

---

## Diagnosis

### Step 1 — Check the error type

```
git status
git log --oneline -5
```

Identify whether the issue is:
- Remote ahead of local (diverged history)
- Merge conflict in specific files
- Permissions or authentication issue
- Branch protection rule triggered

### Step 2 — Confirm local state is clean

```
git diff
git stash list
```

Ensure no uncommitted changes would be affected by recovery steps.

---

## Recovery Steps

### Scenario A — Remote is ahead of local

The most common scenario: another process or manual push has updated the remote.

**Recovery Attempt 1:**
```
git fetch origin
git log --oneline HEAD..origin/main
```
Review what commits exist on remote that are not local. If they are safe (no conflicts with morning update files):
```
git pull --rebase origin main
git push origin main
```

**Recovery Attempt 2 (if rebase creates conflicts):**
```
git rebase --abort
git fetch origin
```
Manually review the divergence. Do not force push. Escalate to Allan.

---

### Scenario B — Merge conflict in files

**Recovery Attempt 1:**
Identify conflicting files:
```
git status
```
Open conflicting files. Look for conflict markers:
```
<<<<<<< HEAD
[local version]
=======
[remote version]
>>>>>>> origin/main
```

For data and content files (JSON, generated content): the morning pipeline's version is authoritative. Accept the local version:
```
git checkout --ours [filename]
git add [filename]
git rebase --continue
```

**Recovery Attempt 2 (if conflicts are unclear):**
Do not guess. Do not force a resolution on files you cannot verify. Escalate to Allan.

---

### Scenario C — Authentication failure

If push fails with authentication error:
1. Verify SSH key or token is configured and valid
2. Test connection: `git remote -v`
3. If credentials expired — this is an infrastructure issue. Escalate to Allan.

---

## Hard Rules

- **Never force push** (`git push --force`) without explicit instruction from Allan Turner
- **Never delete or modify commit history** without explicit instruction
- **Never resolve conflicts in pipeline-critical files by guessing** — escalate

---

## Escalation Criteria

Escalate to Allan if:
- Remote divergence cannot be resolved safely by rebase
- Merge conflicts exist in files you cannot determine the correct resolution for
- Authentication fails and cannot be resolved by credential refresh
- It is past 6:25 AM ET and push has not succeeded

---

## Post-Recovery

- [ ] Confirm push succeeded
- [ ] Confirm Render deployment triggered
- [ ] Log incident in `06-LOGS/`
- [ ] Note in `00-INBOX/` if escalation was required

---

## Related Documents
- `01-SOPs/Deployment SOP.md`
- `03-RUNBOOKS/Render Deployment Failure.md`
- `05-AUTOMATION/GitHub Flow.md`
