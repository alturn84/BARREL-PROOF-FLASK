# FIRECRAWL-002 — Hermes News Intake Operating Rules
**Version:** 1.0
**Last Modified:** 2026-06-18
**Applies To:** Hermes use of Firecrawl and `news_intake.json` in the Barrel Proof workflow

---

## Purpose

Firecrawl provides Hermes with live web and source intake for MLB news-sensitive workflows. It is the fact-gathering layer — not a writing tool.

Firecrawl should be used to gather current, source-backed facts such as:

- Transactions (trades, DFAs, call-ups, IL placements)
- Injuries and returns
- Probable pitcher changes
- Lineup notes and late scratches
- Roster moves
- Team news and series context
- Verified player status updates

These facts then feed into Barrel Proof scripts and Hermes' editorial workflow. They do not become final content on their own.

---

## Core Rule

```
Firecrawl gathers facts.
Barrel Proof scripts generate baseball intelligence.
Hermes interprets and organizes.
Final public writing must be original Barrel Proof analysis.
```

This chain must not be collapsed. Scraped source material is never published directly.

---

## What Firecrawl Should Be Used For

| Use Case | Context |
|----------|---------|
| Checking transaction/injury updates before Press Box | Confirms known developments before writing |
| Enriching Around the League with verified current notes | Adds source-backed tidbits to recap |
| Supporting Dope Sheet with late lineup/probable pitcher context | Fills gaps left by pre-lineup morning run |
| Giving Advanced Scout current series context | Adds recent opponent form, travel notes, series trends |
| Confirming source-backed player/team news | Verifies before making claims in editorial |
| Reducing model hallucination | Provides factual input before generation, grounding outputs |

Firecrawl is most valuable when it narrows the gap between the 6:00 AM data pull and what actually happened closer to game time.

---

## What Firecrawl Must NOT Be Used For

- **Scraping an article and rewriting it as Barrel Proof content** — this is not original analysis
- **Copying or closely paraphrasing another outlet's recap** — even paraphrased structure is not acceptable
- **Publishing long extracted passages from any source**
- **Replacing Barrel Proof's original intelligence with summarized source material**
- **Using scraped content without source metadata** — if source, URL, or date is missing, treat the content as unverifiable
- **Treating Firecrawl output as automatically verified** — source confidence must be assessed before any strong claim is made

If Firecrawl returns a result from a weak, unofficial, or stale source, it should be treated as low-confidence context rather than confirmed fact.

---

## Source Handling Rules

1. **Preserve source metadata** — capture URL, title/outlet name, and date when available
2. **Prefer primary/official sources** — MLB.com, official team accounts, MLB Stats API are preferred; beat writers are secondary; aggregators and opinion sites are tertiary
3. **Keep facts separated from interpretation** — `news_intake.json` stores facts; analysis happens downstream in the editorial step
4. **Label low-confidence items** — when source is unofficial or stale, tag internally as low-confidence and avoid strong claims in generated content
5. **Do not publish raw source text** — Firecrawl output feeds Hermes' context, not the public page
6. **Use facts as inputs, not final copy** — all public-facing sentences must be written as original Barrel Proof analysis

---

## Workflow Placement

Firecrawl runs as part of the morning update pipeline, after intelligence generation and before editorial:

```
scripts/update_news_intake.py        ← gather facts from live sources
scripts/check_news_intake_ready.py   ← validate output (passes on limited)
Site Data/news_intake.json           ← output: facts with source metadata

         │
         ▼
Press Box / Around the League / Dope Sheet / Advanced Scout
         ← consume available notes from news_intake.json
```

**Graceful degradation:** If Firecrawl fails, `FIRECRAWL_API_KEY` is missing, or all sources are unavailable, `update_news_intake.py` writes a valid `limited` fallback JSON and exits 0. The morning update continues without interruption. Firecrawl availability is never a blocking condition for the full pipeline.

See `05-AUTOMATION/Cron Documentation.md` — FIRECRAWL-001 section for cron placement details.

---

## Editorial Boundary

- Hermes and GitHub Copilot can use `news_intake.json` to structure internal notes, identify what changed overnight, and flag items for Press Box or Around the League.
- Public-facing writing quality is a separate concern and must go through the Barrel Proof editorial workflow (voice, tone, editorial rules).
- **Firecrawl does not solve the final voice problem.** Having facts does not mean the writing is done — Hermes still produces original Barrel Proof analysis.

---

## Compliance / Originality Guardrail

Barrel Proof may use facts learned from public sources. It must not copy another outlet's expression, structure, recap framing, or distinctive wording.

Facts are not copyrightable. Sentences are.

When in doubt: write your own sentence about the fact. Do not reproduce the source's sentence, even reworded closely.

---

## Troubleshooting Checklist

- [ ] Is `FIRECRAWL_API_KEY` present in `/opt/data/.env`?
- [ ] Does the active morning wrapper source `/opt/data/.env` before running `update_news_intake.py`?
- [ ] Did `update_news_intake.py` produce `quality: available`, `partial`, or `limited`?
- [ ] Did `check_news_intake_ready.py` pass (exit 0)?
- [ ] Is `news_intake.json` dated for the current slate?
- [ ] Are source counts and item counts reasonable for the day's news volume?
- [ ] Are errors visible in `/opt/data/logs/gateway.log` or `/opt/data/logs/errors.log`?
- [ ] If Firecrawl returned `limited`, confirm that the rest of the morning update still continued and completed normally.

If `update_news_intake.py` exits non-zero, investigate before assuming the morning update failed — the script is designed to exit 0 on all degraded states.

---

## Related Documents
- `05-AUTOMATION/Cron Documentation.md` — FIRECRAWL-001 section (pipeline placement, cron wrapper notes)
- `05-AUTOMATION/Environment Variables.md` — `FIRECRAWL_API_KEY` registry entry
- `05-AUTOMATION/API Inventory.md`
- `04-EDITORIAL/Editorial Rules.md`
- `04-EDITORIAL/Voice & Tone Guide.md`
