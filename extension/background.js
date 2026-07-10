// CivicOS AI - Background Service Worker
// Handles: (1) backend HTTP calls from content scripts
//          (2) page navigation detection and content script re-injection

// The agent is scoped to the Telangana ePASS scholarship portal ONLY.
// (127.0.0.1 / localhost are included so the bundled local demo page works too.)
// The ePASS flow spans two subdomains: the public portal (telanganaepass) and
// the application/login backend (tgepass). The agent must persist across both.
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

// MV3: session storage is hidden from content scripts by default. The content
// script keeps chat history + the "workflow active" flag there, so expose it.
try {
  const r = chrome.storage.session.setAccessLevel({ accessLevel: 'TRUSTED_AND_UNTRUSTED_CONTEXTS' });
  if (r && r.catch) r.catch(() => {});
} catch (e) {
  console.warn('[CivicOS BG] setAccessLevel failed:', e && e.message);
}

// ─── Backend HTTP Relay ───────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
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

    return true; // Keep message channel open for async response
  }
});

// ─── Re-inject content script on full page navigation ──────────────────────
// This is the KEY fix for Problem 2:
// When the browser navigates to a new full page (e.g., clicking Login), the
// content script declared in manifest.json WILL be injected automatically by
// Chrome. However, we also use scripting.executeScript as a belt-and-suspenders
// approach to ensure injection even on pages that load very quickly.
//
// The content script itself uses window.CivicOSInjected to prevent double-injection
// if Chrome's automatic injection fires first.

async function ensureContentScriptInjected(tabId, url) {
  if (!isAllowedDomain(url)) return;

  try {
    // Inject the content script programmatically. Chrome will skip if already injected
    // because of the window.CivicOSInjected guard in content.js.
    await chrome.scripting.executeScript({
      target: { tabId: tabId, allFrames: false },
      files: ['content.js']
    });
    console.log('[CivicOS BG] Content script injection confirmed for tab:', tabId, url);
  } catch (err) {
    // This error is expected when the content script is already running on the page
    // (Chrome will throw "Cannot access a chrome:// URL" or similar for restricted pages)
    console.log('[CivicOS BG] Content script already present or injection skipped:', err.message);
  }
}

// ─── SPA Navigation Detection (pushState / replaceState) ─────────────────────
chrome.webNavigation.onHistoryStateUpdated.addListener((details) => {
  if (details.frameId === 0) {
    console.log('[CivicOS BG] SPA navigation detected:', details.url);
    chrome.tabs.sendMessage(details.tabId, { type: 'PAGE_NAVIGATED', url: details.url })
      .catch(() => {}); // Ignore — content script may not be loaded on this tab
  }
});

// ─── Full Page Load Detection ─────────────────────────────────────────────────
chrome.webNavigation.onCompleted.addListener(async (details) => {
  if (details.frameId === 0) {
    console.log('[CivicOS BG] Full page load completed:', details.url);

    // Step 1: Ensure content script is injected (belt-and-suspenders)
    await ensureContentScriptInjected(details.tabId, details.url);

    // Step 2: Notify any already-running content script of the navigation
    // (This handles the case where the script was already injected and listening)
    chrome.tabs.sendMessage(details.tabId, { type: 'PAGE_NAVIGATED', url: details.url })
      .catch(() => {}); // Ignore — the injected script handles its own init
  }
});
