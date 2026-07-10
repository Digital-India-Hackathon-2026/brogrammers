"""
LLMClient — a thin, provider-agnostic chat wrapper for CivicOS AI.

Resolution order (see config.LLM_PROVIDER = "auto"):
    1. Anthropic Claude  — used when ANTHROPIC_API_KEY is set
    2. Local Ollama      — used when the Ollama server answers
    3. None              — no model available; callers fall back to deterministic logic

The rest of the app only ever calls `chat()` / `available` and never needs to
know which backend answered. Both backends are reached over plain httpx so the
only dependency is `httpx` (no vendor SDK required).
"""

from __future__ import annotations

import httpx
from typing import Optional

from config import settings


class LLMClient:
    def __init__(self) -> None:
        self._client = httpx.Client(timeout=20.0)
        self._provider: Optional[str] = None  # resolved lazily & cached
        self._resolved = False

    # ── provider resolution ───────────────────────────────────────────────────
    def _resolve_provider(self) -> Optional[str]:
        if self._resolved:
            return self._provider

        pref = (settings.LLM_PROVIDER or "auto").lower()

        def anthropic_ok() -> bool:
            return bool(settings.ANTHROPIC_API_KEY.strip())

        def ollama_ok() -> bool:
            try:
                r = self._client.get(f"{settings.OLLAMA_URL}/api/tags", timeout=2.0)
                return r.status_code == 200
            except Exception:
                return False

        provider: Optional[str] = None
        if pref == "anthropic":
            provider = "anthropic" if anthropic_ok() else None
        elif pref == "ollama":
            provider = "ollama" if ollama_ok() else None
        elif pref == "none":
            provider = None
        else:  # auto
            if anthropic_ok():
                provider = "anthropic"
            elif ollama_ok():
                provider = "ollama"
            else:
                provider = None

        self._provider = provider
        self._resolved = True
        print(f"[LLMClient] Provider resolved to: {provider or 'none (deterministic only)'}", flush=True)
        return provider

    @property
    def provider(self) -> Optional[str]:
        return self._resolve_provider()

    @property
    def available(self) -> bool:
        return self._resolve_provider() is not None

    # ── public chat interface ─────────────────────────────────────────────────
    def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.1,
        max_tokens: int = 700,
    ) -> Optional[str]:
        """Return the model's text reply, or None if no provider is available / it errored."""
        provider = self._resolve_provider()
        try:
            if provider == "anthropic":
                return self._chat_anthropic(system, user, temperature, max_tokens)
            if provider == "ollama":
                return self._chat_ollama(system, user, temperature, max_tokens)
        except Exception as e:
            print(f"[LLMClient] {provider} chat error: {e}", flush=True)
            # If Anthropic failed at runtime, try Ollama as a live fallback once.
            if provider == "anthropic":
                try:
                    return self._chat_ollama(system, user, temperature, max_tokens)
                except Exception as e2:
                    print(f"[LLMClient] Ollama fallback error: {e2}", flush=True)
        return None

    # ── backends ──────────────────────────────────────────────────────────────
    def _chat_anthropic(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        resp = self._client.post(
            f"{settings.ANTHROPIC_BASE_URL}/v1/messages",
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.ANTHROPIC_MODEL,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        return "".join(parts).strip()

    def _chat_ollama(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        resp = self._client.post(
            f"{settings.OLLAMA_URL}/v1/chat/completions",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


# Module-level singleton
_llm_singleton: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = LLMClient()
    return _llm_singleton
