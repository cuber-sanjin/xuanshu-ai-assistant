# 记忆系统文档（Phase 5 快照）

## 1. 两层记忆的定位

| 层次 | 载体 | 生命周期 | 作用 |
|------|------|---------|------|
| 短期记忆 | `conversations` / `messages` 表 | 一次会话（可跨请求） | 多轮对话上下文 |
| 长期记忆 | `memories` 表（Phase 6） | 永久 | 用户画像/偏好/目标 |

一句话区分（面试答案）：
> **短期记忆回答"我们刚才聊了什么"，长期记忆回答"我该怎样了解这个用户"。**

## 2. 短期记忆实现（Phase 5）

### 数据流（一次请求）

```text
请求: {message: "帮我安排计划", conversation_id: 6}
  ↓
1. get_or_create_conversation(db, 6)   # 获取或创建会话
2. load_history(db, 6)                 # 加载最近 20 条历史（user/assistant 文本）
3. save_message(db, 6, "user", msg)    # 持久化本次用户消息
4. graph.astream_events({messages: [历史..., HumanMessage(本次)]})
  ↓
5. save_message(db, 6, "assistant", 回复)  # 持久化助手回复
6. done 事件返回 conversation_id
```

### 关键设计决策

1. **为什么不用 LangGraph checkpointer？**
   - 学习项目追求"看得见"：历史自己管理，每条消息去向清晰
   - 企业现实：历史要同时服务对话上下文 + 前端展示 + 审计，业务层单源管理更常见
2. **为什么只存 user/assistant 文本？**
   - 工具调用过程（tool_call/ToolMessage）不持久化——结果已由助手总结进回复
   - 重放工具调用浪费 token 且可能副作用重放（如重复建待办）
3. **窗口控制**：`MAX_HISTORY_MESSAGES = 20`（约 10 轮）。真实企业用 token 计数
   精确裁剪（tiktoken），避免超上下文窗口
4. **async 阻塞规避**：SSE 端点内所有同步 DB 操作用 `run_in_threadpool` 包裹，
   否则事件循环被阻塞，所有并发流全卡住

### 前端会话管理

- `conversationId` 存 localStorage（刷新不丢会话）
- `done` 事件携带 `conversation_id`（首次对话时后端创建）
- 顶部"新对话"按钮：清空消息 + 会话 ID

## 3. 长期记忆（Phase 6 ✅）

### 数据结构

```text
memories 表:
  id / user_id / memory_type / content / importance(0~1) / created_at / updated_at

memory_type: preference(偏好) / profile(资料) / goal(目标) / learning(学习) / habit(习惯) / important_event(重要事件)
```

### 双通道写入（防重复：内容去重）

| 通道 | 触发时机 | 实现 |
|------|---------|------|
| 自动提取 | 每轮对话结束（save_memory 节点） | extractor LLM 判断 + 落库 |
| 主动记忆 | 用户说"记住 XX" | Agent 调用 remember 工具 |

### 图内流程

```text
START → load_memory（语义/importance 取 top5 注入 system prompt，Phase R 起）
      → agent（带着"对用户的了解"回答）
      → tools（ReAct 循环）
      → save_memory（提取器判断本轮是否产生新记忆）
      → END
```

## 3.5 向量检索 RAG（Phase R ✅）

长期记忆与笔记升级为"语义优先 + 词法兜底"的混合检索：

### 架构

```text
写入：save_memories / save_note → embed_texts(百炼 text-embedding-v3, 1024维)
     → embeddings 表 (user_id, entity_type, entity_id, vector_json)  UPSERT
检索：查询文本 → embed_text(带缓存) → 余弦 top-20
     ∥ SQL LIKE top-20
     → RRF(k=60) 融合 → top-k
```

### 关键设计（面试点）

1. **RRF 融合优于加权求和**：免调参、两路排名尺度无关、共命中文档自动加权
2. **零新依赖**：向量存 SQLite JSON 列 + 纯 Python 余弦（个人量级毫秒级）；
   数据量 >1 万条时再引 ANN（sqlite-vec/FAISS），接口可无痛替换
3. **fail-open 三层容错**：
   - `EMBEDDING_ENABLED=false` 默认关，行为与旧版完全一致
   - 嵌入 API 失败 → 读路径降级（笔记→LIKE、记忆→importance）
   - 写入路径失败仅告警，绝不阻断；存量数据用 backfill 脚本兜底：
     `EMBEDDING_ENABLED=true python -m app.scripts.backfill_embeddings all`
4. **查询向量缓存**：同一 query 不重复调嵌入 API（256 条上限）
5. **批量上限**：百炼 text-embedding-v3 单请求 ≤10 条（backfill 按 10 分批）

### 文件

- `app/services/embeddings.py`：嵌入服务（openai 官方 SDK 直连，兼容端点实测正常；
  langchain-openai 新版 input 对象格式百炼不识别，故未用）
- `app/rag/vector_store.py`：向量存取 + 纯 Python 余弦 + top_k
- `app/rag/hybrid.py`：RRF 融合 + 笔记/记忆混合检索（`search_notes_hybrid` /
  `recall_memories_hybrid` / `search_memories_hybrid` / 增强版 `get_relevant_memories`）
- `app/scripts/backfill_embeddings.py`：存量回填（幂等断点续跑）
- `embeddings` 表：`(user_id, entity_type, entity_id, vector)` 唯一约束防重复

### 提取器（extractor.py）

- 专用快速模型 `qwen-flash`（EXTRACTOR_MODEL，可覆盖），temperature=0.1
- `with_structured_output(MemoryExtraction)`：模型必须输出 Pydantic 结构
  `{should_save: bool, items: [{memory_type, content, importance}]}`
- 判断标准：个人资料/目标/学习方向/明确"记住"→ 保存；寒暄/天气/一次性提问 → 不保存
- **提取失败降级为不保存**，绝不阻断主流程

### 踩过的坑（重要）

1. **提取模型输出泄漏**：`astream_events` 会捕获图内**所有**模型的流事件，
   extractor 的 JSON 输出曾以 token 形式推给用户。修复：只转发
   `metadata.langgraph_node == "agent"` 的 token 事件
2. **模型不把记忆当事实**：最初注入格式不够强硬，模型把记忆当"猜测"，
   回答"暂未记住"。修复：标注"以下是已确认的事实"+ 使用原则明确
   "不得说不知道/未记住"

### 前端

- `MemoryPanel.vue`：右侧面板展示记忆列表（类型标签 + 内容 + 删除）
- REST：GET /api/memories、DELETE /api/memories/{id}
