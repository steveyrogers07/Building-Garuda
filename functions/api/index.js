'use strict';

/**
 * GARUDA — Advanced I/O REST function (Track A).
 *
 * Thin REST surface for the frontend. Phase 1 was a health probe; Phase 3 adds the
 * human-in-the-loop review endpoints, backed by Data Store (ZCQL) and the AppSail
 * brain. Heavy logic stays in AppSail/Python — this layer stays thin.
 *
 *   GET  /health           liveness
 *   GET  /review/pending   list Review_Queue rows awaiting a human
 *   POST /review/approve   {review_id, reviewer}          -> promote to canonical
 *   POST /review/reject    {review_id, reviewer, reason}  -> mark rejected
 *
 * env_variables (catalyst-config.json):
 *   APPSAIL_BASE_URL  AppSail brain base URL (used by /review/approve -> /promote)
 *
 * Advanced I/O hands the function the raw Node HTTP request/response.
 *
 * @param {import('http').IncomingMessage} req
 * @param {import('http').ServerResponse} res
 */
const catalyst = require('zcatalyst-sdk-node');
const review = require('./review');

function send(res, code, body) {
	res.writeHead(code, { 'Content-Type': 'application/json' });
	res.end(JSON.stringify(body));
}

function readJson(req) {
	return new Promise((resolve) => {
		let buf = '';
		req.on('data', (c) => { buf += c; });
		req.on('end', () => { try { resolve(buf ? JSON.parse(buf) : {}); } catch (e) { resolve({}); } });
		req.on('error', () => resolve({}));
	});
}

module.exports = async (req, res) => {
	const method = (req.method || 'GET').toUpperCase();
	// Normalise: strip query string and any trailing slash.
	const path = (req.url || '/').split('?')[0].replace(/\/+$/, '') || '/';

	try {
		if (method === 'GET' && (path === '/' || path === '/health')) {
			return send(res, 200, {
				status: 'ok', service: 'garuda-api', surface: 'functions/advanced-io',
				phase: 3, time: new Date().toISOString()
			});
		}

		const app = catalyst.initialize(req);

		if (method === 'GET' && path === '/review/pending') {
			return send(res, 200, { rows: await review.listPending(app) });
		}
		if (method === 'POST' && path === '/review/approve') {
			const body = await readJson(req);
			if (!body.review_id) return send(res, 400, { status: 'bad_request', error: 'review_id required' });
			return send(res, 200, await review.approve(app, body));
		}
		if (method === 'POST' && path === '/review/reject') {
			const body = await readJson(req);
			if (!body.review_id) return send(res, 400, { status: 'bad_request', error: 'review_id required' });
			return send(res, 200, await review.reject(app, body));
		}

		return send(res, 404, { status: 'not_found', path: path, method: method });
	} catch (err) {
		console.error('GARUDA api error:', err && err.message);
		return send(res, 500, { status: 'error', error: (err && err.message) || 'internal' });
	}
};
