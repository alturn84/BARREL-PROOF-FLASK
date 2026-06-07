# GitHub Flow
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** Git and GitHub operations by Hermes

---

## Repository

All Barrel Proof code and content lives in a single GitHub repository. Hermes works exclusively within:
```
/workspace/barrel-proof
```

---

## Hermes Git Permissions

Hermes is authorized to:
- Stage files for commit (`git add`)
- Commit validated files (`git commit`)
- Push to the main branch (`git push origin main`)
- Pull updates when needed (`git pull`)
- Check status and logs (`git status`, `git log`)

Hermes is **not** authorized to:
- Force push (`git push --force`)
- Delete branches
- Merge pull requests
- Modify `.gitignore` or repository configuration
- Create or delete branches
- Revert or reset commits without Allan's instruction

---

## Daily Commit Standards

Every morning commit must:

1. Include only verified, validated files
2. Have a clear, descriptive commit message following this format:
   ```
   morning update YYYY-MM-DD — [content summary]
   ```
   Example:
   ```
   morning update 2025-06-06 — game cards, summaries, press box, advanced scout
   ```

3. Never include:
   - Unvalidated data files
   - Partial or incomplete content
   - Debug or test files
   - Files outside `/workspace/barrel-proof`

---

## Commit Before Checking

Before staging any commit:
- [ ] Run `git status` to confirm exactly which files will be staged
- [ ] Review the file list — no unexpected files
- [ ] Confirm all files have passed validation

Never use `git add .` without reviewing the output of `git status` first.

---

## Conflict Resolution

See `03-RUNBOOKS/Git Conflict Recovery.md` for the full conflict resolution procedure.

In summary:
- Remote ahead of local → rebase if safe, escalate if conflicts exist in critical files
- Merge conflicts in data/content files → local (pipeline) version is authoritative
- Merge conflicts in code files → escalate to Allan, do not resolve independently

---

## Render Trigger

Barrel Proof is configured for automatic deployment on push to `main`. Every successful push triggers a Render build. Hermes confirms build completion after every push per `01-SOPs/Deployment SOP.md`.

---

## Related Documents
- `01-SOPs/Deployment SOP.md`
- `03-RUNBOOKS/Git Conflict Recovery.md`
- `05-AUTOMATION/Render Flow.md`
