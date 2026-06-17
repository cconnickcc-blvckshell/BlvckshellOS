"""Central configuration for the harness.

All secrets and tunables are sourced from environment variables (or a local
``.env`` file). Nothing is hardcoded. Importing :data:`settings` anywhere in the
codebase yields a single, validated, cached configuration object.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated harness configuration loaded from the environment.

    Every backend in the harness (message bus, memory, inference) has an
    in-process fallback so the system runs end to end with zero external
    dependencies. Provide the relevant connection strings to switch to the
    production backends.
    """

    model_config = SettingsConfigDict(
        env_prefix="BLVCKSHELL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Runtime ---------------------------------------------------------
    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Message bus -----------------------------------------------------
    # If a Redis URL is provided the harness uses Redis pub/sub; otherwise it
    # falls back to a fully-featured in-process async bus.
    redis_url: str | None = Field(default=None)
    bus_namespace: str = "blvckshell"

    # --- Shared memory / persistence ------------------------------------
    supabase_url: str | None = Field(default=None)
    supabase_key: str | None = Field(default=None)
    working_memory_ttl_seconds: int = 60 * 60 * 24  # 24 hours

    # --- Inference -------------------------------------------------------
    # Provider selection: "stub" is deterministic and offline (used for tests
    # and local bring-up). "anthropic" and "ollama" hit real models.
    inference_provider: Literal["stub", "anthropic", "ollama"] = "stub"
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = "claude-3-5-sonnet-latest"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.2

    # --- Agent loop ------------------------------------------------------
    max_agent_iterations: int = 8
    heartbeat_interval_seconds: int = 15
    heartbeat_grace_seconds: int = 45

    @property
    def use_redis(self) -> bool:
        """Whether a Redis-backed message bus / working memory should be used."""
        return bool(self.redis_url)

    @property
    def use_supabase(self) -> bool:
        """Whether Supabase-backed persistence should be used."""
        return bool(self.supabase_url and self.supabase_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()


settings = get_settings()
