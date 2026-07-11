// CivicOS AI - Background Script (Chrome MV3 service worker / Firefox MV3 event page)
// Handles: (1) backend HTTP calls from content scripts
//          (2) page navigation detection and content script re-injection
//
// The agent is scoped to the Telangana ePASS scholarship portal ONLY.
// (127.0.0.1 / localhost are included so the bundled local demo page works too.)
// The ePASS flow spans two subdomains: the public portal (telanganaepass) and
// the application/login backend (tgepass). The agent must persist across both.
//
// Cross-browser note: Chrome exposes the callback/Promise `chrome` namespace and
// runs this as a service worker; Firefox exposes the Promise-based `browser`
// namespace (plus a callback-style `chrome` alias) and runs this as an event
// page (declared via "background.scripts" in the manifest). We resolve to the
// Promise-based namespace so `await` and `.catch()` behave identically on both.
const api = globalThis.browser || globalThis.chrome;

const ALLOWED_DOMAINS = [
  'telanganaepass.cgg.gov.in',
  'tgepass.cgg.gov.in',
  '127.0.0.1',
  'localhost'
];

function isAllowedDomain(url) {
  try {
    const hostname = new URL(url).hostname;
    return ALLOWED_DOMAINS.includes(hostname);
  } catch (e) {
    return false;
  }
}

// Chrome MV3 hides session storage from content scripts by default. The content
// script keeps chat history + the "workflow active" flag there, so open it up.
// `setAccessLevel` is Chrome-only; Firefox already lets content scripts read
// session storage, so we feature-detect and skip it there.
try {
  if (api.storage && api.storage.session && typeof api.storage.session.setAccessLevel === 'function') {
    const r = api.storage.session.setAccessLevel({ accessLevel: 'TRUSTED_AND_UNTRUSTED_CONTEXTS' });
    if (r && typeof r.catch === 'function') r.catch(() => {});
  }
} catch (e) {
  console.warn('[CivicOS BG] setAccessLevel skipped:', e && e.message);
}

// ─── Backend HTTP Relay ───────────────────────────────────────────────────────
api.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'CALL_BACKEND') {
    const { endpoint, method, payload } = message.data;

    console.log('[CivicOS BG] Forwarding to backend:', endpoint);

    const fetchOptions = {
      method: method || 'POST',
      headers: { 'Content-Type': 'application/json' }
    };

    if (fetchOptions.method !== 'GET' && payload) {
      fetchOptions.body = JSON.stringify(payload);
    }

    fetch(`http://127.0.0.1:8000${endpoint}`, fetchOptions)
      .then(response => {
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return response.json();
      })
      .then(data => {
        console.log('[CivicOS BG] Backend response received for:', endpoint);
        sendResponse({ success: true, data });
      })
      .catch(error => {
        console.error('[CivicOS BG] Backend call error:', error.message);
        sendResponse({ success: false, error: error.message });
      });

    return true; // Keep message channel open for async sendResponse (Chrome + Firefox)
  }
});

// ─── Re-inject content script on full page navigation ──────────────────────
// When the browser navigates to a new full page (e.g., clicking Login), Chrome/
// Firefox inject the manifest-declared content script automatically. We ALSO
// call scripting.executeScript as a belt-and-suspenders guarantee for pages that
// load very quickly. The content script's window.CivicOSInjected guard prevents
// double-injection if the automatic injection fires first.
async function ensureContentScriptInjected(tabId, url) {
  if (!isAllowedDomain(url)) return;

  try {
    await api.scripting.executeScript({
      target: { tabId: tabId, allFrames: false },
      files: ['content.js']
    });
    console.log('[CivicOS BG] Content script injection confirmed for tab:', tabId, url);
  } catch (err) {
    // Expected when the content script is already running (guard), or on
    // restricted pages the browser refuses to inject into.
    console.log('[CivicOS BG] Content script already present or injection skipped:', err && err.message);
  }
}

// ─── SPA Navigation Detection (pushState / replaceState) ─────────────────────
api.webNavigation.onHistoryStateUpdated.addListener((details) => {
  if (details.frameId === 0) {
    console.log('[CivicOS BG] SPA navigation detected:', details.url);
    // Promise.resolve() guards against namespaces that return undefined here.
    Promise.resolve(api.tabs.sendMessage(details.tabId, { type: 'PAGE_NAVIGATED', url: details.url }))
      .catch(() => {}); // Ignore — content script may not be loaded on this tab
  }
});

// ─── Full Page Load Detection ─────────────────────────────────────────────────
api.webNavigation.onCompleted.addListener(async (details) => {
  if (details.frameId === 0) {
    console.log('[CivicOS BG] Full page load completed:', details.url);

    // Step 1: Ensure content script is injected (belt-and-suspenders)
    await ensureContentScriptInjected(details.tabId, details.url);

    // Step 2: Notify any already-running content script of the navigation
    Promise.resolve(api.tabs.sendMessage(details.tabId, { type: 'PAGE_NAVIGATED', url: details.url }))
      .catch(() => {}); // Ignore — the injected script handles its own init
  }
});
