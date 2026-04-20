"""Request models for the public FastAPI endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Unified chat request."""

    id: str = Field(..., description="Session ID", alias="Id")
    question: str = Field(..., description="User question", alias="Question")
    user_profile: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional user profile memory injection", alias="userProfile"
    )
    trip_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional current trip context", alias="tripContext"
    )
    conversation_mode: Optional[str] = Field(
        default=None,
        description="Optional routing hint: standard_search, deep_search, multi_agent, plan_execute",
        alias="conversationMode",
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "Id": "session-123",
                "Question": "帮我做一个 4 天重庆美食行程，预算 3000",
                "userProfile": {"pace_preference": "慢节奏", "dietary_preferences": ["不吃辣"]},
                "tripContext": {"destination": "重庆", "duration_days": 4},
                "conversationMode": "standard_search",
            }
        }


class ClearRequest(BaseModel):
    """Clear-session request."""

    session_id: str = Field(..., description="Session ID", alias="sessionId")

    class Config:
        populate_by_name = True
