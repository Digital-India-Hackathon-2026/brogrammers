from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import tempfile
import asyncio
import os

from typing import List, Optional

from models.schemas import StepRequest, StepResponse
from orchestrator import Orchestrator
from services.db import init_db, get_last_active_session, clear_session
from services.translator import get_translator, LANGUAGES
from agents.voice import VoiceAgent
from demo_pages import render_demo_page

app = FastAPI(title="CivicOS AI — Telangana ePASS Assistant", version="2.0.0")

# CORS: the backend only ever binds to localhost and is called by the extension
# and the bundled demo page, so a permissive policy is acceptable here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()


@app.on_event("startup")
def startup_event():
    print("Backend starting up, initializing database...", flush=True)
    init_db()
    print(f"[startup] LLM provider: {orchestrator.planner.llm.provider or 'none (deterministic)'}", flush=True)
    print(f"[startup] Loaded {len(orchestrator.workflows)} ePASS service workflows", flush=True)


@app.get("/")
def read_root():
    return {"status": "ok", "app": "CivicOS AI — Telangana ePASS Assistant"}


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "civicos-epass",
        "llm_provider": orchestrator.planner.llm.provider or "none",
        "workflows": len(orchestrator.workflows),
    }


@app.get("/api/v1/services")
def list_services(lang: str = "en"):
    """Catalog of guided services — used by the extension for quick-start chips."""
    services = orchestrator.services_catalog()
    if lang and lang != "en":
        tr = get_translator()
        titles = tr.translate_batch([s["title"] for s in services], lang)
        blurbs = tr.translate_batch([s["blurb"] for s in services], lang)
        for i, s in enumerate(services):
            s["title"] = titles[i]
            s["blurb"] = blurbs[i]
    return {"services": services}


@app.get("/api/v1/languages")
def list_languages():
    """Supported UI languages for the assistant's language selector."""
    return {"languages": LANGUAGES}


class TranslateRequest(BaseModel):
    texts: List[str]
    language: str = "en"


@app.post("/api/v1/translate")
def translate_texts(request: TranslateRequest):
    """Batch-translate UI strings to the selected language (cached server-side)."""
    try:
        translations = get_translator().translate_batch(request.texts, request.language)
        return {"translations": translations}
    except Exception as e:
        print(f"Translate error: {e}", flush=True)
        return {"translations": request.texts}


@app.post("/api/v1/step", response_model=StepResponse)
async def post_step(request: StepRequest):
    try:
        return orchestrator.handle_step(request)
    except Exception as e:
        print(f"Error handling step request: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class VoiceTranscribeRequest(BaseModel):
    session_id: str
    audio_b64: str


@app.post("/api/v1/voice/transcribe")
async def post_voice_transcribe(request: VoiceTranscribeRequest):
    try:
        audio_bytes = base64.b64decode(request.audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            temp_wav.write(audio_bytes)
            temp_wav_path = temp_wav.name
        try:
            voice_agent = VoiceAgent.get_instance()
            loop = asyncio.get_event_loop()
            text = await asyncio.wait_for(
                loop.run_in_executor(None, voice_agent.transcribe, temp_wav_path),
                timeout=15.0,
            )
            return {"status": "success", "text": text}
        finally:
            if os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Voice transcription timed out.")
    except Exception as e:
        print(f"Voice transcription error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/memory/resume")
def get_memory_resume(domain: str):
    try:
        session = get_last_active_session(domain)
        if session:
            return {"status": "found", "session": session}
        return {"status": "not_found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ClearSessionRequest(BaseModel):
    session_id: str


@app.post("/api/v1/memory/clear")
def post_memory_clear(request: ClearSessionRequest):
    try:
        clear_session(request.session_id)
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Local ePASS demo (a stand-in portal so you can rehearse the full flow) ─────
@app.get("/demo", response_class=HTMLResponse)
@app.get("/demo/{page:path}", response_class=HTMLResponse)
def demo(page: str = "home"):
    html = render_demo_page(page or "home")
    if html is None:
        raise HTTPException(status_code=404, detail="Unknown demo page")
    return html


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
