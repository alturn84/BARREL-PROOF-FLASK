# DFS Confidence Grading
**Version:** 1.0
**Last Modified:** 2025-06-06

---

## Overview

Every DFS recommendation published by Hermes includes a confidence level. This document defines what each level means, what data thresholds justify each level, and how to apply grading consistently.

---

## Confidence Levels

### HIGH

**Definition:** Strong, multi-factor data support. The edge is clear and not dependent on a single uncertain variable.

**Criteria — Pitcher (all three should be met):**
- Opponent K% ranks in top 10 of league (bottom 10 for hitters)
- Pitcher ERA or FIP in top 20% over last 5 starts
- Favorable park factor or neutral venue
- Full health confirmed — no injury flags

**Criteria — Hitter (at least three should be met):**
- Favorable pitcher matchup (pitcher ERA 4.50+ or xFIP 4.25+)
- Lineup spot 1–4
- Batting over .280 or OPS over .850 in last 14 days
- Platoon advantage confirmed
- Favorable park factor
- Salary at or below market rate for projected output

**Use sparingly.** HIGH confidence means the data is compelling across multiple dimensions. If you're assigning HIGH to every recommendation, the grading is not calibrated.

---

### MEDIUM

**Definition:** Supportive data with one or more uncertainty factors. A reasonable play, but not a slam dunk.

**Criteria:** Two or more positive indicators from the HIGH criteria, with one or more offsetting factors such as:
- Moderate salary requiring a strong performance to pay off
- One positive matchup indicator but limited supporting data
- Recent form is good but sample is small (last 3–5 games)
- Park is neutral rather than favorable
- Lineup spot confirmed but batting lower in the order

MEDIUM is the most common grade. Most recommendations fall here.

---

### LOW

**Definition:** Limited data, conflicting signals, or a speculative upside play. Higher risk, higher potential reward.

**Use cases:**
- Punt play / salary saver where the value is purely financial
- Streaky player whose recent form is hot but history is inconsistent
- Weather concern exists but game is not yet postponed
- Lineup spot uncertain at time of analysis
- Small sample size batter vs. pitcher matchup (fewer than 10 PA)

LOW confidence plays should always be framed as such in the output. Do not present a LOW confidence play as anything other than speculative.

---

## Grading Checklist

Before assigning a confidence level, answer these:

1. How many positive indicators does this player have? (1 = LOW, 2 = MEDIUM, 3+ = HIGH candidate)
2. Are there any material uncertainty factors? (Injury, weather, unconfirmed lineup, small sample)
3. Does the salary require the player to exceed their baseline to pay off?
4. Is the edge primarily based on one data point or multiple independent signals?

If answers point to conflicting grades: default to the lower grade. Overconfidence in DFS analysis is more harmful than under-confidence.

---

## Related Documents
- `09-DFS/Projection Methodology.md`
- `09-DFS/DFS Checklist.md`
- `02-PROMPTS/DFS Prompt.md`
