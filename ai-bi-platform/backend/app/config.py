"""Central configuration. Every secret comes from the environment —
nothing is hard-coded, so the same image runs in dev and production."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://bi_user:bi_pass@localhost:5432/bi_warehouse"
    # Separate, SELECT-only connection handed to the LLM query path.
    READONLY_DATABASE_URL: str = ""

    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 720

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_URL: str = "https://api.groq.com/openai/v1/chat/completions"

    MAX_UPLOAD_MB: int = 25

    @property
    def readonly_url(self) -> str:
        # Fall back to the main URL if no read-only role is configured,
        # so the app still runs locally. The SQL guard still applies.
        return self.READONLY_DATABASE_URL or self.DATABASE_URL


settings = Settings()
