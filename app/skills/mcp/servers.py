"""MCP 技能封装 - 封装 MCP 协议工具为统一技能"""

from typing import Any, Dict, List, Optional

from loguru import logger

from app.agent.mcp_client import get_mcp_client_with_retry
from app.skills.base import Skill, SkillConfig


# MCP 服务器名称到技能名称的映射
MCP_SERVER_TO_SKILL: Dict[str, str] = {
    "cls": "log_query",
    "monitor": "monitor_query",
}

# 技能名称到 MCP 服务器名称的映射
SKILL_TO_MCP_SERVER: Dict[str, str] = {
    v: k for k, v in MCP_SERVER_TO_SKILL.items()
}


class MCPSkill(Skill):
    """MCP 技能封装

    将 MCP 服务器提供的工具封装为统一的 Skill 接口，
    支持延迟初始化和工具缓存。
    """

    def __init__(self, skill_name: str, mcp_server_name: str) -> None:
        """初始化 MCP 技能

        Args:
            skill_name: 技能名称（如 "log_query"）
            mcp_server_name: MCP 服务器名称（如 "cls"）
        """
        self._skill_name = skill_name
        self._mcp_server_name = mcp_server_name
        self._tools: Optional[List[Any]] = None
        self._config = SkillConfig(
            name=skill_name,
            description=f"MCP 技能 - 服务器: {mcp_server_name}",
            enabled=True,
            mcp_server=mcp_server_name,
            metadata={
                "category": "mcp",
                "server": mcp_server_name,
            }
        )

    @property
    def config(self) -> SkillConfig:
        return self._config

    async def initialize(self) -> None:
        """异步初始化 - 从 MCP 服务器获取工具列表"""
        if self._tools is not None:
            return

        try:
            logger.info(f"初始化 MCP 技能 '{self._skill_name}'...")
            mcp_client = await get_mcp_client_with_retry()
            self._tools = await mcp_client.get_tools()
            logger.info(
                f"MCP 技能 '{self._skill_name}' 初始化完成，"
                f"提供 {len(self._tools)} 个工具"
            )
        except Exception as e:
            logger.error(f"初始化 MCP 技能 '{self._skill_name}' 失败: {e}")
            self._tools = []

    def get_tools(self) -> List[Any]:
        """获取该 MCP 服务器提供的所有工具

        注意：必须在 initialize() 之后调用，或使用 await get_tools_async()

        Returns:
            List[Any]: 工具列表
        """
        if self._tools is None:
            logger.warning(
                f"MCP 技能 '{self._skill_name}' 未初始化，"
                f"请先调用 initialize() 或使用 get_tools_async()"
            )
            return []
        return self._tools

    async def get_tools_async(self) -> List[Any]:
        """异步获取工具列表（自动初始化）"""
        await self.initialize()
        return self.get_tools()

    async def cleanup(self) -> None:
        """清理资源"""
        self._tools = None
        logger.debug(f"MCP 技能 '{self._skill_name}' 资源已清理")


class LogQuerySkill(MCPSkill):
    """日志查询技能 - 封装 CLS MCP 服务器工具"""

    def __init__(self) -> None:
        super().__init__(
            skill_name="log_query",
            mcp_server_name="cls"
        )
        self._config.description = (
            "日志查询服务 - 支持搜索服务日志、分析日志模式、"
            "获取主题信息等"
        )


class MonitorQuerySkill(MCPSkill):
    """监控查询技能 - 封装 Monitor MCP 服务器工具"""

    def __init__(self) -> None:
        super().__init__(
            skill_name="monitor_query",
            mcp_server_name="monitor"
        )
        self._config.description = (
            "监控数据服务 - 支持查询 CPU、内存、进程等指标，"
            "获取服务信息和历史工单"
        )
