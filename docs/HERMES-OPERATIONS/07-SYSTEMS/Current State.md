# Current State
**Document:** HERMES-015 automated capture
**Captured:** 2026-06-06
**Method:** Directly verified from repo and environment. Anything unverifiable is marked NEEDS CONFIRMATION.

---

## Repository

| Field | Value |
|-------|-------|
| Remote | https://github.com/alturn84/BARREL-PROOF-FLASK |
| Branch | main |
| Last commit | `420e371` — DOPE-001: Add standardized Dope Sheet masthead banner |
| Deployment trigger | git push → GitHub → Render webhook |

---

## Hosting

| Field | Value |
|-------|-------|
| Platform | Render |
| Deploy method | GitHub webhook auto-deploy on push to main |
| Production URL | NEEDS CONFIRMATION |
| VPS/SSH access | NEEDS CONFIRMATION — SSH to VPS not confirmed available from this session |

---

## Flask Application

| Field | Value |
|-------|-------|
| Entry point | `app.py` |
| Framework | Flask (Python) |
| Template engine | Jinja2 |
| Data directory | `Site Data/` |
| Media directory | `media/lead-images/` |
| Static assets | `static/` |

### Active Templates

| Template | Route(s) |
|----------|---------|
| `home.html` | `/`, `/index.html`, `/barrel-proof-home.html` |
| `scoreboard.html` | `/scoreboard`, `/scoreboard/` |
| `scoreboard_game.html` | `/scoreboard/<game_slug>` |
| `dope-sheet.html` | `/dope-sheet`, `/dope-sheet.html` |
| `advance_scout.html` | `/advance-scout`, `/advanced-scout` |
| `al_nl.html` | `/al-nl`, `/al-nl/` |
| `archive_index.html` | `/archive`, `/archive/` |
| `archive-edition.html` | `/archive/<year>/<month>/<day>` |
| `team_detail.html` | `/team/<team_slug>` |
| `teams_index.html` | `/teams`, `/teams/` |

### Data Files (Site Data/)

| File | Purpose |
|------|---------|
| `game_cards.json` | Per-game box scores (date: 2026-06-05, updated: 2026-06-06 12:29) |
| `schedule.json` | Today's schedule (updated: 2026-06-06 12:29) |
| `standings.json` | League standings |
| `game_of_day.json` | GOTD editorial content |
| `game_to_watch.json` | Game to Watch content |
| `press_box.json` | Press Box column |
| `around_the_league.json` | Around the League bullets |
| `dope-sheet-data.json` | Dope Sheet preview data |
| `odds.json` | Betting odds |
| `teams.json` | Team metadata |
| `mlb_rosters.json` | Roster data |

---

## Static Image Assets

| File | Purpose |
|------|---------|
| `static/images/banner.png` | Homepage masthead (1774×887) |
| `static/images/hero-scoreboard.png` | Scoreboard banner (1774×887) |
| `static/images/hero-typewriter.png` | Advance Scout banner |
| `static/images/hero-dope-sheet.png` | Dope Sheet banner (3.3MB) |
| `static/images/DopeSheetImage.png` | Source image for dope sheet banner |
| `static/images/frontispiece.png` | Homepage frontispiece |

---

## Automation (Cron Jobs)

| Job | ID | Schedule | Purpose |
|-----|----|----------|---------|
| Cron Job 1 | `98de609020e4` | 6:00 AM ET daily | MLB data collection, JSON generation |
| Cron Job 2 | `e1af79acae93` | 6:15 AM ET daily | Gemini AI content generation |

**Hard deadline:** Both jobs complete by 6:30 AM ET.

**Workspace:** NEEDS CONFIRMATION — `/workspace/barrel-proof` per vault docs; VPS path not directly verified this session.

---

## Content Generation

| Content Type | Source Prompt | Status |
|-------------|--------------|--------|
| Game of the Day | `02-PROMPTS/Game of the Day Prompt.md` | Active |
| Press Box | `02-PROMPTS/Press Box Prompt.md` | Active |
| Around the League | `02-PROMPTS/Around the League Prompt.md` | Active |
| Game to Watch | `02-PROMPTS/Game to Watch Prompt.md` | Active |
| Advanced Scout | `02-PROMPTS/Advanced Scout Prompt.md` | Active |
| DFS Analysis | `02-PROMPTS/DFS Prompt.md` | Active |

---

## API Dependencies

| API | Used By | Auth Location |
|-----|---------|--------------|
| MLB Data API | Cron Job 1 | NEEDS CONFIRMATION |
| Gemini API | Cron Job 2 | NEEDS CONFIRMATION |

---

## GOTD Image System

| Field | Value |
|-------|-------|
| Image size | 1774×887 (banner format) |
| Storage | `media/lead-images/` |
| Metadata | `media/lead-images/captions.json` |
| Valid source types | `ap`, `getty`, `mlb`, `team`, `manual`, `illustrated` |
| Latest image | `2026-06-05_lead.jpg` (LAD 1–0 LAA walk-off, Freddie Freeman) |
| Generation method | AI-generated artwork (no logos, player names, or numbers) |

---

## Partials System (SITE-001)

Standardized shell introduced 2026-06-06:
- `templates/partials/site_nav.html` — universal nav with active_page conditional
- `templates/partials/site_banner.html` — universal banner with optional banner_class

---

## Active Redirects

| From | To | Code |
|------|----|------|
| `/box-scores` | `/scoreboard` | 301 |
| `/boxscores` | `/scoreboard` | 301 |
| `/ledger` | `/scoreboard` | 301 |

---

## Known Issues / Open Items

- `templates/advanced-scout.html` — legacy file, not rendered (route now uses `advance_scout.html`)
- VPS deployment path for HERMES-015 vault: NEEDS CONFIRMATION via manual SSH
- API key storage locations: NEEDS CONFIRMATION
- Render production URL: NEEDS CONFIRMATION
- Gemini API quota limits: NEEDS CONFIRMATION
