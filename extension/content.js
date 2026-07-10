// ============================================================================
// CivicOS AI — Telangana ePASS Assistant  ·  Content Script
// Navigator (spotlight step-by-step) + Accessibility panel + Multilingual UI.
// ============================================================================

(function () {
  if (window.CivicOSInjected) return;
  window.CivicOSInjected = true;

  console.log('[CivicOS] ePASS assistant active on:', window.location.href);

  // ── State ──────────────────────────────────────────────────────────────────
  let sessionId = '';
  let shadowRoot = null, uiRoot = null, panel = null;
  let messagesEl = null, inputEl = null, progressEl = null;
  let services = [];
  let spotlightEls = [], spotlightTarget = null, repositionBound = null;
  let audioContext = null, mediaStream = null, scriptProcessor = null;
  let isRecording = false, audioBuffers = [];
  let lastUrl = window.location.href;
  let autoTimer = null, lastAutoUrl = '';

  // ── Storage keys ─────────────────────────────────────────────────────────
  const HISTORY_KEY = 'civicos_chat_history';
  const WF_ACTIVE_KEY = 'civicos_workflow_active';
  const A11Y_KEY = 'civicos_a11y';
  const LANG_KEY = 'civicos_lang';
  const MAX_HISTORY = 30;

  // ── Backend relay ────────────────────────────────────────────────────────
  function callBackend(endpoint, method, payload) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: 'CALL_BACKEND', data: { endpoint, method, payload } },
        (res) => resolve(res || { success: false, error: 'no response' })
      );
    });
  }

  // ══════════════════════════════════════════════════════════════════════════
  //  I18N  — English is the source of truth; other languages are fetched from
  //  the backend translator (cached) and applied live.
  // ══════════════════════════════════════════════════════════════════════════
  const STR = {
    subtitle: 'Your Telangana ePASS Copilot',
    inputPlaceholder: "Ask me, e.g. 'check my scholarship status'",
    welcomeTitle: "Namaste! 🙏 I'm your ePASS guide.",
    welcomeBody: "Tell me what you need and I'll highlight exactly which button to click — one step at a time.",
    popular: 'Popular services',
    thinking: 'Thinking…',
    transcribing: 'Transcribing…',
    pageChanging: 'Page changed — finding your next step…',
    continuing: '📍 Continuing your guide on this page…',
    backendError: "I can't reach the CivicOS backend. Is it running on 127.0.0.1:8000?",
    micDenied: 'Microphone access was denied.',
    notCaught: "I didn't catch that — please try again.",
    a11yTip: 'Accessibility Options',
    langTip: 'Language',
    resetTip: 'Start a new chat',
    closeTip: 'Close',
    micTip: 'Speak',
    sendTip: 'Send',
    accessibility: 'Accessibility',
    resetAll: 'Reset all settings',
    step: 'Step',
    f_incText: 'Increase Text Size', f_decText: 'Decrease Text Size', f_spacing: 'Text Spacing',
    f_lineH: 'Line Height', f_adhd: 'ADHD Mode', f_sat: 'Saturation', f_light: 'Light Mode',
    f_dark: 'Dark Mode', f_invert: 'Invert Colors', f_links: 'Highlight Links', f_tts: 'Text-to-Speech',
    f_cursor: 'Cursor', f_pause: 'Pause Animations', f_hideImg: 'Hide Images',
    // Image compressor
    compressTip: 'Compress Image', compressTitle: 'Image Compressor',
    compressUpload: 'Click to upload an image (JPG, PNG…)', compressTo: 'Compress to',
    compressBtn: 'Compress', downloadBtn: 'Download',
    compressPick: 'Please choose an image first.', compressBadSize: 'Enter a valid target size.',
    compressWorking: 'Compressing…', compressFail: "Couldn't read this image — try a JPG or PNG.",
    compressFrom: 'from', compressSmaller: 'smaller',
    compressNote: 'This is the smallest we could reach without heavy quality loss.',
  };
  let currentLang = 'en';
  let TR = {};                              // key → translated string for currentLang
  const t = (key) => (TR[key] || STR[key] || key);

  const LANG_BCP = { en: 'en-IN', hi: 'hi-IN', te: 'te-IN', ta: 'ta-IN', kn: 'kn-IN', ml: 'ml-IN', mr: 'mr-IN', gu: 'gu-IN', bn: 'bn-IN', pa: 'pa-IN', or: 'or-IN' };
  let languages = [{ code: 'en', name: 'English', native: 'English' }];

  function fetchUiTranslations(lang, done) {
    if (lang === 'en') { TR = {}; return done && done(); }
    const keys = Object.keys(STR);
    callBackend('/api/v1/translate', 'POST', { texts: keys.map(k => STR[k]), language: lang }).then((res) => {
      TR = {};
      if (res.success && res.data && Array.isArray(res.data.translations)) {
        res.data.translations.forEach((tr, i) => { if (tr) TR[keys[i]] = tr; });
      }
      done && done();
    });
  }

  function setLanguage(code) {
    currentLang = code;
    chrome.storage.local.set({ [LANG_KEY]: code });
    LANG.close();
    fetchUiTranslations(code, () => {
      fetchServices(() => {
        applyUiLanguage();
        refreshWelcome();
      });
    });
  }

  function applyUiLanguage() {
    if (!panel) return;
    const sub = panel.querySelector('.cv-subtitle'); if (sub) sub.innerText = t('subtitle');
    if (inputEl) inputEl.placeholder = t('inputPlaceholder');
    const at = panel.querySelector('.civicos-a11y-title'); if (at) at.innerText = t('accessibility');
    const ar = panel.querySelector('.civicos-a11y-reset'); if (ar) ar.innerText = t('resetAll');
    A11Y.renderTiles();
    LANG.markActive();
    COMPRESS.applyLang();
  }

  // ══════════════════════════════════════════════════════════════════════════
  //  ACCESSIBILITY  — all settings apply live to the assistant; a few safe
  //  visual effects (hide images, big cursor, highlight links, pause anim) also
  //  apply to the host page. Persisted across sessions.
  // ══════════════════════════════════════════════════════════════════════════
  const A11Y = (() => {
    const DEFAULT = {
      fontScale: 1, spacing: 0, lineHeight: 0, adhd: false, saturation: 'normal',
      theme: 'light', invert: false, highlightLinks: false, tts: true,
      bigCursor: false, pauseAnim: false, hideImages: false,
    };
    let s = Object.assign({}, DEFAULT);
    let adhdTop = null, adhdBot = null, adhdMove = null;

    const FEATURES = [
      { key: 'incText', icon: '🔠', labelKey: 'f_incText' },
      { key: 'decText', icon: '🔡', labelKey: 'f_decText' },
      { key: 'spacing', icon: '↔️', labelKey: 'f_spacing' },
      { key: 'lineH', icon: '≣', labelKey: 'f_lineH' },
      { key: 'adhd', icon: '🧠', labelKey: 'f_adhd' },
      { key: 'sat', icon: '🎨', labelKey: 'f_sat' },
      { key: 'light', icon: '☀️', labelKey: 'f_light' },
      { key: 'dark', icon: '🌙', labelKey: 'f_dark' },
      { key: 'invert', icon: '🌓', labelKey: 'f_invert' },
      { key: 'links', icon: '🔗', labelKey: 'f_links' },
      { key: 'tts', icon: '🔊', labelKey: 'f_tts' },
      { key: 'cursor', icon: '🖱️', labelKey: 'f_cursor' },
      { key: 'pause', icon: '⏸️', labelKey: 'f_pause' },
      { key: 'hideImg', icon: '🖼️', labelKey: 'f_hideImg' },
    ];

    const round1 = (n) => Math.round(n * 10) / 10;

    function stateFor(key) {
      switch (key) {
        case 'incText': return { active: s.fontScale > 1, badge: s.fontScale !== 1 ? Math.round(s.fontScale * 100) + '%' : '' };
        case 'decText': return { active: s.fontScale < 1, badge: s.fontScale !== 1 ? Math.round(s.fontScale * 100) + '%' : '' };
        case 'spacing': return { active: s.spacing > 0, badge: s.spacing ? String(s.spacing) : '' };
        case 'lineH': return { active: s.lineHeight > 0, badge: s.lineHeight ? String(s.lineHeight) : '' };
        case 'adhd': return { active: s.adhd, badge: '' };
        case 'sat': return { active: s.saturation !== 'normal', badge: { low: 'LOW', high: 'HIGH', grayscale: 'B&W' }[s.saturation] || '' };
        case 'light': return { active: s.theme === 'light', badge: '' };
        case 'dark': return { active: s.theme === 'dark', badge: '' };
        case 'invert': return { active: s.invert, badge: '' };
        case 'links': return { active: s.highlightLinks, badge: '' };
        case 'tts': return { active: s.tts, badge: '' };
        case 'cursor': return { active: s.bigCursor, badge: '' };
        case 'pause': return { active: s.pauseAnim, badge: '' };
        case 'hideImg': return { active: s.hideImages, badge: '' };
        default: return { active: false, badge: '' };
      }
    }

    function onTile(key) {
      switch (key) {
        case 'incText': s.fontScale = round1(Math.min(1.6, s.fontScale + 0.1)); break;
        case 'decText': s.fontScale = round1(Math.max(0.8, s.fontScale - 0.1)); break;
        case 'spacing': s.spacing = (s.spacing + 1) % 3; break;
        case 'lineH': s.lineHeight = (s.lineHeight + 1) % 3; break;
        case 'adhd': s.adhd = !s.adhd; break;
        case 'sat': s.saturation = { normal: 'low', low: 'high', high: 'grayscale', grayscale: 'normal' }[s.saturation]; break;
        case 'light': s.theme = 'light'; break;
        case 'dark': s.theme = 'dark'; break;
        case 'invert': s.invert = !s.invert; break;
        case 'links': s.highlightLinks = !s.highlightLinks; break;
        case 'tts': s.tts = !s.tts; break;
        case 'cursor': s.bigCursor = !s.bigCursor; break;
        case 'pause': s.pauseAnim = !s.pauseAnim; break;
        case 'hideImg': s.hideImages = !s.hideImages; break;
      }
      apply(); save(); renderTiles();
    }

    function apply() {
      if (!uiRoot) return;
      uiRoot.style.setProperty('--cv-fs', s.fontScale);
      uiRoot.style.setProperty('--cv-ls', ['0em', '.05em', '.12em'][s.spacing]);
      uiRoot.style.setProperty('--cv-ws', ['0em', '.1em', '.2em'][s.spacing]);
      uiRoot.style.setProperty('--cv-lh', ['1.5', '1.8', '2.1'][s.lineHeight]);
      uiRoot.classList.toggle('cv-dark', s.theme === 'dark');
      uiRoot.classList.toggle('cv-highlight-links', s.highlightLinks);
      uiRoot.classList.toggle('cv-big-cursor', s.bigCursor);
      uiRoot.classList.toggle('cv-pause-anim', s.pauseAnim);

      const f = [];
      if (s.invert) f.push('invert(1) hue-rotate(180deg)');
      if (s.saturation === 'low') f.push('saturate(.45)');
      else if (s.saturation === 'high') f.push('saturate(1.7)');
      else if (s.saturation === 'grayscale') f.push('grayscale(1)');
      uiRoot.style.setProperty('--cv-filter', f.length ? f.join(' ') : 'none');

      applyPageStyles();
      toggleAdhd(s.adhd);
    }

    function applyPageStyles() {
      try {
        const de = document.documentElement;
        de.classList.toggle('cv-hide-images', s.hideImages);
        de.classList.toggle('cv-hl-links', s.highlightLinks);
        de.classList.toggle('cv-pause', s.pauseAnim);
        de.classList.toggle('cv-bigcur', s.bigCursor);
        let st = document.getElementById('civicos-a11y-page');
        if (!st) { st = document.createElement('style'); st.id = 'civicos-a11y-page'; document.head.appendChild(st); }
        st.textContent =
          "html.cv-hide-images img, html.cv-hide-images picture, html.cv-hide-images video { visibility:hidden !important; }" +
          "html.cv-hl-links a { outline:2px solid #f59e0b !important; background:rgba(245,158,11,.12) !important; }" +
          "html.cv-pause *, html.cv-pause *::before, html.cv-pause *::after { animation:none !important; transition:none !important; scroll-behavior:auto !important; }" +
          "html.cv-bigcur, html.cv-bigcur * { cursor: url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40'><path d='M6 2l24 13-10 2 6 12-4 2-6-12-8 7z' fill='white' stroke='black' stroke-width='2'/></svg>\") 4 2, auto !important; }";
      } catch (e) { /* CSP may block; assistant effects still work */ }
    }

    function toggleAdhd(on) {
      if (on && !adhdTop) {
        adhdTop = document.createElement('div'); adhdTop.className = 'civicos-adhd-mask';
        adhdBot = document.createElement('div'); adhdBot.className = 'civicos-adhd-mask';
        uiRoot.appendChild(adhdTop); uiRoot.appendChild(adhdBot);
        adhdMove = (e) => {
          const y = e.clientY, h = window.innerHeight, half = 46;
          adhdTop.style.top = '0px'; adhdTop.style.height = Math.max(0, y - half) + 'px';
          adhdBot.style.top = (y + half) + 'px'; adhdBot.style.height = Math.max(0, h - (y + half)) + 'px';
        };
        window.addEventListener('mousemove', adhdMove, { passive: true });
      } else if (!on && adhdTop) {
        window.removeEventListener('mousemove', adhdMove);
        adhdTop.remove(); adhdBot.remove(); adhdTop = adhdBot = adhdMove = null;
      }
    }

    function renderTiles() {
      const grid = panel && panel.querySelector('.civicos-a11y-grid');
      if (!grid) return;
      grid.innerHTML = FEATURES.map(f => {
        const st = stateFor(f.key);
        return `<div class="civicos-a11y-tile ${st.active ? 'active' : ''}" data-a11y="${f.key}">
          ${st.badge ? `<span class="abadge">${escapeHtml(st.badge)}</span>` : ''}
          <div class="ai" style="font-size:22px">${f.icon}</div>
          <div class="al">${escapeHtml(t(f.labelKey))}</div>
        </div>`;
      }).join('');
    }

    function open() { const p = panel.querySelector('.civicos-a11y-panel'); if (p) { renderTiles(); p.classList.add('open'); panel.classList.add('a11y-open'); } }
    function close() { const p = panel.querySelector('.civicos-a11y-panel'); if (p) p.classList.remove('open'); panel.classList.remove('a11y-open'); }
    function resetAll() { s = Object.assign({}, DEFAULT); apply(); save(); renderTiles(); }
    function save() { chrome.storage.local.set({ [A11Y_KEY]: s }); }
    function load(done) {
      chrome.storage.local.get([A11Y_KEY], (r) => {
        if (r[A11Y_KEY]) s = Object.assign({}, DEFAULT, r[A11Y_KEY]);
        apply(); done && done();
      });
    }

    return { FEATURES, apply, renderTiles, open, close, resetAll, load, onTile, ttsEnabled: () => s.tts };
  })();

  // ══════════════════════════════════════════════════════════════════════════
  //  LANGUAGE selector
  // ══════════════════════════════════════════════════════════════════════════
  const LANG = (() => {
    function buildMenu() {
      const menu = panel.querySelector('.civicos-lang-menu');
      if (!menu) return;
      menu.innerHTML = languages.map(l => `
        <div class="civicos-lang-item ${l.code === currentLang ? 'active' : ''}" data-lang="${l.code}">
          <span>${escapeHtml(l.native)}</span><span class="en">${escapeHtml(l.name)}</span>
        </div>`).join('');
    }
    function markActive() {
      const menu = panel && panel.querySelector('.civicos-lang-menu');
      if (!menu) return;
      menu.querySelectorAll('.civicos-lang-item').forEach(it =>
        it.classList.toggle('active', it.getAttribute('data-lang') === currentLang));
    }
    function toggle() { const m = panel.querySelector('.civicos-lang-menu'); if (m) m.classList.toggle('open'); }
    function close() { const m = panel && panel.querySelector('.civicos-lang-menu'); if (m) m.classList.remove('open'); }
    return { buildMenu, markActive, toggle, close };
  })();

  // ══════════════════════════════════════════════════════════════════════════
  //  IMAGE COMPRESSOR  — 100% local (Canvas). Compresses an uploaded image to a
  //  user-set target size (KB/MB) for portal upload limits. Nothing leaves the
  //  machine; no backend call. Output is JPEG (reliable size targeting).
  // ══════════════════════════════════════════════════════════════════════════
  const COMPRESS = (() => {
    let file = null;      // selected File
    let unit = 'KB';
    let outBlob = null;   // compressed result
    let outUrl = null;    // object URL (preview + download)

    const q = (sel) => panel && panel.querySelector(sel);

    function open() {
      LANG.close(); A11Y.close();
      const p = q('.civicos-compress-panel');
      if (p) { p.classList.add('open'); panel.classList.add('compress-open'); }
    }
    function close() {
      const p = q('.civicos-compress-panel');
      if (p) p.classList.remove('open');
      if (panel) panel.classList.remove('compress-open');
    }

    function sizeStr(n) {
      if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(2) + ' MB';
      if (n >= 1024) return (n / 1024).toFixed(1) + ' KB';
      return n + ' B';
    }

    function resetResult() {
      if (outUrl) { URL.revokeObjectURL(outUrl); outUrl = null; }
      outBlob = null;
      const r = q('.civicos-c-result'); if (r) r.innerHTML = '';
    }

    function onFile(input) {
      const f = input.files && input.files[0];
      if (!f) return;
      file = f;
      resetResult();
      const info = q('.civicos-c-file');
      if (info) {
        const url = URL.createObjectURL(f);
        info.innerHTML = `<img class="civicos-c-thumb" src="${url}" alt=""><div class="civicos-c-fmeta"><b>${escapeHtml(f.name)}</b><span>${sizeStr(f.size)}</span></div>`;
      }
    }

    function setUnit(u) {
      unit = u;
      panel.querySelectorAll('.civicos-c-unitbtn').forEach((b) =>
        b.classList.toggle('active', b.getAttribute('data-unit') === u));
    }

    function targetBytes() {
      const v = parseFloat(q('.civicos-c-size').value);
      if (!v || v <= 0) return 0;
      return Math.round(v * (unit === 'MB' ? 1024 * 1024 : 1024));
    }

    function canvasToBlob(canvas, type, quality) {
      return new Promise((res) => canvas.toBlob(res, type, quality));
    }

    async function encode(bitmap, scale, quality) {
      const w = Math.max(1, Math.round(bitmap.width * scale));
      const h = Math.max(1, Math.round(bitmap.height * scale));
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, w, h);   // flatten transparency (PNG → JPG)
      ctx.drawImage(bitmap, 0, 0, w, h);
      return canvasToBlob(canvas, 'image/jpeg', quality);
    }

    // Prefer full resolution at lower quality; downscale only when quality alone
    // can't reach the target. Returns the largest blob that is still ≤ target
    // (or the smallest achievable if the target is unreachable).
    async function compressToTarget(bitmap, target) {
      const scales = [1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15];
      let best = null;
      for (const scale of scales) {
        const low = await encode(bitmap, scale, 0.3);   // cheapest at this scale
        if (!best || low.size < best.size) best = low;
        if (low.size > target) continue;                // can't fit even at min quality → shrink
        let lo = 0.3, hi = 0.95, fit = low;
        for (let i = 0; i < 7; i++) {                   // binary-search highest quality under target
          const mid = (lo + hi) / 2;
          const blob = await encode(bitmap, scale, mid);
          if (blob.size <= target) { fit = blob; lo = mid; }
          else { hi = mid; }
        }
        return { blob: fit, reached: true };
      }
      return { blob: best, reached: !!(best && best.size <= target) };
    }

    async function doCompress() {
      if (!file) { flash(t('compressPick')); return; }
      const target = targetBytes();
      if (!target) { flash(t('compressBadSize')); return; }
      const go = q('.civicos-c-go');
      const prev = go.innerText; go.disabled = true; go.innerText = t('compressWorking');
      try {
        let bitmap;
        try { bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' }); }
        catch (e) { bitmap = await createImageBitmap(file); }
        const { blob, reached } = await compressToTarget(bitmap, target);
        if (bitmap.close) bitmap.close();
        if (!blob) throw new Error('encode failed');
        resetResult();
        outBlob = blob; outUrl = URL.createObjectURL(blob);
        renderResult(reached);
      } catch (e) {
        flash(t('compressFail'));
      } finally {
        go.disabled = false; go.innerText = prev;
      }
    }

    function renderResult(reached) {
      const r = q('.civicos-c-result');
      if (!r) return;
      const pct = file.size ? Math.max(0, Math.round((1 - outBlob.size / file.size) * 100)) : 0;
      const note = reached ? '' : `<div class="civicos-c-note">${escapeHtml(t('compressNote'))}</div>`;
      r.innerHTML = `
        <div class="civicos-c-card">
          <img class="civicos-c-preview" src="${outUrl}" alt="">
          <div class="civicos-c-stats">
            <div class="civicos-c-ok">${sizeStr(outBlob.size)}</div>
            <div class="civicos-c-sub">${escapeHtml(t('compressFrom'))} ${sizeStr(file.size)} · ${pct}% ${escapeHtml(t('compressSmaller'))}</div>
            ${note}
          </div>
          <button class="civicos-c-download">⬇ ${escapeHtml(t('downloadBtn'))}</button>
        </div>`;
      r.querySelector('.civicos-c-download').addEventListener('click', doDownload);
    }

    function doDownload() {
      if (!outBlob) return;
      const base = file && file.name ? file.name.replace(/\.[^.]+$/, '') : 'image';
      const a = document.createElement('a');
      a.href = outUrl || URL.createObjectURL(outBlob);
      a.download = base + '-compressed.jpg';
      uiRoot.appendChild(a); a.click(); a.remove();
    }

    function flash(msg) {
      const r = q('.civicos-c-result');
      if (r) r.innerHTML = `<div class="civicos-c-warn">${escapeHtml(msg)}</div>`;
    }

    function applyLang() {
      const set = (sel, key) => { const el = q(sel); if (el) el.innerText = t(key); };
      set('.civicos-compress-title', 'compressTitle');
      set('.civicos-c-uploadtx', 'compressUpload');
      set('.civicos-c-tolabel', 'compressTo');
      set('.civicos-c-go', 'compressBtn');
    }

    return { open, close, onFile, setUnit, doCompress, applyLang };
  })();

  // ── Icons ────────────────────────────────────────────────────────────────
  const ROBOT_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 7V4"/><circle cx="12" cy="3" r="1.3" fill="#fff"/><circle cx="9" cy="13" r="1.3" fill="#fff" stroke="none"/><circle cx="15" cy="13" r="1.3" fill="#fff" stroke="none"/><path d="M9.5 16.5h5"/><path d="M4 12H2.5"/><path d="M21.5 12H20"/></svg>`;
  const ACCESS_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="3.7" r="1.7" fill="#fff" stroke="none"/><path d="M4.5 8.3c2.4 1 5 1.3 7.5 1.3s5.1-.3 7.5-1.3"/><path d="M12 9.6V15"/><path d="M12 15l-2.7 5.6"/><path d="M12 15l2.7 5.6"/></svg>`;
  const GLOBE_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg>`;
  const COMPRESS_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="M21 15l-4.5-4.5L7 20"/></svg>`;

  // ── Inject UI ────────────────────────────────────────────────────────────
  function injectUI() {
    if (!document.body) { setTimeout(injectUI, 300); return; }

    const host = document.createElement('div');
    host.id = 'civicos-root';
    document.body.appendChild(host);
    shadowRoot = host.attachShadow({ mode: 'open' });

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = chrome.runtime.getURL('overlay/overlay.css');
    shadowRoot.appendChild(link);

    uiRoot = document.createElement('div');
    uiRoot.className = 'civicos-container';
    shadowRoot.appendChild(uiRoot);

    const fab = document.createElement('div');
    fab.className = 'civicos-fab';
    fab.innerHTML = ROBOT_SVG;
    uiRoot.appendChild(fab);

    panel = document.createElement('div');
    panel.className = 'civicos-panel';
    panel.innerHTML = `
      <div class="civicos-header">
        <div class="civicos-a11y-btn" data-tip="a11yTip" aria-label="Accessibility Options">${ACCESS_SVG}</div>
        <div class="civicos-htext">
          <h3>CivicOS AI</h3>
          <p class="cv-subtitle">${escapeHtml(STR.subtitle)}</p>
        </div>
        <div class="civicos-status-dot off"></div>
        <button class="civicos-hbtn civicos-compress-btn" data-tip="compressTip" aria-label="Compress Image">${COMPRESS_SVG}</button>
        <button class="civicos-hbtn civicos-lang-btn" data-tip="langTip" aria-label="Language">${GLOBE_SVG}</button>
        <button class="civicos-hbtn civicos-reset" data-tip="resetTip" aria-label="New chat">&#8635;</button>
        <button class="civicos-hbtn civicos-close" data-tip="closeTip" aria-label="Close">&times;</button>
      </div>
      <div class="civicos-progress">
        <div class="civicos-progress-top"><b>Step 1 of 4</b><span></span></div>
        <div class="civicos-steps"></div>
      </div>
      <div class="civicos-messages"></div>
      <div class="civicos-inputbar">
        <input class="civicos-input" type="text" placeholder="${escapeAttr(STR.inputPlaceholder)}">
        <button class="civicos-iconbtn civicos-mic" data-tip="micTip" aria-label="Speak">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2"/><path d="M12 19v3"/></svg>
        </button>
        <button class="civicos-iconbtn civicos-send" data-tip="sendTip" aria-label="Send">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
        </button>
      </div>
      <div class="civicos-lang-menu"></div>
      <div class="civicos-a11y-panel">
        <div class="civicos-a11y-head">
          <span style="width:24px;height:24px;display:inline-flex">${ACCESS_SVG}</span>
          <b class="civicos-a11y-title">${escapeHtml(STR.accessibility)}</b>
          <button class="civicos-hbtn civicos-a11y-close" aria-label="Back">&times;</button>
        </div>
        <div class="civicos-a11y-scroll">
          <div class="civicos-a11y-grid"></div>
          <button class="civicos-a11y-reset">${escapeHtml(STR.resetAll)}</button>
        </div>
      </div>
      <div class="civicos-compress-panel">
        <div class="civicos-a11y-head">
          <span style="width:24px;height:24px;display:inline-flex">${COMPRESS_SVG}</span>
          <b class="civicos-compress-title">${escapeHtml(STR.compressTitle)}</b>
          <button class="civicos-hbtn civicos-compress-close" aria-label="Back">&times;</button>
        </div>
        <div class="civicos-compress-scroll">
          <label class="civicos-drop">
            <input class="civicos-file" type="file" accept="image/*" hidden>
            <div class="civicos-drop-ic">🖼️</div>
            <div class="civicos-drop-tx civicos-c-uploadtx">${escapeHtml(STR.compressUpload)}</div>
          </label>
          <div class="civicos-c-file"></div>
          <div class="civicos-c-label civicos-c-tolabel">${escapeHtml(STR.compressTo)}</div>
          <div class="civicos-c-presets">
            <button class="civicos-c-chip" data-kb="100">100 KB</button>
            <button class="civicos-c-chip" data-kb="150">150 KB</button>
            <button class="civicos-c-chip" data-kb="250">250 KB</button>
          </div>
          <div class="civicos-c-sizerow">
            <input class="civicos-c-size" type="number" min="1" step="1" inputmode="numeric" placeholder="150">
            <div class="civicos-c-unit">
              <button class="civicos-c-unitbtn active" data-unit="KB">KB</button>
              <button class="civicos-c-unitbtn" data-unit="MB">MB</button>
            </div>
          </div>
          <button class="civicos-c-go">${escapeHtml(STR.compressBtn)}</button>
          <div class="civicos-c-result"></div>
        </div>
      </div>`;
    uiRoot.appendChild(panel);

    messagesEl = panel.querySelector('.civicos-messages');
    inputEl = panel.querySelector('.civicos-input');
    progressEl = panel.querySelector('.civicos-progress');
    const statusDot = panel.querySelector('.civicos-status-dot');

    // ── Wiring ──────────────────────────────────────────────────────────────
    fab.addEventListener('click', () => panel.classList.toggle('active'));
    panel.querySelector('.civicos-close').addEventListener('click', () => panel.classList.remove('active'));
    panel.querySelector('.civicos-reset').addEventListener('click', () => resetChat());
    window.addEventListener('civicos-toggle-overlay', () => panel.classList.toggle('active'));

    panel.querySelector('.civicos-a11y-btn').addEventListener('click', () => { COMPRESS.close(); A11Y.open(); });
    panel.querySelector('.civicos-a11y-close').addEventListener('click', () => A11Y.close());
    panel.querySelector('.civicos-a11y-reset').addEventListener('click', () => A11Y.resetAll());
    panel.querySelector('.civicos-a11y-grid').addEventListener('click', (e) => {
      const tile = e.target.closest('[data-a11y]'); if (tile) A11Y.onTile(tile.getAttribute('data-a11y'));
    });

    panel.querySelector('.civicos-lang-btn').addEventListener('click', (e) => { e.stopPropagation(); LANG.toggle(); });
    panel.querySelector('.civicos-lang-menu').addEventListener('click', (e) => {
      const it = e.target.closest('[data-lang]'); if (it) setLanguage(it.getAttribute('data-lang'));
    });

    // Image compressor
    panel.querySelector('.civicos-compress-btn').addEventListener('click', () => COMPRESS.open());
    panel.querySelector('.civicos-compress-close').addEventListener('click', () => COMPRESS.close());
    panel.querySelector('.civicos-file').addEventListener('change', (e) => COMPRESS.onFile(e.target));
    panel.querySelector('.civicos-c-go').addEventListener('click', () => COMPRESS.doCompress());
    panel.querySelector('.civicos-c-presets').addEventListener('click', (e) => {
      const chip = e.target.closest('[data-kb]'); if (!chip) return;
      panel.querySelector('.civicos-c-size').value = chip.getAttribute('data-kb'); COMPRESS.setUnit('KB');
    });
    panel.querySelector('.civicos-c-unit').addEventListener('click', (e) => {
      const b = e.target.closest('[data-unit]'); if (b) COMPRESS.setUnit(b.getAttribute('data-unit'));
    });
    uiRoot.addEventListener('click', (e) => { if (!e.target.closest('.civicos-lang-btn') && !e.target.closest('.civicos-lang-menu')) LANG.close(); });

    // Click-to-read (accessibility TTS)
    messagesEl.addEventListener('click', (e) => {
      const b = e.target.closest('.civicos-bubble');
      if (b && A11Y.ttsEnabled()) speak(b.innerText);
    });

    const onSend = () => {
      const v = inputEl.value.trim();
      if (!v) return;
      appendMessage(v, 'user');
      inputEl.value = '';
      sendText(v);
    };
    panel.querySelector('.civicos-send').addEventListener('click', onSend);
    inputEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') onSend(); });
    panel.querySelector('.civicos-mic').addEventListener('click', (e) => {
      const btn = e.currentTarget;
      if (isRecording) stopRecording(btn, (b64) => sendVoice(b64));
      else startRecording(btn);
    });

    initTooltips();

    // ── Startup: languages, a11y, health, services, then restore/welcome ─────
    callBackend('/api/v1/languages', 'GET').then((res) => {
      if (res.success && res.data && Array.isArray(res.data.languages) && res.data.languages.length) languages = res.data.languages;
      LANG.buildMenu();
    });
    callBackend('/api/v1/health', 'GET').then((res) => { if (res.success) statusDot.classList.remove('off'); });

    chrome.storage.local.get([LANG_KEY], (r) => {
      currentLang = r[LANG_KEY] || 'en';
      A11Y.load(() => {
        fetchUiTranslations(currentLang, () => {
          applyUiLanguage();
          fetchServices(() => {
            chrome.storage.session.get([WF_ACTIVE_KEY], (w) => {
              if (w[WF_ACTIVE_KEY]) {
                restoreHistory((had) => {
                  if (had) _appendDOM(t('continuing'), 'assistant');
                  panel.classList.add('active');
                  triggerAutoStep();
                });
              } else {
                clearHistory();
                renderWelcome();
              }
            });
          });
        });
      });
    });
  }

  // ── Shared hover tooltip (never clipped) ──────────────────────────────────
  let tipEl = null;
  function initTooltips() {
    tipEl = document.createElement('div');
    tipEl.className = 'civicos-cv-tip';
    uiRoot.appendChild(tipEl);
    uiRoot.addEventListener('mouseover', (e) => {
      const el = e.target.closest && e.target.closest('[data-tip]');
      if (!el) return;
      tipEl.textContent = t(el.getAttribute('data-tip'));
      const r = el.getBoundingClientRect();
      tipEl.style.left = Math.max(6, Math.min(r.left, window.innerWidth - 180)) + 'px';
      tipEl.style.top = (r.bottom + 8) + 'px';
      tipEl.classList.add('show');
    });
    uiRoot.addEventListener('mouseout', (e) => {
      if (e.target.closest && e.target.closest('[data-tip]')) tipEl.classList.remove('show');
    });
  }

  // ── Reset chat ────────────────────────────────────────────────────────────
  function resetChat() {
    removeSpotlight();
    clearHistory();
    lastAutoUrl = '';
    chrome.storage.session.set({ [WF_ACTIVE_KEY]: false });
    if (progressEl) progressEl.classList.remove('show');
    sessionId = 'session_' + Math.random().toString(36).slice(2, 14);
    chrome.storage.local.set({ civicos_session_id: sessionId });
    if (messagesEl) messagesEl.innerHTML = '';
    renderWelcome();
  }

  // ── Session id ───────────────────────────────────────────────────────────
  chrome.storage.local.get(['civicos_session_id'], (r) => {
    sessionId = r.civicos_session_id || ('session_' + Math.random().toString(36).slice(2, 14));
    chrome.storage.local.set({ civicos_session_id: sessionId });
  });

  // ── History persistence ───────────────────────────────────────────────────
  function saveMsg(text, type) {
    chrome.storage.session.get([HISTORY_KEY], (r) => {
      const h = r[HISTORY_KEY] || [];
      h.push({ text, type, ts: Date.now() });
      if (h.length > MAX_HISTORY) h.splice(0, h.length - MAX_HISTORY);
      chrome.storage.session.set({ [HISTORY_KEY]: h });
    });
  }
  function clearHistory() { chrome.storage.session.set({ [HISTORY_KEY]: [] }); }
  function restoreHistory(done) {
    chrome.storage.session.get([HISTORY_KEY], (r) => {
      const h = r[HISTORY_KEY] || [];
      if (!h.length) return done(false);
      h.forEach(m => _appendDOM(m.text, m.type));
      done(true);
    });
  }

  // ── Services + welcome ───────────────────────────────────────────────────
  function fetchServices(done) {
    callBackend('/api/v1/services?lang=' + encodeURIComponent(currentLang), 'GET').then((res) => {
      if (res.success && res.data && res.data.services) services = res.data.services;
      done && done();
    });
  }

  function renderWelcome() {
    if (!messagesEl) return;
    const w = document.createElement('div');
    w.className = 'civicos-welcome';
    const featured = services.filter(s => !s.external).slice(0, 6);
    const chips = featured.map(s => `
      <button class="civicos-chip" data-wf="${escapeAttr(s.workflow_id)}" data-title="${escapeAttr(s.title)}">
        <span class="ic">${s.icon || '📄'}</span>
        <span class="tx"><b>${escapeHtml(s.title)}</b><span>${escapeHtml(s.blurb || '')}</span></span>
      </button>`).join('');
    w.innerHTML = `
      <h4>${escapeHtml(t('welcomeTitle'))}</h4>
      <p>${escapeHtml(t('welcomeBody'))}</p>
      <div class="civicos-chip-label">${escapeHtml(t('popular'))}</div>
      <div class="civicos-chips">${chips}</div>`;
    messagesEl.appendChild(w);
    w.querySelectorAll('.civicos-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        appendMessage(btn.getAttribute('data-title'), 'user');
        sendText('__start__:' + btn.getAttribute('data-wf'));
      });
    });
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
  function clearWelcome() { const w = messagesEl && messagesEl.querySelector('.civicos-welcome'); if (w) w.remove(); }
  function refreshWelcome() {
    if (messagesEl && messagesEl.querySelector('.civicos-welcome')) { clearWelcome(); renderWelcome(); }
  }

  // ── Messages ─────────────────────────────────────────────────────────────
  function _appendDOM(text, type) {
    if (!messagesEl) return null;
    const b = document.createElement('div');
    b.className = `civicos-bubble ${type}`;
    b.innerText = text;
    messagesEl.appendChild(b);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return b;
  }
  function appendMessage(text, type) {
    clearWelcome();
    const b = _appendDOM(text, type);
    if (b) saveMsg(text, type);
    return b;
  }

  // ── Send text / voice ────────────────────────────────────────────────────
  function sendText(text) {
    clearWelcome();
    lastAutoUrl = '';
    const dom = scanDOM();
    const loading = _appendDOM(t('thinking'), 'assistant thinking');
    callBackend('/api/v1/step', 'POST', {
      session_id: sessionId, dom_snapshot: dom, user_utterance: text, url: window.location.href, language: currentLang
    }).then((res) => {
      if (loading) loading.remove();
      if (res.success && res.data) handleResponse(res.data);
      else appendMessage(t('backendError'), 'warning');
    });
  }

  function sendVoice(b64) {
    const loading = _appendDOM(t('transcribing'), 'assistant thinking');
    callBackend('/api/v1/voice/transcribe', 'POST', { session_id: sessionId, audio_b64: b64 }).then((res) => {
      if (loading) loading.remove();
      if (res.success && res.data && res.data.status === 'success' && res.data.text.trim()) {
        const v = res.data.text.trim();
        appendMessage(v, 'user');
        sendText(v);
      } else {
        appendMessage(t('notCaught'), 'warning');
      }
    });
  }

  // ── Handle a StepResponse ────────────────────────────────────────────────
  function handleResponse(step) {
    const cls = step.action === 'confirm_required' ? 'warning'
      : step.action === 'complete' ? 'complete' : 'assistant';
    appendMessage(step.narration_text, cls);
    speak(step.narration_text);

    const active = !!step.workflow_id && !step.is_final && step.action !== 'complete';
    chrome.storage.session.set({ [WF_ACTIVE_KEY]: active });

    updateProgress(step);

    if (step.action === 'form') {
      applySpotlight(step.target_selector, shortInstruction(step.narration_text), { subtle: true, noScroll: true });
    } else if (step.action === 'highlight') {
      applySpotlight(step.target_selector, shortInstruction(step.narration_text), {});
    } else if (step.action === 'confirm_required') {
      applySpotlight(step.target_selector, shortInstruction(step.narration_text), { warning: true });
    } else {
      removeSpotlight();
    }
  }

  function updateProgress(step) {
    if (!progressEl) return;
    const total = step.total_steps || 0;
    const idx = step.step_index;
    if (!step.workflow_id || total <= 0 || idx < 0 || step.is_final || step.action === 'complete') {
      progressEl.classList.remove('show'); return;
    }
    progressEl.classList.add('show');
    progressEl.querySelector('b').innerText = `${t('step')} ${idx + 1} / ${total}`;
    progressEl.querySelector('span').innerText = step.service_title || '';
    const steps = progressEl.querySelector('.civicos-steps');
    steps.innerHTML = '';
    for (let i = 0; i < total; i++) {
      const el = document.createElement('i');
      if (i < idx) el.className = 'done';
      else if (i === idx) el.className = 'current';
      steps.appendChild(el);
    }
  }

  function shortInstruction(text) {
    if (!text) return 'Click here';
    const paras = text.split(/\n\n+/);
    let last = paras[paras.length - 1].trim();
    last = last.split(/(?<=[.!?।])\s/)[0];
    if (last.length > 90) last = last.slice(0, 88) + '…';
    return last;
  }

  // ── TTS ──────────────────────────────────────────────────────────────────
  function speak(text) {
    if (!A11Y.ttsEnabled() || !('speechSynthesis' in window) || !text) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text.replace(/[✅📍🔒🙏📢✍️👉]/g, ''));
      u.lang = LANG_BCP[currentLang] || 'en-IN';
      window.speechSynthesis.speak(u);
    } catch (e) { /* ignore */ }
  }

  // ── Spotlight highlight ───────────────────────────────────────────────────
  function applySpotlight(selector, tipText, opts = {}) {
    const warning = !!opts.warning, subtle = !!opts.subtle, noScroll = !!opts.noScroll;
    const attempt = opts.attempt || 0;
    removeSpotlight();
    if (!selector) return;
    let target = null;
    try { target = document.querySelector(selector); } catch (e) { target = null; }
    if (!target) {
      if (attempt < 6) setTimeout(() => applySpotlight(selector, tipText, Object.assign({}, opts, { attempt: attempt + 1 })), 350);
      return;
    }
    spotlightTarget = target;
    if (!noScroll) target.scrollIntoView({ behavior: 'smooth', block: 'center' });

    const ring = document.createElement('div');
    ring.className = 'civicos-spotlight' + (warning ? ' warning' : '') + (subtle ? ' subtle' : '');
    const tip = document.createElement('div');
    tip.className = 'civicos-tip' + (warning ? ' warning' : '') + (subtle ? ' subtle' : '');
    tip.innerHTML = `<span class="k">${warning ? '🔒' : subtle ? '✍️' : '👉'} ${escapeHtml(tipText || 'Click here')}</span>`;
    uiRoot.appendChild(ring); uiRoot.appendChild(tip);
    spotlightEls = [ring, tip];

    let pointer = null;
    if (!subtle) {
      pointer = document.createElement('div');
      pointer.className = 'civicos-pointer' + (warning ? ' warning' : '');
      pointer.innerHTML = `<svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v13.6l4.3-4.3 1.4 1.4L12 20.4 6.3 13.7l1.4-1.4L12 16.6z"/></svg>`;
      uiRoot.appendChild(pointer); spotlightEls.push(pointer);
    }

    const place = () => {
      if (!spotlightTarget || !document.contains(spotlightTarget)) { removeSpotlight(); return; }
      const r = spotlightTarget.getBoundingClientRect();
      const pad = subtle ? 3 : 6;
      ring.style.left = (r.left - pad) + 'px'; ring.style.top = (r.top - pad) + 'px';
      ring.style.width = (r.width + pad * 2) + 'px'; ring.style.height = (r.height + pad * 2) + 'px';
      const below = r.bottom + 54 < window.innerHeight;
      tip.classList.toggle('below', below); tip.classList.toggle('above', !below);
      tip.style.left = Math.max(8, Math.min(r.left, window.innerWidth - 270)) + 'px';
      tip.style.top = (below ? r.bottom + 12 : r.top - tip.offsetHeight - 12) + 'px';
      if (pointer) {
        pointer.style.left = (r.left + r.width / 2 - 13) + 'px';
        pointer.style.top = Math.max(2, r.top - 32) + 'px';
        pointer.style.display = below ? 'block' : 'none';
      }
    };
    place(); requestAnimationFrame(place);
    repositionBound = place;
    window.addEventListener('scroll', place, { passive: true });
    window.addEventListener('resize', place, { passive: true });
  }
  function removeSpotlight() {
    spotlightEls.forEach(el => el && el.remove());
    spotlightEls = []; spotlightTarget = null;
    if (repositionBound) {
      window.removeEventListener('scroll', repositionBound);
      window.removeEventListener('resize', repositionBound);
      repositionBound = null;
    }
  }

  // ── Auto-continue on navigation ──────────────────────────────────────────
  function triggerAutoStep() {
    if (autoTimer) clearTimeout(autoTimer);
    autoTimer = setTimeout(() => {
      if (!sessionId) return;
      const url = window.location.href;
      if (url === lastAutoUrl) return;
      chrome.storage.session.get([WF_ACTIVE_KEY], (r) => {
        if (!r[WF_ACTIVE_KEY]) return;
        lastAutoUrl = url;
        removeSpotlight();
        const dom = scanDOM();
        const loading = _appendDOM(t('pageChanging'), 'assistant thinking');
        callBackend('/api/v1/step', 'POST', {
          session_id: sessionId, dom_snapshot: dom, user_utterance: '', url: window.location.href, language: currentLang
        }).then((res) => {
          if (loading) loading.remove();
          if (res.success && res.data) {
            if (!panel.classList.contains('active')) panel.classList.add('active');
            handleResponse(res.data);
          }
        });
      });
    }, 1400);
  }

  chrome.runtime.onMessage.addListener((msg) => { if (msg.type === 'PAGE_NAVIGATED') triggerAutoStep(); });
  const spaObserver = new MutationObserver(() => {
    if (window.location.href !== lastUrl) { lastUrl = window.location.href; triggerAutoStep(); }
  });

  // ── DOM scanning ─────────────────────────────────────────────────────────
  const SENSITIVE_RE = /password|passwd|\botp\b|one[\s-]?time|\bpin\b|\bcvv\b|captcha|net[\s-]?banking|netbanking|\bupi\b|credit[\s-]?card|debit[\s-]?card|card[\s-]?number/i;

  function getUniqueSelector(el) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.tagName === 'BODY') return 'body';
    if (el.name) {
      const same = document.querySelectorAll(`${el.tagName.toLowerCase()}[name="${el.name}"]`);
      if (same.length === 1) return `${el.tagName.toLowerCase()}[name="${el.name}"]`;
    }
    const path = [];
    let cur = el;
    while (cur && cur.nodeType === Node.ELEMENT_NODE) {
      let sel = cur.tagName.toLowerCase();
      if (cur.className && typeof cur.className === 'string') {
        const classes = Array.from(cur.classList).filter(c => !c.startsWith('civicos-'));
        if (classes.length) sel += '.' + classes.map(c => CSS.escape(c)).join('.');
      }
      const parent = cur.parentNode;
      if (parent) {
        const sameTag = Array.from(parent.children).filter(s => s.tagName === cur.tagName);
        if (sameTag.length > 1) sel += `:nth-of-type(${sameTag.indexOf(cur) + 1})`;
      }
      path.unshift(sel);
      cur = cur.parentNode;
      if (cur && cur.id) { path.unshift(`#${CSS.escape(cur.id)}`); break; }
    }
    return path.join(' > ');
  }

  function nearestContext(el) {
    let cur = el;
    for (let i = 0; i < 6 && cur; i++) {
      cur = cur.parentElement;
      if (!cur || cur.closest('#civicos-root')) break;
      const cls = (typeof cur.className === 'string' ? cur.className : '');
      if (cur.tagName === 'TR' || cur.tagName === 'LI' ||
        /\b(row|panel|card|box|item|section|tile|service|svc|list-group)\b/i.test(cls)) {
        const tx = (cur.innerText || cur.textContent || '').replace(/\s+/g, ' ').trim();
        if (tx.length >= 8) return tx.slice(0, 320);
      }
    }
    return '';
  }

  function scanDOM() {
    const sel = 'input, button, select, textarea, a, [role="button"], [onclick], [tabindex]';
    const els = Array.from(document.querySelectorAll(sel));
    const out = [];
    let count = 0;
    for (const el of els) {
      if (count >= 160) break;
      if (el.closest && el.closest('#civicos-root')) continue;
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const visible = rect.width > 0 && rect.height > 0 &&
        style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      if (!visible) continue;

      let label = '';
      if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) label = l.innerText.trim(); }
      if (!label && el.closest('label')) label = el.closest('label').innerText.trim();
      if (!label) label = el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') || '';
      if (!label) {
        if (el.tagName === 'INPUT' && (el.type === 'submit' || el.type === 'button')) label = el.value || '';
        else { const tx = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(); if (tx && tx.length <= 100) label = tx; }
      }
      label = (label || '').replace(/\s+/g, ' ').trim().slice(0, 120);

      const href = el.getAttribute('href') || el.getAttribute('onclick') || el.getAttribute('data-href') || '';
      const hay = [el.id, el.name, el.className, el.getAttribute('type'), el.getAttribute('placeholder'), label].join(' ');
      out.push({
        id: el.id || '', tag: el.tagName.toLowerCase(), type: el.getAttribute('type') || '',
        label, placeholder: el.getAttribute('placeholder') || '',
        bbox: { x: Math.round(rect.left), y: Math.round(rect.top), width: Math.round(rect.width), height: Math.round(rect.height) },
        selector: getUniqueSelector(el), sensitive_hint: SENSITIVE_RE.test(hay),
        href: href.slice(0, 200), context: nearestContext(el)
      });
      count++;
    }
    return out;
  }

  // ── Voice recording → WAV ────────────────────────────────────────────────
  function startRecording(micBtn) {
    audioBuffers = [];
    navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
      mediaStream = stream;
      audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      const src = audioContext.createMediaStreamSource(stream);
      scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
      scriptProcessor.onaudioprocess = (e) => { if (isRecording) audioBuffers.push(new Float32Array(e.inputBuffer.getChannelData(0))); };
      src.connect(scriptProcessor); scriptProcessor.connect(audioContext.destination);
      isRecording = true; micBtn.classList.add('recording');
    }).catch(() => appendMessage(t('micDenied'), 'warning'));
  }
  function stopRecording(micBtn, done) {
    if (!isRecording) return;
    isRecording = false; micBtn.classList.remove('recording');
    if (scriptProcessor) { scriptProcessor.disconnect(); scriptProcessor = null; }
    if (mediaStream) { mediaStream.getTracks().forEach(tk => tk.stop()); mediaStream = null; }
    if (audioContext) { audioContext.close(); audioContext = null; }
    let len = 0; audioBuffers.forEach(b => len += b.length);
    const merged = new Float32Array(len); let off = 0;
    audioBuffers.forEach(b => { merged.set(b, off); off += b.length; });
    done(arrayBufferToBase64(encodeWAV(merged, 16000)));
  }
  function encodeWAV(samples, rate) {
    const buf = new ArrayBuffer(44 + samples.length * 2); const v = new DataView(buf);
    const ws = (o, s2) => { for (let i = 0; i < s2.length; i++) v.setUint8(o + i, s2.charCodeAt(i)); };
    ws(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); ws(8, 'WAVE'); ws(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    ws(36, 'data'); v.setUint32(40, samples.length * 2, true);
    let o = 44; for (let i = 0; i < samples.length; i++, o += 2) { const s2 = Math.max(-1, Math.min(1, samples[i])); v.setInt16(o, s2 < 0 ? s2 * 0x8000 : s2 * 0x7FFF, true); }
    return buf;
  }
  function arrayBufferToBase64(buffer) {
    let bin = ''; const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
    return window.btoa(bin);
  }

  // ── Utils ────────────────────────────────────────────────────────────────
  function escapeHtml(s) { return (s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  function escapeAttr(s) { return escapeHtml(s).replace(/"/g, '&quot;'); }

  // ── Bootstrap ────────────────────────────────────────────────────────────
  function boot() {
    injectUI();
    if (document.body) spaObserver.observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
