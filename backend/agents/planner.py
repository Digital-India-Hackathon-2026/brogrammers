"""
Planner Agent — CivicOS AI (Telangana ePASS)

The step-by-step highlighting is deterministic and lives in the Orchestrator, so
the demo works with zero model. The Planner is the *optional intelligence layer*:

  • classify_service()  — map a free-form prompt to one of the guided services
                          (only used when keyword scoring is ambiguous)
  • answer_qa()         — answer a general question from retrieved knowledge

Both use LLMClient (Claude → Ollama → none) and fall back cleanly when no model
is available.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Dict, Any

from services.llm_client import get_llm


class PlannerAgent:
    def __init__(self) -> None:
        self.llm = get_llm()

    # ─────────────────────────────────────────────────────────────────────────
    # Intent classification (LLM tiebreaker)
    # ─────────────────────────────────────────────────────────────────────────
    def classify_service(self, utterance: str, services: List[Dict[str, Any]]) -> Optional[str]:
        """
        Return the best-matching workflow_id for the utterance, or None.
        Used only when deterministic keyword scoring can't decide confidently.
        """
        if not self.llm.available or not services:
            return None

        catalog = "\n".join(
            f"- id: {s['workflow_id']} | {s['title']} — {s.get('blurb', '')}"
            for s in services
        )
        system = (
            "You route a student's request to exactly one Telangana ePASS scholarship service. "
            "Reply with ONLY the service id from the list, or the single word NONE if nothing fits. "
            "No punctuation, no explanation."
        )
        user = (
            f"Services:\n{catalog}\n\n"
            f"Student said: \"{utterance}\"\n\n"
            "Answer with one id or NONE:"
        )
        reply = self.llm.chat(system, user, temperature=0.0, max_tokens=20)
        if not reply:
            return None
        token = reply.strip().split()[0].strip().strip(".,:").lower() if reply.strip() else ""
        valid = {s["workflow_id"].lower(): s["workflow_id"] for s in services}
        if token in valid:
            return valid[token]
        # tolerate the model echoing the id inside a sentence
        for wid_lower, wid in valid.items():
            if wid_lower in reply.lower():
                return wid
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Free-form Q&A
    # ─────────────────────────────────────────────────────────────────────────
    def answer_qa(self, utterance: str, rag_chunks: List[str]) -> str:
        """Return a concise helpful answer. Uses the LLM if available, else the top knowledge chunk."""
        knowledge = "\n\n".join(rag_chunks) if rag_chunks else ""

        if self.llm.available:
            system = (
                "You are CivicOS AI, a friendly assistant for the Telangana ePASS scholarship portal. "
                "Answer the student's question in 2-4 short sentences using ONLY the knowledge provided. "
                "Be concrete (name the exact buttons / documents). If the knowledge doesn't cover it, say so "
                "briefly and suggest opening the relevant scholarship service. Never ask for or handle "
                "passwords, OTPs or payment details."
            )
            user = (
                f"Knowledge:\n{knowledge or '(none retrieved)'}\n\n"
                f"Question: {utterance}\n\nAnswer:"
            )
            reply = self.llm.chat(system, user, temperature=0.2, max_tokens=400)
            if reply:
                return reply.strip()

        # Deterministic fallback: hand back the most relevant knowledge chunk.
        if rag_chunks:
            return rag_chunks[0]
        return (
            "I can guide you through Telangana ePASS scholarship services step by step. "
            "Try asking, for example, 'help me check my scholarship status' or 'apply for post-matric scholarship'."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Helper reused by the Orchestrator to map a hint to a real DOM selector
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def normalize(text: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())
