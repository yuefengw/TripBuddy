"""Live web search and page extraction tools for the travel agent."""

from __future__ import annotations

from typing import Any, Dict, List

import httpx
from langchain_core.tools import tool
from loguru import logger

from app.config import config


def _trim_text(text: Any, limit: int = 420) -> str:
    value = str(text or "").strip().replace("\r", "")
    if len(value) <= limit:
        return value
    return f"{value[:limit].rstrip()}..."


def _search_params(query: str, location: str, num_results: int, restrict_domain: str) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "engine": "google",
        "q": query.strip(),
        "api_key": config.serpapi_api_key,
        "num": max(1, min(num_results, 10)),
        "hl": "zh-cn",
    }
    if location.strip():
        params["location"] = location.strip()
    if restrict_domain.strip():
        params["q"] = f"site:{restrict_domain.strip()} {query.strip()}"
    return params


@tool
def search_web_live(
    query: str,
    location: str = "",
    num_results: int = 5,
    restrict_domain: str = "",
) -> str:
    """Search the live web for up-to-date travel information and return concise results with URLs."""

    if not config.serpapi_api_key:
        return "Live web search is unavailable because SERPAPI_API_KEY is not configured."

    try:
        with httpx.Client(timeout=config.live_search_timeout_seconds) as client:
            response = client.get(
                f"{config.serpapi_base_url.rstrip('/')}/search.json",
                params=_search_params(query, location, num_results, restrict_domain),
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning(f"SerpAPI search failed: {exc}")
        return f"Live web search failed: {exc}"

    organic_results: List[Dict[str, Any]] = list(payload.get("organic_results") or [])
    answer_box = payload.get("answer_box") or {}

    lines: List[str] = [f"Live search results for: {query.strip()}"]
    if answer_box:
        lines.append(f"Answer box: {_trim_text(answer_box.get('answer') or answer_box.get('snippet') or '')}")

    if not organic_results:
        return "\n".join(lines + ["No organic results returned."])

    for index, item in enumerate(organic_results[: max(1, min(num_results, 6))], start=1):
        title = _trim_text(item.get("title") or "Untitled", 120)
        link = str(item.get("link") or "").strip()
        snippet = _trim_text(item.get("snippet") or item.get("snippet_highlighted_words") or "")
        source = _trim_text(item.get("source") or "", 60)
        lines.extend(
            [
                f"{index}. {title}",
                f"   URL: {link or 'N/A'}",
                f"   Source: {source or 'N/A'}",
                f"   Snippet: {snippet or 'N/A'}",
            ]
        )
    return "\n".join(lines)


@tool
def scrape_web_page(url: str, prompt: str = "") -> str:
    """Fetch and clean a webpage into readable markdown, useful after the model picks a URL to inspect."""

    if not config.firecrawl_api_key:
        return "Web page extraction is unavailable because FIRECRAWL_API_KEY is not configured."

    request_body: Dict[str, Any] = {"url": url.strip(), "formats": ["markdown"]}
    if prompt.strip():
        request_body["onlyMainContent"] = True

    try:
        with httpx.Client(timeout=config.live_search_timeout_seconds) as client:
            response = client.post(
                f"{config.firecrawl_base_url.rstrip('/')}/v1/scrape",
                headers={
                    "Authorization": f"Bearer {config.firecrawl_api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning(f"Firecrawl scrape failed for {url}: {exc}")
        return f"Web page extraction failed for {url}: {exc}"

    data = payload.get("data") or {}
    markdown = data.get("markdown") or data.get("content") or ""
    metadata = data.get("metadata") or {}
    title = _trim_text(metadata.get("title") or "", 120)
    description = _trim_text(metadata.get("description") or "", 180)
    extracted = _trim_text(markdown, 4000)

    lines = [f"Scraped page: {url.strip()}"]
    if title:
        lines.append(f"Title: {title}")
    if description:
        lines.append(f"Description: {description}")
    if prompt.strip():
        lines.append(f"Focus requested: {_trim_text(prompt, 180)}")
    lines.append("Content:")
    lines.append(extracted or "No markdown content returned.")
    return "\n".join(lines)

