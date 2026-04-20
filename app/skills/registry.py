"""技能注册中心 - 统一管理所有技能和工具"""

import asyncio
from typing import Any, Dict, List, Optional, Type

import yaml
from loguru import logger

from app.skills.base import Skill, SkillConfig


class SkillRegistry:
    """技能注册中心单例

    负责：
    - 注册和获取技能
    - 从配置文件加载技能
    - 统一提供所有可用工具
    """

    _instance: Optional["SkillRegistry"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._skills: Dict[str, Skill] = {}
        self._skill_configs: Dict[str, SkillConfig] = {}
        self._initialized = True
        logger.info("SkillRegistry 初始化完成")

    def register(self, skill: Skill) -> None:
        """注册技能

        Args:
            skill: 技能实例
        """
        config = skill.config
        if config.name in self._skills:
            logger.warning(f"技能 '{config.name}' 已存在，将被覆盖")

        self._skills[config.name] = skill
        self._skill_configs[config.name] = config
        logger.info(f"注册技能: {config.name} (enabled={config.enabled})")

    def unregister(self, name: str) -> bool:
        """注销技能

        Args:
            name: 技能名称

        Returns:
            bool: 是否成功注销
        """
        if name in self._skills:
            del self._skills[name]
            del self._skill_configs[name]
            logger.info(f"注销技能: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[Skill]:
        """获取技能

        Args:
            name: 技能名称

        Returns:
            Optional[Skill]: 技能实例，不存在返回 None
        """
        return self._skills.get(name)

    def get_config(self, name: str) -> Optional[SkillConfig]:
        """获取技能配置

        Args:
            name: 技能名称

        Returns:
            Optional[SkillConfig]: 技能配置
        """
        return self._skill_configs.get(name)

    def list_skills(self, enabled_only: bool = True) -> List[str]:
        """列出所有技能

        Args:
            enabled_only: 是否只返回已启用的技能

        Returns:
            List[str]: 技能名称列表
        """
        if enabled_only:
            return [
                name for name, config in self._skill_configs.items()
                if config.enabled
            ]
        return list(self._skills.keys())

    def get_all_tools(self, enabled_only: bool = True) -> List[Any]:
        """获取所有启用的工具

        Args:
            enabled_only: 是否只返回已启用技能的工具

        Returns:
            List[Any]: 工具列表
        """
        all_tools: List[Any] = []
        skills_to_process = (
            [name for name in self.list_skills(enabled_only=True)]
            if enabled_only
            else list(self._skills.keys())
        )

        for skill_name in skills_to_process:
            skill = self._skills.get(skill_name)
            if skill:
                try:
                    tools = skill.get_tools()
                    if tools:
                        all_tools.extend(tools)
                        logger.debug(
                            f"技能 '{skill_name}' 提供 {len(tools)} 个工具"
                        )
                except Exception as e:
                    logger.error(f"获取技能 '{skill_name}' 工具失败: {e}")

        logger.info(f"共获取 {len(all_tools)} 个工具（来自 {len(skills_to_process)} 个技能）")
        return all_tools

    async def initialize_all(self) -> None:
        """初始化所有技能"""
        for skill in self._skills.values():
            if skill.config.enabled:
                try:
                    await skill.initialize()
                except Exception as e:
                    logger.error(f"初始化技能 '{skill.config.name}' 失败: {e}")

    async def cleanup_all(self) -> None:
        """清理所有技能资源"""
        for skill in self._skills.values():
            try:
                await skill.cleanup()
            except Exception as e:
                logger.error(f"清理技能 '{skill.config.name}' 失败: {e}")

    @classmethod
    async def load_from_config(cls, config_path: str) -> "SkillRegistry":
        """从配置文件加载技能

        Args:
            config_path: 配置文件路径（YAML 格式）

        Returns:
            SkillRegistry: 加载了技能的注册中心实例
        """
        registry = cls()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            skill_configs = config_data.get("skills", [])
            logger.info(f"从配置文件加载 {len(skill_configs)} 个技能配置")

            for skill_config_dict in skill_configs:
                try:
                    config = SkillConfig(**skill_config_dict)
                    registry._skill_configs[config.name] = config
                    logger.debug(f"解析技能配置: {config.name}")
                except Exception as e:
                    logger.error(f"解析技能配置失败: {e}")
                    continue

            logger.info(f"技能配置加载完成，待注册技能数: {len(registry._skill_configs)}")
        except FileNotFoundError:
            logger.warning(f"技能配置文件不存在: {config_path}")
        except Exception as e:
            logger.error(f"加载技能配置失败: {e}")

        return registry

    def get_tools_by_skill(self, skill_name: str) -> List[Any]:
        """获取指定技能的工具

        Args:
            skill_name: 技能名称

        Returns:
            List[Any]: 工具列表
        """
        skill = self.get(skill_name)
        if not skill:
            logger.warning(f"技能不存在: {skill_name}")
            return []

        if not skill.config.enabled:
            logger.warning(f"技能未启用: {skill_name}")
            return []

        try:
            return skill.get_tools()
        except Exception as e:
            logger.error(f"获取技能 '{skill_name}' 工具失败: {e}")
            return []


# 全局单例（延迟初始化）
skill_registry = SkillRegistry()
