// ═══════════════════════════════════════════════════════════════════════════
// BARREL PROOF · PARK FACTOR ENGINE
// barrel-proof-park-factors.js
//
// HOW TO USE
// ──────────
// This file is loaded by barrel-proof-dope-sheet.html via:
//   <script src="barrel-proof-park-factors.js"></script>
//
// It can also be opened standalone via barrel-proof-park-factors-viewer.html
//
// HOW TO UPDATE PARK DNA
// ──────────────────────
// Each entry in PARK_DNA matches on a partial venue string.
// Fields:
//   runs  – Statcast 3-yr Runs index (100 = MLB avg, >100 = hitter-friendly)
//   hr    – Statcast 3-yr HR index
//   xbh   – Statcast 3-yr XBH (2B+3B) index
//   alt   – Altitude in feet above sea level
//   dims  – Short description of park character / dimensions note
//
// Sources: Baseball Savant Statcast Park Factors (3-yr rolling 2022–2024)
//          FanGraphs Park Factors (basic runs index, 3-yr avg)
// Last updated: May 2026
// ═══════════════════════════════════════════════════════════════════════════

const PARK_DNA = {
  // ── HITTER-FRIENDLY ─────────────────────────────────────────────────────
  "Coors Field":              { runs:120, hr:116, xbh:124, alt:5200, dims:"Short alleys, thin air, extreme altitude" },
  "Great American":           { runs:112, hr:118, xbh:110, alt:490,  dims:"Tight RF porch, very hitter-friendly" },
  "Citizens Bank":            { runs:108, hr:112, xbh:107, alt:40,   dims:"Short RF porch, high HR rate" },
  "Sutter Health":            { runs:107, hr:109, xbh:106, alt:25,   dims:"Minor league park, strong out-blowing wind patterns" },
  "Camden Yards":             { runs:105, hr:103, xbh:107, alt:39,   dims:"LF wall favorable, classic dimensions" },
  "Fenway":                   { runs:106, hr:97,  xbh:115, alt:19,   dims:"Green Monster inflates XBH, suppresses HR" },
  "Globe Life":               { runs:104, hr:108, xbh:106, alt:551,  dims:"Retractable roof, HR-friendly, hot Texas summers" },
  "Truist":                   { runs:103, hr:107, xbh:104, alt:1050, dims:"Elevated park, warm climate, HR-friendly" },
  "Yankee Stadium":           { runs:103, hr:110, xbh:101, alt:55,   dims:"Short RF porch, clear HR booster" },
  "Chase Field":              { runs:103, hr:105, xbh:102, alt:1082, dims:"Retractable roof, warm altitude, offense-friendly" },
  "Minute Maid":              { runs:102, hr:104, xbh:101, alt:43,   dims:"Crawford Boxes in LF boost HR count" },

  // ── NEAR NEUTRAL ────────────────────────────────────────────────────────
  "Wrigley":                  { runs:101, hr:101, xbh:102, alt:597,  dims:"Wind-dependent, avg base — can swing either way" },
  "Dodger Stadium":           { runs:99,  hr:99,  xbh:99,  alt:340,  dims:"Neutral park, slight pitcher lean at night" },
  "Angel Stadium":            { runs:98,  hr:97,  xbh:98,  alt:160,  dims:"Neutral park, average dimensions" },
  "Guaranteed Rate":          { runs:99,  hr:98,  xbh:99,  alt:594,  dims:"Slight pitcher lean, wind often blows in" },

  // ── PITCHER-FRIENDLY ────────────────────────────────────────────────────
  "American Family":          { runs:98,  hr:95,  xbh:97,  alt:646,  dims:"Retractable dome, controlled environment, neutral-to-pitcher" },
  "Rogers":                   { runs:97,  hr:98,  xbh:96,  alt:249,  dims:"Turf dome, suppressed scoring" },
  "Busch Stadium":            { runs:97,  hr:96,  xbh:98,  alt:466,  dims:"Spacious outfield, neutral-to-pitcher" },
  "PNC Park":                 { runs:97,  hr:95,  xbh:98,  alt:730,  dims:"Deep CF, pitcher-friendly, picturesque" },
  "Kauffman":                 { runs:97,  hr:94,  xbh:97,  alt:750,  dims:"Large outfield, pitcher-friendly" },
  "Target Field":             { runs:97,  hr:96,  xbh:97,  alt:830,  dims:"Cold early season suppresses scoring" },
  "Progressive":              { runs:97,  hr:97,  xbh:97,  alt:650,  dims:"Neutral-to-mild pitcher lean, average dimensions" },
  "T-Mobile":                 { runs:96,  hr:94,  xbh:97,  alt:17,   dims:"Marine air suppresses carry, pitcher-friendly" },
  "Steinbrenner":             { runs:96,  hr:94,  xbh:95,  alt:10,   dims:"Minor league park (Rays 2025), pitcher-lean" },
  "George M. Steinbrenner":   { runs:96,  hr:94,  xbh:95,  alt:10,   dims:"Minor league park (Rays 2025), pitcher-lean" },
  "Citi Field":               { runs:96,  hr:95,  xbh:97,  alt:20,   dims:"Marine air, typically blows in, pitcher-friendly" },
  "Comerica":                 { runs:95,  hr:90,  xbh:97,  alt:600,  dims:"Deep CF and alleys, strong pitcher park" },
  "Tropicana":                { runs:94,  hr:92,  xbh:93,  alt:15,   dims:"Dome, suppressed scoring, pitcher-friendly" },
  "loanDepot":                { runs:94,  hr:92,  xbh:94,  alt:10,   dims:"Retractable dome, marine air, pitcher-friendly" },
  "Oracle Park":              { runs:93,  hr:87,  xbh:95,  alt:10,   dims:"Marine layer, cold SF air, one of the best pitcher parks" },
  "Petco":                    { runs:93,  hr:90,  xbh:93,  alt:62,   dims:"Marine layer, ocean air, strong pitcher park" },
};

