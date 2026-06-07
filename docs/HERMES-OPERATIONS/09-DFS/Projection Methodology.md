# DFS Projection Methodology
**Version:** 1.0
**Last Modified:** 2025-06-06

---

## Overview

This document defines how Hermes approaches daily fantasy sports analysis for Barrel Proof. All DFS analysis follows this methodology to ensure consistency, transparency, and accuracy.

---

## Data Sources

All DFS analysis uses data available through the pipeline or approved external sources. Hermes does not use unverified or estimated data.

| Data Type | Source | Used For |
|-----------|--------|---------|
| Starting pitchers | Cron Job 1 output | Pitcher targeting, matchup analysis |
| Lineup data | Cron Job 1 output / public lineup sources | Batting order context |
| Injury/availability | Cron Job 1 output | Exclusion of unavailable players |
| Park factors | Reference data | Adjusting for venue context |
| Weather | Weather API | Outdoor game adjustments |
| Vegas lines/totals | Vegas data source | Team total and implied run context |

---

## Confidence Grading

Every recommendation includes a confidence level:

| Level | Definition |
|-------|-----------|
| HIGH | Strong data support across multiple indicators. Clear edge exists. |
| MEDIUM | Data is supportive but not conclusive. Reasonable play with acknowledged uncertainty. |
| LOW | Limited data or conflicting signals. Speculative — high upside but elevated risk. |

Confidence levels must reflect the actual data. Do not assign HIGH confidence to justify a recommendation when the data is mixed.

---

## Pitcher Targeting Criteria

Target pitchers who show at least two of the following:
- Favorable matchup (opponent K% in top third of league)
- Home game or favorable park factor
- Recent form: ERA under 3.50 in last 3 starts
- High strikeout rate (K/9 above league average)
- Opposing lineup missing key bats (injury, lineup changes)

Salary must be appropriate for the confidence level. Do not recommend a chalk pitcher at HIGH confidence if salary limits lineup construction.

---

## Hitter Targeting Criteria

Target hitters who show at least two of the following:
- Favorable pitcher matchup (pitcher ERA, xFIP, opponent handedness split)
- High lineup spot (1–5 in batting order)
- Favorable park factor (especially for power hitters)
- Recent hot streak (OPS .850+ in last 7 days)
- Platoon advantage (L vs R or R vs L where supported by data)
- Low salary relative to opportunity

---

## Stacking Logic

When the data supports it, identify a team stack worth considering:
- Team with high implied run total (Vegas total favoring offense)
- Opponent pitcher vulnerable to the hand of the team's lineup
- Park factor favorable to offense
- Recent team offensive form strong

Always note the stack target and the data supporting it. Do not recommend a stack without clear data reasoning.

---

## What Hermes Does Not Do

- Does not guarantee outcomes
- Does not recommend based on name recognition or narrative alone
- Does not use estimated or invented projections
- Does not provide advice that presents DFS as a guaranteed income source
- Does not recommend lineups — provides analysis for the reader to use

---

## Related Documents
- `02-PROMPTS/DFS Prompt.md`
- `09-DFS/DFS Checklist.md`
