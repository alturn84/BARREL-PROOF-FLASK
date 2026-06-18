# RENDER-AUTO-001 — Render Auto Deploy Setup
**Version:** 1.0
**Last Modified:** 2026-06-18
**Applies To:** Render deployment for the barrel-proof-flask service

---

## Purpose

This note documents how Barrel Proof gets from a successful GitHub push to a live Render deployment — and what is required for that path to work automatically without manual intervention.

See also `05-AUTOMATION/Render Flow.md` for the general deployment sequence. This note covers the specific Auto-Deploy and Deploy Hook setup that enables fully automated morning updates.

---

## Current Production Service

| Field | Value |
|-------|-------|
| Render service name | `barrel-proof-flask` |
| Runtime | Python 3 |
| Start command | `gunicorn app:app` |
| Region | Ohio |
| Auto-Deploy setting | On Commit (target state) |
| Branch | `main` |

> **Note:** Do not confuse with `barrel-proof-automation` — that is a separate service and is not the deployment target for the public site.

---

## Why This Matters

Hermes can update data, pass all checker scripts, commit, and push to GitHub — but the live website only updates after Render deploys.

This solves the **travel problem**: the publisher should not need to be at the home computer to manually trigger a deploy after morning updates. With Auto-Deploy enabled on the `barrel-proof-flask` service, a push to `main` is sufficient to update the live site.

When Auto-Deploy is Off, GitHub and the live site can diverge. Hermes' data updates are correct on GitHub but invisible to readers until a manual deploy is triggered.

---

## Auto-Deploy Behavior

- **Auto-Deploy must be set to On Commit** for the `barrel-proof-flask` service in the Render dashboard.
- When Hermes pushes to `main`, Render detects the new commit and begins a deploy automatically.
- If Auto-Deploy is Off, pushes from Hermes will not update the live site without manual intervention.
- Allan Turner manages the Auto-Deploy setting in the Render dashboard. Hermes does not change Render service configuration.

To verify Auto-Deploy is enabled: Render dashboard → `barrel-proof-flask` → Settings → Build & Deploy → Auto-Deploy.

---

## Deploy Hook

The `barrel-proof-flask` service has a private Deploy Hook URL available in the Render dashboard.

| Field | Detail |
|-------|--------|
| What it is | A private URL that triggers a deploy of the service when called |
| Where it is stored | Hostinger `/opt/data/.env` as `RENDER_DEPLOY_HOOK` |
| Who manages it | Allan Turner — Hermes does not rotate or expose this value |
| Current use | Reserved for future explicit Hermes-triggered deploys |
| Committed to repo | Never |
| Printed in chat or docs | Never |

**Deploy Hook vs. Render Webhook:** These are different things. Deploy Hooks are incoming triggers — calling the hook URL starts a deploy. Render Webhooks are outgoing event notifications sent by Render when deploy events occur, and may require a higher plan tier. This workflow uses Deploy Hooks only.

---

## Intended Future Workflow

The desired end-to-end automated deployment sequence:

```
Hermes morning update runs
        │
        ▼
All checker scripts pass (exit 0)
        │
        ▼
Generated data committed to repo
        │
        ▼
Commit pushed to origin/main
        │
        ▼
Render Auto-Deploy triggers on commit  ← primary path (active now)
        │
        ▼
[Future] Hermes calls RENDER_DEPLOY_HOOK as explicit fallback
        │
        ▼
[Future] Hermes runs live-site smoke checks
        │
        ▼
[Future] Telegram alert reports deploy status and check results
```

The Auto-Deploy path is the primary mechanism. The Deploy Hook is a future explicit fallback for cases where the auto-trigger does not fire or a forced re-deploy is needed. Do not patch wrappers to call the hook until that step is explicitly authorized.

---

## Troubleshooting Checklist

- [ ] Is the service `barrel-proof-flask` (not `barrel-proof-automation`)?
- [ ] Is Auto-Deploy set to On Commit in the Render dashboard?
- [ ] Is the branch set to `main`?
- [ ] Did Hermes actually push a commit to `origin/main`?
- [ ] Did Render show a new deploy entry after the push?
- [ ] Did the deploy succeed (no build errors in Render logs)?
- [ ] Does the live site show the updated data?
- [ ] Is `RENDER_DEPLOY_HOOK` present in `/opt/data/.env` on Hostinger?
- [ ] Was the hook value kept out of Git history and chat logs?
- [ ] Are Render service logs clean (no runtime errors post-deploy)?

---

## Safety Rules

- **Never paste the Deploy Hook URL into chat, logs, or any document** — including this one
- **Never commit the Deploy Hook to GitHub** in any form (env file, config, hardcoded string)
- **Do not deploy from `barrel-proof-automation`** — that service is not the public site target
- **Do not use workspace-level Render webhook settings** for this workflow
- **A failed deploy must be reported clearly** — do not hide or swallow deploy failures in wrapper scripts
- **Deploy automation must not become a blocking condition for data commits** — if the deploy step fails, the commit still stands; report the deploy failure separately
- Manual redeploy via the Render dashboard is always available as a fallback — see `03-RUNBOOKS/Render Deployment Failure.md`

---

## Related Documents
- `05-AUTOMATION/Render Flow.md` — general deployment sequence and Hermes verification steps
- `03-RUNBOOKS/Render Deployment Failure.md` — recovery steps when deploys fail
- `01-SOPs/Deployment SOP.md` — full deployment SOP
- `05-AUTOMATION/GitHub Flow.md` — commit and push standards
- `05-AUTOMATION/HERMES-ROLE-001 - Hermes Operating Role.md` — Render deploy is listed as a success criterion
