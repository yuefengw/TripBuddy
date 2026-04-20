"""Skill loading and registry helpers."""

from app.skills.base import Skill, SkillConfig
from app.skills.mcp import LogQuerySkill, MonitorQuerySkill, TravelLiveSupportSkill
from app.skills.native import (
    BudgetEstimatorSkill,
    ItineraryBuilderSkill,
    KnowledgeRetrievalSkill,
    LiveSearchSkill,
    PackingChecklistSkill,
    PreferenceMemorySkill,
    TimeQuerySkill,
    TravelKnowledgeSkill,
    TripReplanSkill,
)
from app.skills.registry import SkillRegistry, skill_registry


async def load_skills(config_path: str = "app/config/skills.yaml") -> SkillRegistry:
    """Load and initialize all configured skills."""

    native_skills = [
        KnowledgeRetrievalSkill(),
        LiveSearchSkill(),
        TimeQuerySkill(),
        TravelKnowledgeSkill(),
        ItineraryBuilderSkill(),
        BudgetEstimatorSkill(),
        PackingChecklistSkill(),
        PreferenceMemorySkill(),
        TripReplanSkill(),
    ]
    for skill in native_skills:
        skill_registry.register(skill)

    mcp_skills = [
        LogQuerySkill(),
        MonitorQuerySkill(),
        TravelLiveSupportSkill(),
    ]
    for skill in mcp_skills:
        skill_registry.register(skill)

    await SkillRegistry.load_from_config(config_path)
    await skill_registry.initialize_all()
    return skill_registry


__all__ = [
    "Skill",
    "SkillConfig",
    "SkillRegistry",
    "skill_registry",
    "load_skills",
    "KnowledgeRetrievalSkill",
    "TimeQuerySkill",
    "TravelKnowledgeSkill",
    "LiveSearchSkill",
    "ItineraryBuilderSkill",
    "BudgetEstimatorSkill",
    "PackingChecklistSkill",
    "PreferenceMemorySkill",
    "TripReplanSkill",
    "LogQuerySkill",
    "MonitorQuerySkill",
    "TravelLiveSupportSkill",
]
