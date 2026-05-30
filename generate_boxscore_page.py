#!/usr/bin/env python3
"""
Barrel Proof — Box Score Page Generator
Reads the latest daily vault file and generates barrel-proof-boxscores.html
Run manually or add to cron after mlb_fetch.py
"""
import re, json, sys
from datetime import datetime, timedelta
from pathlib import Path

VAULT    = Path("/Users/allanturner/BARREL PROOF")
DAILY    = VAULT / "Daily"
OUT_HTML = VAULT / "Homepage" / "barrel-proof-boxscores.html"

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
        def sv(k): return (row.get(k,'') or '').strip() or '.---'
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

        im = re.search(r'\*\*Venue:\*\*\s*([^·\n]+?)(?:\s*·\s*\*\*Start:\*\*\s*([^·\n]+?))?(?:\s*·\s*\*\*Attendance:\*\*\s*([^·\n]+?))?(?:\s*·\s*\*\*Duration:\*\*\s*([^·\n]+?))?(?:\s*·\s*\*\*Weather:\*\*\s*(.+?))?$', block, re.MULTILINE)
        venue  = im.group(1).strip() if im else ''
        start  = im.group(2).strip() if im and im.group(2) else ''
        attend = im.group(3).strip() if im and im.group(3) else ''
        dur    = im.group(4).strip() if im and im.group(4) else ''
        wx     = im.group(5).strip() if im and im.group(5) else ''

        dm = re.search(r'\*\*Decisions:\*\*\s*(.+)', block)
        ds = dm.group(1).strip() if dm else ''
        decisions = {
            'W':  (re.search(r'W:\s*([^·\n]+)', ds) or type('',(),{'group': lambda s,n: ''})()).group(1).strip() if re.search(r'W:', ds) else '',
            'L':  (re.search(r'L:\s*([^·\n]+)', ds) or type('',(),{'group': lambda s,n: ''})()).group(1).strip() if re.search(r'L:', ds) else '',
            'SV': (re.search(r'SV:\s*([^·\n]+)', ds) or type('',(),{'group': lambda s,n: ''})()).group(1).strip() if re.search(r'SV:', ds) else '',
        }
        for k in decisions:
            decisions[k] = decisions[k].rstrip(' ·')

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
        lob_m  = re.search(r'\*\*LOB:\*\*\s*(.+)', block)
        lob    = lob_m.group(1).strip() if lob_m else ''

        max_i = max(len(ai), len(hi), 9)
        status = f'Final · F/{max_i}' if max_i > 9 else ('Final · Shutout' if aR==0 or hR==0 else 'Final')

        games.append({'away':away,'home':home,'awayR':aR,'homeR':hR,'status':status,
                      'venue':venue,'start':start,'attendance':attend,'duration':dur,
                      'weather':wx,'decisions':decisions,
                      'innings':{'away':ai,'home':hi},'rhe':{'away':ar,'home':hr_},
                      'batting':batting,'pitching':pitching,'notes':notes,'lob':lob})
    return games

def js_val(v):
    if v is None: return 'null'
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, list): return '[' + ','.join(js_val(x) for x in v) + ']'
    if isinstance(v, dict): return '{' + ','.join(f'{json.dumps(k)}:{js_val(v2)}' for k,v2 in v.items()) + '}'
    return json.dumps(v, ensure_ascii=False)

