# CivicOS AI — Telangana ePASS Assistant

A **Chrome & Firefox** extension + local FastAPI backend that guides students **step-by-step**
through the **Telangana ePASS scholarship portal** (`telanganaepass.cgg.gov.in`).

You type what you need (e.g. *"help me check my scholarship status"*) and the
assistant **dims the page and highlights the one button to click**. You click it,
the page changes, and it **automatically highlights the next button** — all the way
to the end. Password / OTP / payment steps are never auto-clicked; they're handed
back to you with a clear warning.

> The agent appears **only** on the Telangana ePASS site (and the bundled local
> demo). It does not run on any other government portal.

---

## What it does

- **Guided navigation** for 9 ePASS services (from `E-Pass Services.txt`):
  Post-Matric Fresh / Renewal / Status / Print, Pre-Matric Fresh / Renewal / Print /
  Renewal-Print, and Aadhaar Seeding (NPCI, narrated).
- **Spotlight highlighting** — the page dims and one button glows with a tooltip
  telling you what to do; the highlight moves to the next button as you progress.
- **Step progress** — a "Step 2 of 4" bar tracks where you are in the flow.
- **Safety gate** — OTP / password / payment fields are flagged and never touched.
- **Voice input** (optional, local Whisper) and spoken guidance (browser TTS).
- **Smart understanding** — Claude → local Ollama → offline keyword matching, chosen
  automatically. The step highlighting is deterministic, so it works with no model.
- **Accessibility panel** (UPSC-style) — open it from the ♿ icon in the header:
  text size, spacing, line height, ADHD reading mask, saturation, light/dark, invert,
  highlight links, text-to-speech, big cursor, pause animations, hide images. Every
  option works live and persists across sessions.
- **Multilingual** — a language selector (🌐) switches the whole assistant + chat
  responses to English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, Gujarati,
  Bengali, Punjabi or Odia. Translation is Google-Translate-backed (no API key), cached,
  and keeps on-screen button names in English so instructions still match the portal.
  Adding a language later = one row in `services/translator.py:LANGUAGES`.

## Architecture

```
Chrome extension (telanganaepass.cgg.gov.in + localhost)
  content.js  ── scans the page, draws the spotlight, walks the steps
  background.js ─ relays to backend, detects navigations
        │  HTTP → 127.0.0.1:8000
        ▼
FastAPI backend
  orchestrator.py  ─ deterministic step-by-step navigator (the core)
  agents/planner   ─ optional LLM: intent disambiguation + Q&A
  agents/safety    ─ OTP/password/payment gate
  services/llm_client ─ Claude → Ollama → none (auto)
  services/rag_service ─ optional local RAG (FAISS + MiniLM)
  workflows/*.json ─ one file per ePASS service
  demo_pages.py    ─ a local stand-in ePASS portal for rehearsal
```

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv           # or use the repo .venv
.venv\Scripts\activate         # Windows  (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Health check: <http://127.0.0.1:8000/api/v1/health>

### 2. Choose the AI model (optional — it runs without one)

Resolution is automatic (`LLM_PROVIDER=auto`):

| You set…                        | Provider used              |
|---------------------------------|----------------------------|
| `ANTHROPIC_API_KEY=sk-ant-…`    | Anthropic Claude (cloud)   |
| Ollama running + a model pulled | Local Ollama (private)     |
| nothing                         | Deterministic keyword match |

```bash
# Claude (smartest):
set ANTHROPIC_API_KEY=sk-ant-...        # optional: set ANTHROPIC_MODEL=claude-sonnet-5
# or local Ollama:
ollama pull qwen2.5:3b
```

### 3. Load the extension

The **same `extension/` folder** runs on both Chrome/Edge and Firefox (Manifest V3).

**Chrome / Edge**

1. Open `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → select the `extension/` folder.
3. Open **telanganaepass.cgg.gov.in** (or the demo below) and click the floating
   robot button, or the toolbar icon → *Open Assistant Panel*.

> Chrome logs a harmless warning, *"Unrecognized manifest key 'background.scripts'"* —
> that key is read only by Firefox and ignored by Chrome; the extension still works.

**Firefox**

1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on…** and select `extension/manifest.json`.
   (A temporary add-on stays loaded until you restart Firefox.)
3. Open the ePASS site (or the demo below) and use the assistant the same way.

> Developers can instead run `npx web-ext run --source-dir extension` to launch a
> fresh Firefox profile with the add-on auto-loaded and hot-reloaded on save.
> Backend communication targets `http://127.0.0.1:8000` on both browsers, so start
> the backend first (Section 1).

## Try it without the real site (local demo)

With the backend running, open the bundled stand-in portal:

```
http://127.0.0.1:8000/demo
```

Then in the panel type **"help me check my scholarship status"** and follow the
highlights: Home → Post Matric → Know your Application Status → fill form → Status.

## Tests

```bash
cd backend
..\.venv\Scripts\python.exe test_navigator.py          # offline navigator flow
..\.venv\Scripts\python.exe tests\test_rag_fallback.py # intent + safety units
..\.venv\Scripts\python.exe test_rag.py                # live smoke (backend running)
```

## Adding a new service

Drop a JSON file into `backend/workflows/` (copy an existing one), listing the
ordered `steps` with `target_hint` keywords and `narration`, plus `match_keywords`
for intent routing. Restart the backend — no code changes needed.
