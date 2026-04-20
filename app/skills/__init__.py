"""统一工具调用框架 - Skills 配置化封装

提供统一的技能注册和管理接口，支持：
- Function Call（LLM 原生工具调用）
- MCP 协议工具接入
- Skills 配置化封装

使用示例：
    from app.skills import skill_registry, load_skills

    # 加载所有技能
    await load_skills()

    # 获取所有工具
    tools = skill_registry.get_all_tools()

    # 获取指定技能的工具
    tools = skill_registry.get_tools_by_skill("knowledge_retrieval")
"""

from app.skills.base import Skill, SkillConfig
from app.skills.registry import SkillRegistry, skill_registry
from app.skills.native import KnowledgeRetrievalSkill, TimeQuerySkill
from app.skills.mcp import LogQuerySkill, MonitorQuerySkill


async def load_skills(config_path: str = "app/config/skills.yaml") -> SkillRegistry:
    """加载并注册所有技能

    Args:
        config_path: 技能配置文件路径

    Returns:
        SkillRegistry: 技能注册中心实例
    """
    # 注册原生技能
    native_skills = [
        KnowledgeRetrievalSkill(),
        TimeQuerySkill(),
    ]
    for skill in native_skills:
        skill_registry.register(skill)

    # 注册 MCP 技能
    mcp_skills = [
        LogQuerySkill(),
        MonitorQuerySkill(),
    ]
    for skill in mcp_skills:
        skill_registry.register(skill)

    # 从配置文件加载配置（但不重新创建技能实例）
    await SkillRegistry.load_from_config(config_path)

    # 初始化所有启用的技能
    await skill_registry.initialize_all()

    return skill_registry


__all__ = [
    # 基础类
    "Skill",
    "SkillConfig",
    # 注册中心
    "SkillRegistry",
    "skill_registry",
    # 技能加载函数
    "load_skills",
    # 原生技能
    "KnowledgeRetrievalSkill",
    "TimeQuerySkill",
    # MCP 技能
    "LogQuerySkill",
    "MonitorQuerySkill",
]
