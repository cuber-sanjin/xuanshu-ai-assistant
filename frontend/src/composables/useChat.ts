// 组合式函数：聊天状态与 SSE 流式收发
// 为什么用组合式函数而不是 Pinia？
//   - 聊天状态只被 Home.vue 一个组件使用，无需全局状态库
//   - useChat 封装"发消息 + 解析 SSE + 增量渲染"，组件只关心 UI
//
// SSE 解析要点：
//   - 不能用浏览器原生 EventSource：它只支持 GET，聊天需要 POST body
//   - 用 fetch + ReadableStream 手动解析（社区标准做法）
//   - 帧格式：data: <json>\n\n，按空行切分，取 data: 前缀后的 JSON

import { ref } from 'vue'
import { getConversationMessages, synthesizeSpeech } from '../services/api'
import { bump, bumpByTool } from './useDataRefresh'
import { useToast } from './useToast'

// Toast 反馈（模块级单例）
const { error: toastError } = useToast()

export interface MessageItem {
  role: 'user' | 'assistant'
  content: string
  model?: string
  createdAt: string // 显示用时间戳（HH:MM）
  streaming?: boolean // 正在流式输出（用于显示光标动画）
}

/** 生成当前时间的显示字符串（HH:MM） */
function nowTime(): string {
  return new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** 后端 SSE 事件（与 docs/architecture.md 协议一致） */
interface SSEEvent {
  type: 'token' | 'tool_start' | 'tool_end' | 'done' | 'error'
  content?: string
  tool?: string
  args?: unknown
  result?: string
  message?: string
  conversation_id?: number
}

// 消息列表：组件通过 useChat() 拿到同一份响应式状态
const messages = ref<MessageItem[]>([])
const loading = ref(false)

// 工具执行状态条：tool_start 时显示"正在调用 XX…"，tool_end 时清除
const toolStatus = ref<string>('')

// 会话 ID：短期记忆的容器（Phase 5）
// 持久化到 localStorage：刷新页面后仍能延续同一会话
const CONV_KEY = 'xuan_shu_conversation_id'
const conversationId = ref<number | null>(null)

// 启动时从 localStorage 恢复会话
try {
  const saved = localStorage.getItem(CONV_KEY)
  if (saved) conversationId.value = Number(saved)
} catch {
  // localStorage 不可用（隐私模式等）时忽略，本次会话不持久化
}

/** 新建会话：清空消息与会话 ID */
function newConversation() {
  messages.value = []
  toolStatus.value = ''
  conversationId.value = null
  try {
    localStorage.removeItem(CONV_KEY)
  } catch {
    /* ignore */
  }
}

/** ISO 时间 → HH:MM（历史消息的时间戳展示） */
function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** 切换到历史会话：拉取消息记录并载入聊天窗口 */
async function selectConversation(id: number) {
  try {
    const msgs = await getConversationMessages(id)
    messages.value = msgs.map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
      createdAt: formatTime(m.created_at),
    }))
    conversationId.value = id
    try {
      localStorage.setItem(CONV_KEY, String(id))
    } catch {
      /* ignore */
    }
    toolStatus.value = ''
  } catch (err) {
    console.error('load conversation failed:', err)
  }
}

// 工具名 → 友好的中文展示（前端只做映射，不让用户看英文函数名）
const TOOL_LABELS: Record<string, string> = {
  get_current_time: '查询时间',
  calculator: '计算',
  create_todo: '记录待办',
  get_todos: '查询待办',
  complete_todo: '更新待办',
  delete_todo: '删除待办',
  save_note: '保存笔记',
  search_notes: '搜索笔记',
  delete_note: '删除笔记',
}

/** 发送消息：push 用户消息后走流式链路 */
async function sendMessage(text: string) {
  await stream(text, { pushUser: true })
}

/** 重新生成最后一条回复：移除该回复，重发其上一条用户消息 */
async function regenerate() {
  if (loading.value) return
  // 从尾部找最后一条 assistant 消息
  const lastAssistantIdx = [...messages.value]
    .reverse()
    .findIndex((m) => m.role === 'assistant')
  if (lastAssistantIdx === -1) return
  const idx = messages.value.length - 1 - lastAssistantIdx
  // 它之前的最后一条 user 消息文本（作为重发内容）
  let userText = ''
  for (let i = idx - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      userText = messages.value[i].content
      break
    }
  }
  if (!userText) return
  // 移除旧回复，重新流式生成（不再重复 push 用户消息）
  messages.value.splice(idx, 1)
  await stream(userText, { pushUser: false })
}

