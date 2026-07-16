'use strict';

/**
 * GARUDA — Job function (Track A, plan §4.8).
 *
 * Target for Catalyst **Job Scheduling** crons (console: two schedules —
 * nightly 02:00 IST and weekly Mon 08:00 IST, both pointing at this function
 * with a `kind` job param of "nightly" / "weekly"). Deliberately thin: the
 * ordering/error-capture orchestration lives Python-side in
 * app/automation/jobs.py behind AppSail's POST /jobs/nightly | /jobs/weekly,
 * so this function makes exactly ONE call and reports the per-task result.
 *
 * env_variables (catalyst-config.json):
 *   APPSAIL_BASE_URL   AppSail brain base URL
 *   GARUDA_JOBS_TOKEN  optional shared secret; must match the AppSail env of
 *                      the same name (sent as X-Jobs-Token)
 */
const http = require('http');
const https = require('https');
const { URL } = require('url');

/** Job params are not byte-stable across Catalyst versions — probe the likely
 * shapes (same defensive pattern as ingest-event's parseEvent). */
function jobKind(jobRequest) {
	let params = {};
	try {
		if (jobRequest && typeof jobRequest.getAllJobParams === 'function') {
			params = jobRequest.getAllJobParams() || {};
		} else if (jobRequest && jobRequest.params) {
			params = jobRequest.params;
		} else if (jobRequest && jobRequest.job_meta && jobRequest.job_meta.params) {
			params = jobRequest.job_meta.params;
		}
	} catch (e) { /* fall through to default */ }
	const kind = String(params.kind || params.KIND || 'nightly').toLowerCase();
	return kind === 'weekly' ? 'weekly' : 'nightly';
}

function postJson(baseUrl, route, headers, timeoutMs) {
	return new Promise((resolve, reject) => {
		let u;
		try { u = new URL(route, baseUrl); } catch (e) { return reject(e); }
		const lib = u.protocol === 'http:' ? http : https;
		const req = lib.request(u, {
			method: 'POST',
			headers: Object.assign({ 'Content-Length': 0 }, headers),
			timeout: timeoutMs
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
		req.on('timeout', () => req.destroy(new Error('AppSail ' + route + ' timed out')));
		req.on('error', reject);
		req.end();
	});
}

module.exports = async (jobRequest, context) => {
	const kind = jobKind(jobRequest);
	try {
		const base = process.env.APPSAIL_BASE_URL;
		if (!base) throw new Error('APPSAIL_BASE_URL env var not set');
		const headers = {};
		if (process.env.GARUDA_JOBS_TOKEN) headers['X-Jobs-Token'] = process.env.GARUDA_JOBS_TOKEN;

		// Nightly retrains LightGBM + rebuilds the graph — allow a long window.
		const out = await postJson(base, '/jobs/' + kind, headers, 9 * 60 * 1000);

		const report = out.report || {};
		const failed = Object.keys(report)
			.filter((k) => k[0] !== '_' && report[k] && report[k].ok === false);
		console.log('GARUDA job', kind, 'ok=', out.ok,
			'duration_s=', report._duration_s, 'failed=', failed.join(',') || 'none');
		if (out.ok) context.closeWithSuccess();
		else context.closeWithFailure();
	} catch (err) {
		console.error('GARUDA job', kind, 'failed:', err && err.message);
		context.closeWithFailure();
	}
};
