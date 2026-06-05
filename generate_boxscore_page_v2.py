#!/usr/bin/env python3
"""
Barrel Proof — Box Score Page Generator v2
Builds per-day HTML files + manifest + index page with full date navigation.
Usage:
  python generate_boxscore_page_v2.py              # rebuild all dates
  python generate_boxscore_page_v2.py 2026-05-31   # single date
  python generate_boxscore_page_v2.py --latest     # most recent date only
"""
import re, json, sys
from datetime import datetime, timedelta
from pathlib import Path

VAULT    = Path("/Users/allanturner/BARREL PROOF")
DAILY    = VAULT / "Daily"
OUT_DIR  = VAULT / "Homepage" / "boxscores"
INDEX    = VAULT / "Homepage" / "barrel-proof-boxscores.html"
MANIFEST = OUT_DIR / "manifest.json"

NAV_LOGO = "https://i.postimg.cc/pTNWxjb5/barrel-tab-logo-removebg-preview.png"

CSS = r"""
:root{
  --ink:#1A1108;--ink-soft:#2C1F0E;--ink-card:#1E1208;
  --parchment:#EDE5D0;--parchment2:#D8C9A8;
  --gold-dim:#887C60;--smoke:#7A6A52;--smoke-light:#A89070;
  --leather:#3A2010;--rule:rgba(100,68,20,.22);--rule-heavy:rgba(100,68,20,.45);
  --green:#4A8A4A;--red:#A83030;
  --serif-display:"Playfair Display",Georgia,serif;
  --serif-sc:"Playfair Display SC",Georgia,serif;
  --serif-body:"Source Serif 4",Georgia,serif;
  --mono:"IBM Plex Mono","Courier New",monospace;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html{font-size:14px;}
body{background:var(--ink);color:var(--parchment);font-family:var(--serif-body);-webkit-font-smoothing:antialiased;min-height:100vh;}
a{color:inherit;text-decoration:none;}

/* ── TICKER ── */
.ticker-bar{background:var(--leather);border-bottom:1px solid var(--gold-dim);padding:5px 0;overflow:hidden;}
.ticker-inner{display:flex;align-items:center;white-space:nowrap;animation:ticker 60s linear infinite;}
.ticker-inner:hover{animation-play-state:paused;}
@keyframes ticker{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
.ti{font-family:var(--mono);font-size:11px;letter-spacing:.04em;color:var(--parchment2);padding:0 20px;display:inline-flex;align-items:center;gap:7px;}
.ti .w{color:var(--parchment);font-weight:500;}.ti .sep{color:var(--gold-dim);opacity:.5;}

/* ── MASTHEAD ── */
.page{max-width:1280px;margin:0 auto;padding:0 22px 60px;}
.masthead{padding:32px 0 0;border-bottom:2px solid var(--gold-dim);}
.masthead-top{display:flex;justify-content:center;align-items:center;padding-bottom:8px;}
.site-name{font-family:'Perpetua Titling MT','Perpetua','Book Antiqua','Palatino Linotype',Palatino,Georgia,serif;font-size:clamp(34px,5vw,64px);font-weight:400;letter-spacing:.18em;color:var(--parchment);line-height:1;text-align:center;text-transform:uppercase;white-space:nowrap;}
.tagline-bar{text-align:center;padding:8px 0 14px;border-top:.5px solid var(--rule);margin-top:6px;}
.tagline{font-family:var(--serif-sc);font-size:18px;letter-spacing:.2em;color:var(--smoke-light);line-height:1.8;}
.tagline em{color:var(--gold-dim);font-style:normal;}
.tagline-sub{font-size:15px;letter-spacing:.24em;color:var(--gold-dim);}

/* ── NAV ── */
nav.main-nav{display:flex;align-items:center;border-bottom:1px solid var(--rule-heavy);}
.nav-barrel-btn{flex-shrink:0;width:52px;height:48px;cursor:pointer;border-right:.5px solid var(--rule-heavy);background:var(--ink) url('https://i.postimg.cc/pTNWxjb5/barrel-tab-logo-removebg-preview.png') center/40px auto no-repeat;transition:opacity .2s;}
.nav-barrel-btn:hover{opacity:.75;}
.nav-items-wrap{display:flex;align-items:center;overflow:hidden;max-width:0;transition:max-width .45s cubic-bezier(.4,0,.2,1);white-space:nowrap;}
.nav-items-wrap.open{max-width:1400px;}
.nav-item{font-family:var(--serif-sc);font-size:15px;letter-spacing:.14em;color:var(--smoke-light);padding:12px 18px;position:relative;cursor:pointer;transition:color .2s;white-space:nowrap;display:inline-block;}
.nav-item:hover,.nav-item.active{color:var(--parchment);}
.nav-item.active::after{content:'';position:absolute;bottom:-1px;left:0;right:0;height:2px;background:var(--parchment);}
.nav-item:not(:last-child)::before{content:'·';position:absolute;right:-2px;color:var(--rule-heavy);}

/* ── DATE NAVIGATION ── */
.date-nav{display:flex;align-items:center;justify-content:space-between;padding:12px 0 10px;border-bottom:.5px solid var(--rule);gap:12px;}
.date-arrow{background:none;border:.5px solid var(--rule-heavy);border-radius:3px;color:var(--smoke-light);font-family:var(--mono);font-size:13px;padding:5px 12px;cursor:pointer;transition:all .15s;white-space:nowrap;}
.date-arrow:hover:not(:disabled){border-color:var(--gold-dim);color:var(--parchment);}
.date-arrow:disabled{opacity:.25;cursor:default;}
.date-center{display:flex;align-items:center;gap:10px;}
.date-display{font-family:var(--serif-sc);font-size:13px;letter-spacing:.14em;color:var(--parchment);cursor:pointer;white-space:nowrap;}
.date-display:hover{color:var(--gold-dim);}
.game-count{font-family:var(--mono);font-size:10px;color:var(--smoke);letter-spacing:.06em;}

/* ── CALENDAR DROPDOWN ── */
.cal-overlay{display:none;position:fixed;inset:0;z-index:100;background:rgba(20,12,4,.7);}
.cal-overlay.open{display:flex;align-items:flex-start;justify-content:center;padding-top:120px;}
.cal-panel{background:var(--ink-soft);border:1px solid var(--rule-heavy);border-radius:4px;padding:20px;max-width:480px;width:100%;max-height:70vh;overflow-y:auto;}
.cal-panel-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;}
.cal-panel-title{font-family:var(--serif-sc);font-size:12px;letter-spacing:.2em;color:var(--gold-dim);}
.cal-close{background:none;border:none;color:var(--smoke);cursor:pointer;font-size:18px;line-height:1;padding:0 4px;}
.cal-close:hover{color:var(--parchment);}
.cal-month{margin-bottom:18px;}
.cal-month-hdr{font-family:var(--serif-sc);font-size:11px;letter-spacing:.18em;color:var(--smoke-light);margin-bottom:8px;padding-bottom:4px;border-bottom:.5px solid var(--rule);}
.cal-days{display:flex;flex-wrap:wrap;gap:4px;}
.cal-day{font-family:var(--mono);font-size:11px;padding:5px 8px;border-radius:2px;cursor:pointer;border:.5px solid transparent;min-width:36px;text-align:center;color:var(--smoke-light);transition:all .12s;}
.cal-day.has-games{color:var(--parchment2);border-color:var(--rule);}
.cal-day.has-games:hover{border-color:var(--gold-dim);color:var(--parchment);}
.cal-day.current{border-color:var(--gold-dim);background:rgba(136,124,96,.15);color:var(--parchment);}
.cal-day.no-games{opacity:.2;cursor:default;}

/* ── GAME SELECTOR ── */
.game-sel-wrap{margin:12px 0 4px;overflow-x:auto;padding-bottom:3px;}
.game-sel{display:flex;gap:6px;padding:1px 0;min-width:max-content;}
.game-btn{background:var(--ink-soft);border:.5px solid var(--rule-heavy);border-radius:3px;padding:7px 11px;cursor:pointer;transition:border-color .15s,background .15s;flex-shrink:0;text-align:center;min-width:108px;}
.game-btn:hover{border-color:var(--gold-dim);}.game-btn.active{border-color:var(--gold-dim);background:var(--ink-card);}
.gb-status{font-family:var(--mono);font-size:9px;letter-spacing:.09em;color:var(--gold-dim);text-transform:uppercase;margin-bottom:4px;}
.gb-match{display:flex;align-items:center;gap:5px;justify-content:center;}
.gb-team{font-family:var(--serif-sc);font-size:11px;letter-spacing:.05em;}
.gb-team.w{color:var(--parchment);}.gb-team.l{color:var(--smoke);}
.gb-sc{font-family:var(--mono);font-size:14px;}
.gb-sc.w{color:var(--parchment);font-weight:500;}.gb-sc.l{color:var(--smoke);}
.gb-at{color:var(--smoke);font-size:9px;font-family:var(--mono);}

/* ── BOX SCORE LAYOUT ── */
.bs-layout{display:grid;grid-template-columns:1fr 260px;gap:22px;margin-top:16px;}
.sec-hdr{display:flex;align-items:baseline;gap:11px;padding:12px 0 8px;border-bottom:.5px solid var(--rule);margin-bottom:14px;}
.sec-title{font-family:var(--serif-sc);font-size:10.5px;letter-spacing:.2em;color:var(--gold-dim);white-space:nowrap;}
.sec-rule{flex:1;height:.5px;background:var(--rule);}
.sec-sub{font-family:var(--mono);font-size:9.5px;color:var(--smoke);letter-spacing:.05em;}

/* ── GAME HEADER ── */
.game-hdr{margin-bottom:16px;}
.game-teams-row{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;margin-bottom:10px;}
.game-team-block{text-align:center;}
.gt-abbr{font-family:var(--serif-sc);font-size:26px;letter-spacing:.1em;display:block;margin-bottom:2px;}
.gt-abbr.w{color:var(--parchment);}.gt-abbr.l{color:var(--smoke);}
.score-center{display:flex;align-items:center;gap:10px;justify-content:center;}
.gt-score{font-family:var(--mono);font-size:50px;line-height:1;}
.gt-score.w{color:var(--parchment);font-weight:500;}.gt-score.l{color:var(--smoke);}
.game-info-bar{font-family:var(--mono);font-size:10px;color:var(--smoke);letter-spacing:.04em;line-height:1.8;border-top:.5px solid var(--rule);padding-top:8px;margin-bottom:10px;}
.game-info-bar strong{color:var(--smoke-light);}
.game-decisions{font-family:var(--mono);font-size:11px;color:var(--smoke);letter-spacing:.03em;margin-bottom:12px;}
.game-decisions strong{color:var(--parchment2);font-weight:500;}

/* ── LINE SCORE ── */
.ls-wrap{overflow-x:auto;margin-bottom:20px;}
.ls{border-collapse:collapse;width:100%;font-family:var(--mono);font-size:12px;white-space:nowrap;}
.ls th{color:var(--smoke);font-weight:400;font-size:10px;text-align:center;padding:0 6px 5px;letter-spacing:.06em;border-bottom:.5px solid var(--rule);}
.ls th.tn{text-align:left;min-width:42px;}
.ls td{text-align:center;padding:5px 6px;color:var(--smoke);}
.ls td.tn{text-align:left;font-family:var(--serif-sc);font-size:11px;letter-spacing:.08em;min-width:42px;padding-left:1px;}
.ls td.sep{border-left:1px solid var(--rule-heavy);}
.ls tr.w td{color:var(--parchment);}.ls tr.w td.tn{color:var(--parchment);}
.ls tr.w td.sep:first-of-type{font-weight:600;}

/* ── STAT TABLES ── */
.team-block{margin-bottom:22px;}
.team-label{font-family:var(--serif-sc);font-size:11px;letter-spacing:.14em;color:var(--gold-dim);margin-bottom:8px;padding-bottom:4px;border-bottom:.5px solid var(--rule);}
.stat-wrap{overflow-x:auto;margin-bottom:6px;}
.stat-tbl{border-collapse:collapse;width:100%;font-family:var(--mono);font-size:11px;white-space:nowrap;}
.stat-tbl th{color:var(--smoke);font-weight:400;font-size:9.5px;text-align:center;padding:4px 6px;letter-spacing:.06em;border-bottom:.5px solid var(--rule-heavy);background:rgba(0,0,0,.18);}
.stat-tbl th.nl{text-align:left;}
.stat-tbl td{text-align:center;padding:4px 6px;color:var(--parchment2);border-bottom:.5px solid var(--rule);}
.stat-tbl td.nl{text-align:left;min-width:155px;}
.stat-tbl tr:last-child td{border-bottom:none;font-weight:500;background:rgba(0,0,0,.15);}
.stat-tbl tr:hover td{background:rgba(136,124,96,.05);}
.hi-hr{color:var(--parchment);font-weight:600;}.hi-h3{color:var(--parchment);font-weight:500;}
.hi-rbi{color:var(--parchment);font-weight:500;}.hi-k8{color:var(--parchment);font-weight:600;}
.era-good{color:var(--green);}.era-bad{color:var(--red);}

/* ── GAME NOTES ── */
.game-notes{font-family:var(--mono);font-size:10.5px;color:var(--smoke-light);line-height:1.9;margin-bottom:18px;padding:10px 12px;background:rgba(0,0,0,.2);border-left:2px solid var(--gold-dim);}
.game-notes strong{color:var(--parchment2);}

/* ── SIDEBAR ── */
.sb-card{background:var(--ink-soft);border:.5px solid var(--rule-heavy);border-radius:3px;padding:12px 14px;margin-bottom:14px;}
.sb-title{font-family:var(--serif-sc);font-size:10.5px;letter-spacing:.16em;color:var(--gold-dim);margin-bottom:10px;}
.sb-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:.5px solid var(--rule);font-family:var(--mono);font-size:11px;}
.sb-row:last-child{border-bottom:none;}
.sb-lbl{color:var(--parchment2);flex:1;padding-right:8px;}.sb-val{color:var(--parchment);font-weight:500;white-space:nowrap;}
.sb-empty{font-family:var(--mono);font-size:10px;color:var(--smoke);font-style:italic;}

/* ── FOOTER ── */
footer{border-top:.5px solid var(--rule-heavy);margin-top:40px;padding:20px 0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;}
.footer-name{font-family:var(--serif-sc);font-size:15px;color:var(--gold-dim);letter-spacing:.1em;}
.footer-tag{font-family:var(--mono);font-size:9.5px;color:var(--smoke);letter-spacing:.1em;text-align:center;}
.footer-legal{font-family:var(--mono);font-size:9px;color:var(--smoke);opacity:.6;text-align:right;line-height:1.7;}

/* ── RESPONSIVE ── */
@media(max-width:920px){.bs-layout{grid-template-columns:1fr;}.bs-side{order:-1;}}
@media(max-width:540px){.page{padding:0 12px 40px;}.nav-item:nth-child(n+6){display:none;}.gt-score{font-size:38px;}.gt-abbr{font-size:18px;}}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
"""

