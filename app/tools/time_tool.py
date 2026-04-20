"""Time tool."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from loguru import logger


@tool
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """Get the current time in a given timezone."""

    try:
        return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as exc:
        logger.error(f"Time tool failed: {exc}")
        return f"获取时间失败: {exc}"
