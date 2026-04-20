"""Skill 抽象基类定义"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SkillConfig(BaseModel):
    """技能配置"""
    name: str
    description: str
    enabled: bool = True
    mcp_server: Optional[str] = None  # 关联的 MCP 服务器名称
    metadata: Optional[Dict[str, Any]] = None  # 额外配置


class Skill(ABC):
    """技能抽象基类

    所有技能必须继承此类并实现 get_tools() 方法。
    技能分为两类：
    - Native Skill: 本地实现的工具（如知识检索、时间查询）
    - MCP Skill: 封装 MCP 协议工具的技能
    """

    @property
    @abstractmethod
    def config(self) -> SkillConfig:
        """获取技能配置"""
        pass

    @abstractmethod
    def get_tools(self) -> List[Any]:
        """获取该技能包含的所有工具

        Returns:
            List[Any]: LangChain tool 对象列表
        """
        pass

    async def initialize(self) -> None:
        """异步初始化（如需要）"""
        pass

    async def cleanup(self) -> None:
        """清理资源（如需要）"""
        pass