FONTS = 'https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=Playfair+Display+SC:wght@400;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,400&family=IBM+Plex+Mono:wght@300;400;500&display=swap'

# ── PARSERS ───────────────────────────────────────────────────────────────────
def parse_table(block):
    rows, headers = [], []
    for line in block.split('\n'):
        line = line.strip()
        if not line or not line.startswith('|'): continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if all(re.match(r'^[-: ]+$', c) for c in cells): continue
        if not headers: headers = [c.strip('* ') for c in cells]
        else: rows.append(dict(zip(headers, cells)))
    return rows

def parse_innings(rows, away, home):
    ai, hi, ar, hr_ = [], [], [0,0,0], [0,0,0]
    for row in rows:
        team = row.get('Team','').strip('* ')
        vals = []
        for k, v in row.items():
            if re.match(r'^\d+$', k.strip()):
                v = v.strip()
                if v in ('', '  ', '—', '-'): vals.append(None)
                else:
                    try: vals.append(int(v))
                    except: vals.append(None)
        def gi(k):
            try: return int(row.get(k,'0').strip('* ') or '0')
            except: return 0
        rhe = [gi('R'), gi('H'), gi('E')]
        if away in team: ai, ar = vals, rhe
        else: hi, hr_ = vals, rhe
    return ai, hi, ar, hr_

