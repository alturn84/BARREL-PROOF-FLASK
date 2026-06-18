# HERMES OPERATIONS — Vault Index
**Last Updated:** 2025-06-06
**Vault Owner:** Allan Turner
**Operated By:** Hermes

---

## Start Here

New to this vault? Start with:
1. `Hermes Constitution.md` — Hermes' identity, responsibilities, and operating rules
2. `01-SOPs/Morning Update SOP.md` — The daily pipeline workflow
3. `05-AUTOMATION/Pipeline Overview.md` — How the system works end to end

---

## Vault Structure

### Root
| File | Purpose |
|------|---------|
| `Hermes Constitution.md` | Master operating document. Everything flows from here. |
| `Vault Index.md` | This file. Navigation reference. |

---

### 00-INBOX
Active staging area for incidents, flags, and items needing attention.

| File | Purpose |
|------|---------|
| `README.md` | How to use the INBOX |

*Active incident reports and flags are filed here and archived once resolved.*

---

### 01-SOPs
Standard operating procedures for all recurring Hermes responsibilities.

| File | Purpose |
|------|---------|
| `Morning Update SOP.md` | Daily pipeline — pre-run, cron jobs, post-run, verification |
| `Deployment SOP.md` | Commit, push, and Render deployment procedure |
| `Publishing SOP.md` | Content flow from generation to live site |
| `Daily Verification SOP.md` | Post-pipeline verification checklist |
| `Incident Response SOP.md` | How to respond to failures and escalate |

---

### 02-PROMPTS
All AI generation prompts used by Cron Job 2. Each file includes version history and input variable documentation.

| File | Purpose |
|------|---------|
| `Press Box Prompt.md` | Lead editorial section |
| `Around the League Prompt.md` | Multi-item league digest |
| `Game of the Day Prompt.md` | Primary game spotlight |
| `Game to Watch Prompt.md` | Secondary game spotlight |
| `Advanced Scout Prompt.md` | Deep analytical preview |
| `DFS Prompt.md` | Daily fantasy sports analysis |

---

### 03-RUNBOOKS
Step-by-step recovery guides for known failure modes.

| File | Purpose |
|------|---------|
| `Cron Failure Recovery.md` | Cron Job 1 or 2 fails to run or complete |
| `Git Conflict Recovery.md` | Push fails or merge conflict exists |
| `Render Deployment Failure.md` | Render build fails or site is down post-deploy |
| `Gemini API Quota Failure.md` | Content generation API hits quota or rate limit |
| `Missing JSON Recovery.md` | Expected data files absent after Cron Job 1 |
| `Data Validation Failure.md` | Validation fails on data or content output |

---

### 04-EDITORIAL
Editorial standards, voice guidance, and content examples.

| File | Purpose |
|------|---------|
| `Voice & Tone Guide.md` | Barrel Proof editorial voice, language standards, what to avoid |
| `Editorial Rules.md` | 10 non-negotiable content rules |
| `Advanced Scout Standards.md` | Section-by-section standards for the analytical preview |
| `Press Box Examples.md` | Annotated examples of well-written Press Box content |
| `Game of the Day Examples.md` | Annotated examples of well-written Game of the Day content |

---

### 05-AUTOMATION
Technical documentation for the pipeline, APIs, scripts, and infrastructure.

| File | Purpose |
|------|---------|
| `Pipeline Overview.md` | Full pipeline sequence, data flow, dependencies |
| `Cron Documentation.md` | Both cron jobs: IDs, schedules, responsibilities, sequencing rules |
| `API Inventory.md` | All external APIs: purpose, rate limits, failure runbooks |
| `Script Inventory.md` | All pipeline scripts: paths, purposes, modification rules |
| `Environment Variables.md` | Variable registry and security policy |
| `GitHub Flow.md` | Git operations, commit standards, what Hermes can and cannot do |
| `Render Flow.md` | Deployment trigger, build process, verification |
| `HERMES-ROLE-001 - Hermes Operating Role.md` | Hermes' operator role, success criteria, failure patterns, and editorial boundary in the upgraded Copilot/Firecrawl stack |
| `MODEL-001 - Hermes GitHub Copilot Provider Setup.md` | GitHub Copilot provider auth, PAT conflict rules, gateway restart |
| `FIRECRAWL-002 - Hermes News Intake Operating Rules.md` | Firecrawl source intake rules, what it can/cannot be used for |

