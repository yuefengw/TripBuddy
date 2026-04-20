"""Semantic intent router for the unified travel assistant."""

from __future__ import annotations

from typing import Literal, Optional, Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.config import config
from app.core.llm_factory import llm_factory
from app.models.travel import IntentRouteResult, TripContextMemory, UserProfileMemory
from app.services.travel_llm_service import travel_llm_service


class IntentClassification(BaseModel):
    """Structured intent-classification result produced by the LLM."""

    intent: Optional[
        Literal[
            "travel_knowledge",
            "trip_planning",
            "trip_replanning",
            "complex_replanning",
        ]
    ] = None
    route_type: Literal["knowledge", "workflow", "plan_execute"]
    selected_workflow: Optional[
        Literal["trip_planning_workflow", "trip_replanning_workflow"]
    ] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reason: str = ""


class TravelIntentService:
    """Route user queries into the most suitable execution mode."""

    async def route(
        self,
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
        conversation_mode: Optional[str] = None,
        session_history: Optional[Sequence[dict]] = None,
    ) -> IntentRouteResult:
        if conversation_mode in {"deep_search", "multi_agent"}:
            return IntentRouteResult(
                intent="complex_travel_consulting",
                route_type="multi_agent",
                confidence=0.99,
                reason="deep search forces multi-agent orchestration",
            )

        if conversation_mode == "plan_execute":
            return IntentRouteResult(
                intent="trip_replanning",
                route_type="plan_execute",
                confidence=0.99,
                reason="conversation_mode forced plan-and-execute",
            )

        if not travel_llm_service.is_available():
            return self._fallback_route(user_profile, trip_context)

        try:
            classification = await self._classify_with_llm(
                question=question,
                user_profile=user_profile,
                trip_context=trip_context,
                session_history=session_history or [],
            )
            return self._normalize_classification(classification)
        except Exception as exc:
            fallback = self._fallback_route(user_profile, trip_context)
            fallback.reason = f"llm intent classification failed, fallback used: {exc}"
            return fallback

    async def _classify_with_llm(
        self,
        *,
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
        session_history: Sequence[dict],
    ) -> IntentClassification:
        model = llm_factory.create_chat_model(
            model=config.dashscope_model,
            temperature=0.1,
            streaming=False,
        )
        structured_model = model.with_structured_output(IntentClassification)
        return await structured_model.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是旅行助手 TripBuddy 的意图识别器。"
                        "你的职责不是回答问题，而是把用户请求路由到最合适的执行模式。"
                        "只能在 knowledge、workflow、plan_execute 三种 route_type 中选择。"
                        "不要使用 multi_agent，multi_agent 只由 deep search 显式触发。"
                        "你必须输出 JSON 结构化分类结果。"
                        "\n\n"
                        "路由定义：\n"
                        "1. knowledge：单点问答、轻咨询、直接攻略建议，不需要固定流程，也不需要复杂任务拆解。\n"
                        "2. workflow + trip_planning_workflow：适合行前规划，流程固定为“需求理解 -> 目的地/方案落点 -> 行程骨架 -> 预算与准备提醒”。\n"
                        "3. workflow + trip_replanning_workflow：适合局部、简单、可控的行程调整，流程固定为“当前计划 -> 影响评估 -> 替换方案 -> 更新建议”。\n"
                        "4. plan_execute：适合更复杂的规划或重规划，需要多步分解、冲突协调、多个依赖步骤串联后才能给出结论。\n"
                        "\n\n"
                        "判定原则：\n"
                        "- 不要按关键词做机械分类，要结合问题语义、用户画像、trip context 和最近对话历史。\n"
                        "- 如果用户目标明确且中间步骤稳定，优先 workflow。\n"
                        "- 如果用户是在已有计划上做局部调整，但问题边界清晰，优先 trip_replanning_workflow。\n"
                        "- 如果问题包含多重约束、需要连续推理或需要先拆任务再执行，选择 plan_execute。\n"
                        "- 如果只是问“怎么选、怎么玩、值不值得、适不适合”，且不要求完整流程，优先 knowledge。\n"
                        "\n"
                        "few-shot 示例：\n"
                        "示例 1：\n"
                        "问题：6 月第一次去成都适合怎么玩？\n"
                        "输出 JSON：{\"intent\":\"travel_knowledge\",\"route_type\":\"knowledge\",\"selected_workflow\":null,\"confidence\":0.82,\"reason\":\"这是单点目的地咨询，直接问答即可\"}\n"
                        "\n"
                        "示例 2：\n"
                        "问题：帮我做一个 4 天重庆美食行程，预算 3000。\n"
                        "输出 JSON：{\"intent\":\"trip_planning\",\"route_type\":\"workflow\",\"selected_workflow\":\"trip_planning_workflow\",\"confidence\":0.9,\"reason\":\"这是行前规划，输入约束明确，适合固定规划流程\"}\n"
                        "\n"
                        "示例 3：\n"
                        "问题：我明天在杭州，原本下午西湖划船，晚上看夜景，现在下雨了，想尽量少改动，怎么调一下？\n"
                        "输出 JSON：{\"intent\":\"trip_replanning\",\"route_type\":\"workflow\",\"selected_workflow\":\"trip_replanning_workflow\",\"confidence\":0.84,\"reason\":\"这是局部重规划，边界清晰，固定重规划流程足够\"}\n"
                        "\n"
                        "示例 4：\n"
                        "问题：我周五到东京，周日晚上还要去大阪见朋友，中间带孩子，预算有限，而且担心下雨，帮我把两城安排重新拆一下。\n"
                        "输出 JSON：{\"intent\":\"complex_replanning\",\"route_type\":\"plan_execute\",\"selected_workflow\":null,\"confidence\":0.9,\"reason\":\"这是多约束、跨城市、依赖顺序强的复杂问题，需要 Plan-and-Execute\"}"
                    )
                ),
                HumanMessage(
                    content=(
                        f"用户问题：\n{question}\n\n"
                        f"用户画像：\n{self._format_profile(user_profile)}\n\n"
                        f"当前 trip context：\n{self._format_trip_context(trip_context)}\n\n"
                        f"最近对话历史：\n{self._format_history(session_history)}\n\n"
                        "请返回 JSON 结构化分类结果。"
                    )
                ),
            ]
        )

    @staticmethod
    def _normalize_classification(classification: IntentClassification) -> IntentRouteResult:
        selected_workflow = classification.selected_workflow
        intent = classification.intent

        if classification.route_type == "workflow" and selected_workflow is None:
            selected_workflow = (
                "trip_replanning_workflow"
                if intent == "trip_replanning"
                else "trip_planning_workflow"
            )

        if intent is None:
            if classification.route_type == "knowledge":
                intent = "travel_knowledge"
            elif selected_workflow == "trip_replanning_workflow":
                intent = "trip_replanning"
            elif classification.route_type == "plan_execute":
                intent = "complex_replanning"
            else:
                intent = "trip_planning"

        return IntentRouteResult(
            intent=intent,
            route_type=classification.route_type,
            selected_workflow=selected_workflow,
            confidence=classification.confidence,
            reason=classification.reason,
        )

    @staticmethod
    def _fallback_route(
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
    ) -> IntentRouteResult:
        has_replanning_context = bool(
            trip_context.current_plan or trip_context.must_do or trip_context.constraints
        )
        has_planning_context = bool(
            trip_context.destination
            or trip_context.duration_days
            or trip_context.budget_amount
            or trip_context.interests
            or trip_context.travel_month
            or trip_context.companions
            or user_profile.travel_style
            or user_profile.notes
        )

        if has_replanning_context:
            return IntentRouteResult(
                intent="trip_replanning",
                route_type="workflow",
                selected_workflow="trip_replanning_workflow",
                confidence=0.42,
                reason="fallback route based on existing trip context",
            )

        if has_planning_context:
            return IntentRouteResult(
                intent="trip_planning",
                route_type="workflow",
                selected_workflow="trip_planning_workflow",
                confidence=0.4,
                reason="fallback route based on planning-related memory fields",
            )

        return IntentRouteResult(
            intent="travel_knowledge",
            route_type="knowledge",
            confidence=0.35,
            reason="fallback route without semantic classifier",
        )

    @staticmethod
    def _format_profile(user_profile: UserProfileMemory) -> str:
        return "\n".join(
            [
                f"budget_preference={user_profile.budget_preference or 'unknown'}",
                f"travel_style={', '.join(user_profile.travel_style) or 'unknown'}",
                f"dietary_preferences={', '.join(user_profile.dietary_preferences) or 'unknown'}",
                f"pace_preference={user_profile.pace_preference or 'unknown'}",
                f"accommodation_preference={user_profile.accommodation_preference or 'unknown'}",
                f"companion_preference={', '.join(user_profile.companion_preference) or 'unknown'}",
                f"preferred_destinations={', '.join(user_profile.preferred_destinations) or 'unknown'}",
                f"notes={', '.join(user_profile.notes) or 'none'}",
            ]
        )

    @staticmethod
    def _format_trip_context(trip_context: TripContextMemory) -> str:
        return "\n".join(
            [
                f"origin={trip_context.origin or 'unknown'}",
                f"destination={trip_context.destination or 'unknown'}",
                f"travel_month={trip_context.travel_month or 'unknown'}",
                f"duration_days={trip_context.duration_days or 'unknown'}",
                f"budget_amount={trip_context.budget_amount or 'unknown'}",
                f"companions={', '.join(trip_context.companions) or 'unknown'}",
                f"interests={', '.join(trip_context.interests) or 'unknown'}",
                f"current_plan={(trip_context.current_plan or 'none')[:500]}",
                f"must_do={', '.join(trip_context.must_do) or 'none'}",
                f"constraints={', '.join(trip_context.constraints) or 'none'}",
                f"open_questions={', '.join(trip_context.open_questions) or 'none'}",
            ]
        )

    @staticmethod
    def _format_history(session_history: Sequence[dict], limit: int = 6) -> str:
        if not session_history:
            return "No previous turns."

        items = []
        for entry in session_history[-limit:]:
            role = entry.get("role", "unknown")
            content = str(entry.get("content", "")).replace("\n", " ").strip()
            items.append(f"{role}: {content[:220]}")
        return "\n".join(items)


travel_intent_service = TravelIntentService()
