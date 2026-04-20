# TripBuddy Travel Agent

> 一个面向旅行规划与行中重规划场景的 Agent 助手。  
> 项目重点不是“替用户直接下单”，而是展示一套可落地的 `意图识别 + 路由分发 + workflow / agent 双轨执行 + 统一工具调用 + 记忆管理` 架构。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-orange.svg)](https://www.langchain.com/langgraph)

## 项目定位

TripBuddy 是一个旅行 Agent 助手，面向以下两类核心需求：

- 行前规划：目的地咨询、结构化行程生成、预算与准备建议
- 行中调整：下雨、延误、临时改计划等情况下的局部重规划或复杂重排

当前产品交互被收敛为两种搜索模式：

- `标准搜索`
  先做 LLM 语义意图识别，再分流到 `知识问答`、`固定 workflow` 或 `Plan-and-Execute`
- `深度搜索`
  直接进入 `Multi-Agent` 协作，适合多约束、多方案比较和复杂分析

## 核心能力

### 1. LLM 驱动的意图识别与路由

不是基于关键词匹配，而是由 LLM 输出结构化分类结果，再由 policy layer 决定最终执行模式。

标准搜索下的典型路由：

- `knowledge`
  单点旅行咨询、轻攻略问答
- `workflow -> trip_planning_workflow`
  行前规划，输入约束明确，适合固定流程
- `workflow -> trip_replanning_workflow`
  局部重规划，问题边界清晰，适合固定流程
- `plan_execute`
  多约束、强依赖、需要连续拆解和执行的复杂问题

深度搜索下的路由：

- `multi_agent`
  直接进入多角色协作

### 2. 只保留两个合理的固定 Workflow

项目没有把 workflow 拆得很碎，而是只保留两个真正“适合提前固定流程”的场景。

#### `trip_planning_workflow`

适用于行前规划，因为它的输入字段、处理步骤和输出结构都比较稳定。

固定步骤：

1. 需求理解
2. 目的地 / 方案落点
3. 行程骨架生成
4. 预算与准备提醒

这条 workflow 适合回答：

- `帮我做一个 4 天重庆美食行程，预算 3000`
- `帮我规划 5 天东京行程，喜欢二次元和美食`

#### `trip_replanning_workflow`

适用于局部、可控的重规划，因为它本质上是一个带上下文的 SOP。

固定步骤：

1. 当前计划确认
2. 受影响环节判断
3. 替换策略生成
4. 更新后的建议安排

这条 workflow 适合回答：

- `明天杭州下雨，原本西湖划船怎么调`
- `今天下午临时取消一个景点，晚上不想太晚回酒店，怎么改`

### 3. ReAct 风格 Multi-Agent

深度搜索会直接走多智能体协作。当前角色包括：

- `Lead Planner`
  主 Agent，负责理解任务、拆解子问题、汇总结果
- `Destination Researcher`
  负责目的地知识、季节、景点与基础信息
- `Transport And Stay Analyst`
  负责交通、住宿区域、预算测算
- `Itinerary Designer`
  负责按天排程和节奏控制
- `Risk Advisor`
  负责天气、闭馆、体力负担、行中风险提示

适用问题：

- `东京和大阪哪个更适合带 6 岁孩子玩 5 天，预算 1 万，请给两个方案比较`
- `一家三口去日本 7 天，要轻松一点，比较东京/大阪/京都三种方案`

### 4. Plan-and-Execute

标准搜索下，复杂但不一定要进入深度搜索的问题，会进入 `Plan-and-Execute`。

它适合这些情况：

- 需要先规划，再逐步执行，再汇总
- 多个约束之间有依赖关系
- 已有计划需要跨多天、跨城市或跨多个条件重新协调

典型场景：

- `我周五到东京，周日晚上还要去大阪见朋友，预算有限，还担心下雨，帮我重排`

### 5. 统一工具调用框架

项目统一了三类能力接入方式：

- `Function Call Tool`
  本地函数型工具，适合预算估算、行程模板生成、清单辅助等逻辑
- `MCP Tool`
  通过 MCP 协议接入外部能力
- `Skill`
  把多个函数或 MCP 工具封装成更高层的业务能力

当前保留的 MCP 相关内容：

- `travel_server.py`
  旅行场景 mock MCP 服务
- `cls_server.py` / `monitor_server.py`
  仓库中仍保留的旧 AIOps MCP 示例

### 6. 记忆管理

项目中的记忆分为三层：

- `短期会话记忆`
  保存当前 session 的上下文
- `长期用户画像`
  保存预算偏好、旅行风格、饮食禁忌、住宿偏好等
- `Trip Context`
  保存当前旅行任务的目的地、天数、must-do、当前计划、约束条件等

这样在后续对话中，系统可以做到：

- 记住用户不吃辣、偏慢节奏
- 记住当前 trip 的目的地与已有安排
- 在重规划时直接读取上下文，而不是每轮都让用户重复说明

## 为什么这套设计在面试里讲得过去

这个项目没有把所有能力都硬塞成 workflow，而是做了清晰的边界划分：

- 高结构化、高重复、输出稳定的任务 -> 固定 workflow
- 多约束、多视角、需要拆任务的问题 -> Multi-Agent
- 强依赖、强顺序、需要连续推理的问题 -> Plan-and-Execute
- 单点轻咨询 -> Knowledge Q&A

这比“所有问题都让一个 agent 自由发挥”更稳定，也比“所有问题都拆成 workflow”更合理。

## 系统架构

### 交互层

- FastAPI 提供 `/api/chat`、`/api/chat_stream`
- 静态前端位于 `static/`
- 前端支持：
  - 标准搜索
  - 深度搜索
  - 流式回复
  - 会话历史
  - 本地前端缓存

### 编排层

- `travel_agent_service.py`
  统一入口，负责路由、记忆整合、编排执行和最终回答
- `travel_intent_service.py`
  LLM 结构化意图识别与 policy routing
- `travel_llm_service.py`
  LLM 调用封装
- `travel_multi_agent_service.py`
  多角色协作
- `travel_plan_execute_service.py`
  Plan-and-Execute 编排
- `travel_workflow_service.py`
  固定 workflow 实现

### 数据与工具层

- `Milvus`
  旅行知识库向量检索
- `travel-docs/`
  本地旅行知识文档
- `mcp_servers/travel_server.py`
  旅行 MCP mock 服务
- `app/tools/`
  本地工具实现
- `app/skills/`
  skill 封装与注册

## 技术栈

- `FastAPI`
- `LangChain`
- `LangGraph`
- `DashScope / OpenAI compatible chat model`
- `Milvus`
- `MCP`
- `Pydantic v2`
- `Loguru`

## 快速开始

### 环境要求

- Python `3.11+`
- Docker Desktop
- DashScope API Key

### 1. 安装依赖

```bash
git clone <your_repo_url>
cd TripBuddy

# 推荐
uv venv
uv sync

# 或者
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -e .
```

### 2. 配置 `.env`

```env
APP_NAME=TripBuddy Travel Agent
APP_VERSION=2.0.0
HOST=0.0.0.0
PORT=9900

DASHSCOPE_API_KEY=your_api_key
DASHSCOPE_MODEL=qwen-max
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4

MILVUS_HOST=localhost
MILVUS_PORT=19530

RAG_TOP_K=3
CHUNK_MAX_SIZE=800
CHUNK_OVERLAP=100

MCP_TRAVEL_URL=http://localhost:8005/mcp
MCP_CLS_URL=http://localhost:8003/mcp
MCP_MONITOR_URL=http://localhost:8004/mcp
```

### 3. 启动 Milvus

```bash
docker compose -f vector-database.yml up -d
```

### 4. 启动 MCP 服务

推荐至少启动旅行 MCP：

```bash
# travel mcp
.venv\Scripts\python mcp_servers/travel_server.py
```

如果你还想保留仓库里的旧 AIOps demo，也可以额外启动：

```bash
.venv\Scripts\python mcp_servers/cls_server.py
.venv\Scripts\python mcp_servers/monitor_server.py
```

### 5. 启动 FastAPI

开发模式推荐：

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 9900
```

生产/演示模式：

```bash
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```

### 6. 上传旅行知识文档

把 `travel-docs/` 里的 markdown 上传到知识库：

```powershell
Get-ChildItem travel-docs\*.md | ForEach-Object {
  Invoke-RestMethod -Uri "http://localhost:9900/api/upload" -Method Post -Form @{ file = Get-Item $_.FullName }
}
```

### 7. 访问服务

- Web UI: `http://localhost:9900`
- Swagger: `http://localhost:9900/docs`

## API

### `POST /api/chat`

统一聊天入口，返回完整结果。

请求示例：

```json
{
  "Id": "session-123",
  "Question": "帮我做一个4天重庆美食行程，预算3000",
  "conversationMode": "standard_search"
}
```

### `POST /api/chat_stream`

统一流式入口，SSE 输出 route 与 content。

请求示例：

```json
{
  "Id": "session-123",
  "Question": "东京和大阪哪个更适合带6岁孩子玩5天，预算1万，请给两个方案比较",
  "conversationMode": "deep_search"
}
```

### `POST /api/upload`

上传 markdown / txt 文档到知识库。

### `GET /api/chat/session/{session_id}`

获取会话历史。

### `POST /api/chat/clear`

清空 session 和记忆上下文。

### `GET /health`

健康检查。

## 搜索模式说明

### 标准搜索

先走语义意图识别，再按问题复杂度分流。

可能的执行目标：

- `knowledge`
- `trip_planning_workflow`
- `trip_replanning_workflow`
- `plan_execute`

### 深度搜索

不做常规分流，直接进入 `multi_agent`。

适合：

- 多目的地比较
- 多角色分析
- 多约束综合决策
- 需要更强解释链路的问题

## 当前项目目录

```text
TripBuddy/
├─ app/
│  ├─ api/
│  ├─ core/
│  ├─ models/
│  ├─ services/
│  │  ├─ travel_agent_service.py
│  │  ├─ travel_intent_service.py
│  │  ├─ travel_llm_service.py
│  │  ├─ travel_workflow_service.py
│  │  ├─ travel_multi_agent_service.py
│  │  ├─ travel_plan_execute_service.py
│  │  └─ travel_memory_service.py
│  ├─ skills/
│  └─ tools/
├─ mcp_servers/
│  ├─ travel_server.py
│  ├─ cls_server.py
│  └─ monitor_server.py
├─ static/
├─ travel-docs/
├─ tests/
└─ vector-database.yml
```

## 测试与验证

常用命令：

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 单元测试
pytest

# 类型/格式检查
ruff check .
ruff format .
```

## 可直接演示的场景

你可以直接在前端或接口里试下面这些问题：

### 知识问答

```text
6月第一次去成都适合怎么玩
```

### 旅行规划 Workflow

```text
帮我做一个4天重庆美食行程，预算3000
```

### 行程重规划 Workflow

```text
我后天去杭州，但预报下雨，原本西湖一日游怎么重排
```

### 深度搜索 / Multi-Agent

```text
东京和大阪哪个更适合带6岁孩子玩5天，预算1万，请给两个方案比较
```

### 标准搜索下的 Plan-and-Execute

```text
我周五到东京，周日晚上还要去大阪见朋友，预算有限，而且担心下雨，帮我把两城安排重新拆一下
```

## Legacy AIOps Demo

仓库中仍保留了一套旧的 AIOps 示例能力，用于演示历史方案与 MCP 对接方式：

- `/api/aiops`
- `mcp_servers/cls_server.py`
- `mcp_servers/monitor_server.py`

但当前 README 的主产品叙事已经完全切到旅行场景，AIOps 仅作为 legacy demo 保留。

## License

MIT
