"""Environment-driven settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_username: str | None = None
    falkordb_password: str | None = None
    llm_provider: str = "claude_cli"
    llm_api_key: str | None = None
    llm_model: str | None = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"  # comma-separated; add your hosted web URL


settings = Settings()
