# ALERTS-001 — Hermes Telegram Failure Alerts
**Version:** 1.0
**Last Modified:** 2026-06-18
**Applies To:** Hermes operator alerting for morning update and Dope Sheet refresh workflows

---

## Purpose

ALERTS-001 defines the failure states Hermes should report to the publisher through Telegram or an equivalent operator alert path.

The goal is to surface actionable pipeline failures before the publisher discovers them manually — not to replace checker scripts, but to report their results.

---

## Why This Matters

A successful GitHub push and Render deploy is not enough to confirm a clean morning. Barrel Proof needs alerts when the data pipeline is stale, partial, mismatched, or visually incomplete — especially when the publisher is traveling and cannot manually inspect the site.

Current gap: the wrappers (`run_morning_update_with_venv.sh`, `run_dope_sheet_refresh_with_venv.sh`) retry failed scripts once and then continue regardless of exit code. Failures are printed to stdout/logs but nothing surfaces them to the publisher actively.

---

## Alert Philosophy

- Alert on **actionable failure states** — things the publisher can act on
- Avoid **noisy alerts** for normal fallback behavior unless the fallback affects publish quality
- Include the **exact file, script, or check** that failed
- Include **expected vs. actual values** when possible (e.g., game count, gray hitter rate, date mismatch)
- Do **not hide failures** behind a generic "success" summary
- Do **not block data commits** because alert delivery fails
- Alert delivery failures must be **logged**, not silently dropped

---

## Required Alert Categories

### A — Morning Update Status

| Condition | Severity |
|-----------|---------|
| Part 1 / Part 2 completed with all scripts passing | INFO |
| One or more scripts failed after retry | CRITICAL |
| Scripts passed but elapsed time is unusually high | WARNING |

### B — Firecrawl / News Intake

| Condition | Severity |
|-----------|---------|
| `FIRECRAWL_API_KEY` missing from environment | WARNING |
| `news_intake.json` quality is `limited` when `available` or `partial` was expected | WARNING |
| `news_intake.json` date does not match today's slate date | WARNING |
| `source_count` or total item count suspiciously low (e.g., 0 sources returned) | WARNING |
| `update_news_intake.py` exits non-zero | WARNING |

> Firecrawl fallback to `limited` is not itself alertable — it is expected behavior. Alert when `limited` appears after a successful previous day or when item counts suggest a silent scrape failure.

### C — Dope Sheet / Game Intelligence

| Condition | Severity |
|-----------|---------|
| `dope_game_intelligence.json` date does not match today's schedule date | CRITICAL |
| Game Intelligence record count does not match active slate game count | CRITICAL |
| Doubleheader collapse detected (two games at same park as one record) | CRITICAL |
| Gray hitter rate exceeds 45% fail threshold (`check_dope_player_matchups_ready.py`) | CRITICAL |
| Gray hitter rate exceeds 25% warn threshold | WARNING |
| `check_dope_game_intelligence_ready.py` exits non-zero | CRITICAL |
| Arsenal Board or Player Matchup Board sections missing or null | WARNING |

> The 45% gray hitter fail threshold and 25% warn threshold are defined in `scripts/check_dope_player_matchups_ready.py` (`GRAY_MISSING_FAIL_PCT`, `GRAY_MISSING_WARN_PCT`). The checker emits structured `FAIL:`, `WARN:`, and `INFO:` lines — alert integration should parse these.

### D — Player Matchups / Performance

| Condition | Severity |
|-----------|---------|
| `update_dope_player_matchups.py` times out or exits non-zero after retry | CRITICAL |
| `check_dope_player_matchups_ready.py` exits non-zero | CRITICAL |
| Player matchup generation elapsed time above operator warning threshold | WARNING |

### E — Render / Deploy

| Condition | Severity |
|-----------|---------|
| Git push succeeded but no Render deploy observed within expected window | WARNING |
| Render deploy failed (build error or runtime error) | CRITICAL |
| Live site did not update after deploy window | CRITICAL |
| `RENDER_DEPLOY_HOOK` missing if/when explicit hook triggering is implemented | WARNING |

### F — Live Site Smoke Check (Future)

