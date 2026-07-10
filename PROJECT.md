# CivicOS AI — Software Requirements Specification & Technical Design Document

**Document Version:** 1.0 | **Classification:** Internal Engineering Blueprint | **Status:** Build-Ready

This document is the single source of truth for building CivicOS AI end-to-end within a 24-hour hackathon window while remaining production-extensible, using only free and open-source components verified as currently available. [paddleocr](https://www.paddleocr.ai/latest/en/quick_start.html)

***

## 1. Executive Summary

CivicOS AI is a Chrome Extension with an optional local desktop companion service that acts as a multi-agent AI copilot for navigating Indian government portals (EPFO, Passport Seva, DigiLocker, PAN, Aadhaar, Income Tax e-filing, National Scholarship Portal). It combines DOM inspection, OCR-based vision fallback, local LLM reasoning (Qwen, quantized GGUF), voice interaction (Whisper), and a persistent memory layer (FAISS + SQLite) to guide users step-by-step through complex bureaucratic workflows while enforcing a hard safety boundary: the system never autonomously submits passwords, OTPs, digital signatures, or final form submissions.

The system is composed of six cooperating agents — Planner, Browser, Vision, Memory, Voice, Safety — orchestrated through a FastAPI backend that the Chrome Extension communicates with over a local WebSocket/HTTP bridge. The architecture is designed so that a coding agent (Cursor, Claude Code, Copilot Agent, Antigravity) can implement each module independently against the interfaces defined in this document without needing further product clarification.

## 2. Problem Statement

Indian citizens frequently abandon or mishandle government portal workflows (passport renewal, EPF withdrawal, DigiLocker document fetch) due to inconsistent UI/UX, dense bureaucratic terminology, and lack of multilingual guidance. Existing chatbots on these portals are scripted FAQ bots that do not observe the live page state or physically assist navigation. CivicOS AI addresses this gap by embedding an AI agent directly into the browsing session that reads the actual DOM/pixels of the page the user is on and provides grounded, real-time, spoken guidance in the user's preferred language, while refusing to touch sensitive credential or submission actions.

## 3. Target Users

- First-time or infrequent users of government e-services who find forms confusing (rural, elderly, non-English-fluent users).
- Regional-language speakers (Telugu, Hindi) who struggle with English-only government interfaces.
- Users with mild visual/technical impairment who benefit from spoken step-by-step guidance and highlighted UI elements.
- Power users who want faster, guided completion of repetitive bureaucratic tasks (students applying for scholarships, employees checking EPFO balance).

## 4. User Personas

| Persona | Age/Background | Goal | Pain Point |
|---|---|---|---|
| Ramesh, factory worker | 45, Telugu-speaking, limited English | Withdraw EPF after job change | Cannot understand English form labels |
| Priya, college student | 20, Hindi/English bilingual | Apply for a national scholarship | Confused by multi-step document upload UI |
| Suresh, retiree | 62, low tech literacy | Renew passport | Afraid of making an irreversible mistake on submit |
| Anjali, working professional | 30, tech-comfortable | File income tax return quickly | Wants faster field-by-field guidance, not full explanation |

## 5. Goals

- Provide grounded, page-aware, step-by-step navigation assistance on real Indian government websites.
- Support multilingual voice guidance in Telugu, Hindi, and English.
- Maintain persistent memory of in-progress workflows across sessions.
- Guarantee zero autonomous handling of credentials, OTPs, signatures, payments, or submit actions.
- Run the majority of AI computation locally to minimize cost and preserve privacy.
- Be demoable end-to-end within a 24-hour hackathon on a single laptop.

## 6. Non-Goals

- CivicOS AI will not auto-fill or auto-submit any government form field that carries legal consequence without explicit per-field user confirmation.
- It will not attempt to bypass CAPTCHA, 2FA, or bot-detection mechanisms.
- It will not store Aadhaar, PAN, or biometric data in plaintext, nor transmit such data to any external cloud service by default.
- It will not support non-Indian government portals in v1.
- It will not include a native Android app in the hackathon MVP (documented as future work only).

## 7. Complete Functional Requirements

**FR1 — Conversational Intent Capture:** The system accepts natural-language text or voice input ("Help me renew my passport") and maps it to a known Workflow Definition via the Planner Agent.

**FR2 — Live Page Understanding:** The Browser Agent extracts the current page's DOM tree (via content script) and passes a structured representation (interactive elements, form fields, labels, buttons) to the Planner Agent on every navigation or significant DOM mutation.

**FR3 — Vision Fallback:** When DOM extraction confidence is below threshold (canvas-rendered UI, image-only buttons, obscured labels), the Vision Agent captures a screenshot, runs PaddleOCR text detection/recognition and OpenCV template/contour matching to identify actionable elements. [tenorshare](https://www.tenorshare.com/ocr/paddleocr.html)

**FR4 — Step Guidance Generation:** The Planner Agent, using the local Qwen LLM, generates the next micro-instruction ("Click the 'Continue' button in the top-right of the form") and passes it to the Browser Agent for on-page highlighting and to the Voice Agent for spoken narration.

**FR5 — Element Highlighting:** The content script draws a non-intrusive visual overlay (colored border + pulsing animation) around the target DOM element identified by the Planner Agent.

**FR6 — Field Explanation:** On user request or hover, the system explains the purpose of a given form field in plain language and in the selected language.

**FR7 — Page Change Detection:** The system detects SPA route changes (History API) and full navigations (via `webNavigation` API) and re-triggers DOM analysis automatically.

**FR8 — Multilingual Voice I/O:** Voice input is transcribed locally via Whisper (or faster-whisper); voice output uses a local or browser-native TTS engine (Web Speech API as free fallback, Coqui TTS optional). [kx.cloudingenium](https://kx.cloudingenium.com/en/whisper-self-hosted-speech-to-text-transcription-local/)

**FR9 — Persistent Workflow Memory:** The Memory Agent stores workflow progress (current step index, extracted non-sensitive field values, timestamps) in SQLite, and stores semantic conversation history embeddings in FAISS for context retrieval across sessions.

**FR10 — Safety Gate:** Before any DOM `click()`/`fill()` action targeting a field classified as sensitive (password, OTP, signature, payment, submit), the Safety Agent intercepts the action and requires an explicit user confirmation click on an in-overlay "Confirm" button.

**FR11 — Workflow Library:** The system ships with three pre-built Workflow Definitions: Passport Renewal, EPFO Withdrawal, DigiLocker Document Fetch, each expressed in a declarative JSON/YAML schema (Section 89).

**FR12 — Session Resume:** If the user closes the browser mid-workflow and reopens the target site later, the extension detects the matching URL/domain and offers to resume from the last recorded step.

**FR13 — Audit Log:** Every agent decision (DOM element chosen, confidence score, OCR fallback triggered, safety gate invoked) is logged locally in a structured JSON log file for debuggability and hackathon demo transparency.

## 8. Complete Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | Planner Agent response latency under 3 seconds per step on a mid-range laptop (8GB VRAM or CPU-only with quantized Qwen) |
| Privacy | No sensitive field values (Aadhaar, PAN, password, OTP) ever leave the local machine or are persisted to disk |
| Reliability | System must degrade gracefully to a "manual mode" (highlighting only, no LLM narration) if local LLM inference fails or times out |
| Portability | Backend runs identically on Windows, macOS, Linux via Python 3.11+ venv, no OS-specific code paths |
| Security | All local backend endpoints bound to 127.0.0.1 only; no external network exposure by default |
| Usability | Voice narration and overlay text must both be available simultaneously (dual-modality accessibility) |
| Extensibility | New government workflows addable via JSON config without code changes (plugin-style, Section 90) |
| Offline Capability | OCR, voice transcription, LLM reasoning, and memory retrieval must function with zero internet connectivity; only the target government page fetch requires internet |

## 9. User Stories

- As Ramesh, I want the AI to speak instructions in Telugu so that I understand what each form field means without reading English.
- As Priya, I want the AI to remember which step I left off at so that I don't have to restart the scholarship form from scratch.
- As Suresh, I want the AI to never submit anything without asking me first so that I don't accidentally file an irreversible application.
- As Anjali, I want the AI to highlight exactly which button to click so that I complete tax filing faster than reading the portal myself.

## 10. Acceptance Criteria

- Given a user says "help me renew my passport," the system correctly loads the Passport Renewal Workflow Definition and opens (or detects) the Passport Seva portal within 5 seconds.
- Given the DOM contains a submit button, the Safety Agent must block the auto-click and render a confirmation prompt 100% of the time in testing.
- Given the user speaks in Telugu, the Voice Agent must transcribe with Whisper and respond in Telugu TTS without requiring a language toggle.
- Given the browser tab navigates to a new URL within the same domain, the system must re-run DOM analysis within 2 seconds without requiring the user to re-issue their request.
- Given OCR fallback is triggered, PaddleOCR must return recognized text regions with bounding boxes usable for click-target mapping. [paddleocr](https://www.paddleocr.ai/latest/en/quick_start.html)

## 11. End-to-End User Journey

1. User installs the CivicOS Chrome Extension and (optionally) starts the local desktop companion (FastAPI backend + Qwen model server).
2. User clicks the extension icon, opening the Overlay Chat UI, and types or speaks "Help me renew my passport."
3. The extension sends the intent to the local backend; the Planner Agent matches it to the Passport Renewal Workflow Definition and returns the first step.
4. The Browser Agent (content script) captures the current DOM, if the user is not already on the Passport Seva portal, the Planner instructs the user (or auto-opens a new tab) to navigate there.
5. The extension highlights the "Login/Register" area and narrates instructions via Voice Agent.
6. The user proceeds field by field; the Memory Agent checkpoints progress after each completed step.
7. When the workflow reaches a sensitive action (login submission, OTP entry, final application submission), the Safety Agent halts automation and requires explicit manual confirmation click from the user.
8. Upon workflow completion or user exit, the Memory Agent persists final state to SQLite for potential resume in a future session.

## 12. Example Workflows

### 12.1 Passport Renewal Workflow

Steps: navigate to Passport Seva portal → login/register (manual, safety-gated) → click "Apply for Fresh Passport/Reissue" → fill personal details form (AI explains each field, does not auto-fill identity numbers) → upload documents (AI explains required document types) → schedule appointment (AI highlights calendar widget) → review page (AI reads back summary via TTS) → payment and final submit (fully safety-gated, manual only).

### 12.2 EPFO Withdrawal Workflow

Steps: navigate to EPFO Member e-Sewa portal → login via UAN (safety-gated credential entry) → navigate to "Online Services" → select "Claim (Form-31, 19, 10C & 10D)" → verify KYC details displayed (AI reads them aloud, flags mismatches) → select claim type (AI explains eligibility differences between Form 19/10C) → enter bank details section (safety-gated) → OTP verification (safety-gated) → submit claim (safety-gated).

### 12.3 DigiLocker Document Fetch Workflow

Steps: navigate to DigiLocker → login via Aadhaar/mobile OTP (safety-gated) → navigate to "Issued Documents" → AI identifies and highlights the requested document type (e.g., "Driving License") using DOM text matching with OCR fallback for icon-only tiles → click "Download"/"Share" per user's explicit instruction → confirm download location.

## 13–17. System Architecture, Component Diagram, Sequence Diagram, Data Flow, Request Flow

### 13. Complete System Architecture

CivicOS AI uses a three-tier local architecture: (1) Chrome Extension (UI + DOM sensing layer), (2) FastAPI Local Backend (agent orchestration + LLM/OCR/voice inference), (3) Local Storage Layer (SQLite + FAISS + JSON configs). All communication between the extension and backend occurs over `localhost` via HTTP for request/response calls and WebSocket for streaming step-by-step guidance and voice audio chunks.

```
[Chrome Extension]
   Content Script  <---DOM/Mutation Events---  Web Page (Government Portal)
   Background SW   <---chrome.runtime messaging---  Content Script
   Overlay UI (React/vanilla JS injected iframe)
        |
        | WebSocket (ws://127.0.0.1:8765) + HTTP (http://127.0.0.1:8000)
        v
[FastAPI Backend]
   Orchestrator ---> Planner Agent ---> (Qwen LLM local inference)
                 ---> Browser Agent ---> (Playwright, optional headful mirror session)
                 ---> Vision Agent  ---> (OpenCV + PaddleOCR)
                 ---> Memory Agent  ---> (SQLite + FAISS)
                 ---> Voice Agent   ---> (Whisper STT + TTS)
                 ---> Safety Agent  ---> (Rule engine, intercepts all agents)
        |
        v
[Local Storage]
   civicos.db (SQLite)  |  faiss_index/  |  workflows/*.json  |  logs/*.jsonl
```

### 14. Component Diagram (Textual)

- **Extension Layer:** manifest.json, background.js (service worker), content.js, overlay.js, popup.html/js.
- **Backend Layer:** `main.py` (FastAPI app), `orchestrator.py`, `agents/planner.py`, `agents/browser.py`, `agents/vision.py`, `agents/memory.py`, `agents/voice.py`, `agents/safety.py`.
- **Model Layer:** local Qwen GGUF served via llama.cpp server or Ollama; Whisper via whisper.cpp or faster-whisper. [kx.cloudingenium](https://kx.cloudingenium.com/en/whisper-self-hosted-speech-to-text-transcription-local/)
- **Data Layer:** SQLite file, FAISS index directory, JSON workflow definitions, JSONL audit logs.

### 15. Sequence Diagram — Single Step Execution (Textual)

1. User → Overlay UI: "Next step" (voice/text).
2. Overlay UI → Background SW: `postMessage({type:"USER_INTENT", payload})`.
3. Background SW → FastAPI `/api/v1/step`: HTTP POST with DOM snapshot + intent.
4. FastAPI Orchestrator → Safety Agent: pre-check DOM snapshot for sensitive fields.
5. Orchestrator → Planner Agent: request next action given DOM + workflow state.
6. Planner Agent → Qwen LLM: prompt with DOM summary + workflow step definition.
7. Qwen LLM → Planner Agent: structured JSON action (e.g., `{"action":"highlight","selector":"#applyBtn","narration":"Click Apply for Fresh Passport"}`).
8. Planner Agent → Safety Agent: validate action is not in restricted category.
9. Safety Agent → Orchestrator: approved / requires_confirmation.
10. Orchestrator → FastAPI response → Background SW → Content Script: render highlight + trigger Voice Agent TTS.
11. Memory Agent (async): persist step completion to SQLite.

### 16. Data Flow Diagram (Textual)

`Raw DOM HTML` → [Content Script Extraction] → `Structured Element JSON` → [Backend Ingestion] → `Vision Fallback (if low confidence)` → `Screenshot` → [PaddleOCR + OpenCV] → `OCR Text Regions + BBoxes` → [Planner Agent Fusion] → `Unified Page Representation` → [Qwen LLM Reasoning] → `Next Action JSON` → [Safety Agent Filter] → `Approved Action` → [Content Script Renderer] → `Visual Highlight + Voice Narration`.

### 17. Request Flow (API Level)

Every user turn triggers exactly one `POST /api/v1/step` call carrying `{session_id, workflow_id, dom_snapshot, screenshot_base64 (optional), user_utterance, language}`, and receives one `StepResponse` (Section 40). Streaming voice audio uses a separate WebSocket channel `ws://127.0.0.1:8765/voice` to avoid blocking the primary JSON request cycle.

## 18–35. Browser Extension Architecture

### 18. Browser Extension Architecture Overview

The extension operates in three isolated JavaScript contexts per Chrome's Manifest V3 security model: the background service worker (event orchestration, no DOM access), content scripts (DOM access, no direct network calls to arbitrary hosts without host permissions), and the popup/overlay UI (isolated rendering context). Communication between contexts uses `chrome.runtime.sendMessage`/`onMessage` exclusively; no context directly shares a JS heap with another. [developer.chrome](https://developer.chrome.com/docs/extensions/develop/migrate/improve-security)

### 19. Chrome Extension Manifest Design

Use Manifest V3 (mandatory as of 2026; V2 extensions are being deprecated). Required fields: `manifest_version: 3`, `permissions: ["activeTab", "scripting", "storage", "webNavigation", "tabs"]`, `host_permissions` scoped explicitly to the six government domains (epfindia.gov.in, passportindia.gov.in, digilocker.gov.in, incometax.gov.in, tin.tin.nsdl.com, scholarships.gov.in) rather than `<all_urls>`, to minimize the review/security footprint. Define `background.service_worker`, `content_scripts` with `matches` restricted to the same domain list and `run_at: document_idle`, and an `action` (toolbar icon) with a `default_popup`. [developer.chrome](https://developer.chrome.com/docs/extensions/develop/migrate/improve-security)

### 20. Background Service Worker Design

The service worker is event-driven and stateless between invocations (Manifest V3 workers can be terminated at any time). Its responsibilities: relay messages between content script and local backend (fetch calls to `localhost:8000`), manage the WebSocket connection to the voice streaming endpoint, track active tab ID and workflow session ID in `chrome.storage.session` (survives worker restarts within a browser session), and listen to `chrome.webNavigation.onHistoryStateUpdated` and `onCompleted` events to detect page changes and notify the content script to re-extract DOM. [developer.chrome](https://developer.chrome.com/docs/extensions/develop/migrate/known-issues)

### 21. Content Script Design

The content script is injected into every matched government domain page and performs: DOM tree extraction (Section 23), MutationObserver registration (Section 30), overlay element injection into the page's shadow DOM (to avoid CSS collision, Section 32), and forwarding user click/hover events relevant to guidance (e.g., hover-to-explain). It never performs the actual `click()`/`fill()` of sensitive fields itself — those require the safety confirmation round-trip.

### 22. Overlay Chat UI Design

The overlay is rendered inside a `<div>` attached to a closed Shadow DOM root injected at the end of `<body>`, ensuring the host page's CSS cannot override it and vice versa. It contains: a draggable chat panel (collapsed to a floating icon by default), a text input, a microphone button (triggers Voice Agent), and a language selector (Telugu/Hindi/English). The panel communicates with the content script via custom DOM events (`CustomEvent`) rather than direct function calls, preserving the isolation boundary.

### 23. DOM Reading Strategy

On each analysis trigger, the content script walks the DOM using `document.querySelectorAll` targeting interactive elements: `input, button, select, textarea, a[role=button], [onclick], [tabindex]`. For each element, extract: tag name, `id`, `name`, `type`, `placeholder`, associated `<label>` text (via `for` attribute or nearest ancestor text), `aria-label`, visible bounding rect (`getBoundingClientRect`), and computed visibility (`offsetParent !== null` and non-zero dimensions).

### 24. DOM Parsing Strategy

Extracted elements are serialized into a compact JSON array capped at 150 elements per page (prioritized by visibility/viewport proximity) to keep LLM context small. Each entry: `{id, tag, type, label, placeholder, bbox:[x,y,w,h], visible:true, sensitive_hint:boolean}`. The `sensitive_hint` flag is pre-computed client-side using keyword matching (Section 62) before ever reaching the LLM, so the Safety Agent has redundant client + server-side gating.

### 25. Button Detection Strategy

Buttons are identified via `<button>`, `<input type="submit">`, `<a>` with button-like ARIA roles, and elements with `cursor:pointer` computed style plus click handlers. Each candidate button's visible text (or `aria-label`/`title` fallback, or OCR text if image-only) is used as the primary semantic signal for the Planner Agent's button-matching prompt.

### 26. Form Detection Strategy

Forms are identified by traversing `<form>` elements and, for framework-rendered forms without a semantic `<form>` tag (common in React/Angular government portals), grouping input clusters within a shared container `<div>` with a heading or fieldset-like text within 100px above the cluster, using a heuristic proximity grouping algorithm.

### 27. Field Detection Strategy

Each field's semantic type is inferred through a priority-ordered cascade: (1) explicit `type` attribute, (2) `name`/`id` keyword match against a dictionary (e.g., `aadhaar`, `otp`, `pan`, `password`, `dob`, `mobile`), (3) associated label text keyword match, (4) LLM classification as last resort for ambiguous fields. This classification directly feeds the Safety Agent's sensitivity rules (Section 62).

### 28. Dynamic Page Change Detection

Two detection layers run concurrently: MutationObserver for in-page DOM changes (Section 30) and the background service worker's `webNavigation` listeners for full/SPA navigations (Section 29). A debounce window of 500ms coalesces rapid successive mutations (common during page load) before triggering re-analysis, to avoid redundant backend calls.

### 29. URL Change Detection

The background service worker registers `chrome.webNavigation.onHistoryStateUpdated` (for `pushState`/`replaceState` SPA transitions) and `chrome.webNavigation.onCompleted` (for full page loads), both filtered to the extension's monitored domains. On trigger, it sends a `URL_CHANGED` message to the content script, which resets its cached DOM snapshot and re-initiates extraction.

### 30. MutationObserver Strategy

A single `MutationObserver` is attached to `document.body` with `{childList: true, subtree: true, attributes: true, attributeFilter: ['style','class','disabled']}`. Mutation callbacks are throttled via `requestIdleCallback` (falling back to `setTimeout` at 500ms) to avoid performance degradation on highly dynamic government portal pages.

### 31. Highlighting Strategy

Highlighting is implemented by injecting an absolutely-positioned `<div>` overlay (in the Shadow DOM host, but positioned using the target element's `getBoundingClientRect()` translated to page coordinates) with a pulsing CSS `box-shadow` animation, recalculated on scroll/resize via a `ResizeObserver` + `scroll` event listener to keep alignment accurate.

### 32. Overlay Rendering Strategy

All CivicOS UI elements (chat panel, highlights, tooltips) render inside one closed Shadow DOM root to guarantee style isolation from the host government site's CSS and vice versa, preventing both visual conflicts and potential CSS-based fingerprinting/interference.

### 33. Tooltip Strategy

Field explanation tooltips appear on hover (desktop) or tap-and-hold (touch) over a highlighted field, rendered as a small callout anchored to the field's bounding box with a max-width of 280px, auto-flipping position (top/bottom) based on available viewport space.

### 34. Auto-Scroll Strategy

When the Planner Agent targets an element outside the current viewport, the content script calls `element.scrollIntoView({behavior:'smooth', block:'center'})` before rendering the highlight overlay, with a 300ms delay to let scroll settle before positioning the highlight box.

### 35. Browser Safety Rules

The content script never programmatically calls `.click()`, `.submit()`, or sets `.value` on any element without first receiving an explicit "approved" flag from the Safety Agent's response, and even then, only for non-sensitive elements (Section 62–67); sensitive-field interactions are always rendered as a highlight + instruction only, never executed by the extension itself.

## 36–44. FastAPI Backend Architecture

### 36. FastAPI Backend Architecture

The backend is a single FastAPI application (`main.py`) mounting sub-routers per agent domain, run via `uvicorn` bound to `127.0.0.1:8000`, using `async def` endpoints throughout to allow concurrent OCR/LLM/voice processing without blocking the event loop. Long-running inference calls (LLM generation, OCR) are offloaded to a `ThreadPoolExecutor` or run as async-compatible calls if the underlying library supports it.

### 37–39. API Design, Endpoints, Request Schemas

| Endpoint | Method | Purpose | Key Request Fields |
|---|---|---|---|
| `/api/v1/session/start` | POST | Initialize a new workflow session | `user_id, workflow_id, language` |
| `/api/v1/step` | POST | Get next guidance action | `session_id, dom_snapshot, screenshot_b64?, user_utterance?` |
| `/api/v1/voice/transcribe` | POST | Convert audio to text | `session_id, audio_b64, language_hint` |
| `/api/v1/voice/speak` | POST | Convert text to speech | `session_id, text, language` |
| `/api/v1/vision/analyze` | POST | OCR + CV fallback analysis | `session_id, screenshot_b64` |
| `/api/v1/safety/check` | POST | Explicit sensitivity check on a field | `session_id, field_meta` |
| `/api/v1/memory/checkpoint` | POST | Save workflow progress | `session_id, step_id, non_sensitive_state` |
| `/api/v1/memory/resume` | GET | Fetch last saved state for a domain | `user_id, domain` |
| `/api/v1/workflows` | GET | List available workflow definitions | — |
| `/ws/voice` | WebSocket | Streaming audio in/out | binary audio frames |

### 40. Response Schemas

`StepResponse`: `{session_id, action: "highlight"|"explain"|"confirm_required"|"complete", target_selector, narration_text, narration_audio_url?, confidence_score, requires_user_confirmation: bool, next_step_id}`. All responses include `confidence_score` (0.0–1.0) so the extension can visually indicate uncertainty to the user.

### 41. JSON Message Formats

Extension-to-background and background-to-content messages use a consistent envelope: `{type: string, session_id: string, payload: object, timestamp: ISO8601}`, enabling consistent logging and easier debugging correlation between browser-side and server-side logs.

### 42. Error Response Formats

All API errors follow FastAPI's standard `HTTPException` JSON shape extended with an internal error code: `{"detail": "human readable message", "error_code": "PLANNER_TIMEOUT"|"OCR_FAILED"|"SAFETY_VIOLATION_ATTEMPT"|"WORKFLOW_NOT_FOUND", "session_id": "..."}`, with HTTP status codes 400 (bad input), 404 (workflow/session not found), 422 (validation), 500 (internal), 503 (model unavailable).

### 43. Agent Communication Protocol

Agents communicate internally via a simple in-process message bus (a Python `asyncio.Queue` per agent, orchestrated by `orchestrator.py`) rather than a heavyweight message broker, appropriate for a single-process hackathon deployment. Each agent implements a common interface: `async def handle(self, event: AgentEvent) -> AgentEvent`.

### 44. Internal Event Flow

`AgentEvent` objects carry `{event_type, session_id, payload, source_agent, timestamp}`. The Orchestrator routes events in this fixed pipeline order for a step request: `Safety.pre_check → Vision.analyze (conditional) → Planner.decide → Safety.post_check → Memory.checkpoint (async, fire-and-forget) → response assembly`.

## 45–54. Agent Designs

### 45. Planner Agent Design

The Planner Agent is the central reasoning unit. Input: current workflow definition, current step pointer, fused DOM+OCR page representation, user utterance (if any), and conversation memory context retrieved from FAISS. It constructs a structured prompt (Section 80) sent to the local Qwen model and parses a strict JSON action schema from the response, validating it against a Pydantic model before passing downstream; malformed LLM output triggers one automatic retry with a stricter "JSON-only" reminder prompt before falling back to a rule-based default action.

### 46. Browser Agent Design

The Browser Agent has two operating modes: (a) **Passive Mode** — it only receives DOM snapshots pushed by the content script and never touches the live browser tab (default, hackathon-safe mode); (b) **Active Mode** — it optionally drives a separate Playwright-controlled Chromium instance for demo automation of non-sensitive steps (e.g., auto-navigating to the correct URL, auto-scrolling), used only for actions explicitly whitelisted as safe (Section 67). Active Mode requires the desktop companion process and is disabled by default in the pure-extension deployment.

### 47. Vision Agent Design

Triggered when DOM confidence score (computed from proportion of elements with meaningful labels/aria-attributes) falls below 0.6. The Vision Agent receives a base64 screenshot, runs OpenCV preprocessing (grayscale, adaptive thresholding, denoising) followed by PaddleOCR's PP-OCRv5 detection + recognition pipeline to extract text regions with bounding boxes and confidence scores, then fuses OCR bounding boxes with the nearest DOM elements by spatial proximity to resolve final clickable targets. [tenorshare](https://www.tenorshare.com/ocr/paddleocr.html)

### 48. Memory Agent Design

Two memory tiers: **Structured Memory** (SQLite) for workflow state, step completion timestamps, and session metadata; **Semantic Memory** (FAISS) for embedding-based retrieval of past conversation turns and explanations, using a local sentence-embedding model (e.g., `all-MiniLM-L6-v2` via `sentence-transformers`, CPU-friendly and free) to embed and index each conversational turn, retrieved top-k=3 for context injection into Planner prompts.

### 49. Safety Agent Design

The Safety Agent is a rule-first, LLM-second gate. It maintains a static keyword/regex blocklist (Section 62–67) checked against field metadata before any action is approved; only if the static check is ambiguous does it consult the LLM for a secondary classification, and any LLM-flagged "uncertain" case defaults to the safe (blocked/confirm-required) path. This agent's decision always overrides the Planner Agent's proposed action.

### 50. Voice Agent Design

Speech-to-text uses Whisper (via `faster-whisper` for better CPU throughput) with the `base` or `small` multilingual model, chosen for its balance of the ~5.7% English WER and support for Telugu/Hindi in reasonable size (142MB–466MB). Text-to-speech uses the browser-native Web Speech Synthesis API (zero-cost, zero-install, supports Hindi and has partial Telugu support in Chrome) as the primary path, with an optional local Coqui TTS fallback for higher-quality regional voices if GPU time allows during the hackathon. [codersera](https://codersera.com/blog/faster-whisper-vs-whisper-cpp-speech-to-text-2026/)

### 51–52. Agent Responsibilities and Communication

Each agent exposes exactly one public async method (`handle`) and communicates only through the Orchestrator, never directly with another agent's internals, enforcing a strict single-responsibility boundary that a coding agent can implement and test in isolation.

### 53. Agent Lifecycle

Agents are instantiated once at FastAPI application startup (`@app.on_event("startup")`) as singletons holding loaded models (Qwen, Whisper, PaddleOCR, FAISS index) in memory to avoid reload latency per request, and are gracefully released on shutdown (`@app.on_event("shutdown")`).

### 54. Agent State Machine

Each workflow session moves through states: `INIT → ANALYZING → AWAITING_USER_ACTION → CONFIRM_REQUIRED → STEP_COMPLETE → (loop) → WORKFLOW_COMPLETE | ABANDONED`. The Safety Agent can force any state into `CONFIRM_REQUIRED` regardless of the Planner's proposed transition.

## 55–67. Memory, Privacy, Security, Sensitive Data Rules

### 55–57. Memory Design, SQLite Schema, JSON Storage

**SQLite Schema:**

```
sessions(id TEXT PK, user_id TEXT, workflow_id TEXT, domain TEXT, status TEXT, created_at TEXT, updated_at TEXT)
workflow_steps(id TEXT PK, session_id TEXT FK, step_index INTEGER, step_name TEXT, status TEXT, completed_at TEXT)
audit_log(id INTEGER PK AUTOINCREMENT, session_id TEXT, event_type TEXT, payload_json TEXT, timestamp TEXT)
```

No table contains a column for password, OTP, Aadhaar number, PAN number, or any field flagged `sensitive_hint=true`; these are structurally excluded at the ORM/insertion layer, not just by convention. FAISS indices are stored per-user as `faiss_index/{user_id}.index` alongside a parallel JSON metadata file mapping vector IDs to conversation text snippets.

### 58–59. Session Management, Workflow Persistence

Sessions are identified by a UUID generated at `/session/start` and stored in `chrome.storage.session` on the extension side (cleared when the browser closes, unless the user opts into "remember across restarts," which then uses `chrome.storage.local`). Workflow persistence allows resume by matching `(user_id, domain)` pairs on next visit, prompting "Resume your Passport application from Step 4?".

### 60–67. Privacy, Security, Sensitive Data, Password, OTP, Payment, Signature, Submit Rules

These rules form the non-negotiable safety core of CivicOS AI:

- **Privacy Rule:** All sensitive field values are processed transiently in memory only and are never written to disk, log files, or FAISS embeddings; audit logs record only the field's classification label (e.g., "password_field_detected"), never its value.
- **Security Rule:** The FastAPI backend binds exclusively to `127.0.0.1`, rejects any request with an `Origin` header not matching the extension's ID, and requires no external inbound network exposure.
- **Sensitive Data Rule:** Any field classified via keyword match against `{password, otp, pin, cvv, signature, aadhaar, biometric}` is immediately tagged `sensitive_hint=true` client-side before transmission to the backend.
- **Password Rule:** The system never reads, stores, autofills, or suggests values for password fields; it may only highlight the field and narrate "Please enter your password here."
- **OTP Rule:** Identical treatment to passwords; OTP fields are highlighted and explained but never read from clipboard, SMS, or auto-filled.
- **Payment Rule:** Payment gateway iframes/fields are treated as fully opaque and out-of-bounds; the extension does not inject any script or overlay logic inside cross-origin payment iframes (also technically prevented by browser same-origin policy).
- **Digital Signature Rule:** Digital signature/DSC (Digital Signature Certificate) upload or USB-token interactions are flagged sensitive and require full manual user handling; the AI only narrates the expected next physical action ("Insert your DSC token and click Sign").
- **Submit Button Rule:** Any button whose text or `type` matches `{submit, pay, confirm, sign, apply, final}` combined with proximity to a completed form is classified as a terminal action requiring the Safety Agent's mandatory confirmation dialog, rendered as a modal overlay reading "CivicOS AI will NOT click this for you — please review and click it yourself when ready."

## 68–76. Playwright, OCR, and Vision Pipeline

### 68–69. Playwright Architecture, Browser Automation Design

Playwright is used only within the optional desktop companion's Active Mode for non-sensitive navigation assistance (opening the correct URL in a new tab, or driving a secondary "shadow" browser instance for demo purposes), launched via `playwright.chromium.launch(headless=False)` so the user can visually observe and interrupt automation at any time; headless automation of sensitive government portals is explicitly disallowed by design.

### 70. Page Analysis Pipeline

`Screenshot capture (Playwright/content script) → OpenCV preprocessing → PaddleOCR text detection/recognition → Bounding box extraction → Spatial fusion with DOM elements → Unified Page Representation JSON`.

### 71–72. OCR Pipeline, PaddleOCR Integration

Install via `pip install paddleocr` (latest stable v3.x line, e.g., 3.5.0+), using the PP-OCRv5 lightweight multilingual detection+recognition models which support Hindi/Telugu script recognition alongside English, critical for correctly reading mixed-language Indian government portal UI text. Recommend CPU inference mode for hackathon laptops without dedicated GPUs, accepting the modest speed tradeoff. [github](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/installation.en.md)

### 73. OpenCV Pipeline

Pre-OCR image processing: convert to grayscale, apply adaptive Gaussian thresholding to handle inconsistent portal styling/contrast, apply mild denoising (`fastNlMeansDenoising`), and optionally upscale low-resolution screenshot regions 2x before OCR to improve small-font recognition accuracy common in dense government forms.

### 74. Screenshot Processing

Screenshots are captured at the viewport's device pixel ratio via `chrome.tabs.captureVisibleTab` (extension-native, no permission beyond `activeTab`) and transmitted as base64 PNG, capped at a max dimension of 1920px width server-side to bound OCR processing time.

### 75. PDF Reading

For workflows involving downloaded PDF documents (e.g., DigiLocker certificates, passport application acknowledgment receipts), use `PyMuPDF` (fitz, free/open-source) to extract text layers directly when available, falling back to rendering PDF pages as images and running the same PaddleOCR pipeline for scanned/image-only PDFs.

### 76. Vision Fallback Logic

Fallback triggers when: (a) DOM confidence score < 0.6, (b) more than 30% of detected interactive elements lack any label/aria-text, or (c) the Planner Agent's first-pass action targets a selector that fails to resolve on the live page (indicating a canvas/image-rendered UI). All three conditions are checked in the Orchestrator before deciding whether to invoke the Vision Agent, keeping the default DOM-only path fast and vision inference reserved for genuinely necessary cases.

## 77–83. LLM Integration

### 77–78. LLM Integration Design, Local Qwen Integration

Use Qwen2.5-7B-Instruct (or Qwen3 8B) in GGUF quantized format (Q4_K_M recommended for the best quality/size/speed tradeoff on consumer hardware) served locally via `llama.cpp`'s server mode or Ollama, exposing an OpenAI-compatible `/v1/chat/completions` endpoint that the Planner Agent calls internally. For hackathon laptops with limited VRAM, fall back to Qwen2.5-1.5B or 3B quantized variants to guarantee sub-3-second response latency, trading some reasoning depth for reliability. [openwhispr](https://openwhispr.com/models)

### 79–81. Prompt Engineering, Templates, Context Window Strategy

The Planner's system prompt fixes the model's role, output schema, and safety constraints in every call: it instructs the model to output only a single JSON object matching the `StepResponse` action schema, to never propose an action for any element tagged `sensitive_hint=true`, and to prefer asking a clarifying question over guessing when DOM confidence is low. The user-turn prompt includes: workflow step description, top 20 most relevant DOM elements (truncated/prioritized by viewport proximity), the last 3 turns of conversation history retrieved from FAISS, and the raw user utterance. Total context is kept under 3000 tokens to maintain fast local inference on modest hardware.

### 82–83. Conversation Memory Strategy, Reasoning Pipeline

Each user turn and corresponding AI narration is embedded and stored in FAISS immediately after response generation, enabling later semantic retrieval (e.g., "what did the AI tell me about the KYC field earlier?"). The reasoning pipeline itself is a single-pass generation (no multi-step chain-of-thought exposed to the user) to keep latency low, with the JSON-schema-constrained output format enforced via either grammar-based sampling (`llama.cpp` GBNF grammars) or strict post-hoc JSON validation with retry.

## 84–90. Workflow Engine

### 84–85. Workflow Engine, Workflow Definitions

Workflows are declarative JSON files loaded at startup from a `workflows/` directory; the engine is a simple state machine interpreter that walks an ordered list of `steps`, each with a `step_id`, `target_hint` (keywords for DOM/OCR matching), `narration_template`, `sensitive: boolean`, and `next_step_id` (supporting simple conditional branching via `condition` expressions evaluated against page state).

### 86–88. Passport, EPFO, DigiLocker Workflow JSON Structure (Illustrative Schema)

```
{
  "workflow_id": "passport_renewal",
  "domain": "passportindia.gov.in",
  "steps": [
    {"step_id": "login", "target_hint": ["login","register"], "sensitive": true, "narration": "Please log in with your credentials."},
    {"step_id": "apply_fresh", "target_hint": ["Apply for Fresh Passport","Reissue"], "sensitive": false, "narration": "Click here to start your application."},
    {"step_id": "personal_details", "target_hint": ["Given Name","Surname","DOB"], "sensitive": false, "narration": "Fill in your personal details as per your existing passport."},
    {"step_id": "submit_application", "target_hint": ["Submit","Pay and Submit"], "sensitive": true, "narration": "Review everything carefully before submitting."}
  ]
}
```

This same schema pattern applies to EPFO (`epfo_withdrawal`) and DigiLocker (`digilocker_fetch`) workflows with domain-specific `target_hint` keyword sets, described narratively in Section 12.

### 89. Workflow Configuration Format

Formalized as JSON Schema Draft-07 for validation at load time; any malformed workflow file is rejected at startup with a clear console error naming the offending file and field, preventing silent runtime failures during the hackathon demo.

### 90. Future Workflow Plugin System

New workflows can be added purely by dropping a new validated JSON file into `workflows/` and restarting the backend — no code changes required, satisfying the extensibility non-functional requirement (Section 8) and enabling rapid post-hackathon expansion to more government portals.

## 91–107. Engineering Practices

### 91–95. Logging, Debugging, Exception Handling, Retry, Timeout

Use Python's `logging` module configured with a rotating file handler writing structured JSON lines to `logs/civicos.jsonl`, plus console output for hackathon demo visibility. Every agent method wraps its core logic in try/except, converting exceptions into typed `AgentError` objects with an `error_code`, logged with full stack trace but returning a sanitized message to the client. LLM and OCR calls use a 2-retry policy with exponential backoff (1s, 2s) before falling back to a degraded response; all external-facing calls (backend endpoints) enforce a 10-second timeout via `asyncio.wait_for`, after which the extension displays "CivicOS AI is taking longer than expected" and offers manual mode.

### 96–98. Dependency Management, Configuration, Environment Variables

Use `pyproject.toml` with `uv` or `poetry` for reproducible Python dependency locking; key environment variables: `CIVICOS_LLM_MODEL_PATH`, `CIVICOS_LLM_BACKEND` (`ollama`|`llamacpp`), `CIVICOS_WHISPER_MODEL_SIZE`, `CIVICOS_DB_PATH`, `CIVICOS_LOG_LEVEL`, `CIVICOS_ALLOWED_ORIGIN` (extension ID), all loaded via `pydantic-settings` for type-safe config parsing with sensible defaults so the app runs out-of-the-box with zero manual `.env` editing for the hackathon demo.

### 99–102. Repository Structure, Folder Structure, File Responsibility, Naming Conventions

```
civicos-ai/
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── overlay/
│   │   ├── overlay.js
│   │   ├── overlay.css
│   ├── popup/
│   │   ├── popup.html
│   │   ├── popup.js
│   └── icons/
├── backend/
│   ├── main.py
│   ├── orchestrator.py
│   ├── agents/
│   │   ├── planner.py
│   │   ├── browser.py
│   │   ├── vision.py
│   │   ├── memory.py
│   │   ├── voice.py
│   │   └── safety.py
│   ├── models/
│   │   ├── schemas.py
│   ├── services/
│   │   ├── llm_client.py
│   │   ├── ocr_service.py
│   │   ├── stt_service.py
│   │   ├── tts_service.py
│   │   └── db.py
│   ├── workflows/
│   │   ├── passport_renewal.json
│   │   ├── epfo_withdrawal.json
│   │   └── digilocker_fetch.json
│   ├── config.py
│   └── requirements.txt / pyproject.toml
├── data/
│   ├── civicos.db
│   ├── faiss_index/
│   └── logs/
└── docs/
    └── (this document)
```

Naming: Python modules and functions use `snake_case`; classes use `PascalCase`; JavaScript files use `camelCase` for variables/functions and `PascalCase` for any class-like constructs; workflow JSON files are named `{workflow_id}.json` matching the `workflow_id` field internally for consistency.

### 103–106. Coding Standards, PEP-8, JavaScript Standards, Type Hints

All Python code must pass `ruff` linting configured for PEP-8 compliance and include type hints on every function signature, validated with `mypy --strict` where feasible; all Pydantic models define explicit field types and use `Field(...)` descriptions for auto-generated OpenAPI docs. JavaScript follows Airbnb-style conventions (enforced via ESLint if time permits): `const`/`let` only, no `var`, async/await preferred over raw Promise chains, and JSDoc comments on all exported functions.

### 107. Reusable Service Architecture

LLM, OCR, and STT/TTS access are each wrapped in a thin service class (`LLMClient`, `OCRService`, `STTService`, `TTSService`) exposing a stable interface regardless of the underlying model/library, so swapping Qwen for another open-weight model, or PaddleOCR for an alternative engine, requires changing only the service implementation, not any agent logic.

## 108–111. Testing Strategy

### 108–111. Unit, Integration, Manual Testing

Unit tests (`pytest`) cover: DOM-to-JSON parsing logic, Safety Agent's sensitivity classification against a fixture list of 50+ labeled field examples, workflow JSON schema validation, and Planner Agent JSON output parsing/retry logic using mocked LLM responses. Integration tests spin up the FastAPI app with `TestClient` and exercise the full `/api/v1/step` pipeline against recorded fixture DOM snapshots from real government page HTML captures (saved locally, not live-scraped in CI). Manual testing plan for the hackathon: a scripted walkthrough of all three example workflows (Section 12) performed live before the demo, explicitly attempting to trigger the Safety Agent on submit/password/OTP fields to verify it always blocks auto-action.

## 112–116. Roadmap, Risk, Scalability, Performance

### 112–113. MVP Roadmap, Phase-wise Plan

| Phase | Hours | Deliverable |
|---|---|---|
| 1 | 0–3 | Extension skeleton (manifest, content script DOM extraction, overlay rendering) working on one target site |
| 2 | 3–7 | FastAPI backend skeleton + Planner Agent wired to local Qwen, returning hardcoded-then-dynamic step JSON |
| 3 | 7–11 | Safety Agent rule engine + Memory Agent SQLite persistence integrated into the step pipeline |
| 4 | 11–15 | Vision Agent (OpenCV+PaddleOCR) fallback wired for one workflow's image-heavy step |
| 5 | 15–19 | Voice Agent (Whisper STT + Web Speech TTS) integrated into overlay mic button |
| 6 | 19–22 | Full Passport Renewal workflow end-to-end demo polish; EPFO/DigiLocker stubs |
| 7 | 22–24 | Demo rehearsal, logging cleanup, README, submission packaging |

### 114. Risk Analysis

| Risk | Mitigation |
|---|---|
| Local LLM too slow on judge's/demo laptop | Ship a small Qwen 1.5B/3B quantized fallback model as default |
| Government site DOM structure changes before demo | Use offline HTML fixture captures as a backup demo path |
| PaddleOCR install issues on Windows (GPU/CPU wheel mismatches)  [github](https://github.com/PaddlePaddle/PaddleOCR/discussions/17300) | Default to CPU-only `pip install paddleocr` path, documented explicitly |
| Manifest V3 service worker termination causing state loss | Persist session ID in `chrome.storage.session`, not in-memory JS variables |
| Judges question safety of automating government sites | Lead demo with the Safety Agent blocking a submit/OTP action as the core differentiator |

### 115–116. Scalability, Performance Optimization

Post-hackathon scalability path: replace the in-process `asyncio.Queue` agent bus with a proper message broker (Redis Streams) and containerize the backend for multi-user cloud deployment with per-user model routing; for the hackathon itself, optimize performance by caching the parsed DOM representation per URL for repeat visits, and by limiting screenshot resolution/OCR invocation frequency to only when DOM confidence is genuinely low.

## 117–123. Accessibility, Localization, Future Platforms

### 117–119. Accessibility, Localization, Regional Language Support

Dual-modality output (visual highlight + spoken narration) is the core accessibility feature; font sizes in the overlay respect the user's browser zoom settings, and all interactive overlay elements are keyboard-navigable with visible focus rings. Localization uses a simple JSON translation dictionary (`locales/en.json`, `locales/hi.json`, `locales/te.json`) for static UI strings, while dynamic AI narration is generated directly in the target language by instructing Qwen's system prompt to respond in the user's selected language (Qwen supports multilingual generation including Hindi; Telugu quality should be validated during development and may need a translation-layer fallback via a lightweight open translation model if native Telugu generation quality is insufficient).

### 120–122. Android App Future, Desktop Companion Future, Plugin Architecture

Future Android support would require an Android Accessibility Service (to read screen content analogous to DOM access) combined with an embedded WebView bridge, a substantially larger engineering effort deferred entirely past the hackathon. The Desktop Companion, already part of the MVP for Active Mode Playwright automation, can be extended post-hackathon into a full system-tray application managing model lifecycle and multi-browser support. The plugin architecture (Section 90) generalizes beyond workflows to allow future OCR/LLM backend swaps via the service abstraction layer (Section 107).

### 123. Offline Support

Excluding the unavoidable requirement to load the live government page itself, every AI subsystem (LLM, OCR, STT, memory retrieval) functions with the machine disconnected from the internet, which should be explicitly demonstrated during the hackathon by toggling airplane mode after the initial page load to prove the privacy/offline value proposition.

## 124–134. Deployment, Setup, Verification

### 124–128. Deployment Strategy, Localhost Dev, Packaging, Build, Release

For the hackathon, deployment is entirely local: no cloud hosting is required. The Chrome Extension is loaded unpacked via `chrome://extensions` → "Load unpacked" pointing at the `extension/` folder; the backend is started via `uvicorn backend.main:app --reload --port 8000`. Packaging for submission involves zipping the extension folder (for Chrome Web Store-style packaging, though not required for judging) and providing a single `setup.sh`/`setup.ps1` script that creates the Python virtual environment, installs dependencies, and downloads the chosen Qwen GGUF and Whisper model files.

### 129. Demo Flow for Hackathon

Recommended 4-minute demo script: (1) 30s — problem framing with a real EPFO/Passport portal screenshot showing UI complexity; (2) 90s — live demo of Passport Renewal workflow with Telugu voice narration and element highlighting; (3) 60s — deliberately trigger a submit/OTP field to show the Safety Agent blocking auto-action, the key differentiator; (4) 30s — toggle airplane mode to prove local/offline AI processing; (5) 30s — architecture diagram recap and closing statement on Digital India accessibility impact.

### 130–133. Developer Setup Guide, Installation Commands, Dependencies, Versions

```
git clone <repo>
cd civicos-ai/backend
python3.11 -m venv venv && source venv/bin/activate
pip install fastapi uvicorn[standard] pydantic-settings
pip install paddleocr>=3.5.0 opencv-python-headless
pip install faster-whisper sentence-transformers faiss-cpu
pip install llama-cpp-python   # or install Ollama separately
# Download models
ollama pull qwen2.5:7b-instruct-q4_K_M   # or smaller 1.5b/3b variant
bash scripts/download_whisper_model.sh base
uvicorn main:app --port 8000
```

Recommended versions: Python 3.11+, PaddleOCR 3.5.0+, Whisper `base` model (142MB) for balance of speed/accuracy on hackathon hardware, Qwen2.5 7B Q4_K_M for GPU-available machines or Qwen2.5 1.5B/3B for CPU-only fallback, FAISS CPU build (`faiss-cpu`), Chrome 120+ for full Manifest V3 support. [security.snyk](https://security.snyk.io/package/pip/paddleocr/versions)

### 134. Verification Checklist

- [ ] Extension loads without console errors on all six target domains.
- [ ] Backend health check `GET /api/v1/health` returns 200 with model-loaded status.
- [ ] Safety Agent blocks 100% of test cases in the labeled sensitive-field fixture set.
- [ ] Voice round-trip (mic input → Whisper → Qwen → TTS output) completes under 5 seconds.
- [ ] Workflow resume correctly restores step index after simulated browser restart.
- [ ] Airplane-mode offline test passes for all AI subsystems except live page load.

## 135–140. Closing Sections

### 135. Final End-to-End Execution Flow

Install extension → start backend → user issues intent → Planner selects workflow → Browser/Vision agents jointly interpret the live page → Planner generates the next safe action → Safety Agent gates any sensitive action → overlay highlights and narrates → Memory Agent checkpoints progress → loop until `WORKFLOW_COMPLETE`.

### 136. Future Improvements

Add a translation-quality-assured Telugu narration layer, expand to an Android Accessibility Service-based client, integrate a proper message broker for multi-user scaling, add a workflow-authoring UI for non-developers to define new government site guides, and add cryptographically signed audit logs for institutional trust in government-adjacent AI tooling.

### 137–138. Appendix and Glossary

**DOM** — Document Object Model, the browser's structured representation of a webpage. **OCR** — Optical Character Recognition, extracting text from images. **GGUF** — a quantized model file format used by llama.cpp for efficient local LLM inference. **Safety Gate** — the mandatory human-confirmation checkpoint before any sensitive action. **Workflow Definition** — the declarative JSON describing a government process's steps.

### 139. References

Key technologies referenced throughout this document are drawn from Playwright's official documentation, the browser-use open-source agent framework, PaddleOCR's official installation and version documentation, Chrome's Manifest V3 security and migration guides, and current local-LLM/Whisper deployment benchmarks. [github](https://github.com/browser-use/browser-use)

### 140. Complete Build Order

1. Extension skeleton + DOM extraction. 2. FastAPI skeleton + health check. 3. Planner Agent + local LLM wiring. 4. Safety Agent rule engine. 5. Memory Agent (SQLite). 6. Overlay highlighting + narration rendering. 7. Vision Agent (OCV+OCR) fallback. 8. Voice Agent (Whisper+TTS). 9. Workflow JSON definitions for all three example flows. 10. FAISS semantic memory. 11. End-to-end integration testing. 12. Demo rehearsal and packaging.

