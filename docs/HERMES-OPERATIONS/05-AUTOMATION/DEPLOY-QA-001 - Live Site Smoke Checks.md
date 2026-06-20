# DEPLOY-QA-001 — Live Site Smoke Checks
**Version:** 1.0
**Last Modified:** 2026-06-19
**Applies To:** Post-deploy verification for the live Barrel Proof website

---

## Purpose

`scripts/check_live_site_smoke.py` checks that key public routes on the live Barrel Proof site return HTTP 200 and contain expected content markers after a Render deploy.

This helper prints results only — it does not call Telegram, trigger Render, or take any action. Alert wiring will be added in DEPLOY-QA-002.

---

## Default Base URL

```
https://barrel-proof-baseball.com
```

Override via:
- CLI: `--base-url https://...`
- Env var: `BARREL_PROOF_SITE_URL`

---

## Checked Routes

### Critical routes — failures exit 1

| Route | Path | Required marker(s) | Warning markers |
|-------|------|--------------------|----------------|
| Homepage | `/` | Any of: `Page 1`, `Game of the Day`, `Around the League`, `Barrel Proof` | — |
| Dope Sheet | `/dope-sheet` | `Dope Sheet` or `The Dope Sheet` | `Game Intelligence`, `Pitcher Arsenal`, `Player Matchup`, `Lineup Matchup`, `Arsenal Board` |
| Scoreboard | `/scoreboard` | Any of: `Scoreboard`, `Today's Board`, `Final` | — |
| Advanced Scout | `/advance-scout` | Any of: `Advanced Scout`, `Series`, `Scout` | — |

**Dope Sheet warning markers:** The page must load (HTTP 200 + required marker), but if none of the section-level markers are found, the check returns WARN rather than FAIL — section labels may change without the page breaking.

### Optional routes — failures produce WARN only (except HTTP 500 = FAIL)

| Route | Path |
|-------|------|
| Archive | `/archive` |
| Players | `/players` |
| Teams | `/teams` |

---

## Exit Codes

| Exit code | Meaning |
|-----------|---------|
| `0` | PASS — all critical routes loaded with expected markers |
| `0` | WARN — no critical failures, but some warnings exist |
| `1` | FAIL — at least one critical route failed (HTTP error, timeout, or missing required marker) |
| `0` | Always, when `--soft-fail` is set |

---

## CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--base-url` | `https://barrel-proof-baseball.com` | Base URL to check |
| `--timeout` | `15` | Request timeout in seconds |
| `--retries` | `2` | Retry count on network failure |
| `--json` | off | Print full JSON summary to stdout after text output |
| `--soft-fail` | off | Always exit 0 — use for non-blocking cron integration |

---

## Command Examples

Standard check:
```bash
python3 scripts/check_live_site_smoke.py
```

With explicit URL and timeout:
```bash
python3 scripts/check_live_site_smoke.py \
  --base-url https://barrel-proof-baseball.com \
  --timeout 15 \
  --retries 2
```

With JSON output:
```bash
python3 scripts/check_live_site_smoke.py --json
```

Non-blocking (never fails cron):
```bash
python3 scripts/check_live_site_smoke.py --soft-fail
```

---

## Output Format

Text output per route:
```
OK: [Homepage] / — Marker found: 'Barrel Proof'
WARN: [Dope Sheet] /dope-sheet — Page loaded but none of expected section markers found
FAIL: [Scoreboard] /scoreboard — HTTP 404 (expected 200)
```

Final summary:
```
LIVE SITE SMOKE CHECK
Base URL: https://barrel-proof-baseball.com
Critical failures: 0
Warnings: 1
Result: WARN
```

---

## DEPLOY-QA-001B — Hostinger Verification

**Status: Verified on Hostinger. PASS.**

### DNS Finding

The apex/root domain does not resolve from inside the Hostinger Docker environment:

```
barrel-proof-baseball.com  => ERROR: gaierror(-5, 'No address associated with hostname')
www.barrel-proof-baseball.com => 216.24.57.9  ← resolves
google.com  => resolved
render.com  => resolved
```

Hostinger DNS works generally, but the apex Barrel Proof domain fails to resolve from that container. The `www` subdomain resolves correctly.

### Operational Base URL (Hostinger)

Use this base URL for all server-side smoke checks until apex DNS is fixed:

```
https://www.barrel-proof-baseball.com
```

Do not use `https://barrel-proof-baseball.com` (apex/root) in any Hostinger cron or server-side script.

### Verified Smoke Check Result

Run on Hostinger with `--base-url https://www.barrel-proof-baseball.com`:

```
OK: [Homepage] / — Marker found: 'Game of the Day'
OK: [Dope Sheet] /dope-sheet — Marker found: 'Dope Sheet'
OK: [Scoreboard] /scoreboard — Marker found: 'Scoreboard'
OK: [Advanced Scout] /advance-scout — Marker found: 'Advanced Scout'
OK: [Archive] /archive — HTTP 200
OK: [Players] /players — HTTP 200
OK: [Teams] /teams — HTTP 200

LIVE SITE SMOKE CHECK
Base URL: https://www.barrel-proof-baseball.com
Critical failures: 0
Warnings: 0
Result: PASS
```

Both normal run and `--soft-fail` exited 0.

### DEPLOY-QA-002 Note

Future cron wiring (DEPLOY-QA-002) should call:

```bash
python3 scripts/check_live_site_smoke.py \
  --base-url https://www.barrel-proof-baseball.com \
  --soft-fail
```

Use the `www` base URL until apex DNS from Hostinger is confirmed working.

---

## DEPLOY-QA-002 — Live Post-Deploy Smoke Check Wiring

**Status: Live and verified on Hostinger. Not repo-tracked.**

### What Was Patched

The server-only Render deploy helper was updated to run a live-site smoke check after triggering a deploy:

```
/opt/data/scripts/trigger_render_deploy.sh
```

This helper is not tracked in this repo. It was patched directly on the Hostinger server.

### Live Behavior

After `trigger_render_deploy.sh` triggers the Render deploy hook, it now:

1. Sends a Telegram INFO alert that the deploy hook was triggered
2. Waits **75 seconds** for Render to complete the build and serve the updated site
3. Runs:

```bash
python3 scripts/check_live_site_smoke.py \
  --base-url https://www.barrel-proof-baseball.com \
  --timeout 15 \
  --retries 2 \
  --soft-fail
```

4. Prints smoke check output to the log
5. Sends **Telegram INFO** alert if the smoke check result is PASS
6. Sends **Telegram WARNING** alert if the smoke check result is WARN or FAIL
7. Never blocks the pipeline — smoke check and alert delivery failures are logged but do not abort

### Base URL Behavior

- Default base URL: `https://www.barrel-proof-baseball.com`
- `BARREL_PROOF_SITE_URL` env var overrides the default if set
- Do **not** use the apex domain (`barrel-proof-baseball.com`) from Hostinger — it fails DNS resolution from the Hostinger Docker environment (see DEPLOY-QA-001B)
- When apex DNS is confirmed working, `BARREL_PROOF_SITE_URL` can be removed or updated without patching the helper

### Manual Verification

Verified on Hostinger:

```
/opt/data/scripts/trigger_render_deploy.sh "Manual DEPLOY-QA-002 Test"
```

Result:
```
Render deploy hook triggered
Deploy ID: dep-d8qu7nm7r5hc73dlhd5g
Telegram alert sent: deploy triggered
[75 second wait]
OK: [Homepage] / — Marker found: 'Game of the Day'
OK: [Dope Sheet] /dope-sheet — Marker found: 'Dope Sheet'
OK: [Scoreboard] /scoreboard — Marker found: 'Scoreboard'
OK: [Advanced Scout] /advance-scout — Marker found: 'Advanced Scout'
OK: [Archive] /archive — HTTP 200
OK: [Players] /players — HTTP 200
OK: [Teams] /teams — HTTP 200

LIVE SITE SMOKE CHECK
Base URL: https://www.barrel-proof-baseball.com
Critical failures: 0
Warnings: 0
Result: PASS

Telegram alert sent: live site smoke check passed
```

### VPS Rebuild Note

`trigger_render_deploy.sh` is server-only. If the VPS is rebuilt or the server scripts are reset, the 75-second wait and smoke check call must be re-added to `trigger_render_deploy.sh`. `BARREL_PROOF_SITE_URL` should also be set in `/opt/data/.env` if apex DNS is still unresolved at that time.

---

## Current Status

Helper exists at `scripts/check_live_site_smoke.py` and is repo-tracked. Verified PASS on Hostinger (DEPLOY-QA-001B). Post-deploy wiring is live in `trigger_render_deploy.sh` on Hostinger (DEPLOY-QA-002).

---

## VPS Rebuild Note

`scripts/check_live_site_smoke.py` is repo-tracked and will be present after any `git pull` on Hostinger. No server-specific recreation is needed for this helper — only for the Hostinger cron wiring (DEPLOY-QA-002, when added).

---

## Related Documents
- `05-AUTOMATION/RENDER-AUTO-001 - Render Auto Deploy Setup.md` — deploy hook that triggers before smoke check
- `05-AUTOMATION/ALERTS-001 - Hermes Telegram Failure Alerts.md` — smoke check results are a future alert source
- `03-RUNBOOKS/Render Deployment Failure.md` — recovery if smoke check reveals site down