---

### 06-LOGS
Operational logs and review templates.

| File | Purpose |
|------|---------|
| `Daily Log Template.md` | Template for daily pipeline and deployment logs |
| `Weekly Operations Review Template.md` | Weekly reliability and content delivery review |
| `Monthly Reliability Review Template.md` | Monthly metrics, trends, and recommendations |

*Active daily logs should be created here each day using the template.*

---

### 07-SYSTEMS
System architecture, decision authority, and data ownership.

| File | Purpose |
|------|---------|
| `Hermes Architecture.md` | Agent structure, operational scope, decision authority map |
| `Production Stack.md` | Current tech stack: hosting, APIs, repository, data sources |
| `Publishing Flow.md` | Complete path from data collection to live site |
| `GitHub Flow.md` | Repository structure, branch strategy, Render integration |
| `Data Ownership Rules.md` | What data Hermes can and cannot modify |

---

### 08-TEMPLATES
Reusable templates for operational documents.

| File | Purpose |
|------|---------|
| `Daily Log Template.md` | Quick-reference daily log format |
| `Incident Report Template.md` | Standard incident documentation |
| `Postmortem Template.md` | P1/P2 incident post-analysis |
| `SOP Template.md` | Blank SOP for new procedures |
| `Runbook Template.md` | Blank runbook for new failure modes |
| `Prompt Template.md` | Blank prompt file for new content types |

---

### 09-DFS
DFS analysis methodology, grading, and workflow.

| File | Purpose |
|------|---------|
| `Projection Methodology.md` | How Hermes approaches DFS analysis and data sourcing |
| `Confidence Grading.md` | HIGH / MEDIUM / LOW grading definitions and criteria |
| `Research Workflow.md` | Step-by-step workflow from slate assessment to output |
| `DFS Checklist.md` | Pre-analysis and output validation checklist |

---

### 10-SOCIAL
Social media standards, approval workflow, and templates.

| File | Purpose |
|------|---------|
| `X Post Standards.md` | Writing standards, post types, what Hermes does not post |
| `Approval Workflow.md` | Draft → staging → Allan approval → publish |
| `Social Content Templates.md` | Fill-in templates for each post type |

*Draft posts for review are staged in `10-SOCIAL/Drafts/` (create this subfolder as needed).*

---

### 11-ARCHIVE
Resolved incidents, completed reviews, retired documents.

| Subfolder | Contents |
|-----------|---------|
| `Incidents/` | Resolved incident reports |
| `Postmortems/` | Completed P1/P2 postmortems |
| `Reviews/` | Completed weekly and monthly reviews |
| `Retired/` | Deprecated SOPs, runbooks, or prompts |

---

### SCRATCHPAD
Temporary working notes. Not authoritative. Clean regularly.

---

## Quick Reference

| I need to... | Go to... |
|-------------|---------|
| Run the morning pipeline | `01-SOPs/Morning Update SOP.md` |
| Respond to a cron failure | `03-RUNBOOKS/Cron Failure Recovery.md` |
| Fix a git push problem | `03-RUNBOOKS/Git Conflict Recovery.md` |
| Handle a Render failure | `03-RUNBOOKS/Render Deployment Failure.md` |
| Handle Gemini API failure | `03-RUNBOOKS/Gemini API Quota Failure.md` |
| Find missing JSON | `03-RUNBOOKS/Missing JSON Recovery.md` |
| Fix validation failure | `03-RUNBOOKS/Data Validation Failure.md` |
| Write or review content | `04-EDITORIAL/Voice & Tone Guide.md` |
| Update a prompt | `02-PROMPTS/[Content Type] Prompt.md` |
| Log today's run | `06-LOGS/Daily Log Template.md` |
| Draft a social post | `10-SOCIAL/Social Content Templates.md` |
| Document an incident | `08-TEMPLATES/Incident Report Template.md` |
| Understand Hermes' rules | `Hermes Constitution.md` |
