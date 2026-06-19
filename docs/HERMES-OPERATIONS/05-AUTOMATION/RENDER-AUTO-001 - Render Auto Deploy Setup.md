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

## RENDER-HOOK-002 — Deploy Hook: Operational Finding

**Status: Finding documented. Not yet wired into a wrapper.**

Render Auto-Deploy is unreliable for Barrel Proof — pushes from Hostinger do not consistently trigger automatic deploys. Manual Render Deploy Hook trigger from Hostinger has been verified to work.

`RENDER_DEPLOY_HOOK` lives in `/opt/data/.env` on Hostinger. Hook URL must never be committed to the repo.

**Why the repo wrappers were not patched:**

Inspection of `run_morning_update_with_venv.sh` and `run_dope_sheet_refresh_with_venv.sh` found that **neither wrapper currently owns the git commit/push step**. The git operations happen through the Hermes/Copilot gateway or another external operational path that is not tracked in this repo. Adding `git add / git commit / git push` and a deploy hook call directly to `run_morning_update_with_venv.sh` risks creating duplicate commits or committing partial data if Hermes also commits independently.

**Correct future implementation path:**

1. Identify the real post-push control point — the Hermes/Copilot gateway command or external server-side script that actually owns the git push step
2. Wire `RENDER_DEPLOY_HOOK` into that control point after a confirmed successful push
3. Alternatively, create a dedicated external post-push script (outside this repo, in `/opt/data/scripts/`) that is called explicitly after the Hermes push completes

**Until that is resolved:** manual deploy hook trigger from Hostinger is the verified fallback. The hook URL and `RENDER_DEPLOY_HOOK` variable are in `/opt/data/.env`.

**Alert integration when wired:** `scripts/send_operator_alert.py` should report WARNING on hook failure and INFO on hook success. Hook failure must not block or undo the git push.

---

## RENDER-HOOK-003 — Live Hostinger Post-Push Deploy Hook Wiring

**Status: Live and verified on Hostinger. Not repo-tracked.**

### Background

RENDER-HOOK-002 found that neither repo-tracked wrapper owns the git commit/push step — the real post-push owners are server-only scripts outside this repo. RENDER-HOOK-003 was applied directly on Hostinger to wire deploy hook triggering into those scripts.

### Real Post-Push Owners

The scripts that perform `git commit` and `git push origin main` on the Hostinger server are:

| Script | Workflow |
|--------|---------|
| `/opt/data/scripts/run_morning_update_part1.sh` | Morning update Part 1 |
| `/opt/data/scripts/run_morning_update_part2.sh` | Morning update Part 2 |
| `/opt/data/scripts/run_dope_sheet_refresh.sh` | Dope Sheet afternoon refresh |

Backups of all three scripts were created before patching.

### Shared Deploy Helper

A new server-only helper was created:

```
/opt/data/scripts/trigger_render_deploy.sh
```

This helper:
- Sources `/opt/data/.env` to read `RENDER_DEPLOY_HOOK`
- Never prints or logs the hook URL
- Calls the Render deploy hook with `curl`
- Prints the deploy ID when available in the response
- Sends Telegram alerts via `/opt/data/workspace/barrel-proof/scripts/send_operator_alert.py`
- Is non-blocking — exits 0 on all failure paths
- Is server-only and not tracked in this repo

All three scripts above now call `trigger_render_deploy.sh` only after a confirmed successful `git push origin main`. Deploy trigger failure does not block or undo the push.

### Manual Verification

Verified on Hostinger:

```
/opt/data/scripts/trigger_render_deploy.sh "Manual RENDER-HOOK-003 Test"
```

Result:
```
Render deploy hook triggered
Deploy id: dep-d8qp20q8qa3s73dpbjl0
ALERT SENT: [INFO] Manual RENDER-HOOK-003 Test — Render deploy hook triggered
```

### VPS Rebuild Note

`trigger_render_deploy.sh` and its integration into the three post-push scripts exist only on the Hostinger server. If the VPS is rebuilt or the server scripts are reset, this helper must be recreated and the three scripts must be re-patched. `RENDER_DEPLOY_HOOK` must also be re-added to `/opt/data/.env`.

---

## Related Documents
- `05-AUTOMATION/Render Flow.md` — general deployment sequence and Hermes verification steps
- `03-RUNBOOKS/Render Deployment Failure.md` — recovery steps when deploys fail
- `01-SOPs/Deployment SOP.md` — full deployment SOP
- `05-AUTOMATION/GitHub Flow.md` — commit and push standards
- `05-AUTOMATION/HERMES-ROLE-001 - Hermes Operating Role.md` — Render deploy is listed as a success criterion
