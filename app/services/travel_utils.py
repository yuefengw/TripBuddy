"""Shared travel domain helpers used across routing, workflows and memory."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional


KNOWN_DESTINATIONS = [
    "东京",
    "大阪",
    "京都",
    "北海道",
    "冲绳",
    "首尔",
    "釜山",
    "新加坡",
    "曼谷",
    "清迈",
    "普吉",
    "巴厘岛",
    "巴黎",
    "伦敦",
    "罗马",
    "成都",
    "重庆",
    "长沙",
    "杭州",
    "上海",
    "北京",
    "西安",
    "厦门",
    "三亚",
    "云南",
    "昆明",
    "大理",
    "丽江",
    "广州",
    "深圳",
    "香港",
    "澳门",
    "青岛",
    "南京",
    "苏州",
    "天津",
]

INTEREST_KEYWORDS = [
    "美食",
    "亲子",
    "拍照",
    "海边",
    "二次元",
    "购物",
    "博物馆",
    "自然",
    "徒步",
    "温泉",
    "夜景",
    "乐园",
    "古镇",
    "人文",
    "慢节奏",
    "休闲",
]


def unique_strings(values: Iterable[str]) -> List[str]:
    """Deduplicate strings while keeping order."""

    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def extract_budget_amount(text: str) -> Optional[int]:
    """Extract a rough budget amount from natural language."""

    match = re.search(r"预算\s*(?:在|大概|约|差不多)?\s*(\d+(?:\.\d+)?)\s*(万|w|k|千|元)?", text)
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(万|w|k|千|元)\s*预算", text)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2) or "元"

    if unit in {"万", "w"}:
        amount *= 10000
    elif unit == "k":
        amount *= 1000
    elif unit == "千":
        amount *= 1000

    return int(amount)


def extract_duration_days(text: str) -> Optional[int]:
    """Extract trip duration in days."""

    match = re.search(r"(\d+)\s*(?:天|日)(?:\d+\s*晚)?", text)
    if match:
        return int(match.group(1))

    match = re.search(r"(\d+)\s*晚\s*(\d+)\s*天", text)
    if match:
        return int(match.group(2))

    return None


def extract_month(text: str) -> Optional[str]:
    """Extract travel month or season info."""

    match = re.search(r"(\d{1,2})\s*月", text)
    if match:
        return f"{int(match.group(1))}月"

    for season in ("春天", "夏天", "秋天", "冬天", "暑假", "寒假", "国庆", "五一"):
        if season in text:
            return season

    return None


def extract_destinations(text: str) -> List[str]:
    """Extract one or more destinations from a question."""

    destinations = [city for city in KNOWN_DESTINATIONS if city in text]
    if destinations:
        return unique_strings(destinations)

    pattern = re.findall(r"(?:去|到|玩|在|规划|安排)([\u4e00-\u9fa5]{2,8})", text)
    filtered = [
        item
        for item in pattern
        if item not in {"什么", "哪里", "一下", "一个", "一下子", "这个", "那个"}
    ]
    return unique_strings(filtered[:3])


def extract_destination(text: str) -> Optional[str]:
    """Extract the primary destination."""

    destinations = extract_destinations(text)
    return destinations[0] if destinations else None


def extract_origin(text: str) -> Optional[str]:
    """Extract departure city."""

    match = re.search(r"(?:从|由)([\u4e00-\u9fa5]{2,8})(?:出发|过去|飞)", text)
    if match:
        return match.group(1)
    return None


def extract_interests(text: str) -> List[str]:
    """Extract interests or trip themes."""

    detected = [keyword for keyword in INTEREST_KEYWORDS if keyword in text]
    return unique_strings(detected)


def extract_companions(text: str) -> List[str]:
    """Extract companion context."""

    candidates = []
    mapping = {
        "一家三口": "亲子",
        "孩子": "带娃",
        "宝宝": "带娃",
        "父母": "老人同行",
        "老人": "老人同行",
        "情侣": "情侣",
        "朋友": "朋友",
        "闺蜜": "朋友",
        "一个人": "独自出行",
        "独自": "独自出行",
    }
    for key, normalized in mapping.items():
        if key in text:
            candidates.append(normalized)
    return unique_strings(candidates)


def extract_preference_notes(text: str) -> List[str]:
    """Extract stable preference notes from user text."""

    patterns = [
        "不吃辣",
        "喜欢慢节奏",
        "喜欢拍照",
        "预算有限",
        "喜欢自由行",
        "带老人",
        "带孩子",
        "不想太赶",
        "偏好地铁方便",
        "喜欢住市中心",
    ]
    return [item for item in patterns if item in text]


def chunk_text(text: str, chunk_size: int = 120) -> List[str]:
    """Chunk text into fixed-size slices for simple SSE streaming."""

    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)] or [""]

