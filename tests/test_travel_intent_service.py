import pytest

from app.models.travel import TripContextMemory, UserProfileMemory
from app.services.travel_intent_service import IntentClassification, TravelIntentService
from app.services.travel_llm_service import travel_llm_service


@pytest.mark.asyncio
async def test_route_to_trip_planning_workflow(monkeypatch):
    service = TravelIntentService()
    monkeypatch.setattr(travel_llm_service, "is_available", lambda: True)

    async def fake_classify(**kwargs):
        return IntentClassification(
            intent="trip_planning",
            route_type="workflow",
            selected_workflow="trip_planning_workflow",
            confidence=0.88,
            reason="planning request with stable output",
        )

    monkeypatch.setattr(service, "_classify_with_llm", fake_classify)

    result = await service.route(
        "帮我做一个 4 天重庆美食行程，预算 3000",
        UserProfileMemory(),
        TripContextMemory(),
    )

    assert result.route_type == "workflow"
    assert result.selected_workflow == "trip_planning_workflow"


@pytest.mark.asyncio
async def test_deep_search_routes_to_multi_agent():
    service = TravelIntentService()

    result = await service.route(
        "东京和大阪哪个更适合带 6 岁孩子玩 5 天，预算 1 万，请给两个方案比较",
        UserProfileMemory(),
        TripContextMemory(),
        conversation_mode="deep_search",
    )

    assert result.route_type == "multi_agent"
    assert result.intent == "complex_travel_consulting"


@pytest.mark.asyncio
async def test_route_to_plan_execute(monkeypatch):
    service = TravelIntentService()
    monkeypatch.setattr(travel_llm_service, "is_available", lambda: True)

    async def fake_classify(**kwargs):
        return IntentClassification(
            intent="complex_replanning",
            route_type="plan_execute",
            selected_workflow=None,
            confidence=0.9,
            reason="needs multi-step dependent replan",
        )

    monkeypatch.setattr(service, "_classify_with_llm", fake_classify)

    result = await service.route(
        "我后天去杭州，但预报下雨，原本西湖一日游怎么重排",
        UserProfileMemory(),
        TripContextMemory(destination="杭州"),
    )

    assert result.route_type == "plan_execute"
