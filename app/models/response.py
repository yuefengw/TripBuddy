"""Response models used by the FastAPI API layer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatResponse(BaseModel):
    """Basic chat response."""

    answer: str = Field(..., description="Assistant answer")
    session_id: str = Field(..., description="Session ID")


class SessionInfoResponse(BaseModel):
    """Session history response."""

    session_id: str = Field(..., description="Session ID")
    message_count: int = Field(..., description="Number of stored messages")
    history: List[Dict[str, str]] = Field(..., description="Conversation history")


class ApiResponse(BaseModel):
    """Generic API response."""

    status: str = Field(..., description="Status")
    message: str = Field(..., description="Message")
    data: Optional[Any] = Field(default=None, description="Payload")


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str = Field(..., description="Health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
