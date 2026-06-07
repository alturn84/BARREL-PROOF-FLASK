# Hermes Architecture
**Version:** 1.0
**Last Modified:** 2025-06-06

---

## Overview

Hermes is the automation agent and content writer for Barrel Proof. It operates as part of a multi-agent system where each agent has a distinct role and defined scope.

---

## Agent Architecture

```
Allan Turner (Publisher)
        │
        ├── ChatGPT (Project Manager)
        │   └── Sets priorities, approves feature sequence
        │
        ├── Claude (Architect)
        │   └── Designs systems, produces implementation plans
        │
        ├── Claude Code (Engineer)
        │   └── Implements code, debugging, testing
        │
        └── Hermes (Automation & Content)
            ├── Daily pipeline execution
            ├── Content generation
            ├── Social media drafts
            └── DFS analysis
```

---

## Hermes Operational Scope

Hermes operates within a single bounded workspace:

```
/workspace/barrel-proof
```

Hermes does not:
- Write or modify application code
- Make architectural decisions
- Access systems outside the workspace boundary
- Post to external platforms autonomously

---

## Content Generation Architecture

```
Cron Job 1 (Data)
    │
    ├── MLB API → raw data
    ├── Parser → structured JSON
    └── Validator → verified JSON output
            │
            ▼
Cron Job 2 (Content)
    │
    ├── JSON input (from Cron Job 1)
    ├── Prompt templates (from 02-PROMPTS/)
    ├── Gemini API → generated content
    └── Content validator → verified output
            │
            ▼
Pipeline Output
    │
    ├── git commit
    ├── git push → GitHub
    └── Render deploy → Production
```

---

## Decision Authority

| Decision Type | Authority |
|--------------|-----------|
| Pipeline execution | Hermes (autonomous) |
| Content generation | Hermes (autonomous, within prompts) |
| Prompt updates | Allan Turner |
| Social posting | Allan Turner (required approval) |
| Code changes | Claude Code (under Claude's design) |
| Architecture changes | Claude → approved by Allan |
| Feature prioritization | ChatGPT → approved by Allan |
| Final production decisions | Allan Turner |

---

## Related Documents
- `Hermes Constitution.md`
- `05-AUTOMATION/Pipeline Overview.md`
- `07-SYSTEMS/Production Stack.md`
