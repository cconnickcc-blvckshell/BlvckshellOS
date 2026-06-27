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
        run_workers_in_process: Run specialist brains inside the harness process.
            Set false to run each brain in its own container against shared Redis.
        worker_brain_modules: Comma-separated ``module:ClassName`` import paths
            for the brains the harness loads in-process. Adding a brain is a
            config change, not a code change.
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
        frontend_url: Public frontend URL for CORS (production Vercel deployment).
        upwork_client_id: Upwork OAuth2 app client id.
        upwork_client_secret: Upwork OAuth2 app client secret.
        upwork_redirect_uri: Upwork OAuth2 app redirect URI.
        upwork_refresh_token: Long-lived Upwork OAuth2 refresh token, obtained
            once via the authorization-code flow outside the harness.
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
    run_workers_in_process: bool = True
    worker_brain_modules: str = Field(
        default=(
            "brains.blvckbot.brain:BlvckbotBrain,"
            "brains.blvckbot.research:ResearchBrain,"
            "brains.blvckbot.proposal:ProposalBrain,"
            "brains.blvckbot.build:BuildBrain,"
            "brains.blvckbot.ops:OpsBrain,"
            "brains.examples.venture:VentureBrain,"
            "brains.examples.commander:CommanderBrain,"
            "brains.examples.capital:CapitalBrain"
        ),
        description="Comma-separated module:ClassName paths for in-process brains.",
    )

    supabase_url: str | None = None
    supabase_key: str | None = None

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"
    # Org input-tokens-per-minute budget. The harness paces Anthropic calls to
    # stay under this so concurrent web-search-heavy brains don't 429. Set to
    # your tier's actual cap (with headroom); 0 disables pacing.
    anthropic_tokens_per_minute: int = 28_000

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    ollama_base_url: str | None = None
    ollama_url: str | None = None
    ollama_model: str = "qwen2.5:72b"

    use_fake_llm: bool = False

    working_memory_ttl_seconds: int = Field(default=86_400, ge=1)
    heartbeat_interval_seconds: int = Field(default=15, ge=1)
    heartbeat_timeout_seconds: int = Field(default=45, ge=1)

    frontend_url: str | None = None

    upwork_client_id: str | None = None
    upwork_client_secret: str | None = None
    upwork_redirect_uri: str | None = None
    upwork_refresh_token: str | None = None

    @property
    def supabase_enabled(self) -> bool:
        """Whether Supabase credentials are configured."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def anthropic_enabled(self) -> bool:
        """Whether the Anthropic API is configured."""
        return bool(self.anthropic_api_key) and not self.use_fake_llm

    @property
    def openai_enabled(self) -> bool:
        """Whether the OpenAI API is configured."""
        return bool(self.openai_api_key) and not self.use_fake_llm

    @property
    def ollama_effective_url(self) -> str | None:
        """Resolved Ollama base URL (``ollama_base_url`` overrides ``ollama_url``)."""
        return self.ollama_base_url or self.ollama_url

    @property
    def ollama_enabled(self) -> bool:
        """Whether a local Ollama server URL is configured."""
        return bool(self.ollama_effective_url) and not self.use_fake_llm

    @property
    def upwork_enabled(self) -> bool:
        """Whether Upwork OAuth credentials are configured.

        The refresh token is the long-lived credential; client id/secret
        alone are not enough to call the API without completing the OAuth
        authorization-code flow once out of band.
        """
        return bool(
            self.upwork_client_id and self.upwork_client_secret and self.upwork_refresh_token
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached :class:`Settings` instance."""
    return Settings()
