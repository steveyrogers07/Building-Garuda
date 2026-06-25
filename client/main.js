// GARUDA client — minimal auth gate + helpers (Phase 1).
// Uses the Catalyst Web SDK exposed as `window.catalyst`. The real React SPA
// (MapLibre + force-graph + copilot) arrives in Phase 8; this only has to prove
// that hosting works and that a route can be gated behind Catalyst Auth.
(function (global) {
	'use strict';

	function sdkReady() {
		return typeof global.catalyst !== 'undefined' && !!global.catalyst.auth;
	}

	// Resolve to the signed-in user object, or null if not authenticated.
	async function currentUser() {
		if (!sdkReady()) return null;
		try {
			const res = await global.catalyst.auth.isUserAuthenticated();
			return (res && (res.content || res)) || null;
		} catch (e) {
			return null;
		}
	}

	// Guard a protected page: redirect to the login page if not signed in.
	async function requireAuth(loginPage) {
		const user = await currentUser();
		if (!user) {
			global.location.replace(loginPage || 'login.html');
			return null;
		}
		return user;
	}

	async function signOut(redirect) {
		if (!sdkReady()) return;
		try {
			await global.catalyst.auth.signOut(redirect || 'index.html');
		} catch (e) {
			/* no-op */
		}
	}

	// Render the embedded hosted-login form into the given element id.
	function renderLogin(elementId) {
		var el = document.getElementById(elementId);
		if (!sdkReady()) {
			if (el) {
				el.innerHTML =
					'<p class="warn">Catalyst Web SDK not loaded. Enable Authentication in the ' +
					'console and paste the exact embed snippet — see docs/PHASE_1_RUNBOOK.md §6.</p>';
			}
			return;
		}
		// signIn renders Catalyst's hosted login UI into the target element.
		global.catalyst.auth.signIn(elementId);
	}

	global.GARUDA = { sdkReady: sdkReady, currentUser: currentUser, requireAuth: requireAuth, signOut: signOut, renderLogin: renderLogin };
})(window);
