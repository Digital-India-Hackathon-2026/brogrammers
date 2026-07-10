"""
Orchestrator — CivicOS AI (Telangana ePASS Assistant)

Turns a free-form student request into a step-by-step, click-by-click guided
navigation of the Telangana ePASS portal:

    prompt → match a service → highlight the ONE button to click →
    user clicks → page changes → resync & highlight the NEXT button → … → done

The step-by-step matching is fully deterministic (works with no LLM). The LLM,
when available, is used only to disambiguate a vague prompt and to answer
free-form questions.

Every response passes through the Safety Agent, which refuses to act on
password / OTP / payment fields.
"""

from __future__ import annotations

import os
import re
import json
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Tuple

from models.schemas import DOMElement, StepRequest, StepResponse
from agents.planner import PlannerAgent
from agents.safety import SafetyAgent
from services.db import save_session
from services.rag_service import RAGService
from services.translator import get_translator


# ── control-phrase vocabularies ───────────────────────────────────────────────
# single-word advance tokens (matched as whole words only)
_ADVANCE_TOKENS = {"next", "done", "ok", "okay", "continue", "proceed", "finished", "yes", "yep"}
# multi-word advance phrases (matched as substrings)
_ADVANCE_PHRASES = {"next step", "go ahead", "did it", "completed it", "i clicked it", "i did it"}

_STOP_WORDS = {"stop", "cancel", "exit", "quit", "never mind", "nevermind", "restart", "reset"}

# precise service-list triggers (avoid catching "help me to …")
_LIST_PHRASES = {
    "what can you do", "what can you help", "what services", "which services",
    "list services", "show services", "list of services", "what do you do",
    "show me services", "available services",
}
_LIST_EXACT = {"services", "menu", "options", "help", "list", "?"}

_CATEGORY_RANK = {"Post-Matric": 0, "Pre-Matric": 1, "Other": 2}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def _overlap_count(a: set, b: set) -> int:
    """Count shared tokens, treating a prefix relationship (len>=4) as a match.
    This bridges variants like renew/renewal, apply/application, register/registration."""
    count = 0
    for wa in a:
        if wa in b:
            count += 1
            continue
        if len(wa) >= 4 and any(
            (wb.startswith(wa) or wa.startswith(wb)) and min(len(wa), len(wb)) >= 4 for wb in b
        ):
            count += 1
    return count