/** 核心流式逻辑：SSE 接收玄枢回复（pushUser=true 时先展示用户消息） */
async function stream(text: string, opts?: { pushUser?: boolean }) {
  // 1.（可选）立即显示用户消息（带时间戳）
  if (opts?.pushUser !== false) {
    messages.value.push({ role: 'user', content: text, createdAt: nowTime() })
  }

  // 2. 创建"占位"助手消息，流式增量写入 content
  const assistantMsg: MessageItem = {
    role: 'assistant',
    content: '',
    createdAt: nowTime(),
    streaming: true,
  }
  messages.value.push(assistantMsg)
  loading.value = true

  try {
    // 3. POST /api/chat/stream，读取响应体流（携带 conversation_id）
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        conversation_id: conversationId.value ?? undefined,
      }),
    })
    if (!resp.ok || !resp.body) {
      throw new Error(`HTTP ${resp.status}`)
    }

    // 4. 逐块解析 SSE：TextDecoder 处理 UTF-8（中文多字节安全）
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE 帧以空行 \n\n 分隔；最后一段可能不完整，留到下一轮
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''

      for (const frame of frames) {
        const dataLine = frame.split('\n').find((l) => l.startsWith('data: '))
        if (!dataLine) continue // retry: / 注释行等跳过
        const payload = dataLine.slice(6)
        if (payload === '[DONE]') continue

        try {
          handleEvent(JSON.parse(payload) as SSEEvent, assistantMsg)
        } catch {
          // 忽略畸形帧，不中断整个流
        }
      }
    }
  } catch (err) {
    console.error('stream failed:', err)
    assistantMsg.content =
      assistantMsg.content || `抱歉，连接失败：${(err as Error).message}`
    toastError('发送失败，请检查后端服务是否在运行')
  } finally {
    // 5. 收尾：去掉光标，解除 loading
    assistantMsg.streaming = false
    loading.value = false

    // 6. 可选自动播报：开启后自动朗读最后一条回复（TTS）
    if (autoSpeak.value && assistantMsg.content) {
      speak(assistantMsg.content)
    }
  }
}

// ===== 自动播报（Phase 8 可选开关） =====
const autoSpeak = ref(false)

/** 朗读一段文本（复用 TTS 接口；失败静默，不打扰主流程） */
async function speak(text: string) {
  try {
    const blob = await synthesizeSpeech(text)
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.onended = () => URL.revokeObjectURL(url)
    audio.onerror = () => URL.revokeObjectURL(url)
    await audio.play()
  } catch (err) {
    console.warn('auto speak failed:', err)
  }
}
/** 按事件类型更新消息 */
function handleEvent(evt: SSEEvent, msg: MessageItem) {
  switch (evt.type) {
    case 'token':
      msg.content += evt.content ?? ''
      break
    case 'tool_start':
      // 显示状态条：玄枢正在调用工具（不展示模型内部推理过程，只给用户可读状态）
      toolStatus.value = `玄枢正在${TOOL_LABELS[evt.tool ?? ''] ?? evt.tool ?? '处理'}…`
      break
    case 'tool_end':
      // 工具执行完成，清除状态条（若连续调多个工具，会在下一个 tool_start 再显示）
      toolStatus.value = ''
      // 工具可能改写了数据（待办/记忆）→ 通知对应面板刷新
      bumpByTool(evt.tool)
      break
    case 'done':
      // 记录后端返回的会话 ID（首次对话时后端创建）
      if (evt.conversation_id) {
        conversationId.value = evt.conversation_id
        try {
          localStorage.setItem(CONV_KEY, String(evt.conversation_id))
        } catch {
          /* ignore */
        }
      }
      // 自动记忆提取（save_memory 节点）与首条消息自动标题都在本轮完成 → 刷新
      bump('memory')
      bump('conversation')
      break
    case 'error':
      msg.content = msg.content || `出错：${evt.message ?? '未知错误'}`
      break
  }
}

export function useChat() {
  return {
    messages,
    loading,
    toolStatus,
    conversationId,
    autoSpeak,
    sendMessage,
    regenerate,
    newConversation,
    selectConversation,
  }
}
