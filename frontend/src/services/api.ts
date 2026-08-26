// API 请求层：所有后端调用统一走这里
// 为什么独立？1) 后端地址变更只改一处  2) 可统一加拦截器（鉴权/错误提示）
// 说明：流式聊天走 composables/useChat.ts 的 fetch（需要读流），
//       其余 REST 调用（Todo/Note/后续 Memory）都走这里的 axios。

import axios from 'axios'

// 开发期走 Vite proxy（/api → 127.0.0.1:8000），生产由 nginx 代理
const http = axios.create({
  baseURL: '/api',
  timeout: 60000, // 大模型回复可能较慢，给足 60s
})

// ===== 类型定义 =====

export interface ChatResponse {
  reply: string
  model: string
}

export interface Todo {
  id: number
  title: string
  due_time: string | null
  completed: boolean
  created_at: string
}

export interface Note {
  id: number
  content: string
  created_at: string
}

export interface Memory {
  id: number
  memory_type: string
  content: string
  importance: number
  created_at: string
  updated_at: string
}

export interface Conversation {
  id: number
  title: string
  created_at: string
  message_count: number
  last_message: string | null
}

export interface MessageOut {
  id: number
  role: string
  content: string
  created_at: string
}

// ===== 会话管理 =====

/** 会话列表（按创建时间倒序） */
export async function listConversations(): Promise<Conversation[]> {
  const { data } = await http.get<Conversation[]>('/conversations')
  return data
}

/** 某会话的全部历史消息（时间正序） */
export async function getConversationMessages(id: number): Promise<MessageOut[]> {
  const { data } = await http.get<MessageOut[]>(`/conversations/${id}/messages`)
  return data
}

/** 删除会话（含其消息） */
export async function deleteConversation(id: number): Promise<void> {
  await http.delete(`/conversations/${id}`)
}

// ===== 聊天（非流式，调试/兜底用） =====

/** 发送消息，获取玄枢的完整回复（非流式版） */
export async function sendChat(message: string): Promise<ChatResponse> {
  const { data } = await http.post<ChatResponse>('/chat', { message })
  return data
}

// ===== Todo =====

export async function getTodos(): Promise<Todo[]> {
  const { data } = await http.get<Todo[]>('/todos')
  return data
}

export async function createTodo(title: string, dueTime?: string): Promise<Todo> {
  const { data } = await http.post<Todo>('/todos', { title, due_time: dueTime ?? null })
  return data
}

export async function updateTodo(id: number, completed: boolean): Promise<Todo> {
  const { data } = await http.put<Todo>(`/todos/${id}`, { completed })
  return data
}

export async function deleteTodo(id: number): Promise<void> {
  await http.delete(`/todos/${id}`)
}

// ===== Note =====

export async function getNotes(keyword?: string): Promise<Note[]> {
  const { data } = await http.get<Note[]>('/notes', { params: keyword ? { q: keyword } : {} })
  return data
}

export async function createNote(content: string): Promise<Note> {
  const { data } = await http.post<Note>('/notes', { content })
  return data
}

export async function deleteNote(id: number): Promise<void> {
  await http.delete(`/notes/${id}`)
}

// ===== Memory（长期记忆） =====

export async function getMemories(): Promise<Memory[]> {
  const { data } = await http.get<Memory[]>('/memories')
  return data
}

export async function deleteMemory(id: number): Promise<void> {
  await http.delete(`/memories/${id}`)
}

// ===== 语音 =====

/** 上传录音文件（WAV）进行语音识别，返回识别文本 */
export async function transcribeAudio(file: Blob): Promise<string> {
  const form = new FormData()
  form.append('file', file, 'recording.wav')
  // 注意：不手动设置 Content-Type，浏览器自动生成带 boundary 的 multipart 头
  const { data } = await http.post<{ text: string }>('/voice/asr', form, {
    timeout: 30000,
  })
  return data.text
}

/** 文本转语音，返回音频 Blob（WAV） */
export async function synthesizeSpeech(text: string): Promise<Blob> {
  const { data } = await http.post<Blob>(
    '/voice/tts',
    { text },
    { responseType: 'blob', timeout: 60000 },
  )
  return data
}
