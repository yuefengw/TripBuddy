"""Native time skill."""

from __future__ import annotations

from typing import Any, List

from app.skills.base import Skill, SkillConfig
from app.tools.time_tool import get_current_time


class TimeQuerySkill(Skill):
    """Expose current-time lookup as a skill."""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="time_query",
            description="获取当前时间和日期信息",
            enabled=True,
            metadata={"category": "utility", "priority": "medium"},
        )

    def get_tools(self) -> List[Any]:
        return [get_current_time]
