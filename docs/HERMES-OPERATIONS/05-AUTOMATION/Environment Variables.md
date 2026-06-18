# Environment Variables
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** All environment variables used by the Barrel Proof pipeline

---

## Security Policy

All API keys and sensitive credentials must be stored as environment variables. They must never be:
- Hard-coded in any script
- Committed to GitHub in any file (`.env`, config files, or otherwise)
- Written into any note, document, or log in this vault

---

## Variable Registry

> **Note:** Document variable names only — never document values here. This is a reference for what variables exist and where they are expected.

| Variable Name | Purpose | Required By | Storage Location |
|--------------|---------|------------|-----------------|
| `MLB_API_KEY` | MLB data API authentication | Cron Job 1 | Server environment / `.env` |
| `GEMINI_API_KEY` | Gemini API authentication | Cron Job 2 | Server environment / `.env` |
| `FIRECRAWL_API_KEY` | Firecrawl API authentication for news intake | `scripts/update_news_intake.py` | Server environment / `.env` |

---

## Storage Locations

**Local development (Hermes workspace):**
Environment variables should be set in the server environment or a `.env` file that is listed in `.gitignore`.

**Render (production):**
Environment variables are managed in the Render dashboard under the Barrel Proof service settings. Only Allan Turner manages production environment variables.

---

## Rotation Policy

API keys should be rotated when:
- A key is believed to have been exposed
- A key appears in logs or any committed file
- The service provider recommends rotation

Key rotation is initiated by Allan Turner. Hermes does not rotate keys independently.

---

## If a Key Is Missing or Invalid

Symptoms: API authentication failure, 401 or 403 error responses.

Response:
1. Confirm the variable name matches the expected name in the registry above
2. Do not attempt to locate or reconstruct the key value
3. Escalate to Allan immediately — missing keys require manual intervention

---

## Related Documents
- `05-AUTOMATION/API Inventory.md`
- `05-AUTOMATION/Pipeline Overview.md`
- `05-AUTOMATION/MODEL-001 - Hermes GitHub Copilot Provider Setup.md` — Copilot provider auth rules, including the `GITHUB_TOKEN=ghp_*` conflict issue
- `05-AUTOMATION/FIRECRAWL-002 - Hermes News Intake Operating Rules.md` — `FIRECRAWL_API_KEY` usage rules, source handling, and editorial boundaries
