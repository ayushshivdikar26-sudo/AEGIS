"""
AEGIS Configuration & Settings (Backend/app/config.py)
Type-safe application settings validated at start-up with strict production guardrails (PRD Part 2c s3).
"""

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default="development", description="development | production")
    SUPABASE_URL: str = Field(default="https://localhost.supabase.co", description="Supabase project URL")
    SUPABASE_PUBLISHABLE_KEY: str = Field(default="mock-publishable-key", description="Anon / publishable key")
    SUPABASE_SECRET_KEY: str = Field(default="mock-secret-key", description="Service role key for admin tasks only")
    SUPABASE_JWT_SECRET: str = Field(default="", description="Optional legacy HS256 secret fallback")

    # Redis for rate limiting (Upstash Redis or local)
    RATE_LIMIT_STORAGE_URI: str = Field(
        default="redis://localhost:6379/0", description="Redis URI for distributed limits"
    )

    # CORS & Security
    ALLOWED_ORIGINS: list[str] | str = Field(default_factory=list, description="Allowed CORS origins")
    COOKIE_SECURE: bool = Field(default=False, description="Enforce Secure flag on cookies (must be True in prod)")
    TRUSTED_PROXY_COUNT: int = Field(default=0, ge=0, description="Number of reverse proxies to trust for client IP")

    # AI Analyzer (Milestone M8 - Deferred)
    AI_ENABLED: bool = Field(default=False, description="Enable optional Groq LLM explanations")
    GROQ_API_KEY: str = Field(default="", description="Groq API key if AI enabled")
    GROQ_MODEL: str = Field(default="", description="Groq model name")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        env = self.ENVIRONMENT.lower()
        if env == "production":
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be true in production environments.")

            if "*" in self.ALLOWED_ORIGINS:
                raise ValueError("Wildcard origins '*' are prohibited in production CORS configuration.")

            if not self.SUPABASE_URL.startswith("https://"):
                raise ValueError("SUPABASE_URL must use HTTPS in production.")

            if "your-project" in self.SUPABASE_URL or "localhost" in self.SUPABASE_URL:
                raise ValueError("SUPABASE_URL cannot use placeholder or localhost in production.")

            if not self.SUPABASE_PUBLISHABLE_KEY or "your-" in self.SUPABASE_PUBLISHABLE_KEY:
                raise ValueError("Valid SUPABASE_PUBLISHABLE_KEY is required in production.")

            if not self.SUPABASE_SECRET_KEY or "your-" in self.SUPABASE_SECRET_KEY:
                raise ValueError("Valid SUPABASE_SECRET_KEY is required in production.")

        return self


settings = Settings()
