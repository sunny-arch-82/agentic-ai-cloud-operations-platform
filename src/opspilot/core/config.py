"""Validated environment configuration. Model secrets never enter reports."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="OPSPILOT_")

    mode: Literal["demo", "openai"] = "demo"
    database_url: SecretStr = SecretStr("postgresql+psycopg://opspilot@localhost:5432/opspilot")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=512, ge=64, le=1536)
    retrieval_mode: Literal["semantic", "lexical", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=10)
    max_model_calls: int = Field(default=8, ge=1, le=20)
    max_tool_calls: int = Field(default=12, ge=1, le=30)
    max_revisions: int = Field(default=1, ge=0, le=2)
    deadline_seconds: float = Field(default=90, gt=0, le=300)
    provider_timeout_seconds: float = Field(default=25, gt=0, le=60)
    tool_timeout_seconds: float = Field(default=15, gt=0, le=60)
    context_chars: int = Field(default=24000, ge=2000, le=60000)
    log_level: str = "INFO"
    data_dir: Path = Path("data/sample")

    @model_validator(mode="after")
    def provider_key(self):
        if self.mode == "openai" and (
            not self.openai_api_key or not self.openai_api_key.get_secret_value().strip()
        ):
            raise ValueError("OPENAI_API_KEY is required when OPSPILOT_MODE=openai")
        return self

    @property
    def embedding_key(self) -> str:
        name = "hashing-demo-v1" if self.mode == "demo" else self.embedding_model
        return f"{self.mode}:{name}:{self.embedding_dimensions}"

    @property
    def model_id(self) -> str:
        return "deterministic-demo-v1" if self.mode == "demo" else self.llm_model
