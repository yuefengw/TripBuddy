from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
import pytest

from app.models.travel import IntentRouteResult, TripContextMemory, UserProfileMemory
from app.services.travel_llm_service import travel_llm_service
from app.tools.live_search_tools import scrape_web_page, search_web_live


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        return _FakeResponse(self._responses.pop(0))

    def post(self, *args, **kwargs):
        return _FakeResponse(self._responses.pop(0))


def test_search_web_live_formats_results(monkeypatch):
    monkeypatch.setattr("app.tools.live_search_tools.config.serpapi_api_key", "test-key")
    monkeypatch.setattr(
        "app.tools.live_search_tools.httpx.Client",
        lambda timeout: _FakeClient(
            [
                {
                    "answer_box": {"answer": "Japan eVisa depends on nationality"},
                    "organic_results": [
                        {
                            "title": "Official visa page",
                            "link": "https://example.com/visa",
                            "source": "Example",
                            "snippet": "Check the latest visa requirement here.",
                        }
                    ],
                }
            ]
        ),
    )

    result = search_web_live.invoke({"query": "Japan visa requirement"})

    assert "Live search results for" in result
    assert "https://example.com/visa" in result


def test_scrape_web_page_formats_content(monkeypatch):
    monkeypatch.setattr("app.tools.live_search_tools.config.firecrawl_api_key", "test-key")
    monkeypatch.setattr(
        "app.tools.live_search_tools.httpx.Client",
        lambda timeout: _FakeClient(
            [
                {
                    "data": {
                        "markdown": "# Visa\nBring your passport.",
                        "metadata": {
                            "title": "Visa Guide",
                            "description": "Official instructions",
                        },
                    }
                }
            ]
        ),
    )

    result = scrape_web_page.invoke({"url": "https://example.com/visa"})

    assert "Scraped page" in result
    assert "Visa Guide" in result
    assert "Bring your passport" in result


class _FakeBoundModel:
    def __init__(self):
        self._calls = 0

    async def ainvoke(self, messages):
        self._calls += 1
        if self._calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "fake_live_tool",
                        "args": {"query": "latest Japan visa policy"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )
        return AIMessage(content="这是最终答案，并结合了工具结果。")


class _FakeModel:
    def bind_tools(self, tools, **kwargs):
        return _FakeBoundModel()

    async def ainvoke(self, messages):
        return AIMessage(content="这是最终答案，并结合了工具结果。")


@tool
def fake_live_tool(query: str) -> str:
    """Return a fake live-search result."""

    return f"live result for {query}"


@pytest.mark.asyncio
async def test_generate_final_answer_uses_tool_loop(monkeypatch):
    monkeypatch.setattr(travel_llm_service, "is_available", lambda: True)
    monkeypatch.setattr(travel_llm_service, "_create_model", lambda **kwargs: _FakeModel())
    monkeypatch.setattr(
        "app.services.travel_llm_service.skill_registry.get_all_tools",
        lambda: [fake_live_tool],
    )

    answer, metadata = await travel_llm_service.generate_final_answer(
        question="日本签证最近有什么变化？",
        route=IntentRouteResult(
            intent="travel_knowledge",
            route_type="knowledge",
            selected_workflow=None,
            confidence=0.9,
            reason="test",
        ),
        user_profile=UserProfileMemory(),
        trip_context=TripContextMemory(destination="日本"),
        session_history=[],
        draft="草稿答案",
        knowledge_context="",
        metadata={},
    )

    assert "最终答案" in answer
    assert metadata["tool_used"] is True
    assert "fake_live_tool" in metadata["tool_calls"]
