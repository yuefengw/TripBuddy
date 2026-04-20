"""LLM-backed multi-role orchestration for deep-search travel consulting."""

from __future__ import annotations

import asyncio
from typing import Dict, List

from app.models.travel import TripContextMemory, UserProfileMemory
from app.services.travel_llm_service import travel_llm_service
from app.services.travel_utils import extract_destinations, unique_strings
from app.services.travel_workflow_service import travel_workflow_service


class TravelMultiAgentService:
    """Prepare a multi-role collaboration brief for deep search."""

    async def run(
        self, question: str, user_profile: UserProfileMemory, trip_context: TripContextMemory
    ) -> tuple[str, Dict[str, object]]:
        destinations = extract_destinations(question)
        if len(destinations) < 2 and trip_context.destination:
            destinations = unique_strings([trip_context.destination, "备选目的地"])
        elif len(destinations) < 2:
            destinations = ["东京", "大阪"]

        if not travel_llm_service.is_available():
            answer = self._fallback_answer(destinations, question, user_profile, trip_context)
            return answer, {
                "destinations": destinations,
                "roles": 5,
                "llm_used": False,
                "generation_mode": "template_fallback",
            }

        shared_context = self._build_shared_context(destinations, question, user_profile, trip_context)
        role_tasks = {
            "Destination Researcher": travel_llm_service.generate_role_output(
                role_name="Destination Researcher",
                role_goal="Judge destination fit, seasonality, highlights, and suitability.",
                question=question,
                user_profile=user_profile,
                trip_context=trip_context,
                shared_context=shared_context,
            ),
            "Transport And Stay Analyst": travel_llm_service.generate_role_output(
                role_name="Transport And Stay Analyst",
                role_goal="Compare movement cost, stay area strategy, and budget fit.",
                question=question,
                user_profile=user_profile,
                trip_context=trip_context,
                shared_context=shared_context,
            ),
            "Itinerary Designer": travel_llm_service.generate_role_output(
                role_name="Itinerary Designer",
                role_goal="Design pacing, day structure, and scenario-fit suggestions.",
                question=question,
                user_profile=user_profile,
                trip_context=trip_context,
                shared_context=shared_context,
            ),
            "Risk Advisor": travel_llm_service.generate_role_output(
                role_name="Risk Advisor",
                role_goal="Surface hidden constraints, risks, and fallback considerations.",
                question=question,
                user_profile=user_profile,
                trip_context=trip_context,
                shared_context=shared_context,
            ),
        }

        role_results = await asyncio.gather(*role_tasks.values(), return_exceptions=True)
        role_outputs: Dict[str, str] = {}
        for role_name, result in zip(role_tasks.keys(), role_results):
            if isinstance(result, Exception) or not str(result).strip():
                role_outputs[role_name] = self._fallback_role(
                    role_name, destinations, question, user_profile, trip_context
                )
            else:
                role_outputs[role_name] = str(result).strip()

        draft = "\n".join(
            [
                "# 多角色旅行顾问分析草稿",
                "",
                "## Lead Planner 任务拆解",
                f"- 用户问题: {question}",
                f"- 对比目的地: {' / '.join(destinations)}",
                "- 分析目标: 在体验、预算、节奏、风险和可执行性之间做清晰取舍。",
                "",
                *(self._format_role_section(role_name, content) for role_name, content in role_outputs.items()),
                "",
                "## Lead Planner 汇总任务",
                "- 请基于以上角色分析给出最终推荐结论，并明确为什么。",
            ]
        )

        return draft, {
            "destinations": destinations,
            "roles": 5,
            "llm_used": True,
            "role_names": list(role_outputs.keys()),
            "generation_mode": "llm_multi_agent_brief",
        }

    def _build_shared_context(
        self,
        destinations: List[str],
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
    ) -> str:
        parts: List[str] = []
        for destination in destinations:
            knowledge = travel_workflow_service.answer_knowledge_question(
                question.replace("比较", f"了解{destination}"),
                UserProfileMemory(),
                TripContextMemory(destination=destination),
            )
            planning = travel_workflow_service.trip_planning_workflow(
                f"帮我规划 {destination} 行程",
                user_profile,
                trip_context.model_copy(
                    update={"destination": destination, "duration_days": trip_context.duration_days or 4}
                ),
            )
            parts.extend(
                [
                    f"### {destination}",
                    knowledge.answer[:500],
                    "",
                    planning.answer[:900],
                    "",
                ]
            )
        return "\n".join(parts)

    @staticmethod
    def _format_role_section(role_name: str, content: str) -> str:
        return f"## {role_name}\n{content}\n"

    def _fallback_answer(
        self,
        destinations: List[str],
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
    ) -> str:
        role_outputs = {
            "Destination Researcher": self._fallback_role(
                "Destination Researcher", destinations, question, user_profile, trip_context
            ),
            "Transport And Stay Analyst": self._fallback_role(
                "Transport And Stay Analyst", destinations, question, user_profile, trip_context
            ),
            "Itinerary Designer": self._fallback_role(
                "Itinerary Designer", destinations, question, user_profile, trip_context
            ),
            "Risk Advisor": self._fallback_role(
                "Risk Advisor", destinations, question, user_profile, trip_context
            ),
        }
        return "\n".join(
            [
                "# 多角色旅行顾问分析",
                "",
                "## Lead Planner 任务拆解",
                f"- 目标: 围绕 {' vs '.join(destinations)} 做复杂旅行方案比较",
                "- 维度: 目的地适配、交通住宿、节奏设计、风险提醒",
                "",
                *(self._format_role_section(role_name, content) for role_name, content in role_outputs.items()),
                "",
                "## Lead Planner 最终建议",
                self._fallback_summary(destinations),
            ]
        )

    def _fallback_role(
        self,
        role_name: str,
        destinations: List[str],
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
    ) -> str:
        if role_name == "Destination Researcher":
            lines = []
            for destination in destinations:
                result = travel_workflow_service.answer_knowledge_question(
                    question.replace("比较", f"了解{destination}"),
                    UserProfileMemory(),
                    TripContextMemory(destination=destination),
                )
                preview = "\n".join(result.answer.splitlines()[:6])
                lines.append(f"### {destination}\n{preview}")
            return "\n\n".join(lines)

        if role_name == "Transport And Stay Analyst":
            lines = []
            for destination in destinations:
                planning = travel_workflow_service.trip_planning_workflow(
                    f"帮我规划 {destination} 行程",
                    user_profile,
                    trip_context.model_copy(
                        update={"destination": destination, "duration_days": trip_context.duration_days or 4}
                    ),
                )
                budget_line = next(
                    (
                        line
                        for line in planning.answer.splitlines()
                        if "预计总计" in line or "粗略预算拆分" in line
                    ),
                    "- 预算仍需结合实际出发地进一步确认",
                )
                lines.append(
                    "\n".join(
                        [
                            f"### {destination}",
                            budget_line,
                            f"- 住宿建议: {user_profile.accommodation_preference or '优先交通便利区域'}",
                            "- 动线策略: 以一个核心区域为住宿中心，减少折返。",
                        ]
                    )
                )
            return "\n\n".join(lines)

        if role_name == "Itinerary Designer":
            lines = []
            for destination in destinations:
                planning = travel_workflow_service.trip_planning_workflow(
                    f"帮我规划 {destination} 行程",
                    user_profile,
                    trip_context.model_copy(
                        update={"destination": destination, "duration_days": trip_context.duration_days or 4}
                    ),
                )
                preview = "\n".join(planning.answer.splitlines()[8:20])
                lines.append(f"### {destination}\n{preview}")
            return "\n\n".join(lines)

        notes = []
        for destination in destinations:
            notes.extend(
                [
                    f"- {destination}: 热门景点要预留排队时间，最好准备一个室内备选。",
                    f"- {destination}: 实时天气、签证或汇率信息要以用户提供的事实或外部接口结果为准。",
                ]
            )
        if user_profile.dietary_preferences:
            notes.append(f"- 饮食偏好提醒: {'、'.join(user_profile.dietary_preferences)}")
        if "孩子" in question or "老人" in question:
            notes.append("- 特殊人群提醒: 控制单日步行量，避免晚间连续换乘。")
        return "\n".join(unique_strings(notes))

    @staticmethod
    def _fallback_summary(destinations: List[str]) -> str:
        return (
            f"- 如果更看重内容丰富度和城市体验，优先考虑 {destinations[0]}。\n"
            f"- 如果更看重美食密度、动线紧凑或亲子友好，{destinations[-1]} 往往更稳。\n"
            "- 下一步建议先确定一个主目的地，我再把它展开成最终版本。"
        )


travel_multi_agent_service = TravelMultiAgentService()
