# GitHub Flow
**Version:** 1.0
**Last Modified:** 2025-06-06

---

## Repository Structure

The Barrel Proof GitHub repository contains all production code, templates, and pipeline-generated content. It is the single source of truth for what is deployed to the live site.

---

## Branch Strategy

| Branch | Purpose | Who Pushes |
|--------|---------|-----------|
| `main` | Production branch — deploys to live site on every push | Hermes (daily pipeline), Claude Code (features/fixes) |

Hermes pushes only to `main` and only for verified, validated morning update commits.

---

## Hermes Commit Cadence

| When | What |
|------|------|
| After each successful morning pipeline | One commit containing all pipeline output for that day |
| Never | Mid-pipeline partial commits, code changes, config changes |

---

## Render Integration

Barrel Proof uses Render's automatic deploy on push to `main`. Every successful push to `main` triggers a Render build and deployment.

Hermes confirms Render build completion after every push. The pipeline is not considered complete until deployment is verified live.

---

## What Hermes Never Touches in GitHub

- Application code (`.py`, `.js`, `.html`, `.css`, templates)
- Configuration files
- Build scripts
- `.gitignore`
- Branch settings or repository configuration
- Pull requests or merge operations

---

## Related Documents
- `05-AUTOMATION/GitHub Flow.md`
- `05-AUTOMATION/Render Flow.md`
- `03-RUNBOOKS/Git Conflict Recovery.md`