def parse_bat(rows):
    out = []
    for row in rows:
        np_ = row.get('Batter','').strip()
        if not np_: continue
        m = re.match(r'^(.*?)\s*\(([^)]+)\)\s*$', np_)
        name = m.group(1).strip() if m else np_
        pos  = m.group(2).strip() if m else ''
        def iv(k):
            try: return int(row.get(k,'0') or '0')
            except: return 0
        def sv(k): return (row.get(k,'') or '').strip() or '—'
        out.append({'n':name,'pos':pos,'pa':iv('PA'),'ab':iv('AB'),'r':iv('R'),
                    'h':iv('H'),'d':iv('2B'),'t':iv('3B'),'hr':iv('HR'),'rbi':iv('RBI'),
                    'bb':iv('BB'),'so':iv('SO'),'avg':sv('AVG'),'obp':sv('OBP'),
                    'slg':sv('SLG'),'ops':sv('OPS')})
    return out

def parse_pit(rows):
    out = []
    for row in rows:
        name = row.get('Pitcher','').strip()
        if not name: continue
        def iv(k):
            try: return int(row.get(k,'0') or '0')
            except: return 0
        def sv(k): return (row.get(k,'') or '').strip()
        out.append({'n':name,'ip':sv('IP'),'h':iv('H'),'r':iv('R'),'er':iv('ER'),
                    'bb':iv('BB'),'k':iv('K'),'hr':iv('HR'),'bf':sv('BF'),
                    'ps':sv('P-S'),'era':sv('ERA'),'whip':sv('WHIP')})
    return out

