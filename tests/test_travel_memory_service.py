from app.services.travel_memory_service import TravelMemoryService


def test_memory_service_learns_preferences_and_trip_context(tmp_path):
    service = TravelMemoryService(str(tmp_path / "travel_memory.json"))

    profile, trip = service.learn_from_question(
        "session-1",
        "我不吃辣，喜欢慢节奏，帮我规划长沙 3 天，预算 3000",
    )

    assert "不吃辣" in profile.dietary_preferences
    assert profile.pace_preference == "慢节奏"
    assert trip.destination == "长沙"
    assert trip.duration_days == 3
    assert trip.budget_amount == 3000


def test_memory_service_appends_session_history(tmp_path):
    service = TravelMemoryService(str(tmp_path / "travel_memory.json"))
    service.append_turn(
        "session-2",
        "帮我规划成都 2 天",
        "这里是成都 2 天行程",
        type("Route", (), {"route_type": "workflow", "intent": "itinerary_generation"})(),
    )

    history = service.get_session_history("session-2")

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
