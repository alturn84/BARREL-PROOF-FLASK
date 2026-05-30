# Major League Baseball — Daily Feed

Pulls box scores from the **free MLB Stats API** (no API key required)
and saves formatted markdown to `Daily/` each morning.

---

## Setup

### 1. Install the one dependency
```bash
pip install requests
```

### 2. Run manually
```bash
# Yesterday's games (default)
python "/Users/allanturner/Documents/Major League Baseball/mlb_fetch.py"

# Specific date
python "/Users/allanturner/Documents/Major League Baseball/mlb_fetch.py" 2026-05-14
```

### 3. Schedule with cron (8 AM daily, automatic)
Open Terminal and run:
```bash
crontab -e
```
Add this line:
```
0 8 * * * /usr/bin/python3 "/Users/allanturner/Documents/Major League Baseball/mlb_fetch.py" >> "/Users/allanturner/Documents/Major League Baseball/fetch.log" 2>&1
```
Save and exit. A new box score file will appear in `Daily/` every morning.

---

## Output format

Each run creates: `Daily/YYYY-MM-DD-mlb-box-scores.md`

Each game includes:
- Line score (inning by inning, R/H/E)
- Pitching decisions (W/L/SV)
- Batting highlights (HR, multi-hit, RBI leaders)
- Full pitching lines for every pitcher used

---

## Connecting to Claude

This vault is connected to Claude via the Filesystem MCP.  
Open a conversation in the Diamond Daily project and ask:

> "Read yesterday's box scores and build today's Diamond Daily newsletter."

Claude will read the markdown file directly and use it to populate all five newsletter sections — box scores, previews, matchup lab, on the rise, and prospect watch.

---

## Data source

`https://statsapi.mlb.com` — MLB's own API, publicly accessible, no authentication required.  
Covers all regular season games, box scores, play-by-play, and player stats back to 2008.

---

## Directory structure

```
Major League Baseball/
  mlb_fetch.py          ← run this daily (or let cron run it)
  fetch.log             ← cron output log
  README.md             ← this file
  Daily/
    2026-05-14-mlb-box-scores.md
    2026-05-15-mlb-box-scores.md
    ...
```