| Condition | Severity |
|-----------|---------|
| `/` does not load | CRITICAL |
| `/dope-sheet` does not load | CRITICAL |
| `/scoreboard` does not load | WARNING |
| `/advance-scout` does not load | WARNING |
| Expected Dope Sheet sections missing from page | WARNING |
| Expected Advanced Scout cards missing from page | WARNING |

---

## Message Formats

### Failure Alert

```
BARREL PROOF ALERT
Severity: CRITICAL / WARNING / INFO
Workflow: Morning Update / Dope Refresh / Render / Live Site
Problem:
Expected:
Actual:
Likely cause:
Next action:
Log/file:
```

### Success Summary

```
BARREL PROOF OK
Workflow:
Date:
Scripts:
Firecrawl:
Games:
Render:
Notes:
```

Keep messages short enough to read on a phone. Include the specific script name or file path in the Problem and Log/file fields — not a generic description.

---

## Severity Levels

| Level | Meaning |
|-------|---------|
| `CRITICAL` | Publish-blocking or likely live-site stale/broken. Requires immediate action. |
| `WARNING` | Degraded data quality but workflow may continue. Publisher should review before next window. |
| `INFO` | Successful completion summary or non-urgent status. |

---

## Implementation Notes

### Current state (as of 2026-06-18)

**No Telegram helper or alert pattern exists in this repo.** The inspection found:

- Zero matches for `telegram`, `TELEGRAM`, `bot_token`, `chat_id`, `sendMessage` in any `.py` or `.sh` file
- Both wrappers (`run_morning_update_with_venv.sh`, `run_dope_sheet_refresh_with_venv.sh`) loop through scripts, retry once on failure, then continue regardless of exit code — failures are printed to stdout/log only
- Checker scripts emit structured `FAIL:`, `WARN:`, `INFO:` lines to stdout with exit code 1 on failure — well-suited to being parsed by a future helper
- No `send_operator_alert.py` or equivalent helper exists

### Future helper: `scripts/send_operator_alert.py`

When implemented, this helper should:

- Read `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from environment only — never hardcoded
- Accept `severity`, `workflow`, and `message` as arguments
- Be **non-blocking** — if alert delivery fails, log the failure and exit 0
- Never commit tokens or chat IDs
- Be callable from wrapper scripts after key failure checkpoints
- Support a structured format matching the message templates above

Shell helpers calling this script should capture checker exit codes explicitly rather than relying on the current retry-and-continue pattern.

**Do not implement until explicitly authorized.** Document this file as a future addition.

---

## Safety Rules

- Never commit `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` to the repo
- Never paste token values into docs, chat logs, or any committed file
- Never make alert delivery block a data commit — alerting is a side effect, not a gate
- Never send repeated identical alerts without a state change — avoid spam on recurring failures
- Alerts must be specific enough that the publisher knows what failed without checking logs
- Alerts report checker results — they do not replace checker scripts

---

## Relationship to Existing Docs

| Document | Relationship |
|----------|-------------|
| `HERMES-ROLE-001` | Defines Hermes as operator/checker — alerts are how Hermes surfaces checker results to the publisher |
| `FIRECRAWL-002` | Defines `available` / `partial` / `limited` quality states — alerts should distinguish these and only fire on unexpected `limited` |
| `RENDER-AUTO-001` | Defines the deploy path — Category E alerts cover the deploy verification gap |
| `05-AUTOMATION/Cron Documentation.md` | Identifies the active wrappers that are the integration points for future alert calls |
| `03-RUNBOOKS/Cron Failure Recovery.md` | Runbook for what to do after an alert fires |

---

## Related Documents
- `05-AUTOMATION/HERMES-ROLE-001 - Hermes Operating Role.md`
- `05-AUTOMATION/FIRECRAWL-002 - Hermes News Intake Operating Rules.md`
- `05-AUTOMATION/RENDER-AUTO-001 - Render Auto Deploy Setup.md`
- `05-AUTOMATION/Cron Documentation.md`
- `03-RUNBOOKS/Cron Failure Recovery.md`
- `03-RUNBOOKS/Render Deployment Failure.md`
