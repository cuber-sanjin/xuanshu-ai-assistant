# Agent 设计文档（Phase 2 快照）

## 1. 图结构

```text
START → agent → END
```

| 元素 | 文件 | 职责 |
|------|------|------|
| State | `app/agent/state.py` | 图状态：`messages: Annotated[list, add_messages]` |
| 节点 | `app/agent/nodes.py` | `agent_node`：system 提示词 + 历史 → LLM → AI 回复 |
| 提示词 | `app/agent/prompts.py` | 玄枢人设（沉稳、古风科技感、称用户"主人"） |
| 组装 | `app/agent/graph.py` | StateGraph 接线 + 编译，`lru_cache` 进程内单例 |

## 2. 关键机制：add_messages reducer

`Annotated[list, add_messages]` 是 LangGraph 消息合并器：

- 节点返回 `{"messages": [new_msg]}` 时，**追加**而不是覆盖整个列表
- 保证多节点、多轮之间消息不丢、不互相覆盖
- 这是 LangGraph State 与普通 dict 的本质区别：**每个字段可以声明自己的合并策略**

## 3. 数据流（一次对话）

```text
请求: {"messages": [HumanMessage("你好")]}
  ↓
START
  ↓
agent_node:
  messages = [SystemMessage(人设)] + [HumanMessage("你好")]
  response = await llm.ainvoke(messages)
  return {"messages": [AIMessage("...")]}   ← add_messages 追加
  ↓
END
响应: {"messages": [HumanMessage, AIMessage]}
```

## 4. 为什么用 LangGraph（面试回答素材）

1. **显式状态机**：节点 + 边定义清晰的执行拓扑，可画图、可单测、可追踪，不是黑盒 API 调用
2. **预留扩展插槽**：Phase 3 加条件边（要不要调工具）、Phase 5/6 加记忆节点，只改图接线，agent_node 不变
3. **生产可观测**：`graph.get_graph()` 可导出拓扑；后续可用 `astream_events` 做流式与追踪
4. **团队协作**：节点天然按职责拆分，不同人开发不同节点，冲突少

## 5. 后续演进（此图为骨架，逐 Phase 长新器官）

```text
Phase 4:  START → agent → [tool_calls?] → tools → agent → … → END   （ReAct 循环 ✅ 已完成）
Phase 5:  START → load_memory(短期历史) → agent → ... → save_memory → END
Phase 6:  + load_memory(长期记忆注入) + save_memory(记忆提取)
```

## 6. Phase 4：工具调用（ReAct 循环）

图结构：
```text
START → agent ──(tool_calls?)──→ tools → agent ──(再判断)──→ …
                 └──(无工具)──→ END
```

关键机制：
1. **bind_tools**：`llm.bind_tools(ALL_TOOLS)` 把工具 schema（名称+参数+说明）注入模型 API，
   模型据此输出结构化 `tool_calls`（工具名 + 参数 JSON）——模型**决定**调什么，Python **执行**
2. **ToolNode**：langgraph.prebuilt 内置节点，自动执行 tool_calls 并返回 ToolMessage
3. **条件边**：`should_continue` 检查最后一条消息是否含 tool_calls，决定去 tools 还是 END
4. **循环安全**：recursion_limit（默认 25）防止 agent-tools 死循环
5. **动态日期注入**：system prompt 拼接当天日期，模型才能正确换算"明天/后天"
   （不注入会幻觉出错误日期，实测编出过 2024 年）

工具清单（ALL_TOOLS，见 app/tools/__init__.py）：
- get_current_time：北京时间
- calculator：AST 白名单安全求值（拒绝 eval 注入）
- create_todo / get_todos / complete_todo / delete_todo
- save_note / search_notes / delete_note
