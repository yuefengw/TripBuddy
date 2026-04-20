"""时间查询技能"""

from datetime import datetime
from typing import Any, List
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from loguru import logger

from app.skills.base import Skill, SkillConfig


class TimeQuerySkill(Skill):
    """时间查询技能 - 获取当前时间信息"""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="time_query",
            description="获取当前时间和日期信息",
            enabled=True,
            mcp_server=None,
            metadata={"category": "utility", "priority": "high"}
        )

    def get_tools(self) -> List[Any]:
        return [get_current_time]


@tool
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """获取当前时间

    当用户询问"现在几点"、"今天星期几"、"今天日期"等时间相关问题时，使用此工具。

    Args:
        timezone: 时区，默认为 Asia/Shanghai（北京时间）

    Returns:
        str: 格式化的当前时间信息
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return now.strftime('%Y-%m-%d %H:%M:%S')

    except Exception as e:
        logger.error(f"时间查询工具调用失败: {e}")
        return f"获取时间失败: {str(e)}"
