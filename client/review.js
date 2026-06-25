// GARUDA review UI (Phase 3) — list pending FIR extractions, approve/reject.
// Talks to the Advanced I/O api function: GET /review/pending, POST /review/approve|reject.
// Auth-gated (Catalyst Web SDK); low-confidence fields (< 0.80) are highlighted.
(function () {
	'use strict';

	var LOW = 0.80;
	var apiBase = (window.GARUDA_CONFIG && window.GARUDA_CONFIG.apiBaseUrl) || '/server/api';
	var reviewer = 'reviewer';

	var statusEl = document.getElementById('status');
	var queueEl = document.getElementById('queue');

	var FIELDS = ['fir_no', 'occurred_at', 'reported_at', 'district_code', 'station_code',
		'crime_type', 'ipc_bns_code', 'lat', 'long', 'address_text', 'mo_text', 'status'];

	function setStatus(msg, kind) {
		statusEl.textContent = msg || '';
		statusEl.className = 'note ' + (kind || '');
	}

	function api(method, route, body) {
		return fetch(apiBase + route, {
			method: method,
			headers: { 'Content-Type': 'application/json' },
			body: body ? JSON.stringify(body) : undefined
		}).then(function (r) {
			if (!r.ok) return r.text().then(function (t) { throw new Error(t || ('HTTP ' + r.status)); });
			return r.json();
		});
	}

	function esc(s) {
		return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
			return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
		});
	}

	function confBadge(v) {
		if (v == null || v === '') return '';
		var n = Number(v);
		return '<span class="badge ' + (n >= LOW ? 'ok' : 'warn') + '">' + n.toFixed(2) + '</span>';
	}

	function listVals(arr) {
		if (!arr || !arr.length) return '<span class="muted">&mdash;</span>';
		return arr.map(function (x) {
			if (x && typeof x === 'object') return esc(x.value + (x.role ? ' (' + x.role + ')' : ''));
			return esc(x);
		}).join(', ');
	}

	function card(row) {
		var ex = {}, cf = {};
		try { ex = JSON.parse(row.extracted_json || '{}'); } catch (e) { /* ignore */ }
		try { cf = JSON.parse(row.field_confidences || '{}'); } catch (e) { /* ignore */ }
		var overall = cf._overall;
		var flagged = overall != null && Number(overall) < LOW;

		var fieldRows = FIELDS.map(function (f) {
			if (ex[f] == null || ex[f] === '') return '';
			var lc = cf[f] != null && Number(cf[f]) < LOW;
			return '<tr class="' + (lc ? 'low' : '') + '"><td class="k">' + f + '</td>' +
				'<td class="v">' + esc(ex[f]) + '</td><td class="c">' + confBadge(cf[f]) + '</td></tr>';
		}).join('');

		var el = document.createElement('section');
		el.className = 'card review' + (flagged ? ' flagged' : '');
		el.innerHTML =
			'<div class="rhead"><div><strong>' + esc(row.review_id) + '</strong> ' +
			(flagged ? '<span class="badge warn">needs attention</span>' : '<span class="badge ok">ok</span>') +
			'<div class="muted small">' + esc(row.source_fir_url || '') + ' &middot; ' + esc(row.created_at || '') + '</div></div>' +
			'<div>overall ' + confBadge(overall) + '</div></div>' +
			'<table class="fields"><tbody>' + fieldRows + '</tbody></table>' +
			'<div class="lists">' +
			'<div><span class="muted">Persons:</span> ' + listVals(ex.persons) + '</div>' +
			'<div><span class="muted">Vehicles:</span> ' + listVals(ex.vehicles) + '</div>' +
			'<div><span class="muted">Phones:</span> ' + listVals(ex.phones) + '</div>' +
			'</div>' +
			'<div class="ractions"><button class="btn approve">Approve &rarr; canonical</button>' +
			'<button class="btn ghost reject">Reject</button></div>';

		el.querySelector('.approve').addEventListener('click', function () { decide(el, row.review_id, 'approve'); });
		el.querySelector('.reject').addEventListener('click', function () { decide(el, row.review_id, 'reject'); });
		return el;
	}

	function decide(el, id, action) {
		var btns = el.querySelectorAll('button');
		btns.forEach(function (b) { b.disabled = true; });
		setStatus(action + ' ' + id + '…');
		api('POST', '/review/' + action, { review_id: id, reviewer: reviewer }).then(function (res) {
			if (res.ok === false) throw new Error(res.error || 'failed');
			el.classList.add('done');
			el.querySelector('.ractions').innerHTML = '<span class="ok">' + action + 'd' +
				(res.incident_id ? ' &rarr; ' + esc(res.incident_id) : '') + '</span>';
			setStatus(action + 'd ' + id, 'ok');
		}).catch(function (e) {
			btns.forEach(function (b) { b.disabled = false; });
			setStatus('Error: ' + e.message, 'warn');
		});
	}

	function load() {
		setStatus('Loading…');
		queueEl.innerHTML = '';
		api('GET', '/review/pending').then(function (res) {
			var rows = (res && res.rows) || [];
			if (!rows.length) { setStatus('Queue empty — nothing pending.', 'ok'); return; }
			rows.forEach(function (r) { queueEl.appendChild(card(r)); });
			setStatus(rows.length + ' pending', '');
		}).catch(function (e) {
			setStatus('Could not load queue: ' + e.message + ' (set apiBaseUrl in config.js)', 'warn');
		});
	}

	(async function () {
		var user = await GARUDA.requireAuth('login.html');
		if (!user) return;
		reviewer = user.email_id || user.email || (user.user_details && user.user_details.email_id) || 'reviewer';
		document.getElementById('refresh').addEventListener('click', load);
		document.getElementById('signout').addEventListener('click', function () { GARUDA.signOut('index.html'); });
		load();
	})();
})();
