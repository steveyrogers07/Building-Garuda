'use strict';

/**
 * GARUDA — Advanced I/O REST function (Track A).
 *
 * Phase 1: a hello-world health probe that proves the Functions compute
 * surface deploys and is reachable on the Catalyst Dev URL.
 *
 * Later phases turn this into the thin REST layer for the frontend
 * (auth-gated Data Store reads via ZCQL), proxying heavy ML to the
 * Python brain on AppSail. Keep it thin.
 *
 * Advanced I/O hands the function the raw Node HTTP request/response.
 *
 * @param {import('http').IncomingMessage} req
 * @param {import('http').ServerResponse} res
 */
module.exports = (req, res) => {
	// Normalise: strip query string and any trailing slash.
	const path = (req.url || '/').split('?')[0].replace(/\/+$/, '') || '/';

	if (path === '/' || path === '/health') {
		const body = {
			status: 'ok',
			service: 'garuda-api',
			surface: 'functions/advanced-io',
			phase: 1,
			time: new Date().toISOString()
		};
		res.writeHead(200, { 'Content-Type': 'application/json' });
		res.end(JSON.stringify(body));
		return;
	}

	res.writeHead(404, { 'Content-Type': 'application/json' });
	res.end(JSON.stringify({ status: 'not_found', path }));
};
