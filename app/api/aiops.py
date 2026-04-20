"""Legacy AIOps streaming endpoint retained for compatibility."""

from __future__ import annotations

import json

from fastapi import APIRouter
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.models.aiops import AIOpsRequest
from app.services.aiops_service import aiops_service

router = APIRouter()


@router.post("/aiops")
async def diagnose_stream(request: AIOpsRequest):
    """Stream the legacy AIOps demo workflow."""

    session_id = request.session_id or "default"
    logger.info(f"[session {session_id}] legacy AIOps request received")

    async def event_generator():
        try:
            async for event in aiops_service.diagnose(session_id=session_id):
                yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}
                if event.get("type") in {"complete", "error"}:
                    break
        except Exception as exc:
            logger.error(f"Legacy AIOps stream failed: {exc}", exc_info=True)
            yield {
                "event": "message",
                "data": json.dumps(
                    {"type": "error", "stage": "exception", "message": f"诊断异常: {exc}"},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_generator())
