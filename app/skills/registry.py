"""Unified registry for local skills and tools."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from app.skills.base import Skill, SkillConfig


class SkillRegistry:
    """Singleton registry used to register and initialize skills."""

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
        logger.info("SkillRegistry initialized")

    def register(self, skill: Skill) -> None:
        config = skill.config
        if config.name in self._skills:
            logger.warning(f"Skill '{config.name}' already exists and will be overwritten")
        self._skills[config.name] = skill
        self._skill_configs[config.name] = config
        logger.info(f"Registered skill: {config.name} (enabled={config.enabled})")

    def unregister(self, name: str) -> bool:
        if name not in self._skills:
            return False
        del self._skills[name]
        self._skill_configs.pop(name, None)
        logger.info(f"Unregistered skill: {name}")
        return True

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def get_config(self, name: str) -> Optional[SkillConfig]:
        return self._skill_configs.get(name)

    def list_skills(self, enabled_only: bool = True) -> List[str]:
        if not enabled_only:
            return list(self._skills.keys())
        return [name for name, config in self._skill_configs.items() if config.enabled]

    def get_all_tools(self, enabled_only: bool = True) -> List[Any]:
        all_tools: List[Any] = []
        seen_tool_names: set[str] = set()
        skills_to_process = (
            [name for name in self.list_skills(enabled_only=True)]
            if enabled_only
            else list(self._skills.keys())
        )

        for skill_name in skills_to_process:
            skill = self._skills.get(skill_name)
            if not skill:
                continue
            try:
                tools = skill.get_tools()
                for tool in tools:
                    tool_name = getattr(tool, "name", str(tool))
                    if tool_name in seen_tool_names:
                        continue
                    seen_tool_names.add(tool_name)
                    all_tools.append(tool)
                logger.debug(f"Skill '{skill_name}' contributed {len(tools)} tools")
            except Exception as exc:
                logger.error(f"Failed to load tools from skill '{skill_name}': {exc}")

        logger.info(f"Collected {len(all_tools)} tools from {len(skills_to_process)} skills")
        return all_tools

    async def initialize_all(self) -> None:
        for skill in self._skills.values():
            if not skill.config.enabled:
                continue
            try:
                await skill.initialize()
            except Exception as exc:
                logger.error(f"Failed to initialize skill '{skill.config.name}': {exc}")

    async def cleanup_all(self) -> None:
        for skill in self._skills.values():
            try:
                await skill.cleanup()
            except Exception as exc:
                logger.error(f"Failed to cleanup skill '{skill.config.name}': {exc}")

    @classmethod
    async def load_from_config(cls, config_path: str) -> "SkillRegistry":
        registry = cls()
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config_data = yaml.safe_load(file) or {}
        except FileNotFoundError:
            logger.warning(f"Skill config file not found: {config_path}")
            return registry
        except Exception as exc:
            logger.error(f"Failed to read skill config file: {exc}")
            return registry

        for skill_config_dict in config_data.get("skills", []):
            try:
                config = SkillConfig(**skill_config_dict)
            except Exception as exc:
                logger.error(f"Failed to parse skill config: {exc}")
                continue

            existing_skill = registry._skills.get(config.name)
            if existing_skill is not None:
                existing_skill.config.enabled = config.enabled
                existing_skill.config.description = config.description
                existing_skill.config.mcp_server = config.mcp_server
                existing_skill.config.metadata = config.metadata
            registry._skill_configs[config.name] = config

        logger.info(f"Loaded {len(registry._skill_configs)} skill configs from {config_path}")
        return registry

    def get_tools_by_skill(self, skill_name: str) -> List[Any]:
        skill = self.get(skill_name)
        if not skill or not skill.config.enabled:
            return []
        try:
            return skill.get_tools()
        except Exception as exc:
            logger.error(f"Failed to get tools by skill '{skill_name}': {exc}")
            return []


skill_registry = SkillRegistry()