// ═══════════════════════════════════════════════════════════════════════════
// WEATHER MODIFIER ENGINE
// Reads each game's weather object and returns additive index adjustments.
// All modifiers add/subtract from the base 100-scale park DNA values.
// ═══════════════════════════════════════════════════════════════════════════

function getWeatherMods(wx) {
  let runMod = 0, hrMod = 0, xbhMod = 0;
  const notes = [];

  // Roof closed — park DNA only, weather irrelevant
  if (wx.roof === 'Closed') {
    return {
      runMod: 0, hrMod: 0, xbhMod: 0,
      notes: ["Roof closed — weather neutralized. Park dimensions are the sole factor."]
    };
  }

  // ── TEMPERATURE ─────────────────────────────────────────────
  // Ball carry increases ~0.5% per degree above 72°F due to air density
  const temp = parseFloat(wx.temp);
  if (!isNaN(temp)) {
    if      (temp >= 90) { hrMod += 4; runMod += 2;   notes.push(`Extreme heat (${wx.temp}) significantly increases ball carry.`); }
    else if (temp >= 80) { hrMod += 2; runMod += 1.5; notes.push(`Warm temps (${wx.temp}) aid ball carry and boost offense.`); }
    else if (temp >= 72) { hrMod += 1; runMod += 0.5; }
    else if (temp <= 55) { hrMod -= 3; runMod -= 2;   notes.push(`Cold temps (${wx.temp}) suppress ball flight meaningfully.`); }
    else if (temp <= 65) { hrMod -= 1; runMod -= 0.5; }
  }

  // ── WIND ────────────────────────────────────────────────────
  // Direction relative to outfield wall is the key variable
  const windStr = wx.wind || "";
  const windSpd = parseFloat(windStr);
  if (!isNaN(windSpd) && windSpd > 0) {
    const wl     = windStr.toLowerCase();
    const isOut  = wl.includes("out");
    const isIn   = wl.includes("in");
    const isCF   = wl.includes("cf") || wl.includes("center");
    const isLF   = wl.includes("lf") || wl.includes("left");
    const isRF   = wl.includes("rf") || wl.includes("right");
    const isCross = wl.includes("cross") || wl.includes("across");
    const dir    = isCF ? "CF" : isLF ? "LF" : isRF ? "RF" : "the outfield";

    if (isOut) {
      if      (windSpd >= 15) { hrMod += 6; xbhMod += 4; runMod += 3; notes.push(`Strong wind (${windSpd} mph) blowing out to ${dir} — major HR and XBH boost.`); }
      else if (windSpd >= 10) { hrMod += 4; xbhMod += 3; runMod += 2; notes.push(`Wind (${windSpd} mph) blowing out to ${dir} — meaningful boost to ball carry.`); }
      else if (windSpd >=  6) { hrMod += 2; xbhMod += 1.5; runMod += 1; notes.push(`Light outblowing wind (${windSpd} mph to ${dir}) — modest lift.`); }
    } else if (isIn) {
      if      (windSpd >= 15) { hrMod -= 6; xbhMod -= 4; runMod -= 3; notes.push(`Strong wind (${windSpd} mph) blowing in from ${dir} — significant fly ball suppression.`); }
      else if (windSpd >= 10) { hrMod -= 4; xbhMod -= 3; runMod -= 2; notes.push(`Wind (${windSpd} mph) blowing in from ${dir} — fly balls suppressed.`); }
      else if (windSpd >=  6) { hrMod -= 2; xbhMod -= 1.5; runMod -= 1; notes.push(`Light inblowing wind (${windSpd} mph from ${dir}) — mild suppression.`); }
    } else if (isCross) {
      xbhMod += 1;
      notes.push(`Crosswind (${windSpd} mph) adds variance to ball flight direction.`);
    }
  }

  // ── HUMIDITY ────────────────────────────────────────────────
  // Drier air = less resistance = slight carry boost; very humid = modest suppression
  const hum = parseFloat(wx.humidity);
  if (!isNaN(hum)) {
    if      (hum <= 30) { hrMod += 2; notes.push(`Low humidity (${wx.humidity}) reduces air resistance — slight carry boost.`); }
    else if (hum >= 80) { hrMod -= 1; notes.push(`High humidity (${wx.humidity}) adds minor air resistance.`); }
  }

  return { runMod, hrMod, xbhMod, notes };
}

