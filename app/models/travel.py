"""Travel domain models used by the unified travel agent."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


RouteType = Literal["knowledge", "workflow", "multi_agent", "plan_execute"]


class UserProfileMemory(BaseModel):
    """Long-term user preference memory."""

    budget_preference: Optional[str] = Field(default=None, description="Budget range or preference")
    travel_style: List[str] = Field(default_factory=list, description="Travel style tags")
    dietary_preferences: List[str] = Field(
        default_factory=list, description="Food restrictions or preferences"
    )
    pace_preference: Optional[str] = Field(default=None, description="Preferred trip pace")
    accommodation_preference: Optional[str] = Field(
        default=None, description="Preferred stay type or area"
    )
    companion_preference: List[str] = Field(
        default_factory=list, description="Typical travel companions"
    )
    preferred_destinations: List[str] = Field(
        default_factory=list, description="Frequently mentioned destinations"
    )
    notes: List[str] = Field(default_factory=list, description="Additional stable user notes")


class TripContextMemory(BaseModel):
    """Current trip state used for re-planning and context injection."""

    origin: Optional[str] = None
    destination: Optional[str] = None
    travel_month: Optional[str] = None
    duration_days: Optional[int] = None
    budget_amount: Optional[int] = None
    companions: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    current_plan: Optional[str] = None
    must_do: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)


class IntentRouteResult(BaseModel):
    """Intent routing result for the unified entrypoint."""

    intent: str
    route_type: RouteType
    selected_workflow: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reason: str = ""


class TravelAgentResult(BaseModel):
    """Full response payload returned by the travel agent."""

    answer: str
    route: IntentRouteResult
    user_profile: UserProfileMemory
    trip_context: TripContextMemory
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionHistoryEntry(BaseModel):
    """Persisted session history entry."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: str
    route_type: Optional[str] = None
    intent: Optional[str] = None

