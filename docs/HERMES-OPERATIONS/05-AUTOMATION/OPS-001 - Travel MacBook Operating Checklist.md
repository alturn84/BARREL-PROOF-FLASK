# OPS-001 — Travel / MacBook Operating Checklist
**Version:** 1.0
**Last Modified:** 2026-06-19
**Applies To:** Operating Barrel Proof while away from the home iMac

---

## 1. Purpose

This checklist covers how to operate Barrel Proof while traveling or away from the home iMac, using a MacBook + Hostinger SSH + Telegram + Render dashboard.

The pipeline is designed to run unattended. Most mornings require no action — the checklist tells you what to look for, what is normal, and what to do when something is not.

---

## 2. Normal Morning Expectation

The following should happen automatically on weekday mornings:

**Morning Update Part 1 (≈6:00 AM ET):**
- Hermes/Copilot runs data collection and content generation scripts
- If data changed, `git commit` and `git push origin main` run
- Render deploy hook triggers via `/opt/data/scripts/trigger_render_deploy.sh`
- Telegram alert arrives: deploy hook triggered
- 75-second settle wait
- Live-site smoke check runs against `https://www.barrel-proof-baseball.com`
- Telegram alert arrives: PASS / WARN / FAIL

**Morning Update Part 2 (≈6:15 AM ET):**
- Same sequence as Part 1 for the second batch of content scripts
- Same deploy → smoke → alert path

**Dope Sheet Refresh (afternoon, if scheduled):**
- Same push / deploy / smoke / alert path if data changed
- If nothing changed, no deploy is triggered

If all three complete normally, you will receive six Telegram alerts (two per workflow: deploy trigger + smoke result), plus three workflow completion INFO alerts.

---

## 3. Morning Alert Checklist

Open Telegram and scan for these alerts in order:

**Expected good sequence:**

| Alert | Severity | Meaning |
|-------|----------|---------|
| Morning Update Part 1 workflow completed | INFO | Part 1 scripts passed |
| Render deploy hook triggered | INFO | Push succeeded, deploy started |
| Live site smoke check passed | INFO | Site is live and all routes OK |
| Morning Update Part 2 workflow completed | INFO | Part 2 scripts passed |
| Render deploy hook triggered | INFO | Push succeeded, deploy started |
| Live site smoke check passed | INFO | Site is live and all routes OK |
| Dope Sheet Refresh completed (if scheduled) | INFO | Refresh passed |
| Live site smoke check passed (if data pushed) | INFO | Site still live after refresh deploy |

**Severity guide:**

- **INFO** — normal. No action needed.
- **WARNING** — something needs review but site may still be up. Check the specific workflow and route named in the alert. Do not assume the site is down.
- **CRITICAL** — a workflow failed before completing. Data may be missing or stale. Act before the next cron window.

---

## 4. Manual Live-Site Check

Run on Hostinger to verify the live site independently of cron:

```bash
cd /opt/data/workspace/barrel-proof

python3 scripts/check_live_site_smoke.py \
  --base-url https://www.barrel-proof-baseball.com \
  --timeout 15 \
  --retries 2
```

Non-blocking version (exits 0 regardless of result — safe for scripting):

```bash
python3 scripts/check_live_site_smoke.py \
  --base-url https://www.barrel-proof-baseball.com \
  --timeout 15 \
  --retries 2 \
  --soft-fail
```

**Domain rule:** Always use `https://www.barrel-proof-baseball.com` from Hostinger. The apex/root domain (`barrel-proof-baseball.com`) currently fails DNS resolution from the Hostinger Docker environment. The `www` subdomain resolves correctly.

**Result guide:**

| Result | Meaning |
|--------|---------|
| PASS | Live site is reachable and all key pages render with expected markers |
| WARN | Site loads but section markers are missing — review the Dope Sheet or optional routes |
| FAIL | One or more critical routes failed — check Render deploy status, DNS, and route errors |

---

## 5. Manual Render Deploy Trigger

If a push completed but the site did not update, or if you need to force a fresh deploy:

```bash
# On Hostinger
set -a
source /opt/data/.env
set +a

/opt/data/scripts/trigger_render_deploy.sh "Manual Publisher Deploy"
```

