"""Travel-specific native skills."""

from __future__ import annotations

from typing import Any, List

from app.skills.base import Skill, SkillConfig
from app.tools.travel_tools import (
    build_itinerary_outline,
    build_packing_checklist,
    build_trip_replan_options,
    estimate_trip_budget,
    summarize_preference_memory,
)


class TravelKnowledgeSkill(Skill):
    """Travel knowledge retrieval skill."""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="travel_knowledge_skill",
            description="旅行知识检索与目的地问答",
            enabled=True,
            metadata={"category": "travel", "priority": "high"},
        )

    def get_tools(self) -> List[Any]:
        from app.skills.native.knowledge import retrieve_knowledge

        return [retrieve_knowledge]


class ItineraryBuilderSkill(Skill):
    """Skill for itinerary construction."""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="itinerary_builder_skill",
            description="基于目的地、天数和偏好生成行程大纲",
            enabled=True,
            metadata={"category": "travel", "priority": "high"},
        )

    def get_tools(self) -> List[Any]:
        return [build_itinerary_outline]


class BudgetEstimatorSkill(Skill):
    """Skill for budget estimation."""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="budget_estimator_skill",
            description="生成交通、住宿、餐饮、门票预算拆分",
            enabled=True,
            metadata={"category": "travel", "priority": "high"},
        )

    def get_tools(self) -> List[Any]:
        return [estimate_trip_budget]


class PackingChecklistSkill(Skill):
    """Skill for packing and preparation checklists."""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="packing_checklist_skill",
            description="按目的地和季节输出出行准备清单",
            enabled=True,
            metadata={"category": "travel", "priority": "high"},
        )

    def get_tools(self) -> List[Any]:
        return [build_packing_checklist]


class PreferenceMemorySkill(Skill):
    """Skill exposing persisted preference memory."""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="preference_memory_skill",
            description="读取当前会话的偏好画像与用户记忆",
            enabled=True,
            metadata={"category": "memory", "priority": "medium"},
        )

    def get_tools(self) -> List[Any]:
        return [summarize_preference_memory]


class TripReplanSkill(Skill):
    """Skill for local fallback trip re-planning."""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="trip_replan_skill",
            description="根据异常情况生成旅行重规划建议",
            enabled=True,
            metadata={"category": "travel", "priority": "high"},
        )

    def get_tools(self) -> List[Any]:
        return [build_trip_replan_options]
