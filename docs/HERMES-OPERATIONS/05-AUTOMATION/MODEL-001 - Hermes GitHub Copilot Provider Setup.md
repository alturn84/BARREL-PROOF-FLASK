# MODEL-001 — Hermes GitHub Copilot Provider Setup
**Version:** 1.0
**Last Modified:** 2026-06-18
**Applies To:** Hermes model provider configuration on Hostinger

---

## Purpose

Hermes currently uses **GitHub Copilot** as its model provider. This replaced the prior Gemini configuration. This document covers the setup, auth requirements, known working state, and troubleshooting for the Copilot provider.

---

## Why This Matters

GitHub Copilot is being used as Hermes' operator/engineering model for:

- Repo edits and file modifications
- Script debugging and repair
- Cron job and wrapper diagnostics
- Automation pipeline troubleshooting
- Telegram-driven operations and commands
- Code-aware problem solving on Hostinger

> **Editorial quality note:** The Copilot provider has not been validated for editorial writing quality. Do not assume it produces the same output as Gemini for content generation tasks. Writing quality should be evaluated separately before any editorial use.

---

## Required Auth Rule

**Do not use a classic GitHub Personal Access Token (PAT) for the Copilot provider.**

| Rule | Detail |
|------|--------|
| Classic PAT format | `ghp_...` |
| Classic PAT variable | `GITHUB_TOKEN=ghp_*` in `/opt/data/.env` |
| Problem | Classic PATs are rejected by the Copilot API endpoint |
| Error message | `Personal Access Tokens are not supported for this endpoint` |
| Root cause | The old `GITHUB_TOKEN` entry overrides the Copilot OAuth credential |

**If you see the error `Personal Access Tokens are not supported for this endpoint`:**

1. Check `/opt/data/.env` for any line beginning with `GITHUB_TOKEN=ghp_`
2. Remove that line
3. Restart the Hermes gateway (see Known Good Setup below)

Classic PAT entries left in `/opt/data/.env` will override the Copilot OAuth credential even after `hermes setup model` has been run successfully.

---

## Known Good Setup

Follow these steps in order when configuring or re-configuring the Copilot provider:

1. Run the model setup command:
   ```
   hermes setup model
   ```

2. Select **GitHub Copilot** as the provider when prompted.

3. Complete the Copilot-compatible auth flow (OAuth — not a classic PAT).

4. Check `/opt/data/.env` for any existing `GITHUB_TOKEN=ghp_*` entry and remove it if present.

5. Restart the Hermes gateway:
   ```
   HERMES_ALLOW_ROOT_GATEWAY=1 nohup hermes gateway run --replace > /opt/data/logs/gateway.log 2>&1 &
   ```

6. Verify with a Telegram test command.

7. If the test fails, check the logs immediately (see Logs to Check below).

---

## Logs to Check

| Log File | Purpose |
|----------|---------|
| `/opt/data/logs/gateway.log` | Gateway startup, provider initialization, request/response errors |
| `/opt/data/logs/errors.log` | Runtime errors from Hermes operations |

Start with `gateway.log` for any auth-related failures — it will contain the provider rejection message if the token is wrong.

---

## Usage Tracking

GitHub Copilot usage counts against the connected GitHub account's Copilot plan.

Check usage at:

**GitHub → Profile → Settings → Billing and plans → Usage this month**

Monitor this periodically. If usage unexpectedly spikes or approaches limits, escalate to Allan Turner.

---

## Troubleshooting Checklist

- [ ] Is the Hermes gateway running?
- [ ] Does `/opt/data/.env` still contain a `GITHUB_TOKEN=ghp_*` line?
- [ ] Was the gateway restarted after changing the provider or modifying `.env`?
- [ ] Did the Telegram test return a real response from Copilot?
- [ ] Are auth or request errors visible in `gateway.log`?
- [ ] Are runtime errors visible in `errors.log`?
- [ ] If auth breaks after a rebuild or server restart: re-run `hermes setup model`, select GitHub Copilot, and remove any conflicting `GITHUB_TOKEN` entries from `/opt/data/.env` before restarting the gateway.

---

## Related Documents
- `05-AUTOMATION/Environment Variables.md`
- `03-RUNBOOKS/Gemini API Quota Failure.md` — prior provider runbook, archived context
- `07-SYSTEMS/Production Stack.md`
