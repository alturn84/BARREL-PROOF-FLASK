# Render Flow
**Version:** 1.0
**Last Modified:** 2025-06-06
**Applies To:** Render deployment for Barrel Proof

---

## Overview

Barrel Proof is hosted and deployed via Render. Deployments are triggered automatically on every push to the `main` branch on GitHub.

---

## Deployment Trigger

Push to GitHub `main` → Render webhook → Build triggered automatically.

Hermes does not need to manually trigger deployments under normal conditions. Pushing to GitHub is sufficient.

---

## Deployment Steps (Render-Side)

1. Render receives webhook from GitHub on push
2. Render clones the updated repository
3. Render runs the build command
4. If build succeeds: new version is deployed to production
5. If build fails: previous version continues to serve (no downtime from a failed build)

---

## Hermes Verification After Push

After every push, Hermes must:
1. Monitor Render dashboard or logs to confirm build triggered
2. Confirm build completes without errors (typical build time: [document when known])
3. Spot check the live site — homepage, one game summary, one content section
4. Log confirmation in `06-LOGS/`

Do not log the pipeline as complete until Render deployment is confirmed.

---

## Build Failure

See `03-RUNBOOKS/Render Deployment Failure.md` for full recovery procedure.

In summary:
- Transient failure → manual redeploy via Render dashboard
- Build error (code or config) → escalate to Allan
- Do not modify build configuration without Allan's authorization

---

## Environment Variables on Render

Production environment variables are managed in the Render dashboard. Hermes does not modify Render environment variables. If a missing or incorrect environment variable is suspected as the cause of a build failure, escalate to Allan.

---

## Related Documents
- `01-SOPs/Deployment SOP.md`
- `03-RUNBOOKS/Render Deployment Failure.md`
- `05-AUTOMATION/GitHub Flow.md`