This will:
- Trigger the Render deploy hook
- Send a Telegram INFO alert that the deploy hook was triggered
- Wait 75 seconds
- Run a live-site smoke check against `https://www.barrel-proof-baseball.com`
- Send a Telegram INFO (PASS) or WARNING (WARN/FAIL) alert with the smoke result

> Do not print, paste, or log `RENDER_DEPLOY_HOOK`. The value is in `/opt/data/.env` and must stay there.

---

## 6. MacBook Repo Sync Checklist

Before giving Claude Code new work on the MacBook, sync the local repo:

```bash
cd "/Users/allanturner/BARREL PROOF"
git status --short
git fetch origin
git log --oneline HEAD..origin/main
git rebase origin/main
git status --short
```

**Rules:**

- If only `Homepage/barrel-proof-boxscores.html` is dirty, that is known local churn — it can be restored (`git restore "Homepage/barrel-proof-boxscores.html"`) when appropriate
- Do not stash unless explicitly needed
- Do not touch existing stashes
- Stop if unfamiliar files are dirty — investigate before rebasing
- Always pull/rebase before starting new Claude Code work to avoid diverged commits

---

## 7. Hostinger Repo Dirty-State Recovery

If Hermes updates ran but something interrupted before the commit, the Hostinger repo may have uncommitted generated data. Common dirty files:

```
Site Data/dope-sheet-data.json
Site Data/dope_game_intelligence.json
Site Data/dope_pitcher_matchups.json
Site Data/dope_player_matchups.json
Site Data/odds.json
Site Data/mlbam_lookup_cache.json
```

To inspect safely:

```bash
cd /opt/data/workspace/barrel-proof
git status --short
git diff --name-only
```

**Rules:**

- Do not blindly restore generated data — it may be fresh Hermes output that should be committed
- If the dirty files are fresh outputs from the current morning, commit them with a clear refresh message before rebasing (see Section 8)
- If unsure what changed or why, stop and ask before taking action

---

## 8. Manual Generated-Data Commit Pattern (Hostinger)

If you need to manually commit and push generated data:

```bash
cd /opt/data/workspace/barrel-proof
git fetch origin
git status --short

# Stage only the specific files you intend to commit
git add "Site Data/dope-sheet-data.json"
# ... add others as needed

git diff --cached --name-only
git commit --no-verify -m "refresh dope sheet intelligence data"
git rebase origin/main
git push origin main
```

**After a manual push:** The patched Hostinger cron scripts call `trigger_render_deploy.sh` automatically after their own `git push`, but a manual push bypasses them. To trigger Render after a manual commit/push:

```bash
/opt/data/scripts/trigger_render_deploy.sh "Manual Post-Push Deploy"
```

This runs the full deploy → 75s wait → smoke check → Telegram alert sequence.

---

## 9. Render Dashboard Checklist

When checking Render manually:

- Use the **`barrel-proof-flask`** service — not `barrel-proof-automation`
- After a deploy hook trigger, check the **Deploys** tab to confirm the deploy started and succeeded
- Render Auto-Deploy is unreliable for Barrel Proof and is not the primary mechanism — the deploy hook is the verified path
- Do not use workspace-level Render webhook settings for this workflow

---

## 10. Do Not Touch List

| Rule | Reason |
|------|--------|
| Do not paste tokens, hook URLs, or key values into chat, docs, commits, or screenshots | Secret exposure risk — values in `/opt/data/.env` must stay there |
| Do not edit `/opt/data/.env` unless specifically rotating or adding a credential | Accidental edit can break all cron workflows |
| Do not modify server scripts without backing them up first | Server scripts are not repo-tracked; no recovery if overwritten |
| Do not trigger the full morning scripts manually unless explicitly instructed | Running Part 1/Part 2 manually risks double-committing or stale data |
| Do not run destructive git commands (`reset --hard`, `push --force`, `clean -f`) | Risk of lost work or diverged branches |
| Do not touch stashes | Existing stashes may contain in-progress work |
| Do not commit `Homepage/barrel-proof-boxscores.html` churn | Known local churn; not a real change |
| Do not use the apex domain from Hostinger for smoke checks | `barrel-proof-baseball.com` fails DNS from Hostinger Docker; use `www` |

