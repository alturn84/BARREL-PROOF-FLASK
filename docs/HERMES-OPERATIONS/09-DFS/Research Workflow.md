# DFS Research Workflow
**Version:** 1.0
**Last Modified:** 2025-06-06

---

## Overview

This document defines the step-by-step research workflow Hermes follows when producing DFS analysis for Barrel Proof. Following this workflow in order ensures nothing is missed and that all recommendations are grounded in current, verified data.

---

## Step 1 — Confirm the Slate

Before any analysis begins:
- Confirm today's game count
- Note start times (early games may have tighter lineup lock windows)
- Flag any weather-affected games
- Note slate size — full slate (10+ games) vs. small slate (under 6 games) requires different approaches

---

## Step 2 — Gather Required Data

Confirm availability of all required data inputs:

| Data | Source | Required? |
|------|--------|----------|
| Starting pitchers | Cron Job 1 / public sources | Required |
| Confirmed lineups | Public lineup sources | Required |
| Injury report | Cron Job 1 output | Required |
| Vegas lines and totals | Vegas data source | Required |
| Weather data | Weather API | Required for outdoor games |
| Park factors | Reference data | Required |
| Recent player stats | Cron Job 1 output | Required |
| Batter vs. pitcher data | Cron Job 1 output | If available |
| DFS salaries (FD/DK) | Platform data | Required |

If any required data is unavailable: note the gap in the output. Do not estimate.

---

## Step 3 — Assess the Slate Context

With data in hand, establish the slate context:
- Which games have the highest implied totals? (Vegas)
- Which venues are hitter-friendly or pitcher-friendly today?
- Are there any weather concerns that change the expected scoring environment?
- Which teams are on favorable rest situations?

This slate context frames everything that follows.

---

## Step 4 — Pitcher Analysis

For each starting pitcher on the slate:
1. Check recent form (last 3–5 starts): ERA, IP, K rate
2. Check opponent offensive context: K%, OPS against RHP or LHP
3. Check salary vs. expected output
4. Apply grading criteria from `09-DFS/Confidence Grading.md`
5. Select 2–3 targets

---

## Step 5 — Hitter Analysis

For each potential hitter target:
1. Check batting order position (confirmed lineup)
2. Check matchup: pitcher ERA, xFIP, opposing handedness splits
3. Check recent form: last 7–14 days
4. Check park factor for today's venue
5. Check salary — is it priced appropriately?
6. Apply grading criteria
7. Select 4–6 targets across price tiers

---

## Step 6 — Stack Identification

Review teams for potential stack opportunities:
- Team implied run total 5.0 or higher
- Favorable pitcher matchup for the lineup's primary hand
- Favorable park factor
- At least 3 viable hitters in the 1–6 spots
- If a stack exists: note it in the output with supporting data

---

## Step 7 — Value Play Identification

From remaining options, identify 2–3 low-salary plays:
- Why is the salary undervalued relative to the opportunity?
- What is the specific upside path for this player today?
- What are the risk factors?

---

## Step 8 — Compile and Grade

Compile all recommendations. Assign confidence levels per `09-DFS/Confidence Grading.md`. Review the complete output:
- No recommendation without a confidence level
- No recommendation without cited data
- No duplicate data points used to inflate confidence
- Slate overview drafted

---

## Step 9 — Output Validation

Run through `09-DFS/DFS Checklist.md` before submitting.

---

## Related Documents
- `09-DFS/Projection Methodology.md`
- `09-DFS/Confidence Grading.md`
- `09-DFS/DFS Checklist.md`
- `02-PROMPTS/DFS Prompt.md`
