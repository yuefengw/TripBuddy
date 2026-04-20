"""Knowledge retrieval tool backed by Milvus."""

from __future__ import annotations

from typing import List, Tuple

from langchain_core.documents import Document
from langchain_core.tools import tool
from loguru import logger

from app.config import config
from app.services.vector_store_manager import vector_store_manager


@tool(response_format="content_and_artifact")
def retrieve_knowledge(query: str) -> Tuple[str, List[Document]]:
    """Retrieve relevant knowledge-base passages for a query."""

    try:
        logger.info(f"Knowledge retrieval tool called with query={query!r}")
        vector_store = vector_store_manager.get_vector_store()
        retriever = vector_store.as_retriever(search_kwargs={"k": config.rag_top_k})
        docs = retriever.invoke(query)
        if not docs:
            return "没有找到相关旅行资料。", []
        return format_docs(docs), docs
    except Exception as exc:
        logger.error(f"Knowledge retrieval failed: {exc}")
        return f"检索知识时发生错误: {exc}", []


def format_docs(docs: List[Document]) -> str:
    """Format retrieved docs into readable context text."""

    formatted_parts: List[str] = []
    for index, doc in enumerate(docs, start=1):
        metadata = doc.metadata
        source = metadata.get("_file_name", "未知来源")
        headers = [metadata[key] for key in ("h1", "h2", "h3") if metadata.get(key)]
        title = " > ".join(headers)
        block = [f"【参考资料 {index}】"]
        if title:
            block.append(f"标题: {title}")
        block.append(f"来源: {source}")
        block.append("内容:")
        block.append(doc.page_content)
        formatted_parts.append("\n".join(block))
    return "\n\n".join(formatted_parts)
