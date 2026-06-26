/* GARUDA Intelligence Console (Phase 8) — router, typed-ish API client, views.
   Calls the AppSail analytics API same-origin; falls back to mock fixtures (mirroring
   the planted scenario) when an endpoint is unavailable, so the UI always renders. */
(function () {
  'use strict';
  var API = (window.GARUDA_CONFIG && window.GARUDA_CONFIG.apiBaseUrl) || '';

  // ---------- helpers ----------
  function h(s) { var t = document.createElement('template'); t.innerHTML = s.trim(); return t.content.firstChild; }
  function $(s, r) { return (r || document).querySelector(s); }
  function fmt(n) { return n == null ? '–' : Number(n).toLocaleString('en-IN'); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function ic(id, cls) { return '<svg class="' + (cls || '') + '"><use href="#' + id + '"/></svg>'; }
  function shimmer(n) { var s = ''; for (var i = 0; i < (n || 3); i++) s += '<div class="shimmer" style="height:54px;margin:8px 0"></div>'; return s; }

  async function jget(path, mockKey) {
    try { var r = await fetch(API + path); if (!r.ok) throw 0; return await r.json(); }
    catch (e) { return MOCK[mockKey]; }
  }
  async function jpost(path, body, mockKey) {
    try {
      var r = await fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
      if (!r.ok) throw 0; return await r.json();
    } catch (e) { return MOCK[mockKey]; }
  }

  // ---------- router ----------
  var loaded = {};
  var loaders = { overview: viewOverview, network: viewNetwork, map: viewMap, copilot: viewCopilot, alerts: viewAlerts };
  function go(view) {
    document.querySelectorAll('.nav a').forEach(function (a) { a.classList.toggle('active', a.dataset.view === view); });
    document.querySelectorAll('.view').forEach(function (v) { v.classList.remove('active'); });
    $('#view-' + view).classList.add('active');
    $('#crumb').textContent = '/ ' + ({ overview: 'Overview', network: 'Network Reveal', map: 'Hotspot Map', copilot: 'Copilot', alerts: 'Alerts & Risk' })[view];
    if (!loaded[view]) { loaded[view] = true; loaders[view](); }
    location.hash = view;
  }
  document.querySelectorAll('.nav a').forEach(function (a) { a.onclick = function () { go(a.dataset.view); }; });

  // ---------- OVERVIEW ----------
  async function viewOverview() {
    var v = $('#view-overview');
    v.innerHTML =
      '<div class="page-h"><div><h2>Operations Overview</h2><p>Live synthetic feed · Karnataka SCRB · ' +
      'one analyst, end-to-end intelligence.</p></div><div class="spacer"></div>' +
      '<button class="btn primary" id="ov-reveal">' + ic('i-net') + ' Open network reveal</button></div>' +
      '<div class="kpis" id="kpis">' + shimmer(1) + '</div>' +
      '<div class="grid" style="grid-template-columns:1.3fr 1fr">' +
      '<div class="card"><div class="card-h"><span class="k">Organized</span><h3>Cross-district rings</h3>' +
      '<span class="spacer"></span><span class="badge b-mut">shared phone / vehicle</span></div><div class="card-b" id="ov-rings">' + shimmer(3) + '</div></div>' +
      '<div class="card"><div class="card-h"><span class="k">Signals</span><h3>Emerging-trend alerts</h3></div><div class="card-b" id="ov-alerts">' + shimmer(3) + '</div></div>' +
      '</div>' +
      '<div class="card"><div class="card-h"><span class="k">Distribution</span><h3>Incidents by crime type</h3></div><div class="card-b" id="ov-crime">' + shimmer(2) + '</div></div>';
    $('#ov-reveal').onclick = function () { go('network'); };

    var stats = await jget('/stats', 'stats');
    var rings = await jget('/network/rings?top=6', 'rings');
    var an = await jpost('/anomaly/run', { write: false }, 'anomaly');
    var geo = await jget('/geo/districts', 'geo');

    var alerts = (an && an.sample) || [];
    $('#kpis').innerHTML = [
      kpi('Incidents', fmt(stats.incidents), 'tracked FIRs', 'i-act', ''),
      kpi('Entities', fmt(stats.entities), 'persons / phones / vehicles', 'i-users', ''),
      kpi('Cross-district rings', fmt((rings.rings || []).length), 'organized networks', 'i-net', 'accent'),
      kpi('Active alerts', fmt(alerts.length), 'emerging-trend spikes', 'i-siren', 'danger')
    ].join('');

    var rs = (rings.rings || []);
    $('#ov-rings').innerHTML = rs.length ? '<div class="list stagger">' + rs.map(function (r, i) {
      return '<div class="li" style="cursor:pointer" data-king="' + esc(r.kingpin_id) + '">' +
        '<span class="lead" style="background:rgba(249,168,37,.13);border-color:rgba(249,168,37,.3)">' + ic('i-target') + '</span>' +
        '<div><div class="main-t">' + esc(r.kingpin_label) + ' <span class="faint mono">· ring #' + (i + 1) + '</span></div>' +
        '<div class="sub-t">' + r.persons + ' members · ' + (r.shared_links || []).map(esc).join(', ') + '</div></div>' +
        '<div class="end"><span class="badge b-danger">' + r.district_count + ' districts</span><div class="faint" style="margin-top:5px">' + esc((r.districts || []).join(' ')) + '</div></div></div>';
    }).join('') + '</div>' : '<div class="empty">No rings.</div>';
    $('#ov-rings').querySelectorAll('[data-king]').forEach(function (el) {
      el.onclick = function () { NET.pending = el.dataset.king; go('network'); };
    });

    $('#ov-alerts').innerHTML = alerts.length ? '<div class="list stagger">' + alerts.slice(0, 5).map(function (a) {
      return '<div class="li"><span class="dot ' + (a.severity === 'high' ? 'danger' : 'warn') + '"></span>' +
        '<div><div class="main-t">' + esc(a.crime_type) + ' · ' + esc(a.district_code) + '</div>' +
        '<div class="sub-t">' + esc(a.window_start) + ' · baseline ×' + (a.ratio || '?') + '</div></div>' +
        '<div class="end"><span class="badge ' + (a.severity === 'high' ? 'b-danger' : 'b-warn') + '">z ' + (a.z_score || '?') + '</span></div></div>';
    }).join('') + '</div>' : '<div class="empty">No alerts.</div>';

    var byType = {};
    (geo.districts || []).forEach(function (d) { });
    var crimes = (stats.by_crime) || MOCK.stats.by_crime;
    var maxc = Math.max.apply(null, crimes.map(function (c) { return c[1]; }));
    $('#ov-crime').innerHTML = '<div class="grid" style="gap:11px">' + crimes.slice(0, 8).map(function (c) {
      return '<div style="display:grid;grid-template-columns:170px 1fr 56px;gap:12px;align-items:center">' +
        '<span style="font-size:12.5px">' + esc(c[0]) + '</span>' +
        '<div class="bar"><span style="width:' + (100 * c[1] / maxc).toFixed(1) + '%"></span></div>' +
        '<span class="mono tnum faint" style="text-align:right">' + fmt(c[1]) + '</span></div>';
    }).join('') + '</div>';
  }
  function kpi(t, v, d, icon, cls) {
    return '<div class="card kpi ' + cls + '"><div class="ic">' + ic(icon) + '</div>' +
      '<div class="t">' + t + '</div><div class="v tnum">' + v + '</div><div class="d">' + d + '</div></div>';
  }

  // ---------- NETWORK ----------
  var NET = { graph: null, pending: null };
  async function viewNetwork() {
    var v = $('#view-network');
    v.innerHTML = '<div class="page-h"><div><h2>Co-offender Network Reveal</h2>' +
      '<p>Siloed FIRs → one visible gang. Node size = involvement, colour = community, ' +
      '<span style="color:var(--accent)">amber ring = kingpin</span>.</p></div><div class="spacer"></div>' +
      '<div id="ring-chips" style="display:flex;gap:8px;flex-wrap:wrap"></div></div>' +
      '<div class="stage"><canvas id="net-canvas"></canvas>' +
      '<div class="legend" id="net-legend"></div><div id="net-detail"></div></div>';
    var rings = await jget('/network/rings?top=6', 'rings');
    var rs = rings.rings || [];
    $('#nav-rings').textContent = rs.length;
    $('#ring-chips').innerHTML = rs.map(function (r, i) {
      return '<button class="chip" data-king="' + esc(r.kingpin_id) + '">' + esc(r.kingpin_label.split(' ')[0]) + ' · ' + r.district_count + 'd</button>';
    }).join('');
    $('#ring-chips').querySelectorAll('[data-king]').forEach(function (b) { b.onclick = function () { loadEgo(b.dataset.king); }; });
    var start = NET.pending || (rs[0] && rs[0].kingpin_id); NET.pending = null;
    if (start) loadEgo(start);
  }
  async function loadEgo(kingId) {
    var ego = await jget('/network/' + encodeURIComponent(kingId) + '?radius=2', 'ego');
    if (NET.graph) NET.graph.stop();
    var canvas = $('#net-canvas');
    NET.graph = GARUDA_GRAPH.render(canvas, ego, { kingpin: kingId, onSelect: showNode });
    $('#net-legend').innerHTML =
      '<span><span class="dot" style="background:#3b82f6;box-shadow:0 0 8px #3b82f6"></span> community A</span>' +
      '<span><span class="dot" style="background:#f9a825;box-shadow:0 0 8px #f9a825"></span> community B</span>' +
      '<span style="color:#f9a825">◎ kingpin</span><span>☎ phone · ⌗ vehicle</span>';
    var king = (ego.nodes || []).filter(function (n) { return n.id === kingId; })[0];
    if (king) showNode(king);
  }
  function showNode(n) {
    $('#net-detail').innerHTML = '<div class="detail"><h4>' + esc(n.label || n.id) + '</h4>' +
      '<div class="muted mono" style="font-size:11px;margin-top:2px">' + esc(n.type) + ' · ' + esc(n.id) + '</div>' +
      '<div class="meta"><b>incidents</b><span class="mono">' + (n.incident_count || 0) + '</span>' +
      '<b>strength</b><span class="mono">' + (n.strength || 0) + '</span>' +
      '<b>betweenness</b><span class="mono">' + (n.betweenness != null ? n.betweenness : '–') + '</span>' +
      '<b>community</b><span class="mono">#' + (n.community != null ? n.community : '–') + '</span>' +
      '<b>districts</b><span class="mono">' + esc((n.districts || []).join(' ') || '–') + '</span></div>' +
      '<button class="btn" style="margin-top:14px;width:100%" onclick="GARUDA_APP.ask(\'incidents involving ' + esc(n.label) + '\')">' + ic('i-chat') + ' Ask copilot</button></div>';
  }

  // ---------- MAP ----------
  async function viewMap() {
    var v = $('#view-map');
    v.innerHTML = '<div class="page-h"><div><h2>Hotspot Map</h2><p>District incident load — bubble size = volume, ' +
      'colour = intensity, pulsing = top hotspots. Click a district to drill down.</p></div></div>' +
      '<div class="grid" style="grid-template-columns:1fr 300px"><div class="mapwrap" id="mapwrap">' + shimmer(1) + '</div>' +
      '<div class="card"><div class="card-h"><span class="k">Drill-down</span><h3>District</h3></div><div class="card-b" id="map-panel"><div class="empty">Select a district on the map.</div></div></div></div>';
    var geo = await jget('/geo/districts', 'geo');
    drawMap(geo.districts || []);
  }
  function drawMap(ds) {
    if (!ds.length) { $('#mapwrap').innerHTML = '<div class="empty">No geo data.</div>'; return; }
    var W = 760, H = 540, pad = 54;
    var lons = ds.map(function (d) { return d.lng; }), lats = ds.map(function (d) { return d.lat; });
    var minx = Math.min.apply(null, lons), maxx = Math.max.apply(null, lons);
    var miny = Math.min.apply(null, lats), maxy = Math.max.apply(null, lats);
    var maxN = Math.max.apply(null, ds.map(function (d) { return d.incidents; }));
    function X(l) { return pad + (l - minx) / (maxx - minx || 1) * (W - 2 * pad); }
    function Y(l) { return H - pad - (l - miny) / (maxy - miny || 1) * (H - 2 * pad); }
    function col(n) { var t = n / maxN; return t > .66 ? '#ef4444' : t > .33 ? '#f9a825' : '#3b82f6'; }
    var top = ds.slice().sort(function (a, b) { return b.incidents - a.incidents; }).slice(0, 6).map(function (d) { return d.code; });
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '">';
    for (var gx = 0; gx <= 6; gx++) svg += '<line x1="' + (pad + gx * (W - 2 * pad) / 6) + '" y1="' + pad + '" x2="' + (pad + gx * (W - 2 * pad) / 6) + '" y2="' + (H - pad) + '" stroke="rgba(120,150,200,.06)"/>';
    for (var gy = 0; gy <= 5; gy++) svg += '<line x1="' + pad + '" y1="' + (pad + gy * (H - 2 * pad) / 5) + '" x2="' + (W - pad) + '" y2="' + (pad + gy * (H - 2 * pad) / 5) + '" stroke="rgba(120,150,200,.06)"/>';
    ds.forEach(function (d) {
      var r = 6 + 22 * Math.sqrt(d.incidents / maxN), x = X(d.lng), y = Y(d.lat), c = col(d.incidents);
      if (top.indexOf(d.code) >= 0)
        svg += '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + c + '" opacity=".5" class="pulse" style="--r0:' + r + 'px;animation:pulse 2.4s infinite ease-out"/>';
      svg += '<circle class="dist" data-code="' + d.code + '" cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + c + '" fill-opacity=".22" stroke="' + c + '" stroke-width="1.6"/>';
      svg += '<text x="' + x + '" y="' + (y + 3) + '" text-anchor="middle" font-family="Fira Code,monospace" font-size="9.5" fill="#e8eef9" pointer-events="none">' + esc(d.code) + '</text>';
    });
    svg += '</svg>';
    $('#mapwrap').innerHTML = svg;
    $('#mapwrap').querySelectorAll('.dist').forEach(function (c) {
      c.onclick = function () {
        var d = ds.filter(function (x) { return x.code === c.dataset.code; })[0];
        $('#map-panel').innerHTML = '<h4 class="mono" style="font-size:15px">' + esc(d.name || d.code) + '</h4>' +
          '<div class="meta detail" style="display:grid;grid-template-columns:auto 1fr;gap:6px 12px;margin-top:12px;font-size:12.5px">' +
          '<b class="mono muted">code</b><span class="mono">' + esc(d.code) + '</span>' +
          '<b class="mono muted">incidents</b><span class="mono">' + fmt(d.incidents) + '</span>' +
          '<b class="mono muted">top crime</b><span>' + esc(d.top_crime || '–') + '</span></div>' +
          '<button class="btn" style="margin-top:14px;width:100%" onclick="GARUDA_APP.ask(\'crime in ' + esc(d.code) + '\')">' + ic('i-chat') + ' Ask copilot about ' + esc(d.code) + '</button>';
      };
    });
  }

  // ---------- COPILOT ----------
  var CHAT = [];
  async function viewCopilot() {
    var v = $('#view-copilot');
    v.innerHTML = '<div class="page-h"><div><h2>Intelligence Copilot</h2><p>Plain-English questions over the FIR corpus — ' +
      'every answer is grounded in cited records. Never asserts guilt.</p></div></div>' +
      '<div class="card pad chat"><div class="thread" id="thread"></div>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;padding:4px 0 12px" id="chips"></div>' +
      '<div class="composer"><input id="cin" placeholder="e.g. two-wheeler theft in BNU in March 2025" autocomplete="off"/>' +
      '<button class="btn primary" id="csend">' + ic('i-send') + ' Ask</button></div></div>';
    var examples = ['chain snatching in BNU', 'house burglary in Mysuru in May 2024', 'two-wheeler theft in BNU in March 2025', 'is the accused guilty?'];
    $('#chips').innerHTML = examples.map(function (e) { return '<button class="chip">' + esc(e) + '</button>'; }).join('');
    $('#chips').querySelectorAll('.chip').forEach(function (c) { c.onclick = function () { ask(c.textContent); }; });
    $('#csend').onclick = function () { ask($('#cin').value); };
    $('#cin').onkeydown = function (e) { if (e.key === 'Enter') ask($('#cin').value); };
    if (!CHAT.length) push('bot', { answer: 'Ask me about incidents, locations, crime types or time windows. I return matching FIRs with citations — and I won\'t make accusations.', citations: [] });
    else renderThread();
  }
  function renderThread() {
    var t = $('#thread'); if (!t) return;
    t.innerHTML = CHAT.map(function (m) {
      if (m.role === 'user') return '<div class="msg user"><div class="who">SR</div><div class="bubble">' + esc(m.text) + '</div></div>';
      var r = m.res, cites = (r.citations || []);
      var body = '<div class="bubble' + (r.refused ? ' refused' : '') + '">' + esc(r.answer || '').replace(/\n/g, '<br>');
      if (cites.length) body += '<div class="cites">' + cites.slice(0, 6).map(function (c) {
        return '<a class="cite"><div class="fr">' + ic('i-doc') + ' ' + esc(c.fir_no || c.incident_id) + '</div>' +
          '<div class="mt"><span class="badge b-info">' + esc(c.crime_type) + '</span><span class="mono faint">' + esc(c.district_code) + ' · ' + esc(String(c.occurred_at || '').slice(0, 10)) + '</span></div>' +
          '<div class="sn">' + esc(c.snippet || '') + '</div></a>';
      }).join('') + '</div>';
      if (r.guardrail) body += '<div class="gr">' + ic('i-shield') + '<span>' + esc(r.guardrail) + '</span></div>';
      body += '</div>';
      return '<div class="msg bot"><div class="who">AI</div>' + body + '</div>';
    }).join('');
    t.scrollTop = t.scrollHeight;
  }
  function push(role, payload) { CHAT.push(role === 'user' ? { role: 'user', text: payload } : { role: 'bot', res: payload }); renderThread(); }
  async function ask(q) {
    q = (q || '').trim(); if (!q) return;
    if (!loaded.copilot) { loaded.copilot = true; }
    go('copilot');
    setTimeout(async function () {
      $('#cin') && ($('#cin').value = '');
      push('user', q);
      var pend = { role: 'bot', res: { answer: 'Searching the FIR corpus…', citations: [] } }; CHAT.push(pend); renderThread();
      var res = await jpost('/copilot', { query: q }, mockCopilot(q));
      CHAT.pop(); push('bot', res);
    }, 30);
  }
  function mockCopilot(q) { return /guilt|guilty|culprit/i.test(q) ? 'copilotRefuse' : 'copilot'; }

  // ---------- ALERTS & RISK ----------
  async function viewAlerts() {
    var v = $('#view-alerts');
    v.innerHTML = '<div class="page-h"><div><h2>Alerts &amp; Risk Forecast</h2><p>Emerging-trend spikes, ' +
      'walk-forward risk forecast, and the fairness audit.</p></div></div>' +
      '<div class="grid" style="grid-template-columns:1.2fr 1fr"><div class="card"><div class="card-h"><span class="k">Detected</span><h3>Emerging-trend alerts</h3></div><div class="card-b" id="al-list">' + shimmer(4) + '</div></div>' +
      '<div class="card"><div class="card-h"><span class="k">Fairness</span><h3>Predicted vs actual per ward</h3><span class="spacer"></span><span class="badge b-warn" id="al-flag">·</span></div><div class="card-b" id="al-fair">' + shimmer(4) + '</div></div></div>' +
      '<div class="card"><div class="card-h"><span class="k">Forecast</span><h3>Highest-risk cells (next period)</h3><span class="spacer"></span><span class="mono faint" id="al-model">walk-forward</span></div><div class="card-b" id="al-risk">' + shimmer(3) + '</div></div>';
    var an = await jpost('/anomaly/run', { write: false }, 'anomaly');
    var alerts = (an && an.sample) || [];
    $('#nav-alerts').textContent = alerts.length;
    var maxz = Math.max.apply(null, alerts.map(function (a) { return a.z_score || 1; }));
    $('#al-list').innerHTML = '<div class="list">' + alerts.map(function (a) {
      return '<div class="li"><span class="lead" style="background:' + (a.severity === 'high' ? 'var(--danger-soft)' : 'var(--warn-soft)') + '">' + ic('i-alert') + '</span>' +
        '<div style="flex:1"><div class="main-t">' + esc(a.crime_type) + ' · ' + esc(a.district_code) + ' <span class="badge ' + (a.severity === 'high' ? 'b-danger' : 'b-warn') + '">' + esc(a.severity) + '</span></div>' +
        '<div class="sub-t">' + esc(a.detail || '') + '</div><div class="bar ' + (a.severity === 'high' ? 'danger' : 'amber') + '" style="margin-top:7px"><span style="width:' + (100 * (a.z_score || 1) / maxz).toFixed(0) + '%"></span></div></div></div>';
    }).join('') + '</div>';

    var risk = await jget('/risk/top?n=10', 'risktop');
    $('#al-model').textContent = (risk.top && risk.top[0] && risk.top[0].model_version) || 'lgbm';
    $('#al-risk').innerHTML = '<table><thead><tr><th>District</th><th>Crime type</th><th class="num">Risk</th><th>Why (SHAP)</th></tr></thead><tbody>' +
      (risk.top || []).map(function (t) {
        var drv = []; try { drv = JSON.parse(t.top_drivers); } catch (e) { drv = t.top_drivers || []; }
        return '<tr><td class="mono">' + esc(t.district_code) + '</td><td>' + esc(t.crime_type) + '</td>' +
          '<td class="num">' + ((t.risk_score * 100) || 0).toFixed(0) + '%</td>' +
          '<td>' + drv.slice(0, 3).map(function (d) { return '<span class="badge b-mut">' + esc(d) + '</span>'; }).join(' ') + '</td></tr>';
      }).join('') + '</tbody></table>';

    var fair = await jget('/risk/fairness', 'fair');
    var wards = (fair.wards || []).slice(0, 8), fs = fair.summary || {};
    $('#al-flag').textContent = (fs.over_predicted || 0) + ' flagged';
    $('#al-fair').innerHTML = '<div class="grid" style="gap:10px">' + wards.map(function (w) {
      var ratio = w.ratio || 1, over = w.over_predicted, pct = Math.min(100, ratio / 1.6 * 100);
      return '<div style="display:grid;grid-template-columns:54px 1fr 48px;gap:10px;align-items:center">' +
        '<span class="mono" style="font-size:12px">' + esc(w.area_code) + '</span>' +
        '<div class="bar ' + (over ? 'danger' : '') + '"><span style="width:' + pct.toFixed(0) + '%"></span></div>' +
        '<span class="mono tnum faint" style="text-align:right;font-size:11.5px">×' + ratio.toFixed(2) + '</span></div>';
    }).join('') + '</div><p class="faint" style="margin-top:12px;font-size:11.5px">Wards predicted > 1.3× their actual rate are flagged for review (over-policing guard).</p>';
  }

  // ---------- global search → copilot ----------
  $('#globalq').onkeydown = function (e) { if (e.key === 'Enter') ask(e.target.value); };

  // ---------- MOCK fixtures (planted scenario) ----------
  var MOCK = {
    stats: { incidents: 10130, entities: 14608, districts: 31, crime_types: 16, by_crime: [['Two-wheeler theft', 1642], ['Theft', 1380], ['House burglary', 1325], ['Chain snatching', 1037], ['Assault', 834], ['Cheating', 727], ['Robbery', 624], ['Motor vehicle theft', 534]] },
    rings: { rings: [{ kingpin_id: 'ENT014602', kingpin_label: 'Aayush Zachariah', persons: 5, districts: ['BNU', 'KLR', 'RMN', 'TMK'], district_count: 4, incident_count: 10, shared_links: ['+916534933629', 'KA68MC3164'] }] },
    ego: {
      center: 'ENT014602', node_count: 7, nodes: [
        { id: 'ENT014602', label: 'Aayush Zachariah', type: 'person', strength: 31, betweenness: 0, community: 0, incident_count: 9, districts: ['BNU', 'RMN', 'TMK', 'KLR'] },
        { id: 'ENT014603', label: 'Joshua Dhar', type: 'person', strength: 15, community: 0, incident_count: 4, districts: ['BNU', 'TMK'] },
        { id: 'ENT014604', label: 'Urvi Amble', type: 'person', strength: 18, community: 0, incident_count: 5, districts: ['BNU', 'KLR'] },
        { id: 'ENT014605', label: 'Imaran Pal', type: 'person', strength: 14, community: 0, incident_count: 4, districts: ['RMN'] },
        { id: 'ENT014606', label: 'Wyatt Thaker', type: 'person', strength: 2, community: 0, incident_count: 1, districts: ['TMK'] },
        { id: 'ENT014607', label: '+916534933629', type: 'phone', strength: 33, community: 0, incident_count: 10, districts: ['BNU', 'RMN', 'TMK', 'KLR'] },
        { id: 'ENT014608', label: 'KA68MC3164', type: 'vehicle', strength: 33, community: 0, incident_count: 10, districts: ['BNU', 'RMN', 'TMK', 'KLR'] }
      ],
      edges: [['ENT014602', 'ENT014603'], ['ENT014602', 'ENT014604'], ['ENT014602', 'ENT014607'], ['ENT014602', 'ENT014608'], ['ENT014603', 'ENT014607'], ['ENT014604', 'ENT014608'], ['ENT014605', 'ENT014607'], ['ENT014606', 'ENT014608'], ['ENT014604', 'ENT014607'], ['ENT014603', 'ENT014608']].map(function (e) { return { source: e[0], target: e[1], weight: 3, kinds: ['co_offence'] }; })
    },
    anomaly: { sample: [{ crime_type: 'House burglary', district_code: 'BNU', window_start: '2025-04-01', severity: 'high', z_score: 16.9, ratio: 4.8, detail: 'House burglary in BNU 2025-04: 63 incidents vs baseline 13/mo (×4.8, z=16.9)' }, { crime_type: 'Two-wheeler theft', district_code: 'BNU', window_start: '2025-03-01', severity: 'high', z_score: 12.1, ratio: 4.0, detail: 'Two-wheeler theft in BNU 2025-03: 72 vs baseline 18/mo (×4.0, z=12.1)' }, { crime_type: 'Two-wheeler theft', district_code: 'MYS', window_start: '2024-09-01', severity: 'high', z_score: 11.5, ratio: 5.2, detail: 'Two-wheeler theft in MYS 2024-09: 21 vs baseline 4/mo (×5.2, z=11.5)' }] },
    geo: { districts: [{ code: 'BNU', name: 'Bengaluru Urban', incidents: 980, lat: 12.97, lng: 77.59, top_crime: 'Two-wheeler theft' }, { code: 'MYS', name: 'Mysuru', incidents: 410, lat: 12.31, lng: 76.65, top_crime: 'House burglary' }, { code: 'BEL', name: 'Belagavi', incidents: 360, lat: 15.85, lng: 74.5, top_crime: 'Theft' }, { code: 'KLB', name: 'Kalaburagi', incidents: 300, lat: 17.33, lng: 76.83, top_crime: 'Assault' }, { code: 'TMK', name: 'Tumakuru', incidents: 280, lat: 13.34, lng: 77.1, top_crime: 'Chain snatching' }, { code: 'RMN', name: 'Ramanagara', incidents: 240, lat: 12.72, lng: 77.28, top_crime: 'Chain snatching' }, { code: 'KLR', name: 'Kolar', incidents: 220, lat: 13.13, lng: 78.13, top_crime: 'Chain snatching' }, { code: 'DK', name: 'Dakshina Kannada', incidents: 260, lat: 12.87, lng: 75.0, top_crime: 'Cheating' }] },
    risktop: { top: [{ district_code: 'BNU', crime_type: 'Theft', risk_score: 0.42, top_drivers: '["roll_28","population","crime_code"]', model_version: 'lgbm-p6-v1' }, { district_code: 'BNU', crime_type: 'Two-wheeler theft', risk_score: 0.41, top_drivers: '["roll_28","urbanization","dow"]', model_version: 'lgbm-p6-v1' }, { district_code: 'MYS', crime_type: 'House burglary', risk_score: 0.33, top_drivers: '["lag_7","density","month"]', model_version: 'lgbm-p6-v1' }] },
    fair: { summary: { wards: 31, over_predicted: 4, flag_ratio: 1.3, max_ratio: 1.61 }, wards: [{ area_code: 'BNU', ratio: 1.61, over_predicted: true }, { area_code: 'MYS', ratio: 1.44, over_predicted: true }, { area_code: 'BEL', ratio: 1.38, over_predicted: true }, { area_code: 'DK', ratio: 1.33, over_predicted: true }, { area_code: 'KLB', ratio: 1.18, over_predicted: false }, { area_code: 'TMK', ratio: 1.02, over_predicted: false }, { area_code: 'RMN', ratio: 0.94, over_predicted: false }, { area_code: 'KLR', ratio: 0.81, over_predicted: false }] },
    copilot: { answer: 'Found matching FIR records. Top results are cited below — these surface records, not determinations of guilt.', citations: [{ fir_no: 'BNU20/2024/0028', incident_id: 'INC0xx', crime_type: 'Chain snatching', district_code: 'BNU', occurred_at: '2024-01-24', snippet: 'Gold chain snatched near MG Road; accused fled on a two-wheeler bearing KA68MC3164.' }, { fir_no: 'RMN03/2024/0011', incident_id: 'INC010003', crime_type: 'Chain snatching', district_code: 'RMN', occurred_at: '2024-03-08', snippet: 'Two miscreants snatched a chain and sped away; call record links +916534933629.' }], guardrail: 'This system surfaces FIR records matching the query; it does not determine guilt.' },
    copilotRefuse: { refused: true, reason: 'guilt_determination', answer: 'This system surfaces FIR records matching the query; it does not determine guilt. Persons named are as recorded in the FIR, pending investigation/trial.', citations: [], guardrail: 'Surfaces records, never asserts guilt.' }
  };

  window.GARUDA_APP = { go: go, ask: ask };
  var _init = (location.hash || '#overview').slice(1);
  go(_init in loaders ? _init : 'overview');
})();