// ═══════════════════════════════════════════════════════════════════════════
// CORE FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

function getParkDNA(venue) {
  for (const key of Object.keys(PARK_DNA)) {
    if (venue.includes(key)) return { key, ...PARK_DNA[key] };
  }
  return { key: "Unknown", runs: 100, hr: 100, xbh: 100, alt: 100, dims: "No park data available" };
}

function calcParkFactor(g) {
  const dna = getParkDNA(g.venue);
  const { runMod, hrMod, xbhMod, notes } = getWeatherMods(g.weather);

  const adjRuns = dna.runs + runMod;
  const adjHR   = dna.hr   + hrMod;
  const adjXBH  = dna.xbh  + xbhMod;

  // Weighted composite: Runs 40%, HR 35%, XBH 25%
  const composite = (adjRuns * 0.40) + (adjHR * 0.35) + (adjXBH * 0.25);
  const score = Math.round(composite - 100);

  return { dna, adjRuns, adjHR, adjXBH, score, wxNotes: notes };
}

// ═══════════════════════════════════════════════════════════════════════════
// NARRATIVE TEMPLATE ENGINE
// Builds 2–4 sentence summary from rule-based conditionals.
// No AI required — all logic is deterministic.
// ═══════════════════════════════════════════════════════════════════════════

function buildPFNarrative(g, pf) {
  const { dna, adjRuns, adjHR, adjXBH, score, wxNotes } = pf;
  const parts = [];

  // Park character
  if      (dna.runs >= 108) parts.push(`<em>${g.venue}</em> is one of baseball's most hitter-friendly environments — ${dna.dims.toLowerCase()}.`);
  else if (dna.runs >= 104) parts.push(`<em>${g.venue}</em> plays as a meaningful hitter's park. ${dna.dims}.`);
  else if (dna.runs >= 101) parts.push(`<em>${g.venue}</em> carries a slight hitter lean in its baseline park factors. ${dna.dims}.`);
  else if (dna.runs <=  92) parts.push(`<em>${g.venue}</em> is one of the tougher scoring environments in the league — ${dna.dims.toLowerCase()}.`);
  else if (dna.runs <=  96) parts.push(`<em>${g.venue}</em> plays as a pitcher's park at baseline. ${dna.dims}.`);
  else if (dna.runs <=  99) parts.push(`<em>${g.venue}</em> is a mild pitcher's environment. ${dna.dims}.`);
  else                       parts.push(`<em>${g.venue}</em> is a neutral park, close to the MLB average across all categories.`);

  // Altitude callout (meaningful at 1000+ ft, only outdoors)
  if (dna.alt >= 1000 && g.weather.roof !== 'Closed') {
    parts.push(`Altitude of ~${dna.alt.toLocaleString()} ft above sea level reduces air resistance and adds carry to well-struck balls.`);
  }

  // Weather sentences
  wxNotes.forEach(n => parts.push(n));

  // HR / XBH specific callouts
  if      (adjHR >= 112 && adjXBH >= 108) parts.push(`Combined conditions strongly elevate both HR probability and extra-base hit potential today.`);
  else if (adjHR >= 108)                   parts.push(`HR index is notably elevated — environment favors hitters going deep.`);
  else if (adjHR <=  88)                   parts.push(`HR index is significantly suppressed — pitchers benefit from reduced fly ball carry.`);
  else if (adjXBH >= 108)                  parts.push(`Extra-base hit potential is above average even if HRs are not maximally boosted.`);
  else if (adjXBH <=  92)                  parts.push(`Extra-base hits are also suppressed — gap shots may stay in the park.`);

  // Final verdict
  if      (score >= 10) parts.push(`Overall environment leans <em>hitter-friendly</em> — favor the over, stacks, and power hitters.`);
  else if (score >=  5) parts.push(`Modest tilt toward hitters — slightly above-average scoring expected.`);
  else if (score <= -10) parts.push(`Overall environment leans <em>pitcher-friendly</em> — favor strikeout props and the under.`);
  else if (score <=  -5) parts.push(`Mild pitcher lean — below-average scoring environment today.`);
  else                   parts.push(`Conditions are close to neutral — park factor is not a strong lean either way.`);

  return parts.join(' ');
}