def build_html(games, date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = dt.strftime('%A, %B %-d, %Y')

    ticker_items = []
    for g in games:
        aw = g['awayR'] > g['homeR']
        hw = g['homeR'] > g['awayR']
        ext = re.search(r'F/(\d+)', g['status'])
        tag = f' F/{ext.group(1)}' if ext else ''
        wa = 'w' if aw else ''
        wh = 'w' if hw else ''
        ticker_items.append(f'<span class="ti"><span class="{wa}">{g["away"]} {g["awayR"]}</span><span class="sep">–</span><span class="{wh}">{g["home"]} {g["homeR"]}</span>{"<span style=\"font-size:9px;color:var(--smoke-light)\">"+tag+"</span>" if tag else ""}<span class="sep">|</span></span>')
    ticker_html = ''.join(ticker_items * 2)

    games_js = 'const GAMES=' + js_val(games) + ';'
    date_js   = f'const GAME_DATE="{date_str}";'
    date_banner_js = f'document.getElementById("dateBanner").textContent="{date_display} · {len(games)} Games";'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Box Scores · {date_display} — Barrel Proof</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=Playfair+Display+SC:wght@400;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,400&family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
:root{{--ink:#1A1108;--ink-soft:#2C1F0E;--ink-card:#1E1208;--parchment:#F0E6CC;--parchment2:#D8C9A8;--gold:#C4882A;--gold-light:#D9A84A;--gold-dim:#8A6018;--smoke:#7A6A52;--smoke-light:#A89070;--leather:#5C3010;--rule:rgba(100,68,20,.28);--rule-heavy:rgba(100,68,20,.55);--green:#4A8A4A;--red:#A83030;--serif-display:"Playfair Display",Georgia,serif;--serif-sc:"Playfair Display SC",Georgia,serif;--serif-body:"Source Serif 4",Georgia,serif;--mono:"IBM Plex Mono","Courier New",monospace;}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
html{{font-size:14px;}}
body{{background:var(--ink);color:var(--parchment);font-family:var(--serif-body);-webkit-font-smoothing:antialiased;min-height:100vh;}}
a{{color:inherit;text-decoration:none;}}
.ticker-bar{{background:var(--leather);border-bottom:1px solid var(--gold-dim);padding:5px 0;overflow:hidden;}}
.ticker-inner{{display:flex;align-items:center;white-space:nowrap;animation:ticker 60s linear infinite;}}
.ticker-inner:hover{{animation-play-state:paused;}}
@keyframes ticker{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
.ti{{font-family:var(--mono);font-size:11px;letter-spacing:.04em;color:var(--parchment2);padding:0 20px;display:inline-flex;align-items:center;gap:7px;}}
.ti .w{{color:var(--gold-light);font-weight:500;}}.ti .sep{{color:var(--gold-dim);opacity:.5;}}
.page{{max-width:1280px;margin:0 auto;padding:0 22px 60px;}}
.masthead{{padding:24px 0 0;border-bottom:2px solid var(--gold-dim);}}
.masthead-top{{display:flex;justify-content:center;padding-bottom:7px;}}
.site-name{{font-family:"Perpetua Titling MT","Perpetua","Book Antiqua","Palatino Linotype",Palatino,Georgia,serif;font-size:clamp(44px,7vw,88px);font-weight:400;letter-spacing:.18em;color:var(--parchment);line-height:1;text-align:center;text-transform:uppercase;white-space:nowrap;}}
.site-name span{{color:var(--gold);}}
.tagline-bar{{text-align:center;padding:4px 0 10px;border-top:.5px solid var(--rule);margin-top:5px;}}
.tagline{{font-family:var(--serif-sc);font-size:12px;letter-spacing:.22em;color:var(--smoke-light);}}
.tagline em{{color:var(--gold-dim);font-style:normal;}}
nav.main-nav{{display:flex;justify-content:center;border-bottom:1px solid var(--rule-heavy);}}
.nav-item{{font-family:var(--serif-sc);font-size:11px;letter-spacing:.14em;color:var(--smoke-light);padding:10px 16px;position:relative;cursor:pointer;transition:color .2s;white-space:nowrap;}}
.nav-item:hover,.nav-item.active{{color:var(--parchment);}}
.nav-item.active::after{{content:"";position:absolute;bottom:-1px;left:0;right:0;height:2px;background:var(--gold);}}
.nav-item:not(:last-child)::before{{content:"·";position:absolute;right:-2px;color:var(--rule-heavy);}}
.date-banner{{display:flex;align-items:center;gap:14px;padding:11px 0 9px;border-bottom:.5px solid var(--rule);}}
.dbl{{flex:1;height:.5px;background:var(--rule);}}.dbt{{font-family:var(--serif-sc);font-size:11px;letter-spacing:.16em;color:var(--smoke);white-space:nowrap;}}
.game-sel-wrap{{margin:12px 0 4px;overflow-x:auto;padding-bottom:3px;}}
.game-sel{{display:flex;gap:6px;padding:1px 0;min-width:max-content;}}
.game-btn{{background:var(--ink-soft);border:.5px solid var(--rule-heavy);border-radius:3px;padding:7px 11px;cursor:pointer;transition:border-color .15s,background .15s;flex-shrink:0;text-align:center;min-width:108px;}}
.game-btn:hover{{border-color:var(--gold-dim);}}.game-btn.active{{border-color:var(--gold);background:var(--ink-card);}}
.gb-status{{font-family:var(--mono);font-size:9px;letter-spacing:.09em;color:var(--gold-dim);text-transform:uppercase;margin-bottom:4px;}}
.gb-match{{display:flex;align-items:center;gap:5px;justify-content:center;}}
.gb-team{{font-family:var(--serif-sc);font-size:11.5px;letter-spacing:.05em;}}
.gb-team.w{{color:var(--parchment);}}.gb-team.l{{color:var(--smoke);}}
.gb-sc{{font-family:var(--mono);font-size:15px;}}
.gb-sc.w{{color:var(--parchment);font-weight:500;}}.gb-sc.l{{color:var(--smoke);}}
.gb-at{{color:var(--smoke);font-size:9px;font-family:var(--mono);}}
.bs-layout{{display:grid;grid-template-columns:1fr 255px;gap:22px;margin-top:16px;}}
.sec-hdr{{display:flex;align-items:baseline;gap:11px;padding:12px 0 8px;border-bottom:.5px solid var(--rule);margin-bottom:14px;}}
.sec-title{{font-family:var(--serif-sc);font-size:10.5px;letter-spacing:.2em;color:var(--gold);white-space:nowrap;}}
.sec-rule{{flex:1;height:.5px;background:var(--rule);}}
.sec-sub{{font-family:var(--mono);font-size:9.5px;color:var(--smoke);letter-spacing:.05em;}}
.game-hdr{{margin-bottom:16px;}}
.game-teams-row{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;margin-bottom:10px;}}
.game-team-block{{text-align:center;}}
.gt-abbr{{font-family:var(--serif-sc);font-size:26px;letter-spacing:.1em;display:block;margin-bottom:2px;}}
.gt-abbr.w{{color:var(--parchment);}}.gt-abbr.l{{color:var(--smoke);}}
.gt-record{{font-family:var(--mono);font-size:10px;color:var(--smoke);letter-spacing:.06em;}}
.gt-score{{font-family:var(--mono);font-size:50px;line-height:1;}}
.gt-score.w{{color:var(--parchment);font-weight:500;}}.gt-score.l{{color:var(--smoke);}}
.score-center{{display:flex;align-items:center;gap:10px;justify-content:center;}}
.game-info-bar{{font-family:var(--mono);font-size:10px;color:var(--smoke);letter-spacing:.04em;line-height:1.8;border-top:.5px solid var(--rule);padding-top:8px;margin-bottom:10px;}}
.game-info-bar strong{{color:var(--smoke-light);}}
.game-decisions{{font-family:var(--mono);font-size:11px;color:var(--smoke);letter-spacing:.03em;margin-bottom:12px;}}
.game-decisions strong{{color:var(--parchment2);font-weight:500;}}
.ls-wrap{{overflow-x:auto;margin-bottom:20px;}}
.ls{{border-collapse:collapse;width:100%;font-family:var(--mono);font-size:12px;white-space:nowrap;}}
.ls th{{color:var(--smoke);font-weight:400;font-size:10px;text-align:center;padding:0 6px 5px;letter-spacing:.06em;border-bottom:.5px solid var(--rule);}}
.ls th.tn{{text-align:left;min-width:42px;}}
.ls td{{text-align:center;padding:5px 6px;color:var(--smoke);}}
.ls td.tn{{text-align:left;font-family:var(--serif-sc);font-size:11px;letter-spacing:.08em;min-width:42px;padding-left:1px;}}
.ls td.sep{{border-left:1px solid var(--rule-heavy);}}
.ls tr.w td{{color:var(--parchment);}}.ls tr.w td.tn{{color:var(--gold-light);}}
.ls tr.w td.sep:first-of-type{{font-weight:600;}}
.team-block{{margin-bottom:22px;}}
.team-label{{font-family:var(--serif-sc);font-size:11px;letter-spacing:.14em;color:var(--gold);margin-bottom:8px;padding-bottom:4px;border-bottom:.5px solid var(--rule);}}
.stat-wrap{{overflow-x:auto;margin-bottom:6px;}}
.stat-tbl{{border-collapse:collapse;width:100%;font-family:var(--mono);font-size:11px;white-space:nowrap;}}
.stat-tbl th{{color:var(--smoke);font-weight:400;font-size:9.5px;text-align:center;padding:4px 6px;letter-spacing:.06em;border-bottom:.5px solid var(--rule-heavy);background:rgba(0,0,0,.18);}}
.stat-tbl th.nl{{text-align:left;}}
.stat-tbl td{{text-align:center;padding:4px 6px;color:var(--parchment2);border-bottom:.5px solid var(--rule);}}
.stat-tbl td.nl{{text-align:left;min-width:155px;}}
.stat-tbl tr:last-child td{{border-bottom:none;font-weight:500;background:rgba(0,0,0,.15);}}
.stat-tbl tr:hover td{{background:rgba(196,136,42,.05);}}
.hi-hr{{color:var(--gold-light);font-weight:600;}}.hi-h3{{color:var(--parchment);font-weight:500;}}
.hi-rbi{{color:var(--parchment);font-weight:500;}}.hi-k8{{color:var(--gold-light);font-weight:600;}}
.era-good{{color:var(--green);}}.era-bad{{color:var(--red);}}
.savant-btn{{display:inline-flex;align-items:center;gap:2px;font-family:var(--mono);font-size:9px;color:var(--gold-dim);border:.5px solid var(--gold-dim);border-radius:2px;padding:1px 4px;margin-left:4px;cursor:pointer;text-decoration:none;transition:color .15s,border-color .15s;vertical-align:middle;}}
.savant-btn:hover{{color:var(--gold-light);border-color:var(--gold-light);}}
.game-notes{{font-family:var(--mono);font-size:10.5px;color:var(--smoke-light);line-height:1.9;margin-bottom:18px;padding:10px 12px;background:rgba(0,0,0,.2);border-left:2px solid var(--gold-dim);}}
.game-notes strong{{color:var(--parchment2);}}
.sb-card{{background:var(--ink-soft);border:.5px solid var(--rule-heavy);border-radius:3px;padding:12px 14px;margin-bottom:14px;}}
.sb-title{{font-family:var(--serif-sc);font-size:10.5px;letter-spacing:.16em;color:var(--gold);margin-bottom:10px;}}
.sb-row{{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:.5px solid var(--rule);font-family:var(--mono);font-size:11px;}}
.sb-row:last-child{{border-bottom:none;}}
.sb-lbl{{color:var(--parchment2);flex:1;padding-right:8px;}}.sb-val{{color:var(--gold-light);font-weight:500;white-space:nowrap;}}
.savant-full-btn{{display:block;text-align:center;margin-top:10px;font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;color:var(--gold-dim);border:.5px solid var(--gold-dim);border-radius:3px;padding:6px 10px;text-decoration:none;transition:all .15s;}}
.savant-full-btn:hover{{color:var(--gold);border-color:var(--gold);}}
footer{{border-top:.5px solid var(--rule-heavy);margin-top:40px;padding:20px 0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;}}
.footer-name{{font-family:var(--serif-sc);font-size:15px;color:var(--gold-dim);letter-spacing:.1em;}}
.footer-tag{{font-family:var(--mono);font-size:9.5px;color:var(--smoke);letter-spacing:.1em;text-align:center;}}
.footer-legal{{font-family:var(--mono);font-size:9px;color:var(--smoke);opacity:.6;text-align:right;line-height:1.7;}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.masthead,.main-nav,.date-banner,.game-sel-wrap,.bs-layout{{animation:fadeUp .45s ease both;}}
.main-nav{{animation-delay:.06s;}}.date-banner{{animation-delay:.1s;}}
.game-sel-wrap{{animation-delay:.14s;}}.bs-layout{{animation-delay:.18s;}}
@media(max-width:920px){{.bs-layout{{grid-template-columns:1fr;}}.bs-side{{order:-1;}}}}
@media(max-width:540px){{.page{{padding:0 12px 40px;}}.nav-item:nth-child(n+6){{display:none;}}.gt-score{{font-size:38px;}}.gt-abbr{{font-size:18px;}}}}
</style>
</head>
<body>
<div class="ticker-bar"><div class="ticker-inner">{ticker_html}</div></div>
<div class="page">
<header class="masthead">
  <div class="masthead-top"><h1 class="site-name">BARREL <span>PROOF</span></h1></div>
  <div class="tagline-bar"><span class="tagline">Raw &nbsp;<em>·</em>&nbsp; Unfiltered &nbsp;<em>·</em>&nbsp; Baseball &nbsp;<em>·</em>&nbsp; Enjoy Responsibly</span></div>
</header>
<nav class="main-nav">
  <div class="nav-item" onclick="location.href='barrel-proof-home.html'">Today</div>
  <div class="nav-item active">Box Scores</div>
  <div class="nav-item">Dope Sheet</div>
  <div class="nav-item">Advance Scout</div>
  <div class="nav-item">Barrel Leaders</div>
  <div class="nav-item">Minor League</div>
  <div class="nav-item">The War Room</div>
</nav>
<div class="date-banner"><div class="dbl"></div><div class="dbt" id="dateBanner">Loading…</div><div class="dbl"></div></div>
<div class="game-sel-wrap"><div class="game-sel" id="gameSel"></div></div>
<div class="bs-layout"><main id="bsMain"></main><aside id="bsSide"></aside></div>
<footer>
  <div class="footer-name">Barrel Proof</div>
  <div class="footer-tag">RAW · UNFILTERED · BASEBALL · ENJOY RESPONSIBLY<br/><span style="opacity:.5">MLB Stats API · Baseball Savant · Statcast</span></div>
  <div class="footer-legal">© 2026 Barrel Proof<br/>Please gamble responsibly. 21+</div>
</footer>
</div>
<script>
{date_js}
{games_js}

function buildSel(){{
  document.getElementById('gameSel').innerHTML=GAMES.map((g,i)=>{{
    const aw=g.awayR>g.homeR,hw=g.homeR>g.awayR;
    const st=(g.status||'').replace('Final ·','').replace('Final','F').trim()||'F';
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
  const savBase=`https://baseballsavant.mlb.com/statcast_search?hfAB=home+run%7C&hfSea=2026%7C&game_date_gt=${{GAME_DATE}}&game_date_lt=${{GAME_DATE}}&player_type=batter`;
  let tPA=0,tAB=0,tR=0,tH=0,tD=0,tT=0,tHR=0,tRBI=0,tBB=0,tSO=0;
  players.forEach(p=>{{tPA+=p.pa;tAB+=p.ab;tR+=p.r;tH+=p.h;tD+=p.d;tT+=p.t;tHR+=p.hr;tRBI+=p.rbi;tBB+=p.bb;tSO+=p.so;}});
  const rows=players.map(p=>{{
    const sv=p.hr>0?`<a class="savant-btn" href="${{savBase}}" target="_blank">▶</a>`:'';
    return `<tr>
      <td class="nl">${{p.n}} <span style="color:var(--smoke);font-size:9.5px">${{p.pos}}</span>${{sv}}</td>
      <td>${{p.pa}}</td><td>${{p.ab}}</td><td>${{p.r}}</td>
      <td class="${{p.h>=3?'hi-h3':''}}">${{p.h}}</td><td>${{p.d}}</td><td>${{p.t}}</td>
      <td class="${{p.hr>0?'hi-hr':''}}">${{p.hr}}</td>
      <td class="${{p.rbi>=3?'hi-rbi':''}}">${{p.rbi}}</td>
      <td>${{p.bb}}</td><td>${{p.so}}</td>
      <td>${{p.avg}}</td><td>${{p.obp}}</td><td>${{p.slg}}</td><td>${{p.ops}}</td>
    </tr>`;
  }}).join('');
  const tot=`<tr><td class="nl" style="color:var(--smoke)">Totals</td><td>${{tPA}}</td><td>${{tAB}}</td><td>${{tR}}</td><td>${{tH}}</td><td>${{tD}}</td><td>${{tT}}</td><td>${{tHR}}</td><td>${{tRBI}}</td><td>${{tBB}}</td><td>${{tSO}}</td><td colspan="4" style="color:var(--smoke)">—</td></tr>`;
  return `<div class="stat-wrap"><table class="stat-tbl">
    <thead><tr><th class="nl">${{abbr}} Batting</th><th>PA</th><th>AB</th><th>R</th><th>H</th><th>2B</th><th>3B</th><th>HR</th><th>RBI</th><th>BB</th><th>SO</th><th>AVG</th><th>OBP</th><th>SLG</th><th>OPS</th></tr></thead>
    <tbody>${{rows}}${{tot}}</tbody></table></div>`;
}}

function pitHTML(players,abbr){{
  let tIP=0,tH=0,tR=0,tER=0,tBB=0,tK=0,tHR=0,tBF=0;
  players.forEach(p=>{{
    const n=parseFloat((p.ip||'0').replace('.1','.33').replace('.2','.67'))||0;
    tIP+=n;tH+=p.h;tR+=p.r;tER+=p.er;tBB+=p.bb;tK+=p.k;tHR+=p.hr;tBF+=parseInt(p.bf)||0;
  }});
  const tIf=Math.floor(tIP)+'.'+(Math.round((tIP%1)*3));
  const rows=players.map(p=>{{
    const ef=parseFloat(p.era);
    const ec=ef<=3.0?'era-good':ef>=5.5?'era-bad':'';
    const kc=p.k>=8?'hi-k8':'';
    return `<tr><td class="nl">${{p.n}}</td><td>${{p.ip}}</td><td>${{p.h}}</td><td>${{p.r}}</td><td>${{p.er}}</td><td>${{p.bb}}</td><td class="${{kc}}">${{p.k}}</td><td>${{p.hr}}</td><td>${{p.bf}}</td><td>${{p.ps}}</td><td class="${{ec}}">${{p.era}}</td><td>${{p.whip}}</td></tr>`;
  }}).join('');
  const tot=`<tr><td class="nl" style="color:var(--smoke)">Totals</td><td>${{tIf}}</td><td>${{tH}}</td><td>${{tR}}</td><td>${{tER}}</td><td>${{tBB}}</td><td>${{tK}}</td><td>${{tHR}}</td><td>${{tBF}}</td><td colspan="3" style="color:var(--smoke)">—</td></tr>`;
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
        <strong>Venue:</strong> ${{g.venue||'—'}}
        ${{g.start?`&nbsp;·&nbsp;<strong>Start:</strong> ${{g.start}}`:''}}
        ${{g.attendance?`&nbsp;·&nbsp;<strong>Att:</strong> ${{g.attendance}}`:''}}
        ${{g.duration?`&nbsp;·&nbsp;<strong>Time:</strong> ${{g.duration}}`:''}}
        ${{g.weather?`<br/><strong>Weather:</strong> ${{g.weather}}`:''}}</div>
      <div class="game-decisions">${{dec||'—'}}</div>
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
  const savAll=`https://baseballsavant.mlb.com/statcast_search?hfAB=home+run%7C&hfSea=2026%7C&game_date_gt=${{GAME_DATE}}&game_date_lt=${{GAME_DATE}}&player_type=batter`;
  const hrRows=hrs.length?hrs.map(p=>{{
    const tm=g.batting.away.includes(p)?g.away:g.home;
    return `<div class="sb-row"><span class="sb-lbl">${{p.n}} (${{tm}})</span><a class="savant-btn" href="${{savAll}}" target="_blank">${{p.hr}} HR ▶</a></div>`;
  }}).join(''):'<div class="sb-row"><span class="sb-lbl" style="color:var(--smoke)">No home runs</span></div>';

  const standouts=[...(g.pitching.away||[]),...(g.pitching.home||[])].filter(p=>parseFloat(p.ip)>=5&&p.k>=6);
  const pitRows=standouts.length?standouts.map(p=>{{
    const tm=g.pitching.away.includes(p)?g.away:g.home;
    const ef=parseFloat(p.era);
    const ec=ef<=3?'color:var(--green)':ef>=5.5?'color:var(--red)':'';
    return `<div class="sb-row"><span class="sb-lbl">${{p.n}} (${{tm}})</span><span class="sb-val" style="${{ec}}">${{p.k}}K ${{p.ip}}IP ${{p.er}}ER</span></div>`;
  }}).join(''):'<div class="sb-row"><span class="sb-lbl" style="color:var(--smoke)">—</span></div>';

  document.getElementById('bsSide').innerHTML=`
    <div class="sec-hdr" style="padding-top:0"><div class="sec-title">Home Runs</div><div class="sec-rule"></div></div>
    <div class="sb-card">${{hrRows}}<a class="savant-full-btn" href="${{savAll}}" target="_blank">All HRs on Baseball Savant →</a></div>
    <div class="sec-hdr"><div class="sec-title">Pitching Lines</div><div class="sec-rule"></div></div>
    <div class="sb-card">${{pitRows}}</div>
  `;
}}

let cur=0;
function selGame(i){{
  cur=i;
  document.querySelectorAll('.game-btn').forEach((b,j)=>b.classList.toggle('active',j===i));
  renderGame(i);renderSide(i);
  window.scrollTo({{top:document.querySelector('.bs-layout').offsetTop-14,behavior:'smooth'}});
}}

{date_banner_js}
buildSel();renderGame(0);renderSide(0);
</script>
</body>
</html>'''

def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')

    md_file = DAILY / f'{date_str}-mlb-box-scores.md'
    if not md_file.exists():
        print(f'No box score file for {date_str}. Run mlb_fetch.py first.')
        sys.exit(1)

    print(f'Parsing {md_file.name}...')
    games = parse_md(md_file.read_text(encoding='utf-8'))
    print(f'  Found {len(games)} games')

    html = build_html(games, date_str)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding='utf-8')
    print(f'  Saved → {OUT_HTML}')

if __name__ == '__main__':
    main()