def parse_decisions(block, ds):
    if not ds:
        bq = re.search(r'>\s*[^|]+\|\s*\*\*Decisions:\*\*\s*(.+)', block)
        if bq: ds = bq.group(1).strip()
    decisions = {'W':'','L':'','SV':''}
    if ds:
        for key in ['W','L','SV']:
            m = re.search(rf'{key}:\s*([^·\n·]+)', ds)
            if m: decisions[key] = m.group(1).strip().rstrip(' ·')
    return decisions

def parse_venue_info(block):
    im = re.search(r'\*\*Venue:\*\*\s*([^·\n]+?)(?:\s*·\s*\*\*Start:\*\*\s*([^·\n]+?))?(?:\s*·\s*\*\*Attendance:\*\*\s*([^·\n]+?))?(?:\s*·\s*\*\*Duration:\*\*\s*([^·\n]+?))?(?:\s*·\s*\*\*Weather:\*\*\s*(.+?))?$', block, re.MULTILINE)
    if im:
        return (im.group(1).strip(), im.group(2).strip() if im.group(2) else '',
                im.group(3).strip() if im.group(3) else '',
                im.group(4).strip() if im.group(4) else '',
                im.group(5).strip() if im.group(5) else '')
    bq = re.search(r'>\s*([^|]+)\|', block)
    venue = bq.group(1).strip() if bq else ''
    return venue, '', '', '', ''

def parse_md(text):
    text = re.sub(r'^---.*?---\s*', '', text, flags=re.DOTALL)
    games = []
    for block in re.split(r'\n(?=### )', text):
        block = block.strip()
        if not block.startswith('###'): continue
        hm = re.match(r'### (\w+) @ (\w+)[^—\-]*[—\-]\s*(.*)', block.split('\n')[0])
        if not hm: continue
        away, home = hm.group(1), hm.group(2)
        sm = re.findall(r'\*?(\d+)\*?', hm.group(3))
        try: aR, hR = int(sm[0]), int(sm[1])
        except: aR, hR = 0, 0

        venue, start, attend, dur, wx = parse_venue_info(block)
        dm = re.search(r'\*\*Decisions:\*\*\s*(.+)', block)
        ds = dm.group(1).strip() if dm else ''
        decisions = parse_decisions(block, ds)

        ls_lines = [l for l in block.split('\n') if l.strip().startswith('|')][:3]
        ls_rows  = parse_table('\n'.join(ls_lines))
        ai, hi, ar, hr_ = parse_innings(ls_rows, away, home)

        batting  = {'away':[], 'home':[]}
        pitching = {'away':[], 'home':[]}
        for m2 in re.finditer(r'\*\*(' + re.escape(away) + r'|' + re.escape(home) + r') Batting\*\*\n\n((?:\|[^\n]*\n)+)', block):
            key = 'away' if m2.group(1)==away else 'home'
            batting[key] = parse_bat(parse_table(m2.group(2)))
        for m2 in re.finditer(r'\*\*(' + re.escape(away) + r'|' + re.escape(home) + r') Pitching\*\*\n\n((?:\|[^\n]*\n)+)', block):
            key = 'away' if m2.group(1)==away else 'home'
            pitching[key] = parse_pit(parse_table(m2.group(2)))

        notes = [l.strip() for l in block.split('\n')
                 if re.match(r'^\*\*(HR|2B|3B|SB|CS|HBP|LOB|WP|Balk):', l.strip())]
        lob_m = re.search(r'\*\*LOB:\*\*\s*(.+)', block)
        lob   = lob_m.group(1).strip() if lob_m else ''

        max_i  = max(len(ai), len(hi), 9)
        ext    = re.search(r'F/(\d+)', block.split('\n')[0])
        if ext: status = f'F/{ext.group(1)}'
        elif aR == 0 or hR == 0: status = 'Final · SHO'
        else: status = 'Final'

        games.append({'away':away,'home':home,'awayR':aR,'homeR':hR,'status':status,
                      'venue':venue,'start':start,'attendance':attend,'duration':dur,
                      'weather':wx,'decisions':decisions,
                      'innings':{'away':ai,'home':hi},'rhe':{'away':ar,'home':hr_},
                      'batting':batting,'pitching':pitching,'notes':notes,'lob':lob})
    return games

