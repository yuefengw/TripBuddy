"""Deterministic workflows for the slimmed-down travel assistant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.models.travel import TripContextMemory, UserProfileMemory
from app.services.travel_utils import (
    extract_budget_amount,
    extract_destination,
    extract_duration_days,
    extract_interests,
    extract_month,
    unique_strings,
)


DESTINATION_CATALOG: List[Dict[str, object]] = [
    {
        "name": "成都",
        "best_months": ["4月", "5月", "6月", "10月"],
        "budget_level": "medium",
        "tags": ["美食", "休闲", "人文", "慢节奏"],
        "highlights": ["宽窄巷子", "人民公园", "大熊猫基地", "川菜和火锅"],
    },
    {
        "name": "重庆",
        "best_months": ["3月", "4月", "10月", "11月"],
        "budget_level": "medium",
        "tags": ["夜景", "美食", "城市漫游"],
        "highlights": ["洪崖洞", "解放碑", "李子坝", "山城步道"],
    },
    {
        "name": "杭州",
        "best_months": ["3月", "4月", "5月", "10月"],
        "budget_level": "medium",
        "tags": ["自然", "休闲", "拍照", "情侣"],
        "highlights": ["西湖", "灵隐寺", "龙井村", "河坊街"],
    },
    {
        "name": "东京",
        "best_months": ["3月", "4月", "5月", "10月", "11月"],
        "budget_level": "high",
        "tags": ["二次元", "购物", "亲子", "城市漫游"],
        "highlights": ["浅草寺", "涩谷", "上野", "迪士尼"],
    },
    {
        "name": "大阪",
        "best_months": ["3月", "4月", "5月", "10月", "11月"],
        "budget_level": "high",
        "tags": ["美食", "亲子", "乐园", "购物"],
        "highlights": ["环球影城", "道顿堀", "心斋桥", "大阪城"],
    },
    {
        "name": "新加坡",
        "best_months": ["2月", "3月", "7月", "8月"],
        "budget_level": "high",
        "tags": ["亲子", "城市休闲", "整洁", "美食"],
        "highlights": ["滨海湾花园", "圣淘沙", "环球影城", "牛车水"],
    },
]


@dataclass
class WorkflowResult:
    answer: str
    metadata: Dict[str, object]


class TravelWorkflowService:
    """Core fixed workflows after product simplification."""

    def run_workflow(
        self,
        workflow_name: str,
        question: str,
        user_profile: UserProfileMemory,
        trip_context: TripContextMemory,
    ) -> WorkflowResult:
        if workflow_name == "trip_replanning_workflow":
            return self.trip_replanning_workflow(question, user_profile, trip_context)
        return self.trip_planning_workflow(question, user_profile, trip_context)

    def trip_planning_workflow(
        self, question: str, user_profile: UserProfileMemory, trip_context: TripContextMemory
    ) -> WorkflowResult:
        destination = trip_context.destination or extract_destination(question)
        days = trip_context.duration_days or extract_duration_days(question) or 4
        month = trip_context.travel_month or extract_month(question) or "近期"
        budget_amount = trip_context.budget_amount or extract_budget_amount(question)
        interests = unique_strings(
            [*trip_context.interests, *extract_interests(question), *user_profile.travel_style]
        )
        companions = unique_strings(
            [*trip_context.companions, *user_profile.companion_preference]
        ) or ["普通出行"]
        pace = user_profile.pace_preference or "均衡节奏"

        recommendations = self._recommend_destinations(
            month=month,
            budget_amount=budget_amount,
            interests=interests,
            pace=pace,
        )
        selected_destination = destination or recommendations[0]["name"]

        lines = [
            "# 旅行规划 Workflow",
            "",
            "## Step 1: 需求理解",
            f"- 规划目标: {question}",
            f"- 关键约束: 目的地={selected_destination} | 天数={days} | 预算={budget_amount or '待确认'} | 同行人={'、'.join(companions)}",
            f"- 偏好画像: 节奏={pace} | 兴趣={'、'.join(interests) if interests else '经典景点 + 美食 + 轻探索'}",
            "",
            "## Step 2: 方案落点",
        ]

        if destination:
            lines.extend(
                [
                    f"- 已确定目的地: {selected_destination}",
                    f"- 推荐出行月份参考: {month}",
                    f"- 适配理由: {self._destination_reason(selected_destination)}",
                ]
            )
        else:
            lines.append("- 用户还未完全锁定目的地，先给出适配度最高的候选方案：")
            for index, item in enumerate(recommendations[:3], start=1):
                lines.append(
                    f"  {index}. {item['name']} | 亮点: {'、'.join(item['highlights'][:2])} | 标签: {'、'.join(item['tags'][:3])}"
                )
            lines.append(f"- 本次 workflow 先以下述主方案继续展开: {selected_destination}")

        lines.extend(
            [
                "",
                "## Step 3: 行程骨架",
                *self._build_day_plan(selected_destination, days, interests, companions),
                "",
                "## Step 4: 预算与准备提醒",
                *self._build_budget_and_prep_notes(
                    destination=selected_destination,
                    days=days,
                    budget_amount=budget_amount,
                    companions=companions,
                    user_profile=user_profile,
                ),
            ]
        )

        return WorkflowResult(
            answer="\n".join(lines),
            metadata={
                "destination": selected_destination,
                "days": days,
                "month": month,
                "interests": interests,
                "recommended_destinations": [item["name"] for item in recommendations[:3]],
                "workflow_kind": "trip_planning",
            },
        )

    def trip_replanning_workflow(
        self, question: str, user_profile: UserProfileMemory, trip_context: TripContextMemory
    ) -> WorkflowResult:
        destination = trip_context.destination or extract_destination(question) or "当前目的地"
        current_plan = trip_context.current_plan or "暂无完整已确认行程，可按问题中的当前安排理解"
        must_do = unique_strings(trip_context.must_do or ["核心地标", "招牌美食"])
        constraints = unique_strings(
            [
                *trip_context.constraints,
                user_profile.pace_preference or "",
                user_profile.accommodation_preference or "",
            ]
        )
        issue_summary = self._summarize_issue(question)
        replacement_options = self._build_replacement_options(issue_summary, destination)
        updated_outline = self._build_updated_outline(destination, current_plan, replacement_options)

        lines = [
            "# 行程重规划 Workflow",
            "",
            "## Step 1: 当前状态确认",
            f"- 目的地: {destination}",
            f"- 当前计划摘要: {current_plan[:240]}",
            f"- 必保留项: {'、'.join(must_do)}",
            f"- 约束条件: {'、'.join(constraints) if constraints else '优先最小化改动'}",
            "",
            "## Step 2: 受影响环节判断",
            f"- 问题描述: {question}",
            f"- 影响摘要: {issue_summary}",
            "",
            "## Step 3: 替换策略",
            *[f"- {item}" for item in replacement_options],
            "",
            "## Step 4: 更新后的建议安排",
            *[f"- {item}" for item in updated_outline],
            "",
            "## Step 5: 执行提醒",
            "- 先确认不可变约束是否变化，例如返程时间、同行人体力、酒店位置。",
            "- 优先保留 must-do，再替换受影响的半天安排。",
            "- 如果这次改动已经波及多天计划，建议升级到 Plan-and-Execute 做完整重排。",
        ]

        return WorkflowResult(
            answer="\n".join(lines),
            metadata={
                "destination": destination,
                "issue_summary": issue_summary,
                "updated_plan": True,
                "workflow_kind": "trip_replanning",
            },
        )

    def answer_knowledge_question(
        self, question: str, user_profile: UserProfileMemory, trip_context: TripContextMemory
    ) -> WorkflowResult:
        destination = trip_context.destination or extract_destination(question)
        context_text = ""

        try:
            from app.tools import retrieve_knowledge

            retrieved = retrieve_knowledge.invoke({"query": question})
            if isinstance(retrieved, tuple):
                context_text = str(retrieved[0] or "")
            else:
                context_text = str(retrieved or "")
        except Exception:
            context_text = ""

        lines = ["# 旅行知识问答", ""]
        if destination:
            lines.extend([f"- 当前聚焦目的地: {destination}", ""])

        if context_text and "没有找到相关" not in context_text and "错误" not in context_text:
            lines.extend(
                [
                    "## 知识库参考",
                    context_text[:1200],
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "## 直接建议",
                    "- 先明确你的核心目标，是轻松度假、城市漫游、美食打卡还是亲子出行。",
                    "- 如果还没锁定目的地，优先看季节、预算和同行人，再决定主方案。",
                    "- 如果已经锁定目的地，我可以继续把它展开成固定流程的行程规划。",
                    "",
                    "## 可以继续怎么问",
                    "- 帮我做一个 5 天行程",
                    "- 帮我在预算内规划",
                    "- 帮我调整已有安排",
                ]
            )

        if "天气" in question or "汇率" in question or "签证" in question:
            lines.extend(
                [
                    "",
                    "## 实时信息说明",
                    "- 当前版本不会编造实时天气、汇率或官方签证政策。",
                    "- 如果你已经有明确事实条件，例如“后天下雨”或“预算 1 万”，我可以基于这些条件继续规划。",
                ]
            )

        return WorkflowResult(
            answer="\n".join(lines),
            metadata={"destination": destination, "workflow_kind": "knowledge"},
        )

    @staticmethod
    def _recommend_destinations(
        *,
        month: str,
        budget_amount: int | None,
        interests: List[str],
        pace: str,
    ) -> List[Dict[str, object]]:
        ranked: List[tuple[int, Dict[str, object]]] = []
        for candidate in DESTINATION_CATALOG:
            score = 0
            if month in candidate["best_months"]:  # type: ignore[operator]
                score += 2
            score += sum(tag in interests for tag in candidate["tags"])  # type: ignore[arg-type]
            if pace == "慢节奏" and "慢节奏" in candidate["tags"]:  # type: ignore[operator]
                score += 1
            if budget_amount:
                if budget_amount >= 8000 and candidate["budget_level"] == "high":
                    score += 1
                if 3000 <= budget_amount < 8000 and candidate["budget_level"] == "medium":
                    score += 1
            ranked.append((score, candidate))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in ranked[:3]]

    @staticmethod
    def _destination_reason(destination: str) -> str:
        for candidate in DESTINATION_CATALOG:
            if candidate["name"] == destination:
                return f"{destination} 更适合 { '、'.join(candidate['tags'][:3]) } 导向的行程。"
        return "已根据你的约束继续往下展开主方案。"

    @staticmethod
    def _build_day_plan(
        destination: str, days: int, interests: List[str], companions: List[str]
    ) -> List[str]:
        parent_friendly = "带娃" in companions or "亲子" in companions
        slow_trip = "慢节奏" in interests or "休闲" in interests
        food_trip = "美食" in interests

        templates = [
            {
                "morning": f"{destination} 经典区域漫步 + 地标打卡",
                "afternoon": "重点景点 + 周边商圈或咖啡馆休整",
                "evening": "热门餐饮区用餐 + 夜景漫游",
                "transport": "优先地铁/步行，减少跨区折返",
            },
            {
                "morning": "慢节奏早餐 + 半天人文路线" if slow_trip else "上午优先核心景点，避开高峰排队",
                "afternoon": "特色街区探索或博物馆/展馆",
                "evening": "回酒店附近轻松收尾，控制返程距离",
                "transport": "把同一区域活动放在同一天",
            },
        ]
        if food_trip:
            templates.append(
                {
                    "morning": "老店早餐 / 菜市场风味体验",
                    "afternoon": "围绕地道风味店做街区漫游",
                    "evening": "夜市 / 酒吧街 / 招牌餐厅三选一",
                    "transport": "围绕餐饮密集区安排住宿和动线",
                }
            )
        if parent_friendly:
            templates.append(
                {
                    "morning": "儿童友好景点或轻量乐园项目",
                    "afternoon": "中途回酒店休整，再安排一个室内项目",
                    "evening": "提前吃饭，避免过晚返程",
                    "transport": "优先直达和少换乘",
                }
            )

        lines: List[str] = []
        for day in range(1, days + 1):
            template = templates[(day - 1) % len(templates)]
            lines.extend(
                [
                    f"### Day {day}",
                    f"- 上午: {template['morning']}",
                    f"- 下午: {template['afternoon']}",
                    f"- 晚上: {template['evening']}",
                    f"- 动线说明: {template['transport']}",
                ]
            )
        return lines

    @staticmethod
    def _build_budget_and_prep_notes(
        *,
        destination: str,
        days: int,
        budget_amount: int | None,
        companions: List[str],
        user_profile: UserProfileMemory,
    ) -> List[str]:
        travelers = max(len(companions), 1)
        is_domestic = destination in {"成都", "重庆", "杭州", "长沙", "西安", "北京", "上海"}
        transport_cost = 400 * travelers if is_domestic else 1800 * travelers
        stay_cost = (350 if user_profile.accommodation_preference == "市中心" else 280) * days
        meal_cost = 150 * days * travelers
        ticket_cost = 180 * days * travelers
        total = transport_cost + stay_cost + meal_cost + ticket_cost

        lines = [
            f"- 粗略预算拆分: 交通约 {transport_cost} 元 / 住宿约 {stay_cost} 元 / 餐饮约 {meal_cost} 元 / 门票活动约 {ticket_cost} 元",
            f"- 预计总计: 约 {total} 元",
        ]
        if budget_amount:
            status = "可控" if total <= budget_amount * 1.1 else "偏紧"
            lines.append(f"- 与用户预算对比: 当前方案对 {budget_amount} 元预算来说整体 {status}")
        if user_profile.dietary_preferences:
            lines.append(f"- 饮食偏好提醒: {'、'.join(user_profile.dietary_preferences)}")
        if "带娃" in companions or "亲子" in companions:
            lines.append("- 行前准备提醒: 记得预留午休、备药和轻便雨具")
        if "老人同行" in companions:
            lines.append("- 行前准备提醒: 优先地铁/打车便利区域，减少连续步行")
        return lines

    @staticmethod
    def _summarize_issue(question: str) -> str:
        lowered = question.lower()
        if "雨" in question:
            return "天气变化会影响户外活动，需要优先替换为室内或短距离方案。"
        if "delay" in lowered or "延误" in question or "取消" in question:
            return "交通异常会压缩到达后的可用时间，需要重排首日或后续衔接。"
        return "当前需求更像对已有安排做局部调整，需要优先保持主线路不变。"

    @staticmethod
    def _build_replacement_options(issue_summary: str, destination: str) -> List[str]:
        if "天气变化" in issue_summary:
            return [
                f"把 {destination} 的室外活动换成博物馆、商圈、特色餐饮区等室内替代方案",
                "把跨区移动压缩到最少，围绕酒店周边 1 到 2 个区域活动",
                "优先保留 must-do 的地标或美食，再把次优先景点后移",
            ]
        if "交通异常" in issue_summary:
            return [
                "压缩首日安排，只保留优先级最高的 1 到 2 个项目",
                "把轻量活动放到酒店周边，避免晚到后继续长距离换乘",
                "把需要预约或强时段性的活动挪到后一天重新执行",
            ]
        return [
            "保持主目的地和住宿基点不变，只替换受影响的半天安排",
            "优先用就近替代方案覆盖空档，减少整条路线被打乱",
            "确认 must-do 是否仍然要保留在当天，否则后移处理",
        ]

    @staticmethod
    def _build_updated_outline(
        destination: str, current_plan: str, replacement_options: List[str]
    ) -> List[str]:
        return [
            f"先围绕 {destination} 的既有动线保留核心项目，不从头改完整个行程",
            f"当前计划参考: {current_plan[:120]}",
            f"优先执行策略: {replacement_options[0]}",
            "把替代活动尽量安排在同一区域，减少新一轮折返",
        ]


travel_workflow_service = TravelWorkflowService()
