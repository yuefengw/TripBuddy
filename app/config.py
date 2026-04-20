"""Application settings."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TripBuddy Travel Agent"
    app_version: str = "2.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 9900

    dashscope_api_key: str = ""
    dashscope_model: str = "qwen-max"
    dashscope_embedding_model: str = "text-embedding-v4"

    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_timeout: int = 10000

    rag_top_k: int = 3
    rag_model: str = "qwen-max"
    chunk_max_size: int = 800
    chunk_overlap: int = 100

    mcp_cls_transport: str = "streamable-http"
    mcp_cls_url: str = "http://localhost:8003/mcp"
    mcp_monitor_transport: str = "streamable-http"
    mcp_monitor_url: str = "http://localhost:8004/mcp"
    mcp_travel_transport: str = "streamable-http"
    mcp_travel_url: str = "http://localhost:8005/mcp"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_value(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return bool(value)

    @property
    def mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        return {
            "cls": {
                "transport": self.mcp_cls_transport,
                "url": self.mcp_cls_url,
            },
            "monitor": {
                "transport": self.mcp_monitor_transport,
                "url": self.mcp_monitor_url,
            },
            "travel": {
                "transport": self.mcp_travel_transport,
                "url": self.mcp_travel_url,
            },
        }


config = Settings()
