"""Central configuration for the harness.

All secrets and tunables come from environment variables (or a local ``.env``
file). Nothing is hardcoded. The single :func:`get_settings` accessor returns a
cached :class:`Settings` instance.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from the environment.

    Attributes:
        environment: Deployment environment label (``local``/``prod``/...).
        log_level: Root log level for structured logging.
        redis_url: Connection URL for the Redis message bus and working memory.
        use_in_memory_bus: Force the in-memory bus/memory backends (tests/offline).
        supabase_url: Supabase project URL for episodic memory and doctrine.
        supabase_key: Supabase service key.
        anthropic_api_key: Anthropic API key for Claude inference.
        anthropic_model: Default Claude model id.
        ollama_url: Base URL for a local Ollama server (Qwen, etc.).
        ollama_model: Default local model id.
        use_fake_llm: Use the deterministic offline LLM (tests/no-keys mode).
        working_memory_ttl_seconds: TTL for Redis working memory entries.
        heartbeat_interval_seconds: How often brains report a heartbeat.
        heartbeat_timeout_seconds: After this with no heartbeat a brain is stale.
    """

    model_config = SettingsConfigDict(
        env_prefix="BLVCKSHELL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    log_level: str = "INFO"

    redis_url: str = "redis://localhost:6379/0"
    use_in_memory_bus: bool = False

    supabase_url: str | None = None
    supabase_key: str | None = None

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    use_fake_llm: bool = False

    working_memory_ttl_seconds: int = Field(default=86_400, ge=1)
    heartbeat_interval_seconds: int = Field(default=15, ge=1)
    heartbeat_timeout_seconds: int = Field(default=45, ge=1)

    @property
    def supabase_enabled(self) -> bool:
        """Whether Supabase credentials are configured."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def anthropic_enabled(self) -> bool:
        """Whether the Anthropic API is configured."""
        return bool(self.anthropic_api_key) and not self.use_fake_llm


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached :class:`Settings` instance."""
    return Settings()
