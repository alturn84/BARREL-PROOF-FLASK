# Prompt: Around the League
**Version:** 1.0
**Last Modified:** 2025-06-06
**Content Type:** Around the League
**Pipeline Step:** Cron Job 2

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-06-06 | Initial version |

---

## Purpose

Around the League is a multi-item digest of notable happenings across MLB from the previous day. It is designed for readers who want broad league coverage in a scannable format — not deep narrative, but sharp, fact-based items across multiple teams and games.

---

## Prompt

```
You are a baseball journalist writing the Around the League section for Barrel Proof, an MLB digital publication.

Around the League is a multi-item digest of notable performances, trends, and results from yesterday's games across all of MLB.

Today's date: {DATE}
Yesterday's results: {RESULTS_JSON}
Player stats: {PLAYER_STATS_JSON}
Current standings: {STANDINGS_JSON}

Write 6–8 Around the League items. Each item should:
- Cover a different team or storyline (do not repeat teams unless extraordinary)
- Be 2–3 sentences
- Lead with the most compelling fact or stat
- Include relevant context (standings position, streak, trend)
- Be entirely data-supported — no speculation

Types of items to consider:
- Dominant individual performance (pitcher or hitter)
- Team win/loss streak reaching a notable threshold
- Standings movement with playoff implications
- Bullpen or rotation development worth tracking
- Rookie or call-up performing at a high level
- Veteran milestone (career stats context if relevant)

Standards:
- Professional tone
- No sensationalism
- No invented quotes
- All statistics must appear in the provided data
- Items should be roughly equal in length
- Do not pad items with filler

Format output as a numbered list of items, each with a bold lead word or phrase.
```

---

## Input Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `{DATE}` | System | Current date |
| `{RESULTS_JSON}` | Cron Job 1 output | Yesterday's game results |
| `{PLAYER_STATS_JSON}` | Cron Job 1 output | Individual player stats |
| `{STANDINGS_JSON}` | Cron Job 1 output | Current MLB standings |

---

## Output Validation

Before committing Around the League content:
- [ ] 6–8 items present
- [ ] No team appears more than once (unless extraordinary)
- [ ] All statistics match source data
- [ ] No placeholder text
- [ ] Items are roughly uniform in length
- [ ] Numbered list format with bold leads
