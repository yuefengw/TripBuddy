"""Base skill abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SkillConfig(BaseModel):
    """Skill configuration metadata."""

    name: str
    description: str
    enabled: bool = True
    mcp_server: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class Skill(ABC):
    """Base contract for all native and MCP skills."""

    @property
    @abstractmethod
    def config(self) -> SkillConfig:
        raise NotImplementedError

    @abstractmethod
    def get_tools(self) -> List[Any]:
        raise NotImplementedError

    async def initialize(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None
