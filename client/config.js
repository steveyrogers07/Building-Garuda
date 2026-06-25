// GARUDA client runtime config.
// Fill these in after `catalyst deploy` with the Dev URLs (see docs/PHASE_1_RUNBOOK.md).
// Leave a value as null to skip the optional live health check for that surface.
window.GARUDA_CONFIG = {
	// Advanced I/O function base, e.g.
	//   https://<project>-<id>.development.catalystserverless.com/server/api
	apiBaseUrl: null,
	// AppSail base, e.g.
	//   https://<appsail>-<id>.development.catalystappsail.com
	appsailBaseUrl: null
};
