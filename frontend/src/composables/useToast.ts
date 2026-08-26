// Toast 全局反馈：成功/错误/提示的统一视觉反馈
//
// 为什么需要？
//   之前 ASR/TTS 失败只在小字提示、删除会话无确认反馈、发送失败只改气泡文本——
//   用户对"发生了什么/是否成功"缺乏感知。统一 Toast 一次建设，多处受益。
//
// 设计：模块级响应式数组（与 useChat/useRecorder 同模式），
//       任何组件调 useToast() 拿到同一份状态，push 后 4s 自动消失。

import { ref } from 'vue'

export type ToastType = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  type: ToastType
  message: string
}

const toasts = ref<ToastItem[]>([])
let seq = 0

/** 自动消失时长（ms） */
const AUTO_DISMISS_MS = 4000

function pushToast(type: ToastType, message: string) {
  const id = ++seq
  toasts.value.push({ id, type, message })
  // 定时自动移除（不做去重：同类错误连续出现时保留最新观感即可）
  setTimeout(() => removeToast(id), AUTO_DISMISS_MS)
}

function removeToast(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

export function useToast() {
  return {
    toasts,
    success: (message: string) => pushToast('success', message),
    error: (message: string) => pushToast('error', message),
    info: (message: string) => pushToast('info', message),
    remove: removeToast,
  }
}
