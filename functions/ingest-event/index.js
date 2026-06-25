'use strict';

/**
 * GARUDA — FIR ingestion event function (Track A).
 *
 * Trigger: a new FIR scan landing in the Stratus inbox bucket fires this event
 * function (bind the trigger in the console — see docs/PHASE_3_RUNBOOK.md). This is
 * a non-EOL Event Function (the binding is a Stratus trigger / Signal, not the
 * retired Event Listener service).
 *
 * Flow:  Stratus object  ->  Zia OCR  ->  AppSail POST /extract  ->  Review_Queue row
 *
 * The heavy extraction / confidence / promote logic lives in the Python brain
 * (AppSail); this function only wires storage -> OCR -> brain -> Data Store and
 * NEVER auto-promotes to the canonical tables — a human approves in the review UI.
 *
 * env_variables (catalyst-config.json):
 *   APPSAIL_BASE_URL  AppSail brain base URL, e.g.
 *                     https://<appsail>-<id>.development.catalystappsail.com
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const https = require('https');
const { URL } = require('url');
const catalyst = require('zcatalyst-sdk-node');
const { ocrFile } = require('./ocr');

/**
 * The Stratus event payload is not byte-stable across Catalyst versions, so pull
 * bucket + key from the likely fields and log the raw event once (confirm the exact
 * shape on first run — see runbook).
 */
function parseEvent(event) {
	let data = {};
	try {
		data = typeof event.getRawData === 'function' ? event.getRawData() : event;
	} catch (e) {
		data = event || {};
	}
	if (typeof data === 'string') {
		try { data = JSON.parse(data); } catch (e) { /* leave as string */ }
	}
	const d = data && data.data ? data.data : data || {};
	const bucket = d.bucket_name || d.bucket || d.bucketName ||
		(d.bucket_meta && d.bucket_meta.bucket_name);
	const key = d.object_key || d.key || d.key_name || d.object_name ||
		(d.object_meta && d.object_meta.key_name);
	return { bucket, key, raw: data };
}

function postJson(baseUrl, route, payload) {
	return new Promise((resolve, reject) => {
		let u;
		try { u = new URL(route, baseUrl); } catch (e) { return reject(e); }
		const body = Buffer.from(JSON.stringify(payload));
		const lib = u.protocol === 'http:' ? http : https;
		const req = lib.request(u, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', 'Content-Length': body.length }
		}, (res) => {
			let buf = '';
			res.on('data', (c) => { buf += c; });
			res.on('end', () => {
				if (res.statusCode >= 200 && res.statusCode < 300) {
					try { resolve(JSON.parse(buf)); }
					catch (e) { reject(new Error('bad JSON from ' + route + ': ' + buf.slice(0, 200))); }
				} else {
					reject(new Error('AppSail ' + route + ' -> ' + res.statusCode + ': ' + buf.slice(0, 200)));
				}
			});
		});
		req.on('error', reject);
		req.write(body);
		req.end();
	});
}

function streamToFile(readable, dest) {
	return new Promise((resolve, reject) => {
		const out = fs.createWriteStream(dest);
		readable.on('error', reject);
		out.on('error', reject);
		out.on('finish', resolve);
		readable.pipe(out);
	});
}

module.exports = async (event, context) => {
	const app = catalyst.initialize(context);
	try {
		const { bucket, key, raw } = parseEvent(event);
		console.log('GARUDA ingest event:', JSON.stringify(raw).slice(0, 500));
		if (!bucket || !key) throw new Error('could not resolve bucket/key from event payload');

		// 1. Download the scan from Stratus to /tmp (the only writable dir in a function).
		const tmp = path.join(os.tmpdir(), Date.now() + '-' + path.basename(key));
		const obj = await app.stratus().bucket(bucket).getObject(key); // Promise<Readable>
		await streamToFile(obj, tmp);

		// 2. OCR -> text. If the object is already text (.txt), skip Zia.
		let text;
		if (/\.txt$/i.test(key)) {
			text = fs.readFileSync(tmp, 'utf8');
		} else {
			text = await ocrFile(app, tmp);
		}
		if (!text || !text.trim()) throw new Error('OCR produced no text for ' + key);

		// 3. AppSail brain: text -> structured fields + confidence + Review_Queue record.
		const base = process.env.APPSAIL_BASE_URL;
		if (!base) throw new Error('APPSAIL_BASE_URL env var not set');
		const sourceUrl = 'stratus://' + bucket + '/' + key;
		const out = await postJson(base, '/extract', { text: text, source_fir_url: sourceUrl });

		// 4. Persist the Review_Queue row (a human approves later; never auto-promote).
		//    Drop convenience keys (prefixed '_') that are not Data Store columns.
		const review = out.review_record || {};
		const row = {};
		Object.keys(review).forEach((k) => { if (k[0] !== '_') row[k] = review[k]; });
		await app.datastore().table('Review_Queue').insertRow(row);

		console.log('GARUDA queued for review:', row.review_id,
			'overall=', (out.field_confidences || {})._overall);
		context.closeWithSuccess();
	} catch (err) {
		console.error('GARUDA ingest failed:', err && err.message);
		context.closeWithFailure();
	}
};
