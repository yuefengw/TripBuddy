"""Legacy AIOps request/response models kept for backward compatibility."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AIOpsRequest(BaseModel):
    """Legacy AIOps request."""

    session_id: Optional[str] = Field(default="default", description="Session ID")

    class Config:
        json_schema_extra = {"example": {"session_id": "session-123"}}


class DiagnosisResponse(BaseModel):
    """Legacy AIOps response container."""

    code: int = 200
    message: str = "success"
    data: Dict[str, Any]
