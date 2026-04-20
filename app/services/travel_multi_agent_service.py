"""ReAct-style multi-agent orchestration with human-in-the-loop support."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Awaitable, Callable, Dict, List

from app.models.travel import TripContextMemory, UserProfileMemory
from app.services.travel_llm_service import LeadPlannerPlan, MultiAgentTask, travel_llm_service
from app.services.travel_memory_service import travel_memory_service
from app.services.travel_utils import extract_destinations, unique_strings
from app.services.travel_workflow_service import travel_workflow_service
from app.tools import retrieve_knowledge, scrape_web_page, search_web_live


StatusCallback = Callable[[str], Awaitable[None]]


ROLE_GOALS: Dict[str, str] = {
    "Destination Researcher": "判断目的地适配度、季节性、亮点和用户匹配度。",
    "Transport And Stay Analyst": "比较交通成本、住宿区域策略和预算适配。",
    "Itinerary Designer": "设计节奏、按天结构和不同人群适配建议。",
    "Risk Advisor": "识别隐藏约束、风险和备选方案。",
}


@dataclass
class ActiveMultiAgentRun:
    """Mutable state for one in-flight deep-search run."""

    session_id: str
    base_question: str
    pending_updates: List[str] = field(default_factory=list)


class HumanUpdateInterrupt(RuntimeError):
    """Raised when a running sub-agent should yield to a human update."""

    def __init__(self, updates: List[str]) -> None:
        super().__init__("human update received")
        self.updates = updates


class TravelMultiAgentService:
    """Lead-planner orchestration over specialist ReAct agents."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._active_runs: Dict[str, ActiveMultiAgentRun] = {}

    def has_active_run(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._active_runs

    def submit_human_update(self, session_id: str, message: str) -> bool:
        update = message.strip()
        if not update:
            return False

        with self._lock:
            run = self._active_runs.get(session_id)
            if run is None:
                return False
            run.pending_updates.append(update)

        travel_memory_service.learn_from_question(session_id, update)
        return True

    async def run(
        self,
        session_id: str,
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
        on_status: StatusCallback | None = None,
    ) -> tuple[str, Dict[str, object]]:
        run = ActiveMultiAgentRun(session_id=session_id, base_question=question)
        with self._lock:
            self._active_runs[session_id] = run

        try:
            return await self._run_internal(
                run=run,
                question=question,
                user_profile=user_profile,
                trip_context=trip_context,
                on_status=on_status,
            )
        finally:
            with self._lock:
                self._active_runs.pop(session_id, None)

    async def _run_internal(
        self,
        *,
        run: ActiveMultiAgentRun,
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
        on_status: StatusCallback | None,
    ) -> tuple[str, Dict[str, object]]:
        current_question = question
        update_history: List[str] = []
        completed_findings: Dict[str, str] = {}
        react_steps: Dict[str, int] = {}
        lead_rounds = 0
        destinations = self._resolve_destinations(current_question, trip_context)
        shared_bundle, shared_context = self._build_shared_context(
            destinations=destinations,
            question=current_question,
            user_profile=user_profile,
            trip_context=trip_context,
        )

        await self._emit_status(on_status, "Lead Planner 已收到任务，正在做任务分解。")

        while lead_rounds < 4:
            lead_rounds += 1

            buffered_updates = self._consume_updates(run.session_id)
            if buffered_updates:
                update_history.extend(buffered_updates)
                current_question = self._merge_question(question, update_history)
                user_profile = travel_memory_service.get_user_profile(run.session_id)
                trip_context = travel_memory_service.get_trip_context(run.session_id)
                destinations = self._resolve_destinations(current_question, trip_context)
                shared_bundle, shared_context = self._build_shared_context(
                    destinations=destinations,
                    question=current_question,
                    user_profile=user_profile,
                    trip_context=trip_context,
                )
                completed_findings = {
                    role: f"{content}\n\n[注意] 以下结论生成于用户追加条件之前，需要由 Lead Planner 重新校准。"
                    for role, content in completed_findings.items()
                }
                await self._emit_status(
                    on_status,
                    f"收到用户追加条件：{'；'.join(buffered_updates)}。Lead Planner 正在重分解任务。",
                )

            plan = await self._build_plan(
                question=current_question,
                user_profile=user_profile,
                trip_context=trip_context,
                shared_context=shared_context,
                completed_findings=completed_findings,
                pending_updates=update_history,
            )
            await self._emit_status(
                on_status,
                f"Lead Planner 第 {lead_rounds} 轮分解完成，准备分发 {len(plan.tasks)} 个子任务。",
            )

            interrupted = False
            for task in plan.tasks:
                try:
                    result, step_count = await self._run_subagent_react(
                        run=run,
                        task=task,
                        question=current_question,
                        user_profile=user_profile,
                        trip_context=trip_context,
                        shared_bundle=shared_bundle,
                        shared_context=shared_context,
                        completed_findings=completed_findings,
                        update_history=update_history,
                        on_status=on_status,
                    )
                except HumanUpdateInterrupt as exc:
                    update_history.extend(exc.updates)
                    user_profile = travel_memory_service.get_user_profile(run.session_id)
                    trip_context = travel_memory_service.get_trip_context(run.session_id)
                    await self._emit_status(
                        on_status,
                        f"用户新增条件：{'；'.join(exc.updates)}。主 Agent 中断当前任务并重新规划。",
                    )
                    interrupted = True
                    break

                completed_findings[task.role_name] = result
                react_steps[task.role_name] = step_count
                await self._emit_status(
                    on_status,
                    f"{task.role_name} 已完成，主 Agent 已接收对应结论。",
                )

            if interrupted:
                continue

            trailing_updates = self._consume_updates(run.session_id)
            if trailing_updates:
                update_history.extend(trailing_updates)
                await self._emit_status(
                    on_status,
                    f"汇总前又收到新条件：{'；'.join(trailing_updates)}，主 Agent 将再做一轮调整。",
                )
                continue

            draft = self._compose_final_draft(
                current_question=current_question,
                plan=plan,
                completed_findings=completed_findings,
                react_steps=react_steps,
                update_history=update_history,
            )
            return draft, {
                "destinations": destinations,
                "roles": len(completed_findings) + 1,
                "role_names": list(completed_findings.keys()),
                "llm_used": travel_llm_service.is_available(),
                "generation_mode": "react_multi_agent_hitl",
                "human_in_the_loop": True,
                "lead_rounds": lead_rounds,
                "react_step_count": sum(react_steps.values()),
                "human_updates": update_history,
                "convergence_reason": "all assigned sub-agents finished and no pending human updates",
            }

        draft = self._compose_final_draft(
            current_question=current_question,
            plan=self._fallback_plan(destinations, current_question, update_history),
            completed_findings=completed_findings or self._fallback_role_outputs(
                destinations, current_question, user_profile, trip_context
            ),
            react_steps=react_steps,
            update_history=update_history,
            convergence_note="达到最大主循环轮数，按当前最稳定结论收敛。",
        )
        return draft, {
            "destinations": destinations,
            "roles": len(completed_findings) + 1,
            "role_names": list(completed_findings.keys()),
            "llm_used": travel_llm_service.is_available(),
            "generation_mode": "react_multi_agent_hitl",
            "human_in_the_loop": True,
            "lead_rounds": lead_rounds,
            "react_step_count": sum(react_steps.values()),
            "human_updates": update_history,
            "convergence_reason": "max lead-planner rounds reached",
        }

    async def _build_plan(
        self,
        *,
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
        shared_context: str,
        completed_findings: Dict[str, str],
        pending_updates: List[str],
    ) -> LeadPlannerPlan:
        plan = await travel_llm_service.plan_multi_agent_tasks(
            question=question,
            user_profile=user_profile,
            trip_context=trip_context,
            shared_context=shared_context,
            completed_findings=self._format_completed_findings(completed_findings),
            pending_updates=pending_updates,
        )
        if plan and plan.tasks:
            unique_tasks: List[MultiAgentTask] = []
            seen_roles: set[str] = set()
            for task in plan.tasks:
                if task.role_name in seen_roles:
                    continue
                unique_tasks.append(task)
                seen_roles.add(task.role_name)
            plan.tasks = unique_tasks
            return plan

        destinations = self._resolve_destinations(question, trip_context)
        return self._fallback_plan(destinations, question, pending_updates)

    async def _run_subagent_react(
        self,
        *,
        run: ActiveMultiAgentRun,
        task: MultiAgentTask,
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
        shared_bundle: Dict[str, Dict[str, str]],
        shared_context: str,
        completed_findings: Dict[str, str],
        update_history: List[str],
        on_status: StatusCallback | None,
    ) -> tuple[str, int]:
        role_goal = ROLE_GOALS.get(task.role_name, "围绕分配任务给出高质量旅行分析。")
        scratchpad_parts: List[str] = []

        await self._emit_status(on_status, f"{task.role_name} 开始执行分配任务。")

        for step_index in range(1, 5):
            updates = self._consume_updates(run.session_id)
            if updates:
                raise HumanUpdateInterrupt(updates)

            decision = await travel_llm_service.decide_react_step(
                role_name=task.role_name,
                role_goal=role_goal,
                task_objective=task.objective,
                question=question,
                user_profile=user_profile,
                trip_context=trip_context,
                shared_context=shared_context,
                peer_findings=self._format_completed_findings(completed_findings),
                scratchpad="\n\n".join(scratchpad_parts),
                pending_updates=update_history,
            )
            if decision is None:
                break

            if decision.action == "finish" and decision.finish_answer.strip():
                scratchpad_parts.append(f"Step {step_index} finish: {decision.finish_answer.strip()}")
                return decision.finish_answer.strip(), step_index

            observation = self._execute_react_action(
                action=decision.action,
                action_input=decision.action_input,
                question=question,
                task=task,
                trip_context=trip_context,
                user_profile=user_profile,
                shared_bundle=shared_bundle,
                completed_findings=completed_findings,
            )
            scratchpad_parts.append(
                "\n".join(
                    [
                        f"Step {step_index}",
                        f"Thought: {decision.thought}",
                        f"Action: {decision.action}",
                        f"Input: {decision.action_input or '无'}",
                        f"Observation: {observation}",
                    ]
                )
            )
            await self._emit_status(
                on_status,
                f"{task.role_name} 正在 ReAct 第 {step_index} 步：{decision.action}",
            )

        fallback = self._fallback_role(
            task.role_name,
            self._resolve_destinations(question, trip_context),
            question,
            user_profile,
            trip_context,
        )
        if scratchpad_parts:
            fallback = "\n\n".join([fallback, "## ReAct Scratchpad", *scratchpad_parts])
        return fallback, min(len(scratchpad_parts), 4)

    def _execute_react_action(
        self,
        *,
        action: str,
        action_input: str,
        question: str,
        task: MultiAgentTask,
        trip_context: TripContextMemory,
        user_profile: UserProfileMemory,
        shared_bundle: Dict[str, Dict[str, str]],
        completed_findings: Dict[str, str],
    ) -> str:
        target = action_input.strip()
        relevant_destinations = task.destinations or list(shared_bundle.keys())
        destination = next((item for item in relevant_destinations if item in target), "")
        if not destination:
            destination = relevant_destinations[0] if relevant_destinations else (trip_context.destination or "")

        if action == "read_shared_context":
            bundle = shared_bundle.get(destination) if destination else None
            if bundle:
                return (
                    f"{destination} 共享上下文摘要："
                    f"知识={bundle.get('knowledge', '')[:220]} | 规划={bundle.get('planning', '')[:320]}"
                )
            return "共享上下文中没有更合适的目标，继续用已有任务信息推进。"

        if action == "retrieve_knowledge":
            query = target or f"{question}\n补充目标：{task.objective}"
            try:
                result = retrieve_knowledge.invoke({"query": query})
            except Exception as exc:
                return f"知识检索失败：{exc}"
            if isinstance(result, tuple):
                return str(result[0] or "")[:500]
            return str(result or "")[:500]

        if action == "plan_destination":
            local_trip = trip_context.model_copy(
                update={"destination": destination or trip_context.destination}
            )
            planning = travel_workflow_service.trip_planning_workflow(
                question=f"帮我规划 {local_trip.destination or destination or '当前目的地'} 行程",
                user_profile=user_profile,
                trip_context=local_trip,
            )
            return planning.answer[:650]

        if action == "replan_trip":
            local_trip = trip_context.model_copy(
                update={"destination": destination or trip_context.destination}
            )
            replan = travel_workflow_service.trip_replanning_workflow(
                question=target or question,
                user_profile=user_profile,
                trip_context=local_trip,
            )
            return replan.answer[:650]

        if action == "inspect_peer_findings":
            return self._format_completed_findings(completed_findings)[:650] or "其他角色暂未完成。"

        return "动作未命中，回退到已有观察。"

    def _execute_react_action(
        self,
        *,
        action: str,
        action_input: str,
        question: str,
        task: MultiAgentTask,
        trip_context: TripContextMemory,
        user_profile: UserProfileMemory,
        shared_bundle: Dict[str, Dict[str, str]],
        completed_findings: Dict[str, str],
    ) -> str:
        target = action_input.strip()
        relevant_destinations = task.destinations or list(shared_bundle.keys())
        destination = next((item for item in relevant_destinations if item in target), "")
        if not destination:
            destination = relevant_destinations[0] if relevant_destinations else (trip_context.destination or "")

        if action == "read_shared_context":
            bundle = shared_bundle.get(destination) if destination else None
            if bundle:
                return (
                    f"{destination} shared context: "
                    f"knowledge={bundle.get('knowledge', '')[:220]} | planning={bundle.get('planning', '')[:320]}"
                )
            return "No matching shared context yet. Continue with existing task information."

        if action == "retrieve_knowledge":
            query = target or f"{question}\nSupplement objective: {task.objective}"
            try:
                result = retrieve_knowledge.invoke({"query": query})
            except Exception as exc:
                return f"knowledge retrieval failed: {exc}"
            if isinstance(result, tuple):
                return str(result[0] or "")[:500]
            return str(result or "")[:500]

        if action == "plan_destination":
            local_trip = trip_context.model_copy(
                update={"destination": destination or trip_context.destination}
            )
            planning = travel_workflow_service.trip_planning_workflow(
                question=f"Help me plan a trip for {local_trip.destination or destination or 'the current destination'}",
                user_profile=user_profile,
                trip_context=local_trip,
            )
            return planning.answer[:650]

        if action == "replan_trip":
            local_trip = trip_context.model_copy(
                update={"destination": destination or trip_context.destination}
            )
            replan = travel_workflow_service.trip_replanning_workflow(
                question=target or question,
                user_profile=user_profile,
                trip_context=local_trip,
            )
            return replan.answer[:650]

        if action == "search_web_live":
            search_query = target or f"{destination or trip_context.destination or ''} {task.objective}".strip()
            try:
                result = search_web_live.invoke(
                    {
                        "query": search_query or question,
                        "location": "China",
                        "num_results": 4,
                    }
                )
            except Exception as exc:
                return f"live web search failed: {exc}"
            return str(result or "")[:900]

        if action == "scrape_web_page":
            scrape_target = target
            if not scrape_target.startswith("http"):
                peer_blob = self._format_completed_findings(completed_findings)
                for token in peer_blob.split():
                    if token.startswith("http://") or token.startswith("https://"):
                        scrape_target = token.rstrip(").,]")
                        break
            if not scrape_target.startswith("http"):
                return "No URL available to scrape yet. Search first or inspect peer findings."
            try:
                result = scrape_web_page.invoke(
                    {
                        "url": scrape_target,
                        "prompt": task.objective,
                    }
                )
            except Exception as exc:
                return f"page scrape failed: {exc}"
            return str(result or "")[:1200]

        if action == "inspect_peer_findings":
            return self._format_completed_findings(completed_findings)[:650] or "No peer findings yet."

        return "Unknown action. Fall back to existing observations."

    def _build_shared_context(
        self,
        *,
        destinations: List[str],
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
    ) -> tuple[Dict[str, Dict[str, str]], str]:
        bundle: Dict[str, Dict[str, str]] = {}
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
            bundle[destination] = {
                "knowledge": knowledge.answer[:700],
                "planning": planning.answer[:1100],
            }
            parts.extend(
                [
                    f"### {destination}",
                    bundle[destination]["knowledge"],
                    "",
                    bundle[destination]["planning"],
                    "",
                ]
            )
        return bundle, "\n".join(parts)

    @staticmethod
    def _resolve_destinations(question: str, trip_context: TripContextMemory) -> List[str]:
        destinations = extract_destinations(question)
        if len(destinations) < 2 and trip_context.destination:
            destinations = unique_strings([trip_context.destination, "备选目的地"])
        elif len(destinations) < 2:
            destinations = ["东京", "大阪"]
        return destinations

    @staticmethod
    def _merge_question(base_question: str, updates: List[str]) -> str:
        if not updates:
            return base_question
        appended = "\n".join(f"- {item}" for item in updates)
        return f"{base_question}\n\n用户后续追加条件：\n{appended}"

    def _consume_updates(self, session_id: str) -> List[str]:
        with self._lock:
            run = self._active_runs.get(session_id)
            if run is None or not run.pending_updates:
                return []
            updates = list(run.pending_updates)
            run.pending_updates.clear()
            return updates

    async def _emit_status(self, on_status: StatusCallback | None, message: str) -> None:
        if on_status is not None:
            await on_status(message)

    def _compose_final_draft(
        self,
        *,
        current_question: str,
        plan: LeadPlannerPlan,
        completed_findings: Dict[str, str],
        react_steps: Dict[str, int],
        update_history: List[str],
        convergence_note: str | None = None,
    ) -> str:
        lines = [
            "# ReAct Multi-Agent 分析草稿",
            "",
            "## Lead Planner 任务拆解",
            f"- 用户问题: {current_question}",
            f"- 总目标: {plan.overall_goal}",
            f"- 决策标准: {'、'.join(plan.decision_criteria) if plan.decision_criteria else '体验、预算、节奏、风险'}",
        ]

        if update_history:
            lines.extend(
                [
                    "",
                    "## Human-in-the-Loop 追加条件",
                    *(f"- {item}" for item in update_history),
                ]
            )

        lines.extend(["", "## Specialist Findings"])
        for role_name, content in completed_findings.items():
            lines.extend(
                [
                    "",
                    f"### {role_name}",
                    f"- ReAct steps: {react_steps.get(role_name, 0)}",
                    content,
                ]
            )

        lines.extend(
            [
                "",
                "## Lead Planner 汇总任务",
                f"- 汇总要求: {plan.synthesis_instruction}",
            ]
        )

        if convergence_note:
            lines.extend(["", "## 收敛说明", f"- {convergence_note}"])

        return "\n".join(lines)

    @staticmethod
    def _format_completed_findings(completed_findings: Dict[str, str]) -> str:
        if not completed_findings:
            return ""
        return "\n\n".join(
            f"## {role_name}\n{content}" for role_name, content in completed_findings.items()
        )

    def _fallback_plan(
        self, destinations: List[str], question: str, updates: List[str]
    ) -> LeadPlannerPlan:
        return LeadPlannerPlan(
            overall_goal=f"围绕 {' / '.join(destinations)} 对用户问题做多维度旅行决策。",
            decision_criteria=["目的地适配", "交通住宿", "行程节奏", "风险与备选"],
            tasks=[
                MultiAgentTask(
                    role_name="Destination Researcher",
                    objective="比较候选目的地与用户目标的匹配度。",
                    destinations=destinations,
                    success_criteria=["明确每个目的地的亮点与适配人群"],
                ),
                MultiAgentTask(
                    role_name="Transport And Stay Analyst",
                    objective="比较交通成本、住宿区域和预算压力。",
                    destinations=destinations,
                    success_criteria=["说明哪个目的地更省心、更控预算"],
                ),
                MultiAgentTask(
                    role_name="Itinerary Designer",
                    objective="比较节奏感、按天体验和适配场景。",
                    destinations=destinations,
                    success_criteria=["说明哪种用户更适合哪条行程节奏"],
                ),
                MultiAgentTask(
                    role_name="Risk Advisor",
                    objective="识别风险和 human-in-the-loop 新增条件的影响。",
                    destinations=destinations,
                    success_criteria=["给出风险和备选建议"],
                ),
            ],
            synthesis_instruction=(
                "结合四个角色的发现，给出最终推荐、取舍理由，并说明最新追加条件如何改变结论。"
                if updates
                else "结合四个角色的发现，给出最终推荐和取舍理由。"
            ),
        )

    def _fallback_role_outputs(
        self,
        destinations: List[str],
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
    ) -> Dict[str, str]:
        return {
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
                lines.append(f"### {destination}\n" + "\n".join(result.answer.splitlines()[:6]))
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
                lines.append(f"### {destination}\n" + "\n".join(planning.answer.splitlines()[8:20]))
            return "\n\n".join(lines)

        notes: List[str] = []
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


travel_multi_agent_service = TravelMultiAgentService()
