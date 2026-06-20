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

## Current Status

Helper exists at `scripts/check_live_site_smoke.py` and is repo-tracked.

**Not yet wired into Hostinger cron scripts.** This must be added as a post-deploy step after `trigger_render_deploy.sh` calls on the Hostinger server. That wiring is planned for DEPLOY-QA-002.

When wired on Hostinger:
- The helper should run after the Render deploy hook triggers and a short settle delay
- `--soft-fail` should be used so smoke check failures do not block cron completion
- Results should be piped to `send_operator_alert.py` for Telegram reporting

---

## VPS Rebuild Note

`scripts/check_live_site_smoke.py` is repo-tracked and will be present after any `git pull` on Hostinger. No server-specific recreation is needed for this helper — only for the Hostinger cron wiring (DEPLOY-QA-002, when added).

---

## Related Documents
- `05-AUTOMATION/RENDER-AUTO-001 - Render Auto Deploy Setup.md` — deploy hook that triggers before smoke check
- `05-AUTOMATION/ALERTS-001 - Hermes Telegram Failure Alerts.md` — smoke check results are a future alert source
- `03-RUNBOOKS/Render Deployment Failure.md` — recovery if smoke check reveals site down