# ── HTML BUILDERS ─────────────────────────────────────────────────────────────
def js_val(v):
    if v is None: return 'null'
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, list): return '[' + ','.join(js_val(x) for x in v) + ']'
    if isinstance(v, dict): return '{' + ','.join(f'{json.dumps(k)}:{js_val(v2)}' for k,v2 in v.items()) + '}'
    return json.dumps(v, ensure_ascii=False)

def ticker_html(games):
    items = []
    for g in games:
        aw = g['awayR'] > g['homeR']
        hw = g['homeR'] > g['awayR']
        ext = re.search(r'F/(\d+)', g['status'])
        tag = f'<span style="font-size:9px;color:var(--smoke)"> {ext.group(0)}</span>' if ext else ''
        wa = 'w' if aw else ''
        wh = 'w' if hw else ''
        items.append(f'<span class="ti"><span class="{wa}">{g["away"]} {g["awayR"]}</span><span class="sep">–</span><span class="{wh}">{g["home"]} {g["homeR"]}</span>{tag}<span class="sep">|</span></span>')
    doubled = ''.join(items * 2)
    return f'<div class="ticker-bar"><div class="ticker-inner">{doubled}</div></div>'

def masthead_html():
    return '''<header class="masthead">
  <div class="masthead-top"><h1 class="site-name">BARREL PROOF</h1></div>
  <div class="tagline-bar">
    <div class="tagline">Raw &nbsp;<em>·</em>&nbsp; Unfiltered &nbsp;<em>·</em>&nbsp; Baseball.</div>
    <div class="tagline tagline-sub">Enjoy Responsibly.</div>
  </div>
</header>'''

def nav_html(logo):
    return '''<nav class="main-nav">
  <div class="nav-barrel-btn" onclick="this.nextElementSibling.classList.toggle('open')" title="Menu"></div>
  <div class="nav-items-wrap">
    <div class="nav-item" onclick="location.href='../barrel-proof-home.html'">Today</div>
    <div class="nav-item active">Box Scores</div>
    <div class="nav-item" onclick="location.href='../barrel-proof-dope-sheet.html'">Dope Sheet</div>
    <div class="nav-item">Advance Scout</div>
    <div class="nav-item">Barrels &amp; Whiffs</div>
    <div class="nav-item">Rosters</div>
  </div>
</nav>'''

