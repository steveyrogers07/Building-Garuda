/* GARUDA Intelligence Workbench (Iteration 11).
   Object-centric investigation console: universal search -> case files & entity
   dossiers in tabs -> network/map/copilot/alerts modules. Role-aware (X-Role/X-Scope
   headers drive RBAC + PII masking server-side); deep-linkable (#case/INC…,
   #entity/ENT…); falls back to mock fixtures offline so the UI always renders. */
(function () {
  'use strict';
  var API = (window.GARUDA_CONFIG && window.GARUDA_CONFIG.apiBaseUrl) || '';

  // ---------- helpers ----------
  function $(s, r) { return (r || document).querySelector(s); }
  function fmt(n) { return n == null ? '–' : Number(n).toLocaleString('en-IN'); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function ic(id, cls) { return '<svg class="' + (cls || '') + '"><use href="#' + id + '"/></svg>'; }
  function shimmer(n) { var s = ''; for (var i = 0; i < (n || 3); i++) s += '<div class="shimmer" style="height:54px;margin:8px 0"></div>'; return s; }
  function d10(s) { return String(s || '').slice(0, 10); }
  function typeIcon(t) { return t === 'vehicle' ? 'i-car' : t === 'phone' ? 'i-phone' : t === 'case' ? 'i-doc' : 'i-user'; }
  function notice(kind, title, body, extra) {
    return '<div class="notice ' + (kind || '') + '">' + ic(kind === 'err' ? 'i-alert' : 'i-lock') +
      '<div><div class="nt">' + esc(title) + '</div><div class="nb">' + esc(body) + '</div>' + (extra || '') + '</div></div>';
  }

  // ---------- principal (role switcher drives RBAC + masking) ----------
  var ROLE = { role: 'scrb-admin', scope: '' };
  try { var rr = sessionStorage.getItem('garuda.role'); if (rr) ROLE = JSON.parse(rr); } catch (e) { }
  function roleHeaders() {
    var h = { 'X-Actor': 'sr', 'X-Role': ROLE.role };
    if (ROLE.scope) h['X-Scope'] = ROLE.scope;
    return h;
  }

  // ---------- API client (mock fallback offline; typed errors online) ----------
  async function jget(path, mockKey) {
    try { var r = await fetch(API + path, { headers: roleHeaders() }); if (!r.ok) throw 0; return await r.json(); }
    catch (e) { return MOCK[mockKey]; }
  }
  async function jpost(path, body, mockKey) {
    try {
      var r = await fetch(API + path, { method: 'POST', headers: Object.assign({ 'Content-Type': 'application/json' }, roleHeaders()), body: JSON.stringify(body || {}) });
      if (!r.ok) throw 0; return await r.json();
    } catch (e) { return MOCK[mockKey]; }
  }
  async function jgetx(path, mockKey) {   // object reads: keep HTTP error semantics (403/404)
    var r;
    try { r = await fetch(API + path, { headers: roleHeaders() }); }
    catch (e) { return MOCK[mockKey]; }   // offline preview -> mock
    if (r.ok) return r.json();
    var detail = ''; try { detail = (await r.json()).detail || ''; } catch (e) { }
    return { __err: r.status, detail: detail };
  }

  // ---------- workspace tabs + router ----------
  var MODULES = { overview: 'Overview', network: 'Network Reveal', map: 'Hotspot Map', copilot: 'Copilot', alerts: 'Alerts & Risk' };
  var loaders = { overview: viewOverview, network: viewNetwork, map: viewMap, copilot: viewCopilot, alerts: viewAlerts };
  var loaded = {}, RENDERED = {};
  var TABS = [];
  try { TABS = JSON.parse(sessionStorage.getItem('garuda.tabs') || '[]') || []; } catch (e) { TABS = []; }
  var ACTIVE = { kind: 'module', key: 'overview' };
  var NAVLOCK = false;

  function saveTabs() { try { sessionStorage.setItem('garuda.tabs', JSON.stringify(TABS)); } catch (e) { } }
  function tabKey(t) { return t.type + '/' + t.id; }
  function objSection(t) {
    var id = 'view-obj-' + t.type + '-' + t.id.replace(/[^A-Za-z0-9_-]/g, '');
    var el = document.getElementById(id);
    if (!el) { el = document.createElement('section'); el.id = id; el.className = 'view'; $('#content').appendChild(el); }
    return el;
  }
  function renderTabs() {
    var ts = $('#tabstrip');
    if (!TABS.length) { ts.innerHTML = ''; return; }
    ts.innerHTML = '<span class="wsl">Workspace</span>' + TABS.map(function (t, i) {
      var act = ACTIVE.kind === 'object' && ACTIVE.type === t.type && ACTIVE.id === t.id;
      return '<span class="tab' + (act ? ' active' : '') + '" data-i="' + i + '">' + ic(typeIcon(t.type === 'case' ? 'case' : t.icon || 'person')) +
        '<span class="tl">' + esc(t.title || t.id) + '</span><span class="x" data-x="' + i + '">' + ic('i-x') + '</span></span>';
    }).join('');
    ts.querySelectorAll('.tab').forEach(function (el) {
      el.onclick = function (ev) {
        var i = +el.dataset.i;
        if (ev.target.closest('[data-x]')) { closeTab(i); return; }
        activateObject(TABS[i]);
      };
    });
  }
  function closeTab(i) {
    var t = TABS.splice(i, 1)[0]; saveTabs();
    delete RENDERED[tabKey(t)];
    var el = objSection(t); el.remove();
    if (ACTIVE.kind === 'object' && ACTIVE.type === t.type && ACTIVE.id === t.id) {
      if (TABS.length) activateObject(TABS[Math.max(0, i - 1)]); else go('overview');
    } else renderTabs();
  }
  function setHash(h) { NAVLOCK = true; location.hash = h; setTimeout(function () { NAVLOCK = false; }, 0); }

  function go(view) {
    ACTIVE = { kind: 'module', key: view };
    document.querySelectorAll('.nav a').forEach(function (a) { a.classList.toggle('active', a.dataset.view === view); });
    document.querySelectorAll('.view').forEach(function (v) { v.classList.remove('active'); });
    $('#view-' + view).classList.add('active');
    $('#crumb').textContent = '/ ' + MODULES[view];
    if (!loaded[view]) { loaded[view] = true; loaders[view](); }
    renderTabs(); setHash(view);
  }
  function openObject(type, id, title, icon) {
    var t = TABS.find(function (x) { return x.type === type && x.id === id; });
    if (!t) { t = { type: type, id: id, title: title || id, icon: icon }; TABS.push(t); saveTabs(); }
    else if (title) { t.title = title; saveTabs(); }
    activateObject(t);
  }
  function activateObject(t) {
    ACTIVE = { kind: 'object', type: t.type, id: t.id };
    document.querySelectorAll('.nav a').forEach(function (a) { a.classList.remove('active'); });
    document.querySelectorAll('.view').forEach(function (v) { v.classList.remove('active'); });
    var el = objSection(t); el.classList.add('active');
    $('#crumb').textContent = '/ ' + (t.type === 'case' ? 'Case ' : 'Entity ') + t.id;
    if (!RENDERED[tabKey(t)]) { RENDERED[tabKey(t)] = true; (t.type === 'case' ? viewCase : viewEntity)(t, el); }
    renderTabs(); setHash(t.type + '/' + t.id);
  }
  function route() {
    if (NAVLOCK) return;
    var h = (location.hash || '#overview').slice(1);
    var m = h.match(/^(case|entity)\/(.+)$/);
    if (m) openObject(m[1], decodeURIComponent(m[2]));
    else if (MODULES[h]) go(h);
    else go('overview');
  }
  window.addEventListener('hashchange', route);
  document.querySelectorAll('.nav a').forEach(function (a) { a.onclick = function () { go(a.dataset.view); }; });

  // ---------- CASE FILE ----------
  async function viewCase(t, el) {
    el.innerHTML = shimmer(4);
    var c = await jgetx('/case/' + encodeURIComponent(t.id), 'case');
    if (c.__err === 403) { el.innerHTML = notice('', 'Access restricted', (c.detail || 'This case is outside your jurisdiction or role.') + ' Current role: ' + ROLE.role + (ROLE.scope ? ':' + ROLE.scope : '') + '. Switch role in the sidebar to compare access.'); return; }
    if (c.__err === 404 || c.error) { el.innerHTML = notice('err', 'Case not found', 'No FIR with id "' + t.id + '" exists in the canonical store.'); return; }
    var inc = c.incident || {};
    t.title = inc.fir_no || t.id; saveTabs(); renderTabs();

    var parties = (c.parties || []).map(function (p) {
      var clickable = !!p.canonical_id;
      return '<div class="li' + (clickable ? ' rowlink' : '') + '"' + (clickable ? ' data-ent="' + esc(p.canonical_id) + '" data-lab="' + esc(p.value) + '"' : '') + '>' +
        '<span class="lead">' + ic(typeIcon(p.type)) + '</span>' +
        '<div><div class="main-t ' + (p.type !== 'person' ? 'mono' : '') + '">' + esc(p.value) +
        (p.masked ? ' <span class="mask-b">' + ic('i-lock') + esc(p.masked) + '</span>' : '') + '</div>' +
        '<div class="sub-t">' + (p.age ? 'age ' + esc(p.age) + ' · ' : '') + (p.evidence_type ? 'evidence: ' + esc(p.evidence_type) : '') +
        (p.note ? ' · ' + esc(p.note) : '') + '</div></div>' +
        '<div class="end"><span class="rolechip ' + esc(p.role) + '">' + esc(p.role) + '</span></div></div>';
    }).join('');

    var linked = (c.linked_cases || []).map(function (l) {
      return '<a class="lcase" data-case="' + esc(l.incident_id) + '"><div class="l1">' +
        '<span class="fr2">' + esc(l.fir_no || l.incident_id) + '</span>' +
        '<span class="badge b-info">' + esc(l.crime_type) + '</span>' +
        '<span class="mono faint" style="font-size:10.5px">' + esc(l.district_code) + ' · ' + d10(l.occurred_at) + '</span>' +
        '<span class="spacer"></span><span class="mono faint" style="font-size:10px">link ' + l.strength + '</span></div>' +
        '<div class="l2">' + (l.reasons || []).map(function (r) { return '<span class="reason ' + esc(r.type) + '">' + esc(r.detail) + '</span>'; }).join('') + '</div></a>';
    }).join('');

    el.innerHTML =
      '<div class="page-h"><div><h2 class="mono">' + esc(inc.fir_no || t.id) + '</h2>' +
      '<p>' + esc(inc.address_text || '') + '</p></div><div class="spacer"></div>' +
      '<button class="btn sm" id="cf-ask">' + ic('i-chat') + ' Ask copilot</button></div>' +
      '<div class="card"><div class="card-b" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">' +
      '<span class="badge b-info">' + esc(inc.crime_type || '?') + '</span>' +
      '<span class="badge b-mut">' + esc(inc.district_code || '?') + ' / ' + esc(inc.station_code || '?') + '</span>' +
      '<span class="badge ' + (String(inc.status).indexOf('Under') === 0 ? 'b-warn' : 'b-ok') + '">' + esc(inc.status || 'status ?') + '</span>' +
      (inc.ipc_bns_code ? '<span class="badge b-mut mono">§ ' + esc(inc.ipc_bns_code) + '</span>' : '') +
      (c.protected ? '<span class="mask-b">' + ic('i-lock') + 'IPC-228A/POCSO protected</span>' : '') +
      (c.series_id ? '<span class="badge b-warn mono">series ' + esc(c.series_id) + '</span>' : '') +
      '<span class="spacer"></span><span class="mono faint" style="font-size:11px">occurred ' + d10(inc.occurred_at) + (inc.reported_at ? ' · reported ' + d10(inc.reported_at) : '') + '</span>' +
      '</div></div>' +
      '<div class="grid" style="grid-template-columns:1.1fr 1fr">' +
      '<div class="card"><div class="card-h"><span class="k">Parties</span><h3>People, vehicles &amp; phones on this FIR</h3></div>' +
      '<div class="card-b"><div class="list">' + (parties || '<div class="empty">No parties recorded.</div>') + '</div>' +
      '<div class="guard">' + ic('i-shield') + '<span>Persons are as recorded in the FIR, pending investigation/trial. Victim/witness identity is masked outside the owning jurisdiction; IPC-228A/POCSO identities are masked for all but admin/case-officer.</span></div></div></div>' +
      '<div class="card"><div class="card-h"><span class="k">Linked</span><h3>Connected cases</h3><span class="spacer"></span><span class="badge b-mut">' + (c.linked_cases || []).length + '</span></div>' +
      '<div class="card-b">' + (linked || '<div class="empty">No linked cases found — no shared entities, series membership or near-repeat pattern.</div>') + '</div></div></div>' +
      '<div class="card"><div class="card-h"><span class="k">Narrative</span><h3>Brief facts / MO</h3></div>' +
      '<div class="card-b"><p style="font-size:13px;color:var(--muted);line-height:1.7">' + esc(inc.mo_text || '—') + '</p></div></div>';

    el.querySelectorAll('[data-ent]').forEach(function (r) {
      r.onclick = function () { openObject('entity', r.dataset.ent, r.dataset.lab); };
    });
    el.querySelectorAll('[data-case]').forEach(function (r) {
      r.onclick = function () { openObject('case', r.dataset.case); };
    });
    $('#cf-ask', el).onclick = function () { ask('cases similar to ' + (inc.crime_type || '') + ' in ' + (inc.district_code || '')); };
  }

  // ---------- ENTITY DOSSIER ----------
  async function viewEntity(t, el) {
    el.innerHTML = shimmer(4);
    var d = await jgetx('/entity/' + encodeURIComponent(t.id), 'entity');
    if (d.__err === 403) { el.innerHTML = notice('', 'Access restricted', (d.detail || 'Dossiers are not available to this role.') + ' Current role: ' + ROLE.role + '.'); return; }
    if (d.__err === 404 || d.error) { el.innerHTML = notice('err', 'Entity not found', 'No entity "' + t.id + '" in the canonical store.'); return; }
    t.title = d.value; t.icon = d.type; saveTabs(); renderTabs();
    var s = d.stats || {};

    var apps = (d.appearances || []).map(function (a) {
      return '<tr class="rowlink" data-case="' + esc(a.incident_id) + '"><td class="mono">' + esc(a.fir_no || a.incident_id) + '</td>' +
        '<td><span class="rolechip ' + esc(a.role) + '">' + esc(a.role) + '</span></td>' +
        '<td>' + esc(a.crime_type || '') + '</td><td class="mono">' + esc(a.district_code || '') + '</td>' +
        '<td class="mono">' + d10(a.occurred_at) + '</td><td class="faint" style="font-size:11.5px">' + esc(a.status || '') + '</td></tr>';
    }).join('');

    var maxW = Math.max.apply(null, (d.associates || []).map(function (a) { return a.weight || 1; }).concat([1]));
    var assoc = (d.associates || []).map(function (a) {
      return '<div class="li rowlink" data-ent="' + esc(a.canonical_id) + '" data-lab="' + esc(a.label) + '">' +
        '<span class="lead">' + ic(typeIcon(a.type)) + '</span>' +
        '<div style="flex:1;min-width:0"><div class="main-t ' + (a.type !== 'person' ? 'mono' : '') + '">' + esc(a.label) +
        (a.masked ? ' <span class="mask-b">' + ic('i-lock') + esc(a.masked) + '</span>' : '') + '</div>' +
        '<div class="bar" style="margin-top:6px;max-width:180px"><span style="width:' + (100 * (a.weight || 1) / maxW).toFixed(0) + '%"></span></div></div>' +
        '<div class="end"><span class="mono">' + a.weight + '×</span><div class="faint" style="font-size:10px">' + (a.kinds || []).join(', ') + '</div></div></div>';
    }).join('');

    var maxM = Math.max.apply(null, (d.timeline || []).map(function (m) { return m.count; }).concat([1]));
    var bars = (d.timeline || []).map(function (m) {
      return '<div style="height:' + Math.max(8, 100 * m.count / maxM) + '%" title="' + esc(m.month) + ': ' + m.count + '"></div>';
    }).join('');

    el.innerHTML =
      '<div class="card"><div class="doss-head">' +
      '<span class="sig">' + ic(typeIcon(d.type)) + '</span>' +
      '<div style="flex:1;min-width:0"><h2>' + esc(d.value) +
      (d.masked ? ' <span class="mask-b">' + ic('i-lock') + 'masked · ' + esc(d.masked) + '</span>' : '') + '</h2>' +
      '<div class="sub2">' + esc(d.type) + ' · ' + esc(d.canonical_id) +
      ((d.aliases || []).length ? ' · aka ' + d.aliases.map(function (a) { return '<span class="alias">' + esc(a.value) + '</span>'; }).join(' ') : '') + '</div></div>' +
      '<div style="display:flex;gap:8px"><button class="btn sm" id="do-net">' + ic('i-net') + ' Ego network</button>' +
      '<button class="btn sm" id="do-ask">' + ic('i-chat') + ' Ask copilot</button></div></div>' +
      '<div class="kstrip">' +
      '<div><div class="kt">Incidents</div><div class="kv">' + fmt(s.incidents) + '</div></div>' +
      '<div><div class="kt">Districts</div><div class="kv">' + (s.districts || []).length + '</div></div>' +
      '<div><div class="kt">First seen</div><div class="kv" style="font-size:14px">' + esc(s.first_seen || '–') + '</div></div>' +
      '<div><div class="kt">Last seen</div><div class="kv" style="font-size:14px">' + esc(s.last_seen || '–') + '</div></div>' +
      '<div><div class="kt">Reach</div><div class="kv" style="font-size:14px">' + esc((s.districts || []).join(' ') || '–') + '</div></div>' +
      '</div></div>' +
      '<div class="grid" style="grid-template-columns:1.4fr 1fr">' +
      '<div class="card"><div class="card-h"><span class="k">Record</span><h3>Appearances across FIRs</h3></div>' +
      '<div class="card-b" style="max-height:420px;overflow:auto"><table><thead><tr><th>FIR</th><th>Role</th><th>Crime</th><th>District</th><th>Date</th><th>Status</th></tr></thead><tbody>' +
      (apps || '') + '</tbody></table>' + (apps ? '' : '<div class="empty">No recorded appearances.</div>') + '</div></div>' +
      '<div class="card"><div class="card-h"><span class="k">Network</span><h3>Known associates</h3><span class="spacer"></span><span class="badge b-mut">co-occurrence</span></div>' +
      '<div class="card-b"><div class="list">' + (assoc || '<div class="empty">No co-occurring entities.</div>') + '</div></div></div></div>' +
      '<div class="grid" style="grid-template-columns:1.4fr 1fr">' +
      '<div class="card"><div class="card-h"><span class="k">Temporal</span><h3>Activity timeline</h3></div>' +
      '<div class="card-b"><div class="tl-bars">' + bars + '</div>' +
      '<div class="tl-lbl"><span>' + esc(((d.timeline || [])[0] || {}).month || '') + '</span><span>' + esc(((d.timeline || []).slice(-1)[0] || {}).month || '') + '</span></div></div></div>' +
      '<div class="card"><div class="card-h"><span class="k">Assessment</span><h3>Activity indicators</h3></div>' +
      '<div class="card-b"><div class="meta" style="display:grid;grid-template-columns:auto 1fr;gap:7px 14px;font-size:12.5px">' +
      '<b class="mono muted">recorded incidents</b><span class="mono">' + fmt((d.indicators || {}).incident_count) + '</span>' +
      '<b class="mono muted">district span</b><span class="mono">' + fmt((d.indicators || {}).district_span) + '</span>' +
      '<b class="mono muted">peak month</b><span class="mono">' + fmt((d.indicators || {}).active_month_max) + ' incidents</span>' +
      '<b class="mono muted">role mix</b><span class="mono" style="font-size:11px">' + esc(Object.keys(s.roles || {}).map(function (k) { return k + ':' + s.roles[k]; }).join(' ')) + '</span></div>' +
      '<div class="guard">' + ic('i-shield') + '<span>' + esc(d.guardrail || '') + '</span></div></div></div></div>';

    el.querySelectorAll('[data-case]').forEach(function (r) { r.onclick = function () { openObject('case', r.dataset.case); }; });
    el.querySelectorAll('[data-ent]').forEach(function (r) { r.onclick = function () { openObject('entity', r.dataset.ent, r.dataset.lab); }; });
    $('#do-net', el).onclick = function () { openNetworkFor(d.canonical_id); };
    $('#do-ask', el).onclick = function () { ask('incidents involving ' + d.value); };
  }

  // ---------- universal search (typeahead) ----------
  var SBOX = $('#globalq'), SDROP = $('#searchdrop'), SDEB = null, SSEL = -1, SITEMS = [];
  function closeSearch() { SDROP.classList.remove('open'); SSEL = -1; SITEMS = []; }
  function searchRow(icon, t1, t2, end, open) {
    return { icon: icon, t1: t1, t2: t2, end: end, open: open };
  }
  async function runSearch(q) {
    var res = await jgetx('/search?q=' + encodeURIComponent(q), 'search');
    if (res.__err) res = MOCK.search;
    SITEMS = [];
    var g = res.groups || {};
    (g.cases || []).forEach(function (c) {
      SITEMS.push(searchRow('i-doc', c.fir_no || c.incident_id, c.crime_type + ' · ' + c.district_code + ' · ' + d10(c.occurred_at), c.status || '', function () { openObject('case', c.incident_id, c.fir_no); }));
    });
    (g.people || []).forEach(function (p) { SITEMS.push(entRow(p)); });
    (g.vehicles || []).forEach(function (p) { SITEMS.push(entRow(p)); });
    (g.phones || []).forEach(function (p) { SITEMS.push(entRow(p)); });
    (g.places || []).forEach(function (p) {
      SITEMS.push(searchRow('i-pin', p.code, fmt(p.incidents) + ' incidents', 'district', function () { go('map'); }));
    });
    (res.semantic || []).forEach(function (c) {
      SITEMS.push(searchRow('i-search', c.fir_no || c.incident_id, (c.snippet || '').slice(0, 70) + '…', 'narrative', function () { openObject('case', c.incident_id, c.fir_no); }));
    });
    var groupsHtml = '';
    function grp(label, items) { if (items.length) groupsHtml += '<div class="sg">' + label + '</div>' + items.join(''); }
    var idx = -1;
    function rowHtml(r) { idx++; return '<div class="sr" data-i="' + idx + '"><span class="ic2">' + ic(r.icon) + '</span><div><div class="t1">' + esc(r.t1) + '</div><div class="t2">' + esc(r.t2) + '</div></div><span class="end2">' + esc(r.end) + '</span></div>'; }
    var i0 = 0;
    grp('Cases', (g.cases || []).map(function (c, i) { return rowHtml(SITEMS[i0 + i]); })); i0 += (g.cases || []).length;
    grp('People', (g.people || []).map(function (c, i) { return rowHtml(SITEMS[i0 + i]); })); i0 += (g.people || []).length;
    grp('Vehicles', (g.vehicles || []).map(function (c, i) { return rowHtml(SITEMS[i0 + i]); })); i0 += (g.vehicles || []).length;
    grp('Phones', (g.phones || []).map(function (c, i) { return rowHtml(SITEMS[i0 + i]); })); i0 += (g.phones || []).length;
    grp('Places', (g.places || []).map(function (c, i) { return rowHtml(SITEMS[i0 + i]); })); i0 += (g.places || []).length;
    grp('Narrative matches', (res.semantic || []).map(function (c, i) { return rowHtml(SITEMS[i0 + i]); }));
    if (!SITEMS.length) groupsHtml = '<div class="empty" style="padding:20px">' + esc(res.note || 'No matches — press Enter to ask the copilot instead.') + '</div>';
    SDROP.innerHTML = groupsHtml + '<div class="sfoot"><span>' + (res.took_ms != null ? res.took_ms + 'ms' : '') + '</span><span>↑↓ navigate · Enter open · Esc close</span><span style="margin-left:auto">Enter with no selection → copilot</span></div>';
    SDROP.classList.add('open'); SSEL = -1;
    SDROP.querySelectorAll('.sr').forEach(function (el) {
      el.onclick = function () { SITEMS[+el.dataset.i].open(); closeSearch(); SBOX.value = ''; };
    });
  }
  function entRow(p) {
    var sub = fmt(p.incidents) + ' incidents · ' + (p.districts || []).join(' ');
    var t1 = p.value + (p.masked ? '  [masked: ' + p.masked + ']' : '');
    return searchRow(typeIcon(p.type), t1, sub, p.type, function () { openObject('entity', p.canonical_id, p.value, p.type); });
  }
  SBOX.addEventListener('input', function () {
    clearTimeout(SDEB);
    var q = SBOX.value.trim();
    if (q.length < 2) { closeSearch(); return; }
    SDEB = setTimeout(function () { runSearch(q); }, 220);
  });
  SBOX.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeSearch(); SBOX.blur(); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!SITEMS.length) return;
      e.preventDefault();
      SSEL = e.key === 'ArrowDown' ? Math.min(SITEMS.length - 1, SSEL + 1) : Math.max(0, SSEL - 1);
      SDROP.querySelectorAll('.sr').forEach(function (el) { el.classList.toggle('sel', +el.dataset.i === SSEL); });
      var sel = SDROP.querySelector('.sr.sel'); if (sel) sel.scrollIntoView({ block: 'nearest' });
      return;
    }
    if (e.key === 'Enter') {
      if (SSEL >= 0 && SITEMS[SSEL]) { SITEMS[SSEL].open(); closeSearch(); SBOX.value = ''; }
      else if (SBOX.value.trim()) { var q = SBOX.value.trim(); closeSearch(); SBOX.value = ''; ask(q); }
    }
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('.searchwrap')) closeSearch(); });
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); SBOX.focus(); SBOX.select(); }
  });

  // ---------- role switcher (live governance demo) ----------
  var RSEL = $('#roleswitch');
  RSEL.value = ROLE.role + '|' + (ROLE.scope || '');
  if (!RSEL.value) RSEL.value = 'scrb-admin|';
  function roleLabel() {
    var names = { 'scrb-admin': 'SCRB · Admin', analyst: 'SCRB · Analyst', district: 'District · ' + ROLE.scope, station: 'Station · ' + ROLE.scope, ethics: 'Ethics · Oversight' };
    $('#rolelabel').textContent = names[ROLE.role] || ROLE.role;
    $('.avatar').textContent = ROLE.role === 'scrb-admin' ? 'SR' : ROLE.role.slice(0, 2).toUpperCase();
  }
  RSEL.onchange = function () {
    var p = RSEL.value.split('|');
    ROLE = { role: p[0], scope: p[1] || '' };
    try { sessionStorage.setItem('garuda.role', JSON.stringify(ROLE)); } catch (e) { }
    roleLabel();
    RENDERED = {};                       // masked payloads are stale — refetch on view
    if (ACTIVE.kind === 'object') {
      var t = TABS.find(function (x) { return x.type === ACTIVE.type && x.id === ACTIVE.id; });
      if (t) { RENDERED[tabKey(t)] = true; (t.type === 'case' ? viewCase : viewEntity)(t, objSection(t)); }
    }
  };
  roleLabel();

  // ---------- clock ----------
  function tick() {
    var now = new Date();
    var ist = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(now);
    $('#clock').innerHTML = '<b>' + ist + '</b> IST';
  }
  setInterval(tick, 1000); tick();

  // ---------- OVERVIEW ----------
  async function viewOverview() {
    var v = $('#view-overview');
    v.innerHTML =
      '<div class="page-h"><div><h2>Operations Overview</h2><p>Karnataka SCRB · every tile drills into a case, an entity or the graph.</p></div><div class="spacer"></div>' +
      '<button class="btn primary" id="ov-reveal">' + ic('i-net') + ' Open network reveal</button></div>' +
      '<div class="kpis" id="kpis">' + shimmer(1) + '</div>' +
      '<div class="grid" style="grid-template-columns:1.3fr 1fr">' +
      '<div class="card"><div class="card-h"><span class="k">Organized</span><h3>Cross-district rings</h3>' +
      '<span class="spacer"></span><span class="badge b-mut">click → kingpin dossier</span></div><div class="card-b" id="ov-rings">' + shimmer(3) + '</div></div>' +
      '<div class="card"><div class="card-h"><span class="k">Signals</span><h3>Emerging-trend alerts</h3></div><div class="card-b" id="ov-alerts">' + shimmer(3) + '</div></div>' +
      '</div>' +
      '<div class="card"><div class="card-h"><span class="k">Distribution</span><h3>Incidents by crime type</h3></div><div class="card-b" id="ov-crime">' + shimmer(2) + '</div></div>';
    $('#ov-reveal').onclick = function () { go('network'); };

    var stats = await jget('/stats', 'stats');
    var rings = await jget('/network/rings?top=6', 'rings');
    var an = await jpost('/anomaly/run', { write: false }, 'anomaly');

    var alerts = (an && an.sample) || [];
    $('#kpis').innerHTML = [
      kpi('Incidents', fmt(stats.incidents), 'tracked FIRs', 'i-act', ''),
      kpi('Entities', fmt(stats.entities), 'persons / phones / vehicles', 'i-users', ''),
      kpi('Cross-district rings', fmt((rings.rings || []).length), 'organized networks', 'i-net', 'accent'),
      kpi('Active alerts', fmt(alerts.length), 'emerging-trend spikes', 'i-siren', 'danger')
    ].join('');

    var rs = (rings.rings || []);
    $('#ov-rings').innerHTML = rs.length ? '<div class="list stagger">' + rs.map(function (r, i) {
      return '<div class="li rowlink" data-king="' + esc(r.kingpin_id) + '" data-lab="' + esc(r.kingpin_label) + '">' +
        '<span class="lead" style="background:rgba(249,168,37,.13);border-color:rgba(249,168,37,.3)">' + ic('i-target') + '</span>' +
        '<div><div class="main-t">' + esc(r.kingpin_label) + ' <span class="faint mono">· ring #' + (i + 1) + '</span></div>' +
        '<div class="sub-t">' + r.persons + ' members · ' + (r.shared_links || []).map(esc).join(', ') + '</div></div>' +
        '<div class="end"><span class="badge b-danger">' + r.district_count + ' districts</span><div class="faint" style="margin-top:5px">' + esc((r.districts || []).join(' ')) + '</div></div></div>';
    }).join('') + '</div>' : '<div class="empty">No rings.</div>';
    $('#ov-rings').querySelectorAll('[data-king]').forEach(function (el) {
      el.onclick = function () { openObject('entity', el.dataset.king, el.dataset.lab, 'person'); };
    });

    $('#ov-alerts').innerHTML = alerts.length ? '<div class="list stagger">' + alerts.slice(0, 5).map(function (a) {
      return '<div class="li"><span class="dot ' + (a.severity === 'high' ? 'danger' : 'warn') + '"></span>' +
        '<div><div class="main-t">' + esc(a.crime_type) + ' · ' + esc(a.district_code) + '</div>' +
        '<div class="sub-t">' + esc(a.window_start) + ' · baseline ×' + (a.ratio || '?') + '</div></div>' +
        '<div class="end"><span class="badge ' + (a.severity === 'high' ? 'b-danger' : 'b-warn') + '">z ' + (a.z_score || '?') + '</span></div></div>';
    }).join('') + '</div>' : '<div class="empty">No alerts.</div>';

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
  function openNetworkFor(cid) {
    NET.pending = cid;
    if (loaded.network) loadEgo(cid);
    go('network');
  }
  async function viewNetwork() {
    var v = $('#view-network');
    v.innerHTML = '<div class="page-h"><div><h2>Co-offender Network Reveal</h2>' +
      '<p>Siloed FIRs → one visible gang. Node size = involvement, colour = community, ' +
      '<span style="color:var(--accent)">amber ring = kingpin</span>. First load computes centrality (~1 min live).</p></div><div class="spacer"></div>' +
      '<div id="ring-chips" style="display:flex;gap:8px;flex-wrap:wrap"></div></div>' +
      '<div class="stage"><canvas id="net-canvas"></canvas>' +
      '<div class="legend" id="net-legend"></div><div id="net-detail"></div></div>';
    var rings = await jget('/network/rings?top=6', 'rings');
    var rs = rings.rings || [];
    $('#nav-rings').textContent = rs.length;
    $('#ring-chips').innerHTML = rs.map(function (r) {
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
      '<button class="btn sm" style="margin-top:14px;width:100%" onclick="GARUDA_APP.openEntity(\'' + esc(n.id) + '\',\'' + esc(n.label || n.id) + '\')">' + ic('i-user') + ' Open dossier</button>' +
      '<button class="btn sm" style="margin-top:8px;width:100%" onclick="GARUDA_APP.ask(\'incidents involving ' + esc(n.label) + '\')">' + ic('i-chat') + ' Ask copilot</button></div>';
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
          '<button class="btn sm" style="margin-top:14px;width:100%" onclick="GARUDA_APP.ask(\'crime in ' + esc(d.code) + '\')">' + ic('i-chat') + ' Ask copilot about ' + esc(d.code) + '</button>';
      };
    });
  }

  // ---------- COPILOT ----------
  var CHAT = [];
  async function viewCopilot() {
    var v = $('#view-copilot');
    v.innerHTML = '<div class="page-h"><div><h2>Intelligence Copilot</h2><p>Plain-English questions over the FIR corpus — ' +
      'every answer is grounded in cited records. Citations open the case file.</p></div></div>' +
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
        return '<a class="cite" data-case="' + esc(c.incident_id) + '" data-fir="' + esc(c.fir_no || '') + '"><div class="fr">' + ic('i-doc') + ' ' + esc(c.fir_no || c.incident_id) + '</div>' +
          '<div class="mt"><span class="badge b-info">' + esc(c.crime_type) + '</span><span class="mono faint">' + esc(c.district_code) + ' · ' + d10(c.occurred_at) + '</span></div>' +
          '<div class="sn">' + esc(c.snippet || '') + '</div></a>';
      }).join('') + '</div>';
      if (r.guardrail) body += '<div class="gr">' + ic('i-shield') + '<span>' + esc(r.guardrail) + '</span></div>';
      body += '</div>';
      return '<div class="msg bot"><div class="who">AI</div>' + body + '</div>';
    }).join('');
    t.querySelectorAll('[data-case]').forEach(function (el) {
      el.onclick = function () { openObject('case', el.dataset.case, el.dataset.fir || undefined); };
    });
    t.scrollTop = t.scrollHeight;
  }
  function push(role, payload) { CHAT.push(role === 'user' ? { role: 'user', text: payload } : { role: 'bot', res: payload }); renderThread(); }
  async function ask(q) {
    q = (q || '').trim(); if (!q) return;
    go('copilot');
    setTimeout(async function () {
      var box = $('#cin'); if (box) box.value = '';
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
    }).join('') + '</div><p class="faint" style="margin-top:12px;font-size:11.5px">Wards predicted > 1.3× their actual rate are flagged for review (over-policing guard). Forecasts target places &amp; times, never individuals.</p>';
  }

  // ---------- MOCK fixtures (planted scenario; offline preview) ----------
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
    copilot: { answer: 'Found matching FIR records. Top results are cited below — these surface records, not determinations of guilt.', citations: [{ fir_no: 'BNU20/2024/0028', incident_id: 'INC010001', crime_type: 'Chain snatching', district_code: 'BNU', occurred_at: '2024-01-24', snippet: 'Gold chain snatched near MG Road; accused fled on a two-wheeler bearing KA68MC3164.' }, { fir_no: 'RMN03/2024/0011', incident_id: 'INC010003', crime_type: 'Chain snatching', district_code: 'RMN', occurred_at: '2024-03-08', snippet: 'Two miscreants snatched a chain and sped away; call record links +916534933629.' }], guardrail: 'This system surfaces FIR records matching the query; it does not determine guilt.' },
    copilotRefuse: { refused: true, reason: 'guilt_determination', answer: 'This system surfaces FIR records matching the query; it does not determine guilt. Persons named are as recorded in the FIR, pending investigation/trial.', citations: [], guardrail: 'Surfaces records, never asserts guilt.' },
    search: {
      query: '', took_ms: 3, groups: {
        cases: [{ incident_id: 'INC010001', fir_no: 'BNU20/2024/0028', crime_type: 'Chain snatching', district_code: 'BNU', occurred_at: '2024-01-24', status: 'Under Investigation' }],
        people: [{ canonical_id: 'ENT014602', value: 'Aayush Zachariah', type: 'person', incidents: 9, districts: ['BNU', 'KLR', 'RMN', 'TMK'] }],
        vehicles: [{ canonical_id: 'ENT014608', value: 'KA68MC3164', type: 'vehicle', incidents: 10, districts: ['BNU', 'KLR', 'RMN', 'TMK'] }],
        phones: [{ canonical_id: 'ENT014607', value: '+916534933629', type: 'phone', incidents: 10, districts: ['BNU', 'KLR', 'RMN', 'TMK'] }],
        places: []
      }, semantic: []
    },
    entity: {
      canonical_id: 'ENT014602', type: 'person', value: 'Aayush Zachariah', masked: null, aliases: [],
      stats: { incidents: 9, districts: ['BNU', 'KLR', 'RMN', 'TMK'], first_seen: '2024-01-24', last_seen: '2024-11-02', roles: { suspect: 9 } },
      appearances: [{ incident_id: 'INC010001', fir_no: 'BNU20/2024/0028', role: 'suspect', crime_type: 'Chain snatching', district_code: 'BNU', occurred_at: '2024-01-24', status: 'Under Investigation' }, { incident_id: 'INC010003', fir_no: 'RMN03/2024/0011', role: 'suspect', crime_type: 'Chain snatching', district_code: 'RMN', occurred_at: '2024-03-08', status: 'Under Investigation' }],
      associates: [{ canonical_id: 'ENT014607', label: '+916534933629', type: 'phone', weight: 9, kinds: ['shared_phone'] }, { canonical_id: 'ENT014608', label: 'KA68MC3164', type: 'vehicle', weight: 9, kinds: ['shared_vehicle'] }, { canonical_id: 'ENT014604', label: 'Urvi Amble', type: 'person', weight: 5, kinds: ['co_offence'] }],
      timeline: [{ month: '2024-01', count: 1 }, { month: '2024-03', count: 2 }, { month: '2024-06', count: 3 }, { month: '2024-09', count: 2 }, { month: '2024-11', count: 1 }],
      indicators: { incident_count: 9, district_span: 4, active_month_max: 3, recent_month_incidents: 1 },
      guardrail: 'Activity indicators describe recorded involvement only; no determination of guilt is made or implied.',
      viewer: { role: 'demo', scope: null }
    },
    case: {
      incident: { incident_id: 'INC010002', fir_no: 'RMN03/2024/0007', occurred_at: '2024-02-12 21:40:00', reported_at: '2024-02-13 09:15:00', district_code: 'RMN', station_code: 'RMN03', crime_type: 'Chain snatching', ipc_bns_code: '304(2)', address_text: 'Old Market Road, Ramanagara', mo_text: 'Two miscreants on a motorcycle snatched a gold chain and sped away. CCTV places vehicle KA68MC3164 at the scene; call records link +916534933629.', status: 'Under Investigation' },
      protected: false, series_id: null,
      parties: [{ role: 'suspect', entity_id: 'ENT014602', canonical_id: 'ENT014602', type: 'person', value: 'Aayush Zachariah', age: '29', evidence_type: 'cctv', note: 'as recorded in the FIR; pending investigation/trial' }, { role: 'victim', entity_id: 'ENTV', canonical_id: 'ENTV', type: 'person', value: 'M. R.', masked: 'jurisdiction', evidence_type: 'fir_named' }, { role: 'vehicle_used', entity_id: 'ENT014608', canonical_id: 'ENT014608', type: 'vehicle', value: 'KA68MC3164', evidence_type: 'cctv' }, { role: 'phone_used', entity_id: 'ENT014607', canonical_id: 'ENT014607', type: 'phone', value: '+916534933629', evidence_type: 'call_record' }],
      linked_cases: [{ incident_id: 'INC010001', fir_no: 'BNU20/2024/0028', crime_type: 'Chain snatching', district_code: 'BNU', occurred_at: '2024-01-24', strength: 11, reasons: [{ type: 'shared_vehicle', detail: 'vehicle: KA68MC3164' }, { type: 'shared_phone', detail: 'phone: +916534933629' }, { type: 'shared_person', detail: 'person: Aayush Zachariah' }] }],
      timeline: [{ ts: '2024-02-12 21:40:00', label: 'Incident occurred' }, { ts: '2024-02-13 09:15:00', label: 'FIR registered' }],
      viewer: { role: 'demo', scope: null }
    }
  };

  // ---------- boot ----------
  window.GARUDA_APP = {
    go: go, ask: ask, openEntity: function (id, lab) { openObject('entity', id, lab); },
    openCase: function (id, lab) { openObject('case', id, lab); }
  };
  renderTabs();
  route();
})();
