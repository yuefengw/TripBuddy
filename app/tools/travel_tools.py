"""Travel-specific local tools exposed through the unified skill registry."""

from __future__ import annotations

from langchain_core.tools import tool

from app.services.travel_memory_service import travel_memory_service
from app.services.travel_utils import unique_strings
from app.services.travel_workflow_service import travel_workflow_service


@tool
def estimate_trip_budget(
    destination: str,
    days: int = 3,
    travelers: int = 1,
    accommodation_level: str = "舒适型酒店",
) -> str:
    """Estimate a rough travel budget for a destination."""

    transport_cost = 400 * travelers if destination in {"成都", "重庆", "杭州", "长沙"} else 1800 * travelers
    stay_cost = (350 if accommodation_level == "舒适型酒店" else 260) * days
    meal_cost = 150 * days * travelers
    ticket_cost = 180 * days * travelers
    total = transport_cost + stay_cost + meal_cost + ticket_cost

    return (
        f"{destination} {days} 天预算估算\n"
        f"- 交通: 约 {transport_cost} 元\n"
        f"- 住宿: 约 {stay_cost} 元\n"
        f"- 餐饮: 约 {meal_cost} 元\n"
        f"- 门票活动: 约 {ticket_cost} 元\n"
        f"- 总计: 约 {total} 元"
    )


@tool
def build_itinerary_outline(
    destination: str,
    days: int = 3,
    interests: str = "",
    companions: str = "",
) -> str:
    """Build a planning-workflow outline for a destination."""

    trip_context = {
        "destination": destination,
        "duration_days": days,
        "interests": unique_strings(interests.split("、") if interests else []),
        "companions": unique_strings(companions.split("、") if companions else []),
    }
    result = travel_workflow_service.trip_planning_workflow(
        f"帮我规划 {destination} 行程",
        user_profile=travel_memory_service.get_user_profile("default"),
        trip_context=travel_memory_service.get_trip_context("default").model_copy(update=trip_context),
    )
    return result.answer


@tool
def build_packing_checklist(destination: str, season: str = "当季", companions: str = "") -> str:
    """Generate a lightweight travel preparation checklist as a tool output."""

    companion_list = unique_strings(companions.split("、") if companions else [])
    lines = [
        f"{destination} 行前准备清单",
        f"- 适用时段: {season}",
        f"- 同行人: {'、'.join(companion_list) if companion_list else '普通出行'}",
        "- 证件与订单: 身份证/护照、酒店订单、交通订单、保险截图",
        "- 电子设备: 充电器、充电宝、转换插头、网络方案",
        "- 行李基础项: 舒适步行鞋、常备药品、雨具、随身水杯",
    ]
    if "带娃" in companion_list or "亲子" in companion_list:
        lines.append("- 亲子提醒: 备好湿巾、儿童药品、可替换零食和轻便外套")
    if "老人同行" in companion_list:
        lines.append("- 长辈提醒: 优先准备常用药、弹性行程和少换乘路线")
    return "\n".join(lines)


@tool
def summarize_preference_memory(session_id: str) -> str:
    """Load the current user preference memory for a session."""

    profile = travel_memory_service.get_user_profile(session_id)
    return (
        f"session={session_id}\n"
        f"budget_preference={profile.budget_preference or 'unknown'}\n"
        f"travel_style={'、'.join(profile.travel_style) or 'unknown'}\n"
        f"dietary_preferences={'、'.join(profile.dietary_preferences) or 'unknown'}\n"
        f"pace_preference={profile.pace_preference or 'unknown'}\n"
        f"accommodation_preference={profile.accommodation_preference or 'unknown'}\n"
        f"companion_preference={'、'.join(profile.companion_preference) or 'unknown'}"
    )


@tool
def build_trip_replan_options(issue: str, destination: str, current_plan: str = "") -> str:
    """Generate a local fallback re-planning suggestion bundle."""

    if "雨" in issue:
        strategy = "优先替换成室内景点、商圈和短距离步行方案，并缩短跨区移动。"
    elif "延误" in issue or "取消" in issue:
        strategy = "压缩首日安排，只保留高优先级项目，并把轻量活动放到酒店周边。"
    else:
        strategy = "保留 must-do 项目，再围绕住宿点做就近替换，避免整段路线被打乱。"

    return (
        f"{destination} 重规划建议\n"
        f"- 问题: {issue}\n"
        f"- 当前计划摘要: {current_plan[:120] or '暂无'}\n"
        f"- 调整策略: {strategy}\n"
        "- 备选活动方向: 室内景点 / 商圈 / 特色餐饮区 / 近距离步行路线"
    )
