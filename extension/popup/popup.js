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
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return;
      chrome.scripting.executeScript({
        target: { tabId: tabs[0].id },
        func: () => window.dispatchEvent(new CustomEvent('civicos-toggle-overlay'))
      }).catch(() => {});
    });
  });
});
