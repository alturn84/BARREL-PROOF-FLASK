# Production Stack
**Version:** 1.0
**Last Modified:** 2025-06-06

---

## Barrel Proof Production Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Hosting | Render | Production deployment and serving |
| Repository | GitHub | Source control and deployment trigger |
| Content AI | Gemini API | Editorial content generation |
| Data Source | MLB Data API | Game data, scores, schedules, standings |
| Workspace | `/workspace/barrel-proof` | Hermes operating environment |

> **Note:** Update this table as the stack evolves. Always document the actual production services, not planned ones.

---

## Deployment Pipeline

```
/workspace/barrel-proof (local)
        │
        └── git push origin main
                │
                └── GitHub repository
                        │
                        └── Render webhook → build → deploy
                                │
                                └── Production (live site)
```

---

## Data Flow

```
MLB Data API
    │
    └── Cron Job 1 (data collection & parsing)
            │
            └── JSON files → /workspace/barrel-proof/
                    │
                    └── Cron Job 2 (content generation)
                            │
                            └── Gemini API (AI generation)
                                    │
                                    └── Content files → /workspace/barrel-proof/
                                            │
                                            └── git push → Render → Production
```

---

## Stack Change Policy

Changes to the production stack (adding services, changing APIs, modifying hosting) are architectural decisions. They require:

1. Proposal by Claude (Architect)
2. Approval by Allan Turner (Publisher)
3. Implementation by Claude Code (Engineer)

Hermes does not initiate stack changes and does not modify infrastructure configuration.

---

## Related Documents
- `07-SYSTEMS/Hermes Architecture.md`
- `05-AUTOMATION/Pipeline Overview.md`
- `05-AUTOMATION/API Inventory.md`
