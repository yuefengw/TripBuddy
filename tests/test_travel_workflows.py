import pytest

from app.models.travel import TripContextMemory, UserProfileMemory
from app.services.travel_llm_service import travel_llm_service
from app.services.travel_multi_agent_service import TravelMultiAgentService
from app.services.travel_plan_execute_service import TravelPlanExecuteService
from app.services.travel_workflow_service import TravelWorkflowService


def test_trip_planning_workflow_contains_steps():
    service = TravelWorkflowService()

    result = service.trip_planning_workflow(
        "帮我规划 4 天重庆美食行程",
        UserProfileMemory(pace_preference="慢节奏"),
        TripContextMemory(destination="重庆", duration_days=4, interests=["美食"]),
    )

    assert "# 旅行规划 Workflow" in result.answer
    assert "## Step 3: 行程骨架" in result.answer
    assert result.metadata["destination"] == "重庆"


def test_trip_replanning_workflow_contains_steps():
    service = TravelWorkflowService()

    result = service.trip_replanning_workflow(
        "我后天去杭州，但预报下雨，原本西湖一日游怎么重排",
        UserProfileMemory(pace_preference="慢节奏"),
        TripContextMemory(destination="杭州", current_plan="Day1 西湖步行 + 雷峰塔"),
    )

    assert "# 行程重规划 Workflow" in result.answer
    assert "## Step 4: 更新后的建议安排" in result.answer
    assert result.metadata["updated_plan"] is True


@pytest.mark.asyncio
async def test_multi_agent_output_includes_roles(monkeypatch):
    monkeypatch.setattr(travel_llm_service, "is_available", lambda: False)
    service = TravelMultiAgentService()

    answer, metadata = await service.run(
        "东京和大阪哪个更适合带 6 岁孩子玩 5 天，预算 1 万，请给两个方案比较",
        UserProfileMemory(companion_preference=["亲子"]),
        TripContextMemory(duration_days=5, companions=["带娃"]),
    )

    assert "Lead Planner" in answer
    assert "Destination Researcher" in answer
    assert metadata["roles"] == 5


@pytest.mark.asyncio
async def test_plan_execute_output_contains_steps(monkeypatch):
    monkeypatch.setattr(travel_llm_service, "is_available", lambda: False)
    service = TravelPlanExecuteService()

    answer, metadata = await service.run(
        "我后天去杭州，但预报下雨，原本西湖一日游怎么重排",
        UserProfileMemory(pace_preference="慢节奏"),
        TripContextMemory(destination="杭州", current_plan="Day1 西湖步行 + 雷峰塔"),
    )

    assert "Step 1" in answer
    assert "最终执行建议" in answer
    assert metadata["updated_plan"] is True
