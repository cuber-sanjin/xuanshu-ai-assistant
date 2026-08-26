# 玄枢架构文档（Phase 1 快照）

> 本文档随开发推进持续更新。Phase 1 结束时的架构快照如下。

## 1. 总体架构

```text
Vue 3 前端 (Vite dev server :5173)
        │  HTTP (fetch/axios) 走 /api 前缀
        ▼  Vite proxy 转发
FastAPI 后端 (uvicorn :8000)
        │
        ▼  ChatOpenAI (OpenAI 兼容接口)
阿里云百炼 (DashScope) Qwen 模型
```

Phase 1 是最简链路：前端 → 后端 → 单次 LLM 调用 → 返回完整回复（非流式）。
后续 Phase 依次替换链路中间环节：

| Phase | 链路变化 |
|-------|---------|
| 2 | 后端改为调用 LangGraph（START→agent→END） |
| 3 | 聊天接口改为 SSE 流式（token/done/error 事件） |
| 4 | ReAct 工具循环（时间/计算器/Todo/Note）+ SQLite ✅ |
| 5-6 | 加入短期/长期记忆 |
| 7-8 | 语音链路 ASR/TTS |
| 9 | 前端打磨（Markdown/动画/波形）✅ |
| 10 | Docker 部署（nginx 托管 + 反代）✅ |
| R | 向量检索 RAG（语义+词法 RRF 混合召回）✅ |

## 3. SSE 事件协议（Phase 3 生效）

所有事件均为 `data: <json>\n\n` 帧：

```json
{"type": "token", "content": "今天"}          // 逐字输出
{"type": "tool_start", "tool": "get_todos"}   // Phase 4：工具开始（前端显示状态条）
{"type": "tool_end", "tool": "get_todos", "result": "..."}  // Phase 4：工具结束
{"type": "done"}                              // 流结束
{"type": "error", "message": "..."}           // 出错
```

后端实现：`graph.astream_events(version="v2")` 过滤 `on_chat_model_stream`，
跳过 `tool_call_chunks` 增量；响应头 `Cache-Control: no-cache` + `X-Accel-Buffering: no`（防 nginx 缓冲）。

前端实现：`fetch` + `ReadableStream` 手动解析（EventSource 只支持 GET），
`TextDecoder` 处理 UTF-8 分块边界，按 `\n\n` 切帧。

## 4. 模块职责

### 后端

| 模块 | 职责 | 关键点 |
|------|------|--------|
| `app/main.py` | 应用入口 | 路由注册、CORS、lifespan 建表+种子用户 |
| `app/config.py` | 配置中心 | 全项目唯一读环境变量处；API Key 优先级：`AI_CHAT_API_KEY` > `DASHSCOPE_API_KEY` |
| `app/api/chat.py` | 聊天路由 | POST /api/chat（非流式）+ POST /api/chat/stream（SSE，含 tool 事件） |
| `app/api/todo.py` / `note.py` | 资源路由 | Todo/Note REST CRUD（同步 def 端点，FastAPI 自动线程池） |
| `app/agent/*` | LangGraph 层 | state/nodes/prompts/graph（ReAct 循环，见 docs/agent.md） |
| `app/tools/*` | 工具层 | 时间/计算器/Todo/Note，docstring 即 LLM 说明书 |
| `app/database/*` | 数据层 | SQLAlchemy + SQLite（WAL），init_db 建表+默认用户 |
| `app/services/llm.py` | LLM 工厂 | 唯一创建 ChatOpenAI 处；切模型只改 .env |
| `app/schemas/chat.py` | 请求/响应模型 | 字段校验 + 自动生成 Swagger 文档 |

### 前端

| 模块 | 职责 |
|------|------|
| `src/views/Home.vue` | 品牌区 + 聊天区布局，串联 useChat |
| `src/composables/useChat.ts` | 消息状态 + SSE 流式收发（fetch/ReadableStream 解析） |
| `src/components/ChatWindow.vue` | 消息列表、空状态引导、流式自动滚动 |
| `src/components/ChatMessage.vue` | 单条消息气泡（含流式光标） |
| `src/components/InputBox.vue` | 输入框 + 发送按钮，回车发送 |
| `src/services/api.ts` | axios 封装（后续 Todo/Note 用；流式聊天走 useChat） |
| `vite.config.ts` | /api 代理到 8000，开发期免 CORS |

## 4. 配置说明

- 后端环境变量（见 `backend/.env.example`）：`AI_CHAT_API_KEY` / `DASHSCOPE_API_KEY`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_TEMPERATURE`、`SERVER_PORT`
- API Key 优先级：**系统环境变量 `AI_CHAT_API_KEY`** > 环境变量/.env 的 `DASHSCOPE_API_KEY`
- 模型默认 `qwen-plus`，改 `.env` 的 `LLM_MODEL` 即可切换

## 5. 运行方式

```bash
# 后端
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev        # http://localhost:5173
```

- Swagger 调试：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 6. 企业真实场景对照

- **路由层/服务层分离**：真实企业 Agent 服务同样分层，API 只暴露稳定契约，内部实现可演进
- **LLM 抽象层**：企业中切换模型供应商是常态（成本/合规/容量），集中封装是标准做法
- **配置外置**：API Key 永不入库，通过环境变量/配置中心管理，本项目的 .env 即其简化版
- **统一异常兜底**：LLM 是外部依赖，必然失败，统一转 5xx + 日志是企业服务的必备能力