---

## 11. Emergency Triage

### Telegram CRITICAL alert

1. Note the workflow name in the alert (Part 1 / Part 2 / Dope Refresh)
2. SSH to Hostinger and check the script log output
3. Run `git status --short` in `/opt/data/workspace/barrel-proof`
4. Do not deploy blindly if data is stale — identify what failed first
5. See `03-RUNBOOKS/Cron Failure Recovery.md` for step-by-step recovery

---

### Deploy hook triggered but smoke check WARN or FAIL

1. Check the Render Deploys tab — the build may still be in progress
2. Wait 2–3 minutes and run a manual smoke check (Section 4)
3. Use `https://www.barrel-proof-baseball.com` (www, not apex)
4. If still failing, open the failing route in a browser to see the actual error
5. If Render shows a successful deploy but the route fails, check the app logs in the Render dashboard

---

### No Telegram alerts arrive

1. SSH to Hostinger and verify the Hermes gateway/Copilot process is running
2. Check that `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in `/opt/data/.env` (confirm they exist — do not print values)
3. Run a dry-run alert to confirm the helper works:

```bash
cd /opt/data/workspace/barrel-proof
python3 scripts/send_operator_alert.py \
  --dry-run \
  --severity INFO \
  --workflow "Manual Alert Test" \
  --problem "Testing alert pipeline from travel"
```

4. If dry-run prints correctly but alerts are still not arriving, check `BARREL_PROOF_ALERTS_ENABLED` — it must not be set to `0`, `false`, or `off`

---

### GitHub updated but live site did not change

1. Confirm the push appears in the GitHub commit log
2. Manually trigger the Render deploy (Section 5)
3. Check the Render Deploys tab for the new deploy
4. Run a manual smoke check after the deploy completes (Section 4)

---

## 12. Current Known Quirks

| Quirk | Status |
|-------|--------|
| Render Auto-Deploy is unreliable | Replaced by explicit deploy hook in server-only scripts |
| Hostinger resolves `www.barrel-proof-baseball.com` but not apex `barrel-proof-baseball.com` | Use `www` for all server-side smoke checks until DNS is confirmed |
| Server-only script patches must be recreated on VPS rebuilds | `trigger_render_deploy.sh`, ERR traps, alert wiring are not repo-tracked |
| Operator alert dates use Eastern Time | Fixed in ALERTS-DATE-001; `zoneinfo` with UTC-5 fallback |
| `Homepage/barrel-proof-boxscores.html` is chronically dirty on Mac | Known local churn; restore without staging when needed |

---

## 13. Related Documents

| Document | Purpose |
|----------|---------|
| `05-AUTOMATION/MODEL-001 - Hermes GitHub Copilot Provider Setup.md` | Copilot auth, PAT conflict rules, gateway restart |
| `05-AUTOMATION/FIRECRAWL-002 - Hermes News Intake Operating Rules.md` | Firecrawl source intake rules, quality states |
| `05-AUTOMATION/HERMES-ROLE-001 - Hermes Operating Role.md` | Hermes operator role, success criteria, failure patterns |
| `05-AUTOMATION/RENDER-AUTO-001 - Render Auto Deploy Setup.md` | Deploy hook setup, RENDER-HOOK-003 live wiring, DEPLOY-QA-002 smoke integration |
| `05-AUTOMATION/ALERTS-001 - Hermes Telegram Failure Alerts.md` | Alert categories, message formats, ALERTS-003 live wiring, ALERTS-DATE-001 ET fix |
| `05-AUTOMATION/DEPLOY-QA-001 - Live Site Smoke Checks.md` | Smoke check helper reference, DEPLOY-QA-001B DNS finding, DEPLOY-QA-002 live wiring |
| `05-AUTOMATION/Cron Documentation.md` | Cron job schedules, script responsibilities, sequencing rules |
| `05-AUTOMATION/Environment Variables.md` | Variable registry including `BARREL_PROOF_SITE_URL` and all Telegram/Render vars |
| `03-RUNBOOKS/Cron Failure Recovery.md` | Step-by-step recovery for cron failures |
| `03-RUNBOOKS/Render Deployment Failure.md` | Recovery when Render deploys fail |
