"""Native knowledge-retrieval skill."""

from __future__ import annotations

from typing import Any, List

from app.skills.base import Skill, SkillConfig
from app.tools.knowledge_tool import retrieve_knowledge


class KnowledgeRetrievalSkill(Skill):
    """Expose vector-knowledge retrieval as a skill."""

    @property
    def config(self) -> SkillConfig:
        return SkillConfig(
            name="knowledge_retrieval",
            description="从向量知识库检索相关旅行资料",
            enabled=True,
            metadata={"category": "rag", "priority": "high"},
        )

    def get_tools(self) -> List[Any]:
        return [retrieve_knowledge]
