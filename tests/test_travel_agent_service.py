import pytest

from app.models.travel import IntentRouteResult
from app.services.travel_agent_service import TravelAgentService
from app.services.travel_llm_service import travel_llm_service
from app.services.travel_memory_service import TravelMemoryService


@pytest.mark.asyncio
async def test_travel_agent_query_returns_route_and_answer(monkeypatch, tmp_path):
    temp_memory = TravelMemoryService(str(tmp_path / "memory.json"))
    monkeypatch.setattr("app.services.travel_agent_service.travel_memory_service", temp_memory)
    monkeypatch.setattr("app.tools.travel_tools.travel_memory_service", temp_memory)
    monkeypatch.setattr(travel_llm_service, "is_available", lambda: False)

    async def fake_route(*args, **kwargs):
        return IntentRouteResult(
            intent="trip_planning",
            route_type="workflow",
            selected_workflow="trip_planning_workflow",
            confidence=0.9,
            reason="test stub",
        )

    monkeypatch.setattr("app.services.travel_agent_service.travel_intent_service.route", fake_route)

    service = TravelAgentService()
    result = await service.query(
        question="帮我做一个 4 天重庆美食行程，预算 3000",
        session_id="test-session",
    )

    assert result.route.route_type == "workflow"
    assert result.route.selected_workflow == "trip_planning_workflow"
    assert "旅行规划 Workflow" in result.answer
    assert temp_memory.get_session_history("test-session")
