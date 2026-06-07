# Script Inventory
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** All scripts in the Barrel Proof pipeline

---

## Purpose

This document is a living inventory of every script Hermes runs or interacts with. It should be updated whenever a script is added, modified, or retired.

---

## Active Scripts

> **Note:** Populate this inventory with actual script names and paths from the Barrel Proof repository. The structure below is the template.

| Script Name | Path | Purpose | Run By | Frequency |
|-------------|------|---------|--------|-----------|
| [script name] | `/workspace/barrel-proof/[path]` | [what it does] | Cron Job 1 | Daily 6:00 AM |
| [script name] | `/workspace/barrel-proof/[path]` | [what it does] | Cron Job 2 | Daily 6:15 AM |

---

## Script Modification Rules

Scripts in the Barrel Proof pipeline must not be modified by Hermes without explicit instruction from Allan Turner or Claude Code under Allan's direction.

If a script appears to be failing due to a code issue:
1. Document the failure symptoms in `00-INBOX/`
2. Escalate to Allan
3. Do not attempt to edit or patch scripts independently

---

## Retired Scripts

| Script Name | Retired Date | Reason | Replaced By |
|-------------|-------------|--------|-------------|
| — | — | — | — |

---

## Related Documents
- `05-AUTOMATION/Pipeline Overview.md`
- `05-AUTOMATION/Cron Documentation.md`
