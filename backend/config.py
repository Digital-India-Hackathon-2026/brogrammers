import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Central configuration for CivicOS AI (Telangana ePASS Assistant).

    LLM provider is chosen automatically at runtime in this priority order:
      1. Anthropic Claude   — if ANTHROPIC_API_KEY is set (smartest understanding)
      2. Local Ollama       — if reachable (private / offline)
      3. Deterministic only — no model needed; the step-by-step navigator still works

    Everything below has a sensible default so the app runs out-of-the-box.
    """

    # ── LLM provider selection ────────────────────────────────────────────────
    # "auto" | "anthropic" | "ollama" | "none"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")

    # Anthropic Claude (cloud)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    # Local Ollama (OpenAI-compatible endpoint)
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

    # ── Target portal ─────────────────────────────────────────────────────────
    TARGET_DOMAIN: str = os.getenv("TARGET_DOMAIN", "telanganaepass.cgg.gov.in")

    class Config:
        env_file = ".env"


settings = Settings()
