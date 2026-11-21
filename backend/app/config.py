"""Settings, read once from environment variables.

Secrets (API keys) come only from the environment and are never sent to the browser
or written to logs (OWASP A02 / A05).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

Provider = Literal["none", "anthropic", "ollama"]


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


def _int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: os.getenv("APP_ENV", "production"))
    cors_origins: list[str] = field(default_factory=lambda: _list("CORS_ORIGINS", "http://localhost:5173"))
    allowed_hosts: list[str] = field(default_factory=lambda: _list("ALLOWED_HOSTS", "localhost,127.0.0.1,backend"))
    trust_proxy_headers: bool = field(default_factory=lambda: _bool("TRUST_PROXY_HEADERS", False))
    enable_hsts: bool = field(default_factory=lambda: _bool("ENABLE_HSTS", False))
    max_body_bytes: int = field(default_factory=lambda: _int("MAX_BODY_BYTES", 16_384, 1_024, 1_048_576))
    rate_limit_assistant: int = field(default_factory=lambda: _int("RATE_LIMIT_ASSISTANT_PER_MIN", 10, 1, 1_000))
    rate_limit_write: int = field(default_factory=lambda: _int("RATE_LIMIT_WRITE_PER_MIN", 30, 1, 1_000))
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "none").strip().lower())
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"))
    llm_timeout_s: int = field(default_factory=lambda: _int("LLM_TIMEOUT_SECONDS", 45, 5, 300))
    # Fixed by the operator, never taken from a request: prevents SSRF (OWASP A10)
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1"))

    @property
    def is_dev(self) -> bool:
        return self.env == "development"

    @property
    def provider(self) -> Provider:
        return self.llm_provider if self.llm_provider in ("anthropic", "ollama") else "none"  # type: ignore[return-value]
