# 玄枢 API 文档（Phase 4 快照）

> 完整 OpenAPI 文档见运行后 http://localhost:8000/docs（Swagger UI，可直接调试）

## 1. 聊天

### POST /api/chat（非流式）

请求：
```json
{ "message": "你好" }
```
响应 200：
```json
{ "reply": "主人，有何吩咐？", "model": "qwen-plus" }
```

### POST /api/chat/stream（SSE 流式）

请求同上。响应为 `text/event-stream`，事件序列（data: JSON 帧）：

| type | 字段 | 含义 |
|------|------|------|
| token | content | LLM 输出增量（逐字） |
| tool_start | tool, args | 工具开始执行 |
| tool_end | tool, result | 工具执行完成（结果截断 200 字） |
| done | - | 流结束 |
| error | message | 出错 |

示例（"现在几点了？"）：
```
data: {"type":"tool_start","tool":"get_current_time","args":{}}
data: {"type":"tool_end","tool":"get_current_time","result":"2026-08-22 10:04:20 星期六"}
data: {"type":"token","content":"现在是："}
data: {"type":"token","content":"2026年8月22日"}
data: {"type":"done"}
```

## 2. 待办 Todo

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/todos | 获取全部待办（未完成在前） |
| POST | /api/todos | 创建 `{title, due_time?}` |
| PUT | /api/todos/{id} | 更新 `{completed}` |
| DELETE | /api/todos/{id} | 删除 |

Todo 对象：`{id, title, due_time, completed, created_at}`

## 3. 笔记 Note

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/notes?q=关键词 | 获取笔记（可选关键词过滤） |
| POST | /api/notes | 创建 `{content}` |
| DELETE | /api/notes/{id} | 删除 |

Note 对象：`{id, content, created_at}`

## 3.5 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/conversations | 会话列表（标题/消息数/最后消息预览，倒序） |
| GET | /api/conversations/{id}/messages | 某会话全部历史消息（时间正序） |
| DELETE | /api/conversations/{id} | 删除会话（级联删消息，204） |

说明：新会话首条消息自动取前 20 字作为标题（`maybe_set_title`）。

## 4. 语音

### POST /api/voice/asr（语音转文字）

请求：`multipart/form-data`，字段 `file`（WAV 音频，≤8MB）

响应 200：
```json
{ "text": "玄枢，现在几点" }
```

### POST /api/voice/tts（语音合成）

请求：
```json
{ "text": "主人，待办已记录。", "voice": "Cherry" }
```
- `text`：1~500 字（超长被 Pydantic 422 拒绝）
- `voice`：可选，Cherry/Serena/Ethan，空用默认

响应：`audio/wav` 音频字节（前端 `<audio>` 播放）。
注意：实测 qwen3-tts-flash 无论请求 mp3 还是 wav 都返回 WAV（RIFF 头），故固定 wav。

## 5. 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 `{status: "ok"}` |

## 6. 错误处理

- 422：Pydantic 校验失败（字段缺失/类型错误/空字符串）
- 404：资源不存在
- 500：LLM 调用失败等内部错误（detail 带说明）
