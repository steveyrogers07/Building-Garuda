'use strict';

/**
 * GARUDA — review (human-in-the-loop) handlers for the Advanced I/O api function.
 *
 * Reads/writes Review_Queue via ZCQL and, on approval, asks the AppSail brain to
 * map the extracted JSON to canonical rows (POST /promote), then writes them to
 * Incidents / Entities / Incident_Edges. Keeping the canonical mapping in AppSail
 * (Python promote.py) means a single source of truth — Node stays thin.
 *
 * SDK (zcatalyst-sdk-node v3):
 *   app.zcql().executeZCQLQuery(sql)            -> [{ Review_Queue: {...} }, ...]
 *   app.datastore().table(name).insertRows(arr) -> inserted rows
 */
const http = require('http');
const https = require('https');
const { URL } = require('url');

// ZCQL string-literal escape (double single quotes); guards the reviewer field.
function q(v) {
	return String(v == null ? '' : v).replace(/'/g, "''");
}

// Drop empty values so typed (numeric/datetime) columns are left null rather than ''.
function clean(row) {
	const o = {};
	Object.keys(row).forEach((k) => {
		if (row[k] !== '' && row[k] !== null && row[k] !== undefined) o[k] = row[k];
	});
	return o;
}

function postJson(baseUrl, route, payload) {
	return new Promise((resolve, reject) => {
		let u;
		try { u = new URL(route, baseUrl); } catch (e) { return reject(e); }
		const body = Buffer.from(JSON.stringify(payload));
		const lib = u.protocol === 'http:' ? http : https;
		const r = lib.request(u, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', 'Content-Length': body.length }
		}, (resp) => {
			let buf = '';
			resp.on('data', (c) => { buf += c; });
			resp.on('end', () => {
				if (resp.statusCode >= 200 && resp.statusCode < 300) {
					try { resolve(JSON.parse(buf)); } catch (e) { reject(new Error('bad JSON from ' + route)); }
				} else {
					reject(new Error('AppSail ' + route + ' -> ' + resp.statusCode));
				}
			});
		});
		r.on('error', reject);
		r.write(body);
		r.end();
	});
}

async function listPending(app) {
	const sql = 'SELECT Review_Queue.review_id, Review_Queue.source_fir_url, ' +
		'Review_Queue.extracted_json, Review_Queue.field_confidences, ' +
		'Review_Queue.status, Review_Queue.created_at FROM Review_Queue ' +
		"WHERE Review_Queue.status = 'pending' ORDER BY Review_Queue.created_at DESC LIMIT 200";
	const rows = await app.zcql().executeZCQLQuery(sql);
	return rows.map((r) => r.Review_Queue);
}

async function approve(app, body) {
	const id = q(body.review_id);
	const reviewer = q(body.reviewer || 'reviewer');

	const sel = 'SELECT Review_Queue.ROWID, Review_Queue.extracted_json, ' +
		'Review_Queue.field_confidences, Review_Queue.status FROM Review_Queue ' +
		"WHERE Review_Queue.review_id = '" + id + "' LIMIT 1";
	const found = await app.zcql().executeZCQLQuery(sel);
	if (!found.length) return { ok: false, error: 'review_id not found' };
	const rq = found[0].Review_Queue;
	if (rq.status && rq.status !== 'pending') return { ok: false, error: 'already ' + rq.status };

	const extraction = JSON.parse(rq.extracted_json || '{}');
	let overall = null;
	try { overall = JSON.parse(rq.field_confidences || '{}')._overall; } catch (e) { /* ignore */ }

	// AppSail brain maps extraction -> canonical rows (single source of truth).
	const base = process.env.APPSAIL_BASE_URL;
	if (!base) return { ok: false, error: 'APPSAIL_BASE_URL not set' };
	const canon = await postJson(base, '/promote', { extraction: extraction, confidence: overall });

	const ds = app.datastore();
	const counts = {};
	for (const tbl of ['Incidents', 'Entities', 'Incident_Edges']) {
		const arr = (canon[tbl] || []).map(clean);
		if (arr.length) await ds.table(tbl).insertRows(arr);
		counts[tbl] = arr.length;
	}

	const upd = "UPDATE Review_Queue SET status='approved', reviewer='" + reviewer +
		"' WHERE review_id='" + id + "'";
	await app.zcql().executeZCQLQuery(upd);

	const incidentId = (canon.Incidents && canon.Incidents[0] && canon.Incidents[0].incident_id) || null;
	return { ok: true, review_id: body.review_id, incident_id: incidentId, counts: counts };
}

async function reject(app, body) {
	const id = q(body.review_id);
	const reviewer = q(body.reviewer || 'reviewer');
	const upd = "UPDATE Review_Queue SET status='rejected', reviewer='" + reviewer +
		"' WHERE review_id='" + id + "'";
	await app.zcql().executeZCQLQuery(upd);
	return { ok: true, review_id: body.review_id, reason: body.reason || '' };
}

module.exports = { listPending, approve, reject };
