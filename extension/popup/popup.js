// CivicOS AI — toolbar popup (cross-browser: Chrome `chrome` / Firefox `browser`)
const api = globalThis.browser || globalThis.chrome;

document.addEventListener('DOMContentLoaded', () => {
  const statusEl = document.getElementById('status');
  const metaEl = document.getElementById('meta');

  fetch('http://127.0.0.1:8000/api/v1/health')
    .then(res => res.ok ? res.json() : Promise.reject())
    .then(data => {
      statusEl.className = 'status-badge';
      statusEl.innerText = 'Backend connected';
      const provider = data.llm_provider && data.llm_provider !== 'none'
        ? `AI: ${data.llm_provider}` : 'AI: deterministic (offline)';
      metaEl.innerText = `${provider} · ${data.workflows || 0} services loaded`;
    })
    .catch(() => {
      statusEl.className = 'status-badge disconnected';
      statusEl.innerText = 'Backend not running';
      metaEl.innerText = 'Start it: uvicorn main:app --port 8000';
    });

  document.getElementById('btn-toggle').addEventListener('click', () => {
    // Promise form works on both Chrome (MV3) and Firefox; Promise.resolve()
    // normalises any namespace that might not return a thenable.
    Promise.resolve(api.tabs.query({ active: true, currentWindow: true }))
      .then((tabs) => {
        if (!tabs || !tabs[0]) return undefined;
        return api.scripting.executeScript({
          target: { tabId: tabs[0].id },
          func: () => window.dispatchEvent(new CustomEvent('civicos-toggle-overlay'))
        });
      })
      .catch(() => {});
  });
});
