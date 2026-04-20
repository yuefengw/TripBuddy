"""Plan-and-execute preparation for complex travel adjustments."""

from __future__ import annotations

from typing import Dict, List

from app.models.travel import TripContextMemory, UserProfileMemory
from app.services.travel_llm_service import travel_llm_service
from app.services.travel_workflow_service import travel_workflow_service


class TravelPlanExecuteService:
    """Prepare a complex execution brief for planning or re-planning."""

    async def run(
        self, question: str, user_profile: UserProfileMemory, trip_context: TripContextMemory
    ) -> tuple[str, Dict[str, object]]:
        fallback_draft, fallback_metadata = self._fallback_run(question, user_profile, trip_context)

        artifact = await travel_llm_service.generate_replan_artifact(
            question=question,
            user_profile=user_profile,
            trip_context=trip_context,
            deterministic_brief=fallback_draft,
        )
        if artifact is None:
            fallback_metadata["llm_used"] = False
            fallback_metadata["generation_mode"] = "template_fallback"
            return fallback_draft, fallback_metadata

        lines = [
            "# Plan-and-Execute 执行草稿",
            "",
            "## Step 1: 当前目标与约束",
            self._summarize_current_state(question, trip_context, user_profile),
            "",
            "## Step 2: 冲突识别",
            f"- 冲突类型: {artifact.conflict_type}",
            f"- 优化目标: {artifact.objective}",
            "",
            "## Step 3: 候选方案",
            *(f"- {option}" for option in artifact.candidate_options),
            "",
            "## Step 4: 推荐路径",
            f"- 推荐方案: {artifact.recommended_option}",
            *(f"- 必保留项: {item}" for item in artifact.must_keep),
            "",
            "## Step 5: 执行动作",
            *(
                f"- {index}. {step.title}: {step.action}（原因: {step.rationale}）"
                for index, step in enumerate(artifact.execution_steps, start=1)
            ),
            "",
            "## Step 6: 风险与提醒",
            *(f"- {risk}" for risk in artifact.risks),
        ]

        return "\n".join(lines), {
            "steps": max(len(artifact.execution_steps), 1),
            "updated_plan": True,
            "llm_used": True,
            "generation_mode": "llm_plan_execute_brief",
            "recommended_option": artifact.recommended_option,
            "conflict_type": artifact.conflict_type,
        }

    def _fallback_run(
        self, question: str, user_profile: UserProfileMemory, trip_context: TripContextMemory
    ) -> tuple[str, Dict[str, object]]:
        simple_replan = travel_workflow_service.trip_replanning_workflow(
            question, user_profile, trip_context
        )
        steps: List[Dict[str, str]] = [
            {
                "title": "提取目标与约束",
                "result": self._summarize_current_state(question, trip_context, user_profile),
            },
            {
                "title": "识别冲突",
                "result": self._detect_conflict(question),
            },
            {
                "title": "调用固定重规划 workflow 生成局部候选方案",
                "result": simple_replan.answer[:1200],
            },
            {
                "title": "评估执行顺序",
                "result": self._recommend_option(question, trip_context),
            },
            {
                "title": "更新 trip memory",
                "result": "本轮复杂调整已经生成新的执行草稿，可继续扩展成完整的多天更新版行程。",
            },
        ]

        lines = ["# Plan-and-Execute 重规划结果", ""]
        for index, step in enumerate(steps, start=1):
            lines.extend([f"## Step {index}: {step['title']}", step["result"], ""])

        lines.extend(
            [
                "## 最终执行建议",
                "- 先锁定不可变约束，例如天气、交通变更、返程时间和同行人的体力。",
                "- 再确认哪些部分必须保留，哪些部分可以后移或替换。",
                "- 如果你愿意，我可以基于这版继续生成完整的更新后行程。 ",
            ]
        )
        return "\n".join(lines), {"steps": len(steps), "updated_plan": True}

    @staticmethod
    def _summarize_current_state(
        question: str, trip_context: TripContextMemory, user_profile: UserProfileMemory
    ) -> str:
        parts = [
            f"- 当前目的地: {trip_context.destination or '待确认'}",
            f"- 当前已有计划: {trip_context.current_plan[:160] + '...' if trip_context.current_plan else '暂无已确认计划'}",
            f"- 当前 must-do: {'、'.join(trip_context.must_do) if trip_context.must_do else '暂未显式记录'}",
            f"- 用户偏好节奏: {user_profile.pace_preference or '均衡'}",
            f"- 用户新增问题: {question}",
        ]
        return "\n".join(parts)

    @staticmethod
    def _detect_conflict(question: str) -> str:
        if "雨" in question:
            return "- 冲突类型: 天气变化\n- 影响: 户外活动、跨景点步行和开放式行程会受到明显影响。"
        if "延误" in question or "取消" in question:
            return "- 冲突类型: 交通异常\n- 影响: 到达时间和后续衔接被打乱，需要重新调整执行顺序。"
        return "- 冲突类型: 复杂约束变化\n- 影响: 需要拆解多步任务后再做整体调整。"

    @staticmethod
    def _recommend_option(question: str, trip_context: TripContextMemory) -> str:
        if "雨" in question:
            return (
                "- 先保留核心地标和美食，再把受影响的户外活动改成室内或短距离替代方案。\n"
                f"- 围绕 {trip_context.destination or '当前目的地'} 的酒店周边或同一区域重新排布动线。"
            )
        if "延误" in question or "取消" in question:
            return "- 先压缩首日安排，保留高优先级项目，再把弱时效活动后移到下一天。"
        return "- 先用固定 workflow 给出局部稳定方案，再通过 Plan-and-Execute 串联成完整执行路径。"


travel_plan_execute_service = TravelPlanExecuteService()
