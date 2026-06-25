'use strict';

/**
 * GARUDA — OCR wrapper over Catalyst Zia (Track A ingestion).
 *
 * Turns an FIR scan (image) into raw text so the rest of the pipeline
 * (AppSail /extract) only ever sees text. Co-located with the ingest-event
 * function on purpose: Catalyst bundles each function folder on its own, so a
 * require() reaching outside this directory would not deploy.
 *
 * SDK (zcatalyst-sdk-node v3):
 *   app.zia().extractOpticalCharacters(readStream, { language, modelType })
 *     -> Promise<{ text: string, confidence?: string }>
 */
const fs = require('fs');

/**
 * @param {object} app       initialised Catalyst app (catalyst.initialize(context))
 * @param {string} filePath  local path to the downloaded scan (e.g. under /tmp)
 * @param {object} [opts]    { language='eng', modelType }
 * @returns {Promise<string>} extracted plain text ('' if none)
 */
async function ocrFile(app, filePath, opts) {
	const options = Object.assign({ language: 'eng' }, opts || {});
	const stream = fs.createReadStream(filePath);
	const res = await app.zia().extractOpticalCharacters(stream, options);
	return res && res.text ? String(res.text) : '';
}

module.exports = { ocrFile };