// ═══════════════════════════════════════════════════════════════════════════
// RENDER — called by the Dope Sheet render() function per game
// ═══════════════════════════════════════════════════════════════════════════

function renderParkFactor(g) {
  const pf = calcParkFactor(g);
  const { adjRuns, adjHR, adjXBH, score } = pf;

  const sign       = score > 0 ? '+' : '';
  const scoreClass = score >= 5 ? 'pos' : score <= -5 ? 'neg' : 'neu';
  const badgeLabel = score >= 5 ? 'HITTER FRIENDLY' : score <= -5 ? 'PITCHER FRIENDLY' : 'NEUTRAL PARK';
  const badgeClass = score >= 5 ? 'hitter' : score <= -5 ? 'pitcher' : 'neutral';

  const ixClass = v => v >= 105 ? 'above' : v <= 95 ? 'below' : 'avg';
  const ixSign  = v => v >= 100 ? `+${(v - 100).toFixed(0)}%` : `${(v - 100).toFixed(0)}%`;
  const barW    = v => Math.min(100, Math.max(0, 50 + (v - 100) * 2));
  const barClass = v => v >= 105 ? 'pos' : v <= 95 ? 'neg' : 'neu';

  const narrative = buildPFNarrative(g, pf);

  return `
  <div class="detail-section full">
    <div class="ds-title">Park Factor · Barrel Proof Index</div>
    <div class="pf-shell">
      <div class="pf-verdict">
        <div class="pf-badge ${badgeClass}">${badgeLabel}</div>
        <div class="pf-score-big ${scoreClass}">${sign}${score}</div>
        <div class="pf-score-lbl">BP Index</div>
      </div>
      <div class="pf-body">
        <div class="pf-indices">
          <div class="pf-index">
            <span class="pf-ix-val ${ixClass(adjRuns)}">${ixSign(adjRuns)}</span>
            <span class="pf-ix-lbl">Runs</span>
            <span class="pf-ix-sub">Index: ${adjRuns.toFixed(0)}</span>
          </div>
          <div class="pf-index">
            <span class="pf-ix-val ${ixClass(adjHR)}">${ixSign(adjHR)}</span>
            <span class="pf-ix-lbl">Home Runs</span>
            <span class="pf-ix-sub">Index: ${adjHR.toFixed(0)}</span>
          </div>
          <div class="pf-index">
            <span class="pf-ix-val ${ixClass(adjXBH)}">${ixSign(adjXBH)}</span>
            <span class="pf-ix-lbl">Extra Base Hits</span>
            <span class="pf-ix-sub">Index: ${adjXBH.toFixed(0)}</span>
          </div>
        </div>
        <div class="pf-bars">
          <div class="pf-bar-row">
            <span class="pf-bar-lbl">Runs</span>
            <div class="pf-bar-track"><div class="pf-bar-fill ${barClass(adjRuns)}" style="width:${barW(adjRuns)}%"></div></div>
            <span class="pf-bar-val ${barClass(adjRuns)}">${adjRuns.toFixed(0)}</span>
          </div>
          <div class="pf-bar-row">
            <span class="pf-bar-lbl">Home Runs</span>
            <div class="pf-bar-track"><div class="pf-bar-fill ${barClass(adjHR)}" style="width:${barW(adjHR)}%"></div></div>
            <span class="pf-bar-val ${barClass(adjHR)}">${adjHR.toFixed(0)}</span>
          </div>
          <div class="pf-bar-row">
            <span class="pf-bar-lbl">XBH</span>
            <div class="pf-bar-track"><div class="pf-bar-fill ${barClass(adjXBH)}" style="width:${barW(adjXBH)}%"></div></div>
            <span class="pf-bar-val ${barClass(adjXBH)}">${adjXBH.toFixed(0)}</span>
          </div>
        </div>
        <div class="pf-summary">${narrative}</div>
        <div class="pf-src">SOURCES: Baseball Savant Statcast Park Factors (3-yr 2022–2024) · FanGraphs Park Factors · Weather via NWS · Barrel Proof composite model</div>
      </div>
    </div>
  </div>`;
}
