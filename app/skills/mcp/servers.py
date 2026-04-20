"""MCP skill wrappers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from app.agent.mcp_client import get_mcp_client_with_retry
from app.skills.base import Skill, SkillConfig


MCP_SERVER_TO_SKILL: Dict[str, str] = {
    "cls": "log_query",
    "monitor": "monitor_query",
    "travel": "travel_live_support",
}

SKILL_TO_MCP_SERVER: Dict[str, str] = {skill_name: server for server, skill_name in MCP_SERVER_TO_SKILL.items()}


class MCPSkill(Skill):
    """Base wrapper around MCP-provided tools."""

    def __init__(self, skill_name: str, mcp_server_name: str, description: Optional[str] = None) -> None:
        self._skill_name = skill_name
        self._mcp_server_name = mcp_server_name
        self._description = description or f"MCP tools from {mcp_server_name}"
        self._tools: Optional[List[Any]] = None
        self._config = SkillConfig(
            name=skill_name,
            description=self._description,
            enabled=True,
            mcp_server=mcp_server_name,
            metadata={"category": "mcp", "server": mcp_server_name},
        )

    @property
    def config(self) -> SkillConfig:
        return self._config

    async def initialize(self) -> None:
        if self._tools is not None:
            return
        try:
            logger.info(f"Initializing MCP skill '{self._skill_name}' from server '{self._mcp_server_name}'")
            client = await get_mcp_client_with_retry()
            self._tools = await client.get_tools()
            logger.info(
                f"MCP skill '{self._skill_name}' initialized with {len(self._tools or [])} tools"
            )
        except Exception as exc:
            logger.warning(
                f"MCP skill '{self._skill_name}' failed to initialize, falling back to no tools: {exc}"
            )
            self._tools = []

    def get_tools(self) -> List[Any]:
        if self._tools is None:
            logger.warning(f"MCP skill '{self._skill_name}' requested before initialize()")
            return []
        return self._tools

    async def cleanup(self) -> None:
        self._tools = None


class LogQuerySkill(MCPSkill):
    def __init__(self) -> None:
        super().__init__(
            skill_name="log_query",
            mcp_server_name="cls",
            description="AIOps log query tools served over MCP",
        )


class MonitorQuerySkill(MCPSkill):
    def __init__(self) -> None:
        super().__init__(
            skill_name="monitor_query",
            mcp_server_name="monitor",
            description="AIOps monitoring tools served over MCP",
        )


class TravelLiveSupportSkill(MCPSkill):
    def __init__(self) -> None:
        super().__init__(
            skill_name="travel_live_support",
            mcp_server_name="travel",
            description="Mock travel weather, FX, visa and POI tools served over MCP",
        )