class Orchestrator:
    def __init__(self) -> None:
        self.planner = PlannerAgent()
        self.safety = SafetyAgent()
        self.translator = get_translator()
        self.rag = RAGService.get_instance()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self._load_workflows()

        try:
            self.rag.load()
        except Exception as e:
            print(f"[Orchestrator] RAG pre-load warning: {e}", flush=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow loading & catalog
    # ─────────────────────────────────────────────────────────────────────────
    def _load_workflows(self) -> None:
        workflows_dir = os.path.join(os.path.dirname(__file__), "workflows")
        if not os.path.isdir(workflows_dir):
            print(f"[Orchestrator] No workflows dir at {workflows_dir}", flush=True)
            return
        for filename in sorted(os.listdir(workflows_dir)):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(workflows_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    wf = json.load(f)
                wid = wf.get("workflow_id")
                if wid and wf.get("steps"):
                    self.workflows[wid] = wf
                    print(f"[Orchestrator] Loaded workflow: {wid} ({len(wf['steps'])} steps)", flush=True)
            except Exception as e:
                print(f"[Orchestrator] Failed to load workflow {filename}: {e}", flush=True)

    def services_catalog(self) -> List[Dict[str, Any]]:
        """Public list of services for the extension's quick-start chips."""
        items = [
            {
                "workflow_id": wf["workflow_id"],
                "title": wf.get("title", wf["workflow_id"]),
                "category": wf.get("category", "Other"),
                "icon": wf.get("icon", "📄"),
                "blurb": wf.get("blurb", ""),
                "external": wf.get("external", False),
            }
            for wf in self.workflows.values()
        ]
        items.sort(key=lambda s: (_CATEGORY_RANK.get(s["category"], 9), s["title"]))
        return items

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────
    def handle_step(self, request: StepRequest) -> StepResponse:
        session_id = request.session_id
        raw = request.user_utterance or ""
        utterance = _normalize(raw)
        dom = request.dom_snapshot or []
        current_url = request.url or ""
        language = getattr(request, "language", "en") or "en"

        print(f"[Orchestrator] session={session_id} url={current_url[:60]} utterance='{utterance[:80]}'", flush=True)
        session = self._get_session(session_id)

        try:
            resp = self._route(session, raw, utterance, dom)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Orchestrator] routing error: {e}", flush=True)
            resp = StepResponse(
                action="explain",
                narration_text="Sorry, I hit a snag processing that. Please try again.",
                confidence_score=0.0,
            )

        # Safety gate — always.
        resp = self.safety.check(resp.target_selector, dom, resp)

        # Localize the narration to the user's chosen language (no-op for English).
        if language != "en" and resp.narration_text:
            try:
                resp.narration_text = self.translator.translate(resp.narration_text, language)
            except Exception as e:
                print(f"[Orchestrator] translate error: {e}", flush=True)

        # Persist a lightweight checkpoint.
        try:
            domain = urlparse(current_url).netloc or "telanganaepass.cgg.gov.in"
            save_session(session_id, domain, max(0, session.get("step_index", 0)), "active")
        except Exception as e:
            print(f"[Orchestrator] checkpoint error: {e}", flush=True)

        return resp

    # ─────────────────────────────────────────────────────────────────────────
    # Routing
    # ─────────────────────────────────────────────────────────────────────────
    def _route(self, session: Dict[str, Any], raw: str, utterance: str, dom: List[DOMElement]) -> StepResponse:
        # Deterministic start from a service chip: "__start__:<workflow_id>".
        # (Bypasses fuzzy matching so clicking a service always launches exactly that flow.)
        if raw.strip().startswith("__start__:"):
            wid = raw.strip().split(":", 1)[1].strip()
            if wid in self.workflows:
                return self._start_workflow(session, wid, dom)

        active_wid = session.get("workflow_id")
        active = self.workflows.get(active_wid) if active_wid else None
        completed = session.get("completed", False)

        # ── Empty utterance = a page change fired the auto-continue. ───────────
        if not utterance:
            if active and not completed:
                return self._auto_continue(session, active, dom)
            return StepResponse(
                action="explain",
                narration_text="Tell me which scholarship service you need and I'll guide you click by click.",
                confidence_score=0.3,
            )

        # ── Stop / reset ──────────────────────────────────────────────────────
        if any(w in utterance for w in _STOP_WORDS):
            session["workflow_id"] = None
            session["completed"] = False
            session["step_index"] = 0
            return StepResponse(
                action="explain",
                narration_text="Okay, I've stopped the guide. Ask me for another service whenever you're ready.",
                confidence_score=1.0,
            )

        # ── Explicit advance while a guide is running ─────────────────────────
        if active and not completed and self._is_advance(utterance):
            return self._advance_manual(session, active, dom)

        # ── "what can you do" / list services ─────────────────────────────────
        if self._wants_service_list(utterance):
            return self._service_list_response()

        # ── Try to match the request to a service ─────────────────────────────
        wid, confident = self._match_workflow(utterance)
        if wid and not confident and self.planner.llm.available:
            llm_pick = self.planner.classify_service(raw, self.services_catalog())
            if llm_pick:
                wid, confident = llm_pick, True
        if wid is None and self.planner.llm.available:
            llm_pick = self.planner.classify_service(raw, self.services_catalog())
            if llm_pick:
                wid, confident = llm_pick, True

        if wid and confident:
            return self._start_workflow(session, wid, dom)

        # ── Otherwise: answer as a general question ───────────────────────────
        return self._answer_question(raw, utterance, wid, dom)

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow driving
    # ─────────────────────────────────────────────────────────────────────────
    def _start_workflow(self, session: Dict[str, Any], wid: str, dom: List[DOMElement]) -> StepResponse:
        wf = self.workflows[wid]
        session["workflow_id"] = wid
        session["step_index"] = 0
        session["completed"] = False
        print(f"[Orchestrator] Starting workflow '{wid}': {wf.get('title')}", flush=True)

        if wf.get("external"):
            session["completed"] = True
            return self._external_guide(wf)

        return self._step_response(wf, 0, dom, intro=True)

    def _auto_continue(self, session: Dict[str, Any], wf: Dict[str, Any], dom: List[DOMElement]) -> StepResponse:
        """
        Page changed — figure out which step we're on now. Key rule for real-site
        continuity: NEVER declare 'complete' just because we can't find a target —
        only complete when we were on the last step. Unknown intermediate pages
        (e.g. a login screen between routes) are held, not abandoned.
        """
        steps = wf["steps"]
        cur = session.get("step_index", 0)

        # 0. A login / captcha gate between routes → hold FIRST (before any step match),
        #    so a stray "Register"/"Submit" link on the login page can't skip us past it.
        if self._is_login_gate(dom):
            return StepResponse(
                action="confirm_required",
                target_selector="",
                narration_text=(
                    "Please sign in yourself on this page — I never handle passwords, OTPs or captcha. "
                    "Once you're logged in, I'll automatically continue guiding you."
                ),
                confidence_score=1.0,
                workflow_id=wf["workflow_id"],
                service_title=wf.get("title", ""),
                step_index=cur,
                total_steps=len(steps),
            )

        # 1. A later step's target is visible → jump forward to it.
        for idx in range(cur + 1, len(steps)):
            if self._match_element(steps[idx]["target_hint"], dom) is not None:
                session["step_index"] = idx
                return self._step_response(wf, idx, dom)

        # 2. Current step's target still on the page → re-show it (page hasn't advanced).
        if self._match_element(steps[cur]["target_hint"], dom) is not None:
            return self._step_response(wf, cur, dom)

        # 3. We were on the final step and its target is gone → genuinely done.
        if cur >= len(steps) - 1:
            session["completed"] = True
            return self._complete_response(wf)

        # 4. Unexpected intermediate page → hold (keep the guide alive), don't complete.
        return StepResponse(
            action="explain",
            target_selector="",
            narration_text="I'm with you — continue on this page and I'll pick up the next step automatically.",
            confidence_score=0.4,
            workflow_id=wf["workflow_id"],
            service_title=wf.get("title", ""),
            step_index=cur,
            total_steps=len(steps),
        )

    def _is_login_gate(self, dom: List[DOMElement]) -> bool:
        for el in dom:
            blob = _normalize(" ".join([el.label, el.selector, el.id, el.type, el.placeholder]))
            if "password" in blob or "captcha" in blob:
                return True
        return False

    def _advance_manual(self, session: Dict[str, Any], wf: Dict[str, Any], dom: List[DOMElement]) -> StepResponse:
        """User said 'next'/'done' — move forward one step on the current page."""
        steps = wf["steps"]
        new_idx = session.get("step_index", 0) + 1
        if new_idx >= len(steps):
            session["completed"] = True
            return self._complete_response(wf)
        session["step_index"] = new_idx
        return self._step_response(wf, new_idx, dom)

    def _step_response(
        self, wf: Dict[str, Any], idx: int, dom: List[DOMElement], intro: bool = False
    ) -> StepResponse:
        steps = wf["steps"]
        step = steps[idx]
        el = self._match_element(step["target_hint"], dom)
        narration = step["narration"]
        if intro:
            narration = f"Let's do this together — {wf.get('title', 'this service')}.\n\n{narration}"

        base = dict(
            workflow_id=wf["workflow_id"],
            service_title=wf.get("title", ""),
            step_index=idx,
            total_steps=len(steps),
        )
        action_type = step.get("action", "click")

        # Sensitive (login / OTP / final submit) → always hand back to the user.
        if step.get("sensitive"):
            return StepResponse(
                action="confirm_required",
                target_selector=el.selector if el else "",
                narration_text=narration,
                confidence_score=1.0,
                **base,
            )

        # Form-filling step → subtle marker on the submit button, NO page dim.
        if action_type == "form":
            if el is not None:
                return StepResponse(
                    action="form",
                    target_selector=el.selector,
                    narration_text=narration,
                    confidence_score=0.85,
                    **base,
                )
            return StepResponse(
                action="explain",
                target_selector="",
                narration_text=narration,
                confidence_score=0.6,
                **base,
            )

        # Normal navigation click → spotlight the button.
        if el is not None:
            return StepResponse(
                action="highlight",
                target_selector=el.selector,
                narration_text=narration,
                confidence_score=0.9,
                **base,
            )

        # Target not found yet (page still loading, or scrolled away).
        return StepResponse(
            action="explain",
            target_selector="",
            narration_text=narration + "\n\n(If you don't see it yet, scroll down or wait for the page to finish loading.)",
            confidence_score=0.5,
            **base,
        )

    def _complete_response(self, wf: Dict[str, Any]) -> StepResponse:
        return StepResponse(
            action="complete",
            target_selector="",
            narration_text=(
                f"✅ That's the full flow for '{wf.get('title', 'this service')}'. "
                "You're on the right page now — complete the details shown. "
                "Ask me for another service anytime!"
            ),
            confidence_score=1.0,
            workflow_id=wf["workflow_id"],
            service_title=wf.get("title", ""),
            step_index=len(wf["steps"]) - 1,
            total_steps=len(wf["steps"]),
            is_final=True,
        )

    def _external_guide(self, wf: Dict[str, Any]) -> StepResponse:
        lines = [f"{i+1}. {s['narration']}" for i, s in enumerate(wf["steps"])]
        body = "\n".join(lines)
        return StepResponse(
            action="explain",
            target_selector="",
            narration_text=f"{wf.get('title', 'Guide')} — this happens on an external site, so here are the steps:\n\n{body}",
            confidence_score=0.9,
            workflow_id=wf["workflow_id"],
            service_title=wf.get("title", ""),
            total_steps=len(wf["steps"]),
            is_final=True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Q&A fallback
    # ─────────────────────────────────────────────────────────────────────────
    def _answer_question(self, raw: str, utterance: str, hinted_wid: Optional[str], dom: List[DOMElement]) -> StepResponse:
        rag_chunks: List[str] = []
        try:
            meta = self.rag.retrieve_with_meta(utterance or raw, top_k=3)
            rag_chunks = [m["text"] for m in meta]
        except Exception as e:
            print(f"[Orchestrator] RAG error: {e}", flush=True)

        answer = self.planner.answer_qa(raw, rag_chunks)

        # If the question clearly relates to a service, nudge the user to start it.
        suffix = ""
        if hinted_wid and hinted_wid in self.workflows:
            title = self.workflows[hinted_wid].get("title", "")
            suffix = f"\n\nWant me to guide you through '{title}' step by step? Just say yes."
        return StepResponse(
            action="explain",
            narration_text=(answer + suffix).strip(),
            confidence_score=0.7,
        )

    def _service_list_response(self) -> StepResponse:
        cat = self.services_catalog()
        lines = [f"{s['icon']} {s['title']}" for s in cat if not s["external"]]
        body = "\n".join(lines)
        return StepResponse(
            action="explain",
            narration_text=(
                "I can guide you step by step through these Telangana ePASS services:\n\n"
                f"{body}\n\nJust tell me which one, e.g. 'check my scholarship status'."
            ),
            confidence_score=1.0,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Matching helpers (deterministic)
    # ─────────────────────────────────────────────────────────────────────────
    def _is_advance(self, utterance: str) -> bool:
        words = set(utterance.split())
        if words & _ADVANCE_TOKENS:
            return True
        return any(p in utterance for p in _ADVANCE_PHRASES)

    def _wants_service_list(self, utterance: str) -> bool:
        if utterance in _LIST_EXACT:
            return True
        return any(p in utterance for p in _LIST_PHRASES)

    def _match_workflow(self, utterance: str) -> Tuple[Optional[str], bool]:
        """Deterministic keyword scoring. Returns (workflow_id | None, confident)."""
        u = _normalize(utterance)
        uwords = set(u.split())
        scored: List[Tuple[int, str]] = []
        for wid, wf in self.workflows.items():
            phrases = list(wf.get("match_keywords", [])) + [wf.get("title", "")]
            score = 0
            for phrase in phrases:
                p = _normalize(phrase)
                if not p:
                    continue
                if p in u:
                    score += 3 + len(p.split())
                else:
                    ov = _overlap_count(set(p.split()), uwords)
                    if ov >= 2:
                        score += ov
            scored.append((score, wid))

        scored.sort(reverse=True)
        if not scored or scored[0][0] < 4:
            return None, False
        top_score, top_wid = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0
        confident = top_score >= 5 and (top_score - second) >= 2
        return top_wid, confident

    def _match_element(self, target_hints: List[str], dom: List[DOMElement]) -> Optional[DOMElement]:
        """
        Find the DOM element that best matches a step's target hints.

        Two signals per element:
          • primary — the element's own text/href (label, selector, id, placeholder, href)
          • context — the surrounding section/row text (weighted lower)
        Context lets us pick the right button when several share the same label
        (e.g. two "Registration" buttons under different section headings).
        """
        best: Optional[DOMElement] = None
        best_score = 0.0
        for el in dom:
            primary = _normalize(" ".join([el.label, el.selector, el.id, el.placeholder, el.type, getattr(el, "href", "")]))
            context = _normalize(getattr(el, "context", ""))
            if not primary and not context:
                continue
            pw, cw = set(primary.split()), set(context.split())
            score = 0.0
            for hint in target_hints:
                h = _normalize(hint)
                if not h:
                    continue
                if h in primary:
                    score += 4 + len(h.split())
                elif h and h in context:
                    score += 2 + 0.5 * len(h.split())          # section/context match — lower weight
                else:
                    ov = _overlap_count(set(h.split()), pw)
                    if ov >= 2:
                        score += ov
                    else:
                        ovc = _overlap_count(set(h.split()), cw)
                        if ovc >= 2:
                            score += 0.5 * ovc
            if score <= 0:
                continue
            if el.tag in ("a", "button") or el.type in ("submit", "button"):
                score += 0.5
            if score > best_score:
                best_score = score
                best = el
        return best if best_score >= 4 else None

    # ─────────────────────────────────────────────────────────────────────────
    # Session
    # ─────────────────────────────────────────────────────────────────────────
    def _get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {"workflow_id": None, "step_index": 0, "completed": False}
        return self.sessions[session_id]
