"""Travel chat endpoints backed by the unified travel agent service."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.models.request import ChatRequest, ClearRequest
from app.models.response import ApiResponse, SessionInfoResponse
from app.services.travel_agent_service import travel_agent_service

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest):
    """Unified chat endpoint routed by travel intent."""

    try:
        logger.info(f"[session {request.id}] chat request: {request.question}")
        result = await travel_agent_service.query(
            question=request.question,
            session_id=request.id,
            user_profile=request.user_profile,
            trip_context=request.trip_context,
            conversation_mode=request.conversation_mode,
        )
        return {
            "code": 200,
            "message": "success",
            "data": {
                "success": True,
                "answer": result.answer,
                "route": result.route.model_dump(),
                "tripContext": result.trip_context.model_dump(),
                "userProfile": result.user_profile.model_dump(),
                "metadata": result.metadata,
                "errorMessage": None,
            },
        }
    except Exception as exc:
        logger.error(f"Chat endpoint failed: {exc}", exc_info=True)
        return {
            "code": 500,
            "message": "error",
            "data": {
                "success": False,
                "answer": None,
                "route": None,
                "tripContext": None,
                "userProfile": None,
                "metadata": None,
                "errorMessage": str(exc),
            },
        }


@router.post("/chat_stream")
async def chat_stream(request: ChatRequest):
    """SSE chat endpoint for streamed travel responses."""

    logger.info(f"[session {request.id}] stream chat request: {request.question}")

    async def event_generator():
        try:
            async for chunk in travel_agent_service.query_stream(
                question=request.question,
                session_id=request.id,
                user_profile=request.user_profile,
                trip_context=request.trip_context,
                conversation_mode=request.conversation_mode,
            ):
                chunk_type = chunk.get("type", "unknown")
                data = chunk.get("data")
                if chunk_type == "route":
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "route", "data": data}, ensure_ascii=False),
                    }
                elif chunk_type == "content":
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "content", "data": data}, ensure_ascii=False),
                    }
                elif chunk_type == "complete":
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "done", "data": data}, ensure_ascii=False),
                    }
                else:
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": chunk_type, "data": data}, ensure_ascii=False),
                    }
        except Exception as exc:
            logger.error(f"Stream chat endpoint failed: {exc}", exc_info=True)
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "data": str(exc)}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.post("/chat/clear", response_model=ApiResponse)
async def clear_session(request: ClearRequest):
    """Clear session history and current trip context."""

    try:
        success = travel_agent_service.clear_session(request.session_id)
        return ApiResponse(
            status="success" if success else "error",
            message="会话已清空" if success else "未找到需要清理的会话",
            data=None,
        )
    except Exception as exc:
        logger.error(f"Failed to clear session: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/chat/session/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(session_id: str) -> SessionInfoResponse:
    """Return persisted session history for the travel assistant."""

    try:
        history = travel_agent_service.get_session_history(session_id)
        return SessionInfoResponse(
            session_id=session_id,
            message_count=len(history),
            history=history,
        )
    except Exception as exc:
        logger.error(f"Failed to fetch session history: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
