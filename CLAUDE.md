# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SuperBizAgent (in directory TripBuddy) is an intelligent business agent system built with FastAPI, LangChain, and LangGraph. It supports RAG-based chat and AIOps automated fault diagnosis using a Plan-Execute-Replan pattern. The system integrates with Milvus vector database and external tools via MCP (Model Context Protocol).

## Development Commands

### Environment Setup
```bash
# Install dependencies (using uv - recommended)
uv venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"
```

### Running the Application
```bash
# Start all services (MCP + FastAPI) - Linux/macOS
make start

# Windows - use batch scripts
.\start-windows.bat

# Development mode with hot reload
make dev

# Run directly
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 9900
```

### Code Quality
```bash
make format    # Format code with ruff/black
make lint      # Lint with ruff
make fix       # Auto-fix linting issues
make type-check  # Type check with mypy
```

### Testing
```bash
make test              # Run all tests with coverage
make test-quick        # Run tests without coverage
pytest tests/ -v       # Single test file
pytest tests/ -k "test_name"  # Run tests matching pattern
```

### Docker Services
```bash
make up      # Start Milvus containers
make down     # Stop Milvus containers
make status   # Check container status
```

## Architecture

### Core Layers

1. **API Layer** (`app/api/`) - FastAPI route handlers
   - `chat.py` - RAG chat endpoints (standard + streaming)
   - `aiops.py` - AIOps diagnosis endpoints
   - `file.py` - Document upload/indexing
   - `health.py` - Health checks

2. **Agent Layer** (`app/agent/`) - Agent implementations
   - `mcp_client.py` - Global MCP client singleton using `langchain-mcp-adapters` with retry interceptor
   - `aiops/planner.py` - Plan generation (uses LLM + retrieves knowledge from vector store)
   - `aiops/executor.py` - Tool execution
   - `aiops/replanner.py` - Replanning logic
   - `aiops/state.py` - `PlanExecuteState` TypedDict for LangGraph

3. **Services Layer** (`app/services/`) - Business logic
   - `rag_agent_service.py` - LangGraph-based RAG agent with streaming, uses `ChatQwen` from `langchain_qwq`
   - `aiops_service.py` - Plan-Execute-Replan workflow orchestration via LangGraph `StateGraph`
   - `vector_*_service.py` - Vector database operations (embedding, indexing, search, store management)

4. **Tools Layer** (`app/tools/`) - Agent tools
   - `knowledge_tool.py` - `retrieve_knowledge` tool using `@tool(response_format="content_and_artifact")` decorator
   - `time_tool.py` - `get_current_time` tool

### Key Patterns

**MCP Integration**: The `get_mcp_client_with_retry()` function returns a singleton `MultiServerMCPClient` from `langchain-mcp-adapters`. It wraps tool calls with a retry interceptor using exponential backoff. MCP servers are configured via `app/config.py` (`mcp_servers` property).

**LangGraph Workflows**: Both RAG and AIOps use LangGraph:
- RAG: `create_agent()` with `MemorySaver` checkpointer for session history
- AIOps: `StateGraph` with Plan→Execute→Replan nodes and conditional edges

**Vector Store**: Uses `langchain-milvus`. Documents are chunked (configurable size/overlap), embedded with DashScope's `text-embedding-v4`, and stored in Milvus.

### External Dependencies

- **LLM**: DashScope (Alibaba Cloud) - configured via `DASHSCOPE_API_KEY` and `DASHSCOPE_API_BASE`
- **Vector DB**: Milvus (Docker-based, see `vector-database.yml`)
- **MCP Servers**: `mcp_servers/cls_server.py` (log queries) and `mcp_servers/monitor_server.py` (monitoring data)

### Configuration

All settings in `app/config.py` (Pydantic `BaseSettings`) loaded from `.env`:
- `dashscope_api_key`, `dashscope_model`, `dashscope_embedding_model`
- `milvus_host`, `milvus_port`
- `rag_top_k`, `chunk_max_size`, `chunk_overlap`
- `mcp_cls_url`, `mcp_monitor_url`

## Testing Notes

Tests live in `tests/` directory. Use `pytest` with `asyncio_mode = "auto"`. The `pyproject.toml` configures coverage to exclude test files.
