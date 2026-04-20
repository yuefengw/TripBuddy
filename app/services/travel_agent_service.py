"""Unified travel agent orchestrator for the /api/chat entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Optional

from loguru import logger

from app.models.travel import IntentRouteResult, TravelAgentResult, TripContextMemory, UserProfileMemory
from app.services.travel_intent_service import travel_intent_service
from app.services.travel_llm_service import travel_llm_service
from app.services.travel_memory_service import travel_memory_service
from app.services.travel_multi_agent_service import travel_multi_agent_service
from app.services.travel_plan_execute_service import travel_plan_execute_service
from app.services.travel_workflow_service import travel_workflow_service
from app.tools import retrieve_knowledge


@dataclass
class PreparedTravelRequest:
    """Internal execution bundle shared by sync and stream paths."""

    route: IntentRouteResult
    user_profile: UserProfileMemory
    trip_context: TripContextMemory
    session_history: list[Dict[str, Any]]
    draft: str
    metadata: Dict[str, Any]
    knowledge_context: str


class TravelAgentService:
    """Main orchestration service that routes and executes travel requests."""

    async def query(
        self,
        question: str,
        session_id: str,
        user_profile: Optional[Dict[str, Any]] = None,
        trip_context: Optional[Dict[str, Any]] = None,
        conversation_mode: Optional[str] = None,
    ) -> TravelAgentResult:
        logger.info(f"[session {session_id}] Travel agent received query: {question}")

        prepared = await self._prepare_request(
            question=question,
            session_id=session_id,
            user_profile=user_profile,
            trip_context=trip_context,
            conversation_mode=conversation_mode,
        )
        answer, metadata = await travel_llm_service.generate_final_answer(
            question=question,
            route=prepared.route,
            user_profile=prepared.user_profile,
            trip_context=prepared.trip_context,
            session_history=prepared.session_history,
            draft=prepared.draft,
            knowledge_context=prepared.knowledge_context,
            metadata=prepared.metadata,
        )

        travel_memory_service.append_turn(session_id, question, answer, prepared.route)
        travel_memory_service.remember_trip_output(session_id, answer, prepared.route)

        latest_profile = travel_memory_service.get_user_profile(session_id)
        latest_trip = travel_memory_service.get_trip_context(session_id)
        return TravelAgentResult(
            answer=answer,
            route=prepared.route,
            user_profile=latest_profile,
            trip_context=latest_trip,
            metadata=metadata,
        )

    async def query_stream(
        self,
        question: str,
        session_id: str,
        user_profile: Optional[Dict[str, Any]] = None,
        trip_context: Optional[Dict[str, Any]] = None,
        conversation_mode: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        prepared = await self._prepare_request(
            question=question,
            session_id=session_id,
            user_profile=user_profile,
            trip_context=trip_context,
            conversation_mode=conversation_mode,
        )

        yield {
            "type": "route",
            "data": {
                "intent": prepared.route.intent,
                "route_type": prepared.route.route_type,
                "selected_workflow": prepared.route.selected_workflow,
                "confidence": prepared.route.confidence,
            },
        }

        collected_chunks: list[str] = []
        async for chunk in travel_llm_service.stream_final_answer(
            question=question,
            route=prepared.route,
            user_profile=prepared.user_profile,
            trip_context=prepared.trip_context,
            session_history=prepared.session_history,
            draft=prepared.draft,
            knowledge_context=prepared.knowledge_context,
            metadata=prepared.metadata,
        ):
            collected_chunks.append(chunk)
            yield {"type": "content", "data": chunk}

        answer = "".join(collected_chunks).strip() or prepared.draft
        travel_memory_service.append_turn(session_id, question, answer, prepared.route)
        travel_memory_service.remember_trip_output(session_id, answer, prepared.route)

        latest_profile = travel_memory_service.get_user_profile(session_id)
        latest_trip = travel_memory_service.get_trip_context(session_id)
        final_metadata = dict(prepared.metadata)
        final_metadata.setdefault("llm_enabled", travel_llm_service.is_available())
        final_metadata.setdefault(
            "generation_mode",
            "llm_stream" if travel_llm_service.is_available() else "template_fallback",
        )
        final_metadata.setdefault("llm_used", travel_llm_service.is_available())

        yield {
            "type": "complete",
            "data": {
                "answer": answer,
                "route": prepared.route.model_dump(),
                "trip_context": latest_trip.model_dump(),
                "user_profile": latest_profile.model_dump(),
                "metadata": final_metadata,
            },
        }

    def get_session_history(self, session_id: str) -> list:
        return travel_memory_service.get_session_history(session_id)

    def clear_session(self, session_id: str) -> bool:
        return travel_memory_service.clear_session(session_id)

    async def _prepare_request(
        self,
        *,
        question: str,
        session_id: str,
        user_profile: Optional[Dict[str, Any]],
        trip_context: Optional[Dict[str, Any]],
        conversation_mode: Optional[str],
    ) -> PreparedTravelRequest:
        travel_memory_service.merge_memories(
            session_id, user_profile=user_profile, trip_context=trip_context
        )
        learned_profile, learned_trip = travel_memory_service.learn_from_question(session_id, question)
        session_history = travel_memory_service.get_session_history(session_id)

        route = await travel_intent_service.route(
            question=question,
            user_profile=learned_profile,
            trip_context=learned_trip,
            conversation_mode=conversation_mode,
            session_history=session_history,
        )

        metadata: Dict[str, Any] = {"route_reason": route.reason}
        knowledge_context = ""

        if route.route_type == "knowledge":
            workflow_result = travel_workflow_service.answer_knowledge_question(
                question, learned_profile, learned_trip
            )
            draft = workflow_result.answer
            metadata.update(workflow_result.metadata)
            knowledge_context = self._retrieve_knowledge_context(question)
        elif route.route_type == "workflow":
            workflow_result = travel_workflow_service.run_workflow(
                route.selected_workflow or "trip_planning_workflow",
                question,
                learned_profile,
                learned_trip,
            )
            draft = workflow_result.answer
            metadata.update(workflow_result.metadata)
            knowledge_context = self._retrieve_knowledge_context(question)
        elif route.route_type == "multi_agent":
            draft, multi_metadata = await travel_multi_agent_service.run(
                question, learned_profile, learned_trip
            )
            metadata.update(multi_metadata)
            knowledge_context = self._retrieve_knowledge_context(question)
        else:
            draft, plan_metadata = await travel_plan_execute_service.run(
                question, learned_profile, learned_trip
            )
            metadata.update(plan_metadata)
            knowledge_context = self._retrieve_knowledge_context(question)

        metadata["knowledge_context_used"] = bool(knowledge_context)
        return PreparedTravelRequest(
            route=route,
            user_profile=learned_profile,
            trip_context=learned_trip,
            session_history=session_history,
            draft=draft,
            metadata=metadata,
            knowledge_context=knowledge_context,
        )

    @staticmethod
    def _retrieve_knowledge_context(question: str) -> str:
        try:
            result = retrieve_knowledge.invoke({"query": question})
        except Exception as exc:
            logger.warning(f"Knowledge retrieval context load failed: {exc}")
            return ""

        if isinstance(result, tuple):
            return str(result[0] or "")
        if isinstance(result, dict):
            if "content" in result:
                return str(result["content"] or "")
            return str(result)
        return str(result or "")


travel_agent_service = TravelAgentService()