def build_day_html(games, date_str, all_dates):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = dt.strftime('%A, %B %-d, %Y')
    prev_date = (dt - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
    has_prev = prev_date in all_dates
    has_next = next_date in all_dates
    prev_attr = '' if has_prev else ' disabled'
    next_attr = '' if has_next else ' disabled'
    prev_href = f'boxscores-{prev_date}.html' if has_prev else '#'
    next_href = f'boxscores-{next_date}.html' if has_next else '#'

    games_js   = 'const GAMES=' + js_val(games) + ';'
    date_js    = f'const GAME_DATE="{date_str}";'
    all_dates_js = 'const ALL_DATES=' + json.dumps(sorted(all_dates)) + ';'

    from itertools import groupby
    sorted_dates = sorted(all_dates)
    cal_months_html = ''
    for mo_key, days in groupby(sorted_dates, key=lambda d: d[:7]):
        mo_dt  = datetime.strptime(mo_key, '%Y-%m')
        mo_lbl = mo_dt.strftime('%B %Y').upper()
        day_btns = ''
        for d in days:
            dd   = datetime.strptime(d, '%Y-%m-%d')
            cls  = 'cal-day has-games' + (' current' if d == date_str else '')
            day_btns += f'<div class="{cls}" onclick="gotoDate(\'{d}\')">{dd.day}</div>'
        cal_months_html += f'<div class="cal-month"><div class="cal-month-hdr">{mo_lbl}</div><div class="cal-days">{day_btns}</div></div>'

    tick  = ticker_html(games)
    mast  = masthead_html()
    nav   = nav_html(NAV_LOGO)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Box Scores · {date_display} — Barrel Proof</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="{FONTS}" rel="stylesheet"/>
<style>{CSS}</style>
</head>
<body>
{tick}
<div class="page">
{mast}
{nav}

<div class="date-nav">
  <button class="date-arrow" onclick="location.href='{prev_href}'" {prev_attr}>← Prev</button>
  <div class="date-center">
    <div class="date-display" onclick="openCal()" title="Browse archive">
      {date_display}
    </div>
    <span class="game-count">{len(games)} games</span>
  </div>
  <button class="date-arrow" onclick="location.href='{next_href}'" {next_attr}>Next →</button>
</div>

<div class="game-sel-wrap"><div class="game-sel" id="gameSel"></div></div>
<div class="bs-layout"><main id="bsMain"></main><aside class="bs-side" id="bsSide"></aside></div>

<footer>
  <div class="footer-name">Barrel Proof</div>
  <div class="footer-tag">RAW · UNFILTERED · BASEBALL · ENJOY RESPONSIBLY<br/><span style="opacity:.5">MLB Stats API · statsapi.mlb.com</span></div>
  <div class="footer-legal">© 2026 Barrel Proof<br/>Please gamble responsibly. 21+</div>
</footer>
</div>

<!-- Calendar overlay -->
<div class="cal-overlay" id="calOverlay" onclick="if(event.target===this)closeCal()">
  <div class="cal-panel">
    <div class="cal-panel-hdr">
      <span class="cal-panel-title">Box Score Archive</span>
      <button class="cal-close" onclick="closeCal()">✕</button>
    </div>
    {cal_months_html}
  </div>
</div>

<script>
{date_js}
{all_dates_js}
{games_js}

function openCal(){{document.getElementById('calOverlay').classList.add('open');}}
function closeCal(){{document.getElementById('calOverlay').classList.remove('open');}}
function gotoDate(d){{location.href='boxscores-'+d+'.html';}}

function buildSel(){{
  document.getElementById('gameSel').innerHTML=GAMES.map((g,i)=>{{
    const aw=g.awayR>g.homeR,hw=g.homeR>g.awayR;
    const st=g.status.replace('Final · SHO','SHO').replace('Final','F');
    return `<div class="game-btn${{i===0?' active':''}}" onclick="selGame(${{i}})">
      <div class="gb-status">${{st}}</div>
      <div class="gb-match">
        <span class="gb-team ${{aw?'w':'l'}}">${{g.away}}</span>
        <span class="gb-sc ${{aw?'w':'l'}}">${{g.awayR}}</span>
        <span class="gb-at">@</span>
        <span class="gb-sc ${{hw?'w':'l'}}">${{g.homeR}}</span>
        <span class="gb-team ${{hw?'w':'l'}}">${{g.home}}</span>
      </div></div>`;
  }}).join('');
}}

function lsHTML(g){{
  const aw=g.awayR>g.homeR,hw=g.homeR>g.awayR;
  const ai=g.innings.away,hi=g.innings.home;
  const maxI=Math.max(ai.length,hi.length,9);
  let hdrs='<th class="tn"></th>';
  for(let i=1;i<=maxI;i++)hdrs+=`<th>${{i}}</th>`;
  hdrs+='<th class="sep">R</th><th>H</th><th>E</th>';
  function row(abbr,runs,rhe,win){{
    let c='';for(let i=0;i<maxI;i++){{const v=runs[i];c+=`<td>${{v===null||v===undefined?'—':v}}</td>`;}}
    return `<tr class="${{win?'w':''}}"><td class="tn">${{abbr}}</td>${{c}}<td class="sep">${{rhe[0]}}</td><td>${{rhe[1]}}</td><td>${{rhe[2]}}</td></tr>`;
  }}
  return `<div class="ls-wrap"><table class="ls"><thead><tr>${{hdrs}}</tr></thead><tbody>${{row(g.away,ai,g.rhe.away,aw)}}${{row(g.home,hi,g.rhe.home,hw)}}</tbody></table></div>`;
}}

function batHTML(players,abbr){{
  if(!players||!players.length)return`<div class="sb-empty">No batting data available.</div>`;
  let tPA=0,tAB=0,tR=0,tH=0,tD=0,tT=0,tHR=0,tRBI=0,tBB=0,tSO=0;
  players.forEach(p=>{{tPA+=p.pa;tAB+=p.ab;tR+=p.r;tH+=p.h;tD+=p.d;tT+=p.t;tHR+=p.hr;tRBI+=p.rbi;tBB+=p.bb;tSO+=p.so;}});
  const hasAdv=players.some(p=>p.obp&&p.obp!=='—');
  const advHdr=hasAdv?'<th>OBP</th><th>SLG</th><th>OPS</th>':'';
  const rows=players.map(p=>{{
    const adv=hasAdv?`<td>${{p.obp}}</td><td>${{p.slg}}</td><td>${{p.ops}}</td>`:'';
    return `<tr>
      <td class="nl">${{p.n}} <span style="color:var(--smoke);font-size:9.5px">${{p.pos}}</span></td>
      <td>${{p.pa||p.ab}}</td><td>${{p.ab}}</td><td>${{p.r}}</td>
      <td class="${{p.h>=3?'hi-h3':''}}">${{p.h}}</td><td>${{p.d}}</td><td>${{p.t}}</td>
      <td class="${{p.hr>0?'hi-hr':''}}">${{p.hr}}</td>
      <td class="${{p.rbi>=3?'hi-rbi':''}}">${{p.rbi}}</td>
      <td>${{p.bb}}</td><td>${{p.so}}</td><td>${{p.avg}}</td>${{adv}}
    </tr>`;
  }}).join('');
  const advTot=hasAdv?'<td colspan="3" style="color:var(--smoke)">—</td>':'';
  const tot=`<tr><td class="nl" style="color:var(--smoke)">Totals</td><td>${{tPA||tAB}}</td><td>${{tAB}}</td><td>${{tR}}</td><td>${{tH}}</td><td>${{tD}}</td><td>${{tT}}</td><td>${{tHR}}</td><td>${{tRBI}}</td><td>${{tBB}}</td><td>${{tSO}}</td><td style="color:var(--smoke)">—</td>${{advTot}}</tr>`;
  return `<div class="stat-wrap"><table class="stat-tbl">
    <thead><tr><th class="nl">${{abbr}} Batting</th><th>PA</th><th>AB</th><th>R</th><th>H</th><th>2B</th><th>3B</th><th>HR</th><th>RBI</th><th>BB</th><th>SO</th><th>AVG</th>${{advHdr}}</tr></thead>
    <tbody>${{rows}}${{tot}}</tbody></table></div>`;
}}

function pitHTML(players,abbr){{
  if(!players||!players.length)return`<div class="sb-empty">No pitching data available.</div>`;
  let tIP=0,tH=0,tR=0,tER=0,tBB=0,tK=0,tHR=0;
  players.forEach(p=>{{
    const n=parseFloat((p.ip||'0').replace('.1','.333').replace('.2','.667'))||0;
    tIP+=n;tH+=p.h;tR+=p.r;tER+=p.er;tBB+=p.bb;tK+=p.k;tHR+=p.hr;
  }});
  const tIf=Math.floor(tIP)+'.'+(Math.round((tIP%1)*3));
  const rows=players.map(p=>{{
    const ef=parseFloat(p.era);
    const ec=ef<=3.0?'era-good':ef>=5.5?'era-bad':'';
    const kc=p.k>=8?'hi-k8':'';
    return `<tr><td class="nl">${{p.n}}</td><td>${{p.ip}}</td><td>${{p.h}}</td><td>${{p.r}}</td><td>${{p.er}}</td><td>${{p.bb}}</td><td class="${{kc}}">${{p.k}}</td><td>${{p.hr}}</td><td>${{p.bf||'—'}}</td><td>${{p.ps||'—'}}</td><td class="${{ec}}">${{p.era}}</td><td>${{p.whip}}</td></tr>`;
  }}).join('');
  const tot=`<tr><td class="nl" style="color:var(--smoke)">Totals</td><td>${{tIf}}</td><td>${{tH}}</td><td>${{tR}}</td><td>${{tER}}</td><td>${{tBB}}</td><td>${{tK}}</td><td>${{tHR}}</td><td colspan="4" style="color:var(--smoke)">—</td></tr>`;
  return `<div class="stat-wrap"><table class="stat-tbl">
    <thead><tr><th class="nl">${{abbr}} Pitching</th><th>IP</th><th>H</th><th>R</th><th>ER</th><th>BB</th><th>K</th><th>HR</th><th>BF</th><th>P-S</th><th>ERA</th><th>WHIP</th></tr></thead>
    <tbody>${{rows}}${{tot}}</tbody></table></div>`;
}}

function renderGame(i){{
  const g=GAMES[i];
  const aw=g.awayR>g.homeR,hw=g.homeR>g.awayR;
  const dec=[
    g.decisions.W?`W: <strong>${{g.decisions.W}}</strong>`:'',
    g.decisions.L?`L: <strong>${{g.decisions.L}}</strong>`:'',
    g.decisions.SV?`SV: <strong>${{g.decisions.SV}}</strong>`:''
  ].filter(Boolean).join(' &nbsp;·&nbsp; ');
  const notesHTML=g.notes.length?`<div class="game-notes">${{g.notes.join('<br/>')}}</div>`:'';

  document.getElementById('bsMain').innerHTML=`
    <div class="sec-hdr"><div class="sec-title">Box Score</div><div class="sec-rule"></div><div class="sec-sub">${{g.away}} at ${{g.home}} &nbsp;·&nbsp; ${{g.status}}</div></div>
    <div class="game-hdr">
      <div class="game-teams-row">
        <div class="game-team-block"><span class="gt-abbr ${{aw?'w':'l'}}">${{g.away}}</span></div>
        <div class="score-center">
          <span class="gt-score ${{aw?'w':'l'}}">${{g.awayR}}</span>
          <span style="font-family:var(--mono);color:var(--smoke);font-size:22px;">–</span>
          <span class="gt-score ${{hw?'w':'l'}}">${{g.homeR}}</span>
        </div>
        <div class="game-team-block"><span class="gt-abbr ${{hw?'w':'l'}}">${{g.home}}</span></div>
      </div>
      <div class="game-info-bar">
        ${{g.venue?`<strong>Venue:</strong> ${{g.venue}}`:''}}&nbsp;
        ${{g.start?`&nbsp;·&nbsp;<strong>Start:</strong> ${{g.start}}`:''}}
        ${{g.attendance?`&nbsp;·&nbsp;<strong>Att:</strong> ${{g.attendance}}`:''}}
        ${{g.duration?`&nbsp;·&nbsp;<strong>Time:</strong> ${{g.duration}}`:''}}
        ${{g.weather?`<br/><strong>Weather:</strong> ${{g.weather}}`:''}}</div>
      <div class="game-decisions">${{dec||'&mdash;'}}</div>
    </div>
    ${{lsHTML(g)}}
    <div class="team-block"><div class="team-label">${{g.away}} Batting</div>${{batHTML(g.batting.away,g.away)}}</div>
    <div class="team-block"><div class="team-label">${{g.home}} Batting</div>${{batHTML(g.batting.home,g.home)}}</div>
    ${{notesHTML}}
    <div class="team-block"><div class="team-label">${{g.away}} Pitching</div>${{pitHTML(g.pitching.away,g.away)}}</div>
    <div class="team-block"><div class="team-label">${{g.home}} Pitching</div>${{pitHTML(g.pitching.home,g.home)}}</div>
  `;
}}

function renderSide(i){{
  const g=GAMES[i];
  const hrs=[...(g.batting.away||[]),...(g.batting.home||[])].filter(p=>p.hr>0);
  const hrRows=hrs.length?hrs.map(p=>{{
    const tm=(g.batting.away||[]).includes(p)?g.away:g.home;
    return `<div class="sb-row"><span class="sb-lbl">${{p.n}} <span style="color:var(--smoke)">${{tm}}</span></span><span class="sb-val">${{p.hr}} HR</span></div>`;
  }}).join(''):`<div class="sb-row"><span class="sb-empty">No home runs</span></div>`;

  const quality=[...(g.pitching.away||[]),...(g.pitching.home||[])].filter(p=>parseFloat(p.ip)>=6&&p.er<=3);
  const qRows=quality.length?quality.map(p=>{{
    const tm=(g.pitching.away||[]).includes(p)?g.away:g.home;
    const ef=parseFloat(p.era);
    const ec=ef<=3?'color:var(--green)':ef>=5.5?'color:var(--red)':'';
    return `<div class="sb-row"><span class="sb-lbl">${{p.n}} <span style="color:var(--smoke)">${{tm}}</span></span><span class="sb-val" style="${{ec}}">${{p.k}}K ${{p.ip}}IP</span></div>`;
  }}).join(''):`<div class="sb-row"><span class="sb-empty">—</span></div>`;

  const notable=[...(g.batting.away||[]),...(g.batting.home||[])].filter(p=>p.h>=3||p.rbi>=3||p.hr>=2);
  const notRows=notable.length?notable.map(p=>{{
    const tm=(g.batting.away||[]).includes(p)?g.away:g.home;
    const tags=[];
    if(p.hr>=2)tags.push(`${{p.hr}}HR`);
    if(p.h>=3)tags.push(`${{p.h}}-for-${{p.ab}}`);
    if(p.rbi>=3)tags.push(`${{p.rbi}}RBI`);
    return `<div class="sb-row"><span class="sb-lbl">${{p.n}} <span style="color:var(--smoke)">${{tm}}</span></span><span class="sb-val">${{tags.join(' · ')}}</span></div>`;
  }}).join(''):`<div class="sb-row"><span class="sb-empty">—</span></div>`;

  document.getElementById('bsSide').innerHTML=`
    <div class="sec-hdr" style="padding-top:0"><div class="sec-title">Home Runs</div><div class="sec-rule"></div></div>
    <div class="sb-card">${{hrRows}}</div>
    <div class="sec-hdr"><div class="sec-title">Quality Starts</div><div class="sec-rule"></div></div>
    <div class="sb-card">${{qRows}}</div>
    <div class="sec-hdr"><div class="sec-title">Notable Performances</div><div class="sec-rule"></div></div>
    <div class="sb-card">${{notRows}}</div>
  `;
}}

let cur=0;
function selGame(i){{
  cur=i;
  document.querySelectorAll('.game-btn').forEach((b,j)=>b.classList.toggle('active',j===i));
  renderGame(i);renderSide(i);
  window.scrollTo({{top:document.querySelector('.bs-layout').offsetTop-14,behavior:'smooth'}});
}}

buildSel();renderGame(0);renderSide(0);
</script>
</body>
</html>'''


# ── MAIN ─────────────────────────────────────────────────────────────────────
def get_all_dates():
    dates = set()
    for f in DAILY.glob('*-mlb-box-scores.md'):
        m = re.match(r'(\d{4}-\d{2}-\d{2})', f.name)
        if m: dates.add(m.group(1))
    return dates

def build_manifest(dates):
    manifest = {'dates': sorted(dates), 'generated': datetime.now().isoformat()}
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f'  Manifest updated: {len(dates)} dates')

def build_date(date_str, all_dates):
    md_file = DAILY / f'{date_str}-mlb-box-scores.md'
    if not md_file.exists():
        print(f'  SKIP {date_str} — no file')
        return False
    games = parse_md(md_file.read_text(encoding='utf-8'))
    if not games:
        print(f'  SKIP {date_str} — no games parsed')
        return False
    html = build_day_html(games, date_str, all_dates)
    out  = OUT_DIR / f'boxscores-{date_str}.html'
    out.write_text(html, encoding='utf-8')
    print(f'  Built {date_str} ({len(games)} games) → {out.name}')
    return True

def build_index(all_dates):
    latest = max(all_dates)
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta http-equiv="refresh" content="0; url=boxscores/boxscores-{latest}.html"/>
<title>Box Scores — Barrel Proof</title>
<style>body{{background:#1A1108;color:#EDE5D0;font-family:Georgia,serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}</style>
</head>
<body>
<p style="font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:.1em;color:#887C60;">
  Loading box scores…<br/>
  <a href="boxscores/boxscores-{latest}.html" style="color:#EDE5D0;">Click here if not redirected.</a>
</p>
</body>
</html>'''
    INDEX.write_text(html, encoding='utf-8')
    print(f'  Index → redirects to {latest}')

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_dates = get_all_dates()

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == '--latest':
            date_str = max(all_dates)
            build_date(date_str, all_dates)
            build_manifest(all_dates)
            build_index(all_dates)
        else:
            build_date(arg, all_dates)
            build_manifest(all_dates)
            build_index(all_dates)
    else:
        print(f'Building all {len(all_dates)} dates...')
        built = 0
        for d in sorted(all_dates):
            if build_date(d, all_dates): built += 1
        build_manifest(all_dates)
        build_index(all_dates)
        print(f'\nDone. {built} pages built → {OUT_DIR}')

if __name__ == '__main__':
    main()
