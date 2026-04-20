"""Mock travel MCP server for weather, FX, visa and POI lookups."""

from __future__ import annotations

from typing import Any, Dict, List

from fastmcp import FastMCP


mcp = FastMCP("Travel")


TRAVEL_FACTS: Dict[str, Dict[str, Any]] = {
    "东京": {
        "weather": {"4月": "白天温和，早晚略凉，适合城市步行", "11月": "适合看红叶，注意早晚温差"},
        "currency": "JPY",
        "visa": "如使用中国护照前往日本，请以最新签证政策和材料要求为准。",
        "pois": {
            "亲子": ["东京迪士尼", "上野动物园", "台场 teamLab"],
            "二次元": ["秋叶原", "池袋乙女路", "中野百老汇"],
            "美食": ["筑地 / 丰洲周边", "新宿居酒屋街", "浅草小吃线"],
        },
    },
    "大阪": {
        "weather": {"4月": "气候舒适，适合城市+乐园组合", "11月": "适合逛吃和周边一日游"},
        "currency": "JPY",
        "visa": "如使用中国护照前往日本，请以最新签证政策和材料要求为准。",
        "pois": {
            "亲子": ["环球影城", "海游馆", "天保山周边"],
            "美食": ["道顿堀", "黑门市场", "心斋桥"],
            "购物": ["梅田", "心斋桥", "临空城"],
        },
    },
    "新加坡": {
        "weather": {"全年": "常年炎热潮湿，建议轻装并准备雨具"},
        "currency": "SGD",
        "visa": "请以出发前官方政策为准，关注入境卡和签证要求。",
        "pois": {
            "亲子": ["圣淘沙", "滨海湾花园", "新加坡环球影城"],
            "美食": ["麦士威熟食中心", "老巴刹", "牛车水"],
            "拍照": ["鱼尾狮", "滨海湾", "甘榜格南"],
        },
    },
    "成都": {
        "weather": {"6月": "湿热感上升，建议午后安排室内活动", "10月": "舒适宜人，适合慢节奏漫游"},
        "currency": "CNY",
        "visa": "中国境内目的地无需签证，请关注天气和预约信息。",
        "pois": {
            "美食": ["建设路", "奎星楼街", "玉林路"],
            "慢节奏": ["人民公园", "宽窄巷子", "望平街"],
            "亲子": ["大熊猫基地", "东郊记忆", "博物馆"],
        },
    },
}

FX_RATES = {
    "JPY": "1 人民币约兑 20 日元（模拟值）",
    "SGD": "1 新加坡元约兑 5.4 人民币（模拟值）",
    "USD": "1 美元约兑 7.2 人民币（模拟值）",
}


@mcp.tool()
def get_destination_weather(destination: str, travel_month: str = "全年") -> Dict[str, Any]:
    """Return mock destination weather guidance."""

    facts = TRAVEL_FACTS.get(destination, {})
    weather = facts.get("weather", {})
    summary = weather.get(travel_month) or weather.get("全年") or "暂无该目的地天气数据，请以实时天气为准。"
    return {"destination": destination, "travel_month": travel_month, "summary": summary, "is_mock": True}


@mcp.tool()
def get_exchange_rate(currency: str) -> Dict[str, Any]:
    """Return a mock FX rate string."""

    return {
        "currency": currency,
        "summary": FX_RATES.get(currency.upper(), "暂无该币种汇率模拟数据"),
        "is_mock": True,
    }


@mcp.tool()
def get_visa_hint(destination: str, passport_country: str = "中国") -> Dict[str, Any]:
    """Return a mock visa reminder."""

    facts = TRAVEL_FACTS.get(destination, {})
    return {
        "destination": destination,
        "passport_country": passport_country,
        "summary": facts.get("visa", "请以官方签证政策和航空公司要求为准。"),
        "is_mock": True,
    }


@mcp.tool()
def suggest_pois(destination: str, theme: str = "美食") -> Dict[str, List[str] | str | bool]:
    """Return mock POI suggestions by theme."""

    facts = TRAVEL_FACTS.get(destination, {})
    pois = facts.get("pois", {})
    suggestions = pois.get(theme, [])
    return {
        "destination": destination,
        "theme": theme,
        "suggestions": suggestions or ["暂无该主题 POI，建议切换主题或补充更具体的偏好"],
        "is_mock": True,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8005, path="/mcp")
