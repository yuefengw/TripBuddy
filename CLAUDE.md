# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TripBuddy is a travel planning and re-planning agent with two interaction modes:
- **Standard Search**: LLM-driven intent classification routing to knowledge Q&A, fixed workflows, or Plan-and-Execute
- **Deep Search**: Multi-agent collaboration for complex multi-constraint analysis

The system uses unified routing, layered memory management, and MCP-integrated tools.

## Development Commands

### Environment Setup
```bash
uv venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows
uv pip install -e .
uv pip install -e ".[dev]"
```

### Running the Application
```bash
# Start all services (MCP + FastAPI)
make start

# Windows
.\start-windows.bat

# Development mode with hot reload
make dev

# Run directly
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 9900
```

### Code Quality
```bash
make format      # Format code with ruff/black
make lint        # Lint with ruff
make fix         # Auto-fix linting issues
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
make down    # Stop Milvus containers
make status  # Check container status
```

## Architecture

### Intent Routing System

Requests flow through `TravelAgentService` (`app/services/travel_agent_service.py`):

1. **Intent Classification** (`travel_intent_service.py`): LLM outputs structured intent → `route.route_type`
2. **Route Types**:
   - `knowledge` → Knowledge Q&A via vector retrieval
   - `workflow` → Fixed SOP workflows (`trip_planning_workflow`, `trip_replanning_workflow`)
   - `multi_agent` → Multi-role agent collaboration (Lead Planner, Destination Researcher, etc.)
   - `plan_execute` → Plan-Execute-Replan pattern for complex dependencies

### Core Layers

1. **API Layer** (`app/api/`)
   - `chat.py` - `/api/chat`, `/api/chat_stream` (unified travel chat)
   - `file.py` - Document upload/indexing
   - `health.py` - Health checks

2. **Services Layer** (`app/services/`)
   - `travel_agent_service.py` - Orchestration entry point
   - `travel_intent_service.py` - Intent classification via LLM
   - `travel_llm_service.py` - LLM invocation (DashScope/qwen)
   - `travel_workflow_service.py` - Fixed workflow execution
   - `travel_multi_agent_service.py` - Multi-agent collaboration
   - `travel_plan_execute_service.py` - Plan-Execute-Replan orchestration
   - `travel_memory_service.py` - Session/memory management
   - `vector_*_service.py` - Milvus operations

3. **Skills Layer** (`app/skills/`)
   - Native skills: travel operations, knowledge retrieval, time
   - MCP skills: travel_server integration
   - Skill registry (`registry.py`) loads all skills at startup

4. **Agent Layer** (`app/agent/`)
   - `mcp_client.py` - Global MCP client singleton with retry interceptor
   - `aiops/` - Legacy AIOps demo (planner, executor, replanner, state)

5. **Tools Layer** (`app/tools/`)
   - `knowledge_tool.py` - Vector retrieval with `@tool(response_format="content_and_artifact")`
   - `time_tool.py` - Current time tool
   - `travel_tools.py` - Trip-related tools

### Memory Architecture

Three-layer memory (`travel_memory_service.py`):
- **Short-term**: Current session conversation history
- **User Profile**: Budget, travel style, dietary restrictions, accommodation preferences
- **Trip Context**: Destination, days, must-do items, current plan, constraints

### MCP Integration

`get_mcp_client_with_retry()` in `mcp_client.py` returns a singleton `MultiServerMCPClient`. Three servers configured:
- `travel` - Travel operations (primary)
- `cls`, `monitor` - Legacy AIOps demo

### Vector Store

Uses `langchain-milvus`. Documents chunked (configurable `chunk_max_size`/`chunk_overlap`), embedded via DashScope `text-embedding-v4`.

## Configuration

All settings in `app/config.py` (Pydantic `BaseSettings`) from `.env`:
- DashScope: `dashscope_api_key`, `dashscope_model`, `dashscope_embedding_model`
- Milvus: `milvus_host`, `milvus_port`
- RAG: `rag_top_k`, `chunk_max_size`, `chunk_overlap`
- MCP: `mcp_travel_url`, `mcp_cls_url`, `mcp_monitor_url`

## Testing Notes

Tests in `tests/`, use `pytest` with `asyncio_mode = "auto"` (configured in `pyproject.toml`).

## Legacy AIOps

The `/api/aiops` endpoint and `mcp_servers/cls_server.py`, `mcp_servers/monitor_server.py` are retained as legacy demos. The primary product is the travel agent.
